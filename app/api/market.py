"""
市況データAPI エンドポイント
Yahoo Finance APIを使用した株価・為替データの提供
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel

from app.services.market_data import (
    market_data_service,
    QuoteData,
    ChartData,
    MarketSummary,
    MAJOR_INDICES,
    CURRENCY_PAIRS,
    MAJOR_JP_STOCKS,
)

router = APIRouter(prefix="/market", tags=["market"])


class QuoteResponse(BaseModel):
    """クォートレスポンス"""
    success: bool
    data: Optional[QuoteData] = None
    error: Optional[str] = None


class IndicesResponse(BaseModel):
    """指数一覧レスポンス"""
    success: bool
    data: List[QuoteData]


class ChartResponse(BaseModel):
    """チャートデータレスポンス"""
    success: bool
    data: Optional[ChartData] = None
    error: Optional[str] = None


class SearchResult(BaseModel):
    """検索結果"""
    symbol: str
    name: str


class SearchResponse(BaseModel):
    """検索レスポンス"""
    success: bool
    data: List[SearchResult]


class AvailableSymbols(BaseModel):
    """利用可能なシンボル一覧"""
    indices: dict
    currencies: dict
    jp_stocks: dict


@router.get("/indices", response_model=IndicesResponse)
async def get_indices():
    """
    主要指数一覧を取得

    日経平均、TOPIX、NYダウ、S&P500等の主要株価指数のリアルタイムデータを取得します。

    Returns:
        主要指数のクォートデータ一覧
    """
    try:
        indices = market_data_service.get_indices()
        return IndicesResponse(success=True, data=indices)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch indices: {str(e)}")


@router.get("/currencies", response_model=IndicesResponse)
async def get_currencies():
    """
    主要通貨ペア一覧を取得

    USD/JPY、EUR/JPY等の主要通貨ペアのリアルタイムレートを取得します。

    Returns:
        主要通貨ペアのクォートデータ一覧
    """
    try:
        currencies = market_data_service.get_currencies()
        return IndicesResponse(success=True, data=currencies)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch currencies: {str(e)}")


@router.get("/stocks/jp", response_model=IndicesResponse)
async def get_jp_stocks():
    """
    主要日本株一覧を取得

    トヨタ、ソニー等の主要日本株のリアルタイムデータを取得します。

    Returns:
        主要日本株のクォートデータ一覧
    """
    try:
        stocks = market_data_service.get_major_jp_stocks()
        return IndicesResponse(success=True, data=stocks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch JP stocks: {str(e)}")


@router.get("/quote/{symbol}", response_model=QuoteResponse)
async def get_quote(symbol: str):
    """
    個別銘柄/指数のクォートを取得

    指定されたシンボルのリアルタイム株価・指数情報を取得します。

    Args:
        symbol: ティッカーシンボル（例: ^N225, 7203.T, USDJPY=X）

    Returns:
        クォートデータ

    Examples:
        - 日経平均: /api/market/quote/^N225
        - トヨタ: /api/market/quote/7203.T
        - ドル円: /api/market/quote/USDJPY=X
    """
    try:
        quote = market_data_service.get_quote(symbol)
        if quote is None:
            return QuoteResponse(
                success=False,
                error=f"Could not fetch quote for symbol: {symbol}"
            )
        return QuoteResponse(success=True, data=quote)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch quote: {str(e)}")


@router.get("/chart/{symbol}", response_model=ChartResponse)
async def get_chart(
    symbol: str,
    period: str = Query(
        default="1d",
        description="期間 (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)"
    ),
    interval: str = Query(
        default="5m",
        description="間隔 (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)"
    )
):
    """
    チャートデータを取得

    指定されたシンボルの価格履歴データをOHLC形式で取得します。

    Args:
        symbol: ティッカーシンボル
        period: データ期間（デフォルト: 1d）
        interval: データ間隔（デフォルト: 5m）

    Returns:
        OHLC形式のチャートデータ

    Note:
        - 1d期間: 5分足がデフォルト
        - 1mo期間: 1時間足がデフォルト
        - 1y期間: 日足がデフォルト
    """
    # 期間のバリデーション
    valid_periods = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"]
    if period not in valid_periods:
        return ChartResponse(
            success=False,
            error=f"Invalid period. Valid values: {', '.join(valid_periods)}"
        )

    # 間隔のバリデーション
    valid_intervals = ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"]
    if interval not in valid_intervals:
        return ChartResponse(
            success=False,
            error=f"Invalid interval. Valid values: {', '.join(valid_intervals)}"
        )

    try:
        chart = market_data_service.get_chart_data(symbol, period, interval)
        if chart is None:
            return ChartResponse(
                success=False,
                error=f"Could not fetch chart data for symbol: {symbol}"
            )
        return ChartResponse(success=True, data=chart)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch chart data: {str(e)}")


@router.get("/summary", response_model=MarketSummary)
async def get_market_summary():
    """
    本日の市場サマリーを取得

    主要指数と通貨ペアのまとめ情報を一括で取得します。
    市場の開閉状態も含まれます。

    Returns:
        市場サマリー（指数、通貨、市場状態）

    Market Status:
        - open_morning: 前場取引中
        - lunch_break: 昼休み
        - open_afternoon: 後場取引中
        - pre_market: プレマーケット
        - after_hours: 時間外
        - closed_weekend: 週末休場
    """
    try:
        summary = market_data_service.get_market_summary()
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch market summary: {str(e)}")


@router.get("/search", response_model=SearchResponse)
async def search_symbols(
    q: str = Query(..., min_length=1, description="検索クエリ")
):
    """
    銘柄検索

    シンボルまたは銘柄名で検索します。

    Args:
        q: 検索クエリ（例: トヨタ, 7203, SONY）

    Returns:
        マッチした銘柄リスト（最大10件）
    """
    try:
        results = market_data_service.search_symbol(q)
        return SearchResponse(
            success=True,
            data=[SearchResult(**r) for r in results]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/symbols")
async def get_available_symbols() -> AvailableSymbols:
    """
    利用可能なシンボル一覧を取得

    API で取得可能な全銘柄のシンボルと名称の一覧を返します。

    Returns:
        カテゴリ別のシンボル一覧
    """
    return AvailableSymbols(
        indices=MAJOR_INDICES,
        currencies=CURRENCY_PAIRS,
        jp_stocks=MAJOR_JP_STOCKS
    )
