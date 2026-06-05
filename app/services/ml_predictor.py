"""
機械学習予測サービス
ml-trading-japan, FinRL参考の株価方向性予測
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel
from datetime import datetime, timedelta
import logging
import pickle
import os
from pathlib import Path
import hashlib
import json

# ML Libraries
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    classification_report, confusion_matrix
)
from sklearn.preprocessing import StandardScaler
import warnings

# Market Data
import yfinance as yf

warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

# モデル保存ディレクトリ
MODEL_DIR = Path(os.getenv("ML_MODEL_DIR", "./ml_models"))
MODEL_DIR.mkdir(parents=True, exist_ok=True)


class PredictionResult(BaseModel):
    """予測結果"""
    ticker: str
    prediction: str  # "up", "down", "neutral"
    probability: float  # 0-1
    confidence: str  # "high", "medium", "low"
    features_importance: Dict[str, float]
    model_used: str
    prediction_horizon: str  # "1d" (翌日) or "1w" (翌週)
    timestamp: str
    disclaimer: str = "この予測はAIモデルによる参考値であり、投資判断の根拠とすべきではありません。"


class ModelEvaluation(BaseModel):
    """モデル評価結果"""
    ticker: str
    accuracy: float
    precision: Dict[str, float]
    recall: Dict[str, float]
    f1: Dict[str, float]
    confusion_matrix: List[List[int]]
    train_samples: int
    test_samples: int
    feature_count: int
    last_trained: str
    walk_forward_results: List[Dict[str, Any]]


class TrainedModelInfo(BaseModel):
    """訓練済みモデル情報"""
    ticker: str
    model_type: str
    trained_at: str
    train_period_start: str
    train_period_end: str
    feature_count: int
    accuracy: float
    status: str


class FeatureEngineering:
    """特徴量エンジニアリング（63種類以上の特徴量生成）"""

    @staticmethod
    def add_technical_features(df: pd.DataFrame) -> pd.DataFrame:
        """
        テクニカル指標の追加
        RSI, MACD, Bollinger Bands, ATR, ADX, Stochastic等
        """
        df = df.copy()

        # 基本価格データ
        close = df['Close']
        high = df['High']
        low = df['Low']
        volume = df['Volume']

        # === RSI (Relative Strength Index) ===
        for period in [7, 14, 21]:
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss.replace(0, np.nan)
            df[f'RSI_{period}'] = 100 - (100 / (1 + rs))

        # === MACD (Moving Average Convergence Divergence) ===
        ema_12 = close.ewm(span=12, adjust=False).mean()
        ema_26 = close.ewm(span=26, adjust=False).mean()
        df['MACD'] = ema_12 - ema_26
        df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_hist'] = df['MACD'] - df['MACD_signal']

        # === Bollinger Bands ===
        for period in [20]:
            sma = close.rolling(window=period).mean()
            std = close.rolling(window=period).std()
            df[f'BB_upper_{period}'] = sma + (2 * std)
            df[f'BB_lower_{period}'] = sma - (2 * std)
            df[f'BB_middle_{period}'] = sma
            df[f'BB_width_{period}'] = (df[f'BB_upper_{period}'] - df[f'BB_lower_{period}']) / sma
            df[f'BB_position_{period}'] = (close - df[f'BB_lower_{period}']) / (df[f'BB_upper_{period}'] - df[f'BB_lower_{period}'])

        # === ATR (Average True Range) ===
        for period in [14, 21]:
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            df[f'ATR_{period}'] = tr.rolling(window=period).mean()
            df[f'ATR_ratio_{period}'] = df[f'ATR_{period}'] / close

        # === ADX (Average Directional Index) ===
        period = 14
        tr = pd.concat([
            high - low,
            abs(high - close.shift(1)),
            abs(low - close.shift(1))
        ], axis=1).max(axis=1)

        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

        atr = tr.rolling(window=period).mean()
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)
        df['ADX'] = dx.rolling(window=period).mean()
        df['Plus_DI'] = plus_di
        df['Minus_DI'] = minus_di

        # === Stochastic Oscillator ===
        for period in [14]:
            lowest_low = low.rolling(window=period).min()
            highest_high = high.rolling(window=period).max()
            df[f'Stoch_K_{period}'] = 100 * (close - lowest_low) / (highest_high - lowest_low)
            df[f'Stoch_D_{period}'] = df[f'Stoch_K_{period}'].rolling(window=3).mean()

        # === CCI (Commodity Channel Index) ===
        for period in [20]:
            tp = (high + low + close) / 3
            sma_tp = tp.rolling(window=period).mean()
            mad = tp.rolling(window=period).apply(lambda x: np.abs(x - x.mean()).mean())
            df[f'CCI_{period}'] = (tp - sma_tp) / (0.015 * mad)

        # === Williams %R ===
        for period in [14]:
            highest_high = high.rolling(window=period).max()
            lowest_low = low.rolling(window=period).min()
            df[f'Williams_R_{period}'] = -100 * (highest_high - close) / (highest_high - lowest_low)

        # === MFI (Money Flow Index) ===
        period = 14
        tp = (high + low + close) / 3
        mf = tp * volume

        pos_mf = mf.where(tp > tp.shift(1), 0).rolling(window=period).sum()
        neg_mf = mf.where(tp < tp.shift(1), 0).rolling(window=period).sum()

        mfr = pos_mf / neg_mf.replace(0, np.nan)
        df['MFI'] = 100 - (100 / (1 + mfr))

        # === OBV (On Balance Volume) ===
        obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
        df['OBV'] = obv
        df['OBV_SMA_20'] = obv.rolling(window=20).mean()
        df['OBV_ratio'] = obv / df['OBV_SMA_20']

        # === VWAP (Volume Weighted Average Price) ===
        df['VWAP'] = (volume * (high + low + close) / 3).cumsum() / volume.cumsum()
        df['VWAP_ratio'] = close / df['VWAP']

        return df

    @staticmethod
    def add_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
        """移動平均線と乖離率"""
        df = df.copy()
        close = df['Close']

        # SMA (Simple Moving Average)
        for period in [5, 10, 20, 50, 100, 200]:
            df[f'SMA_{period}'] = close.rolling(window=period).mean()
            df[f'SMA_{period}_ratio'] = close / df[f'SMA_{period}']
            df[f'SMA_{period}_slope'] = df[f'SMA_{period}'].diff(5) / df[f'SMA_{period}'].shift(5)

        # EMA (Exponential Moving Average)
        for period in [5, 10, 20, 50]:
            df[f'EMA_{period}'] = close.ewm(span=period, adjust=False).mean()
            df[f'EMA_{period}_ratio'] = close / df[f'EMA_{period}']

        # ゴールデンクロス・デッドクロス
        df['Golden_Cross'] = (df['SMA_50'] > df['SMA_200']).astype(int)
        df['SMA_5_20_cross'] = (df['SMA_5'] > df['SMA_20']).astype(int)

        return df

    @staticmethod
    def add_lag_features(df: pd.DataFrame, lags: List[int] = None) -> pd.DataFrame:
        """ラグ特徴量（過去データの参照）"""
        df = df.copy()

        if lags is None:
            lags = [1, 2, 3, 5, 10, 20]

        close = df['Close']
        volume = df['Volume']

        for lag in lags:
            # 価格変化率
            df[f'Return_lag_{lag}'] = close.pct_change(lag)

            # 出来高変化率
            df[f'Volume_change_lag_{lag}'] = volume.pct_change(lag)

            # 高値・安値比率
            df[f'HL_ratio_lag_{lag}'] = (df['High'] / df['Low']).shift(lag)

        return df

    @staticmethod
    def add_rolling_features(df: pd.DataFrame, windows: List[int] = None) -> pd.DataFrame:
        """ローリング統計量"""
        df = df.copy()

        if windows is None:
            windows = [5, 10, 20, 60]

        close = df['Close']
        returns = close.pct_change()
        volume = df['Volume']

        for window in windows:
            # リターンの統計量
            df[f'Return_mean_{window}'] = returns.rolling(window=window).mean()
            df[f'Return_std_{window}'] = returns.rolling(window=window).std()
            df[f'Return_skew_{window}'] = returns.rolling(window=window).skew()
            df[f'Return_kurt_{window}'] = returns.rolling(window=window).kurt()

            # 価格レンジ
            df[f'Price_range_{window}'] = (
                df['High'].rolling(window=window).max() -
                df['Low'].rolling(window=window).min()
            ) / close

            # 出来高統計
            df[f'Volume_mean_{window}'] = volume.rolling(window=window).mean()
            df[f'Volume_std_{window}'] = volume.rolling(window=window).std()
            df[f'Volume_ratio_{window}'] = volume / df[f'Volume_mean_{window}']

            # 最高値・最安値からの位置
            df[f'High_position_{window}'] = (
                close - df['Low'].rolling(window=window).min()
            ) / (
                df['High'].rolling(window=window).max() -
                df['Low'].rolling(window=window).min()
            )

        return df

    @staticmethod
    def add_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
        """カレンダー特徴量"""
        df = df.copy()

        if isinstance(df.index, pd.DatetimeIndex):
            dates = df.index
        else:
            dates = pd.to_datetime(df.index)

        # 曜日（月曜効果、週末効果）
        df['DayOfWeek'] = dates.dayofweek
        df['IsMonday'] = (dates.dayofweek == 0).astype(int)
        df['IsFriday'] = (dates.dayofweek == 4).astype(int)

        # 月（決算期等）
        df['Month'] = dates.month
        df['IsQuarterEnd'] = dates.is_quarter_end.astype(int)

        # 月初・月末効果
        df['DayOfMonth'] = dates.day
        df['IsMonthStart'] = (dates.day <= 5).astype(int)
        df['IsMonthEnd'] = (dates.day >= 25).astype(int)

        return df

    @staticmethod
    def add_target(df: pd.DataFrame, horizon: int = 1, threshold: float = 0.0) -> pd.DataFrame:
        """
        ターゲット変数の追加（先読みバイアスを避けるため注意が必要）

        Args:
            df: データフレーム
            horizon: 予測期間（1=翌日、5=翌週）
            threshold: ニュートラルの閾値（0なら2クラス、0.005なら3クラス等）

        Returns:
            ターゲット変数付きデータフレーム
        """
        df = df.copy()

        # 将来リターン（horizon日後のリターン）
        future_return = df['Close'].shift(-horizon) / df['Close'] - 1

        if threshold == 0:
            # 2クラス分類（上昇=1、下降=0）
            df['Target'] = (future_return > 0).astype(int)
        else:
            # 3クラス分類（上昇=2、ニュートラル=1、下降=0）
            df['Target'] = 1  # ニュートラル
            df.loc[future_return > threshold, 'Target'] = 2  # 上昇
            df.loc[future_return < -threshold, 'Target'] = 0  # 下降

        return df


class MLPredictorService:
    """機械学習予測サービス"""

    def __init__(self):
        self.models: Dict[str, Dict[str, Any]] = {}  # キャッシュされたモデル
        self.scalers: Dict[str, StandardScaler] = {}
        self.feature_columns: Dict[str, List[str]] = {}
        self.feature_engineering = FeatureEngineering()

    async def _fetch_historical_data(
        self,
        ticker: str,
        days: int = 756
    ) -> Optional[pd.DataFrame]:
        """
        過去データの取得

        Args:
            ticker: ティッカーシンボル（日本株は7203.Tのような形式）
            days: 取得日数（デフォルト756日=約3年）

        Returns:
            OHLCVデータのDataFrame
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            yf_ticker = yf.Ticker(ticker)
            df = yf_ticker.history(start=start_date, end=end_date)

            if df.empty:
                logger.warning(f"No data found for {ticker}")
                return None

            # インデックスをDatetimeIndexに統一
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)

            # タイムゾーンを除去（計算の都合上）
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)

            return df

        except Exception as e:
            logger.error(f"Failed to fetch data for {ticker}: {e}")
            return None

    async def generate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        63種類以上の特徴量生成（ml-trading-japan参考）

        Args:
            df: OHLCVデータ

        Returns:
            特徴量付きDataFrame
        """
        # 各種特徴量の追加
        df = self.feature_engineering.add_technical_features(df)
        df = self.feature_engineering.add_moving_averages(df)
        df = self.feature_engineering.add_lag_features(df)
        df = self.feature_engineering.add_rolling_features(df)
        df = self.feature_engineering.add_calendar_features(df)

        return df

    def _get_feature_columns(self, df: pd.DataFrame) -> List[str]:
        """特徴量カラムの取得（非特徴量を除外）"""
        exclude_cols = [
            'Open', 'High', 'Low', 'Close', 'Volume',
            'Dividends', 'Stock Splits', 'Target'
        ]
        return [col for col in df.columns if col not in exclude_cols]

    async def train_model(
        self,
        ticker: str,
        days: int = 756,
        horizon: int = 1,
        n_splits: int = 5
    ) -> Dict[str, Any]:
        """
        ウォークフォワード法でモデル訓練

        先読みバイアスを避けるため、以下を厳守：
        1. TimeSeriesSplitで時系列順に分割
        2. 各フォールドで訓練データのみでスケーリング
        3. テストデータは訓練データより後の期間のみ

        Args:
            ticker: ティッカーシンボル
            days: 訓練データ期間
            horizon: 予測期間（1=翌日、5=翌週）
            n_splits: クロスバリデーション分割数

        Returns:
            訓練結果
        """
        logger.info(f"Training model for {ticker} with {days} days of data")

        # データ取得
        df = await self._fetch_historical_data(ticker, days)
        if df is None:
            raise ValueError(f"Could not fetch data for {ticker}")

        # 特徴量生成
        df = await self.generate_features(df)

        # ターゲット追加
        df = self.feature_engineering.add_target(df, horizon=horizon, threshold=0)

        # NaNを含む行を削除
        df = df.dropna()

        if len(df) < 100:
            raise ValueError(f"Not enough data for {ticker}: {len(df)} samples")

        # 特徴量とターゲットを分離
        feature_cols = self._get_feature_columns(df)
        X = df[feature_cols].values
        y = df['Target'].values

        # ウォークフォワード法（TimeSeriesSplit）
        tscv = TimeSeriesSplit(n_splits=n_splits)

        # モデル定義
        xgb_model = XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            use_label_encoder=False,
            eval_metric='logloss'
        )

        lgb_model = LGBMClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbose=-1
        )

        # ウォークフォワード結果
        walk_forward_results = []
        all_predictions = []
        all_actuals = []

        for fold, (train_idx, test_idx) in enumerate(tscv.split(X)):
            X_train, X_test = X[train_idx], X[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]

            # スケーリング（訓練データのみでfit）
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            # XGBoost訓練
            xgb_model.fit(X_train_scaled, y_train)
            xgb_pred = xgb_model.predict(X_test_scaled)
            xgb_prob = xgb_model.predict_proba(X_test_scaled)

            # LightGBM訓練
            lgb_model.fit(X_train_scaled, y_train)
            lgb_pred = lgb_model.predict(X_test_scaled)
            lgb_prob = lgb_model.predict_proba(X_test_scaled)

            # アンサンブル（平均確率）
            ensemble_prob = (xgb_prob + lgb_prob) / 2
            ensemble_pred = (ensemble_prob[:, 1] > 0.5).astype(int)

            # 評価
            fold_accuracy = accuracy_score(y_test, ensemble_pred)
            fold_f1 = f1_score(y_test, ensemble_pred, average='weighted')

            walk_forward_results.append({
                'fold': fold + 1,
                'train_samples': len(train_idx),
                'test_samples': len(test_idx),
                'accuracy': float(fold_accuracy),
                'f1_score': float(fold_f1),
                'xgb_accuracy': float(accuracy_score(y_test, xgb_pred)),
                'lgb_accuracy': float(accuracy_score(y_test, lgb_pred))
            })

            all_predictions.extend(ensemble_pred.tolist())
            all_actuals.extend(y_test.tolist())

        # 最終モデルの訓練（全データ使用）
        final_scaler = StandardScaler()
        X_scaled = final_scaler.fit_transform(X)

        xgb_model.fit(X_scaled, y)
        lgb_model.fit(X_scaled, y)

        # 特徴量重要度（XGBoostとLightGBMの平均）
        xgb_importance = dict(zip(feature_cols, xgb_model.feature_importances_))
        lgb_importance = dict(zip(feature_cols, lgb_model.feature_importances_))

        combined_importance = {}
        for col in feature_cols:
            combined_importance[col] = (xgb_importance[col] + lgb_importance[col]) / 2

        # 重要度でソート（上位20）
        sorted_importance = dict(
            sorted(combined_importance.items(), key=lambda x: x[1], reverse=True)[:20]
        )

        # モデル保存
        model_data = {
            'xgb_model': xgb_model,
            'lgb_model': lgb_model,
            'scaler': final_scaler,
            'feature_columns': feature_cols,
            'feature_importance': sorted_importance,
            'trained_at': datetime.now().isoformat(),
            'train_period_start': df.index[0].isoformat(),
            'train_period_end': df.index[-1].isoformat(),
            'horizon': horizon,
            'accuracy': float(accuracy_score(all_actuals, all_predictions)),
            'f1_score': float(f1_score(all_actuals, all_predictions, average='weighted')),
            'walk_forward_results': walk_forward_results
        }

        # メモリキャッシュ
        self.models[ticker] = model_data
        self.scalers[ticker] = final_scaler
        self.feature_columns[ticker] = feature_cols

        # ファイルに保存
        model_path = MODEL_DIR / f"{ticker.replace('.', '_')}_model.pkl"
        with open(model_path, 'wb') as f:
            pickle.dump(model_data, f)

        logger.info(f"Model trained for {ticker}. Accuracy: {model_data['accuracy']:.4f}")

        return {
            'ticker': ticker,
            'accuracy': model_data['accuracy'],
            'f1_score': model_data['f1_score'],
            'feature_count': len(feature_cols),
            'train_samples': len(df),
            'walk_forward_results': walk_forward_results,
            'top_features': sorted_importance,
            'trained_at': model_data['trained_at']
        }

    async def _load_model(self, ticker: str) -> Optional[Dict[str, Any]]:
        """モデルの読み込み"""
        # メモリキャッシュを確認
        if ticker in self.models:
            return self.models[ticker]

        # ファイルから読み込み
        model_path = MODEL_DIR / f"{ticker.replace('.', '_')}_model.pkl"
        if model_path.exists():
            try:
                with open(model_path, 'rb') as f:
                    model_data = pickle.load(f)

                self.models[ticker] = model_data
                self.scalers[ticker] = model_data['scaler']
                self.feature_columns[ticker] = model_data['feature_columns']

                return model_data
            except Exception as e:
                logger.error(f"Failed to load model for {ticker}: {e}")
                return None

        return None

    async def predict(
        self,
        ticker: str,
        horizon: str = "1d"
    ) -> PredictionResult:
        """
        翌日/翌週の方向性予測

        Args:
            ticker: ティッカーシンボル
            horizon: "1d" (翌日) or "1w" (翌週)

        Returns:
            予測結果
        """
        # モデル読み込み
        model_data = await self._load_model(ticker)

        if model_data is None:
            # モデルがない場合は訓練
            logger.info(f"No model found for {ticker}, training new model...")
            await self.train_model(ticker)
            model_data = await self._load_model(ticker)

        if model_data is None:
            raise ValueError(f"Could not load or train model for {ticker}")

        # 最新データ取得
        df = await self._fetch_historical_data(ticker, days=100)
        if df is None:
            raise ValueError(f"Could not fetch recent data for {ticker}")

        # 特徴量生成
        df = await self.generate_features(df)
        df = df.dropna()

        if len(df) == 0:
            raise ValueError(f"No valid data after feature generation for {ticker}")

        # 最新の特徴量
        feature_cols = model_data['feature_columns']

        # 欠損カラムのチェック
        missing_cols = [col for col in feature_cols if col not in df.columns]
        if missing_cols:
            logger.warning(f"Missing columns: {missing_cols}")
            for col in missing_cols:
                df[col] = 0

        X_latest = df[feature_cols].iloc[-1:].values

        # スケーリング
        scaler = model_data['scaler']
        X_scaled = scaler.transform(X_latest)

        # 予測
        xgb_model = model_data['xgb_model']
        lgb_model = model_data['lgb_model']

        xgb_prob = xgb_model.predict_proba(X_scaled)[0]
        lgb_prob = lgb_model.predict_proba(X_scaled)[0]

        # アンサンブル
        ensemble_prob = (xgb_prob + lgb_prob) / 2

        # 予測結果
        up_probability = ensemble_prob[1]

        if up_probability > 0.6:
            prediction = "up"
            confidence = "high" if up_probability > 0.7 else "medium"
        elif up_probability < 0.4:
            prediction = "down"
            confidence = "high" if up_probability < 0.3 else "medium"
        else:
            prediction = "neutral"
            confidence = "low"

        # 特徴量重要度（上位10）
        feature_importance = dict(
            sorted(
                model_data['feature_importance'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
        )

        # 正規化
        total_importance = sum(feature_importance.values())
        if total_importance > 0:
            feature_importance = {
                k: round(v / total_importance, 4)
                for k, v in feature_importance.items()
            }

        return PredictionResult(
            ticker=ticker,
            prediction=prediction,
            probability=round(float(up_probability), 4),
            confidence=confidence,
            features_importance=feature_importance,
            model_used="XGBoost + LightGBM Ensemble",
            prediction_horizon=horizon,
            timestamp=datetime.now().isoformat()
        )

    async def get_feature_importance(self, ticker: str) -> Dict[str, float]:
        """特徴量重要度の取得"""
        model_data = await self._load_model(ticker)

        if model_data is None:
            raise ValueError(f"No model found for {ticker}")

        return model_data['feature_importance']

    async def evaluate_model(self, ticker: str) -> ModelEvaluation:
        """モデル評価指標の取得"""
        model_data = await self._load_model(ticker)

        if model_data is None:
            raise ValueError(f"No model found for {ticker}")

        # 最新データで再評価
        df = await self._fetch_historical_data(ticker, days=200)
        if df is None:
            raise ValueError(f"Could not fetch data for {ticker}")

        df = await self.generate_features(df)
        df = self.feature_engineering.add_target(
            df,
            horizon=model_data.get('horizon', 1),
            threshold=0
        )
        df = df.dropna()

        feature_cols = model_data['feature_columns']
        missing_cols = [col for col in feature_cols if col not in df.columns]
        for col in missing_cols:
            df[col] = 0

        X = df[feature_cols].values
        y = df['Target'].values

        # スケーリング
        scaler = model_data['scaler']
        X_scaled = scaler.transform(X)

        # 予測
        xgb_model = model_data['xgb_model']
        lgb_model = model_data['lgb_model']

        xgb_prob = xgb_model.predict_proba(X_scaled)
        lgb_prob = lgb_model.predict_proba(X_scaled)

        ensemble_prob = (xgb_prob + lgb_prob) / 2
        predictions = (ensemble_prob[:, 1] > 0.5).astype(int)

        # 評価指標
        accuracy = accuracy_score(y, predictions)
        precision = precision_score(y, predictions, average=None, zero_division=0)
        recall = recall_score(y, predictions, average=None, zero_division=0)
        f1 = f1_score(y, predictions, average=None, zero_division=0)
        cm = confusion_matrix(y, predictions)

        return ModelEvaluation(
            ticker=ticker,
            accuracy=float(accuracy),
            precision={'down': float(precision[0]), 'up': float(precision[1]) if len(precision) > 1 else 0.0},
            recall={'down': float(recall[0]), 'up': float(recall[1]) if len(recall) > 1 else 0.0},
            f1={'down': float(f1[0]), 'up': float(f1[1]) if len(f1) > 1 else 0.0},
            confusion_matrix=cm.tolist(),
            train_samples=model_data.get('train_samples', len(df)),
            test_samples=len(df),
            feature_count=len(feature_cols),
            last_trained=model_data['trained_at'],
            walk_forward_results=model_data.get('walk_forward_results', [])
        )

    async def list_models(self) -> List[TrainedModelInfo]:
        """利用可能なモデル一覧"""
        models = []

        for model_file in MODEL_DIR.glob("*_model.pkl"):
            try:
                with open(model_file, 'rb') as f:
                    model_data = pickle.load(f)

                ticker = model_file.stem.replace('_model', '').replace('_', '.')

                models.append(TrainedModelInfo(
                    ticker=ticker,
                    model_type="XGBoost + LightGBM Ensemble",
                    trained_at=model_data.get('trained_at', 'unknown'),
                    train_period_start=model_data.get('train_period_start', 'unknown'),
                    train_period_end=model_data.get('train_period_end', 'unknown'),
                    feature_count=len(model_data.get('feature_columns', [])),
                    accuracy=model_data.get('accuracy', 0.0),
                    status='active'
                ))
            except Exception as e:
                logger.error(f"Failed to load model info from {model_file}: {e}")

        return models

    def generate_iris_prediction_comment(self, result: PredictionResult) -> str:
        """
        イリス（AI VTuber）向けの予測コメント生成

        Args:
            result: 予測結果

        Returns:
            自然言語のコメント
        """
        ticker = result.ticker
        prediction = result.prediction
        probability = result.probability * 100
        confidence = result.confidence

        # 確率に基づくコメント
        if prediction == "up":
            if confidence == "high":
                comment = f"AIモデルによると、{ticker}は来週上昇する確率が{probability:.1f}%と予測されています。かなり強気のシグナルですね！"
            else:
                comment = f"{ticker}は上昇傾向にあるようです。AIの予測では{probability:.1f}%の確率で上がると見ています。"
        elif prediction == "down":
            if confidence == "high":
                comment = f"要注意です！{ticker}はAIモデルによると{100-probability:.1f}%の確率で下落すると予測されています。"
            else:
                comment = f"{ticker}は少し弱気なシグナルが出ています。下落確率は{100-probability:.1f}%程度です。"
        else:
            comment = f"{ticker}はちょっと方向感がつかみにくい状況ですね。AIモデルでも明確な傾向は見られません。"

        # 重要特徴量の説明
        top_features = list(result.features_importance.keys())[:3]
        feature_names_jp = {
            'RSI_14': 'RSI指標',
            'MACD': 'MACD',
            'SMA_20_ratio': '20日移動平均乖離率',
            'BB_position_20': 'ボリンジャーバンド位置',
            'Volume_ratio_20': '出来高比率',
            'ATR_14': 'ATR（変動率）',
            'Return_std_20': 'ボラティリティ'
        }

        feature_jp = [feature_names_jp.get(f, f) for f in top_features]
        comment += f" 今回の予測で特に重視されたのは{', '.join(feature_jp)}です。"

        # 免責事項
        comment += " ただし、これはあくまでAIによる参考値なので、投資判断は自己責任でお願いしますね！"

        return comment


# シングルトンインスタンス
ml_predictor_service = MLPredictorService()
