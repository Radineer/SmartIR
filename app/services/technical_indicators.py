"""
テクニカル指標計算サービス
taライブラリを使用して63種類以上のテクニカル指標を計算
ml-trading-japan参考
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from datetime import datetime
import logging

# ta library imports
from ta.trend import (
    SMAIndicator, EMAIndicator, MACD, ADXIndicator,
    AroonIndicator, IchimokuIndicator, PSARIndicator,
    WMAIndicator, KSTIndicator, DPOIndicator, TRIXIndicator
)
from ta.momentum import (
    RSIIndicator, StochasticOscillator, WilliamsRIndicator,
    ROCIndicator, UltimateOscillator, TSIIndicator,
    StochRSIIndicator
)
from ta.volatility import (
    BollingerBands, AverageTrueRange, KeltnerChannel,
    DonchianChannel, UlcerIndex
)
from ta.volume import (
    OnBalanceVolumeIndicator, VolumeWeightedAveragePrice,
    AccDistIndexIndicator, ChaikinMoneyFlowIndicator,
    MFIIndicator, ForceIndexIndicator, EaseOfMovementIndicator,
    NegativeVolumeIndexIndicator, VolumePriceTrendIndicator
)

logger = logging.getLogger(__name__)


class IndicatorResult(BaseModel):
    """テクニカル指標の計算結果"""
    name: str
    value: float
    signal: str  # "buy", "sell", "neutral"
    description: str
    additional_data: Optional[Dict[str, Any]] = None


class IndicatorSummary(BaseModel):
    """指標サマリー"""
    ticker: str
    timestamp: str
    total_indicators: int
    buy_signals: int
    sell_signals: int
    neutral_signals: int
    overall_signal: str
    indicators: Dict[str, IndicatorResult]
    summary_text: str


class TechnicalIndicatorService:
    """テクニカル指標計算サービス"""

    def __init__(self):
        pass

    def _safe_float(self, value: Any) -> float:
        """安全にfloatに変換"""
        if value is None or pd.isna(value):
            return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _get_latest_value(self, series: pd.Series) -> float:
        """シリーズから最新の有効な値を取得"""
        if series is None or series.empty:
            return 0.0
        # 最新の非NaN値を取得
        valid_values = series.dropna()
        if valid_values.empty:
            return 0.0
        return self._safe_float(valid_values.iloc[-1])

    def calculate_all_indicators(self, df: pd.DataFrame) -> Dict[str, IndicatorResult]:
        """
        63種類のテクニカル指標を計算（ml-trading-japan参考）

        Args:
            df: OHLCVデータを含むDataFrame
                必要なカラム: Open, High, Low, Close, Volume

        Returns:
            指標名をキーとしたIndicatorResultの辞書
        """
        if df is None or df.empty:
            logger.warning("Empty DataFrame provided")
            return {}

        # カラム名を小文字に正規化
        df = df.copy()
        df.columns = df.columns.str.lower()

        indicators = {}

        try:
            # === トレンド系指標 ===
            # 1-5. SMA (単純移動平均)
            for period in [5, 10, 20, 50, 200]:
                result = self.calculate_sma_single(df, period)
                if result:
                    indicators[f"sma_{period}"] = result

            # 6-10. EMA (指数移動平均)
            for period in [5, 10, 20, 50, 200]:
                result = self.calculate_ema_single(df, period)
                if result:
                    indicators[f"ema_{period}"] = result

            # 11. MACD
            macd_result = self.calculate_macd(df)
            if macd_result:
                indicators["macd"] = macd_result

            # 12. ADX (Average Directional Index)
            adx_result = self.calculate_adx(df)
            if adx_result:
                indicators["adx"] = adx_result

            # 13. Parabolic SAR
            psar_result = self.calculate_parabolic_sar(df)
            if psar_result:
                indicators["psar"] = psar_result

            # 14-16. 一目均衡表
            ichimoku_result = self.calculate_ichimoku(df)
            if ichimoku_result:
                indicators["ichimoku"] = ichimoku_result

            # 17. Aroon
            aroon_result = self.calculate_aroon(df)
            if aroon_result:
                indicators["aroon"] = aroon_result

            # === オシレーター系指標 ===
            # 18. RSI
            rsi_result = self.calculate_rsi(df)
            if rsi_result:
                indicators["rsi"] = rsi_result

            # 19. Stochastic Oscillator
            stoch_result = self.calculate_stochastic(df)
            if stoch_result:
                indicators["stochastic"] = stoch_result

            # 20. Williams %R
            willr_result = self.calculate_williams_r(df)
            if willr_result:
                indicators["williams_r"] = willr_result

            # 21. CCI (Commodity Channel Index) - calculated manually
            cci_result = self.calculate_cci(df)
            if cci_result:
                indicators["cci"] = cci_result

            # 22. ROC (Rate of Change)
            roc_result = self.calculate_roc(df)
            if roc_result:
                indicators["roc"] = roc_result

            # 23. Momentum - calculated manually
            mom_result = self.calculate_momentum(df)
            if mom_result:
                indicators["momentum"] = mom_result

            # 24. Ultimate Oscillator
            uo_result = self.calculate_ultimate_oscillator(df)
            if uo_result:
                indicators["ultimate_oscillator"] = uo_result

            # 25. TSI (True Strength Index)
            tsi_result = self.calculate_tsi(df)
            if tsi_result:
                indicators["tsi"] = tsi_result

            # === ボラティリティ系指標 ===
            # 26. Bollinger Bands
            bb_result = self.calculate_bollinger_bands(df)
            if bb_result:
                indicators["bollinger_bands"] = bb_result

            # 27. ATR (Average True Range)
            atr_result = self.calculate_atr(df)
            if atr_result:
                indicators["atr"] = atr_result

            # 28. Keltner Channel
            kc_result = self.calculate_keltner_channel(df)
            if kc_result:
                indicators["keltner_channel"] = kc_result

            # 29. Donchian Channel
            dc_result = self.calculate_donchian_channel(df)
            if dc_result:
                indicators["donchian_channel"] = dc_result

            # 30. Standard Deviation
            std_result = self.calculate_std(df)
            if std_result:
                indicators["std"] = std_result

            # === 出来高系指標 ===
            # 31. OBV (On Balance Volume)
            obv_result = self.calculate_obv(df)
            if obv_result:
                indicators["obv"] = obv_result

            # 32. VWAP (Volume Weighted Average Price)
            vwap_result = self.calculate_vwap(df)
            if vwap_result:
                indicators["vwap"] = vwap_result

            # 33. AD (Accumulation/Distribution)
            ad_result = self.calculate_ad(df)
            if ad_result:
                indicators["ad"] = ad_result

            # 34. CMF (Chaikin Money Flow)
            cmf_result = self.calculate_cmf(df)
            if cmf_result:
                indicators["cmf"] = cmf_result

            # 35. MFI (Money Flow Index)
            mfi_result = self.calculate_mfi(df)
            if mfi_result:
                indicators["mfi"] = mfi_result

            # 36. Force Index
            fi_result = self.calculate_force_index(df)
            if fi_result:
                indicators["force_index"] = fi_result

            # 37. EOM (Ease of Movement)
            eom_result = self.calculate_eom(df)
            if eom_result:
                indicators["eom"] = eom_result

            # 38. Volume SMA
            vol_sma_result = self.calculate_volume_sma(df)
            if vol_sma_result:
                indicators["volume_sma"] = vol_sma_result

            # === 追加のトレンド系指標 ===
            # 39-43. WMA (加重移動平均)
            for period in [10, 20, 50]:
                wma_result = self.calculate_wma(df, period)
                if wma_result:
                    indicators[f"wma_{period}"] = wma_result

            # 44. DEMA (Double EMA) - calculated manually
            dema_result = self.calculate_dema(df)
            if dema_result:
                indicators["dema"] = dema_result

            # 45. TEMA (Triple EMA) - calculated manually
            tema_result = self.calculate_tema(df)
            if tema_result:
                indicators["tema"] = tema_result

            # 46. KST
            kst_result = self.calculate_kst(df)
            if kst_result:
                indicators["kst"] = kst_result

            # === 追加のオシレーター系 ===
            # 47. Stochastic RSI
            stoch_rsi_result = self.calculate_stochastic_rsi(df)
            if stoch_rsi_result:
                indicators["stochastic_rsi"] = stoch_rsi_result

            # 48. PPO (Percentage Price Oscillator)
            ppo_result = self.calculate_ppo(df)
            if ppo_result:
                indicators["ppo"] = ppo_result

            # 49. DPO (Detrended Price Oscillator)
            dpo_result = self.calculate_dpo(df)
            if dpo_result:
                indicators["dpo"] = dpo_result

            # 50. TRIX
            trix_result = self.calculate_trix(df)
            if trix_result:
                indicators["trix"] = trix_result

            # === 追加のボラティリティ系 ===
            # 51. Ulcer Index
            ui_result = self.calculate_ulcer_index(df)
            if ui_result:
                indicators["ulcer_index"] = ui_result

            # 52. Normalized ATR
            natr_result = self.calculate_natr(df)
            if natr_result:
                indicators["natr"] = natr_result

            # 53. True Range
            tr_result = self.calculate_true_range(df)
            if tr_result:
                indicators["true_range"] = tr_result

            # === 追加の出来高系 ===
            # 54. NVI (Negative Volume Index)
            nvi_result = self.calculate_nvi(df)
            if nvi_result:
                indicators["nvi"] = nvi_result

            # === パターン認識系 ===
            # 55. Price vs SMA20
            price_vs_sma_result = self.calculate_price_vs_sma(df)
            if price_vs_sma_result:
                indicators["price_vs_sma20"] = price_vs_sma_result

            # 56. Golden/Death Cross
            cross_result = self.calculate_ma_cross(df)
            if cross_result:
                indicators["ma_cross"] = cross_result

            # 57. Support/Resistance
            sr_result = self.calculate_support_resistance(df)
            if sr_result:
                indicators["support_resistance"] = sr_result

            # 58. Pivot Points
            pivot_result = self.calculate_pivot_points(df)
            if pivot_result:
                indicators["pivot_points"] = pivot_result

            # 59. Average Price
            avg_price_result = self.calculate_average_price(df)
            if avg_price_result:
                indicators["average_price"] = avg_price_result

        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")

        return indicators

    # === トレンド系指標の実装 ===

    def calculate_sma_single(self, df: pd.DataFrame, period: int) -> Optional[IndicatorResult]:
        """SMA (単純移動平均) を計算"""
        try:
            indicator = SMAIndicator(close=df['close'], window=period)
            sma = indicator.sma_indicator()
            if sma is None or sma.empty:
                return None

            sma_value = self._get_latest_value(sma)
            current_price = self._get_latest_value(df['close'])

            if sma_value == 0:
                return None

            # シグナル判定
            if current_price > sma_value * 1.02:
                signal = "buy"
                desc = f"価格がSMA{period}を上回っています（上昇トレンド）"
            elif current_price < sma_value * 0.98:
                signal = "sell"
                desc = f"価格がSMA{period}を下回っています（下降トレンド）"
            else:
                signal = "neutral"
                desc = f"価格がSMA{period}付近で推移しています"

            return IndicatorResult(
                name=f"SMA{period}",
                value=round(sma_value, 2),
                signal=signal,
                description=desc,
                additional_data={"current_price": round(current_price, 2)}
            )
        except Exception as e:
            logger.error(f"Error calculating SMA{period}: {e}")
            return None

    def calculate_sma(self, df: pd.DataFrame, periods: List[int] = [5, 10, 20, 50, 200]) -> List[IndicatorResult]:
        """複数期間のSMAを計算"""
        results = []
        for period in periods:
            result = self.calculate_sma_single(df, period)
            if result:
                results.append(result)
        return results

    def calculate_ema_single(self, df: pd.DataFrame, period: int) -> Optional[IndicatorResult]:
        """EMA (指数移動平均) を計算"""
        try:
            indicator = EMAIndicator(close=df['close'], window=period)
            ema = indicator.ema_indicator()
            if ema is None or ema.empty:
                return None

            ema_value = self._get_latest_value(ema)
            current_price = self._get_latest_value(df['close'])

            if ema_value == 0:
                return None

            if current_price > ema_value * 1.02:
                signal = "buy"
                desc = f"価格がEMA{period}を上回っています"
            elif current_price < ema_value * 0.98:
                signal = "sell"
                desc = f"価格がEMA{period}を下回っています"
            else:
                signal = "neutral"
                desc = f"価格がEMA{period}付近で推移しています"

            return IndicatorResult(
                name=f"EMA{period}",
                value=round(ema_value, 2),
                signal=signal,
                description=desc,
                additional_data={"current_price": round(current_price, 2)}
            )
        except Exception as e:
            logger.error(f"Error calculating EMA{period}: {e}")
            return None

    def calculate_ema(self, df: pd.DataFrame, periods: List[int] = [5, 10, 20, 50, 200]) -> List[IndicatorResult]:
        """複数期間のEMAを計算"""
        results = []
        for period in periods:
            result = self.calculate_ema_single(df, period)
            if result:
                results.append(result)
        return results

    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> Optional[IndicatorResult]:
        """RSI (相対力指数) を計算"""
        try:
            indicator = RSIIndicator(close=df['close'], window=period)
            rsi = indicator.rsi()
            if rsi is None or rsi.empty:
                return None

            rsi_value = self._get_latest_value(rsi)

            if rsi_value >= 70:
                sig = "sell"
                desc = f"RSI={rsi_value:.1f}で買われすぎ領域です。反落に注意"
            elif rsi_value <= 30:
                sig = "buy"
                desc = f"RSI={rsi_value:.1f}で売られすぎ領域です。反発の可能性"
            elif rsi_value >= 60:
                sig = "neutral"
                desc = f"RSI={rsi_value:.1f}で上昇傾向ですが、過熱気味"
            elif rsi_value <= 40:
                sig = "neutral"
                desc = f"RSI={rsi_value:.1f}で下落傾向ですが、売られすぎではない"
            else:
                sig = "neutral"
                desc = f"RSI={rsi_value:.1f}で中立的な水準です"

            return IndicatorResult(
                name="RSI",
                value=round(rsi_value, 2),
                signal=sig,
                description=desc,
                additional_data={"period": period, "overbought": 70, "oversold": 30}
            )
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            return None

    def calculate_macd(self, df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> Optional[IndicatorResult]:
        """MACD (移動平均収束拡散) を計算"""
        try:
            indicator = MACD(close=df['close'], window_slow=slow, window_fast=fast, window_sign=signal)
            macd_line = indicator.macd()
            signal_line = indicator.macd_signal()
            histogram = indicator.macd_diff()

            if macd_line is None or signal_line is None:
                return None

            macd_value = self._get_latest_value(macd_line)
            signal_value = self._get_latest_value(signal_line)
            hist_value = self._get_latest_value(histogram)

            # 前回のヒストグラム値を取得
            prev_hist = self._safe_float(histogram.iloc[-2]) if len(histogram) > 1 else 0

            if macd_value > signal_value and hist_value > prev_hist:
                sig = "buy"
                desc = "MACDがシグナルを上回り、上昇モメンタム強化"
            elif macd_value < signal_value and hist_value < prev_hist:
                sig = "sell"
                desc = "MACDがシグナルを下回り、下落モメンタム強化"
            elif macd_value > signal_value:
                sig = "neutral"
                desc = "MACDはシグナル上だが、モメンタム鈍化"
            else:
                sig = "neutral"
                desc = "MACDはシグナル下だが、下落モメンタム鈍化"

            return IndicatorResult(
                name="MACD",
                value=round(macd_value, 4),
                signal=sig,
                description=desc,
                additional_data={
                    "macd_line": round(macd_value, 4),
                    "signal_line": round(signal_value, 4),
                    "histogram": round(hist_value, 4)
                }
            )
        except Exception as e:
            logger.error(f"Error calculating MACD: {e}")
            return None

    def calculate_bollinger_bands(self, df: pd.DataFrame, period: int = 20, std: float = 2.0) -> Optional[IndicatorResult]:
        """Bollinger Bands を計算"""
        try:
            indicator = BollingerBands(close=df['close'], window=period, window_dev=int(std))
            upper = indicator.bollinger_hband()
            middle = indicator.bollinger_mavg()
            lower = indicator.bollinger_lband()
            percent_b = indicator.bollinger_pband()

            if upper is None or lower is None:
                return None

            upper_val = self._get_latest_value(upper)
            middle_val = self._get_latest_value(middle)
            lower_val = self._get_latest_value(lower)
            current_price = self._get_latest_value(df['close'])
            pb_value = self._get_latest_value(percent_b)

            if upper_val == 0 or lower_val == 0:
                return None

            if pb_value >= 1.0:
                sig = "sell"
                desc = f"価格が上限バンド付近（%B={pb_value:.2f}）。過熱気味"
            elif pb_value <= 0.0:
                sig = "buy"
                desc = f"価格が下限バンド付近（%B={pb_value:.2f}）。売られすぎ"
            elif pb_value >= 0.8:
                sig = "neutral"
                desc = f"価格が上限バンドに接近（%B={pb_value:.2f}）"
            elif pb_value <= 0.2:
                sig = "neutral"
                desc = f"価格が下限バンドに接近（%B={pb_value:.2f}）"
            else:
                sig = "neutral"
                desc = f"価格がバンド中央付近（%B={pb_value:.2f}）"

            return IndicatorResult(
                name="Bollinger Bands",
                value=round(middle_val, 2),
                signal=sig,
                description=desc,
                additional_data={
                    "upper": round(upper_val, 2),
                    "middle": round(middle_val, 2),
                    "lower": round(lower_val, 2),
                    "percent_b": round(pb_value, 4),
                    "current_price": round(current_price, 2)
                }
            )
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {e}")
            return None

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> Optional[IndicatorResult]:
        """ATR (Average True Range) を計算"""
        try:
            indicator = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=period)
            atr = indicator.average_true_range()
            if atr is None or atr.empty:
                return None

            atr_value = self._get_latest_value(atr)
            current_price = self._get_latest_value(df['close'])

            if current_price == 0:
                return None

            # ATR%を計算
            atr_percent = (atr_value / current_price) * 100

            if atr_percent >= 5:
                sig = "neutral"
                desc = f"ATR%={atr_percent:.2f}%でボラティリティが非常に高い"
            elif atr_percent >= 3:
                sig = "neutral"
                desc = f"ATR%={atr_percent:.2f}%でボラティリティが高め"
            elif atr_percent >= 1:
                sig = "neutral"
                desc = f"ATR%={atr_percent:.2f}%で標準的なボラティリティ"
            else:
                sig = "neutral"
                desc = f"ATR%={atr_percent:.2f}%でボラティリティが低い"

            return IndicatorResult(
                name="ATR",
                value=round(atr_value, 2),
                signal=sig,
                description=desc,
                additional_data={
                    "atr_percent": round(atr_percent, 2),
                    "period": period
                }
            )
        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
            return None

    def calculate_stochastic(self, df: pd.DataFrame, k: int = 14, d: int = 3, smooth_k: int = 3) -> Optional[IndicatorResult]:
        """Stochastic Oscillator を計算"""
        try:
            indicator = StochasticOscillator(
                high=df['high'], low=df['low'], close=df['close'],
                window=k, smooth_window=d
            )
            stoch_k = indicator.stoch()
            stoch_d = indicator.stoch_signal()

            if stoch_k is None or stoch_d is None:
                return None

            k_value = self._get_latest_value(stoch_k)
            d_value = self._get_latest_value(stoch_d)

            if k_value >= 80 and d_value >= 80:
                sig = "sell"
                desc = f"ストキャスティクス(%K={k_value:.1f}, %D={d_value:.1f})が買われすぎ領域"
            elif k_value <= 20 and d_value <= 20:
                sig = "buy"
                desc = f"ストキャスティクス(%K={k_value:.1f}, %D={d_value:.1f})が売られすぎ領域"
            elif k_value > d_value and k_value > 50:
                sig = "neutral"
                desc = f"ストキャスティクスは上昇傾向（%K={k_value:.1f}）"
            elif k_value < d_value and k_value < 50:
                sig = "neutral"
                desc = f"ストキャスティクスは下落傾向（%K={k_value:.1f}）"
            else:
                sig = "neutral"
                desc = f"ストキャスティクスは中立（%K={k_value:.1f}, %D={d_value:.1f}）"

            return IndicatorResult(
                name="Stochastic",
                value=round(k_value, 2),
                signal=sig,
                description=desc,
                additional_data={
                    "k": round(k_value, 2),
                    "d": round(d_value, 2)
                }
            )
        except Exception as e:
            logger.error(f"Error calculating Stochastic: {e}")
            return None

    def calculate_ichimoku(self, df: pd.DataFrame) -> Optional[IndicatorResult]:
        """一目均衡表を計算"""
        try:
            indicator = IchimokuIndicator(high=df['high'], low=df['low'])
            tenkan = indicator.ichimoku_conversion_line()
            kijun = indicator.ichimoku_base_line()
            senkou_a = indicator.ichimoku_a()
            senkou_b = indicator.ichimoku_b()

            if tenkan is None or kijun is None:
                return None

            tenkan_val = self._get_latest_value(tenkan)
            kijun_val = self._get_latest_value(kijun)
            senkou_a_val = self._get_latest_value(senkou_a)
            senkou_b_val = self._get_latest_value(senkou_b)
            current_price = self._get_latest_value(df['close'])

            # 雲の上端と下端
            cloud_top = max(senkou_a_val, senkou_b_val)
            cloud_bottom = min(senkou_a_val, senkou_b_val)

            if current_price > cloud_top and tenkan_val > kijun_val:
                sig = "buy"
                desc = "価格が雲の上、転換線が基準線の上（強い上昇トレンド）"
            elif current_price < cloud_bottom and tenkan_val < kijun_val:
                sig = "sell"
                desc = "価格が雲の下、転換線が基準線の下（強い下降トレンド）"
            elif cloud_bottom <= current_price <= cloud_top:
                sig = "neutral"
                desc = "価格が雲の中（方向感なし、様子見）"
            elif current_price > cloud_top:
                sig = "neutral"
                desc = "価格は雲の上だが、転換線と基準線が交錯"
            else:
                sig = "neutral"
                desc = "価格は雲の下だが、売りシグナル未確定"

            return IndicatorResult(
                name="Ichimoku",
                value=round(current_price, 2),
                signal=sig,
                description=desc,
                additional_data={
                    "tenkan": round(tenkan_val, 2),
                    "kijun": round(kijun_val, 2),
                    "senkou_a": round(senkou_a_val, 2),
                    "senkou_b": round(senkou_b_val, 2),
                    "cloud_top": round(cloud_top, 2),
                    "cloud_bottom": round(cloud_bottom, 2)
                }
            )
        except Exception as e:
            logger.error(f"Error calculating Ichimoku: {e}")
            return None

    def calculate_adx(self, df: pd.DataFrame, period: int = 14) -> Optional[IndicatorResult]:
        """ADX (Average Directional Index) を計算"""
        try:
            indicator = ADXIndicator(high=df['high'], low=df['low'], close=df['close'], window=period)
            adx = indicator.adx()
            dmp = indicator.adx_pos()
            dmn = indicator.adx_neg()

            if adx is None:
                return None

            adx_value = self._get_latest_value(adx)
            dmp_value = self._get_latest_value(dmp)
            dmn_value = self._get_latest_value(dmn)

            if adx_value >= 25 and dmp_value > dmn_value:
                sig = "buy"
                desc = f"ADX={adx_value:.1f}で強い上昇トレンド（+DI > -DI）"
            elif adx_value >= 25 and dmp_value < dmn_value:
                sig = "sell"
                desc = f"ADX={adx_value:.1f}で強い下降トレンド（-DI > +DI）"
            elif adx_value < 20:
                sig = "neutral"
                desc = f"ADX={adx_value:.1f}でトレンドなし（レンジ相場）"
            else:
                sig = "neutral"
                desc = f"ADX={adx_value:.1f}でトレンド発生中だが方向性不明確"

            return IndicatorResult(
                name="ADX",
                value=round(adx_value, 2),
                signal=sig,
                description=desc,
                additional_data={
                    "adx": round(adx_value, 2),
                    "plus_di": round(dmp_value, 2),
                    "minus_di": round(dmn_value, 2)
                }
            )
        except Exception as e:
            logger.error(f"Error calculating ADX: {e}")
            return None

    def calculate_obv(self, df: pd.DataFrame) -> Optional[IndicatorResult]:
        """OBV (On Balance Volume) を計算"""
        try:
            indicator = OnBalanceVolumeIndicator(close=df['close'], volume=df['volume'])
            obv = indicator.on_balance_volume()
            if obv is None or obv.empty:
                return None

            obv_value = self._get_latest_value(obv)

            # OBVの20日移動平均を計算
            obv_sma = SMAIndicator(close=obv, window=20).sma_indicator()
            obv_sma_value = self._get_latest_value(obv_sma) if obv_sma is not None else obv_value

            if obv_value > obv_sma_value * 1.05:
                sig = "buy"
                desc = "OBVが上昇トレンド（買い圧力増加）"
            elif obv_value < obv_sma_value * 0.95:
                sig = "sell"
                desc = "OBVが下落トレンド（売り圧力増加）"
            else:
                sig = "neutral"
                desc = "OBVは横ばい"

            return IndicatorResult(
                name="OBV",
                value=round(obv_value, 0),
                signal=sig,
                description=desc,
                additional_data={
                    "obv_sma20": round(obv_sma_value, 0)
                }
            )
        except Exception as e:
            logger.error(f"Error calculating OBV: {e}")
            return None

    # === 追加のオシレーター系指標 ===

    def calculate_williams_r(self, df: pd.DataFrame, period: int = 14) -> Optional[IndicatorResult]:
        """Williams %R を計算"""
        try:
            indicator = WilliamsRIndicator(high=df['high'], low=df['low'], close=df['close'], lbp=period)
            willr = indicator.williams_r()
            if willr is None or willr.empty:
                return None

            willr_value = self._get_latest_value(willr)

            if willr_value >= -20:
                sig = "sell"
                desc = f"Williams %R={willr_value:.1f}で買われすぎ"
            elif willr_value <= -80:
                sig = "buy"
                desc = f"Williams %R={willr_value:.1f}で売られすぎ"
            else:
                sig = "neutral"
                desc = f"Williams %R={willr_value:.1f}で中立"

            return IndicatorResult(
                name="Williams %R",
                value=round(willr_value, 2),
                signal=sig,
                description=desc
            )
        except Exception as e:
            logger.error(f"Error calculating Williams %R: {e}")
            return None

    def calculate_cci(self, df: pd.DataFrame, period: int = 20) -> Optional[IndicatorResult]:
        """CCI (Commodity Channel Index) を計算 - manual implementation"""
        try:
            tp = (df['high'] + df['low'] + df['close']) / 3
            sma = tp.rolling(window=period).mean()
            mad = tp.rolling(window=period).apply(lambda x: np.abs(x - x.mean()).mean())
            cci = (tp - sma) / (0.015 * mad)

            if cci is None or cci.empty:
                return None

            cci_value = self._get_latest_value(cci)

            if cci_value >= 100:
                sig = "sell"
                desc = f"CCI={cci_value:.1f}で買われすぎ領域"
            elif cci_value <= -100:
                sig = "buy"
                desc = f"CCI={cci_value:.1f}で売られすぎ領域"
            else:
                sig = "neutral"
                desc = f"CCI={cci_value:.1f}で中立領域"

            return IndicatorResult(
                name="CCI",
                value=round(cci_value, 2),
                signal=sig,
                description=desc
            )
        except Exception as e:
            logger.error(f"Error calculating CCI: {e}")
            return None

    def calculate_roc(self, df: pd.DataFrame, period: int = 12) -> Optional[IndicatorResult]:
        """ROC (Rate of Change) を計算"""
        try:
            indicator = ROCIndicator(close=df['close'], window=period)
            roc = indicator.roc()
            if roc is None or roc.empty:
                return None

            roc_value = self._get_latest_value(roc)

            if roc_value > 5:
                sig = "buy"
                desc = f"ROC={roc_value:.2f}%で強い上昇モメンタム"
            elif roc_value < -5:
                sig = "sell"
                desc = f"ROC={roc_value:.2f}%で強い下落モメンタム"
            elif roc_value > 0:
                sig = "neutral"
                desc = f"ROC={roc_value:.2f}%で上昇傾向"
            else:
                sig = "neutral"
                desc = f"ROC={roc_value:.2f}%で下落傾向"

            return IndicatorResult(
                name="ROC",
                value=round(roc_value, 2),
                signal=sig,
                description=desc
            )
        except Exception as e:
            logger.error(f"Error calculating ROC: {e}")
            return None

    def calculate_momentum(self, df: pd.DataFrame, period: int = 10) -> Optional[IndicatorResult]:
        """Momentum を計算"""
        try:
            mom = df['close'] - df['close'].shift(period)
            if mom is None or mom.empty:
                return None

            mom_value = self._get_latest_value(mom)
            current_price = self._get_latest_value(df['close'])
            mom_percent = (mom_value / current_price) * 100 if current_price != 0 else 0

            if mom_percent > 3:
                sig = "buy"
                desc = f"モメンタム={mom_percent:.2f}%で強い上昇"
            elif mom_percent < -3:
                sig = "sell"
                desc = f"モメンタム={mom_percent:.2f}%で強い下落"
            else:
                sig = "neutral"
                desc = f"モメンタム={mom_percent:.2f}%で中立"

            return IndicatorResult(
                name="Momentum",
                value=round(mom_value, 2),
                signal=sig,
                description=desc,
                additional_data={"percent": round(mom_percent, 2)}
            )
        except Exception as e:
            logger.error(f"Error calculating Momentum: {e}")
            return None

    def calculate_ultimate_oscillator(self, df: pd.DataFrame) -> Optional[IndicatorResult]:
        """Ultimate Oscillator を計算"""
        try:
            indicator = UltimateOscillator(high=df['high'], low=df['low'], close=df['close'])
            uo = indicator.ultimate_oscillator()
            if uo is None or uo.empty:
                return None

            uo_value = self._get_latest_value(uo)

            if uo_value >= 70:
                sig = "sell"
                desc = f"Ultimate Oscillator={uo_value:.1f}で買われすぎ"
            elif uo_value <= 30:
                sig = "buy"
                desc = f"Ultimate Oscillator={uo_value:.1f}で売られすぎ"
            else:
                sig = "neutral"
                desc = f"Ultimate Oscillator={uo_value:.1f}で中立"

            return IndicatorResult(
                name="Ultimate Oscillator",
                value=round(uo_value, 2),
                signal=sig,
                description=desc
            )
        except Exception as e:
            logger.error(f"Error calculating Ultimate Oscillator: {e}")
            return None

    def calculate_tsi(self, df: pd.DataFrame) -> Optional[IndicatorResult]:
        """TSI (True Strength Index) を計算"""
        try:
            indicator = TSIIndicator(close=df['close'])
            tsi = indicator.tsi()
            if tsi is None or tsi.empty:
                return None

            tsi_value = self._get_latest_value(tsi)

            if tsi_value > 25:
                sig = "buy"
                desc = f"TSI={tsi_value:.1f}で強い上昇モメンタム"
            elif tsi_value < -25:
                sig = "sell"
                desc = f"TSI={tsi_value:.1f}で強い下落モメンタム"
            else:
                sig = "neutral"
                desc = f"TSI={tsi_value:.1f}で中立"

            return IndicatorResult(
                name="TSI",
                value=round(tsi_value, 2),
                signal=sig,
                description=desc
            )
        except Exception as e:
            logger.error(f"Error calculating TSI: {e}")
            return None

    # === ボラティリティ系指標 ===

    def calculate_keltner_channel(self, df: pd.DataFrame, period: int = 20) -> Optional[IndicatorResult]:
        """Keltner Channel を計算"""
        try:
            indicator = KeltnerChannel(high=df['high'], low=df['low'], close=df['close'], window=period)
            upper = indicator.keltner_channel_hband()
            middle = indicator.keltner_channel_mband()
            lower = indicator.keltner_channel_lband()

            if upper is None or lower is None:
                return None

            upper_val = self._get_latest_value(upper)
            middle_val = self._get_latest_value(middle)
            lower_val = self._get_latest_value(lower)
            current_price = self._get_latest_value(df['close'])

            if current_price > upper_val:
                sig = "sell"
                desc = "価格がKeltner上限を突破（過熱気味）"
            elif current_price < lower_val:
                sig = "buy"
                desc = "価格がKeltner下限を突破（売られすぎ）"
            else:
                sig = "neutral"
                desc = "価格がKeltnerチャネル内"

            return IndicatorResult(
                name="Keltner Channel",
                value=round(middle_val, 2),
                signal=sig,
                description=desc,
                additional_data={
                    "upper": round(upper_val, 2),
                    "basis": round(middle_val, 2),
                    "lower": round(lower_val, 2)
                }
            )
        except Exception as e:
            logger.error(f"Error calculating Keltner Channel: {e}")
            return None

    def calculate_donchian_channel(self, df: pd.DataFrame, period: int = 20) -> Optional[IndicatorResult]:
        """Donchian Channel を計算"""
        try:
            indicator = DonchianChannel(high=df['high'], low=df['low'], close=df['close'], window=period)
            upper = indicator.donchian_channel_hband()
            lower = indicator.donchian_channel_lband()
            middle = indicator.donchian_channel_mband()

            if upper is None or lower is None:
                return None

            upper_val = self._get_latest_value(upper)
            lower_val = self._get_latest_value(lower)
            middle_val = self._get_latest_value(middle)
            current_price = self._get_latest_value(df['close'])

            if current_price >= upper_val:
                sig = "buy"
                desc = f"{period}日高値を更新（ブレイクアウト）"
            elif current_price <= lower_val:
                sig = "sell"
                desc = f"{period}日安値を更新（ブレイクダウン）"
            else:
                sig = "neutral"
                desc = "Donchianチャネル内で推移"

            return IndicatorResult(
                name="Donchian Channel",
                value=round(middle_val, 2),
                signal=sig,
                description=desc,
                additional_data={
                    "upper": round(upper_val, 2),
                    "lower": round(lower_val, 2),
                    "mid": round(middle_val, 2)
                }
            )
        except Exception as e:
            logger.error(f"Error calculating Donchian Channel: {e}")
            return None

    def calculate_std(self, df: pd.DataFrame, period: int = 20) -> Optional[IndicatorResult]:
        """Standard Deviation を計算"""
        try:
            std = df['close'].rolling(window=period).std()
            if std is None or std.empty:
                return None

            std_value = self._get_latest_value(std)
            current_price = self._get_latest_value(df['close'])
            std_percent = (std_value / current_price) * 100 if current_price != 0 else 0

            return IndicatorResult(
                name="Standard Deviation",
                value=round(std_value, 2),
                signal="neutral",
                description=f"標準偏差={std_value:.2f}（{std_percent:.2f}%）",
                additional_data={"std_percent": round(std_percent, 2)}
            )
        except Exception as e:
            logger.error(f"Error calculating Standard Deviation: {e}")
            return None

    # === 出来高系指標 ===

    def calculate_vwap(self, df: pd.DataFrame) -> Optional[IndicatorResult]:
        """VWAP (Volume Weighted Average Price) を計算"""
        try:
            indicator = VolumeWeightedAveragePrice(high=df['high'], low=df['low'], close=df['close'], volume=df['volume'])
            vwap = indicator.volume_weighted_average_price()
            if vwap is None or vwap.empty:
                return None

            vwap_value = self._get_latest_value(vwap)
            current_price = self._get_latest_value(df['close'])

            if current_price > vwap_value * 1.02:
                sig = "buy"
                desc = "価格がVWAPを大きく上回る（強気）"
            elif current_price < vwap_value * 0.98:
                sig = "sell"
                desc = "価格がVWAPを大きく下回る（弱気）"
            else:
                sig = "neutral"
                desc = "価格がVWAP付近で推移"

            return IndicatorResult(
                name="VWAP",
                value=round(vwap_value, 2),
                signal=sig,
                description=desc,
                additional_data={"current_price": round(current_price, 2)}
            )
        except Exception as e:
            logger.error(f"Error calculating VWAP: {e}")
            return None

    def calculate_ad(self, df: pd.DataFrame) -> Optional[IndicatorResult]:
        """AD (Accumulation/Distribution) を計算"""
        try:
            indicator = AccDistIndexIndicator(high=df['high'], low=df['low'], close=df['close'], volume=df['volume'])
            ad = indicator.acc_dist_index()
            if ad is None or ad.empty:
                return None

            ad_value = self._get_latest_value(ad)
            ad_sma = SMAIndicator(close=ad, window=20).sma_indicator()
            ad_sma_value = self._get_latest_value(ad_sma) if ad_sma is not None else ad_value

            if ad_value > ad_sma_value * 1.05:
                sig = "buy"
                desc = "A/Dラインが上昇トレンド（買い集め）"
            elif ad_value < ad_sma_value * 0.95:
                sig = "sell"
                desc = "A/Dラインが下落トレンド（売り逃げ）"
            else:
                sig = "neutral"
                desc = "A/Dラインは横ばい"

            return IndicatorResult(
                name="A/D",
                value=round(ad_value, 0),
                signal=sig,
                description=desc
            )
        except Exception as e:
            logger.error(f"Error calculating A/D: {e}")
            return None

    def calculate_cmf(self, df: pd.DataFrame, period: int = 20) -> Optional[IndicatorResult]:
        """CMF (Chaikin Money Flow) を計算"""
        try:
            indicator = ChaikinMoneyFlowIndicator(high=df['high'], low=df['low'], close=df['close'], volume=df['volume'], window=period)
            cmf = indicator.chaikin_money_flow()
            if cmf is None or cmf.empty:
                return None

            cmf_value = self._get_latest_value(cmf)

            if cmf_value > 0.1:
                sig = "buy"
                desc = f"CMF={cmf_value:.3f}で買い圧力優勢"
            elif cmf_value < -0.1:
                sig = "sell"
                desc = f"CMF={cmf_value:.3f}で売り圧力優勢"
            else:
                sig = "neutral"
                desc = f"CMF={cmf_value:.3f}で中立"

            return IndicatorResult(
                name="CMF",
                value=round(cmf_value, 4),
                signal=sig,
                description=desc
            )
        except Exception as e:
            logger.error(f"Error calculating CMF: {e}")
            return None

    def calculate_mfi(self, df: pd.DataFrame, period: int = 14) -> Optional[IndicatorResult]:
        """MFI (Money Flow Index) を計算"""
        try:
            indicator = MFIIndicator(high=df['high'], low=df['low'], close=df['close'], volume=df['volume'], window=period)
            mfi = indicator.money_flow_index()
            if mfi is None or mfi.empty:
                return None

            mfi_value = self._get_latest_value(mfi)

            if mfi_value >= 80:
                sig = "sell"
                desc = f"MFI={mfi_value:.1f}で買われすぎ（出来高伴う）"
            elif mfi_value <= 20:
                sig = "buy"
                desc = f"MFI={mfi_value:.1f}で売られすぎ（出来高伴う）"
            else:
                sig = "neutral"
                desc = f"MFI={mfi_value:.1f}で中立"

            return IndicatorResult(
                name="MFI",
                value=round(mfi_value, 2),
                signal=sig,
                description=desc
            )
        except Exception as e:
            logger.error(f"Error calculating MFI: {e}")
            return None

    def calculate_force_index(self, df: pd.DataFrame, period: int = 13) -> Optional[IndicatorResult]:
        """Force Index を計算"""
        try:
            indicator = ForceIndexIndicator(close=df['close'], volume=df['volume'], window=period)
            fi = indicator.force_index()
            if fi is None or fi.empty:
                return None

            fi_value = self._get_latest_value(fi)

            if fi_value > 0:
                sig = "buy"
                desc = f"Force Index={fi_value:.0f}で買い圧力優勢"
            elif fi_value < 0:
                sig = "sell"
                desc = f"Force Index={fi_value:.0f}で売り圧力優勢"
            else:
                sig = "neutral"
                desc = "Force Indexは中立"

            return IndicatorResult(
                name="Force Index",
                value=round(fi_value, 0),
                signal=sig,
                description=desc
            )
        except Exception as e:
            logger.error(f"Error calculating Force Index: {e}")
            return None

    def calculate_eom(self, df: pd.DataFrame, period: int = 14) -> Optional[IndicatorResult]:
        """EOM (Ease of Movement) を計算"""
        try:
            indicator = EaseOfMovementIndicator(high=df['high'], low=df['low'], volume=df['volume'], window=period)
            eom = indicator.ease_of_movement()
            if eom is None or eom.empty:
                return None

            eom_value = self._get_latest_value(eom)

            if eom_value > 0:
                sig = "buy"
                desc = f"EOM={eom_value:.4f}で上昇しやすい状態"
            elif eom_value < 0:
                sig = "sell"
                desc = f"EOM={eom_value:.4f}で下落しやすい状態"
            else:
                sig = "neutral"
                desc = "EOMは中立"

            return IndicatorResult(
                name="EOM",
                value=round(eom_value, 4),
                signal=sig,
                description=desc
            )
        except Exception as e:
            logger.error(f"Error calculating EOM: {e}")
            return None

    def calculate_volume_sma(self, df: pd.DataFrame, period: int = 20) -> Optional[IndicatorResult]:
        """Volume SMA を計算"""
        try:
            vol_sma = SMAIndicator(close=df['volume'], window=period).sma_indicator()
            if vol_sma is None or vol_sma.empty:
                return None

            vol_sma_value = self._get_latest_value(vol_sma)
            current_volume = self._get_latest_value(df['volume'])

            ratio = current_volume / vol_sma_value if vol_sma_value != 0 else 1

            if ratio > 1.5:
                sig = "neutral"
                desc = f"出来高が平均の{ratio:.1f}倍（活発）"
            elif ratio < 0.5:
                sig = "neutral"
                desc = f"出来高が平均の{ratio:.1f}倍（閑散）"
            else:
                sig = "neutral"
                desc = f"出来高は平均的（{ratio:.1f}倍）"

            return IndicatorResult(
                name="Volume SMA",
                value=round(vol_sma_value, 0),
                signal=sig,
                description=desc,
                additional_data={
                    "current_volume": round(current_volume, 0),
                    "ratio": round(ratio, 2)
                }
            )
        except Exception as e:
            logger.error(f"Error calculating Volume SMA: {e}")
            return None

    # === 追加のトレンド系指標 ===

    def calculate_wma(self, df: pd.DataFrame, period: int) -> Optional[IndicatorResult]:
        """WMA (加重移動平均) を計算"""
        try:
            indicator = WMAIndicator(close=df['close'], window=period)
            wma = indicator.wma()
            if wma is None or wma.empty:
                return None

            wma_value = self._get_latest_value(wma)
            current_price = self._get_latest_value(df['close'])

            if current_price > wma_value * 1.02:
                sig = "buy"
                desc = f"価格がWMA{period}を上回る"
            elif current_price < wma_value * 0.98:
                sig = "sell"
                desc = f"価格がWMA{period}を下回る"
            else:
                sig = "neutral"
                desc = f"価格がWMA{period}付近"

            return IndicatorResult(
                name=f"WMA{period}",
                value=round(wma_value, 2),
                signal=sig,
                description=desc
            )
        except Exception as e:
            logger.error(f"Error calculating WMA{period}: {e}")
            return None

    def calculate_dema(self, df: pd.DataFrame, period: int = 20) -> Optional[IndicatorResult]:
        """DEMA (Double EMA) を計算"""
        try:
            ema1 = EMAIndicator(close=df['close'], window=period).ema_indicator()
            ema2 = EMAIndicator(close=ema1, window=period).ema_indicator()
            dema = 2 * ema1 - ema2

            if dema is None or dema.empty:
                return None

            dema_value = self._get_latest_value(dema)
            current_price = self._get_latest_value(df['close'])

            if current_price > dema_value * 1.02:
                sig = "buy"
                desc = "価格がDEMAを上回る"
            elif current_price < dema_value * 0.98:
                sig = "sell"
                desc = "価格がDEMAを下回る"
            else:
                sig = "neutral"
                desc = "価格がDEMA付近"

            return IndicatorResult(
                name="DEMA",
                value=round(dema_value, 2),
                signal=sig,
                description=desc
            )
        except Exception as e:
            logger.error(f"Error calculating DEMA: {e}")
            return None

    def calculate_tema(self, df: pd.DataFrame, period: int = 20) -> Optional[IndicatorResult]:
        """TEMA (Triple EMA) を計算"""
        try:
            ema1 = EMAIndicator(close=df['close'], window=period).ema_indicator()
            ema2 = EMAIndicator(close=ema1, window=period).ema_indicator()
            ema3 = EMAIndicator(close=ema2, window=period).ema_indicator()
            tema = 3 * ema1 - 3 * ema2 + ema3

            if tema is None or tema.empty:
                return None

            tema_value = self._get_latest_value(tema)
            current_price = self._get_latest_value(df['close'])

            if current_price > tema_value * 1.02:
                sig = "buy"
                desc = "価格がTEMAを上回る"
            elif current_price < tema_value * 0.98:
                sig = "sell"
                desc = "価格がTEMAを下回る"
            else:
                sig = "neutral"
                desc = "価格がTEMA付近"

            return IndicatorResult(
                name="TEMA",
                value=round(tema_value, 2),
                signal=sig,
                description=desc
            )
        except Exception as e:
            logger.error(f"Error calculating TEMA: {e}")
            return None

    def calculate_kst(self, df: pd.DataFrame) -> Optional[IndicatorResult]:
        """KST (Know Sure Thing) を計算"""
        try:
            indicator = KSTIndicator(close=df['close'])
            kst = indicator.kst()
            signal = indicator.kst_sig()

            if kst is None or signal is None:
                return None

            kst_value = self._get_latest_value(kst)
            signal_value = self._get_latest_value(signal)

            if kst_value > signal_value:
                sig = "buy"
                desc = f"KSTがシグナルを上回る（上昇モメンタム）"
            elif kst_value < signal_value:
                sig = "sell"
                desc = f"KSTがシグナルを下回る（下落モメンタム）"
            else:
                sig = "neutral"
                desc = "KSTは中立"

            return IndicatorResult(
                name="KST",
                value=round(kst_value, 2),
                signal=sig,
                description=desc
            )
        except Exception as e:
            logger.error(f"Error calculating KST: {e}")
            return None

    def calculate_parabolic_sar(self, df: pd.DataFrame) -> Optional[IndicatorResult]:
        """Parabolic SAR を計算"""
        try:
            indicator = PSARIndicator(high=df['high'], low=df['low'], close=df['close'])
            psar = indicator.psar()
            psar_up = indicator.psar_up()
            psar_down = indicator.psar_down()

            if psar is None:
                return None

            psar_value = self._get_latest_value(psar)
            current_price = self._get_latest_value(df['close'])
            psar_up_val = self._get_latest_value(psar_up) if psar_up is not None else 0
            psar_down_val = self._get_latest_value(psar_down) if psar_down is not None else 0

            if current_price > psar_value:
                sig = "buy"
                desc = "Parabolic SARが価格下（上昇トレンド）"
            else:
                sig = "sell"
                desc = "Parabolic SARが価格上（下降トレンド）"

            return IndicatorResult(
                name="Parabolic SAR",
                value=round(psar_value, 2),
                signal=sig,
                description=desc,
                additional_data={"current_price": round(current_price, 2)}
            )
        except Exception as e:
            logger.error(f"Error calculating Parabolic SAR: {e}")
            return None

    def calculate_aroon(self, df: pd.DataFrame, period: int = 25) -> Optional[IndicatorResult]:
        """Aroon を計算"""
        try:
            indicator = AroonIndicator(high=df['high'], low=df['low'], window=period)
            aroon_up = indicator.aroon_up()
            aroon_down = indicator.aroon_down()
            aroon_ind = indicator.aroon_indicator()

            if aroon_up is None or aroon_down is None:
                return None

            aroon_up_val = self._get_latest_value(aroon_up)
            aroon_down_val = self._get_latest_value(aroon_down)
            aroon_osc = aroon_up_val - aroon_down_val

            if aroon_osc > 50:
                sig = "buy"
                desc = f"Aroon Oscillator={aroon_osc:.0f}で強い上昇トレンド"
            elif aroon_osc < -50:
                sig = "sell"
                desc = f"Aroon Oscillator={aroon_osc:.0f}で強い下降トレンド"
            else:
                sig = "neutral"
                desc = f"Aroon Oscillator={aroon_osc:.0f}でトレンド不明確"

            return IndicatorResult(
                name="Aroon",
                value=round(aroon_osc, 2),
                signal=sig,
                description=desc,
                additional_data={
                    "aroon_up": round(aroon_up_val, 2),
                    "aroon_down": round(aroon_down_val, 2)
                }
            )
        except Exception as e:
            logger.error(f"Error calculating Aroon: {e}")
            return None

    # === 追加のオシレーター系 ===

    def calculate_stochastic_rsi(self, df: pd.DataFrame, period: int = 14) -> Optional[IndicatorResult]:
        """Stochastic RSI を計算"""
        try:
            indicator = StochRSIIndicator(close=df['close'], window=period)
            stoch_rsi = indicator.stochrsi()
            stoch_rsi_k = indicator.stochrsi_k()
            stoch_rsi_d = indicator.stochrsi_d()

            if stoch_rsi_k is None:
                return None

            k_value = self._get_latest_value(stoch_rsi_k) * 100  # Convert to percentage
            d_value = self._get_latest_value(stoch_rsi_d) * 100 if stoch_rsi_d is not None else k_value

            if k_value >= 80:
                sig = "sell"
                desc = f"Stochastic RSI={k_value:.1f}で買われすぎ"
            elif k_value <= 20:
                sig = "buy"
                desc = f"Stochastic RSI={k_value:.1f}で売られすぎ"
            else:
                sig = "neutral"
                desc = f"Stochastic RSI={k_value:.1f}で中立"

            return IndicatorResult(
                name="Stochastic RSI",
                value=round(k_value, 2),
                signal=sig,
                description=desc,
                additional_data={"k": round(k_value, 2), "d": round(d_value, 2)}
            )
        except Exception as e:
            logger.error(f"Error calculating Stochastic RSI: {e}")
            return None

    def calculate_ppo(self, df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> Optional[IndicatorResult]:
        """PPO (Percentage Price Oscillator) を計算 - 手動実装"""
        try:
            close = df['close']
            ema_fast = close.ewm(span=fast, adjust=False).mean()
            ema_slow = close.ewm(span=slow, adjust=False).mean()
            ppo = ((ema_fast - ema_slow) / ema_slow) * 100
            ppo_signal = ppo.ewm(span=signal, adjust=False).mean()

            if ppo.empty:
                return None

            ppo_value = self._get_latest_value(ppo)
            signal_value = self._get_latest_value(ppo_signal)

            if ppo_value > signal_value and ppo_value > 0:
                sig = "buy"
                desc = f"PPO={ppo_value:.2f}%でシグナル上回る（強気）"
            elif ppo_value < signal_value and ppo_value < 0:
                sig = "sell"
                desc = f"PPO={ppo_value:.2f}%でシグナル下回る（弱気）"
            else:
                sig = "neutral"
                desc = f"PPO={ppo_value:.2f}%で中立"

            return IndicatorResult(
                name="PPO",
                value=round(ppo_value, 2),
                signal=sig,
                description=desc
            )
        except Exception as e:
            logger.error(f"Error calculating PPO: {e}")
            return None

    def calculate_dpo(self, df: pd.DataFrame, period: int = 20) -> Optional[IndicatorResult]:
        """DPO (Detrended Price Oscillator) を計算"""
        try:
            indicator = DPOIndicator(close=df['close'], window=period)
            dpo = indicator.dpo()
            if dpo is None or dpo.empty:
                return None

            dpo_value = self._get_latest_value(dpo)

            if dpo_value > 0:
                sig = "buy"
                desc = f"DPO={dpo_value:.2f}で価格がトレンド上"
            elif dpo_value < 0:
                sig = "sell"
                desc = f"DPO={dpo_value:.2f}で価格がトレンド下"
            else:
                sig = "neutral"
                desc = "DPOは中立"

            return IndicatorResult(
                name="DPO",
                value=round(dpo_value, 2),
                signal=sig,
                description=desc
            )
        except Exception as e:
            logger.error(f"Error calculating DPO: {e}")
            return None

    def calculate_trix(self, df: pd.DataFrame, period: int = 18) -> Optional[IndicatorResult]:
        """TRIX を計算"""
        try:
            indicator = TRIXIndicator(close=df['close'], window=period)
            trix = indicator.trix()
            if trix is None or trix.empty:
                return None

            trix_value = self._get_latest_value(trix)

            if trix_value > 0:
                sig = "buy"
                desc = f"TRIX={trix_value:.4f}で上昇モメンタム"
            elif trix_value < 0:
                sig = "sell"
                desc = f"TRIX={trix_value:.4f}で下落モメンタム"
            else:
                sig = "neutral"
                desc = "TRIXは中立"

            return IndicatorResult(
                name="TRIX",
                value=round(trix_value, 4),
                signal=sig,
                description=desc
            )
        except Exception as e:
            logger.error(f"Error calculating TRIX: {e}")
            return None

    # === 追加のボラティリティ系 ===

    def calculate_ulcer_index(self, df: pd.DataFrame, period: int = 14) -> Optional[IndicatorResult]:
        """Ulcer Index を計算"""
        try:
            indicator = UlcerIndex(close=df['close'], window=period)
            ui = indicator.ulcer_index()
            if ui is None or ui.empty:
                return None

            ui_value = self._get_latest_value(ui)

            if ui_value > 10:
                sig = "neutral"
                desc = f"Ulcer Index={ui_value:.2f}で高リスク"
            elif ui_value > 5:
                sig = "neutral"
                desc = f"Ulcer Index={ui_value:.2f}で中程度のリスク"
            else:
                sig = "neutral"
                desc = f"Ulcer Index={ui_value:.2f}で低リスク"

            return IndicatorResult(
                name="Ulcer Index",
                value=round(ui_value, 2),
                signal=sig,
                description=desc
            )
        except Exception as e:
            logger.error(f"Error calculating Ulcer Index: {e}")
            return None

    def calculate_natr(self, df: pd.DataFrame, period: int = 14) -> Optional[IndicatorResult]:
        """Normalized ATR を計算"""
        try:
            atr_indicator = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=period)
            atr = atr_indicator.average_true_range()
            current_price = self._get_latest_value(df['close'])

            if atr is None or current_price == 0:
                return None

            atr_value = self._get_latest_value(atr)
            natr_value = (atr_value / current_price) * 100

            if natr_value >= 5:
                sig = "neutral"
                desc = f"NATR={natr_value:.2f}%で高ボラティリティ"
            elif natr_value >= 2:
                sig = "neutral"
                desc = f"NATR={natr_value:.2f}%で中程度のボラティリティ"
            else:
                sig = "neutral"
                desc = f"NATR={natr_value:.2f}%で低ボラティリティ"

            return IndicatorResult(
                name="NATR",
                value=round(natr_value, 2),
                signal=sig,
                description=desc
            )
        except Exception as e:
            logger.error(f"Error calculating NATR: {e}")
            return None

    def calculate_true_range(self, df: pd.DataFrame) -> Optional[IndicatorResult]:
        """True Range を計算"""
        try:
            high_low = df['high'] - df['low']
            high_close = abs(df['high'] - df['close'].shift(1))
            low_close = abs(df['low'] - df['close'].shift(1))
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

            if tr is None or tr.empty:
                return None

            tr_value = self._get_latest_value(tr)
            current_price = self._get_latest_value(df['close'])
            tr_percent = (tr_value / current_price) * 100 if current_price != 0 else 0

            return IndicatorResult(
                name="True Range",
                value=round(tr_value, 2),
                signal="neutral",
                description=f"True Range={tr_value:.2f}（{tr_percent:.2f}%）",
                additional_data={"percent": round(tr_percent, 2)}
            )
        except Exception as e:
            logger.error(f"Error calculating True Range: {e}")
            return None

    # === 追加の出来高系 ===

    def calculate_nvi(self, df: pd.DataFrame) -> Optional[IndicatorResult]:
        """NVI (Negative Volume Index) を計算"""
        try:
            indicator = NegativeVolumeIndexIndicator(close=df['close'], volume=df['volume'])
            nvi = indicator.negative_volume_index()
            if nvi is None or nvi.empty:
                return None

            nvi_value = self._get_latest_value(nvi)
            nvi_sma = SMAIndicator(close=nvi, window=255).sma_indicator() if len(nvi) >= 255 else nvi
            nvi_sma_value = self._get_latest_value(nvi_sma) if nvi_sma is not None else nvi_value

            if nvi_value > nvi_sma_value:
                sig = "buy"
                desc = "NVIがSMA上（スマートマネー買い）"
            else:
                sig = "neutral"
                desc = "NVIがSMA下"

            return IndicatorResult(
                name="NVI",
                value=round(nvi_value, 2),
                signal=sig,
                description=desc
            )
        except Exception as e:
            logger.error(f"Error calculating NVI: {e}")
            return None

    # === パターン認識系 ===

    def calculate_price_vs_sma(self, df: pd.DataFrame, period: int = 20) -> Optional[IndicatorResult]:
        """価格とSMA20の比較"""
        try:
            sma = SMAIndicator(close=df['close'], window=period).sma_indicator()
            if sma is None or sma.empty:
                return None

            sma_value = self._get_latest_value(sma)
            current_price = self._get_latest_value(df['close'])
            diff_percent = ((current_price - sma_value) / sma_value) * 100 if sma_value != 0 else 0

            if diff_percent > 5:
                sig = "sell"
                desc = f"価格がSMA{period}より{diff_percent:.1f}%高い（過熱）"
            elif diff_percent < -5:
                sig = "buy"
                desc = f"価格がSMA{period}より{diff_percent:.1f}%低い（売られすぎ）"
            elif diff_percent > 0:
                sig = "neutral"
                desc = f"価格がSMA{period}より{diff_percent:.1f}%高い"
            else:
                sig = "neutral"
                desc = f"価格がSMA{period}より{diff_percent:.1f}%低い"

            return IndicatorResult(
                name=f"Price vs SMA{period}",
                value=round(diff_percent, 2),
                signal=sig,
                description=desc
            )
        except Exception as e:
            logger.error(f"Error calculating Price vs SMA: {e}")
            return None

    def calculate_ma_cross(self, df: pd.DataFrame) -> Optional[IndicatorResult]:
        """Golden/Death Cross (SMA50/SMA200)"""
        try:
            sma50 = SMAIndicator(close=df['close'], window=50).sma_indicator()
            sma200 = SMAIndicator(close=df['close'], window=200).sma_indicator()

            if sma50 is None or sma200 is None or sma50.empty or sma200.empty:
                return None

            sma50_value = self._get_latest_value(sma50)
            sma200_value = self._get_latest_value(sma200)

            # 前日の値
            sma50_prev = self._safe_float(sma50.iloc[-2]) if len(sma50) > 1 else sma50_value
            sma200_prev = self._safe_float(sma200.iloc[-2]) if len(sma200) > 1 else sma200_value

            cross_value = ((sma50_value - sma200_value) / sma200_value) * 100 if sma200_value != 0 else 0

            # ゴールデンクロス検出
            if sma50_prev <= sma200_prev and sma50_value > sma200_value:
                sig = "buy"
                desc = "ゴールデンクロス発生！（SMA50がSMA200を上抜け）"
            # デッドクロス検出
            elif sma50_prev >= sma200_prev and sma50_value < sma200_value:
                sig = "sell"
                desc = "デッドクロス発生！（SMA50がSMA200を下抜け）"
            elif sma50_value > sma200_value:
                sig = "buy"
                desc = f"SMA50がSMA200の上（上昇トレンド、乖離{cross_value:.1f}%）"
            else:
                sig = "sell"
                desc = f"SMA50がSMA200の下（下降トレンド、乖離{cross_value:.1f}%）"

            return IndicatorResult(
                name="MA Cross",
                value=round(cross_value, 2),
                signal=sig,
                description=desc,
                additional_data={
                    "sma50": round(sma50_value, 2),
                    "sma200": round(sma200_value, 2)
                }
            )
        except Exception as e:
            logger.error(f"Error calculating MA Cross: {e}")
            return None

    def calculate_support_resistance(self, df: pd.DataFrame, period: int = 20) -> Optional[IndicatorResult]:
        """Support/Resistance レベルを計算"""
        try:
            high_max = df['high'].rolling(window=period).max()
            low_min = df['low'].rolling(window=period).min()

            resistance = self._get_latest_value(high_max)
            support = self._get_latest_value(low_min)
            current_price = self._get_latest_value(df['close'])

            # 現在価格の位置を計算
            range_size = resistance - support
            position = ((current_price - support) / range_size * 100) if range_size != 0 else 50

            if position >= 90:
                sig = "sell"
                desc = f"価格がレジスタンス付近（{resistance:.0f}）"
            elif position <= 10:
                sig = "buy"
                desc = f"価格がサポート付近（{support:.0f}）"
            else:
                sig = "neutral"
                desc = f"S:{support:.0f} / R:{resistance:.0f}のレンジ内"

            return IndicatorResult(
                name="Support/Resistance",
                value=round(position, 2),
                signal=sig,
                description=desc,
                additional_data={
                    "support": round(support, 2),
                    "resistance": round(resistance, 2),
                    "position_percent": round(position, 2)
                }
            )
        except Exception as e:
            logger.error(f"Error calculating Support/Resistance: {e}")
            return None

    def calculate_pivot_points(self, df: pd.DataFrame) -> Optional[IndicatorResult]:
        """Pivot Points を計算"""
        try:
            # 前日の高値・安値・終値を使用
            high = self._safe_float(df['high'].iloc[-2]) if len(df) > 1 else self._get_latest_value(df['high'])
            low = self._safe_float(df['low'].iloc[-2]) if len(df) > 1 else self._get_latest_value(df['low'])
            close = self._safe_float(df['close'].iloc[-2]) if len(df) > 1 else self._get_latest_value(df['close'])

            pivot = (high + low + close) / 3
            r1 = 2 * pivot - low
            r2 = pivot + (high - low)
            s1 = 2 * pivot - high
            s2 = pivot - (high - low)

            current_price = self._get_latest_value(df['close'])

            if current_price > r1:
                sig = "buy"
                desc = f"価格がR1（{r1:.0f}）を上回る"
            elif current_price < s1:
                sig = "sell"
                desc = f"価格がS1（{s1:.0f}）を下回る"
            else:
                sig = "neutral"
                desc = f"ピボット（{pivot:.0f}）付近で推移"

            return IndicatorResult(
                name="Pivot Points",
                value=round(pivot, 2),
                signal=sig,
                description=desc,
                additional_data={
                    "pivot": round(pivot, 2),
                    "r1": round(r1, 2),
                    "r2": round(r2, 2),
                    "s1": round(s1, 2),
                    "s2": round(s2, 2)
                }
            )
        except Exception as e:
            logger.error(f"Error calculating Pivot Points: {e}")
            return None

    def calculate_average_price(self, df: pd.DataFrame) -> Optional[IndicatorResult]:
        """Average Price (OHLC/4) を計算"""
        try:
            avg = (df['open'] + df['high'] + df['low'] + df['close']) / 4
            avg_value = self._get_latest_value(avg)
            current_close = self._get_latest_value(df['close'])

            if current_close > avg_value:
                sig = "buy"
                desc = "終値が平均価格を上回る（日中上昇）"
            elif current_close < avg_value:
                sig = "sell"
                desc = "終値が平均価格を下回る（日中下落）"
            else:
                sig = "neutral"
                desc = "終値が平均価格付近"

            return IndicatorResult(
                name="Average Price",
                value=round(avg_value, 2),
                signal=sig,
                description=desc
            )
        except Exception as e:
            logger.error(f"Error calculating Average Price: {e}")
            return None

    def generate_summary(self, indicators: Dict[str, IndicatorResult], ticker: str = "") -> IndicatorSummary:
        """
        イリス向けのサマリーを生成

        Args:
            indicators: 計算された指標の辞書
            ticker: ティッカーシンボル

        Returns:
            IndicatorSummary オブジェクト
        """
        buy_count = 0
        sell_count = 0
        neutral_count = 0

        key_insights = []

        for name, indicator in indicators.items():
            if indicator.signal == "buy":
                buy_count += 1
            elif indicator.signal == "sell":
                sell_count += 1
            else:
                neutral_count += 1

        total = len(indicators)

        # 全体シグナルを判定
        if total == 0:
            overall = "neutral"
        elif buy_count > sell_count * 1.5:
            overall = "strong_buy"
        elif buy_count > sell_count:
            overall = "buy"
        elif sell_count > buy_count * 1.5:
            overall = "strong_sell"
        elif sell_count > buy_count:
            overall = "sell"
        else:
            overall = "neutral"

        # 重要な指標のインサイトを抽出
        key_indicator_names = ["rsi", "macd", "bollinger_bands", "ichimoku", "adx", "stochastic", "ma_cross"]
        for key in key_indicator_names:
            if key in indicators:
                ind = indicators[key]
                key_insights.append(f"- {ind.name}: {ind.description}")

        # サマリーテキスト生成
        signal_text = {
            "strong_buy": "強い買いシグナル",
            "buy": "買いシグナル優勢",
            "neutral": "中立（様子見）",
            "sell": "売りシグナル優勢",
            "strong_sell": "強い売りシグナル"
        }

        summary_text = f"""
