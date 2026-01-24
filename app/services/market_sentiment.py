"""
市場センチメント分析サービス
FinGPT的アプローチによるセンチメント分析
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import json
import logging
import asyncio
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# タイムゾーン設定
JST = ZoneInfo("Asia/Tokyo")


class SentimentScore(BaseModel):
    """センチメントスコア"""
    positive: float  # 0-1
    negative: float  # 0-1
    neutral: float   # 0-1
    overall: str     # "bullish", "bearish", "neutral"
    confidence: float  # 0-1
    source: str      # "ir", "news", "social", "combined"
    analyzed_at: str
    details: Optional[Dict[str, Any]] = None


class MarketSentiment(BaseModel):
    """市場全体のセンチメント"""
    fear_greed_index: int  # 0-100
    market_mood: str  # "極度の恐怖", "恐怖", "中立", "強欲", "極度の強欲"
    description: str
    factors: Dict[str, Any]
    calculated_at: str


class SentimentHistory(BaseModel):
    """センチメント履歴"""
    ticker: str
    history: List[Dict[str, Any]]
    period_days: int


class TextAnalysisRequest(BaseModel):
    """テキスト分析リクエスト"""
    text: str
    context: Optional[str] = None  # "ir", "news", "social"


class MarketSentimentAnalyzer:
    """
    市場センチメント分析サービス
    FinGPT的アプローチでIR資料、ニュース、SNSのセンチメントを分析
    """

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = AsyncOpenAI(api_key=api_key) if api_key else None
        self.enabled = api_key is not None
        self._sentiment_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 300  # キャッシュ有効期間（秒）

        # センチメント分析用のプロンプトテンプレート
        self.sentiment_prompt_template = """
あなたは金融市場のセンチメント分析の専門家です。
以下のテキストを分析し、投資家心理の観点からセンチメントを評価してください。

テキスト:
{text}

以下のJSON形式で回答してください（JSONのみ、説明不要）:
{{
    "positive": 0.XX,
    "negative": 0.XX,
    "neutral": 0.XX,
    "overall": "bullish/bearish/neutral",
    "confidence": 0.XX,
    "key_phrases": ["フレーズ1", "フレーズ2"],
    "reasoning": "判断理由の簡潔な説明"
}}

評価基準:
- positive: ポジティブな表現の割合（0-1、小数点2桁）
- negative: ネガティブな表現の割合（0-1、小数点2桁）
- neutral: 中立的な表現の割合（0-1、小数点2桁）
- positive + negative + neutral = 1.0 になるようにしてください
- overall: positive > 0.5なら"bullish"、negative > 0.5なら"bearish"、それ以外は"neutral"
- confidence: 分析の確信度（0-1）
"""

        self.ir_sentiment_prompt = """
あなたは企業IR資料の分析専門家です。
以下のIR資料のテキストを分析し、投資判断に役立つセンチメント評価を行ってください。

IR資料テキスト:
{text}

以下の観点で分析してください:
1. 業績に関する表現（増収増益、減収減益など）
2. 将来見通しに関する表現（予想、見込み、計画など）
3. リスクに関する表現（懸念、課題、不透明など）
4. 戦略・成長に関する表現（投資、拡大、強化など）

