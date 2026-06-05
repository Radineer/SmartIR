"""
テクニカル指標API
株価のテクニカル分析指標を提供するAPIエンドポイント
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import pandas as pd
import yfinance as yf
import logging

from app.services.technical_indicators import (
    technical_indicator_service,
    IndicatorResult,
    IndicatorSummary
)
from app.services.market_data import market_data_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/technical", tags=["technical"])


class CustomIndicatorRequest(BaseModel):
    """カスタム指標計算リクエスト"""
    ticker: str = Field(..., description="ティッカーシンボル")
    indicators: List[str] = Field(..., description="計算する指標のリスト")
    period: str = Field(default="6mo", description="データ取得期間")
    interval: str = Field(default="1d", description="データ間隔")


class IndicatorListResponse(BaseModel):
    """利用可能な指標一覧レスポンス"""
    total: int
    indicators: List[Dict[str, str]]


def get_ohlcv_dataframe(ticker: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """
    ティッカーからOHLCVデータをDataFrameで取得

    Args:
        ticker: ティッカーシンボル
        period: データ取得期間
        interval: データ間隔

    Returns:
        OHLCVデータを含むDataFrame
    """
    try:
        yf_ticker = yf.Ticker(ticker)
        df = yf_ticker.history(period=period, interval=interval)

        if df.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for ticker: {ticker}"
            )

        return df
    except Exception as e:
        logger.error(f"Error fetching data for {ticker}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch data for {ticker}: {str(e)}"
        )


@router.get("/indicators", response_model=IndicatorListResponse)
async def list_available_indicators():
    """
    利用可能なテクニカル指標の一覧を取得

    Returns:
        利用可能な指標のリスト
    """
    indicators = [
        {"name": "sma", "description": "単純移動平均 (Simple Moving Average)"},
        {"name": "ema", "description": "指数移動平均 (Exponential Moving Average)"},
        {"name": "wma", "description": "加重移動平均 (Weighted Moving Average)"},
        {"name": "dema", "description": "二重指数移動平均 (Double EMA)"},
        {"name": "tema", "description": "三重指数移動平均 (Triple EMA)"},
        {"name": "t3", "description": "T3移動平均"},
        {"name": "kama", "description": "カウフマン適応移動平均 (Kaufman Adaptive MA)"},
        {"name": "vwma", "description": "出来高加重移動平均 (Volume Weighted MA)"},
        {"name": "rsi", "description": "相対力指数 (Relative Strength Index)"},
        {"name": "macd", "description": "移動平均収束拡散 (MACD)"},
        {"name": "stochastic", "description": "ストキャスティクス"},
        {"name": "stochastic_rsi", "description": "ストキャスティクスRSI"},
        {"name": "williams_r", "description": "ウィリアムズ%R"},
        {"name": "cci", "description": "商品チャネル指数 (CCI)"},
        {"name": "roc", "description": "変化率 (Rate of Change)"},
        {"name": "momentum", "description": "モメンタム"},
        {"name": "ultimate_oscillator", "description": "アルティメットオシレーター"},
        {"name": "tsi", "description": "トゥルーストレングスインデックス"},
        {"name": "ppo", "description": "パーセンテージプライスオシレーター"},
        {"name": "dpo", "description": "ディトレンドプライスオシレーター"},
        {"name": "kst", "description": "KST"},
        {"name": "trix", "description": "TRIX"},
        {"name": "bollinger_bands", "description": "ボリンジャーバンド"},
        {"name": "atr", "description": "平均真の範囲 (Average True Range)"},
        {"name": "natr", "description": "正規化ATR"},
        {"name": "true_range", "description": "真の範囲"},
        {"name": "keltner_channel", "description": "ケルトナーチャネル"},
        {"name": "donchian_channel", "description": "ドンチャンチャネル"},
        {"name": "std", "description": "標準偏差"},
        {"name": "ulcer_index", "description": "アルサーインデックス"},
        {"name": "ichimoku", "description": "一目均衡表"},
        {"name": "adx", "description": "平均方向性指数 (ADX)"},
        {"name": "psar", "description": "パラボリックSAR"},
        {"name": "aroon", "description": "アルーン"},
        {"name": "obv", "description": "オンバランスボリューム (OBV)"},
        {"name": "vwap", "description": "出来高加重平均価格 (VWAP)"},
        {"name": "ad", "description": "蓄積/配布 (A/D)"},
        {"name": "cmf", "description": "チャイキンマネーフロー"},
        {"name": "mfi", "description": "マネーフローインデックス"},
        {"name": "force_index", "description": "フォースインデックス"},
        {"name": "eom", "description": "イーズオブムーブメント"},
        {"name": "volume_sma", "description": "出来高移動平均"},
        {"name": "nvi", "description": "ネガティブボリュームインデックス"},
        {"name": "pvi", "description": "ポジティブボリュームインデックス"},
        {"name": "price_vs_sma", "description": "価格対SMA乖離"},
        {"name": "ma_cross", "description": "移動平均クロス (ゴールデン/デッドクロス)"},
        {"name": "support_resistance", "description": "サポート/レジスタンス"},
        {"name": "pivot_points", "description": "ピボットポイント"},
        {"name": "average_price", "description": "平均価格"},
    ]

    return IndicatorListResponse(
        total=len(indicators),
        indicators=indicators
    )


@router.get("/{ticker}/all", response_model=IndicatorSummary)
async def get_all_indicators(
    ticker: str,
    period: str = Query(default="6mo", description="データ取得期間 (1mo, 3mo, 6mo, 1y, 2y)"),
    interval: str = Query(default="1d", description="データ間隔 (1d, 1wk)")
):
    """
    指定銘柄の全テクニカル指標を取得

    Args:
        ticker: ティッカーシンボル（例: 7203.T, AAPL, ^N225）
        period: データ取得期間
        interval: データ間隔

    Returns:
        全指標の計算結果とサマリー
    """
    df = get_ohlcv_dataframe(ticker, period, interval)
    indicators = technical_indicator_service.calculate_all_indicators(df)
    summary = technical_indicator_service.generate_summary(indicators, ticker)

    return summary


@router.get("/{ticker}/rsi", response_model=IndicatorResult)
async def get_rsi(
    ticker: str,
    period: int = Query(default=14, description="RSI計算期間"),
    data_period: str = Query(default="3mo", description="データ取得期間")
):
    """
    RSI (相対力指数) を取得

    Args:
        ticker: ティッカーシンボル
        period: RSI計算期間（デフォルト14）
        data_period: データ取得期間

    Returns:
        RSIの計算結果
    """
    df = get_ohlcv_dataframe(ticker, data_period)
    result = technical_indicator_service.calculate_rsi(df, period)

    if result is None:
        raise HTTPException(status_code=500, detail="Failed to calculate RSI")

    return result


@router.get("/{ticker}/macd", response_model=IndicatorResult)
async def get_macd(
    ticker: str,
    fast: int = Query(default=12, description="短期EMA期間"),
    slow: int = Query(default=26, description="長期EMA期間"),
    signal: int = Query(default=9, description="シグナル期間"),
    data_period: str = Query(default="3mo", description="データ取得期間")
):
    """
    MACD (移動平均収束拡散) を取得

    Args:
        ticker: ティッカーシンボル
        fast: 短期EMA期間
        slow: 長期EMA期間
        signal: シグナル期間
        data_period: データ取得期間

    Returns:
        MACDの計算結果
    """
    df = get_ohlcv_dataframe(ticker, data_period)
    result = technical_indicator_service.calculate_macd(df, fast, slow, signal)

    if result is None:
        raise HTTPException(status_code=500, detail="Failed to calculate MACD")

    return result


@router.get("/{ticker}/bollinger", response_model=IndicatorResult)
async def get_bollinger_bands(
    ticker: str,
    period: int = Query(default=20, description="移動平均期間"),
    std: float = Query(default=2.0, description="標準偏差倍率"),
    data_period: str = Query(default="3mo", description="データ取得期間")
):
    """
    ボリンジャーバンドを取得

    Args:
        ticker: ティッカーシンボル
        period: 移動平均期間
        std: 標準偏差倍率
        data_period: データ取得期間

    Returns:
        ボリンジャーバンドの計算結果
    """
    df = get_ohlcv_dataframe(ticker, data_period)
    result = technical_indicator_service.calculate_bollinger_bands(df, period, std)

    if result is None:
        raise HTTPException(status_code=500, detail="Failed to calculate Bollinger Bands")

    return result


@router.get("/{ticker}/atr", response_model=IndicatorResult)
async def get_atr(
    ticker: str,
    period: int = Query(default=14, description="ATR計算期間"),
    data_period: str = Query(default="3mo", description="データ取得期間")
):
    """
    ATR (Average True Range) を取得

    Args:
        ticker: ティッカーシンボル
        period: ATR計算期間
        data_period: データ取得期間

    Returns:
        ATRの計算結果
    """
    df = get_ohlcv_dataframe(ticker, data_period)
    result = technical_indicator_service.calculate_atr(df, period)

    if result is None:
        raise HTTPException(status_code=500, detail="Failed to calculate ATR")

    return result


@router.get("/{ticker}/stochastic", response_model=IndicatorResult)
async def get_stochastic(
    ticker: str,
    k: int = Query(default=14, description="%K期間"),
    d: int = Query(default=3, description="%D期間"),
    smooth_k: int = Query(default=3, description="%Kスムージング"),
    data_period: str = Query(default="3mo", description="データ取得期間")
):
    """
    ストキャスティクスを取得

    Args:
        ticker: ティッカーシンボル
        k: %K期間
        d: %D期間
        smooth_k: %Kスムージング
        data_period: データ取得期間

    Returns:
        ストキャスティクスの計算結果
    """
    df = get_ohlcv_dataframe(ticker, data_period)
    result = technical_indicator_service.calculate_stochastic(df, k, d, smooth_k)

    if result is None:
        raise HTTPException(status_code=500, detail="Failed to calculate Stochastic")

    return result


@router.get("/{ticker}/ichimoku", response_model=IndicatorResult)
async def get_ichimoku(
    ticker: str,
    data_period: str = Query(default="6mo", description="データ取得期間")
):
    """
    一目均衡表を取得

    Args:
        ticker: ティッカーシンボル
        data_period: データ取得期間

    Returns:
        一目均衡表の計算結果
    """
    df = get_ohlcv_dataframe(ticker, data_period)
    result = technical_indicator_service.calculate_ichimoku(df)

    if result is None:
        raise HTTPException(status_code=500, detail="Failed to calculate Ichimoku")

    return result


@router.get("/{ticker}/adx", response_model=IndicatorResult)
async def get_adx(
    ticker: str,
    period: int = Query(default=14, description="ADX計算期間"),
    data_period: str = Query(default="3mo", description="データ取得期間")
):
    """
    ADX (Average Directional Index) を取得

    Args:
        ticker: ティッカーシンボル
        period: ADX計算期間
        data_period: データ取得期間

    Returns:
        ADXの計算結果
    """
    df = get_ohlcv_dataframe(ticker, data_period)
    result = technical_indicator_service.calculate_adx(df, period)

    if result is None:
        raise HTTPException(status_code=500, detail="Failed to calculate ADX")

    return result


@router.get("/{ticker}/obv", response_model=IndicatorResult)
async def get_obv(
    ticker: str,
    data_period: str = Query(default="3mo", description="データ取得期間")
):
    """
    OBV (On Balance Volume) を取得

    Args:
        ticker: ティッカーシンボル
        data_period: データ取得期間

    Returns:
        OBVの計算結果
    """
    df = get_ohlcv_dataframe(ticker, data_period)
    result = technical_indicator_service.calculate_obv(df)

    if result is None:
        raise HTTPException(status_code=500, detail="Failed to calculate OBV")

    return result


@router.get("/{ticker}/sma", response_model=List[IndicatorResult])
async def get_sma(
    ticker: str,
    periods: str = Query(default="5,10,20,50,200", description="計算期間（カンマ区切り）"),
    data_period: str = Query(default="1y", description="データ取得期間")
):
    """
    SMA (単純移動平均) を取得

    Args:
        ticker: ティッカーシンボル
        periods: 計算期間（カンマ区切り）
        data_period: データ取得期間

    Returns:
        SMAの計算結果リスト
    """
    df = get_ohlcv_dataframe(ticker, data_period)
    period_list = [int(p.strip()) for p in periods.split(",")]
    results = technical_indicator_service.calculate_sma(df, period_list)

    if not results:
        raise HTTPException(status_code=500, detail="Failed to calculate SMA")

    return results


@router.get("/{ticker}/ema", response_model=List[IndicatorResult])
async def get_ema(
    ticker: str,
    periods: str = Query(default="5,10,20,50,200", description="計算期間（カンマ区切り）"),
    data_period: str = Query(default="1y", description="データ取得期間")
):
    """
    EMA (指数移動平均) を取得

    Args:
        ticker: ティッカーシンボル
        periods: 計算期間（カンマ区切り）
        data_period: データ取得期間

    Returns:
        EMAの計算結果リスト
    """
    df = get_ohlcv_dataframe(ticker, data_period)
    period_list = [int(p.strip()) for p in periods.split(",")]
    results = technical_indicator_service.calculate_ema(df, period_list)

    if not results:
        raise HTTPException(status_code=500, detail="Failed to calculate EMA")

    return results


@router.get("/{ticker}/summary", response_model=IndicatorSummary)
async def get_summary(
    ticker: str,
    period: str = Query(default="6mo", description="データ取得期間")
):
    """
    イリス向けテクニカル分析サマリーを取得

    Args:
        ticker: ティッカーシンボル
        period: データ取得期間

    Returns:
        テクニカル分析のサマリー（AIVtuber用）
    """
    df = get_ohlcv_dataframe(ticker, period)
    indicators = technical_indicator_service.calculate_all_indicators(df)
    summary = technical_indicator_service.generate_summary(indicators, ticker)

    return summary


@router.post("/calculate", response_model=Dict[str, IndicatorResult])
async def calculate_custom_indicators(request: CustomIndicatorRequest):
    """
    カスタム指標を計算

    リクエストボディで指定した指標のみを計算して返す

    Args:
        request: カスタム指標計算リクエスト

    Returns:
        指定された指標の計算結果
    """
    df = get_ohlcv_dataframe(request.ticker, request.period, request.interval)

    # 指標名とメソッドのマッピング
    indicator_methods = {
        "rsi": lambda: technical_indicator_service.calculate_rsi(df),
        "macd": lambda: technical_indicator_service.calculate_macd(df),
        "bollinger_bands": lambda: technical_indicator_service.calculate_bollinger_bands(df),
        "atr": lambda: technical_indicator_service.calculate_atr(df),
        "stochastic": lambda: technical_indicator_service.calculate_stochastic(df),
        "ichimoku": lambda: technical_indicator_service.calculate_ichimoku(df),
        "adx": lambda: technical_indicator_service.calculate_adx(df),
        "obv": lambda: technical_indicator_service.calculate_obv(df),
        "williams_r": lambda: technical_indicator_service.calculate_williams_r(df),
        "cci": lambda: technical_indicator_service.calculate_cci(df),
        "roc": lambda: technical_indicator_service.calculate_roc(df),
        "momentum": lambda: technical_indicator_service.calculate_momentum(df),
        "ultimate_oscillator": lambda: technical_indicator_service.calculate_ultimate_oscillator(df),
        "tsi": lambda: technical_indicator_service.calculate_tsi(df),
        "keltner_channel": lambda: technical_indicator_service.calculate_keltner_channel(df),
        "donchian_channel": lambda: technical_indicator_service.calculate_donchian_channel(df),
        "vwap": lambda: technical_indicator_service.calculate_vwap(df),
        "ad": lambda: technical_indicator_service.calculate_ad(df),
        "cmf": lambda: technical_indicator_service.calculate_cmf(df),
        "mfi": lambda: technical_indicator_service.calculate_mfi(df),
        "force_index": lambda: technical_indicator_service.calculate_force_index(df),
        "eom": lambda: technical_indicator_service.calculate_eom(df),
        "volume_sma": lambda: technical_indicator_service.calculate_volume_sma(df),
        "dema": lambda: technical_indicator_service.calculate_dema(df),
        "tema": lambda: technical_indicator_service.calculate_tema(df),
        "t3": lambda: technical_indicator_service.calculate_t3(df),
        "kama": lambda: technical_indicator_service.calculate_kama(df),
        "psar": lambda: technical_indicator_service.calculate_parabolic_sar(df),
        "aroon": lambda: technical_indicator_service.calculate_aroon(df),
        "stochastic_rsi": lambda: technical_indicator_service.calculate_stochastic_rsi(df),
        "ppo": lambda: technical_indicator_service.calculate_ppo(df),
        "dpo": lambda: technical_indicator_service.calculate_dpo(df),
        "kst": lambda: technical_indicator_service.calculate_kst(df),
        "trix": lambda: technical_indicator_service.calculate_trix(df),
        "ulcer_index": lambda: technical_indicator_service.calculate_ulcer_index(df),
        "natr": lambda: technical_indicator_service.calculate_natr(df),
        "true_range": lambda: technical_indicator_service.calculate_true_range(df),
        "nvi": lambda: technical_indicator_service.calculate_nvi(df),
        "pvi": lambda: technical_indicator_service.calculate_pvi(df),
        "vwma": lambda: technical_indicator_service.calculate_vwma(df),
        "price_vs_sma": lambda: technical_indicator_service.calculate_price_vs_sma(df),
        "ma_cross": lambda: technical_indicator_service.calculate_ma_cross(df),
        "support_resistance": lambda: technical_indicator_service.calculate_support_resistance(df),
        "pivot_points": lambda: technical_indicator_service.calculate_pivot_points(df),
        "average_price": lambda: technical_indicator_service.calculate_average_price(df),
    }

    results = {}
    for indicator_name in request.indicators:
        indicator_key = indicator_name.lower().replace("-", "_")
        if indicator_key in indicator_methods:
            result = indicator_methods[indicator_key]()
            if result:
                results[indicator_key] = result
        else:
            logger.warning(f"Unknown indicator requested: {indicator_name}")

    if not results:
        raise HTTPException(
            status_code=400,
            detail=f"No valid indicators found. Available indicators: {list(indicator_methods.keys())}"
        )

    return results


@router.get("/{ticker}/trend", response_model=Dict[str, Any])
async def get_trend_analysis(
    ticker: str,
    period: str = Query(default="6mo", description="データ取得期間")
):
    """
    トレンド分析を取得

    移動平均系の指標を中心にトレンドを分析

    Args:
        ticker: ティッカーシンボル
        period: データ取得期間

    Returns:
        トレンド分析結果
    """
    df = get_ohlcv_dataframe(ticker, period)

    trend_indicators = {}

    # 移動平均
    for p in [20, 50, 200]:
        sma = technical_indicator_service.calculate_sma_single(df, p)
        ema = technical_indicator_service.calculate_ema_single(df, p)
        if sma:
            trend_indicators[f"sma_{p}"] = sma
        if ema:
            trend_indicators[f"ema_{p}"] = ema

    # その他のトレンド指標
    adx = technical_indicator_service.calculate_adx(df)
    if adx:
        trend_indicators["adx"] = adx

    ichimoku = technical_indicator_service.calculate_ichimoku(df)
    if ichimoku:
        trend_indicators["ichimoku"] = ichimoku

    psar = technical_indicator_service.calculate_parabolic_sar(df)
    if psar:
        trend_indicators["psar"] = psar

    ma_cross = technical_indicator_service.calculate_ma_cross(df)
    if ma_cross:
        trend_indicators["ma_cross"] = ma_cross

    # トレンド判定
    buy_count = sum(1 for ind in trend_indicators.values() if ind.signal == "buy")
    sell_count = sum(1 for ind in trend_indicators.values() if ind.signal == "sell")

    if buy_count > sell_count * 1.5:
        trend = "strong_uptrend"
        trend_text = "強い上昇トレンド"
    elif buy_count > sell_count:
        trend = "uptrend"
        trend_text = "上昇トレンド"
    elif sell_count > buy_count * 1.5:
        trend = "strong_downtrend"
        trend_text = "強い下降トレンド"
    elif sell_count > buy_count:
        trend = "downtrend"
        trend_text = "下降トレンド"
    else:
        trend = "sideways"
        trend_text = "横ばい（レンジ）"

    return {
        "ticker": ticker,
        "trend": trend,
        "trend_text": trend_text,
        "buy_signals": buy_count,
        "sell_signals": sell_count,
        "indicators": trend_indicators
    }


@router.get("/{ticker}/momentum", response_model=Dict[str, Any])
async def get_momentum_analysis(
    ticker: str,
    period: str = Query(default="3mo", description="データ取得期間")
):
    """
    モメンタム分析を取得

    オシレーター系の指標を中心にモメンタムを分析

    Args:
        ticker: ティッカーシンボル
        period: データ取得期間

    Returns:
        モメンタム分析結果
    """
    df = get_ohlcv_dataframe(ticker, period)

    momentum_indicators = {}

    rsi = technical_indicator_service.calculate_rsi(df)
    if rsi:
        momentum_indicators["rsi"] = rsi

    macd = technical_indicator_service.calculate_macd(df)
    if macd:
        momentum_indicators["macd"] = macd

    stoch = technical_indicator_service.calculate_stochastic(df)
    if stoch:
        momentum_indicators["stochastic"] = stoch

    willr = technical_indicator_service.calculate_williams_r(df)
    if willr:
        momentum_indicators["williams_r"] = willr

    cci = technical_indicator_service.calculate_cci(df)
    if cci:
        momentum_indicators["cci"] = cci

    roc = technical_indicator_service.calculate_roc(df)
    if roc:
        momentum_indicators["roc"] = roc

    mom = technical_indicator_service.calculate_momentum(df)
    if mom:
        momentum_indicators["momentum"] = mom

    # モメンタム判定
    buy_count = sum(1 for ind in momentum_indicators.values() if ind.signal == "buy")
    sell_count = sum(1 for ind in momentum_indicators.values() if ind.signal == "sell")

    if buy_count >= 4:
        momentum = "strong_bullish"
        momentum_text = "強い強気モメンタム"
    elif buy_count > sell_count:
        momentum = "bullish"
        momentum_text = "強気モメンタム"
    elif sell_count >= 4:
        momentum = "strong_bearish"
        momentum_text = "強い弱気モメンタム"
    elif sell_count > buy_count:
        momentum = "bearish"
        momentum_text = "弱気モメンタム"
    else:
        momentum = "neutral"
        momentum_text = "中立"

    return {
        "ticker": ticker,
        "momentum": momentum,
        "momentum_text": momentum_text,
        "buy_signals": buy_count,
        "sell_signals": sell_count,
        "indicators": momentum_indicators
    }


@router.get("/{ticker}/volatility", response_model=Dict[str, Any])
async def get_volatility_analysis(
    ticker: str,
    period: str = Query(default="3mo", description="データ取得期間")
):
    """
    ボラティリティ分析を取得

    ボラティリティ系の指標を中心に分析

    Args:
        ticker: ティッカーシンボル
        period: データ取得期間

    Returns:
        ボラティリティ分析結果
    """
    df = get_ohlcv_dataframe(ticker, period)

    volatility_indicators = {}

    bb = technical_indicator_service.calculate_bollinger_bands(df)
    if bb:
        volatility_indicators["bollinger_bands"] = bb

    atr = technical_indicator_service.calculate_atr(df)
    if atr:
        volatility_indicators["atr"] = atr

    natr = technical_indicator_service.calculate_natr(df)
    if natr:
        volatility_indicators["natr"] = natr

    kc = technical_indicator_service.calculate_keltner_channel(df)
    if kc:
        volatility_indicators["keltner_channel"] = kc

    dc = technical_indicator_service.calculate_donchian_channel(df)
    if dc:
        volatility_indicators["donchian_channel"] = dc

    std = technical_indicator_service.calculate_std(df)
    if std:
        volatility_indicators["std"] = std

    ui = technical_indicator_service.calculate_ulcer_index(df)
    if ui:
        volatility_indicators["ulcer_index"] = ui

    # ボラティリティ判定
    natr_value = natr.value if natr else 0

    if natr_value >= 5:
        volatility = "very_high"
        volatility_text = "非常に高いボラティリティ"
    elif natr_value >= 3:
        volatility = "high"
        volatility_text = "高いボラティリティ"
    elif natr_value >= 1.5:
        volatility = "moderate"
        volatility_text = "中程度のボラティリティ"
    elif natr_value >= 0.5:
        volatility = "low"
        volatility_text = "低いボラティリティ"
    else:
        volatility = "very_low"
        volatility_text = "非常に低いボラティリティ"

    return {
        "ticker": ticker,
        "volatility": volatility,
        "volatility_text": volatility_text,
        "natr_percent": natr_value,
        "indicators": volatility_indicators
    }
