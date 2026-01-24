"""
ウォッチリストサービス
ウォッチリスト管理とアラート機能を提供
"""

from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.watchlist import Watchlist, WatchlistItem, PriceAlert, AlertType
from app.schemas.watchlist import (
    WatchlistCreate,
    WatchlistItemCreate,
    WatchlistItemUpdate,
    PriceAlertCreate,
    WatchlistResponse,
    WatchlistDetailResponse,
    WatchlistWithPricesResponse,
    WatchlistItemWithPrice,
    TriggeredAlertResponse,
)
from app.services.market_data import market_data_service
from typing import TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class WatchlistService:
    """ウォッチリストサービスクラス"""

    def create_watchlist(
        self,
        db: Session,
        user_id: int,
        data: WatchlistCreate
    ) -> Watchlist:
        """
        ウォッチリストを作成

        Args:
            db: DBセッション
            user_id: ユーザーID
            data: 作成データ

        Returns:
            作成されたウォッチリスト
        """
        watchlist = Watchlist(
            user_id=user_id,
            name=data.name
        )
        db.add(watchlist)
        db.commit()
        db.refresh(watchlist)
        return watchlist

    def get_user_watchlists(
        self,
        db: Session,
        user_id: int
    ) -> List[WatchlistResponse]:
        """
        ユーザーのウォッチリスト一覧を取得

        Args:
            db: DBセッション
            user_id: ユーザーID

        Returns:
            ウォッチリスト一覧
        """
        watchlists = db.query(Watchlist).filter(
            Watchlist.user_id == user_id
        ).all()

        results = []
        for wl in watchlists:
            response = WatchlistResponse(
                id=wl.id,
                user_id=wl.user_id,
                name=wl.name,
                item_count=len(wl.items),
                created_at=wl.created_at,
                updated_at=wl.updated_at
            )
            results.append(response)
        return results

    def get_watchlist(
        self,
        db: Session,
        watchlist_id: int,
        user_id: int
    ) -> Optional[Watchlist]:
        """
        ウォッチリストを取得（所有者確認付き）

        Args:
            db: DBセッション
            watchlist_id: ウォッチリストID
            user_id: ユーザーID

        Returns:
            ウォッチリストまたはNone
        """
        return db.query(Watchlist).filter(
            and_(
                Watchlist.id == watchlist_id,
                Watchlist.user_id == user_id
            )
        ).first()

    def get_watchlist_detail(
        self,
        db: Session,
        watchlist_id: int,
        user_id: int
    ) -> Optional[WatchlistDetailResponse]:
        """
        ウォッチリスト詳細を取得

        Args:
            db: DBセッション
            watchlist_id: ウォッチリストID
            user_id: ユーザーID

        Returns:
            ウォッチリスト詳細
        """
        watchlist = self.get_watchlist(db, watchlist_id, user_id)
        if not watchlist:
            return None

        return WatchlistDetailResponse(
            id=watchlist.id,
            user_id=watchlist.user_id,
            name=watchlist.name,
            item_count=len(watchlist.items),
            items=watchlist.items,
            created_at=watchlist.created_at,
            updated_at=watchlist.updated_at
        )

    def get_watchlist_with_prices(
        self,
        db: Session,
        watchlist_id: int,
        user_id: int
    ) -> Optional[WatchlistWithPricesResponse]:
        """
        現在価格付きでウォッチリストを取得

        Args:
            db: DBセッション
            watchlist_id: ウォッチリストID
            user_id: ユーザーID

        Returns:
            現在価格付きウォッチリスト
        """
        watchlist = self.get_watchlist(db, watchlist_id, user_id)
        if not watchlist:
            return None

        items_with_prices = []
        for item in watchlist.items:
            # Yahoo Financeのシンボル形式に変換
            symbol = self._to_yahoo_symbol(item.ticker_code)
            quote = market_data_service.get_quote(symbol)

            # アラートのトリガー状態をチェック
            is_alert_triggered = any(alert.is_triggered for alert in item.alerts)

            item_with_price = WatchlistItemWithPrice(
                id=item.id,
                watchlist_id=item.watchlist_id,
                ticker_code=item.ticker_code,
                added_at=item.added_at,
                target_price_high=item.target_price_high,
                target_price_low=item.target_price_low,
                notes=item.notes,
                alerts=[alert for alert in item.alerts],
                created_at=item.created_at,
                name=quote.name if quote else None,
                current_price=quote.price if quote else None,
                price_change=quote.change if quote else None,
                price_change_percent=quote.change_percent if quote else None,
                is_alert_triggered=is_alert_triggered
            )
            items_with_prices.append(item_with_price)

        return WatchlistWithPricesResponse(
            id=watchlist.id,
            user_id=watchlist.user_id,
            name=watchlist.name,
            item_count=len(watchlist.items),
            items=items_with_prices,
            created_at=watchlist.created_at,
            updated_at=watchlist.updated_at
        )

    def delete_watchlist(
        self,
        db: Session,
        watchlist_id: int,
        user_id: int
    ) -> bool:
        """
        ウォッチリストを削除

        Args:
            db: DBセッション
            watchlist_id: ウォッチリストID
            user_id: ユーザーID

        Returns:
            削除成功したかどうか
        """
        watchlist = self.get_watchlist(db, watchlist_id, user_id)
        if not watchlist:
            return False

        db.delete(watchlist)
        db.commit()
        return True

    def add_item(
        self,
        db: Session,
        watchlist_id: int,
        user_id: int,
        data: WatchlistItemCreate
    ) -> Optional[WatchlistItem]:
        """
        ウォッチリストにアイテムを追加

        Args:
            db: DBセッション
            watchlist_id: ウォッチリストID
            user_id: ユーザーID
            data: アイテム追加データ

        Returns:
            追加されたアイテムまたはNone
        """
        watchlist = self.get_watchlist(db, watchlist_id, user_id)
        if not watchlist:
            return None

        # 重複チェック
        existing = db.query(WatchlistItem).filter(
            and_(
                WatchlistItem.watchlist_id == watchlist_id,
                WatchlistItem.ticker_code == data.ticker_code
            )
        ).first()
        if existing:
            return existing

        item = WatchlistItem(
            watchlist_id=watchlist_id,
            ticker_code=data.ticker_code,
            target_price_high=data.target_price_high,
            target_price_low=data.target_price_low,
            notes=data.notes
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    def update_item(
        self,
        db: Session,
        item_id: int,
        user_id: int,
        data: WatchlistItemUpdate
    ) -> Optional[WatchlistItem]:
        """
        ウォッチリストアイテムを更新

        Args:
            db: DBセッション
            item_id: アイテムID
            user_id: ユーザーID
            data: 更新データ

        Returns:
            更新されたアイテムまたはNone
        """
        item = self._get_item_with_user_check(db, item_id, user_id)
        if not item:
            return None

        if data.target_price_high is not None:
            item.target_price_high = data.target_price_high
        if data.target_price_low is not None:
            item.target_price_low = data.target_price_low
        if data.notes is not None:
            item.notes = data.notes

        db.commit()
        db.refresh(item)
        return item

    def remove_item(
        self,
        db: Session,
        item_id: int,
        user_id: int
    ) -> bool:
        """
        ウォッチリストからアイテムを削除

        Args:
            db: DBセッション
            item_id: アイテムID
            user_id: ユーザーID

        Returns:
            削除成功したかどうか
        """
        item = self._get_item_with_user_check(db, item_id, user_id)
        if not item:
            return False

        db.delete(item)
        db.commit()
        return True

    def create_alert(
        self,
        db: Session,
        item_id: int,
        user_id: int,
        data: PriceAlertCreate
    ) -> Optional[PriceAlert]:
        """
        アラートを作成

        Args:
            db: DBセッション
            item_id: アイテムID
            user_id: ユーザーID
            data: アラート作成データ

        Returns:
            作成されたアラートまたはNone
        """
        item = self._get_item_with_user_check(db, item_id, user_id)
        if not item:
            return None

        alert = PriceAlert(
            watchlist_item_id=item_id,
            alert_type=AlertType(data.alert_type.value),
            threshold=data.threshold
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert

    def delete_alert(
        self,
        db: Session,
        alert_id: int,
        user_id: int
    ) -> bool:
        """
        アラートを削除

        Args:
            db: DBセッション
            alert_id: アラートID
            user_id: ユーザーID

        Returns:
            削除成功したかどうか
        """
        alert = db.query(PriceAlert).filter(PriceAlert.id == alert_id).first()
        if not alert:
            return False

        # 所有者確認
        item = self._get_item_with_user_check(db, alert.watchlist_item_id, user_id)
        if not item:
            return False

        db.delete(alert)
        db.commit()
        return True

    def check_alerts(self, db: Session) -> List[TriggeredAlertResponse]:
        """
        全アラートをチェックしてトリガーされたものを返す

        Args:
            db: DBセッション

        Returns:
            トリガーされたアラート一覧
        """
        # 未トリガーのアラートを取得
        alerts = db.query(PriceAlert).filter(
            PriceAlert.is_triggered == False
        ).all()

        triggered = []
        for alert in alerts:
            item = alert.watchlist_item
            symbol = self._to_yahoo_symbol(item.ticker_code)
            quote = market_data_service.get_quote(symbol)

            if not quote or quote.price is None or quote.price == 0:
                continue

            is_triggered = False
            if alert.alert_type == AlertType.PRICE_ABOVE:
                is_triggered = quote.price >= alert.threshold
            elif alert.alert_type == AlertType.PRICE_BELOW:
                is_triggered = quote.price <= alert.threshold
            elif alert.alert_type == AlertType.VOLATILITY:
                # ボラティリティは変動率の絶対値で判定
                if quote.change_percent is not None:
                    is_triggered = abs(quote.change_percent) >= alert.threshold

            if is_triggered:
                alert.is_triggered = True
                alert.triggered_at = datetime.utcnow()

                triggered.append(TriggeredAlertResponse(
                    alert_id=alert.id,
                    watchlist_item_id=item.id,
                    ticker_code=item.ticker_code,
                    stock_name=quote.name,
                    alert_type=alert.alert_type,
                    threshold=alert.threshold,
                    current_price=quote.price,
                    triggered_at=alert.triggered_at
                ))

        if triggered:
            db.commit()

        return triggered

    async def check_alerts_and_notify(self, db: Session) -> List[TriggeredAlertResponse]:
        """
        全アラートをチェックしてトリガーされたものに通知を送信

        Args:
            db: DBセッション

        Returns:
            トリガーされたアラート一覧
        """
        from app.services.notification_service import notification_service

        triggered = self.check_alerts(db)

        # トリガーされた各アラートに対して通知を送信
        for alert_response in triggered:
            try:
                # アラートからユーザーIDを取得
                alert = db.query(PriceAlert).filter(
                    PriceAlert.id == alert_response.alert_id
                ).first()

                if alert and alert.watchlist_item:
                    watchlist = alert.watchlist_item.watchlist
                    if watchlist:
                        user_id = watchlist.user_id

                        # 通知を送信
                        await notification_service.send_alert_notification(
                            db=db,
                            user_id=user_id,
                            alert_id=alert_response.alert_id,
                            ticker_code=alert_response.ticker_code,
                            stock_name=alert_response.stock_name or "",
                            alert_type=alert_response.alert_type,
                            threshold=alert_response.threshold,
                            current_price=alert_response.current_price
                        )
                        logger.info(
                            f"Notification sent for alert {alert_response.alert_id} "
                            f"to user {user_id}"
                        )
            except Exception as e:
                logger.error(f"Failed to send notification for alert {alert_response.alert_id}: {e}")

        return triggered

    def reset_alert(
        self,
        db: Session,
        alert_id: int,
        user_id: int
    ) -> Optional[PriceAlert]:
        """
        アラートをリセット

        Args:
            db: DBセッション
            alert_id: アラートID
            user_id: ユーザーID

        Returns:
            リセットされたアラートまたはNone
        """
        alert = db.query(PriceAlert).filter(PriceAlert.id == alert_id).first()
        if not alert:
            return None

        item = self._get_item_with_user_check(db, alert.watchlist_item_id, user_id)
        if not item:
            return None

        alert.is_triggered = False
        alert.triggered_at = None
        db.commit()
        db.refresh(alert)
        return alert

    def _get_item_with_user_check(
        self,
        db: Session,
        item_id: int,
        user_id: int
    ) -> Optional[WatchlistItem]:
        """
        アイテムを取得（所有者確認付き）

        Args:
            db: DBセッション
            item_id: アイテムID
            user_id: ユーザーID

        Returns:
            アイテムまたはNone
        """
        item = db.query(WatchlistItem).filter(WatchlistItem.id == item_id).first()
        if not item:
            return None

        # ウォッチリストの所有者確認
        watchlist = self.get_watchlist(db, item.watchlist_id, user_id)
        if not watchlist:
            return None

        return item

    def _to_yahoo_symbol(self, ticker_code: str) -> str:
        """
        ティッカーコードをYahoo Financeのシンボル形式に変換

        Args:
            ticker_code: ティッカーコード

        Returns:
            Yahoo Financeシンボル
        """
        # 日本株の場合は .T を付ける
        if ticker_code.isdigit() and len(ticker_code) == 4:
            return f"{ticker_code}.T"
        return ticker_code


# シングルトンインスタンス
watchlist_service = WatchlistService()
