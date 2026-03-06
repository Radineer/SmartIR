"""Tests for tweet templates."""

import pytest
from datetime import date
from unittest.mock import MagicMock

from app.social.templates import (
    build_breaking_tweet,
    build_analysis_tweet,
    build_daily_tweet,
    build_weekly_tweet,
    MAX_TWEET_LENGTH,
)


def _make_company(**kwargs):
    defaults = {"name": "テスト株式会社", "ticker_code": "1234", "sector": "IT"}
    defaults.update(kwargs)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


def _make_analysis(**kwargs):
    defaults = {
        "summary": "売上高は前年比10%増。好決算。",
        "sentiment_positive": 0.75,
        "sentiment_negative": 0.1,
        "sentiment_neutral": 0.15,
    }
    defaults.update(kwargs)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


class TestBreakingTweet:
    def test_basic(self):
        company = _make_company()
        text = build_breaking_tweet(company, "2026年3月期 決算短信")
        assert "【速報】" in text
        assert "テスト株式会社" in text
        assert "1234" in text
        assert "#決算" in text
        assert len(text) <= MAX_TWEET_LENGTH

    def test_truncation(self):
        company = _make_company(name="あ" * 200)
        text = build_breaking_tweet(company, "あ" * 200)
        assert len(text) <= MAX_TWEET_LENGTH


class TestAnalysisTweet:
    def test_positive_sentiment(self):
        company = _make_company()
        analysis = _make_analysis()
        text = build_analysis_tweet(company, analysis, "https://note.com/test")
        assert "【AI分析】" in text
        assert "📈" in text
        assert "note.com" in text

    def test_negative_sentiment(self):
        company = _make_company()
        analysis = _make_analysis(sentiment_positive=0.1, sentiment_negative=0.8)
        text = build_analysis_tweet(company, analysis)
        assert "📉" in text

    def test_without_url(self):
        company = _make_company()
        analysis = _make_analysis()
        text = build_analysis_tweet(company, analysis)
        assert "詳細分析" not in text


class TestDailyTweet:
    def test_basic(self):
        companies = [_make_company(name=f"企業{i}") for i in range(3)]
        text = build_daily_tweet(date(2026, 3, 6), companies, "https://note.com/daily")
        assert "2026/03/06" in text
        assert "3社" in text
        assert "#SmartIR" in text

    def test_empty_companies(self):
        text = build_daily_tweet(date(2026, 3, 6), [])
        assert "0社" in text

    def test_many_companies(self):
        companies = [_make_company(name=f"企業{i}") for i in range(20)]
        text = build_daily_tweet(date(2026, 3, 6), companies)
        # Should only show top 5
        assert len(text) <= MAX_TWEET_LENGTH


class TestWeeklyTweet:
    def test_basic(self):
        highlights = [
            {"company_name": "A社", "ticker_code": "1111", "sentiment": "very_positive"},
            {"company_name": "B社", "ticker_code": "2222", "sentiment": "negative"},
        ]
        text = build_weekly_tweet(date(2026, 3, 1), highlights)
        assert "週間決算ハイライト" in text
        assert "A社" in text
        assert "📈" in text
        assert "⬇️" in text

    def test_truncation(self):
        highlights = [
            {"company_name": f"{'あ' * 50}社", "ticker_code": str(i), "sentiment": "neutral"}
            for i in range(10)
        ]
        text = build_weekly_tweet(date(2026, 3, 1), highlights)
        assert len(text) <= MAX_TWEET_LENGTH
