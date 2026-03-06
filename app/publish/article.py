"""IR analysis article generator for note.com."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from app.models.company import Company
from app.models.document import Document
from app.models.analysis import AnalysisResult

log = logging.getLogger(__name__)

BRAND = "SmartIR"

# note.com supported HTML tags (ProseMirror editor)
# h2, h3, p, strong, ul, li, hr -- NOT h1, table, blockquote, code


@dataclass
class ArticleContent:
    title: str
    body_html: str
    hashtags: list[str] = field(default_factory=list)
    price: int = 0


def _sentiment_label(analysis: AnalysisResult) -> str:
    pos = analysis.sentiment_positive or 0
    neg = analysis.sentiment_negative or 0
    if pos >= 0.7:
        return "非常にポジティブ"
    elif pos >= 0.5:
        return "ポジティブ"
    elif neg >= 0.7:
        return "非常にネガティブ"
    elif neg >= 0.5:
        return "ネガティブ"
    return "中立"


def _sentiment_emoji(analysis: AnalysisResult) -> str:
    pos = analysis.sentiment_positive or 0
    neg = analysis.sentiment_negative or 0
    if pos >= 0.7:
        return "📈"
    elif pos >= 0.5:
        return "⬆️"
    elif neg >= 0.7:
        return "📉"
    elif neg >= 0.5:
        return "⬇️"
    return "➡️"


def _key_points_html(key_points: list) -> str:
    if not key_points:
        return ""
    items = "".join(f"<li>{point}</li>" for point in key_points[:5])
    return f"<ul>{items}</ul>"


class ArticleGenerator:
    """IR分析結果からnote.com記事HTMLを生成"""

    def generate_analysis_article(
        self,
        document: Document,
        analysis: AnalysisResult,
        company: Company,
        free: bool = False,
        youtube_url: str | None = None,
        default_price: int = 500,
    ) -> ArticleContent:
        """単一銘柄の分析記事を生成"""
        label = _sentiment_label(analysis)
        emoji = _sentiment_emoji(analysis)

        title = f"【AI分析】{company.name}({company.ticker_code}) 決算分析 - {BRAND}"

        # Free section
        parts = []
        parts.append(f"<h2>{emoji} 決算サマリー</h2>")
        parts.append(
            f"<p>{company.name}({company.ticker_code})の決算が発表されました。"
            f"AIによるセンチメント分析: <strong>{label}</strong></p>"
        )

        summary_short = (analysis.summary or "")[:300]
        if summary_short:
            parts.append(f"<p>{summary_short}</p>")

        key_points = analysis.key_points or []
        if key_points:
            parts.append("<h3>注目ポイント</h3>")
            items = "".join(f"<li>{p}</li>" for p in key_points[:3])
            parts.append(f"<ul>{items}</ul>")

        if free:
            # Full content for free article
            parts.append("<hr>")
            parts.append("<h2>詳細AI分析</h2>")
            parts.append(f"<p>{analysis.summary}</p>")
            if len(key_points) > 3:
                parts.append("<h3>その他のポイント</h3>")
                items = "".join(f"<li>{p}</li>" for p in key_points[3:])
                parts.append(f"<ul>{items}</ul>")
            if youtube_url:
                parts.append("<h2>VTuber解説動画</h2>")
                parts.append(f"<p>Irisによる解説はこちら: {youtube_url}</p>")
            parts.append("<hr>")
            parts.append(f"<p>{BRAND} - AI搭載IR分析サービス</p>")
            price = 0
        else:
            # Paid section
            parts.append("<pay>")
            parts.append("<h2>詳細AI分析</h2>")
            parts.append(f"<p>{analysis.summary}</p>")
            if len(key_points) > 3:
                parts.append("<h3>その他のポイント</h3>")
                items = "".join(f"<li>{p}</li>" for p in key_points[3:])
                parts.append(f"<ul>{items}</ul>")

            parts.append("<h2>センチメントスコア</h2>")
            parts.append(
                f"<p>ポジティブ: {(analysis.sentiment_positive or 0) * 100:.0f}% / "
                f"ネガティブ: {(analysis.sentiment_negative or 0) * 100:.0f}% / "
                f"中立: {(analysis.sentiment_neutral or 0) * 100:.0f}%</p>"
            )

            if youtube_url:
                parts.append("<h2>VTuber解説動画</h2>")
                parts.append(f"<p>Irisによる解説はこちら: {youtube_url}</p>")

            parts.append("<hr>")
            parts.append(f"<p>{BRAND} - AI搭載IR分析サービス</p>")
            price = default_price

        hashtags = self._generate_hashtags(company)

        return ArticleContent(
            title=title,
            body_html="\n".join(parts),
            hashtags=hashtags,
            price=price,
        )

    def generate_daily_summary(
        self,
        target_date: date,
        analyses: list[tuple[Document, AnalysisResult, Company]],
    ) -> ArticleContent:
        """日次まとめ記事（無料）を生成"""
        n = len(analyses)
        date_str = target_date.strftime("%Y/%m/%d")

        title = f"【決算まとめ】{date_str} 発表{n}社のAI分析 - {BRAND}"

        parts = []
        parts.append(f"<h2>{date_str} 決算発表まとめ</h2>")
        parts.append(
            f"<p>本日{n}社の決算が発表されました。AIによる分析結果をお届けします。</p>"
        )

        for doc, analysis, company in analyses:
            emoji = _sentiment_emoji(analysis)
            label = _sentiment_label(analysis)
            parts.append(f"<h3>{emoji} {company.name}({company.ticker_code})</h3>")

            summary_short = (analysis.summary or "")[:200]
            parts.append(f"<p>センチメント: <strong>{label}</strong></p>")
            if summary_short:
                parts.append(f"<p>{summary_short}</p>")

            key_points = analysis.key_points or []
            if key_points:
                items = "".join(f"<li>{p}</li>" for p in key_points[:2])
                parts.append(f"<ul>{items}</ul>")
            parts.append("<hr>")

        parts.append(
            f"<p>詳細分析は各銘柄の有料記事をご覧ください。</p>"
        )
        parts.append(f"<p>{BRAND} - AI搭載IR分析サービス</p>")

        hashtags = ["決算", "IR分析", "AI分析", BRAND]
        # Add top company names
        for _, _, company in analyses[:4]:
            hashtags.append(company.name)

        return ArticleContent(
            title=title,
            body_html="\n".join(parts),
            hashtags=hashtags[:8],
            price=0,
        )

    def _generate_hashtags(self, company: Company) -> list[str]:
        tags = ["決算", "IR分析", "AI分析", BRAND]
        if company.name:
            tags.append(company.name)
        if company.ticker_code:
            tags.append(company.ticker_code)
        if company.sector:
            tags.append(company.sector)
        return tags[:8]
