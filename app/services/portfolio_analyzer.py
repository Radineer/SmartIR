"""
ポートフォリオ分析・リスク管理サービス
PySystemTrade的アプローチでVaR、相関分析、リバランス提案を提供
"""

import pandas as pd
import numpy as np
from scipy import stats
from scipy.optimize import minimize
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel
from datetime import datetime, timedelta
import yfinance as yf
import logging

logger = logging.getLogger(__name__)


# ==================== データモデル ====================

class Position(BaseModel):
    """ポートフォリオのポジション"""
    ticker: str
    shares: int
    avg_price: float
    current_price: Optional[float] = None
    sector: Optional[str] = None


class PortfolioMetrics(BaseModel):
    """ポートフォリオの主要メトリクス"""
    total_value: float
    total_cost: float
    total_return: float
    total_return_pct: float
    daily_var_95: float  # 95% VaR (日次)
    daily_var_99: float  # 99% VaR (日次)
    volatility: float  # 年率ボラティリティ
    sharpe_ratio: float
    max_drawdown: float
    sector_exposure: Dict[str, float]  # セクター別配分
    position_weights: Dict[str, float]  # 銘柄別ウェイト


class CorrelationAnalysis(BaseModel):
    """相関分析結果"""
    correlation_matrix: Dict[str, Dict[str, float]]
    highly_correlated_pairs: List[Dict]  # 相関0.7以上のペア
    low_correlated_pairs: List[Dict]  # 相関-0.3〜0.3のペア
    diversification_score: float  # 0-100


class RebalanceSuggestion(BaseModel):
    """リバランス提案"""
    ticker: str
    current_weight: float
    target_weight: float
    action: str  # "buy", "sell", "hold"
    amount: float  # 金額
    shares_change: int  # 株数変更
    reason: str


class EfficientFrontierPoint(BaseModel):
    """効率的フロンティアのポイント"""
    expected_return: float
    volatility: float
    sharpe_ratio: float
    weights: Dict[str, float]


class RiskDecomposition(BaseModel):
    """リスク分解"""
    ticker: str
    weight: float
    marginal_var: float
    component_var: float
    contribution_pct: float


# ==================== セクター定義 ====================

SECTOR_MAPPING = {
    # 自動車
    "7203.T": "自動車", "7267.T": "自動車", "7201.T": "自動車",
    # 電機・精密
    "6758.T": "電機・精密", "6861.T": "電機・精密", "6501.T": "電機・精密",
    "6902.T": "電機・精密", "6752.T": "電機・精密", "6971.T": "電機・精密",
    # 金融
    "8306.T": "金融", "8316.T": "金融", "8411.T": "金融",
    "8035.T": "金融", "8766.T": "金融",
    # 通信
    "9432.T": "通信", "9433.T": "通信", "9434.T": "通信",
    # IT・サービス
    "9984.T": "IT・サービス", "6098.T": "IT・サービス", "4689.T": "IT・サービス",
    "4755.T": "IT・サービス", "3382.T": "IT・サービス",
    # 医薬品
    "4502.T": "医薬品", "4503.T": "医薬品", "4568.T": "医薬品",
    # ゲーム・エンタメ
    "7974.T": "ゲーム・エンタメ", "9697.T": "ゲーム・エンタメ",
    # 素材
    "5401.T": "素材", "5411.T": "素材", "4063.T": "素材",
    # 商社
    "8058.T": "商社", "8031.T": "商社", "8001.T": "商社",
    # 小売
    "9983.T": "小売", "8267.T": "小売", "3099.T": "小売",
    # 食品
    "2914.T": "食品", "2502.T": "食品", "2503.T": "食品",
    # 不動産
    "8801.T": "不動産", "8802.T": "不動産",
    # 建設
    "1801.T": "建設", "1802.T": "建設",
    # 運輸
    "9020.T": "運輸", "9021.T": "運輸", "9022.T": "運輸",
    # 米国株
    "AAPL": "テクノロジー", "MSFT": "テクノロジー", "GOOGL": "テクノロジー",
    "AMZN": "Eコマース", "NVDA": "半導体", "TSLA": "自動車",
    "META": "テクノロジー", "JPM": "金融", "JNJ": "ヘルスケア",
}

