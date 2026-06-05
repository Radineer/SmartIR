"""
バックテスト（戦略シミュレーション）サービス
backtesting.pyライブラリを使用してトレーディング戦略のバックテストを実行
"""

import yfinance as yf
import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
from backtesting.lib import crossover
from typing import Dict, List, Optional, Any, Type
from pydantic import BaseModel
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# ===== Pydantic Models =====

class BacktestConfig(BaseModel):
    """バックテスト設定"""
    ticker: str
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    initial_capital: float = 1000000  # 100万円
    strategy: str  # "sma_cross", "rsi", "macd", "bollinger", "golden_cross", "custom"
    params: Dict[str, Any] = {}  # 戦略パラメータ


class TradeRecord(BaseModel):
    """取引記録"""
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    pnl_percent: float
    is_long: bool


class BacktestResult(BaseModel):
    """バックテスト結果"""
    total_return: float  # 総リターン%
    annual_return: float  # 年率リターン%
    max_drawdown: float  # 最大ドローダウン%
    sharpe_ratio: float  # シャープレシオ
    win_rate: float  # 勝率%
    total_trades: int  # 総取引数
    profit_factor: float  # プロフィットファクター
    avg_trade_return: float  # 平均取引リターン%
    best_trade: float  # ベストトレード%
    worst_trade: float  # ワーストトレード%
    equity_curve: List[Dict[str, Any]]  # 資産推移
    trades: List[TradeRecord]  # 取引履歴
    drawdown_curve: List[Dict[str, Any]]  # ドローダウン推移


class StrategyInfo(BaseModel):
    """戦略情報"""
    id: str
    name: str
    description: str
    params: List[Dict[str, Any]]  # パラメータ定義


class OptimizationResult(BaseModel):
    """最適化結果"""
    best_params: Dict[str, Any]
    best_return: float
    best_sharpe: float
    optimization_history: List[Dict[str, Any]]


# ===== Trading Strategies =====

class SMACrossStrategy(Strategy):
    """
    SMA（単純移動平均）クロス戦略
    短期SMAが長期SMAを上抜けたら買い、下抜けたら売り
    """
    short_window = 10
    long_window = 30

    def init(self):
        close = pd.Series(self.data.Close)
        self.sma_short = self.I(lambda: close.rolling(self.short_window).mean())
        self.sma_long = self.I(lambda: close.rolling(self.long_window).mean())

    def next(self):
        if crossover(self.sma_short, self.sma_long):
            self.buy()
        elif crossover(self.sma_long, self.sma_short):
            self.position.close()


class RSIStrategy(Strategy):
    """
    RSI（相対力指数）戦略
    RSIが売られすぎ水準（デフォルト30）を下回ったら買い、
    買われすぎ水準（デフォルト70）を上回ったら売り
    """
    rsi_period = 14
    oversold = 30
    overbought = 70

    def init(self):
        close = pd.Series(self.data.Close)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.rsi_period).mean()
        rs = gain / loss
        self.rsi = self.I(lambda: 100 - (100 / (1 + rs)))

    def next(self):
        if self.rsi[-1] < self.oversold:
            if not self.position:
                self.buy()
        elif self.rsi[-1] > self.overbought:
            if self.position:
                self.position.close()


class MACDStrategy(Strategy):
    """
    MACD（移動平均収束拡散）戦略
    MACDがシグナルラインを上抜けたら買い、下抜けたら売り
    """
    fast_period = 12
    slow_period = 26
    signal_period = 9

    def init(self):
        close = pd.Series(self.data.Close)
        ema_fast = close.ewm(span=self.fast_period, adjust=False).mean()
        ema_slow = close.ewm(span=self.slow_period, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.signal_period, adjust=False).mean()

        self.macd = self.I(lambda: macd_line)
        self.signal = self.I(lambda: signal_line)

    def next(self):
        if crossover(self.macd, self.signal):
            self.buy()
        elif crossover(self.signal, self.macd):
            self.position.close()


