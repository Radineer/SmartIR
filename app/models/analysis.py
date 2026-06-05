from sqlalchemy import Column, Integer, Float, String, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class AnalysisResult(BaseModel):
    """分析結果の永続化モデル"""
    __tablename__ = "analysis_results"

    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    summary = Column(Text, nullable=False)
    sentiment_positive = Column(Float, nullable=False, default=0.0)
    sentiment_negative = Column(Float, nullable=False, default=0.0)
    sentiment_neutral = Column(Float, nullable=False, default=0.0)
    key_points = Column(JSON, default=list)

    # 3段階分析の拡張フィールド
    analysis_depth = Column(String(20))          # quick / standard / deep
    llm_model = Column(String(100))              # 使用モデル名
    processing_time_sec = Column(Float)          # 処理時間（秒）

    # 財務数値
    financial_metrics = Column(JSON)             # revenue, op, np, yoy等

    # 業績予想修正
    guidance_revision = Column(String(20))       # up / down / unchanged / none / new
    guidance_detail = Column(JSON)               # 修正前後の数値

    # セグメント・リスク・成長
    segments = Column(JSON)                      # セグメント別分析
    risk_factors = Column(JSON)                  # リスク要因
    growth_drivers = Column(JSON)                # 成長ドライバー

    # 株価インパクト予測
    stock_impact_prediction = Column(String(20)) # positive / negative / neutral
    stock_impact_confidence = Column(Float)      # 0-1
    stock_impact_reasoning = Column(Text)        # 予測根拠

    # PDF表抽出データ
    extracted_tables = Column(JSON)              # Vision API抽出結果

    # リレーションシップ
    document = relationship("Document", backref="analysis_results")

    def __repr__(self):
        return f"<AnalysisResult(document_id={self.document_id}, depth={self.analysis_depth})>"
