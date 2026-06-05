"""
バックテストジョブモデル
バックテストの実行履歴と結果を保存
"""

from sqlalchemy import Column, String, Integer, Float, ForeignKey, JSON, Enum as SQLEnum, Text
from sqlalchemy.orm import relationship
from enum import Enum
from app.models.base import BaseModel


class BacktestStatus(str, Enum):
    """バックテストジョブのステータス"""
    PENDING = "pending"      # 実行待ち
    RUNNING = "running"      # 実行中
    COMPLETED = "completed"  # 完了
    FAILED = "failed"        # 失敗


class BacktestJob(BaseModel):
    """バックテストジョブモデル"""
    __tablename__ = "backtest_jobs"

    # ユーザーとの紐付け（任意）
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # バックテスト設定
    ticker = Column(String(20), nullable=False, index=True)
    start_date = Column(String(10), nullable=False)  # YYYY-MM-DD
    end_date = Column(String(10), nullable=False)    # YYYY-MM-DD
    initial_capital = Column(Float, nullable=False, default=1000000)
    strategy = Column(String(50), nullable=False, index=True)
    params = Column(JSON, nullable=True)  # 戦略パラメータ

    # 実行状態
    status = Column(
        SQLEnum(BacktestStatus),
        default=BacktestStatus.PENDING,
        nullable=False,
        index=True
    )
    error_message = Column(Text, nullable=True)

    # 結果サマリー（クイック参照用）
    total_return = Column(Float, nullable=True)
    annual_return = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    win_rate = Column(Float, nullable=True)
    total_trades = Column(Integer, nullable=True)

    # 詳細結果（JSON）
    result = Column(JSON, nullable=True)

    # イリス用解説テキスト
    iris_summary = Column(Text, nullable=True)

    # ユーザーリレーション
    user = relationship("User", backref="backtest_jobs")

    def __repr__(self):
        return f"<BacktestJob(id={self.id}, ticker={self.ticker}, strategy={self.strategy}, status={self.status})>"


class BacktestTemplate(BaseModel):
    """バックテスト戦略テンプレート（ユーザー保存用）"""
    __tablename__ = "backtest_templates"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    strategy = Column(String(50), nullable=False)
    params = Column(JSON, nullable=True)
    is_public = Column(Integer, default=0)  # 公開設定

    # ユーザーリレーション
    user = relationship("User", backref="backtest_templates")

    def __repr__(self):
        return f"<BacktestTemplate(id={self.id}, name={self.name}, strategy={self.strategy})>"
