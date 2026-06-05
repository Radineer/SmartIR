"""
センチメント分析API エンドポイント
FinGPT的アプローチによる市場センチメント分析
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from pydantic import BaseModel

from app.services.market_sentiment import (
    market_sentiment_analyzer,
    SentimentScore,
    MarketSentiment,
    SentimentHistory,
    TextAnalysisRequest,
)

router = APIRouter(prefix="/sentiment", tags=["sentiment"])


class SentimentResponse(BaseModel):
    """センチメントレスポンス"""
    success: bool
    data: Optional[SentimentScore] = None
    error: Optional[str] = None


class MarketSentimentResponse(BaseModel):
    """市場センチメントレスポンス"""
    success: bool
    data: Optional[MarketSentiment] = None
    error: Optional[str] = None


class SentimentHistoryResponse(BaseModel):
    """センチメント履歴レスポンス"""
    success: bool
    data: Optional[SentimentHistory] = None
    error: Optional[str] = None


class IrisCommentResponse(BaseModel):
    """イリスコメントレスポンス"""
    success: bool
    comment: Optional[str] = None
    sentiment: Optional[SentimentScore] = None
    error: Optional[str] = None


class AnalyzeTextRequest(BaseModel):
    """テキスト分析リクエスト"""
    text: str
    context: Optional[str] = None  # "ir", "news", "social"


class CombinedSentimentRequest(BaseModel):
    """統合センチメントリクエスト"""
    ticker: str
    ir_text: Optional[str] = None


@router.get("/{ticker}", response_model=SentimentResponse)
async def get_ticker_sentiment(
    ticker: str,
    days: int = Query(default=7, ge=1, le=30, description="分析対象期間（日数）")
):
    """
    銘柄のセンチメントを取得

    指定された銘柄のニュースベースのセンチメント分析結果を返します。

    Args:
        ticker: ティッカーシンボル（例: 7203.T, ^N225）
        days: 分析対象期間（1-30日、デフォルト: 7日）

    Returns:
        センチメントスコア（positive, negative, neutral, overall, confidence）

    Examples:
        - トヨタ: /api/sentiment/7203.T
        - 日経平均: /api/sentiment/^N225
    """
    try:
        sentiment = await market_sentiment_analyzer.analyze_news_sentiment(ticker, days)
        return SentimentResponse(success=True, data=sentiment)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sentiment analysis failed: {str(e)}")


@router.get("/{ticker}/history", response_model=SentimentHistoryResponse)
async def get_sentiment_history(
    ticker: str,
    days: int = Query(default=30, ge=1, le=90, description="取得期間（日数）")
):
    """
    センチメント履歴を取得

    指定された銘柄のセンチメントの時系列データを返します。

    Args:
        ticker: ティッカーシンボル
        days: 取得期間（1-90日、デフォルト: 30日）

    Returns:
        日次のセンチメントデータ配列

    Note:
        - 過去のセンチメントトレンドを可視化するために使用
        - データは推定値であり、実際の過去データではありません
    """
    try:
        history = await market_sentiment_analyzer.get_sentiment_history(ticker, days)
        return SentimentHistoryResponse(success=True, data=history)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sentiment history: {str(e)}")


@router.get("/market/overview", response_model=MarketSentimentResponse)
async def get_market_sentiment():
    """
    市場全体のセンチメントを取得

    日本株式市場全体の投資家心理を分析した結果を返します。

    Returns:
        市場センチメント情報
        - fear_greed_index: 恐怖・強欲指数（0-100）
        - market_mood: 市場ムード
        - description: 詳細説明
        - factors: 各種要因のスコア
    """
    try:
        sentiment = await market_sentiment_analyzer.calculate_fear_greed_index()
        return MarketSentimentResponse(success=True, data=sentiment)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get market sentiment: {str(e)}")


@router.get("/fear-greed", response_model=MarketSentimentResponse)
async def get_fear_greed_index():
    """
    恐怖強欲指数を取得

    CNN Fear & Greed Index に相当する日本市場版の指数を返します。

    Returns:
        恐怖・強欲指数
        - 0-20: 極度の恐怖
        - 21-40: 恐怖
        - 41-60: 中立
        - 61-80: 強欲
        - 81-100: 極度の強欲

    Note:
        以下の要素から計算されます:
        - ボラティリティ（VIX相当）
        - モメンタム（騰落率）
        - 出来高トレンド
        - 市場の幅（騰落銘柄数）
        - 投資家心理
    """
    try:
        sentiment = await market_sentiment_analyzer.calculate_fear_greed_index()
        return MarketSentimentResponse(success=True, data=sentiment)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get fear/greed index: {str(e)}")


@router.post("/analyze", response_model=SentimentResponse)
async def analyze_text_sentiment(request: AnalyzeTextRequest):
    """
    テキストのセンチメント分析

    任意のテキストを分析し、センチメントスコアを返します。

    Args:
        text: 分析対象テキスト
        context: コンテキスト（"ir", "news", "social"）

    Returns:
        センチメントスコア

    Examples:
        ```json
        {
            "text": "当社は増収増益を達成し、配当金を増額します。",
            "context": "ir"
        }
        ```

    Note:
        - context="ir": IR資料向けの詳細分析
        - context="news": ニュース記事向け分析
        - context="social": SNS投稿向け分析
    """
    try:
        if not request.text or len(request.text.strip()) == 0:
            return SentimentResponse(
                success=False,
                error="Text is required"
            )

        sentiment = await market_sentiment_analyzer.analyze_text_sentiment(
            request.text,
            request.context
        )
        return SentimentResponse(success=True, data=sentiment)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text analysis failed: {str(e)}")


@router.post("/analyze/ir", response_model=SentimentResponse)
async def analyze_ir_sentiment(request: AnalyzeTextRequest):
    """
    IR資料のセンチメント分析

    IR資料に特化した詳細なセンチメント分析を行います。

    Args:
        text: IR資料のテキスト

    Returns:
        詳細なセンチメントスコア
        - performance_sentiment: 業績に関するセンチメント
        - outlook_sentiment: 将来見通しに関するセンチメント
        - risk_level: リスクレベル
        - growth_signals: 成長シグナル
        - warning_signals: 警告シグナル

    Examples:
        ```json
        {
            "text": "第3四半期決算において、売上高は前年同期比15%増の500億円..."
        }
        ```
    """
    try:
        if not request.text or len(request.text.strip()) == 0:
            return SentimentResponse(
                success=False,
                error="Text is required"
            )

        sentiment = await market_sentiment_analyzer.analyze_ir_sentiment(request.text)
        return SentimentResponse(success=True, data=sentiment)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"IR analysis failed: {str(e)}")


@router.post("/combined", response_model=SentimentResponse)
async def get_combined_sentiment(request: CombinedSentimentRequest):
    """
    統合センチメントを取得

    ニュースとIR資料のセンチメントを統合した分析結果を返します。

    Args:
        ticker: ティッカーシンボル
        ir_text: IR資料のテキスト（オプション）

    Returns:
        統合センチメントスコア
        - source: "combined"
        - details: ニュースとIRそれぞれのセンチメント

    Note:
        IR資料が提供された場合:
        - IR: 60% の重み
        - ニュース: 40% の重み
    """
    try:
        sentiment = await market_sentiment_analyzer.get_combined_sentiment(
            request.ticker,
            request.ir_text
        )
        return SentimentResponse(success=True, data=sentiment)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Combined sentiment analysis failed: {str(e)}")


@router.get("/{ticker}/iris-comment", response_model=IrisCommentResponse)
async def get_iris_comment(
    ticker: str,
    days: int = Query(default=7, ge=1, le=30, description="分析対象期間（日数）")
):
    """
    イリス向けコメントを取得

    センチメント分析結果に基づいて、AIキャラクター「イリス」向けのコメントを生成します。

    Args:
        ticker: ティッカーシンボル
        days: 分析対象期間

    Returns:
        イリスのコメントとセンチメント情報

    Note:
        VTuber配信や動画コンテンツで使用するためのコメントを生成します。
    """
    try:
        sentiment = await market_sentiment_analyzer.analyze_news_sentiment(ticker, days)
        comment = market_sentiment_analyzer.generate_iris_comment(sentiment)

        return IrisCommentResponse(
            success=True,
            comment=comment,
            sentiment=sentiment
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate Iris comment: {str(e)}")
