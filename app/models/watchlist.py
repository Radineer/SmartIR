from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.orm import relationship
from enum import Enum
from datetime import datetime
from app.models.base import BaseModel


class AlertType(str, Enum):
    """アラートタイプ"""
    PRICE_ABOVE = "price_above"      # 指定価格を上回った
    PRICE_BELOW = "price_below"      # 指定価格を下回った
    VOLATILITY = "volatility"        # ボラティリティが閾値を超えた
    IR_RELEASE = "ir_release"        # IR資料が公開された


class Watchlist(BaseModel):
    """ウォッチリストモデル"""
    __tablename__ = "watchlists"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False, default="メインウォッチリスト")

    # リレーション
    items = relationship("WatchlistItem", back_populates="watchlist", cascade="all, delete-orphan")


class WatchlistItem(BaseModel):
    """ウォッチリストアイテムモデル"""
    __tablename__ = "watchlist_items"

    watchlist_id = Column(Integer, ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False, index=True)
    ticker_code = Column(String(20), nullable=False, index=True)
    added_at = Column(DateTime, default=datetime.utcnow)
    target_price_high = Column(Float, nullable=True)  # 上限アラート価格
    target_price_low = Column(Float, nullable=True)   # 下限アラート価格
    notes = Column(Text, nullable=True)               # メモ

    # リレーション
    watchlist = relationship("Watchlist", back_populates="items")
    alerts = relationship("PriceAlert", back_populates="watchlist_item", cascade="all, delete-orphan")


class PriceAlert(BaseModel):
    """価格アラートモデル"""
    __tablename__ = "price_alerts"

    watchlist_item_id = Column(Integer, ForeignKey("watchlist_items.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_type = Column(SQLEnum(AlertType), nullable=False)
    threshold = Column(Float, nullable=False)         # アラート閾値
    is_triggered = Column(Boolean, default=False)     # トリガー済みかどうか
    triggered_at = Column(DateTime, nullable=True)    # トリガーされた日時

    # リレーション
    watchlist_item = relationship("WatchlistItem", back_populates="alerts")
