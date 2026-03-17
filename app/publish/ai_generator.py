"""Claude API-powered article generator for note.com.

Uses Iris character personality and tool_use for structured output,
following the boatrace-ai pattern. Falls back to template-based
ArticleGenerator on API failure.
"""

from __future__ import annotations

import logging
import os
from datetime import date
from typing import TYPE_CHECKING

from app.publish.article import ArticleContent, ArticleGenerator
from app.publish.prompts import (
    ARTICLE_TOOL,
    BRAND,
    DISCLAIMER,
    IRIS_DAILY_SYSTEM_PROMPT,
    IRIS_INDUSTRY_SYSTEM_PROMPT,
    IRIS_SYSTEM_PROMPT,
    IRIS_WEEKLY_SYSTEM_PROMPT,
    format_analysis_for_prompt,
    format_multi_analysis_for_prompt,
)

if TYPE_CHECKING:
    from app.models.analysis import AnalysisResult
    from app.models.company import Company
    from app.models.document import Document

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MAX_TOKENS = 8192
DEFAULT_PRICE = int(os.getenv("NOTE_DEFAULT_PRICE", "500"))


class AIArticleGenerator:
    """Claude API-powered article generator with template fallback."""

    def __init__(self) -> None:
        self._client = None
        self._model = os.getenv("SMARTIR_MODEL", DEFAULT_MODEL)
        self._max_tokens = int(os.getenv("SMARTIR_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)))
        self._fallback = ArticleGenerator()

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic()
            except ImportError:
                raise RuntimeError(
                    "anthropic がインストールされていません。\n"
                    "pip install anthropic"
                )
        return self._client

    def _call_claude(self, system: str, user_content: str) -> dict | None:
        """Call Claude API with tool_use and return the structured output."""
        try:
            client = self._get_client()
            response = client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system,
                tools=[ARTICLE_TOOL],
                tool_choice={"type": "tool", "name": "submit_article"},
                messages=[{"role": "user", "content": user_content}],
            )

            for block in response.content:
                if block.type == "tool_use" and block.name == "submit_article":
                    return block.input

            log.warning("Claude response did not contain submit_article tool_use")
            return None

        except Exception as e:
            log.error("Claude API call failed: %s", e)
            return None

    def _assemble_html(self, data: dict, paid: bool = False) -> str:
        """Assemble article HTML from structured Claude output."""
        parts = [data["free_section"]]

        if paid and data.get("paid_section"):
            parts.append("<pay>")
            parts.append(data["paid_section"])

        parts.append(DISCLAIMER)
        return "\n".join(parts)

    def generate_analysis_article(
        self,
        document: Document,
        analysis: AnalysisResult,
        company: Company,
        free: bool = False,
        youtube_url: str | None = None,
        default_price: int = DEFAULT_PRICE,
    ) -> ArticleContent:
        """Generate a single-company analysis article using Claude API."""
        context = format_analysis_for_prompt(document, analysis, company)

        price_instruction = ""
        if free:
            price_instruction = "この記事は無料公開です。paid_sectionは空文字列にしてください。"
        else:
            price_instruction = (
                f"この記事は有料（{default_price}円）です。"
                "free_sectionには導入+サマリー+注目ポイント3つを入れ、"
                "paid_sectionに詳細分析+センチメントスコア+まとめを入れてください。"
            )

        youtube_text = ""
        if youtube_url:
            youtube_text = f"\nVTuber解説動画URL: {youtube_url}（記事内で紹介してください）"

        user_content = (
            f"以下のIR分析結果をもとに、note.com記事を作成してください。\n\n"
            f"{price_instruction}\n{youtube_text}\n\n"
            f"{context}"
        )

        data = self._call_claude(IRIS_SYSTEM_PROMPT, user_content)
        if data:
            return ArticleContent(
                title=data["title"],
                body_html=self._assemble_html(data, paid=not free),
                hashtags=data.get("hashtags", [])[:8],
                price=0 if free else default_price,
            )

        log.warning("Falling back to template-based generator for analysis article")
        return self._fallback.generate_analysis_article(
            document, analysis, company, free, youtube_url, default_price,
        )

    def generate_daily_summary(
        self,
        target_date: date,
        analyses: list[tuple[Document, AnalysisResult, Company]],
    ) -> ArticleContent:
        """Generate daily summary article using Claude API."""
        context = format_multi_analysis_for_prompt(analyses, target_date)
        date_str = target_date.strftime("%Y/%m/%d")
        n = len(analyses)

        user_content = (
            f"本日（{date_str}）に発表された{n}社の決算分析をまとめた"
            f"日次サマリー記事を作成してください。\n"
            f"この記事は無料公開です。paid_sectionは空文字列にしてください。\n\n"
            f"{context}"
        )

        data = self._call_claude(IRIS_DAILY_SYSTEM_PROMPT, user_content)
        if data:
            return ArticleContent(
                title=data["title"],
                body_html=self._assemble_html(data, paid=False),
                hashtags=data.get("hashtags", [])[:8],
                price=0,
            )

        log.warning("Falling back to template-based generator for daily summary")
        return self._fallback.generate_daily_summary(target_date, analyses)

    def generate_breaking_article(
        self,
        document: Document,
        company: Company,
    ) -> ArticleContent:
        """Generate a breaking news article for a newly detected IR document."""
        user_content = (
            f"以下の決算が発表されました。速報記事を作成してください。\n"
            f"この記事は無料公開です。paid_sectionは空文字列にしてください。\n"
            f"AI分析はまだ完了していないため、書類の基本情報のみで構成してください。\n"
            f"「詳細なAI分析は後ほど公開予定です」と言及してください。\n\n"
            f"企業名: {company.name}（{company.ticker_code}）\n"
            f"業種: {company.sector or '不明'}\n"
            f"書類名: {document.title or '決算短信'}\n"
            f"発表日: {document.publish_date or '本日'}\n"
        )

        data = self._call_claude(IRIS_SYSTEM_PROMPT, user_content)
        if data:
            return ArticleContent(
                title=data["title"],
                body_html=self._assemble_html(data, paid=False),
                hashtags=data.get("hashtags", [])[:8],
                price=0,
            )

        # Simple template fallback
        title = f"【速報】{company.name}({company.ticker_code}) {document.title or '決算発表'} - {BRAND}"
        body = (
            f"<h2>{company.name}({company.ticker_code}) 決算速報</h2>"
            f"<p>{document.title or '決算短信'}が発表されました。</p>"
            f"<p>AI分析を準備中です。詳細な分析結果は後ほど公開予定です。</p>"
            f"{DISCLAIMER}"
        )
        return ArticleContent(
            title=title,
            body_html=body,
            hashtags=["速報", "決算", company.name, company.ticker_code or "", BRAND],
            price=0,
        )

    def generate_weekly_trend(
        self,
        week_start: date,
        analyses: list[tuple[Document, AnalysisResult, Company]],
    ) -> ArticleContent:
        """Generate weekly trend report using Claude API."""
        week_end = week_start
        context = format_multi_analysis_for_prompt(analyses)
        n = len(analyses)
        start_str = week_start.strftime("%Y/%m/%d")

        user_content = (
            f"{start_str}からの1週間で発表された{n}社の決算分析をまとめた"
            f"週次トレンドレポートを作成してください。\n"
            f"この記事は無料公開です。paid_sectionは空文字列にしてください。\n\n"
            f"{context}"
        )

        data = self._call_claude(IRIS_WEEKLY_SYSTEM_PROMPT, user_content)
        if data:
            return ArticleContent(
                title=data["title"],
                body_html=self._assemble_html(data, paid=False),
                hashtags=data.get("hashtags", [])[:8],
                price=0,
            )

        # Template fallback
        title = f"【週次レポート】{start_str}〜 決算トレンド - {BRAND}"
        parts = [
            f"<h2>{start_str}〜 週間決算トレンド</h2>",
            f"<p>今週{n}社の決算が発表されました。</p>",
        ]
        for doc, analysis, company in analyses[:10]:
            pos = analysis.sentiment_positive or 0
            label = "ポジティブ" if pos >= 0.5 else "ネガティブ" if (analysis.sentiment_negative or 0) >= 0.5 else "中立"
            parts.append(f"<h3>{company.name}({company.ticker_code})</h3>")
            parts.append(f"<p>センチメント: <strong>{label}</strong></p>")
            summary = (analysis.summary or "")[:150]
            if summary:
                parts.append(f"<p>{summary}</p>")
            parts.append("<hr>")
        parts.append(DISCLAIMER)

        return ArticleContent(
            title=title,
            body_html="\n".join(parts),
            hashtags=["週間決算", "決算トレンド", "IR分析", BRAND],
            price=0,
        )

    def generate_industry_comparison(
        self,
        sector: str,
        analyses: list[tuple[Document, AnalysisResult, Company]],
    ) -> ArticleContent:
        """Generate industry comparison article using Claude API."""
        context = format_multi_analysis_for_prompt(analyses)
        n = len(analyses)

        user_content = (
            f"業種「{sector}」に属する{n}社の決算分析を比較する"
            f"業界分析記事を作成してください。\n"
            f"この記事は無料公開です。paid_sectionは空文字列にしてください。\n\n"
            f"{context}"
        )

        data = self._call_claude(IRIS_INDUSTRY_SYSTEM_PROMPT, user_content)
        if data:
            return ArticleContent(
                title=data["title"],
                body_html=self._assemble_html(data, paid=False),
                hashtags=data.get("hashtags", [])[:8],
                price=0,
            )

        # Template fallback
        title = f"【業界分析】{sector} {n}社の決算比較 - {BRAND}"
        parts = [
            f"<h2>{sector} 業界決算比較</h2>",
            f"<p>{sector}セクターの{n}社の決算をAIが分析・比較しました。</p>",
        ]
        for doc, analysis, company in analyses:
            pos = analysis.sentiment_positive or 0
            label = "ポジティブ" if pos >= 0.5 else "ネガティブ" if (analysis.sentiment_negative or 0) >= 0.5 else "中立"
            parts.append(f"<h3>{company.name}({company.ticker_code})</h3>")
            parts.append(f"<p>センチメント: <strong>{label}</strong></p>")
            summary = (analysis.summary or "")[:200]
            if summary:
                parts.append(f"<p>{summary}</p>")
            parts.append("<hr>")
        parts.append(DISCLAIMER)

        return ArticleContent(
            title=title,
            body_html="\n".join(parts),
            hashtags=[sector, "業界分析", "決算比較", "IR分析", BRAND],
            price=0,
        )

    def generate_earnings_calendar(
        self,
        target_date: date,
        companies: list[Company],
    ) -> ArticleContent:
        """Generate earnings calendar preview article using Claude API."""
        date_str = target_date.strftime("%Y/%m/%d")
        n = len(companies)

        company_list = "\n".join(
            f"- {c.name}（{c.ticker_code}）業種: {c.sector or '不明'}"
            for c in companies
        )

        user_content = (
            f"{date_str}に決算発表が予定されている{n}社の"
            f"決算カレンダープレビュー記事を作成してください。\n"
            f"この記事は無料公開です。paid_sectionは空文字列にしてください。\n"
            f"各企業の注目ポイントや過去の業績傾向に軽く触れてください。\n\n"
            f"## 発表予定企業\n{company_list}\n"
        )

        data = self._call_claude(IRIS_SYSTEM_PROMPT, user_content)
        if data:
            return ArticleContent(
                title=data["title"],
                body_html=self._assemble_html(data, paid=False),
                hashtags=data.get("hashtags", [])[:8],
                price=0,
            )

        # Template fallback
        title = f"【決算カレンダー】{date_str} 発表予定{n}社 - {BRAND}"
        parts = [
            f"<h2>{date_str} 決算発表予定</h2>",
            f"<p>本日{n}社の決算発表が予定されています。</p>",
            "<h3>発表予定企業</h3>",
            "<ul>",
        ]
        for c in companies:
            parts.append(f"<li>{c.name}（{c.ticker_code}）- {c.sector or '不明'}</li>")
        parts.append("</ul>")
        parts.append("<p>決算発表後、AIによる分析記事を順次公開予定です。</p>")
        parts.append(DISCLAIMER)

        return ArticleContent(
            title=title,
            body_html="\n".join(parts),
            hashtags=["決算カレンダー", "決算予定", "IR分析", BRAND],
            price=0,
        )
