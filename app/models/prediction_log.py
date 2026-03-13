"""予測精度トラッキング用モデル"""

from sqlalchemy import Column, Integer, Float, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class PredictionLog(BaseModel):
    """株価インパクト予測の記録と検証"""
    __tablename__ = "prediction_logs"

    analysis_id = Column(Integer, ForeignKey("analysis_results.id"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)

    # 予測
    predicted_impact = Column(String(20), nullable=False)  # positive/negative/neutral
    predicted_confidence = Column(Float)
    predicted_reasoning = Column(String(500))
    analysis_depth = Column(String(20))   # quick/standard/deep
    llm_model = Column(String(100))
    predicted_at = Column(DateTime)

    # 実結果（翌営業日に自動記録）
    actual_price_change_pct = Column(Float)   # 翌日終値の変化率(%)
    actual_direction = Column(String(20))     # up/down/flat
    was_correct = Column(Boolean)
    verified_at = Column(DateTime)

    # リレーション
    analysis = relationship("AnalysisResult", backref="prediction_logs")
    company = relationship("Company", backref="prediction_logs")

    def __repr__(self):
        return (
            f"<PredictionLog(company_id={self.company_id}, "
            f"predicted={self.predicted_impact}, correct={self.was_correct})>"
        )
