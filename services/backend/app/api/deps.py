from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Optional

from app.core.logger import logger
from app.core.config import settings
from app.core.redis import redis_client
from app.db.session import get_db
from app.models.user import User
from app.schemas.token import TokenPayload

class OAuth2PasswordBearerWithCookie(OAuth2PasswordBearer):
    async def __call__(self, request: Request) -> Optional[str]:
        # Сначала ищем в заголовках (стандартное поведение)
        authorization: str = request.headers.get("Authorization")
        
        if not authorization:
            # Если нет в заголовках, ищем в куках
            authorization = request.cookies.get("access_token")
            if authorization:
                # Если нашли в куках, возвращаем его
                # OAuth2PasswordBearer ожидает просто строку токена (без Bearer)
                return authorization
            
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            else:
                return None
        
        # Если есть заголовок, используем родительский метод для парсинга "Bearer <token>"
        return await super().__call__(request)

reusable_oauth2 = OAuth2PasswordBearerWithCookie(
    tokenUrl="/api/auth/login"
)

async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(reusable_oauth2)
) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (JWTError, Exception) as e:
        logger.error(f"JWT decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check denylist in Redis
    if token_data.jti:
        try:
            is_revoked = await redis_client.exists(f"denylist:{token_data.jti}")
            if is_revoked:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except HTTPException:
            raise
        except Exception:
            # Redis is down
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service temporarily unavailable, please try later"
            )

    if token_data.sub is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    result = await db.execute(
        select(User)
        .where(User.id == token_data.sub)
        .options(selectinload(User.role_obj))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

async def get_current_active_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    if not current_user.role_obj or current_user.role_obj.name != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="The user doesn't have enough privileges"
        )
    return current_user
