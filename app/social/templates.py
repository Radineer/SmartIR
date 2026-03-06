"""Tweet template generation for IR analysis posts."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.analysis import AnalysisResult

MAX_TWEET_LENGTH = 280

SENTIMENT_EMOJI = {
    "very_positive": "📈",
    "positive": "⬆️",
    "neutral": "➡️",
    "negative": "⬇️",
    "very_negative": "📉",
}


def _truncate(text: str, max_len: int = MAX_TWEET_LENGTH) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _get_sentiment_key(analysis: AnalysisResult) -> str:
    pos = analysis.sentiment_positive or 0
    neg = analysis.sentiment_negative or 0
    if pos >= 0.7:
        return "very_positive"
    elif pos >= 0.5:
        return "positive"
    elif neg >= 0.7:
        return "very_negative"
    elif neg >= 0.5:
        return "negative"
    return "neutral"


def build_breaking_tweet(
    company: Company,
    document_title: str,
) -> str:
    """決算速報ツイート"""
    lines = [
        f"【速報】{company.name}({company.ticker_code})",
        f"{document_title}",
        "",
        "AI分析を準備中...",
        f"#決算 #{company.ticker_code} #IR分析",
    ]
    return _truncate("\n".join(lines))


def build_analysis_tweet(
    company: Company,
    analysis: AnalysisResult,
    note_url: str = "",
) -> str:
    """分析完了ツイート"""
    key = _get_sentiment_key(analysis)
    emoji = SENTIMENT_EMOJI.get(key, "➡️")

    summary = (analysis.summary or "")[:100]

    lines = [
        f"【AI分析】{company.name}({company.ticker_code})",
        f"{emoji} {summary}",
    ]
    if note_url:
        lines.append("")
        lines.append(f"詳細分析 → {note_url}")
    lines.append(f"#決算分析 #{company.ticker_code} #IR分析")

    return _truncate("\n".join(lines))


def build_daily_tweet(
    target_date: date,
    companies: list[Company],
    note_url: str = "",
) -> str:
    """日次まとめツイート"""
    date_str = target_date.strftime("%Y/%m/%d")
    n = len(companies)

    lines = [f"【{date_str} 決算まとめ】"]
    lines.append(f"本日{n}社の決算をAI分析しました")

    if companies:
        top = ", ".join(c.name for c in companies[:5])
        lines.append(f"注目: {top}")

    lines.append("")
    if note_url:
        lines.append(f"まとめ → {note_url}")
    lines.append("#決算 #IR分析 #SmartIR")

    return _truncate("\n".join(lines))


def build_weekly_tweet(
    week_start: date,
    highlights: list[dict],
) -> str:
    """週次まとめツイート

    highlights: list of {"company_name": str, "ticker_code": str, "sentiment": str}
    """
    date_str = week_start.strftime("%m/%d")

    lines = [f"【週間決算ハイライト】{date_str}〜"]

    for h in highlights[:5]:
        emoji = SENTIMENT_EMOJI.get(h.get("sentiment", "neutral"), "➡️")
        lines.append(f"{emoji} {h['company_name']}({h['ticker_code']})")

    lines.append("")
    lines.append("#週間決算 #IR分析 #SmartIR")

    return _truncate("\n".join(lines))
