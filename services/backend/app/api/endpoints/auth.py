from fastapi import APIRouter, Depends, HTTPException, Response, Request
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Any
from jose import jwt, JWTError

from app.api import deps
from app.core import security
from app.core.config import settings
from app.core.redis import redis_client
from app.db.session import get_db
from app.models.user import User
from app.models.role import Role
from app.schemas.user import User as UserSchema, UserCreate, UserUpdate
from app.schemas.token import Token, TokenPayload

router = APIRouter(
    tags=["auth"],
    responses={404: {"description": "Not found"}},
)

async def get_role_by_name(db: AsyncSession, name: str) -> Role:
    result = await db.execute(select(Role).where(Role.name == name))
    return result.scalar_one_or_none()

@router.patch(
    "/me",
    response_model=UserSchema,
    summary="Обновить профиль",
    description="Позволяет текущему пользователю изменить свой email, имя пользователя или пароль. При смене email проверяется его уникальность.",
    response_description="Данные обновленного пользователя."
)
async def update_user_me(
    *,
    db: AsyncSession = Depends(get_db),
    user_in: UserUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    if user_in.email is not None and user_in.email != current_user.email:
        result = await db.execute(select(User).where(User.email == user_in.email))
        user = result.scalar_one_or_none()
        if user:
            raise HTTPException(
                status_code=400,
                detail="The user with this email already exists in the system.",
            )
        current_user.email = user_in.email
    
    if user_in.username is not None:
        current_user.username = user_in.username
    
    if user_in.password is not None:
        current_user.hashed_password = security.get_password_hash(user_in.password)
    
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    
    # Reload with role_obj
    result = await db.execute(
        select(User)
        .where(User.id == current_user.id)
        .options(selectinload(User.role_obj))
    )
    return result.scalar_one()

@router.post(
    "/register",
    response_model=UserSchema,
    summary="Регистрация",
    description="Создание новой учётной записи пользователя. По умолчанию назначается роль 'user'.",
    response_description="Данные созданного пользователя."
)
async def register(
    *,
    db: AsyncSession = Depends(get_db),
    user_in: UserCreate
) -> Any:
    try:
        result = await db.execute(select(User).where(User.email == user_in.email))
        user = result.scalar_one_or_none()
        if user:
            raise HTTPException(
                status_code=400,
                detail="The user with this email already exists in the system.",
            )
        
        role = await get_role_by_name(db, "user")
        if not role:
            from app.core.logger import logger
            logger.error("CRITICAL: Role 'user' not found in database. Registration failed.")
            raise HTTPException(
                status_code=500,
                detail="System configuration error: default role not found."
            )
        
        user = User(
            username=user_in.username,
            email=user_in.email,
            hashed_password=security.get_password_hash(user_in.password),
            is_active=True,
            role_id=role.id
        )
        db.add(user)
        await db.commit()
        
        # Eagerly load role_obj for serialization
        result = await db.execute(
            select(User)
            .where(User.id == user.id)
            .options(selectinload(User.role_obj))
        )
        user = result.scalar_one()
        
        # Создаем токены и устанавливаем куки сразу после регистрации
        access_token = security.create_access_token(user.id)
        refresh_token = security.create_refresh_token(user.id)
        
        response = JSONResponse(UserSchema.model_validate(user).model_dump())
        
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="lax",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/",
        )
        
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="strict",
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            path="/api/auth",
        )
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        from app.core.logger import logger
        logger.exception(f"Error during user registration: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal Server Error during registration: {str(e)}"
        )

from fastapi_limiter.depends import RateLimiter

@router.post(
    "/login",
    tags=["auth"],
    summary="Войти в систему",
    description=(
        "Принимает логин и пароль, возвращает JWT-токен. "
        "Пароль передаётся в открытом виде — предполагается, что соединение защищено TLS. "
        "При ошибке возвращается 401 с пояснением: неверный пароль, пользователь не найден и т.д."
    ),
    response_description="Успешная аутентификация. Токен действителен 24 часа.",
    dependencies=[Depends(RateLimiter(times=5, seconds=60))]
)
async def login(
    request: Request,
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    from app.core.logger import logger
    
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "unknown")
    
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        logger.warning(f"Failed login attempt for email: {form_data.username} from IP: {ip}, UA: {ua}")
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        logger.warning(f"Login attempt for inactive user: {form_data.username} from IP: {ip}, UA: {ua}")
        raise HTTPException(status_code=400, detail="Inactive user")
    
    logger.info(f"Successful login for user: {user.email} from IP: {ip}, UA: {ua}")
    
    access_token = security.create_access_token(user.id)
    refresh_token = security.create_refresh_token(user.id)
    
    response = JSONResponse({
        "token_type": "bearer",
    })
    
    # Access Token в HttpOnly куку (BFF pattern)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    
    # Refresh Token в HttpOnly куку
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/api/auth",
    )
    
    return response

