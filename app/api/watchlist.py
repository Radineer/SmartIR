"""
ウォッチリストAPI
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.schemas.watchlist import (
    WatchlistCreate,
    WatchlistItemCreate,
    WatchlistItemUpdate,
    PriceAlertCreate,
    WatchlistResponse,
    WatchlistDetailResponse,
    WatchlistWithPricesResponse,
    WatchlistItemResponse,
    PriceAlertResponse,
    TriggeredAlertResponse,
)
from app.services.watchlist_service import watchlist_service

router = APIRouter(
    prefix="/watchlist",
    tags=["watchlist"],
)


@router.post("/", response_model=WatchlistResponse, status_code=status.HTTP_201_CREATED)
def create_watchlist(
    data: WatchlistCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    ウォッチリストを作成
    """
    watchlist = watchlist_service.create_watchlist(db, current_user.id, data)
    return WatchlistResponse(
        id=watchlist.id,
        user_id=watchlist.user_id,
        name=watchlist.name,
        item_count=0,
        created_at=watchlist.created_at,
        updated_at=watchlist.updated_at
    )


@router.get("/", response_model=List[WatchlistResponse])
def get_watchlists(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    ユーザーのウォッチリスト一覧を取得
    """
    return watchlist_service.get_user_watchlists(db, current_user.id)


@router.get("/{watchlist_id}", response_model=WatchlistWithPricesResponse)
def get_watchlist(
    watchlist_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    ウォッチリスト詳細を取得（現在価格付き）
    """
    watchlist = watchlist_service.get_watchlist_with_prices(
        db, watchlist_id, current_user.id
    )
    if not watchlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist not found"
        )
    return watchlist


@router.get("/{watchlist_id}/detail", response_model=WatchlistDetailResponse)
def get_watchlist_detail(
    watchlist_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    ウォッチリスト詳細を取得（価格なし、高速）
    """
    watchlist = watchlist_service.get_watchlist_detail(
        db, watchlist_id, current_user.id
    )
    if not watchlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist not found"
        )
    return watchlist


@router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist(
    watchlist_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    ウォッチリストを削除
    """
    success = watchlist_service.delete_watchlist(db, watchlist_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist not found"
        )


@router.post("/{watchlist_id}/items", response_model=WatchlistItemResponse, status_code=status.HTTP_201_CREATED)
def add_item(
    watchlist_id: int,
    data: WatchlistItemCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    ウォッチリストに銘柄を追加
    """
    item = watchlist_service.add_item(db, watchlist_id, current_user.id, data)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist not found"
        )
    return item


@router.put("/items/{item_id}", response_model=WatchlistItemResponse)
def update_item(
    item_id: int,
    data: WatchlistItemUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    ウォッチリストアイテムを更新
    """
    item = watchlist_service.update_item(db, item_id, current_user.id, data)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    return item


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_item(
    item_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    ウォッチリストから銘柄を削除
    """
    success = watchlist_service.remove_item(db, item_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )


@router.post("/items/{item_id}/alerts", response_model=PriceAlertResponse, status_code=status.HTTP_201_CREATED)
def create_alert(
    item_id: int,
    data: PriceAlertCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    価格アラートを設定
    """
    alert = watchlist_service.create_alert(db, item_id, current_user.id, data)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    return alert


@router.delete("/alerts/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert(
    alert_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    アラートを削除
    """
    success = watchlist_service.delete_alert(db, alert_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )


@router.post("/alerts/{alert_id}/reset", response_model=PriceAlertResponse)
def reset_alert(
    alert_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    トリガー済みアラートをリセット
    """
    alert = watchlist_service.reset_alert(db, alert_id, current_user.id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )
    return alert


@router.get("/alerts/check", response_model=List[TriggeredAlertResponse])
def check_alerts(
    db: Session = Depends(get_db)
):
    """
    全アラートをチェック（定期実行用、認証不要）
    トリガーされたアラートを返す
    """
    return watchlist_service.check_alerts(db)
