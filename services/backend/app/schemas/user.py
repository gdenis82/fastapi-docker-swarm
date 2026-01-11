from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from app.schemas.role import Role

class UserBase(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = True
    role_id: Optional[int] = None

class UserCreate(UserBase):
    username: str
    email: EmailStr
    password: str = Field(..., min_length=8)

class UserUpdate(UserBase):
    password: Optional[str] = Field(None, min_length=8)

class UserInDBBase(UserBase):
    id: Optional[int] = None
    role_obj: Optional[Role] = None
    model_config = ConfigDict(from_attributes=True)

class User(UserInDBBase):
    pass

class UserInDB(UserInDBBase):
    hashed_password: str
