from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class CompanyBase(BaseModel):
    """企業情報の基本スキーマ"""
    name: str
    ticker_code: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    website_url: Optional[str] = None

class CompanyCreate(CompanyBase):
    """企業情報作成用スキーマ"""
    pass

class CompanyResponse(CompanyBase):
    """企業情報レスポンス用スキーマ"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True 