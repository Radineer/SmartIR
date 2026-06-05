from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional

from app.schemas.company import CompanyResponse
from app.schemas.document import DocumentResponse


class StockListResponse(BaseModel):
    """銘柄一覧レスポンス（SEO用）"""
    total: int = Field(..., description="総銘柄数")
    stocks: List[CompanyResponse] = Field(..., description="銘柄リスト")


class StockDetailResponse(BaseModel):
    """銘柄詳細レスポンス（SEO用）"""
    id: int
    name: str
    ticker_code: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    website_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    recent_documents: List[DocumentResponse] = Field(default=[], description="最新ドキュメント")
    document_count: int = Field(default=0, description="ドキュメント総数")

    class Config:
        from_attributes = True


class StockAnalysisResponse(BaseModel):
    """銘柄分析結果レスポンス"""
    document_id: int = Field(..., description="分析対象ドキュメントID")
    document_title: str = Field(..., description="ドキュメントタイトル")
    publish_date: str = Field(..., description="公開日")
    summary: str = Field(..., description="AI要約")
    sentiment_positive: float = Field(..., ge=0, le=1, description="ポジティブスコア")
    sentiment_negative: float = Field(..., ge=0, le=1, description="ネガティブスコア")
    sentiment_neutral: float = Field(..., ge=0, le=1, description="ニュートラルスコア")
    key_points: List[str] = Field(default=[], description="重要ポイント")
    analyzed_at: datetime = Field(..., description="分析日時")

    class Config:
        from_attributes = True


class SectorInfo(BaseModel):
    """業種情報"""
    name: str = Field(..., description="業種名")
    stock_count: int = Field(..., description="銘柄数")


class SectorListResponse(BaseModel):
    """業種一覧レスポンス"""
    sectors: List[SectorInfo] = Field(..., description="業種リスト")


class SectorStocksResponse(BaseModel):
    """業種別銘柄レスポンス"""
    sector: str = Field(..., description="業種名")
    total: int = Field(..., description="銘柄数")
    stocks: List[CompanyResponse] = Field(..., description="銘柄リスト")
