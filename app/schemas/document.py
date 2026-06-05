from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from enum import Enum

class DocumentType(str, Enum):
    """ドキュメントタイプの列挙型"""
    FINANCIAL_REPORT = "financial_report"
    ANNUAL_REPORT = "annual_report"
    PRESS_RELEASE = "press_release"
    PRESENTATION = "presentation"
    OTHER = "other"

class DocumentBase(BaseModel):
    """ドキュメント情報の基本スキーマ"""
    title: str
    doc_type: DocumentType
    publish_date: str  # YYYY-MM-DD
    source_url: str
    storage_url: Optional[str] = None
    is_processed: bool = False
    raw_text: Optional[str] = None

class DocumentCreate(DocumentBase):
    """ドキュメント作成用スキーマ"""
    company_id: int

class DocumentResponse(DocumentBase):
    """ドキュメントレスポンス用スキーマ"""
    id: int
    company_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        use_enum_values = True 