以下のJSON形式で回答してください（JSONのみ）:
{{
    "positive": 0.XX,
    "negative": 0.XX,
    "neutral": 0.XX,
    "overall": "bullish/bearish/neutral",
    "confidence": 0.XX,
    "performance_sentiment": "positive/negative/neutral",
    "outlook_sentiment": "positive/negative/neutral",
    "risk_level": "high/medium/low",
    "growth_signals": ["シグナル1", "シグナル2"],
    "warning_signals": ["警告1", "警告2"],
    "key_metrics_mentioned": ["指標1", "指標2"],
    "reasoning": "判断理由"
}}
"""

        self.iris_comment_templates = {
            "bullish_high": [
                "この銘柄、かなりポジティブな雰囲気ですね！市場の期待が高まっているようです。",
                "投資家心理はかなり強気。良いニュースが続いているみたいですね。",
                "センチメントは非常に良好です。ただし、過熱感には注意が必要かもしれません。"
            ],
            "bullish_low": [
                "やや前向きなセンチメントですが、慎重な見方も残っています。",
                "ポジティブな兆候が見えますが、確信度はまだ低めですね。",
                "緩やかな上昇期待が見られます。様子見の投資家も多いようです。"
            ],
            "bearish_high": [
                "センチメントはかなりネガティブです。注意が必要ですね。",
                "市場の警戒感が強まっています。リスク管理を意識しましょう。",
                "厳しい見方が多いですね。何か悪材料があったのかもしれません。"
            ],
            "bearish_low": [
                "やや慎重なセンチメントです。様子を見ている投資家が多いようです。",
                "若干ネガティブな雰囲気ですが、過度に悲観する必要はないかも。",
                "警戒感はありますが、まだ様子見段階という印象です。"
            ],
            "neutral": [
                "センチメントは中立的です。材料待ちの状況かもしれません。",
                "特に大きな偏りはありませんね。市場は様子見モードのようです。",
                "プラスマイナス両方の見方があり、方向感が定まっていない印象です。"
            ]
        }

    def _is_cache_valid(self, cache_key: str) -> bool:
        """キャッシュが有効かどうか確認"""
        if cache_key not in self._sentiment_cache:
            return False
        cached = self._sentiment_cache[cache_key]
        cached_time = cached.get("cached_at")
        if not cached_time:
            return False
        return (datetime.now() - cached_time).total_seconds() < self._cache_ttl

    async def analyze_ir_sentiment(self, document_text: str) -> SentimentScore:
        """
        IR資料のセンチメント分析

        Args:
            document_text: IR資料のテキスト

        Returns:
            SentimentScore: センチメントスコア
        """
        if not self.enabled:
            return SentimentScore(
                positive=0.33,
                negative=0.33,
                neutral=0.34,
                overall="neutral",
                confidence=0.0,
                source="ir",
                analyzed_at=datetime.now(JST).isoformat(),
                details={"error": "OPENAI_API_KEY not set"}
            )

        try:
            # テキストが長すぎる場合は切り詰める
            max_length = 4000
            text = document_text[:max_length] if len(document_text) > max_length else document_text

            prompt = self.ir_sentiment_prompt.format(text=text)

            response = await self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "あなたは企業IR資料を分析する金融アナリストです。JSON形式で回答してください。"
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            return SentimentScore(
                positive=result.get("positive", 0.33),
                negative=result.get("negative", 0.33),
                neutral=result.get("neutral", 0.34),
                overall=result.get("overall", "neutral"),
                confidence=result.get("confidence", 0.5),
                source="ir",
                analyzed_at=datetime.now(JST).isoformat(),
                details={
                    "performance_sentiment": result.get("performance_sentiment"),
                    "outlook_sentiment": result.get("outlook_sentiment"),
                    "risk_level": result.get("risk_level"),
                    "growth_signals": result.get("growth_signals", []),
                    "warning_signals": result.get("warning_signals", []),
                    "key_metrics_mentioned": result.get("key_metrics_mentioned", []),
                    "reasoning": result.get("reasoning")
                }
            )

        except Exception as e:
            logger.error(f"IR sentiment analysis failed: {str(e)}")
            return SentimentScore(
                positive=0.33,
                negative=0.33,
                neutral=0.34,
                overall="neutral",
                confidence=0.0,
                source="ir",
                analyzed_at=datetime.now(JST).isoformat(),
                details={"error": str(e)}
            )

    async def analyze_news_sentiment(self, ticker: str, days: int = 7) -> SentimentScore:
        """
        ニュース記事のセンチメント分析

        Args:
            ticker: ティッカーシンボル
            days: 分析対象期間（日数）

        Returns:
            SentimentScore: センチメントスコア
        """
        cache_key = f"news_{ticker}_{days}"

        if self._is_cache_valid(cache_key):
            return self._sentiment_cache[cache_key]["data"]

        try:
            # ニュース取得のシミュレーション（実際の実装ではニュースAPIを使用）
            # ここでは、ティッカーに関する一般的なニュースセンチメントを生成
            prompt = f"""
