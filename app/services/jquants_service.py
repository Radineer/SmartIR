"""
J-Quants API サービス
日本取引所グループ公式APIを使用して株価・財務情報等を取得
"""

import os
import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List, Any
from pydantic import BaseModel
from zoneinfo import ZoneInfo

import jquantsapi
import pandas as pd

logger = logging.getLogger(__name__)

# タイムゾーン設定
JST = ZoneInfo("Asia/Tokyo")


class StockPrice(BaseModel):
    """株価四本値データ"""
    date: str
    code: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None
    turnover_value: Optional[float] = None
    adjustment_factor: Optional[float] = None
    adjustment_open: Optional[float] = None
    adjustment_high: Optional[float] = None
    adjustment_low: Optional[float] = None
    adjustment_close: Optional[float] = None
    adjustment_volume: Optional[float] = None


class FinancialStatement(BaseModel):
    """財務情報データ"""
    disclosed_date: Optional[str] = None
    code: str
    company_name: Optional[str] = None
    fiscal_year: Optional[str] = None
    fiscal_quarter: Optional[int] = None
    type_of_document: Optional[str] = None
    net_sales: Optional[float] = None
    operating_profit: Optional[float] = None
    ordinary_profit: Optional[float] = None
    profit: Optional[float] = None
    earnings_per_share: Optional[float] = None
    total_assets: Optional[float] = None
    equity: Optional[float] = None
    equity_to_asset_ratio: Optional[float] = None
    book_value_per_share: Optional[float] = None
    cash_flows_from_operating_activities: Optional[float] = None
    cash_flows_from_investing_activities: Optional[float] = None
    cash_flows_from_financing_activities: Optional[float] = None
    result_dividend_per_share_annual: Optional[float] = None
    forecast_dividend_per_share_annual: Optional[float] = None
    number_of_issued_and_outstanding_shares_at_the_end_of_fiscal_year_including_treasury_stock: Optional[int] = None


class ListedCompany(BaseModel):
    """上場企業情報"""
    code: str
    company_name: str
    company_name_english: Optional[str] = None
    sector17_code: Optional[str] = None
    sector17_code_name: Optional[str] = None
    sector33_code: Optional[str] = None
    sector33_code_name: Optional[str] = None
    scale_category: Optional[str] = None
    market_code: Optional[str] = None
    market_code_name: Optional[str] = None


class SectorInfo(BaseModel):
    """業種情報"""
    date: str
    sector_code: str
    sector_name: Optional[str] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None


class ShortSellingInfo(BaseModel):
    """空売り比率情報"""
    date: str
    code: str
    selling_exempt_volume: Optional[int] = None
    selling_short_volume: Optional[int] = None
    total_sell_volume: Optional[int] = None
    selling_short_ratio: Optional[float] = None


