from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    """ユーザーロール"""
    ADMIN = "admin"
    USER = "user"
    PREMIUM = "premium"


class UserRegister(BaseModel):
    """ユーザー登録リクエスト"""
    email: EmailStr = Field(..., description="メールアドレス")
    password: str = Field(..., min_length=8, description="パスワード（8文字以上）")
    name: Optional[str] = Field(None, max_length=100, description="名前")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "password123",
                "name": "山田太郎"
            }
        }


class UserLogin(BaseModel):
    """ログインリクエスト"""
    email: EmailStr = Field(..., description="メールアドレス")
    password: str = Field(..., description="パスワード")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "password123"
            }
        }


class Token(BaseModel):
    """トークンレスポンス"""
    access_token: str = Field(..., description="アクセストークン")
    token_type: str = Field(default="bearer", description="トークンタイプ")


class TokenData(BaseModel):
    """トークンデータ（内部用）"""
    user_id: Optional[int] = None
    email: Optional[str] = None


class UserResponse(BaseModel):
    """ユーザー情報レスポンス"""
    id: int
    email: str
    name: Optional[str]
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
