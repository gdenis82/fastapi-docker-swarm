from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

from app.api import deps
from app.db.session import get_db
from app.models.user import User
from app.models.role import Role
from app.schemas.user import User as UserSchema

router = APIRouter(
    tags=["admin"],
    responses={404: {"description": "Not found"}},
)

# Описание тега: Панель администратора: управление пользователями и системные настройки.

@router.get(
    "/users",
    response_model=Any,
    summary="Список пользователей",
    description="Возвращает список всех пользователей системы с поддержкой фильтрации по имени, роли, а также с пагинацией и сортировкой. Доступно только администраторам.",
    response_description="Список пользователей и общее количество записей."
)
async def read_users(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: str = Query(None),
    role: str = Query(None),
    sort: str = Query("name:asc"),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """
    Retrieve users for admin dashboard.
    """
    query = select(User)
    
    # Filtering
    if search:
        search_filter = f"%{search}%"
        filters = [
            User.username.ilike(search_filter),
            User.email.ilike(search_filter),
        ]
        query = query.where(or_(*filters))
    
    if role:
        query = query.join(User.role_obj).where(Role.name == role)
    
    # Count total users after filtering but before pagination and options
    total_query = select(func.count(User.id)).select_from(query.subquery())
    total_result = await db.execute(total_query)
    total = total_result.scalar() or 0
    
    # Add relations and sorting
    query = query.options(selectinload(User.role_obj))
    
    if sort and ":" in sort:
        try:
            field, order = sort.split(":")
            attr = getattr(User, field, User.username)
            if order == "desc":
                query = query.order_by(attr.desc())
            else:
                query = query.order_by(attr.asc())
        except Exception:
            query = query.order_by(User.username.asc())
    else:
        query = query.order_by(User.username.asc())
    
    # Pagination
    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()
    
    return {"users": [u.serialization() for u in users], "total": total}
