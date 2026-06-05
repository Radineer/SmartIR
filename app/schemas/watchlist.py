from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class AlertType(str, Enum):
    """アラートタイプ"""
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    VOLATILITY = "volatility"
    IR_RELEASE = "ir_release"


# === リクエストスキーマ ===

class WatchlistCreate(BaseModel):
    """ウォッチリスト作成リクエスト"""
    name: str = Field(default="メインウォッチリスト", max_length=100, description="ウォッチリスト名")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "お気に入り銘柄"
            }
        }


class WatchlistItemCreate(BaseModel):
    """ウォッチリストアイテム追加リクエスト"""
    ticker_code: str = Field(..., max_length=20, description="ティッカーコード")
    target_price_high: Optional[float] = Field(None, description="上限アラート価格")
    target_price_low: Optional[float] = Field(None, description="下限アラート価格")
    notes: Optional[str] = Field(None, max_length=500, description="メモ")

    class Config:
        json_schema_extra = {
            "example": {
                "ticker_code": "7203",
                "target_price_high": 3000.0,
                "target_price_low": 2500.0,
                "notes": "決算発表後に購入検討"
            }
        }


class WatchlistItemUpdate(BaseModel):
    """ウォッチリストアイテム更新リクエスト"""
    target_price_high: Optional[float] = Field(None, description="上限アラート価格")
    target_price_low: Optional[float] = Field(None, description="下限アラート価格")
    notes: Optional[str] = Field(None, max_length=500, description="メモ")


class PriceAlertCreate(BaseModel):
    """アラート作成リクエスト"""
    alert_type: AlertType = Field(..., description="アラートタイプ")
    threshold: float = Field(..., description="閾値")

    class Config:
        json_schema_extra = {
            "example": {
                "alert_type": "price_above",
                "threshold": 3000.0
            }
        }


# === レスポンススキーマ ===

class PriceAlertResponse(BaseModel):
    """アラートレスポンス"""
    id: int
    watchlist_item_id: int
    alert_type: AlertType
    threshold: float
    is_triggered: bool
    triggered_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class WatchlistItemResponse(BaseModel):
    """ウォッチリストアイテムレスポンス"""
    id: int
    watchlist_id: int
    ticker_code: str
    added_at: datetime
    target_price_high: Optional[float]
    target_price_low: Optional[float]
    notes: Optional[str]
    alerts: List[PriceAlertResponse] = []
    created_at: datetime

    class Config:
        from_attributes = True


class WatchlistItemWithPrice(WatchlistItemResponse):
    """現在価格付きウォッチリストアイテム"""
    name: Optional[str] = None
    current_price: Optional[float] = None
    price_change: Optional[float] = None
    price_change_percent: Optional[float] = None
    is_alert_triggered: bool = False


class WatchlistResponse(BaseModel):
    """ウォッチリストレスポンス"""
    id: int
    user_id: int
    name: str
    item_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WatchlistDetailResponse(WatchlistResponse):
    """ウォッチリスト詳細レスポンス（アイテム付き）"""
    items: List[WatchlistItemResponse] = []


class WatchlistWithPricesResponse(WatchlistResponse):
    """ウォッチリスト詳細レスポンス（現在価格付き）"""
    items: List[WatchlistItemWithPrice] = []


class TriggeredAlertResponse(BaseModel):
    """トリガーされたアラートレスポンス"""
    alert_id: int
    watchlist_item_id: int
    ticker_code: str
    stock_name: Optional[str]
    alert_type: AlertType
    threshold: float
    current_price: float
    triggered_at: datetime
