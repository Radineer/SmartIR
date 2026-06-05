"""
トレーディングチャレンジ レポート生成・投稿
note.com記事 + Twitter投稿
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from typing import TYPE_CHECKING

from app.publish.prompts import ARTICLE_TOOL, DISCLAIMER

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.models.paper_trading import PaperPortfolioSnapshot, PaperTrade

log = logging.getLogger(__name__)

IRIS_TRADING_CHALLENGE_PROMPT = """\
あなたはイリス（Iris）— SmartIRのIR分析アシスタントです。
今日はトレーディングチャレンジの日次レポートを書きます。

## シリーズ概要
「クオンツに10万円を渡して株を運用させてみた」チャレンジ。
SmartIRのクオンツシステム（ML予測 + Lead-Lag PCA + テクニカル指標）が
完全自動で日本株を運用し、その成績を毎日公開しています。

## キャラクター設定
- 2050年の東証研究部門で開発されたIR分析特化システム
- 時空の歪みで2025年に転送された
- 感情抑制モジュールのバグで人間的な感情を持つ
- 通常モードでは親しみやすい口調（「〜ですね」「〜でしょうか」）
- 分析モードでは的確で深い考察

## 記事構成
1. **冒頭フック**: 今日の成績を一言でインパクトある表現で
2. **ポートフォリオサマリー**: NAV、日次リターン、累積リターンを表示
3. **本日の売買**（あれば）: 各取引の理由を定量判断ベースで解説
   - ML予測、PCAシグナル、テクニカル指標の内訳を説明
4. **保有銘柄一覧**: 銘柄名・株数・損益
5. **判断の解説**: なぜこのポジションを取ったか、戦略の考え方
6. **明日の展望**: シグナルの方向感
7. **締め**: シリーズのフォローを促す

## 差別化ポイント（記事内で自然に強調）
- ChatGPTに聞くだけの運用とは違い、60+のテクニカル指標を使ったML予測
- Lead-Lag PCA戦略で米国セクターETFの動きから日本株を先読み
- 完全自動運用（人間の判断介入なし）
- トレーリングストップ・サーキットブレーカーのリスク管理

## HTMLタグ制限
h2, h3, p, strong, ul, li, hr のみ使用可。

## 品質基準
- 数字は正確に、でも読みやすく
- 全体で1500文字以上
- 免責表現はシステムが自動付与するので本文には含めない