SECTOR_INFO = {
    "自動車": {"risk_weight": 1.2, "description": "景気敏感、為替影響大"},
    "電機・精密": {"risk_weight": 1.1, "description": "技術革新リスク、需要変動"},
    "金融": {"risk_weight": 1.0, "description": "金利感応度高、規制リスク"},
    "通信": {"risk_weight": 0.7, "description": "ディフェンシブ、安定配当"},
    "IT・サービス": {"risk_weight": 1.3, "description": "成長性高、バリュエーションリスク"},
    "医薬品": {"risk_weight": 0.8, "description": "ディフェンシブ、開発リスク"},
    "ゲーム・エンタメ": {"risk_weight": 1.2, "description": "ヒット依存、消費者嗜好変化"},
    "素材": {"risk_weight": 1.1, "description": "景気敏感、コモディティ価格影響"},
    "商社": {"risk_weight": 1.0, "description": "資源価格影響、分散投資"},
    "小売": {"risk_weight": 0.9, "description": "消費動向、競争激化"},
    "食品": {"risk_weight": 0.6, "description": "ディフェンシブ、安定需要"},
    "不動産": {"risk_weight": 1.0, "description": "金利敏感、景気影響"},
    "建設": {"risk_weight": 1.0, "description": "公共投資、景気影響"},
    "運輸": {"risk_weight": 0.9, "description": "インフラ、燃料コスト"},
    "テクノロジー": {"risk_weight": 1.3, "description": "高成長、高ボラティリティ"},
    "Eコマース": {"risk_weight": 1.2, "description": "成長市場、競争激化"},
    "半導体": {"risk_weight": 1.4, "description": "景気循環、需給変動大"},
    "ヘルスケア": {"risk_weight": 0.8, "description": "ディフェンシブ、規制リスク"},
    "その他": {"risk_weight": 1.0, "description": "分類外"},
}