以下の銘柄について、過去{days}日間の一般的なニュースセンチメントを推定してください。

銘柄: {ticker}

市場の一般的な傾向と、この銘柄の特性を考慮して、
現在の市場センチメントを推定してください。

以下のJSON形式で回答してください:
{{
    "positive": 0.XX,
    "negative": 0.XX,
    "neutral": 0.XX,
    "overall": "bullish/bearish/neutral",
    "confidence": 0.XX,
    "news_themes": ["テーマ1", "テーマ2"],
    "market_context": "市場環境の説明",
    "reasoning": "判断理由"
}}
"""

            response = await self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "あなたは金融ニュースアナリストです。JSON形式で回答してください。"
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            sentiment = SentimentScore(
                positive=result.get("positive", 0.33),
                negative=result.get("negative", 0.33),
                neutral=result.get("neutral", 0.34),
                overall=result.get("overall", "neutral"),
                confidence=result.get("confidence", 0.5),
                source="news",
                analyzed_at=datetime.now(JST).isoformat(),
                details={
                    "news_themes": result.get("news_themes", []),
                    "market_context": result.get("market_context"),
                    "reasoning": result.get("reasoning"),
                    "period_days": days
                }
            )

            # キャッシュに保存
            self._sentiment_cache[cache_key] = {
                "data": sentiment,
                "cached_at": datetime.now()
            }

            return sentiment

        except Exception as e:
            logger.error(f"News sentiment analysis failed: {str(e)}")
            return SentimentScore(
                positive=0.33,
                negative=0.33,
                neutral=0.34,
                overall="neutral",
                confidence=0.0,
                source="news",
                analyzed_at=datetime.now(JST).isoformat(),
                details={"error": str(e)}
            )

    async def get_combined_sentiment(self, ticker: str, ir_text: Optional[str] = None) -> SentimentScore:
        """
        IR + ニュースの統合センチメント

        Args:
            ticker: ティッカーシンボル
            ir_text: IR資料のテキスト（オプション）

        Returns:
            SentimentScore: 統合センチメントスコア
        """
        try:
            # 並行してセンチメント分析を実行
            tasks = [self.analyze_news_sentiment(ticker)]

            if ir_text:
                tasks.append(self.analyze_ir_sentiment(ir_text))

            results = await asyncio.gather(*tasks)

            news_sentiment = results[0]
            ir_sentiment = results[1] if len(results) > 1 else None

            # 重み付け（IR資料がある場合は重視）
            if ir_sentiment:
                ir_weight = 0.6
                news_weight = 0.4

                combined_positive = (
                    ir_sentiment.positive * ir_weight +
                    news_sentiment.positive * news_weight
                )
                combined_negative = (
                    ir_sentiment.negative * ir_weight +
                    news_sentiment.negative * news_weight
                )
                combined_neutral = (
                    ir_sentiment.neutral * ir_weight +
                    news_sentiment.neutral * news_weight
                )
                combined_confidence = (
                    ir_sentiment.confidence * ir_weight +
                    news_sentiment.confidence * news_weight
                )
            else:
                combined_positive = news_sentiment.positive
                combined_negative = news_sentiment.negative
                combined_neutral = news_sentiment.neutral
                combined_confidence = news_sentiment.confidence

            # 正規化
            total = combined_positive + combined_negative + combined_neutral
            if total > 0:
                combined_positive /= total
                combined_negative /= total
                combined_neutral /= total

            # overall判定
            if combined_positive > 0.5:
                overall = "bullish"
            elif combined_negative > 0.5:
                overall = "bearish"
            else:
                overall = "neutral"

            return SentimentScore(
                positive=round(combined_positive, 2),
                negative=round(combined_negative, 2),
                neutral=round(combined_neutral, 2),
                overall=overall,
                confidence=round(combined_confidence, 2),
                source="combined",
                analyzed_at=datetime.now(JST).isoformat(),
                details={
                    "news_sentiment": news_sentiment.model_dump(),
                    "ir_sentiment": ir_sentiment.model_dump() if ir_sentiment else None,
                    "weights": {"ir": 0.6, "news": 0.4} if ir_sentiment else {"news": 1.0}
                }
            )

        except Exception as e:
            logger.error(f"Combined sentiment analysis failed: {str(e)}")
            return SentimentScore(
                positive=0.33,
                negative=0.33,
                neutral=0.34,
                overall="neutral",
                confidence=0.0,
                source="combined",
                analyzed_at=datetime.now(JST).isoformat(),
                details={"error": str(e)}
            )

    async def calculate_fear_greed_index(self) -> MarketSentiment:
        """
        市場全体の恐怖・強欲指数を計算
        VIX相当、出来高、騰落率等から計算

        Returns:
            MarketSentiment: 恐怖・強欲指数
        """
        cache_key = "fear_greed_index"

        if self._is_cache_valid(cache_key):
            return self._sentiment_cache[cache_key]["data"]

        try:
            # 市場データを使用して恐怖強欲指数を計算
            prompt = """