class JQuantsClient:
    """
    J-Quants APIクライアント
    認証とトークン自動更新を管理
    """

    def __init__(self):
        self._client: Optional[jquantsapi.Client] = None
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 300  # キャッシュ有効期間（秒）
        self._initialized = False

    def _get_client(self) -> jquantsapi.Client:
        """認証済みクライアントを取得（遅延初期化）"""
        if self._client is None:
            mail_address = os.getenv("JQUANTS_MAIL_ADDRESS")
            password = os.getenv("JQUANTS_PASSWORD")

            if not mail_address or not password:
                raise ValueError(
                    "JQUANTS_MAIL_ADDRESS and JQUANTS_PASSWORD environment variables are required"
                )

            try:
                self._client = jquantsapi.Client(
                    mail_address=mail_address,
                    password=password
                )
                self._initialized = True
                logger.info("J-Quants API client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize J-Quants client: {e}")
                raise

        return self._client

    def _is_cache_valid(self, key: str) -> bool:
        """キャッシュが有効かどうか確認"""
        if key not in self._cache:
            return False
        cached = self._cache[key]
        cached_time = cached.get("cached_at")
        if not cached_time:
            return False
        return (datetime.now() - cached_time).total_seconds() < self._cache_ttl

    def _set_cache(self, key: str, data: Any) -> None:
        """キャッシュにデータを保存"""
        self._cache[key] = {
            "data": data,
            "cached_at": datetime.now()
        }

    def _get_cache(self, key: str) -> Optional[Any]:
        """キャッシュからデータを取得"""
        if self._is_cache_valid(key):
            return self._cache[key]["data"]
        return None

    def is_available(self) -> bool:
        """APIが利用可能かどうか確認"""
        mail_address = os.getenv("JQUANTS_MAIL_ADDRESS")
        password = os.getenv("JQUANTS_PASSWORD")
        return bool(mail_address and password)

    def get_stock_prices(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[StockPrice]:
        """
        株価四本値を取得

        Args:
            ticker: 銘柄コード（例: 7203）
            start_date: 開始日（YYYY-MM-DD形式）
            end_date: 終了日（YYYY-MM-DD形式）

        Returns:
            StockPriceオブジェクトのリスト
        """
        try:
            client = self._get_client()

            # デフォルトの日付設定
            if end_date is None:
                end_dt = datetime.now(JST)
            else:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=JST)

            if start_date is None:
                start_dt = end_dt - timedelta(days=30)
            else:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=JST)

            # キャッシュキー
            cache_key = f"prices_{ticker}_{start_dt.date()}_{end_dt.date()}"
            cached_data = self._get_cache(cache_key)
            if cached_data:
                return cached_data

            # API呼び出し
            df = client.get_prices_daily_quotes(
                code=ticker,
                from_yyyymmdd=start_dt.strftime("%Y%m%d"),
                to_yyyymmdd=end_dt.strftime("%Y%m%d")
            )

            if df is None or df.empty:
                return []

            # データ変換
            prices = []
            for _, row in df.iterrows():
                price = StockPrice(
                    date=str(row.get("Date", "")),
                    code=str(row.get("Code", ticker)),
                    open=row.get("Open"),
                    high=row.get("High"),
                    low=row.get("Low"),
                    close=row.get("Close"),
                    volume=int(row.get("Volume")) if pd.notna(row.get("Volume")) else None,
                    turnover_value=row.get("TurnoverValue"),
                    adjustment_factor=row.get("AdjustmentFactor"),
                    adjustment_open=row.get("AdjustmentOpen"),
                    adjustment_high=row.get("AdjustmentHigh"),
                    adjustment_low=row.get("AdjustmentLow"),
                    adjustment_close=row.get("AdjustmentClose"),
                    adjustment_volume=row.get("AdjustmentVolume"),
                )
                prices.append(price)

            self._set_cache(cache_key, prices)
            return prices

        except Exception as e:
            logger.error(f"Failed to get stock prices for {ticker}: {e}")
            raise

    def get_financial_statements(self, ticker: str) -> List[FinancialStatement]:
        """
        財務情報を取得

        Args:
            ticker: 銘柄コード（例: 7203）

        Returns:
            FinancialStatementオブジェクトのリスト
        """
        try:
            client = self._get_client()

            # キャッシュキー
            cache_key = f"financials_{ticker}"
            cached_data = self._get_cache(cache_key)
            if cached_data:
                return cached_data

            # API呼び出し
            df = client.get_fins_statements(code=ticker)

            if df is None or df.empty:
                return []

            # データ変換
            statements = []
            for _, row in df.iterrows():
                statement = FinancialStatement(
                    disclosed_date=str(row.get("DisclosedDate", "")) if pd.notna(row.get("DisclosedDate")) else None,
                    code=str(row.get("LocalCode", ticker)),
                    company_name=row.get("CompanyName"),
                    fiscal_year=str(row.get("FiscalYear", "")) if pd.notna(row.get("FiscalYear")) else None,
                    fiscal_quarter=int(row.get("CurrentFiscalYearEndDate")[-1]) if pd.notna(row.get("CurrentFiscalYearEndDate")) and row.get("CurrentFiscalYearEndDate") else None,
                    type_of_document=row.get("TypeOfDocument"),
                    net_sales=row.get("NetSales"),
                    operating_profit=row.get("OperatingProfit"),
                    ordinary_profit=row.get("OrdinaryProfit"),
                    profit=row.get("Profit"),
                    earnings_per_share=row.get("EarningsPerShare"),
                    total_assets=row.get("TotalAssets"),
                    equity=row.get("Equity"),
                    equity_to_asset_ratio=row.get("EquityToAssetRatio"),
                    book_value_per_share=row.get("BookValuePerShare"),
                    cash_flows_from_operating_activities=row.get("CashFlowsFromOperatingActivities"),
                    cash_flows_from_investing_activities=row.get("CashFlowsFromInvestingActivities"),
                    cash_flows_from_financing_activities=row.get("CashFlowsFromFinancingActivities"),
                    result_dividend_per_share_annual=row.get("ResultDividendPerShareAnnual"),
                    forecast_dividend_per_share_annual=row.get("ForecastDividendPerShareAnnual"),
                    number_of_issued_and_outstanding_shares_at_the_end_of_fiscal_year_including_treasury_stock=int(row.get("NumberOfIssuedAndOutstandingSharesAtTheEndOfFiscalYearIncludingTreasuryStock")) if pd.notna(row.get("NumberOfIssuedAndOutstandingSharesAtTheEndOfFiscalYearIncludingTreasuryStock")) else None,
                )
                statements.append(statement)

            self._set_cache(cache_key, statements)
            return statements

        except Exception as e:
            logger.error(f"Failed to get financial statements for {ticker}: {e}")
            raise

    def get_listed_companies(
        self,
        code: Optional[str] = None,
        date_yyyymmdd: Optional[str] = None
    ) -> List[ListedCompany]:
        """
        上場企業一覧を取得

        Args:
            code: 銘柄コード（指定時はその銘柄のみ）
            date_yyyymmdd: 取得日（YYYYMMDD形式）

        Returns:
            ListedCompanyオブジェクトのリスト
        """
        try:
            client = self._get_client()

            # キャッシュキー
            cache_key = f"companies_{code or 'all'}_{date_yyyymmdd or 'latest'}"
            cached_data = self._get_cache(cache_key)
            if cached_data:
                return cached_data

            # API呼び出し
            df = client.get_listed_info(code=code, date_yyyymmdd=date_yyyymmdd)

            if df is None or df.empty:
                return []

            # データ変換
            companies = []
            for _, row in df.iterrows():
                company = ListedCompany(
                    code=str(row.get("Code", "")),
                    company_name=row.get("CompanyName", ""),
                    company_name_english=row.get("CompanyNameEnglish"),
                    sector17_code=row.get("Sector17Code"),
                    sector17_code_name=row.get("Sector17CodeName"),
                    sector33_code=row.get("Sector33Code"),
                    sector33_code_name=row.get("Sector33CodeName"),
                    scale_category=row.get("ScaleCategory"),
                    market_code=row.get("MarketCode"),
                    market_code_name=row.get("MarketCodeName"),
                )
                companies.append(company)

            self._set_cache(cache_key, companies)
            return companies

        except Exception as e:
            logger.error(f"Failed to get listed companies: {e}")
            raise

    def get_sector_info(
        self,
        sector_code: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> List[SectorInfo]:
        """
        業種別情報を取得

        Args:
            sector_code: 業種コード（17業種または33業種）
            from_date: 開始日（YYYY-MM-DD形式）
            to_date: 終了日（YYYY-MM-DD形式）

        Returns:
            SectorInfoオブジェクトのリスト
        """
        try:
            client = self._get_client()

            # デフォルトの日付設定
            if to_date is None:
                to_dt = datetime.now(JST)
            else:
                to_dt = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=JST)

            if from_date is None:
                from_dt = to_dt - timedelta(days=30)
            else:
                from_dt = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=JST)

            # キャッシュキー
            cache_key = f"sectors_{sector_code or 'all'}_{from_dt.date()}_{to_dt.date()}"
            cached_data = self._get_cache(cache_key)
            if cached_data:
                return cached_data

            # API呼び出し（33業種指数）
            df = client.get_indices_topix(
                from_yyyymmdd=from_dt.strftime("%Y%m%d"),
                to_yyyymmdd=to_dt.strftime("%Y%m%d")
            )

            if df is None or df.empty:
                return []

            # 業種コードでフィルタリング
            if sector_code:
                df = df[df["Code"] == sector_code]

            # データ変換
            sectors = []
            for _, row in df.iterrows():
                sector = SectorInfo(
                    date=str(row.get("Date", "")),
                    sector_code=str(row.get("Code", "")),
                    sector_name=row.get("Name"),
                    open=row.get("Open"),
                    high=row.get("High"),
                    low=row.get("Low"),
                    close=row.get("Close"),
                )
                sectors.append(sector)

            self._set_cache(cache_key, sectors)
            return sectors

        except Exception as e:
            logger.error(f"Failed to get sector info: {e}")
            raise

    def get_short_selling_ratio(
        self,
        ticker: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> List[ShortSellingInfo]:
        """
        空売り比率を取得

        Args:
            ticker: 銘柄コード（例: 7203）
            from_date: 開始日（YYYY-MM-DD形式）
            to_date: 終了日（YYYY-MM-DD形式）

        Returns:
            ShortSellingInfoオブジェクトのリスト
        """
        try:
            client = self._get_client()

            # デフォルトの日付設定
            if to_date is None:
                to_dt = datetime.now(JST)
            else:
                to_dt = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=JST)

            if from_date is None:
                from_dt = to_dt - timedelta(days=30)
            else:
                from_dt = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=JST)

            # キャッシュキー
            cache_key = f"short_selling_{ticker}_{from_dt.date()}_{to_dt.date()}"
            cached_data = self._get_cache(cache_key)
            if cached_data:
                return cached_data

            # API呼び出し
            df = client.get_markets_short_selling(
                code=ticker,
                from_yyyymmdd=from_dt.strftime("%Y%m%d"),
                to_yyyymmdd=to_dt.strftime("%Y%m%d")
            )

            if df is None or df.empty:
                return []

            # データ変換
            short_selling = []
            for _, row in df.iterrows():
                info = ShortSellingInfo(
                    date=str(row.get("Date", "")),
                    code=str(row.get("Code", ticker)),
                    selling_exempt_volume=int(row.get("SellingExemptVolume")) if pd.notna(row.get("SellingExemptVolume")) else None,
                    selling_short_volume=int(row.get("SellingShortVolume")) if pd.notna(row.get("SellingShortVolume")) else None,
                    total_sell_volume=int(row.get("TotalSellVolume")) if pd.notna(row.get("TotalSellVolume")) else None,
                    selling_short_ratio=row.get("SellingShortRatio"),
                )
                short_selling.append(info)

            self._set_cache(cache_key, short_selling)
            return short_selling

        except Exception as e:
            logger.error(f"Failed to get short selling ratio for {ticker}: {e}")
            raise

    def clear_cache(self) -> None:
        """キャッシュをクリア"""
        self._cache.clear()
        logger.info("J-Quants cache cleared")


# シングルトンインスタンス
jquants_client = JQuantsClient()
