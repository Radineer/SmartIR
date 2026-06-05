"""
ポートフォリオマネージャー
ML予測 + Lead-Lag PCA + テクニカル指標のシグナル集約と売買判断
"""

import logging
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
import yfinance as yf

from app.services.paper_trading_engine import Order, INITIAL_CAPITAL

logger = logging.getLogger(__name__)

# --- 銘柄ユニバース（Lead-Lag PCA v4から） ---
JP_SECTOR_BASKETS: dict[str, list[str]] = {
    "Foods":         ["2914.T", "2502.T", "2269.T"],
    "Energy":        ["5020.T", "1605.T", "5019.T"],
    "Construction":  ["5401.T", "1925.T", "1928.T"],
    "Materials":     ["4063.T", "4452.T", "4901.T"],
    "Pharma":        ["4519.T", "4568.T", "4502.T"],
    "Auto":          ["7203.T", "7267.T", "7261.T"],
    "Steel":         ["5802.T", "5706.T", "5713.T"],
    "Machinery":     ["6301.T", "6367.T", "6503.T"],
    "ElecPrecision": ["6758.T", "6861.T", "6902.T"],
    "InfoComm":      ["9432.T", "9984.T", "9433.T"],
    "Utilities":     ["9501.T", "9502.T", "9503.T"],
    "Transport":     ["9020.T", "9021.T", "9022.T"],
    "Trading":       ["8058.T", "8031.T", "8001.T"],
    "Retail":        ["9983.T", "3382.T", "8267.T"],
    "Banks":         ["8306.T", "8316.T", "8411.T"],
    "Finance":       ["8766.T", "8750.T", "8591.T"],
    "RealEstate":    ["8801.T", "8802.T", "8830.T"],
}

ALL_TICKERS = [t for stocks in JP_SECTOR_BASKETS.values() for t in stocks]
TICKER_TO_SECTOR = {
    t: sector for sector, stocks in JP_SECTOR_BASKETS.items() for t in stocks
}

# --- 戦略パラメータ ---
WEIGHT_ML = 0.40
WEIGHT_PCA = 0.40
WEIGHT_TECH = 0.20

MAX_POSITION_PCT = 0.20   # 1銘柄あたり最大20%
MAX_POSITIONS = 8
MIN_SIGNAL = 0.15          # 最低シグナル閾値
STOP_LOSS_PCT = 0.10       # トレーリングストップ10%
CIRCUIT_BREAKER_NAV = INITIAL_CAPITAL * 0.85  # NAV 85,000円でサーキットブレーカー

# 銘柄名マッピング（表示用）
TICKER_NAMES: dict[str, str] = {
    "2914.T": "JT", "2502.T": "アサヒ", "2269.T": "明治HD",
    "5020.T": "ENEOS", "1605.T": "INPEX", "5019.T": "出光興産",
    "5401.T": "日本製鉄", "1925.T": "大和ハウス", "1928.T": "積水ハウス",
    "4063.T": "信越化学", "4452.T": "花王", "4901.T": "富士フイルム",
    "4519.T": "中外製薬", "4568.T": "第一三共", "4502.T": "武田薬品",
    "7203.T": "トヨタ", "7267.T": "ホンダ", "7261.T": "マツダ",
    "5802.T": "住友電工", "5706.T": "三井金属", "5713.T": "住友金属鉱山",
    "6301.T": "コマツ", "6367.T": "ダイキン", "6503.T": "三菱電機",
    "6758.T": "ソニーG", "6861.T": "キーエンス", "6902.T": "デンソー",
    "9432.T": "NTT", "9984.T": "ソフトバンクG", "9433.T": "KDDI",
    "9501.T": "東京電力", "9502.T": "中部電力", "9503.T": "関西電力",
    "9020.T": "JR東日本", "9021.T": "JR西日本", "9022.T": "JR東海",
    "8058.T": "三菱商事", "8031.T": "三井物産", "8001.T": "伊藤忠",
    "9983.T": "ファーストリテイリング", "3382.T": "セブン&アイ", "8267.T": "イオン",
    "8306.T": "三菱UFJ", "8316.T": "三井住友FG", "8411.T": "みずほFG",
    "8766.T": "東京海上", "8750.T": "第一生命", "8591.T": "オリックス",
    "8801.T": "三井不動産", "8802.T": "三菱地所", "8830.T": "住友不動産",
}


