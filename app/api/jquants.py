"""
J-Quants API エンドポイント
日本取引所グループ公式APIを使用した株価・財務データの提供
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel

from app.services.jquants_service import (
    jquants_client,
    StockPrice,
    FinancialStatement,
    ListedCompany,
    SectorInfo,
    ShortSellingInfo,
)

router = APIRouter(prefix="/jquants", tags=["jquants"])


class StockPricesResponse(BaseModel):
    """株価レスポンス"""
    success: bool
    data: List[StockPrice]
    error: Optional[str] = None


class FinancialStatementsResponse(BaseModel):
    """財務情報レスポンス"""
    success: bool
    data: List[FinancialStatement]
    error: Optional[str] = None


class ListedCompaniesResponse(BaseModel):
    """上場企業一覧レスポンス"""
    success: bool
    data: List[ListedCompany]
    count: int
    error: Optional[str] = None


class SectorInfoResponse(BaseModel):
    """業種情報レスポンス"""
    success: bool
    data: List[SectorInfo]
    error: Optional[str] = None


class ShortSellingResponse(BaseModel):
    """空売り比率レスポンス"""
    success: bool
    data: List[ShortSellingInfo]
    error: Optional[str] = None


class ApiStatusResponse(BaseModel):
    """APIステータスレスポンス"""
    available: bool
    message: str


@router.get("/status", response_model=ApiStatusResponse)
async def get_status():
    """
    J-Quants APIの利用可否を確認

    環境変数が設定されているかどうかを確認します。

    Returns:
        APIの利用可否ステータス
    """
    is_available = jquants_client.is_available()
    return ApiStatusResponse(
        available=is_available,
        message="J-Quants API is ready" if is_available else "J-Quants API credentials not configured"
    )


@router.get("/prices/{ticker}", response_model=StockPricesResponse)
async def get_stock_prices(
    ticker: str,
    start_date: Optional[str] = Query(
        default=None,
        description="開始日（YYYY-MM-DD形式）。未指定時は30日前から"
    ),
    end_date: Optional[str] = Query(
        default=None,
        description="終了日（YYYY-MM-DD形式）。未指定時は本日まで"
    )
):
    """
    株価四本値を取得

    J-Quants APIを使用して指定銘柄の日次株価データを取得します。
    調整済み株価も含まれます。

    Args:
        ticker: 銘柄コード（例: 7203, 6758）
        start_date: 開始日（YYYY-MM-DD形式）
        end_date: 終了日（YYYY-MM-DD形式）

    Returns:
        株価データのリスト

    Examples:
        - トヨタ自動車: /api/jquants/prices/7203
        - ソニー: /api/jquants/prices/6758?start_date=2024-01-01&end_date=2024-01-31
    """
    if not jquants_client.is_available():
        return StockPricesResponse(
            success=False,
            data=[],
            error="J-Quants API credentials not configured"
        )

    try:
        prices = jquants_client.get_stock_prices(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date
        )
        return StockPricesResponse(success=True, data=prices)
    except ValueError as e:
        return StockPricesResponse(
            success=False,
            data=[],
            error=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch stock prices: {str(e)}"
        )


@router.get("/financials/{ticker}", response_model=FinancialStatementsResponse)
async def get_financial_statements(ticker: str):
    """
    財務情報を取得

    J-Quants APIを使用して指定銘柄の財務諸表データを取得します。
    売上高、営業利益、純利益、EPS等の主要指標を含みます。

    Args:
        ticker: 銘柄コード（例: 7203, 6758）

    Returns:
        財務情報のリスト

    Examples:
        - トヨタ自動車: /api/jquants/financials/7203
        - ソニー: /api/jquants/financials/6758
    """
    if not jquants_client.is_available():
        return FinancialStatementsResponse(
            success=False,
            data=[],
            error="J-Quants API credentials not configured"
        )

    try:
        statements = jquants_client.get_financial_statements(ticker=ticker)
        return FinancialStatementsResponse(success=True, data=statements)
    except ValueError as e:
        return FinancialStatementsResponse(
            success=False,
            data=[],
            error=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch financial statements: {str(e)}"
        )


@router.get("/companies", response_model=ListedCompaniesResponse)
async def get_listed_companies(
    code: Optional[str] = Query(
        default=None,
        description="銘柄コード（指定時はその銘柄のみ取得）"
    ),
    date: Optional[str] = Query(
        default=None,
        description="取得日（YYYYMMDD形式）"
    )
):
    """
    上場企業一覧を取得

    J-Quants APIを使用して上場企業の基本情報を取得します。
    業種分類（17業種・33業種）、市場区分などが含まれます。

    Args:
        code: 銘柄コード（指定時はその銘柄のみ）
        date: 取得日（YYYYMMDD形式）

    Returns:
        上場企業情報のリスト

    Examples:
        - 全企業: /api/jquants/companies
        - 特定企業: /api/jquants/companies?code=7203
    """
    if not jquants_client.is_available():
        return ListedCompaniesResponse(
            success=False,
            data=[],
            count=0,
            error="J-Quants API credentials not configured"
        )

    try:
        companies = jquants_client.get_listed_companies(
            code=code,
            date_yyyymmdd=date
        )
        return ListedCompaniesResponse(
            success=True,
            data=companies,
            count=len(companies)
        )
    except ValueError as e:
        return ListedCompaniesResponse(
            success=False,
            data=[],
            count=0,
            error=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch listed companies: {str(e)}"
        )


@router.get("/sectors", response_model=SectorInfoResponse)
async def get_sector_info(
    sector_code: Optional[str] = Query(
        default=None,
        description="業種コード（17業種または33業種）"
    ),
    from_date: Optional[str] = Query(
        default=None,
        description="開始日（YYYY-MM-DD形式）。未指定時は30日前から"
    ),
    to_date: Optional[str] = Query(
        default=None,
        description="終了日（YYYY-MM-DD形式）。未指定時は本日まで"
    )
):
    """
    業種別情報を取得

    J-Quants APIを使用してTOPIX業種別指数データを取得します。

    Args:
        sector_code: 業種コード
        from_date: 開始日（YYYY-MM-DD形式）
        to_date: 終了日（YYYY-MM-DD形式）

    Returns:
        業種情報のリスト

    Examples:
        - 全業種: /api/jquants/sectors
        - 特定業種: /api/jquants/sectors?sector_code=0050
    """
    if not jquants_client.is_available():
        return SectorInfoResponse(
            success=False,
            data=[],
            error="J-Quants API credentials not configured"
        )

    try:
        sectors = jquants_client.get_sector_info(
            sector_code=sector_code,
            from_date=from_date,
            to_date=to_date
        )
        return SectorInfoResponse(success=True, data=sectors)
    except ValueError as e:
        return SectorInfoResponse(
            success=False,
            data=[],
            error=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch sector info: {str(e)}"
        )


@router.get("/short-selling/{ticker}", response_model=ShortSellingResponse)
async def get_short_selling_ratio(
    ticker: str,
    from_date: Optional[str] = Query(
        default=None,
        description="開始日（YYYY-MM-DD形式）。未指定時は30日前から"
    ),
    to_date: Optional[str] = Query(
        default=None,
        description="終了日（YYYY-MM-DD形式）。未指定時は本日まで"
    )
):
    """
    空売り比率を取得

    J-Quants APIを使用して指定銘柄の空売り比率データを取得します。

    Args:
        ticker: 銘柄コード（例: 7203, 6758）
        from_date: 開始日（YYYY-MM-DD形式）
        to_date: 終了日（YYYY-MM-DD形式）

    Returns:
        空売り比率データのリスト

    Examples:
        - トヨタ自動車: /api/jquants/short-selling/7203
        - ソニー: /api/jquants/short-selling/6758?from_date=2024-01-01
    """
    if not jquants_client.is_available():
        return ShortSellingResponse(
            success=False,
            data=[],
            error="J-Quants API credentials not configured"
        )

    try:
        short_selling = jquants_client.get_short_selling_ratio(
            ticker=ticker,
            from_date=from_date,
            to_date=to_date
        )
        return ShortSellingResponse(success=True, data=short_selling)
    except ValueError as e:
        return ShortSellingResponse(
            success=False,
            data=[],
            error=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch short selling ratio: {str(e)}"
        )


@router.post("/cache/clear")
async def clear_cache():
    """
    キャッシュをクリア

    J-Quants APIのキャッシュデータを全てクリアします。

    Returns:
        クリア完了メッセージ
    """
    jquants_client.clear_cache()
    return {"success": True, "message": "Cache cleared successfully"}