【テクニカル分析サマリー】{ticker}

■ 総合判定: {signal_text.get(overall, '中立')}
  - 買いシグナル: {buy_count}個
  - 売りシグナル: {sell_count}個
  - 中立: {neutral_count}個
  - 分析指標数: {total}個

■ 主要指標の状況:
{chr(10).join(key_insights) if key_insights else '- データ不足'}

■ 投資判断の参考:
"""
        if overall == "strong_buy":
            summary_text += "複数の指標が買いシグナルを示しており、上昇の可能性が高いと考えられます。"
        elif overall == "buy":
            summary_text += "全体的に買い優勢ですが、一部の指標は注意を示しています。"
        elif overall == "strong_sell":
            summary_text += "複数の指標が売りシグナルを示しており、下落リスクに注意が必要です。"
        elif overall == "sell":
            summary_text += "全体的に売り優勢ですが、反発の可能性も残っています。"
        else:
            summary_text += "シグナルが混在しており、方向感が出るまで様子見が賢明です。"

        return IndicatorSummary(
            ticker=ticker,
            timestamp=datetime.now().isoformat(),
            total_indicators=total,
            buy_signals=buy_count,
            sell_signals=sell_count,
            neutral_signals=neutral_count,
            overall_signal=overall,
            indicators=indicators,
            summary_text=summary_text.strip()
        )


# シングルトンインスタンス
technical_indicator_service = TechnicalIndicatorService()