@router.post(
    "/refresh",
    response_model=Token,
    summary="Обновить токен доступа",
    description="Использует refresh_token из кук для получения нового access_token. Старый refresh_token аннулируется и заносится в denylist.",
    response_description="Новый токен доступа."
)
async def refresh(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Any:
    # Try to get refresh token from Authorization header first (preferred for CSRF protection)
    auth_header = request.headers.get("Authorization")
    refresh_token = None
    if auth_header and auth_header.startswith("Bearer "):
        refresh_token = auth_header.split(" ")[1]
    
    # Fallback to cookie if not in header
    if not refresh_token:
        refresh_token = request.cookies.get("refresh_token")
        if refresh_token:
            # Basic CSRF protection for cookie fallback: check Origin or Referer
            origin = request.headers.get("origin")
            referer = request.headers.get("referer")
            
            # Simple check: at least one must be present and match our allowed origins if in production
            if not settings.DEBUG:
                allowed = False
                for allowed_origin in settings.CORS_ORIGINS:
                    if (origin and origin.startswith(allowed_origin)) or \
                       (referer and referer.startswith(allowed_origin)):
                        allowed = True
                        break
                if not allowed:
                    raise HTTPException(
                        status_code=403, 
                        detail="CSRF protection: Invalid Origin or Referer for cookie-based refresh"
                    )
    
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")
    
    try:
        payload = jwt.decode(
            refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
        if payload.get("type") != "refresh" or not token_data.jti or not token_data.sub or not token_data.exp:
            raise HTTPException(status_code=401, detail="Invalid token type or missing JTI/sub/exp")
        
        # Check denylist in Redis
        try:
            is_revoked = await redis_client.exists(f"denylist:{token_data.jti}")
            if is_revoked:
                response = JSONResponse(status_code=401, content={"detail": "Token has been revoked"})
                response.delete_cookie("refresh_token", path="/api/auth", samesite="strict")
                return response
        except Exception:
            # Redis is down
            raise HTTPException(status_code=503, detail="Service temporarily unavailable, please try later")

    except jwt.ExpiredSignatureError:
        response = JSONResponse(status_code=401, content={"detail": "Refresh token expired"})
        response.delete_cookie("refresh_token", path="/api/auth", samesite="strict")
        return response
    except HTTPException:
        raise
    except (JWTError, Exception):
        response = JSONResponse(status_code=401, content={"detail": "Could not validate credentials"})
        response.delete_cookie("refresh_token", path="/api/auth", samesite="strict")
        return response
    
    result = await db.execute(select(User).where(User.id == token_data.sub))
    user = result.scalar_one_or_none()
    if not user:
        response = JSONResponse(status_code=404, content={"detail": "User not found"})
        response.delete_cookie("refresh_token", path="/api/auth", samesite="strict")
        return response
    if not user.is_active:
        response = JSONResponse(status_code=400, content={"detail": "Inactive user"})
        response.delete_cookie("refresh_token", path="/api/auth", samesite="strict")
        return response
    
    new_access_token = security.create_access_token(user.id)
    new_refresh_token = security.create_refresh_token(user.id)
    
    # Revoke old jti in Redis
    from datetime import datetime, timezone
    try:
        ttl = int(token_data.exp - datetime.now(timezone.utc).timestamp())
        if ttl > 0:
            await redis_client.set(f"denylist:{token_data.jti}", user.id, ex=ttl)
    except Exception:
        # Redis is down
        raise HTTPException(status_code=503, detail="Service temporarily unavailable, please try later")
    
    response = JSONResponse({
        "token_type": "bearer",
    })
    
    # Access Token в HttpOnly куку (BFF pattern)
    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/api/auth",
    )
    return response

@router.post(
    "/logout",
    summary="Выйти из системы",
    description="Аннулирует текущий сеанс, удаляя refresh_token из кук и добавляя его в список отозванных (denylist) в Redis.",
    response_description="Сообщение об успешном выходе."
)
async def logout(
    request: Request,
    response: Response
):
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        try:
            payload = jwt.decode(
                refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            token_data = TokenPayload(**payload)
            if payload.get("type") == "refresh" and token_data.jti and token_data.sub and token_data.exp:
                from datetime import datetime, timezone
                try:
                    ttl = int(token_data.exp - datetime.now(timezone.utc).timestamp())
                    if ttl > 0:
                        await redis_client.set(f"denylist:{token_data.jti}", token_data.sub, ex=ttl)
                except Exception:
                    # Redis is down, but we continue logout (clear cookie)
                    pass
        except Exception:
            pass

    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=not settings.DEBUG,
        samesite="strict",
        path="/api/auth",
    )
    return {"detail": "Successfully logged out"}

@router.get(
    "/me",
    response_model=UserSchema,
    summary="Получить профиль",
    description="Возвращает информацию о текущем авторизованном пользователе.",
    response_description="Данные текущего пользователя."
)
async def read_user_me(
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    return current_user
