from sqlalchemy import Column, String, Boolean, Enum as SQLEnum
from enum import Enum
from app.models.base import BaseModel


class UserRole(str, Enum):
    """ユーザーロール"""
    ADMIN = "admin"
    USER = "user"
    PREMIUM = "premium"


class User(BaseModel):
    """ユーザー情報モデル"""
    __tablename__ = "users"

    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(100), nullable=True)
    role = Column(SQLEnum(UserRole), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