class BollingerStrategy(Strategy):
    """
    ボリンジャーバンド戦略
    価格がロワーバンドを下回ったら買い、アッパーバンドを上回ったら売り
    """
    bb_period = 20
    bb_std = 2.0

    def init(self):
        close = pd.Series(self.data.Close)
        sma = close.rolling(self.bb_period).mean()
        std = close.rolling(self.bb_period).std()

        self.upper = self.I(lambda: sma + (std * self.bb_std))
        self.lower = self.I(lambda: sma - (std * self.bb_std))
        self.middle = self.I(lambda: sma)

    def next(self):
        if self.data.Close[-1] < self.lower[-1]:
            if not self.position:
                self.buy()
        elif self.data.Close[-1] > self.upper[-1]:
            if self.position:
                self.position.close()


class GoldenCrossStrategy(Strategy):
    """
    ゴールデンクロス戦略
    50日移動平均が200日移動平均を上抜けたら買い（ゴールデンクロス）、
    下抜けたら売り（デッドクロス）
    """
    short_window = 50
    long_window = 200

    def init(self):
        close = pd.Series(self.data.Close)
        self.sma_short = self.I(lambda: close.rolling(self.short_window).mean())
        self.sma_long = self.I(lambda: close.rolling(self.long_window).mean())

    def next(self):
        if crossover(self.sma_short, self.sma_long):
            self.buy()
        elif crossover(self.sma_long, self.sma_short):
            self.position.close()


class MomentumStrategy(Strategy):
    """
    モメンタム戦略
    過去N日間のリターンが正なら買い、負なら売り
    """
    momentum_period = 20
    threshold = 0.0

    def init(self):
        close = pd.Series(self.data.Close)
        self.momentum = self.I(lambda: close.pct_change(self.momentum_period) * 100)

    def next(self):
        if self.momentum[-1] > self.threshold:
            if not self.position:
                self.buy()
        elif self.momentum[-1] < -self.threshold:
            if self.position:
                self.position.close()


class MeanReversionStrategy(Strategy):
    """
    平均回帰戦略
    価格が移動平均から一定以上乖離したら逆張りエントリー
    """
    ma_period = 20
    entry_threshold = 2.0  # 標準偏差の倍数
    exit_threshold = 0.5

    def init(self):
        close = pd.Series(self.data.Close)
        sma = close.rolling(self.ma_period).mean()
        std = close.rolling(self.ma_period).std()
        self.zscore = self.I(lambda: (close - sma) / std)

    def next(self):
        if self.zscore[-1] < -self.entry_threshold:
            if not self.position:
                self.buy()
        elif self.zscore[-1] > self.entry_threshold:
            if self.position:
                self.position.close()
        elif abs(self.zscore[-1]) < self.exit_threshold:
            if self.position:
                self.position.close()


# 戦略マッピング
STRATEGY_MAP: Dict[str, Type[Strategy]] = {
    "sma_cross": SMACrossStrategy,
    "rsi": RSIStrategy,
    "macd": MACDStrategy,
    "bollinger": BollingerStrategy,
    "golden_cross": GoldenCrossStrategy,
    "momentum": MomentumStrategy,
    "mean_reversion": MeanReversionStrategy,
}