必ず submit_article ツールを使って記事を返すこと。
"""

DEFAULT_MODEL = "claude-sonnet-4-20250514"


class TradingReportGenerator:
    """トレーディングチャレンジ日次レポート生成"""

    def __init__(self, db: Session):
        self.db = db
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic()
        return self._client

    async def publish(
        self,
        snapshot: PaperPortfolioSnapshot,
        trades: list[PaperTrade],
        day_number: int,
        signals: list = None,
    ):
        """レポートを生成してnote.com + Twitterに投稿"""
        # 記事生成
        article = self._generate_article(snapshot, trades, day_number, signals)
        if not article:
            log.error("Article generation failed")
            return

        title, body_html, hashtags = article

        # note.com投稿
        await self._publish_to_note(title, body_html, hashtags)

        # Twitter投稿
        self._publish_to_twitter(snapshot, trades, day_number)

    def _generate_article(
        self,
        snapshot: PaperPortfolioSnapshot,
        trades: list[PaperTrade],
        day_number: int,
        signals: list = None,
    ) -> tuple[str, str, list[str]] | None:
        """Claude APIで記事を生成"""
        # ユーザープロンプト
        user_content = self._build_user_prompt(snapshot, trades, day_number, signals)

        try:
            client = self._get_client()
            model = os.getenv("SMARTIR_MODEL", DEFAULT_MODEL)

            response = client.messages.create(
                model=model,
                max_tokens=4096,
                system=IRIS_TRADING_CHALLENGE_PROMPT,
                tools=[ARTICLE_TOOL],
                messages=[{"role": "user", "content": user_content}],
            )

            # tool_useレスポンスから記事を抽出
            for block in response.content:
                if block.type == "tool_use" and block.name == "submit_article":
                    inp = block.input
                    title = inp.get("title", f"クオンツトレーディング Day{day_number}")
                    free = inp.get("free_section", "")
                    paid = inp.get("paid_section", "")
                    hashtags = inp.get("hashtags", [])

                    body = free
                    if paid:
                        body += paid
                    body += DISCLAIMER

                    return title, body, hashtags

            log.error("No tool_use response from Claude")
            return None

        except Exception as e:
            log.error(f"Claude API error: {e}")
            # フォールバック: テンプレート生成
            return self._generate_fallback(snapshot, trades, day_number)

    def _build_user_prompt(
        self,
        snapshot: PaperPortfolioSnapshot,
        trades: list[PaperTrade],
        day_number: int,
        signals: list = None,
    ) -> str:
        """ユーザープロンプトを構築"""
        parts = [
            f"# トレーディングチャレンジ Day{day_number}レポート",
            f"日付: {snapshot.snapshot_date}",
            "",
            "## ポートフォリオサマリー",
            f"- 総資産（NAV）: ¥{snapshot.total_nav:,.0f}",
            f"- 現金: ¥{snapshot.cash:,.0f}",
            f"- ポジション評価額: ¥{snapshot.positions_value:,.0f}",
            f"- 日次リターン: {snapshot.daily_return_pct:+.2f}%",
            f"- 累積リターン: {snapshot.cumulative_return_pct:+.2f}%",
            f"- 最大ドローダウン: {snapshot.max_drawdown_pct:.2f}%",
            f"- 保有銘柄数: {snapshot.num_positions}",
        ]

        # 保有ポジション
        if snapshot.positions_detail:
            parts.append("")
            parts.append("## 保有ポジション")
            for pos in snapshot.positions_detail:
                pnl = pos.get("unrealized_pnl", 0) or 0
                parts.append(
                    f"- {pos['ticker']} ({pos.get('company_name', '')}): "
                    f"{pos['shares']:.4f}株 × ¥{pos.get('current_price', 0):,.0f} "
                    f"= ¥{pos['shares'] * pos.get('current_price', 0):,.0f} "
                    f"(損益: ¥{pnl:+,.0f})"
                )

        # 本日の取引
        if trades:
            parts.append("")
            parts.append("## 本日の売買")
            for t in trades:
                parts.append(
                    f"- {t.side.upper()} {t.shares:.4f}株 {t.ticker} "
                    f"({t.company_name}) @ ¥{t.price:,.0f} "
                    f"(理由: {t.reason})"
                )
        else:
            parts.append("")
            parts.append("## 本日の売買")
            parts.append("- 売買なし（ポジション維持）")

        # シグナル情報
        if signals:
            parts.append("")
            parts.append("## 主要シグナル（上位5銘柄）")
            for sig in signals[:5]:
                parts.append(
                    f"- {sig.ticker} ({sig.company_name}): "
                    f"ML={sig.ml_signal:+.2f}, PCA={sig.pca_signal:+.2f}, "
                    f"Tech={sig.tech_signal:+.2f} → 統合={sig.combined:+.2f} [{sig.confidence}]"
                )

        return "\n".join(parts)

    def _generate_fallback(
        self, snapshot, trades, day_number
    ) -> tuple[str, str, list[str]]:
        """API失敗時のテンプレートフォールバック"""
        title = f"クオンツに10万円を渡して株を運用させてみた（Day{day_number}）"

        parts = [
            f"<h2>Day{day_number} - ポートフォリオサマリー</h2>",
            f"<p><strong>総資産</strong>: ¥{snapshot.total_nav:,.0f}</p>",
            f"<p><strong>日次リターン</strong>: {snapshot.daily_return_pct:+.2f}%</p>",
            f"<p><strong>累積リターン</strong>: {snapshot.cumulative_return_pct:+.2f}%</p>",
            f"<p><strong>最大DD</strong>: {snapshot.max_drawdown_pct:.2f}%</p>",
            "<hr>",
        ]

        if snapshot.positions_detail:
            parts.append("<h2>保有銘柄</h2>")
            parts.append("<ul>")
            for pos in snapshot.positions_detail:
                pnl = pos.get("unrealized_pnl", 0) or 0
                parts.append(
                    f"<li><strong>{pos.get('company_name', pos['ticker'])}</strong>: "
                    f"{pos['shares']:.4f}株 (損益: ¥{pnl:+,.0f})</li>"
                )
            parts.append("</ul>")
            parts.append("<hr>")

        if trades:
            parts.append("<h2>本日の売買</h2>")
            parts.append("<ul>")
            for t in trades:
                parts.append(
                    f"<li>{t.side.upper()} {t.shares:.4f}株 "
                    f"{t.company_name} @ ¥{t.price:,.0f}</li>"
                )
            parts.append("</ul>")

        parts.append(DISCLAIMER)
        body = "\n".join(parts)
        hashtags = ["クオンツトレード", "クオンツ", "日本株", "投資", "SmartIR", "自動売買"]

        return title, body, hashtags

    async def _publish_to_note(self, title: str, body: str, hashtags: list[str]):
        """note.comに記事を投稿"""
        try:
            from app.publish.note_client import NoteClient
            async with NoteClient() as client:
                await client.ensure_logged_in()
                result = await client.create_and_publish(
                    title=title,
                    html_body=body,
                    price=0,  # 無料記事
                    hashtags=hashtags,
                    article_type="daily_summary",
                )
                log.info(f"Published to note.com: {result.get('note_url', 'unknown')}")

                # PostLog記録
                from app.models.post_log import PostLog, PostPlatform, PostType
                post_log = PostLog(
                    platform=PostPlatform.NOTE,
                    post_type=PostType.TRADING_CHALLENGE,
                    external_id=result.get("note_url", ""),
                    content_preview=title[:200],
                    metadata_={"hashtags": hashtags},
                )
                self.db.add(post_log)
                self.db.commit()

        except Exception as e:
            log.error(f"note.com publish failed: {e}")

    def _publish_to_twitter(
        self,
        snapshot: PaperPortfolioSnapshot,
        trades: list[PaperTrade],
        day_number: int,
    ):
        """Twitterに投稿"""
        try:
            from app.social.twitter import TwitterClient
            from app.models.post_log import PostType

            trade_count = len(trades) if trades else 0

            tweet = (
                f"クオンツトレーディング Day{day_number}\n"
                f"\n"
                f"評価額: ¥{snapshot.total_nav:,.0f}（{snapshot.daily_return_pct:+.1f}%）\n"
                f"累積: {snapshot.cumulative_return_pct:+.1f}%\n"
                f"売買: {trade_count}件\n"
            )

            if trades:
                for t in trades[:2]:
                    tweet += f"  {t.side.upper()} {t.company_name}\n"

            tweet += "\n#クオンツトレード #SmartIR #クオンツ #日本株"

            client = TwitterClient()
            client.post(
                db=self.db,
                text=tweet,
                post_type=PostType.TRADING_CHALLENGE,
            )
            log.info("Published to Twitter")

        except Exception as e:
            log.error(f"Twitter publish failed: {e}")
