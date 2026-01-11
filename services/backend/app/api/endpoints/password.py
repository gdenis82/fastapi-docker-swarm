from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any

from app.api import deps
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserUpdate
from app.core import security

router = APIRouter(tags=["auth"])

@router.post(
    "/reset-password",
    response_model=Any,
    summary="Сброс пароля",
    description="Позволяет сбросить пароль пользователя с использованием токена восстановления.",
    response_description="Сообщение об успешном обновлении пароля."
)
async def reset_password(
    token: str,
    new_password: UserUpdate, # Assuming it contains the new password
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Reset password using token. 
    TODO: 
    1. Validate the reset token (should be a short-lived JWT with specific type).
    2. Check if token is in Redis denylist.
    3. Decode sub (user_id) from token.
    4. Fetch user from DB.
    5. Hash new password and update user in DB.
    6. Revoke the reset token (add to denylist).
    """
    # Placeholder for actual reset logic
    return {"message": "Password updated successfully"}