# 戦略情報
STRATEGY_INFO: List[StrategyInfo] = [
    StrategyInfo(
        id="sma_cross",
        name="SMAクロス戦略",
        description="短期移動平均が長期移動平均を上抜けたら買い、下抜けたら売り。トレンドフォロー型の基本戦略。",
        params=[
            {"name": "short_window", "type": "int", "default": 10, "min": 5, "max": 50, "description": "短期SMA期間"},
            {"name": "long_window", "type": "int", "default": 30, "min": 20, "max": 200, "description": "長期SMA期間"},
        ]
    ),
    StrategyInfo(
        id="rsi",
        name="RSI戦略",
        description="RSIが売られすぎ水準を下回ったら買い、買われすぎ水準を上回ったら売り。オシレーター系の逆張り戦略。",
        params=[
            {"name": "rsi_period", "type": "int", "default": 14, "min": 5, "max": 30, "description": "RSI計算期間"},
            {"name": "oversold", "type": "int", "default": 30, "min": 10, "max": 40, "description": "売られすぎ水準"},
            {"name": "overbought", "type": "int", "default": 70, "min": 60, "max": 90, "description": "買われすぎ水準"},
        ]
    ),
    StrategyInfo(
        id="macd",
        name="MACD戦略",
        description="MACDがシグナルラインを上抜けたら買い、下抜けたら売り。トレンドの転換点を捉える戦略。",
        params=[
            {"name": "fast_period", "type": "int", "default": 12, "min": 5, "max": 20, "description": "短期EMA期間"},
            {"name": "slow_period", "type": "int", "default": 26, "min": 20, "max": 40, "description": "長期EMA期間"},
            {"name": "signal_period", "type": "int", "default": 9, "min": 5, "max": 15, "description": "シグナル期間"},
        ]
    ),
    StrategyInfo(
        id="bollinger",
        name="ボリンジャーバンド戦略",
        description="価格がロワーバンドを下回ったら買い、アッパーバンドを上回ったら売り。ボラティリティを考慮した逆張り戦略。",
        params=[
            {"name": "bb_period", "type": "int", "default": 20, "min": 10, "max": 50, "description": "ボリンジャーバンド期間"},
            {"name": "bb_std", "type": "float", "default": 2.0, "min": 1.0, "max": 3.0, "description": "標準偏差の倍数"},
        ]
    ),
    StrategyInfo(
        id="golden_cross",
        name="ゴールデンクロス戦略",
        description="50日移動平均が200日移動平均を上抜けたら買い（ゴールデンクロス）、下抜けたら売り（デッドクロス）。長期トレンドフォロー戦略。",
        params=[
            {"name": "short_window", "type": "int", "default": 50, "min": 20, "max": 100, "description": "短期SMA期間"},
            {"name": "long_window", "type": "int", "default": 200, "min": 100, "max": 300, "description": "長期SMA期間"},
        ]
    ),
    StrategyInfo(
        id="momentum",
        name="モメンタム戦略",
        description="過去N日間のリターンが正なら買い、負なら売り。トレンドの継続性を利用した戦略。",
        params=[
            {"name": "momentum_period", "type": "int", "default": 20, "min": 5, "max": 60, "description": "モメンタム計算期間"},
            {"name": "threshold", "type": "float", "default": 0.0, "min": -5.0, "max": 5.0, "description": "エントリー閾値(%)"},
        ]
    ),
    StrategyInfo(
        id="mean_reversion",
        name="平均回帰戦略",
        description="価格が移動平均から一定以上乖離したら逆張りエントリー。短期的な価格の歪みを狙う戦略。",
        params=[
            {"name": "ma_period", "type": "int", "default": 20, "min": 10, "max": 50, "description": "移動平均期間"},
            {"name": "entry_threshold", "type": "float", "default": 2.0, "min": 1.0, "max": 3.0, "description": "エントリー閾値(σ)"},
            {"name": "exit_threshold", "type": "float", "default": 0.5, "min": 0.0, "max": 1.0, "description": "イグジット閾値(σ)"},
        ]
    ),
]