class PortfolioAnalyzer:
    """ポートフォリオ分析・リスク管理サービス"""

    def __init__(self):
        self._price_cache: Dict[str, pd.DataFrame] = {}
        self._cache_ttl = 300  # 5分
        self._cache_time: Dict[str, datetime] = {}
        self.risk_free_rate = 0.001  # 日本の無リスク金利（約0.1%）

    def _get_sector(self, ticker: str) -> str:
        """ティッカーからセクターを取得"""
        return SECTOR_MAPPING.get(ticker, "その他")

    async def _get_historical_prices(
        self,
        tickers: List[str],
        days: int = 252
    ) -> pd.DataFrame:
        """過去の価格データを取得"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=int(days * 1.5))  # 余裕を持って取得

        prices_dict = {}
        for ticker in tickers:
            try:
                # キャッシュチェック
                cache_key = f"{ticker}_{days}"
                if (cache_key in self._price_cache and
                    cache_key in self._cache_time and
                    (datetime.now() - self._cache_time[cache_key]).seconds < self._cache_ttl):
                    prices_dict[ticker] = self._price_cache[cache_key]
                    continue

                # Yahoo Financeからデータ取得
                stock = yf.Ticker(ticker)
                hist = stock.history(start=start_date, end=end_date)

                if not hist.empty:
                    prices_dict[ticker] = hist['Close']
                    self._price_cache[cache_key] = hist['Close']
                    self._cache_time[cache_key] = datetime.now()
            except Exception as e:
                logger.warning(f"Failed to fetch price for {ticker}: {e}")

        if not prices_dict:
            return pd.DataFrame()

        # DataFrameに変換
        prices_df = pd.DataFrame(prices_dict)
        prices_df = prices_df.dropna()

        # 最新のdays日分に制限
        if len(prices_df) > days:
            prices_df = prices_df.tail(days)

        return prices_df

    async def _get_current_prices(self, tickers: List[str]) -> Dict[str, float]:
        """現在価格を取得"""
        prices = {}
        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                price = (
                    info.get("regularMarketPrice") or
                    info.get("currentPrice") or
                    info.get("previousClose") or
                    0
                )
                prices[ticker] = float(price)
            except Exception as e:
                logger.warning(f"Failed to fetch current price for {ticker}: {e}")
                prices[ticker] = 0
        return prices

    def _calculate_returns(self, prices: pd.DataFrame) -> pd.DataFrame:
        """日次リターンを計算"""
        return prices.pct_change().dropna()

    async def analyze_portfolio(self, positions: List[Position]) -> PortfolioMetrics:
        """
        ポートフォリオの総合分析

        Args:
            positions: ポジションリスト

        Returns:
            PortfolioMetrics: ポートフォリオメトリクス
        """
        if not positions:
            raise ValueError("ポジションが空です")

        tickers = [p.ticker for p in positions]

        # 現在価格を取得
        current_prices = await self._get_current_prices(tickers)

        # ポジションに現在価格を設定
        for pos in positions:
            if pos.current_price is None:
                pos.current_price = current_prices.get(pos.ticker, pos.avg_price)

        # ポートフォリオ価値計算
        total_value = sum(p.shares * (p.current_price or p.avg_price) for p in positions)
        total_cost = sum(p.shares * p.avg_price for p in positions)
        total_return = total_value - total_cost
        total_return_pct = (total_return / total_cost * 100) if total_cost > 0 else 0

        # ウェイト計算
        position_weights = {}
        for pos in positions:
            value = pos.shares * (pos.current_price or pos.avg_price)
            position_weights[pos.ticker] = value / total_value if total_value > 0 else 0

        # 過去データ取得
        prices = await self._get_historical_prices(tickers, days=252)

        if prices.empty:
            # データが取得できない場合はデフォルト値を返す
            return PortfolioMetrics(
                total_value=total_value,
                total_cost=total_cost,
                total_return=total_return,
                total_return_pct=total_return_pct,
                daily_var_95=total_value * 0.02,
                daily_var_99=total_value * 0.03,
                volatility=0.2,
                sharpe_ratio=0,
                max_drawdown=0,
                sector_exposure=await self.analyze_sector_exposure(positions),
                position_weights=position_weights
            )

        returns = self._calculate_returns(prices)

        # ポートフォリオリターン計算
        weights = np.array([position_weights.get(t, 0) for t in returns.columns])
        portfolio_returns = (returns * weights).sum(axis=1)

        # ボラティリティ（年率）
        daily_vol = portfolio_returns.std()
        annual_vol = daily_vol * np.sqrt(252)

        # VaR計算
        var_95 = await self.calculate_var(positions, confidence=0.95)
        var_99 = await self.calculate_var(positions, confidence=0.99)

        # シャープレシオ
        annual_return = portfolio_returns.mean() * 252
        sharpe = (annual_return - self.risk_free_rate) / annual_vol if annual_vol > 0 else 0

        # 最大ドローダウン
        cumulative = (1 + portfolio_returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = abs(drawdown.min())

        # セクター配分
        sector_exposure = await self.analyze_sector_exposure(positions)

        return PortfolioMetrics(
            total_value=round(total_value, 2),
            total_cost=round(total_cost, 2),
            total_return=round(total_return, 2),
            total_return_pct=round(total_return_pct, 2),
            daily_var_95=round(var_95, 2),
            daily_var_99=round(var_99, 2),
            volatility=round(annual_vol, 4),
            sharpe_ratio=round(sharpe, 4),
            max_drawdown=round(max_drawdown, 4),
            sector_exposure=sector_exposure,
            position_weights={k: round(v, 4) for k, v in position_weights.items()}
        )

    async def calculate_var(
        self,
        positions: List[Position],
        confidence: float = 0.95,
        method: str = "historical"
    ) -> float:
        """
        Value at Risk計算

        Args:
            positions: ポジションリスト
            confidence: 信頼水準（0.95 or 0.99）
            method: 計算方法（"historical", "parametric", "montecarlo"）

        Returns:
            float: VaR金額
        """
        tickers = [p.ticker for p in positions]

        # 現在価格と過去データ取得
        current_prices = await self._get_current_prices(tickers)
        prices = await self._get_historical_prices(tickers, days=252)

        if prices.empty:
            # フォールバック: 概算値を返す
            total_value = sum(
                p.shares * (current_prices.get(p.ticker, p.avg_price))
                for p in positions
            )
            return total_value * (0.02 if confidence == 0.95 else 0.03)

        returns = self._calculate_returns(prices)

        # ウェイト計算
        total_value = sum(
            p.shares * current_prices.get(p.ticker, p.avg_price)
            for p in positions
        )
        weights = np.array([
            (p.shares * current_prices.get(p.ticker, p.avg_price)) / total_value
            for p in positions
        ])

        # 銘柄順序を揃える
        ordered_returns = returns[[p.ticker for p in positions if p.ticker in returns.columns]]
        if ordered_returns.empty:
            return total_value * (0.02 if confidence == 0.95 else 0.03)

        # 不足している銘柄のウェイトを再計算
        available_tickers = ordered_returns.columns.tolist()
        adjusted_weights = np.array([
            (p.shares * current_prices.get(p.ticker, p.avg_price)) / total_value
            for p in positions if p.ticker in available_tickers
        ])
        adjusted_weights = adjusted_weights / adjusted_weights.sum()

        # ポートフォリオリターン
        portfolio_returns = (ordered_returns * adjusted_weights).sum(axis=1)

        if method == "historical":
            # ヒストリカルVaR
            var_pct = np.percentile(portfolio_returns, (1 - confidence) * 100)
            var = abs(var_pct) * total_value

        elif method == "parametric":
            # パラメトリックVaR（正規分布仮定）
            mean_return = portfolio_returns.mean()
            std_return = portfolio_returns.std()
            z_score = stats.norm.ppf(1 - confidence)
            var_pct = mean_return + z_score * std_return
            var = abs(var_pct) * total_value

        elif method == "montecarlo":
            # モンテカルロVaR
            mean_return = portfolio_returns.mean()
            std_return = portfolio_returns.std()
            simulations = np.random.normal(mean_return, std_return, 10000)
            var_pct = np.percentile(simulations, (1 - confidence) * 100)
            var = abs(var_pct) * total_value

        else:
            raise ValueError(f"Unknown VaR method: {method}")

        return round(var, 2)

    async def get_correlation_matrix(
        self,
        tickers: List[str],
        days: int = 252
    ) -> CorrelationAnalysis:
        """
        相関行列と分散分析

        Args:
            tickers: ティッカーリスト
            days: 分析期間（日数）

        Returns:
            CorrelationAnalysis: 相関分析結果
        """
        prices = await self._get_historical_prices(tickers, days)

        if prices.empty or len(prices.columns) < 2:
            return CorrelationAnalysis(
                correlation_matrix={},
                highly_correlated_pairs=[],
                low_correlated_pairs=[],
                diversification_score=50.0
            )

        returns = self._calculate_returns(prices)
        corr_matrix = returns.corr()

        # 辞書形式に変換
        corr_dict = {}
        for col in corr_matrix.columns:
            corr_dict[col] = {
                idx: round(corr_matrix.loc[idx, col], 4)
                for idx in corr_matrix.index
            }

        # 高相関ペア（0.7以上）
        highly_correlated = []
        low_correlated = []

        for i, ticker1 in enumerate(corr_matrix.columns):
            for j, ticker2 in enumerate(corr_matrix.columns):
                if i < j:  # 重複を避ける
                    corr_val = corr_matrix.loc[ticker1, ticker2]
                    pair_info = {
                        "ticker1": ticker1,
                        "ticker2": ticker2,
                        "correlation": round(corr_val, 4),
                        "sector1": self._get_sector(ticker1),
                        "sector2": self._get_sector(ticker2)
                    }
                    if corr_val >= 0.7:
                        highly_correlated.append(pair_info)
                    elif -0.3 <= corr_val <= 0.3:
                        low_correlated.append(pair_info)

        # 分散スコア計算（相関が低いほど高スコア）
        n = len(tickers)
        if n > 1:
            # 相関行列の上三角部分の平均
            upper_tri = corr_matrix.values[np.triu_indices(n, k=1)]
            avg_corr = np.mean(np.abs(upper_tri))
            # 平均相関が0なら100点、1なら0点
            diversification_score = max(0, min(100, (1 - avg_corr) * 100))
        else:
            diversification_score = 0

        return CorrelationAnalysis(
            correlation_matrix=corr_dict,
            highly_correlated_pairs=sorted(
                highly_correlated,
                key=lambda x: x["correlation"],
                reverse=True
            ),
            low_correlated_pairs=sorted(
                low_correlated,
                key=lambda x: abs(x["correlation"])
            ),
            diversification_score=round(diversification_score, 2)
        )

    async def suggest_rebalance(
        self,
        positions: List[Position],
        target_volatility: float = 0.15,
        method: str = "volatility_targeting"
    ) -> List[RebalanceSuggestion]:
        """
        リバランス提案

        Args:
            positions: 現在のポジション
            target_volatility: 目標年率ボラティリティ
            method: リバランス方法
                - "volatility_targeting": ボラティリティターゲティング
                - "equal_weight": 均等配分
                - "risk_parity": リスクパリティ
                - "min_variance": 最小分散

        Returns:
            List[RebalanceSuggestion]: リバランス提案リスト
        """
        if not positions:
            return []

        tickers = [p.ticker for p in positions]
        current_prices = await self._get_current_prices(tickers)
        prices = await self._get_historical_prices(tickers, days=252)

        # 現在の総資産価値
        total_value = sum(
            p.shares * current_prices.get(p.ticker, p.avg_price)
            for p in positions
        )

        # 現在のウェイト
        current_weights = {
            p.ticker: (p.shares * current_prices.get(p.ticker, p.avg_price)) / total_value
            for p in positions
        }

        if prices.empty:
            # データがない場合は均等配分を提案
            target_weights = {t: 1.0 / len(tickers) for t in tickers}
        else:
            returns = self._calculate_returns(prices)

            if method == "volatility_targeting":
                target_weights = self._volatility_targeting(
                    returns, tickers, target_volatility
                )
            elif method == "equal_weight":
                target_weights = {t: 1.0 / len(tickers) for t in tickers}
            elif method == "risk_parity":
                target_weights = self._risk_parity(returns, tickers)
            elif method == "min_variance":
                target_weights = self._min_variance(returns, tickers)
            else:
                target_weights = {t: 1.0 / len(tickers) for t in tickers}

        # 提案を生成
        suggestions = []
        for pos in positions:
            ticker = pos.ticker
            current_w = current_weights.get(ticker, 0)
            target_w = target_weights.get(ticker, 0)
            diff = target_w - current_w

            price = current_prices.get(ticker, pos.avg_price)
            amount = diff * total_value
            shares_change = int(amount / price) if price > 0 else 0

            if abs(diff) < 0.01:  # 1%未満の差は無視
                action = "hold"
                reason = "現在のウェイトは目標に近い"
            elif diff > 0:
                action = "buy"
                reason = f"目標ウェイト{target_w:.1%}達成のため追加購入"
            else:
                action = "sell"
                reason = f"目標ウェイト{target_w:.1%}達成のため一部売却"

            suggestions.append(RebalanceSuggestion(
                ticker=ticker,
                current_weight=round(current_w, 4),
                target_weight=round(target_w, 4),
                action=action,
                amount=round(abs(amount), 2),
                shares_change=abs(shares_change) if action == "buy" else -abs(shares_change),
                reason=reason
            ))

        return sorted(suggestions, key=lambda x: abs(x.amount), reverse=True)

    def _volatility_targeting(
        self,
        returns: pd.DataFrame,
        tickers: List[str],
        target_vol: float
    ) -> Dict[str, float]:
        """ボラティリティターゲティングによるウェイト計算"""
        available_tickers = [t for t in tickers if t in returns.columns]
        if not available_tickers:
            return {t: 1.0 / len(tickers) for t in tickers}

        # 各銘柄のボラティリティ
        vols = returns[available_tickers].std() * np.sqrt(252)

        # 逆ボラティリティ加重
        inv_vols = 1 / vols
        inv_vols = inv_vols.fillna(0)

        # ウェイト計算
        weights = inv_vols / inv_vols.sum()

        # 目標ボラティリティにスケーリング
        port_vol = np.sqrt(
            np.dot(weights.values, np.dot(returns[available_tickers].cov() * 252, weights.values))
        )

        if port_vol > 0:
            scale = target_vol / port_vol
            weights = weights * min(scale, 1.0)  # レバレッジは避ける

        # 正規化
        weights = weights / weights.sum()

        result = {t: 0.0 for t in tickers}
        for t in available_tickers:
            result[t] = weights.get(t, 0)

        return result

    def _risk_parity(
        self,
        returns: pd.DataFrame,
        tickers: List[str]
    ) -> Dict[str, float]:
        """リスクパリティによるウェイト計算"""
        available_tickers = [t for t in tickers if t in returns.columns]
        if not available_tickers:
            return {t: 1.0 / len(tickers) for t in tickers}

        cov_matrix = returns[available_tickers].cov() * 252
        n = len(available_tickers)

        def risk_parity_objective(weights):
            port_var = np.dot(weights, np.dot(cov_matrix, weights))
            port_vol = np.sqrt(port_var)
            marginal_contrib = np.dot(cov_matrix, weights) / port_vol
            risk_contrib = weights * marginal_contrib
            target_risk = port_vol / n
            return np.sum((risk_contrib - target_risk) ** 2)

        constraints = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1}
        ]
        bounds = [(0.01, 0.5) for _ in range(n)]
        initial_weights = np.array([1.0 / n] * n)

        try:
            result = minimize(
                risk_parity_objective,
                initial_weights,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints
            )
            weights = result.x
        except Exception:
            weights = initial_weights

        result_dict = {t: 0.0 for t in tickers}
        for i, t in enumerate(available_tickers):
            result_dict[t] = weights[i]

        return result_dict

    def _min_variance(
        self,
        returns: pd.DataFrame,
        tickers: List[str]
    ) -> Dict[str, float]:
        """最小分散ポートフォリオのウェイト計算"""
        available_tickers = [t for t in tickers if t in returns.columns]
        if not available_tickers:
            return {t: 1.0 / len(tickers) for t in tickers}

        cov_matrix = returns[available_tickers].cov() * 252
        n = len(available_tickers)

        def portfolio_variance(weights):
            return np.dot(weights, np.dot(cov_matrix, weights))

        constraints = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1}
        ]
        bounds = [(0.01, 0.5) for _ in range(n)]
        initial_weights = np.array([1.0 / n] * n)

        try:
            result = minimize(
                portfolio_variance,
                initial_weights,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints
            )
            weights = result.x
        except Exception:
            weights = initial_weights

        result_dict = {t: 0.0 for t in tickers}
        for i, t in enumerate(available_tickers):
            result_dict[t] = weights[i]

        return result_dict

    async def calculate_efficient_frontier(
        self,
        tickers: List[str],
        n_points: int = 50
    ) -> List[EfficientFrontierPoint]:
        """
        効率的フロンティア計算

        Args:
            tickers: 分析対象のティッカー
            n_points: フロンティア上のポイント数

        Returns:
            List[EfficientFrontierPoint]: 効率的フロンティアのポイント
        """
        prices = await self._get_historical_prices(tickers, days=252)

        if prices.empty or len(prices.columns) < 2:
            return []

        returns = self._calculate_returns(prices)
        available_tickers = returns.columns.tolist()
        n = len(available_tickers)

        mean_returns = returns.mean() * 252
        cov_matrix = returns.cov() * 252

        def portfolio_stats(weights):
            ret = np.dot(weights, mean_returns)
            vol = np.sqrt(np.dot(weights, np.dot(cov_matrix, weights)))
            sharpe = (ret - self.risk_free_rate) / vol if vol > 0 else 0
            return ret, vol, sharpe

        def neg_sharpe(weights):
            _, _, sharpe = portfolio_stats(weights)
            return -sharpe

        # 制約条件
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
        bounds = [(0, 1) for _ in range(n)]

        # 最大シャープレシオポートフォリオ
        initial_weights = np.array([1.0 / n] * n)
        try:
            max_sharpe_result = minimize(
                neg_sharpe,
                initial_weights,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints
            )
            max_sharpe_weights = max_sharpe_result.x
        except Exception:
            max_sharpe_weights = initial_weights

        # 最小分散ポートフォリオ
        def portfolio_variance(weights):
            return np.dot(weights, np.dot(cov_matrix, weights))

        try:
            min_var_result = minimize(
                portfolio_variance,
                initial_weights,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints
            )
            min_var_weights = min_var_result.x
        except Exception:
            min_var_weights = initial_weights

        # リターン範囲を決定
        min_ret, _, _ = portfolio_stats(min_var_weights)
        max_ret = mean_returns.max()

        # 効率的フロンティアを計算
        frontier_points = []
        target_returns = np.linspace(min_ret, max_ret, n_points)

        for target_ret in target_returns:
            constraints_with_return = [
                {"type": "eq", "fun": lambda w: np.sum(w) - 1},
                {"type": "eq", "fun": lambda w, r=target_ret: np.dot(w, mean_returns) - r}
            ]

            try:
                result = minimize(
                    portfolio_variance,
                    initial_weights,
                    method="SLSQP",
                    bounds=bounds,
                    constraints=constraints_with_return
                )

                if result.success:
                    ret, vol, sharpe = portfolio_stats(result.x)
                    weights_dict = {
                        t: round(w, 4)
                        for t, w in zip(available_tickers, result.x)
                        if w > 0.001
                    }
                    frontier_points.append(EfficientFrontierPoint(
                        expected_return=round(ret, 4),
                        volatility=round(vol, 4),
                        sharpe_ratio=round(sharpe, 4),
                        weights=weights_dict
                    ))
            except Exception:
                continue

        return frontier_points

    async def analyze_sector_exposure(
        self,
        positions: List[Position]
    ) -> Dict[str, float]:
        """
        セクター別エクスポージャー分析

        Args:
            positions: ポジションリスト

        Returns:
            Dict[str, float]: セクター別の配分比率
        """
        current_prices = await self._get_current_prices([p.ticker for p in positions])

        total_value = sum(
            p.shares * current_prices.get(p.ticker, p.avg_price)
            for p in positions
        )

        if total_value == 0:
            return {}

        sector_values: Dict[str, float] = {}
        for pos in positions:
            sector = self._get_sector(pos.ticker)
            value = pos.shares * current_prices.get(pos.ticker, pos.avg_price)
            sector_values[sector] = sector_values.get(sector, 0) + value

        sector_exposure = {
            sector: round(value / total_value, 4)
            for sector, value in sector_values.items()
        }

        return dict(sorted(sector_exposure.items(), key=lambda x: x[1], reverse=True))

    async def calculate_risk_decomposition(
        self,
        positions: List[Position]
    ) -> List[RiskDecomposition]:
        """
        リスク分解分析

        Args:
            positions: ポジションリスト

        Returns:
            List[RiskDecomposition]: 各銘柄のリスク寄与度
        """
        tickers = [p.ticker for p in positions]
        current_prices = await self._get_current_prices(tickers)
        prices = await self._get_historical_prices(tickers, days=252)

        if prices.empty:
            return []

        returns = self._calculate_returns(prices)
        available_tickers = [t for t in tickers if t in returns.columns]

        if not available_tickers:
            return []

        # ウェイト計算
        total_value = sum(
            p.shares * current_prices.get(p.ticker, p.avg_price)
            for p in positions
        )
        weights = np.array([
            (p.shares * current_prices.get(p.ticker, p.avg_price)) / total_value
            for p in positions if p.ticker in available_tickers
        ])

        # 共分散行列
        cov_matrix = returns[available_tickers].cov() * 252

        # ポートフォリオボラティリティ
        port_var = np.dot(weights, np.dot(cov_matrix, weights))
        port_vol = np.sqrt(port_var)

        # 各銘柄のリスク寄与度
        marginal_var = np.dot(cov_matrix, weights) / port_vol
        component_var = weights * marginal_var

        results = []
        for i, ticker in enumerate(available_tickers):
            contribution_pct = component_var[i] / port_vol * 100

            results.append(RiskDecomposition(
                ticker=ticker,
                weight=round(weights[i], 4),
                marginal_var=round(marginal_var[i], 4),
                component_var=round(component_var[i], 4),
                contribution_pct=round(contribution_pct, 2)
            ))

        return sorted(results, key=lambda x: x.contribution_pct, reverse=True)

    def generate_iris_portfolio_review(
        self,
        metrics: PortfolioMetrics,
        suggestions: List[RebalanceSuggestion]
    ) -> str:
        """
        イリス（AIキャラクター）向けのポートフォリオレビュー生成

        Args:
            metrics: ポートフォリオメトリクス
            suggestions: リバランス提案

        Returns:
            str: イリス用のスクリプト
        """
        # リスク評価
        if metrics.volatility < 0.1:
            risk_level = "低リスク"
            risk_comment = "安定志向のポートフォリオです"
        elif metrics.volatility < 0.2:
            risk_level = "中リスク"
            risk_comment = "バランスの取れたリスク水準です"
        else:
            risk_level = "高リスク"
            risk_comment = "積極的なポートフォリオです。リスク管理にご注意ください"

        # シャープレシオ評価
        if metrics.sharpe_ratio > 1.0:
            sharpe_comment = "効率的なリターンを上げています"
        elif metrics.sharpe_ratio > 0.5:
            sharpe_comment = "まずまずの効率性です"
        else:
            sharpe_comment = "リスクに対するリターンの効率が低めです"

        # セクター集中度チェック
        max_sector_weight = max(metrics.sector_exposure.values()) if metrics.sector_exposure else 0
        if max_sector_weight > 0.4:
            sector_comment = f"特定セクターへの集中度が高めです。分散を検討してください"
        else:
            sector_comment = "セクター分散は適切です"

        # リバランス提案のサマリー
        buy_suggestions = [s for s in suggestions if s.action == "buy"]
        sell_suggestions = [s for s in suggestions if s.action == "sell"]

        script = f"""
ポートフォリオレビューをお伝えしますね。

まず、現在のポートフォリオ価値は{metrics.total_value:,.0f}円、
トータルリターンは{metrics.total_return_pct:+.2f}%です。

リスク分析の結果、年率ボラティリティは{metrics.volatility:.1%}で、{risk_level}に分類されます。
{risk_comment}。

1日あたりの最大損失リスク（95%信頼区間）は{metrics.daily_var_95:,.0f}円と推計されます。

シャープレシオは{metrics.sharpe_ratio:.2f}で、{sharpe_comment}。

{sector_comment}

リバランス提案としては、
"""

        if buy_suggestions:
            script += "買い増しを検討すべき銘柄: "
            script += "、".join([s.ticker for s in buy_suggestions[:3]])
            script += "。\n"

        if sell_suggestions:
            script += "一部売却を検討すべき銘柄: "
            script += "、".join([s.ticker for s in sell_suggestions[:3]])
            script += "。\n"

        if not buy_suggestions and not sell_suggestions:
            script += "現在のポジションは目標配分に近いため、大きな調整は不要です。\n"

        script += "\n投資判断の参考にしてくださいね。"

        return script.strip()


# シングルトンインスタンス
portfolio_analyzer = PortfolioAnalyzer()
