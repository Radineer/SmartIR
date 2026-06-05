from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from datetime import datetime


class SentimentScore(BaseModel):
    """センチメント分析結果"""
    positive: float = Field(..., ge=0, le=1, description="ポジティブスコア")
    negative: float = Field(..., ge=0, le=1, description="ネガティブスコア")
    neutral: float = Field(..., ge=0, le=1, description="ニュートラルスコア")


class AnalysisRequest(BaseModel):
    """テキスト分析リクエスト"""
    text: str = Field(..., min_length=1, max_length=100000, description="分析対象テキスト")
    doc_type: str = Field(..., description="ドキュメントタイプ")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "当社の2024年度決算は、売上高が前年比15%増加...",
                "doc_type": "financial_report"
            }
        }


class AnalysisResponse(BaseModel):
    """テキスト分析レスポンス"""
    summary: str = Field(..., description="要約テキスト")
    sentiment: SentimentScore = Field(..., description="センチメントスコア")
    key_points: List[str] = Field(..., description="重要ポイント")
    processing_time: Optional[float] = Field(None, description="処理時間（秒）")

    class Config:
        json_schema_extra = {
            "example": {
                "summary": "2024年度の営業収益は前年比15%増加...",
                "sentiment": {
                    "positive": 0.7,
                    "negative": 0.1,
                    "neutral": 0.2
                },
                "key_points": [
                    "1. 営業収益が前年比15%増加",
                    "2. 営業利益率が3ポイント改善",
                    "3. 設備投資を50%増加"
                ],
                "processing_time": 12.5
            }
        }


class DocumentAnalysisRequest(BaseModel):
    """ドキュメント分析リクエスト（document_idを指定）"""
    document_id: int = Field(..., description="分析対象ドキュメントID")


class PipelineRequest(BaseModel):
    """統合パイプラインリクエスト"""
    pdf_url: str = Field(..., description="PDF URL")
    company_id: int = Field(..., description="企業ID")
    doc_type: str = Field(default="other", description="ドキュメントタイプ")

    class Config:
        json_schema_extra = {
            "example": {
                "pdf_url": "https://example.com/ir_report.pdf",
                "company_id": 1,
                "doc_type": "financial_report"
            }
        }


class PipelineResponse(BaseModel):
    """統合パイプラインレスポンス"""
    extracted_text: str = Field(..., description="抽出されたテキスト")
    analysis: AnalysisResponse = Field(..., description="分析結果")
    processing_time: float = Field(..., description="総処理時間（秒）")