class BacktestService:
    """バックテストサービス"""

    def __init__(self):
        self._cache: Dict[str, pd.DataFrame] = {}

    def _fetch_data(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        株価データを取得

        Args:
            ticker: ティッカーシンボル（例: 7203.T）
            start_date: 開始日（YYYY-MM-DD）
            end_date: 終了日（YYYY-MM-DD）

        Returns:
            OHLCVデータのDataFrame
        """
        cache_key = f"{ticker}_{start_date}_{end_date}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            # yfinanceでデータ取得
            data = yf.download(
                ticker,
                start=start_date,
                end=end_date,
                progress=False
            )

            if data.empty:
                raise ValueError(f"No data found for {ticker}")

            # backtesting.pyが期待する形式に変換
            # カラム名を正規化（マルチインデックスの場合の対応）
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            data = data.rename(columns={
                'Open': 'Open',
                'High': 'High',
                'Low': 'Low',
                'Close': 'Close',
                'Volume': 'Volume'
            })

            # 必要なカラムのみ選択
            data = data[['Open', 'High', 'Low', 'Close', 'Volume']]

            # NaN値を除去
            data = data.dropna()

            self._cache[cache_key] = data
            return data

        except Exception as e:
            logger.error(f"Failed to fetch data for {ticker}: {e}")
            raise

    def run_backtest(self, config: BacktestConfig) -> BacktestResult:
        """
        バックテストを実行

        Args:
            config: バックテスト設定

        Returns:
            バックテスト結果
        """
        # データ取得
        data = self._fetch_data(config.ticker, config.start_date, config.end_date)

        if len(data) < 50:
            raise ValueError(f"Insufficient data points: {len(data)} (minimum 50 required)")

        # 戦略クラスを取得
        strategy_class = STRATEGY_MAP.get(config.strategy)
        if not strategy_class:
            raise ValueError(f"Unknown strategy: {config.strategy}")

        # パラメータを設定した戦略クラスを作成
        if config.params:
            # 動的にパラメータを設定
            strategy_class = type(
                f"{strategy_class.__name__}Custom",
                (strategy_class,),
                config.params
            )

        # バックテスト実行
        bt = Backtest(
            data,
            strategy_class,
            cash=config.initial_capital,
            commission=0.001,  # 手数料0.1%
            exclusive_orders=True
        )

        stats = bt.run()

        # 結果を整形
        return self._format_results(stats, data)

    def _format_results(self, stats, data: pd.DataFrame) -> BacktestResult:
        """バックテスト結果を整形"""

        # 資産推移（Equity Curve）
        equity_curve = []
        if hasattr(stats, '_equity_curve') and stats._equity_curve is not None:
            eq = stats._equity_curve
            for idx, row in eq.iterrows():
                equity_curve.append({
                    "date": idx.isoformat() if hasattr(idx, 'isoformat') else str(idx),
                    "equity": float(row.get('Equity', 0)),
                    "drawdown_pct": float(row.get('DrawdownPct', 0)) * 100 if 'DrawdownPct' in row else 0
                })

        # 取引履歴
        trades = []
        if hasattr(stats, '_trades') and stats._trades is not None and len(stats._trades) > 0:
            for _, trade in stats._trades.iterrows():
                entry_time = trade.get('EntryTime')
                exit_time = trade.get('ExitTime')
                trades.append(TradeRecord(
                    entry_date=entry_time.isoformat() if hasattr(entry_time, 'isoformat') else str(entry_time),
                    exit_date=exit_time.isoformat() if hasattr(exit_time, 'isoformat') else str(exit_time),
                    entry_price=float(trade.get('EntryPrice', 0)),
                    exit_price=float(trade.get('ExitPrice', 0)),
                    size=float(trade.get('Size', 0)),
                    pnl=float(trade.get('PnL', 0)),
                    pnl_percent=float(trade.get('ReturnPct', 0)),
                    is_long=float(trade.get('Size', 0)) > 0
                ))

        # ドローダウン推移
        drawdown_curve = []
        if equity_curve:
            for point in equity_curve:
                drawdown_curve.append({
                    "date": point["date"],
                    "drawdown": point.get("drawdown_pct", 0)
                })

        # 安全に統計値を取得
        def safe_get(key: str, default: float = 0.0) -> float:
            val = stats.get(key, default)
            if pd.isna(val):
                return default
            return float(val)

        return BacktestResult(
            total_return=safe_get('Return [%]'),
            annual_return=safe_get('Return (Ann.) [%]'),
            max_drawdown=safe_get('Max. Drawdown [%]'),
            sharpe_ratio=safe_get('Sharpe Ratio'),
            win_rate=safe_get('Win Rate [%]'),
            total_trades=int(safe_get('# Trades')),
            profit_factor=safe_get('Profit Factor', 1.0),
            avg_trade_return=safe_get('Avg. Trade [%]'),
            best_trade=safe_get('Best Trade [%]'),
            worst_trade=safe_get('Worst Trade [%]'),
            equity_curve=equity_curve,
            trades=trades,
            drawdown_curve=drawdown_curve
        )

    def get_available_strategies(self) -> List[StrategyInfo]:
        """利用可能な戦略一覧を取得"""
        return STRATEGY_INFO

    def optimize_parameters(
        self,
        config: BacktestConfig,
        param_ranges: Dict[str, List]
    ) -> OptimizationResult:
        """
        パラメータ最適化を実行

        Args:
            config: ベースとなるバックテスト設定
            param_ranges: パラメータ範囲（例: {"short_window": range(5, 20), "long_window": range(20, 50)}）

        Returns:
            最適化結果
        """
        # データ取得
        data = self._fetch_data(config.ticker, config.start_date, config.end_date)

        # 戦略クラスを取得
        strategy_class = STRATEGY_MAP.get(config.strategy)
        if not strategy_class:
            raise ValueError(f"Unknown strategy: {config.strategy}")

        # バックテストオブジェクト作成
        bt = Backtest(
            data,
            strategy_class,
            cash=config.initial_capital,
            commission=0.001,
            exclusive_orders=True
        )

        # 最適化実行
        try:
            stats, heatmap = bt.optimize(
                **param_ranges,
                maximize='Return [%]',
                return_heatmap=True,
                constraint=lambda p: True  # 制約なし
            )
        except Exception as e:
            logger.error(f"Optimization failed: {e}")
            # ヒートマップなしで再試行
            stats = bt.optimize(
                **param_ranges,
                maximize='Return [%]',
                constraint=lambda p: True
            )
            heatmap = None

        # 最適パラメータを抽出
        best_params = {}
        for key in param_ranges.keys():
            if hasattr(stats, '_strategy'):
                best_params[key] = getattr(stats._strategy, key, None)

        # 最適化履歴を整形
        optimization_history = []
        if heatmap is not None:
            try:
                for idx, val in heatmap.items():
                    if isinstance(idx, tuple):
                        params = dict(zip(param_ranges.keys(), idx))
                    else:
                        params = {list(param_ranges.keys())[0]: idx}
                    optimization_history.append({
                        "params": params,
                        "return": float(val) if not pd.isna(val) else 0
                    })
            except Exception as e:
                logger.warning(f"Failed to parse heatmap: {e}")

        return OptimizationResult(
            best_params=best_params,
            best_return=float(stats.get('Return [%]', 0)) if not pd.isna(stats.get('Return [%]', 0)) else 0,
            best_sharpe=float(stats.get('Sharpe Ratio', 0)) if not pd.isna(stats.get('Sharpe Ratio', 0)) else 0,
            optimization_history=optimization_history[:100]  # 最大100件
        )

    def generate_iris_summary(self, result: BacktestResult, config: BacktestConfig) -> str:
        """
        イリス向けのバックテスト結果解説を生成

        Args:
            result: バックテスト結果
            config: バックテスト設定

        Returns:
            イリスが読み上げる解説テキスト
        """
        # 戦略名を取得
        strategy_name = next(
            (s.name for s in STRATEGY_INFO if s.id == config.strategy),
            config.strategy
        )

        # 評価コメント生成
        if result.total_return > 50:
            performance_comment = "素晴らしい成績ですね！"
        elif result.total_return > 20:
            performance_comment = "なかなか良いパフォーマンスです。"
        elif result.total_return > 0:
            performance_comment = "プラスで終われましたね。"
        else:
            performance_comment = "残念ながらマイナスになってしまいました。"

        # リスクコメント
        if abs(result.max_drawdown) > 30:
            risk_comment = "ただし、最大ドローダウンが大きいので、リスク管理には注意が必要です。"
        elif abs(result.max_drawdown) > 15:
            risk_comment = "ドローダウンも許容範囲内かと思います。"
        else:
            risk_comment = "リスクも抑えられていて良いですね。"

        # シャープレシオコメント
        if result.sharpe_ratio > 1.5:
            sharpe_comment = "シャープレシオも高く、効率的な運用ができています。"
        elif result.sharpe_ratio > 1.0:
            sharpe_comment = "シャープレシオも1以上で合格点です。"
        elif result.sharpe_ratio > 0:
            sharpe_comment = ""
        else:
            sharpe_comment = "シャープレシオがマイナスなので、戦略の見直しが必要かもしれません。"

        summary = f"""
{config.ticker}の{strategy_name}によるバックテスト結果をお伝えします。

期間は{config.start_date}から{config.end_date}まで、初期資金{config.initial_capital:,.0f}円でのシミュレーションです。

結果は、総リターン{result.total_return:.1f}%、年率リターン{result.annual_return:.1f}%となりました。
{performance_comment}

最大ドローダウンは{abs(result.max_drawdown):.1f}%、勝率は{result.win_rate:.1f}%、総取引回数は{result.total_trades}回でした。
{risk_comment}
{sharpe_comment}

詳細な取引履歴やチャートはダッシュボードでご確認いただけます。
""".strip()

        return summary


# シングルトンインスタンス
backtest_service = BacktestService()
