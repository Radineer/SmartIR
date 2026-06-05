from sqlalchemy import Column, String, Text, ForeignKey, Enum, Boolean, Integer
from sqlalchemy.orm import relationship
import enum
from app.models.base import BaseModel

class DocumentType(enum.Enum):
    """IR資料の種類"""
    FINANCIAL_REPORT = "financial_report"  # 決算短信
    ANNUAL_REPORT = "annual_report"        # 有価証券報告書
    PRESS_RELEASE = "press_release"        # プレスリリース
    PRESENTATION = "presentation"          # 決算説明会資料
    OTHER = "other"                        # その他

class Document(BaseModel):
    """IR資料モデル"""
    __tablename__ = "documents"

    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    title = Column(String(255), nullable=False)
    doc_type = Column(Enum(DocumentType), nullable=False)
    publish_date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    source_url = Column(String(512), nullable=False)
    storage_url = Column(String(512))  # S3等のストレージURL
    is_processed = Column(Boolean, default=False)  # テキスト抽出済みフラグ
    raw_text = Column(Text)  # 抽出したテキスト
    
    # リレーションシップ
    company = relationship("Company", backref="documents")
    
    def __repr__(self):
        return f"<Document(title={self.title}, company_id={self.company_id})>" 