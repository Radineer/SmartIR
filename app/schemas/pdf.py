from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List
from enum import Enum


class ExtractionMethod(str, Enum):
    """抽出方法"""
    DIRECT = "direct"
    OCR = "ocr"
    HYBRID = "hybrid"


class PDFExtractionRequest(BaseModel):
    """PDF抽出リクエスト"""
    url: str = Field(..., description="PDF URL")
    use_ocr: bool = Field(default=True, description="OCRを使用するか")

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com/ir_report.pdf",
                "use_ocr": True
            }
        }


class PDFExtractionResponse(BaseModel):
    """PDF抽出レスポンス"""
    text: str = Field(..., description="抽出されたテキスト")
    source_url: str = Field(..., description="元のURL")
    extraction_method: ExtractionMethod = Field(..., description="使用した抽出方法")
    processing_time: float = Field(..., description="処理時間（秒）")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "抽出されたテキスト...",
                "source_url": "https://example.com/ir_report.pdf",
                "extraction_method": "direct",
                "processing_time": 2.5
            }
        }
