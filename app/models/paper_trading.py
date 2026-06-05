"""
ペーパートレーディングモデル
AIトレーディングチャレンジ用の仮想ポジション・取引・スナップショット
"""

import enum
from datetime import datetime

from sqlalchemy import Column, String, Integer, Float, Text, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.models.base import BaseModel


class TradeSide(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"


class PaperPosition(BaseModel):
    """現在の保有ポジション"""
    __tablename__ = "paper_positions"

    ticker = Column(String(20), nullable=False, index=True)
    company_name = Column(String(200), nullable=True)
    shares = Column(Float, nullable=False)
    avg_cost = Column(Float, nullable=False)
    current_price = Column(Float, nullable=True)
    unrealized_pnl = Column(Float, nullable=True)
    sector = Column(String(50), nullable=True)
    signal_source = Column(String(50), nullable=True)
    opened_at = Column(DateTime, default=datetime.utcnow)
    peak_price = Column(Float, nullable=True)
    metadata_ = Column("metadata", JSONB, server_default="{}")

    def __repr__(self):
        return f"<PaperPosition(ticker={self.ticker}, shares={self.shares}, avg_cost={self.avg_cost})>"


class PaperTrade(BaseModel):
    """取引履歴"""
    __tablename__ = "paper_trades"

    ticker = Column(String(20), nullable=False, index=True)
    company_name = Column(String(200), nullable=True)
    side = Column(String(4), nullable=False)  # "buy" / "sell"
    shares = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    cost = Column(Float, nullable=False, default=0)
    total_amount = Column(Float, nullable=False)
    signal_source = Column(String(50), nullable=True)
    signal_strength = Column(Float, nullable=True)
    reason = Column(Text, nullable=True)
    executed_at = Column(DateTime, default=datetime.utcnow)
    metadata_ = Column("metadata", JSONB, server_default="{}")

    __table_args__ = (
        Index("ix_paper_trades_executed_at", "executed_at"),
    )

    def __repr__(self):
        return f"<PaperTrade(ticker={self.ticker}, side={self.side}, shares={self.shares}, price={self.price})>"


class PaperPortfolioSnapshot(BaseModel):
    """日次ポートフォリオスナップショット"""
    __tablename__ = "paper_portfolio_snapshots"

    snapshot_date = Column(String(10), nullable=False, unique=True, index=True)  # YYYY-MM-DD
    cash = Column(Float, nullable=False)
    positions_value = Column(Float, nullable=False, default=0)
    total_nav = Column(Float, nullable=False)
    daily_return_pct = Column(Float, nullable=True)
    cumulative_return_pct = Column(Float, nullable=True)
    max_drawdown_pct = Column(Float, nullable=True)
    num_positions = Column(Integer, nullable=False, default=0)
    positions_detail = Column(JSONB, server_default="[]")
    trades_today = Column(JSONB, server_default="[]")
    metadata_ = Column("metadata", JSONB, server_default="{}")

    def __repr__(self):
        return f"<PaperPortfolioSnapshot(date={self.snapshot_date}, nav={self.total_nav})>"