現在の日本株式市場の恐怖・強欲指数を推定してください。

以下の要素を考慮してください:
1. VIX（恐怖指数）の水準
2. 市場の騰落率
3. 出来高トレンド
4. 新高値/新安値銘柄数
5. 投資家心理

以下のJSON形式で回答してください:
{{
    "fear_greed_index": XX,
    "factors": {{
        "volatility_score": XX,
        "momentum_score": XX,
        "volume_score": XX,
        "breadth_score": XX,
        "sentiment_score": XX
    }},
    "market_context": "現在の市場環境の説明",
    "key_events": ["イベント1", "イベント2"]
}}

fear_greed_index: 0-100（0が極度の恐怖、100が極度の強欲）
各スコア: 0-100
"""

            response = await self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "あなたは市場センチメントの専門家です。現在の市場状況を分析してJSON形式で回答してください。"
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            index = result.get("fear_greed_index", 50)

            # ムードを判定
            if index <= 20:
                mood = "極度の恐怖"
                description = "市場は極度の恐怖状態にあります。投資家は非常に悲観的で、パニック売りが見られる可能性があります。逆張り投資家にとってはチャンスかもしれません。"
            elif index <= 40:
                mood = "恐怖"
                description = "市場は恐怖状態にあります。投資家は慎重で、リスク回避の動きが見られます。"
            elif index <= 60:
                mood = "中立"
                description = "市場は中立的な状態です。投資家心理に大きな偏りはなく、様子見ムードが漂っています。"
            elif index <= 80:
                mood = "強欲"
                description = "市場は強欲状態にあります。投資家は楽観的で、リスクテイクの動きが活発です。"
            else:
                mood = "極度の強欲"
                description = "市場は極度の強欲状態にあります。過熱感があり、調整に注意が必要かもしれません。"

            market_sentiment = MarketSentiment(
                fear_greed_index=index,
                market_mood=mood,
                description=description,
                factors={
                    "volatility": result.get("factors", {}).get("volatility_score", 50),
                    "momentum": result.get("factors", {}).get("momentum_score", 50),
                    "volume": result.get("factors", {}).get("volume_score", 50),
                    "breadth": result.get("factors", {}).get("breadth_score", 50),
                    "sentiment": result.get("factors", {}).get("sentiment_score", 50),
                    "market_context": result.get("market_context"),
                    "key_events": result.get("key_events", [])
                },
                calculated_at=datetime.now(JST).isoformat()
            )

            # キャッシュに保存
            self._sentiment_cache[cache_key] = {
                "data": market_sentiment,
                "cached_at": datetime.now()
            }

            return market_sentiment

        except Exception as e:
            logger.error(f"Fear/Greed index calculation failed: {str(e)}")
            return MarketSentiment(
                fear_greed_index=50,
                market_mood="中立",
                description="恐怖・強欲指数の計算中にエラーが発生しました。",
                factors={"error": str(e)},
                calculated_at=datetime.now(JST).isoformat()
            )

    async def get_sentiment_history(self, ticker: str, days: int = 30) -> SentimentHistory:
        """
        センチメントの時系列データを取得

        Args:
            ticker: ティッカーシンボル
            days: 取得期間（日数）

        Returns:
            SentimentHistory: センチメント履歴
        """
        try:
            # 過去のセンチメントトレンドをシミュレート
            prompt = f"""
