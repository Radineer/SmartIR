"""
市況データ取得サービス
Yahoo Finance APIを使用して株価・為替等のリアルタイムデータを取得
"""

import yfinance as yf
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from pydantic import BaseModel
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)

# タイムゾーン設定
JST = ZoneInfo("Asia/Tokyo")


class QuoteData(BaseModel):
    """個別銘柄/指数のクォートデータ"""
    symbol: str
    name: str
    price: float
    change: float
    change_percent: float
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    previous_close: Optional[float] = None
    volume: Optional[int] = None
    market_cap: Optional[int] = None
    timestamp: str


class ChartData(BaseModel):
    """チャートデータ"""
    symbol: str
    name: str
    period: str
    interval: str
    data: List[Dict[str, Any]]


class MarketSummary(BaseModel):
    """市場サマリー"""
    timestamp: str
    indices: List[QuoteData]
    currencies: List[QuoteData]
    market_status: str


# 主要指数の定義
MAJOR_INDICES = {
    "^N225": "日経平均株価",
    "^TOPX": "TOPIX",
    "^DJI": "NYダウ工業株30種",
    "^GSPC": "S&P 500",
    "^IXIC": "NASDAQ総合",
    "^HSI": "香港ハンセン指数",
}

# 通貨ペア
CURRENCY_PAIRS = {
    "USDJPY=X": "ドル/円",
    "EURJPY=X": "ユーロ/円",
    "GBPJPY=X": "ポンド/円",
    "EURUSD=X": "ユーロ/ドル",
}

# 主要日本株
MAJOR_JP_STOCKS = {
    "7203.T": "トヨタ自動車",
    "6758.T": "ソニーグループ",
    "9984.T": "ソフトバンクグループ",
    "6861.T": "キーエンス",
    "8306.T": "三菱UFJフィナンシャル・グループ",
    "6501.T": "日立製作所",
    "9432.T": "日本電信電話(NTT)",
    "6098.T": "リクルートホールディングス",
    "4502.T": "武田薬品工業",
    "7974.T": "任天堂",
}

# 全銘柄辞書を統合
ALL_SYMBOLS = {**MAJOR_INDICES, **CURRENCY_PAIRS, **MAJOR_JP_STOCKS}