@dataclass
class Signal:
    """個別銘柄シグナル"""
    ticker: str
    company_name: str
    sector: str
    ml_signal: float         # -1 to +1
    pca_signal: float        # -1 to +1
    tech_signal: float       # -1 to +1
    combined: float          # 加重平均
    confidence: str          # "high" / "medium" / "low"


class PortfolioManager:
    """シグナル集約とポートフォリオ構築"""

    async def generate_signals(self) -> list[Signal]:
        """全ソースからシグナルを生成・集約"""
        logger.info("Generating signals for %d tickers...", len(ALL_TICKERS))

        ml_signals = await self._get_ml_signals()
        pca_signals = self._get_pca_signals()
        tech_signals = self._get_technical_signals()

        signals = []
        for ticker in ALL_TICKERS:
            ml = ml_signals.get(ticker, 0.0)
            pca = pca_signals.get(ticker, 0.0)
            tech = tech_signals.get(ticker, 0.0)

            combined = (
                WEIGHT_ML * ml + WEIGHT_PCA * pca + WEIGHT_TECH * tech
            )

            if abs(combined) < MIN_SIGNAL:
                continue

            confidence = "high" if abs(combined) > 0.6 else "medium" if abs(combined) > 0.4 else "low"

            signals.append(Signal(
                ticker=ticker,
                company_name=TICKER_NAMES.get(ticker, ticker),
                sector=TICKER_TO_SECTOR.get(ticker, ""),
                ml_signal=ml,
                pca_signal=pca,
                tech_signal=tech,
                combined=combined,
                confidence=confidence,
            ))

        # シグナル強度順にソート
        signals.sort(key=lambda s: abs(s.combined), reverse=True)
        logger.info("Generated %d signals above threshold", len(signals))
        return signals

    async def _get_ml_signals(self) -> dict[str, float]:
        """ML予測からシグナルを取得"""
        signals = {}
        try:
            from app.services.ml_predictor import ml_predictor_service

            for ticker in ALL_TICKERS:
                try:
                    result = await ml_predictor_service.predict(ticker, "1d")
                    if result.prediction == "up":
                        if result.confidence == "high":
                            signals[ticker] = 1.0
                        elif result.confidence == "medium":
                            signals[ticker] = 0.5
                        else:
                            signals[ticker] = 0.2
                    elif result.prediction == "down":
                        if result.confidence == "high":
                            signals[ticker] = -1.0
                        elif result.confidence == "medium":
                            signals[ticker] = -0.5
                        else:
                            signals[ticker] = -0.2
                    else:
                        signals[ticker] = 0.0
                except Exception as e:
                    logger.debug(f"ML prediction failed for {ticker}: {e}")
                    signals[ticker] = 0.0
        except ImportError:
            logger.warning("ML predictor not available, using zero signals")

        return signals

    def _get_pca_signals(self) -> dict[str, float]:
        """Lead-Lag PCA戦略からセクターシグナルを取得し個別銘柄にマッピング"""
        signals = {}
        try:
            # US ETF + JP sector basket のデータをダウンロード
            us_tickers = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
            all_dl = us_tickers + ALL_TICKERS

            data = yf.download(all_dl, period="90d", auto_adjust=True, progress=False)
            if data.empty:
                return signals

            close = data["Close"]

            # セクター平均リターン
            jp_sectors = list(JP_SECTOR_BASKETS.keys())
            stock_returns = close[ALL_TICKERS].pct_change()
            sector_returns = pd.DataFrame(index=stock_returns.index)
            for sector, stocks in JP_SECTOR_BASKETS.items():
                avail = [s for s in stocks if s in stock_returns.columns]
                if avail:
                    sector_returns[sector] = stock_returns[avail].mean(axis=1)

            us_returns = close[us_tickers].pct_change()

            # 週次リターン
            all_returns = pd.concat([us_returns, sector_returns], axis=1)
            weekly = all_returns.resample("W-FRI").apply(lambda x: (1 + x).prod() - 1)
            weekly = weekly.dropna()

            if len(weekly) < 6:
                logger.warning("Not enough weekly data for PCA signals")
                return signals

            # 簡易PCAシグナル: 直近リターンのz-scoreをセクターシグナルとして使用
            lookback = min(12, len(weekly) - 1)
            window = weekly.iloc[-lookback:]
            latest = weekly.iloc[-1]

            for sector in jp_sectors:
                if sector not in window.columns:
                    continue
                mu = window[sector].mean()
                std = window[sector].std()
                if std > 1e-10:
                    z = (latest[sector] - mu) / std
                    # z-scoreを[-1, 1]にクリップ
                    z_clipped = max(-1.0, min(1.0, z / 2))
                    for ticker in JP_SECTOR_BASKETS[sector]:
                        signals[ticker] = z_clipped

        except Exception as e:
            logger.error(f"PCA signal generation error: {e}")

        return signals

    def _get_technical_signals(self) -> dict[str, float]:
        """テクニカル指標（RSI + MACD）からシグナルを取得"""
        signals = {}
        try:
            data = yf.download(ALL_TICKERS, period="60d", auto_adjust=True, progress=False)
            if data.empty:
                return signals

            close = data["Close"]

            for ticker in ALL_TICKERS:
                if ticker not in close.columns:
                    continue

                prices = close[ticker].dropna()
                if len(prices) < 30:
                    continue

                signal = 0.0

                # RSI(14)
                delta = prices.diff()
                gain = delta.clip(lower=0).rolling(14).mean()
                loss = (-delta.clip(upper=0)).rolling(14).mean()
                rs = gain / loss.replace(0, np.nan)
                rsi = 100 - (100 / (1 + rs))
                if not rsi.empty:
                    current_rsi = rsi.iloc[-1]
                    if current_rsi < 30:
                        signal += 1.0  # 売られすぎ → 買い
                    elif current_rsi > 70:
                        signal -= 1.0  # 買われすぎ → 売り
                    elif current_rsi < 40:
                        signal += 0.3
                    elif current_rsi > 60:
                        signal -= 0.3

                # MACD
                ema12 = prices.ewm(span=12).mean()
                ema26 = prices.ewm(span=26).mean()
                macd = ema12 - ema26
                macd_signal = macd.ewm(span=9).mean()
                if len(macd) >= 2:
                    # MACDクロスオーバー
                    if macd.iloc[-1] > macd_signal.iloc[-1] and macd.iloc[-2] <= macd_signal.iloc[-2]:
                        signal += 0.5  # ゴールデンクロス
                    elif macd.iloc[-1] < macd_signal.iloc[-1] and macd.iloc[-2] >= macd_signal.iloc[-2]:
                        signal -= 0.5  # デッドクロス

                signals[ticker] = max(-1.0, min(1.0, signal))

        except Exception as e:
            logger.error(f"Technical signal generation error: {e}")

        return signals

    def compute_orders(
        self,
        signals: list[Signal],
        positions: list,
        cash: float,
        nav: float,
    ) -> list[Order]:
        """シグナルから売買注文を生成"""
        orders = []
        current_tickers = {p.ticker: p for p in positions}

        # --- 売り判断 ---
        for pos in positions:
            # トレーリングストップ
            if pos.peak_price and pos.current_price:
                drawdown = 1 - pos.current_price / pos.peak_price
                if drawdown >= STOP_LOSS_PCT:
                    orders.append(Order(
                        ticker=pos.ticker,
                        side="sell",
                        shares=pos.shares,
                        company_name=pos.company_name or "",
                        sector=pos.sector or "",
                        signal_source="stop_loss",
                        reason=f"トレーリングストップ発動（ピークから{drawdown*100:.1f}%下落）",
                    ))
                    continue

            # シグナル反転による売り
            sig = next((s for s in signals if s.ticker == pos.ticker), None)
            if sig and sig.combined < -MIN_SIGNAL:
                orders.append(Order(
                    ticker=pos.ticker,
                    side="sell",
                    shares=pos.shares,
                    company_name=pos.company_name or "",
                    sector=pos.sector or "",
                    signal_source=self._dominant_source(sig),
                    signal_strength=abs(sig.combined),
                    reason=self._build_reason(sig, "sell"),
                ))

        # --- サーキットブレーカー ---
        if nav <= CIRCUIT_BREAKER_NAV:
            logger.warning("Circuit breaker triggered! NAV=%.0f", nav)
            for pos in positions:
                if pos.ticker not in {o.ticker for o in orders}:
                    orders.append(Order(
                        ticker=pos.ticker,
                        side="sell",
                        shares=round(pos.shares * 0.5, 4),
                        company_name=pos.company_name or "",
                        signal_source="circuit_breaker",
                        reason=f"サーキットブレーカー（NAV ¥{nav:,.0f}）",
                    ))
            return orders

        # --- 買い判断 ---
        sell_tickers = {o.ticker for o in orders if o.side == "sell"}
        remaining_positions = len(current_tickers) - len(sell_tickers)

        buy_candidates = [
            s for s in signals
            if s.combined > MIN_SIGNAL
            and s.ticker not in current_tickers
            and s.ticker not in sell_tickers
        ]

        slots = MAX_POSITIONS - remaining_positions
        max_per_position = nav * MAX_POSITION_PCT

        for sig in buy_candidates[:slots]:
            if cash < 1000:  # 最低1000円
                break

            amount = min(max_per_position, cash * 0.9)  # 余裕を残す
            # 株価から株数を逆算（後でexecute_ordersが最終調整）
            orders.append(Order(
                ticker=sig.ticker,
                side="buy",
                shares=0,  # 金額ベース → execute時に株数計算
                company_name=sig.company_name,
                sector=sig.sector,
                signal_source=self._dominant_source(sig),
                signal_strength=sig.combined,
                reason=self._build_reason(sig, "buy"),
            ))
            cash -= amount  # 仮の資金確保

        return orders

    def resolve_share_counts(
        self, orders: list[Order], prices: dict[str, float], nav: float
    ) -> list[Order]:
        """金額ベースの注文を株数に変換"""
        max_per_position = nav * MAX_POSITION_PCT
        resolved = []

        for order in orders:
            if order.side == "sell":
                resolved.append(order)
                continue

            price = prices.get(order.ticker)
            if not price or price <= 0:
                continue

            amount = min(max_per_position, nav * 0.15)  # 保守的に15%
            shares = round(amount / price, 4)
            if shares < 0.01:
                continue

            order.shares = shares
            resolved.append(order)

        return resolved

    def _dominant_source(self, sig: Signal) -> str:
        """最も影響の大きいシグナルソースを返す"""
        sources = {
            "ml": abs(sig.ml_signal) * WEIGHT_ML,
            "lead_lag": abs(sig.pca_signal) * WEIGHT_PCA,
            "technical": abs(sig.tech_signal) * WEIGHT_TECH,
        }
        return max(sources, key=sources.get)

    def _build_reason(self, sig: Signal, side: str) -> str:
        """売買理由を日本語で構築"""
        parts = []
        if abs(sig.ml_signal) > 0.3:
            direction = "上昇" if sig.ml_signal > 0 else "下落"
            parts.append(f"ML予測: {direction}（{abs(sig.ml_signal):.1f}）")
        if abs(sig.pca_signal) > 0.3:
            direction = "強気" if sig.pca_signal > 0 else "弱気"
            parts.append(f"PCAシグナル: {sig.sector}{direction}（{abs(sig.pca_signal):.1f}）")
        if abs(sig.tech_signal) > 0.3:
            if sig.tech_signal > 0:
                parts.append("テクニカル: 売られすぎ/MACD買いシグナル")
            else:
                parts.append("テクニカル: 買われすぎ/MACD売りシグナル")

        action = "買い" if side == "buy" else "売り"
        return f"{action}判断 - " + "、".join(parts) if parts else f"統合シグナル{action}（{sig.combined:+.2f}）"