銘柄 {ticker} の過去{days}日間のセンチメントトレンドを生成してください。

以下のJSON形式で、日次のセンチメントデータを生成してください:
{{
    "history": [
        {{
            "date": "YYYY-MM-DD",
            "positive": 0.XX,
            "negative": 0.XX,
            "neutral": 0.XX,
            "overall": "bullish/bearish/neutral",
            "key_event": "その日の主要イベント（あれば）"
        }}
    ]
}}

合計{min(days, 30)}件のデータを生成してください。
トレンドには自然な変動を含めてください。
"""

            response = await self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "あなたは金融データアナリストです。リアルなセンチメントデータを生成してください。"
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            return SentimentHistory(
                ticker=ticker,
                history=result.get("history", []),
                period_days=days
            )

        except Exception as e:
            logger.error(f"Sentiment history retrieval failed: {str(e)}")
            return SentimentHistory(
                ticker=ticker,
                history=[],
                period_days=days
            )

    async def analyze_text_sentiment(self, text: str, context: Optional[str] = None) -> SentimentScore:
        """
        任意のテキストのセンチメント分析

        Args:
            text: 分析対象テキスト
            context: コンテキスト（"ir", "news", "social"）

        Returns:
            SentimentScore: センチメントスコア
        """
        try:
            # コンテキストに応じたプロンプト選択
            if context == "ir":
                return await self.analyze_ir_sentiment(text)

            prompt = self.sentiment_prompt_template.format(text=text[:4000])

            response = await self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "あなたは金融テキストのセンチメント分析専門家です。JSON形式で回答してください。"
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            return SentimentScore(
                positive=result.get("positive", 0.33),
                negative=result.get("negative", 0.33),
                neutral=result.get("neutral", 0.34),
                overall=result.get("overall", "neutral"),
                confidence=result.get("confidence", 0.5),
                source=context or "text",
                analyzed_at=datetime.now(JST).isoformat(),
                details={
                    "key_phrases": result.get("key_phrases", []),
                    "reasoning": result.get("reasoning")
                }
            )

        except Exception as e:
            logger.error(f"Text sentiment analysis failed: {str(e)}")
            return SentimentScore(
                positive=0.33,
                negative=0.33,
                neutral=0.34,
                overall="neutral",
                confidence=0.0,
                source=context or "text",
                analyzed_at=datetime.now(JST).isoformat(),
                details={"error": str(e)}
            )

    def generate_iris_comment(self, sentiment: SentimentScore) -> str:
        """
        イリス向けのコメント生成

        Args:
            sentiment: センチメントスコア

        Returns:
            str: イリスのコメント
        """
        import random

        overall = sentiment.overall
        confidence = sentiment.confidence

        if overall == "bullish":
            if confidence >= 0.7:
                templates = self.iris_comment_templates["bullish_high"]
            else:
                templates = self.iris_comment_templates["bullish_low"]
        elif overall == "bearish":
            if confidence >= 0.7:
                templates = self.iris_comment_templates["bearish_high"]
            else:
                templates = self.iris_comment_templates["bearish_low"]
        else:
            templates = self.iris_comment_templates["neutral"]

        base_comment = random.choice(templates)

        # 詳細情報があれば追加
        if sentiment.details:
            if sentiment.source == "ir":
                if sentiment.details.get("growth_signals"):
                    signals = sentiment.details["growth_signals"][:2]
                    base_comment += f" 注目ポイントは「{'、'.join(signals)}」です。"
                if sentiment.details.get("warning_signals"):
                    warnings = sentiment.details["warning_signals"][:1]
                    base_comment += f" ただし「{warnings[0]}」には注意が必要です。"

        return base_comment


# シングルトンインスタンス
market_sentiment_analyzer = MarketSentimentAnalyzer()