class MarketDataService:
    """市況データ取得サービス"""

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 60  # キャッシュ有効期間（秒）

    def _get_ticker(self, symbol: str) -> yf.Ticker:
        """Tickerオブジェクトを取得"""
        return yf.Ticker(symbol)

    def _get_name(self, symbol: str) -> str:
        """シンボルから名称を取得"""
        if symbol in ALL_SYMBOLS:
            return ALL_SYMBOLS[symbol]

        try:
            ticker = self._get_ticker(symbol)
            info = ticker.info
            # 日本株の場合は shortName を優先
            if symbol.endswith(".T"):
                return info.get("shortName", info.get("longName", symbol))
            return info.get("longName", info.get("shortName", symbol))
        except Exception:
            return symbol

    def _is_cache_valid(self, symbol: str) -> bool:
        """キャッシュが有効かどうか確認"""
        if symbol not in self._cache:
            return False
        cached = self._cache[symbol]
        cached_time = cached.get("cached_at")
        if not cached_time:
            return False
        return (datetime.now() - cached_time).total_seconds() < self._cache_ttl

    def get_quote(self, symbol: str) -> Optional[QuoteData]:
        """
        個別銘柄/指数のクォートを取得

        Args:
            symbol: ティッカーシンボル（例: ^N225, 7203.T, USDJPY=X）

        Returns:
            QuoteData オブジェクト
        """
        try:
            # キャッシュチェック
            if self._is_cache_valid(symbol):
                return self._cache[symbol]["data"]

            ticker = self._get_ticker(symbol)
            info = ticker.info

            # 最新価格を取得（複数のフィールドから取得を試みる）
            price = (
                info.get("regularMarketPrice") or
                info.get("currentPrice") or
                info.get("previousClose") or
                0
            )

            previous_close = info.get("regularMarketPreviousClose") or info.get("previousClose") or 0
            change = info.get("regularMarketChange", 0)
            change_percent = info.get("regularMarketChangePercent", 0)

            # 変化がない場合は計算
            if change == 0 and price and previous_close:
                change = price - previous_close
                change_percent = (change / previous_close * 100) if previous_close else 0

            quote = QuoteData(
                symbol=symbol,
                name=self._get_name(symbol),
                price=round(price, 2) if price else 0,
                change=round(change, 2) if change else 0,
                change_percent=round(change_percent, 2) if change_percent else 0,
                open=info.get("regularMarketOpen") or info.get("open"),
                high=info.get("regularMarketDayHigh") or info.get("dayHigh"),
                low=info.get("regularMarketDayLow") or info.get("dayLow"),
                previous_close=previous_close,
                volume=info.get("regularMarketVolume") or info.get("volume"),
                market_cap=info.get("marketCap"),
                timestamp=datetime.now(JST).isoformat()
            )

            # キャッシュに保存
            self._cache[symbol] = {
                "data": quote,
                "cached_at": datetime.now()
            }

            return quote

        except Exception as e:
            logger.error(f"Failed to get quote for {symbol}: {e}")
            return None

    def get_indices(self) -> List[QuoteData]:
        """
        主要指数一覧を取得

        Returns:
            主要指数のQuoteDataリスト
        """
        indices = []
        for symbol in MAJOR_INDICES.keys():
            quote = self.get_quote(symbol)
            if quote:
                indices.append(quote)
        return indices

    def get_currencies(self) -> List[QuoteData]:
        """
        主要通貨ペア一覧を取得

        Returns:
            主要通貨ペアのQuoteDataリスト
        """
        currencies = []
        for symbol in CURRENCY_PAIRS.keys():
            quote = self.get_quote(symbol)
            if quote:
                currencies.append(quote)
        return currencies

    def get_chart_data(
        self,
        symbol: str,
        period: str = "1d",
        interval: str = "5m"
    ) -> Optional[ChartData]:
        """
        チャートデータを取得

        Args:
            symbol: ティッカーシンボル
            period: 期間 (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: 間隔 (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)

        Returns:
            ChartData オブジェクト
        """
        try:
            ticker = self._get_ticker(symbol)

            # 期間に応じた適切な間隔を設定
            interval_map = {
                "1d": "5m",
                "5d": "15m",
                "1mo": "1h",
                "3mo": "1d",
                "6mo": "1d",
                "1y": "1d",
                "2y": "1wk",
                "5y": "1wk",
                "max": "1mo"
            }

            # 指定がなければ期間に応じた間隔を使用
            if interval == "5m" and period != "1d":
                interval = interval_map.get(period, interval)

            hist = ticker.history(period=period, interval=interval)

            if hist.empty:
                return None

            # データを整形
            chart_data = []
            for index, row in hist.iterrows():
                chart_data.append({
                    "timestamp": index.isoformat(),
                    "open": round(row["Open"], 2) if row["Open"] else None,
                    "high": round(row["High"], 2) if row["High"] else None,
                    "low": round(row["Low"], 2) if row["Low"] else None,
                    "close": round(row["Close"], 2) if row["Close"] else None,
                    "volume": int(row["Volume"]) if row["Volume"] else None,
                })

            return ChartData(
                symbol=symbol,
                name=self._get_name(symbol),
                period=period,
                interval=interval,
                data=chart_data
            )

        except Exception as e:
            logger.error(f"Failed to get chart data for {symbol}: {e}")
            return None

    def get_market_summary(self) -> MarketSummary:
        """
        本日の市場サマリーを取得

        Returns:
            MarketSummary オブジェクト
        """
        indices = self.get_indices()
        currencies = self.get_currencies()

        # 市場状態を判定（日本時間基準）
        now = datetime.now(JST)
        market_status = self._get_market_status(now)

        return MarketSummary(
            timestamp=now.isoformat(),
            indices=indices,
            currencies=currencies,
            market_status=market_status
        )

    def _get_market_status(self, now: datetime) -> str:
        """
        現在の市場状態を取得

        Args:
            now: 現在時刻（JST）

        Returns:
            市場状態の文字列
        """
        weekday = now.weekday()
        hour = now.hour
        minute = now.minute
        current_time = hour * 60 + minute

        # 土日は休場
        if weekday >= 5:
            return "closed_weekend"

        # 東証の取引時間
        # 前場: 9:00 - 11:30
        # 後場: 12:30 - 15:00
        morning_start = 9 * 60
        morning_end = 11 * 60 + 30
        afternoon_start = 12 * 60 + 30
        afternoon_end = 15 * 60

        if morning_start <= current_time < morning_end:
            return "open_morning"
        elif morning_end <= current_time < afternoon_start:
            return "lunch_break"
        elif afternoon_start <= current_time < afternoon_end:
            return "open_afternoon"
        elif current_time < morning_start:
            return "pre_market"
        else:
            return "after_hours"

    def search_symbol(self, query: str) -> List[Dict[str, str]]:
        """
        銘柄検索

        Args:
            query: 検索クエリ

        Returns:
            マッチした銘柄のリスト
        """
        results = []
        query_lower = query.lower()

        # 登録済み銘柄から検索
        for symbol, name in ALL_SYMBOLS.items():
            if query_lower in symbol.lower() or query_lower in name.lower():
                results.append({
                    "symbol": symbol,
                    "name": name
                })

        return results[:10]  # 最大10件

    def get_major_jp_stocks(self) -> List[QuoteData]:
        """
        主要日本株一覧を取得

        Returns:
            主要日本株のQuoteDataリスト
        """
        stocks = []
        for symbol in MAJOR_JP_STOCKS.keys():
            quote = self.get_quote(symbol)
            if quote:
                stocks.append(quote)
        return stocks


# シングルトンインスタンス
market_data_service = MarketDataService()
