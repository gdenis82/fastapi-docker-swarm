from sqlalchemy import String, Boolean, ForeignKey, inspect
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base
from typing import TYPE_CHECKING,Dict, Any

if TYPE_CHECKING:
    from app.models.role import Role

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    role_obj: Mapped["Role"] = relationship("Role", back_populates="users")

    def role_name(self):
        if self.role_obj:
            return self.role_obj.name
        return "No Role"

    # Serialization method
    def serialization(self) -> Dict[str, Any]:
        serialized = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role_name": self.role_name(),
            "role_id": self.role_id,
            "is_active": self.is_active
        }
        return serialized
