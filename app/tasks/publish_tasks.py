"""Celery tasks for automated note.com publishing and X posting."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import date, timedelta

from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.analysis import AnalysisResult
from app.models.company import Company
from app.models.post_log import PostLog, PostPlatform, PostType

log = logging.getLogger(__name__)


def _should_auto_tweet() -> bool:
    return os.getenv("PUBLISH_AUTO_TWEET", "true").lower() == "true"


def _should_auto_note() -> bool:
    return os.getenv("PUBLISH_AUTO_NOTE", "true").lower() == "true"


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def publish_breaking_tweet(self, document_id: int):
    """新着IR検知時 → 速報ツイート"""
    if not _should_auto_tweet():
        log.info("Auto tweet disabled, skipping breaking tweet")
        return

    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            log.warning("Document %d not found", document_id)
            return

        company = db.query(Company).filter(Company.id == doc.company_id).first()
        if not company:
            log.warning("Company not found for document %d", document_id)
            return

        from app.social.templates import build_breaking_tweet
        from app.social.twitter import TwitterClient

        text = build_breaking_tweet(company, doc.title)
        twitter = TwitterClient()
        tweet_id = twitter.post(
            db=db,
            text=text,
            post_type=PostType.BREAKING,
            document_id=document_id,
            company_id=company.id,
        )
        if tweet_id:
            log.info("Breaking tweet posted for document %d: %s", document_id, tweet_id)
    except Exception as exc:
        log.error("Failed to post breaking tweet: %s", exc)
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def publish_analysis_article(self, document_id: int, free: bool = False):
    """分析完了時 → note記事投稿 + 分析完了ツイート"""
    if not _should_auto_note():
        log.info("Auto note disabled, skipping analysis article")
        return

    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            log.warning("Document %d not found", document_id)
            return

        analysis = (
            db.query(AnalysisResult)
            .filter(AnalysisResult.document_id == document_id)
            .first()
        )
        if not analysis:
            log.warning("No analysis result for document %d", document_id)
            return

        company = db.query(Company).filter(Company.id == doc.company_id).first()
        if not company:
            return

        # Check duplicate
        existing = (
            db.query(PostLog)
            .filter(
                PostLog.platform == PostPlatform.NOTE,
                PostLog.document_id == document_id,
            )
            .first()
        )
        if existing:
            log.info("Article already published for document %d", document_id)
            return

        from app.publish.article import ArticleGenerator
        from app.publish.note_client import NoteClient

        gen = ArticleGenerator()
        article = gen.generate_analysis_article(
            document=doc, analysis=analysis, company=company, free=free
        )

        client = NoteClient()
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(client.ensure_logged_in())
            result = loop.run_until_complete(
                client.create_and_publish(
                    title=article.title,
                    html_body=article.body_html,
                    price=article.price,
                    hashtags=article.hashtags,
                )
            )
        finally:
            loop.close()

        note_url = result.get("note_url", "")

        post_log = PostLog(
            platform=PostPlatform.NOTE,
            post_type=PostType.ANALYSIS,
            external_id=note_url,
            document_id=document_id,
            company_id=company.id,
            content_preview=article.title[:200],
        )
        db.add(post_log)
        db.commit()
        log.info("Article published: %s → %s", article.title, note_url)

        # Post analysis tweet with note URL
        if _should_auto_tweet():
            from app.social.templates import build_analysis_tweet
            from app.social.twitter import TwitterClient

            text = build_analysis_tweet(company, analysis, note_url)
            twitter = TwitterClient()
            twitter.post(
                db=db,
                text=text,
                post_type=PostType.ANALYSIS,
                document_id=document_id,
                company_id=company.id,
            )

    except Exception as exc:
        log.error("Failed to publish analysis article: %s", exc)
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task
def publish_daily_summary(date_str: str | None = None):
    """日次まとめ (Celery Beat 毎日20:00)"""
    db = SessionLocal()
    try:
        target_date = (
            date.fromisoformat(date_str) if date_str else date.today()
        )
        d_str = target_date.isoformat()

        results = (
            db.query(AnalysisResult, Document, Company)
            .join(Document, AnalysisResult.document_id == Document.id)
            .join(Company, Document.company_id == Company.id)
            .filter(Document.publish_date == d_str)
            .all()
        )

        if not results:
            log.info("No analyses found for %s, skipping daily summary", d_str)
            return

        analyses = [(doc, analysis, company) for analysis, doc, company in results]
        companies = [company for _, _, company in analyses]

        # Daily tweet
        if _should_auto_tweet():
            from app.social.templates import build_daily_tweet
            from app.social.twitter import TwitterClient

            text = build_daily_tweet(target_date, companies)
            twitter = TwitterClient()
            twitter.post_daily(db=db, text=text, target_date=target_date)

        # Daily note article
        if _should_auto_note():
            from app.publish.article import ArticleGenerator
            from app.publish.note_client import NoteClient

            gen = ArticleGenerator()
            article = gen.generate_daily_summary(target_date, analyses)

            client = NoteClient()
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(client.ensure_logged_in())
                result = loop.run_until_complete(
                    client.create_and_publish(
                        title=article.title,
                        html_body=article.body_html,
                        price=0,
                        hashtags=article.hashtags,
                    )
                )
            finally:
                loop.close()

            note_url = result.get("note_url", "")
            post_log = PostLog(
                platform=PostPlatform.NOTE,
                post_type=PostType.DAILY_SUMMARY,
                external_id=note_url,
                content_preview=article.title[:200],
                metadata_={"date": d_str, "count": len(analyses)},
            )
            db.add(post_log)
            db.commit()
            log.info("Daily summary published: %s", note_url)

    except Exception as exc:
        log.error("Failed to publish daily summary: %s", exc)
    finally:
        db.close()


@celery_app.task
def publish_weekly_summary():
    """週次まとめ (Celery Beat 毎週日曜10:00)"""
    if not _should_auto_tweet():
        return

    db = SessionLocal()
    try:
        today = date.today()
        week_start = today - timedelta(days=7)

        results = (
            db.query(AnalysisResult, Company)
            .join(Document, AnalysisResult.document_id == Document.id)
            .join(Company, Document.company_id == Company.id)
            .filter(Document.publish_date >= week_start.isoformat())
            .filter(Document.publish_date <= today.isoformat())
            .all()
        )

        if not results:
            log.info("No analyses found for the week, skipping weekly summary")
            return

        highlights = []
        for analysis, company in results:
            pos = analysis.sentiment_positive or 0
            neg = analysis.sentiment_negative or 0
            if pos >= 0.7:
                sentiment = "very_positive"
            elif pos >= 0.5:
                sentiment = "positive"
            elif neg >= 0.7:
                sentiment = "very_negative"
            elif neg >= 0.5:
                sentiment = "negative"
            else:
                sentiment = "neutral"
            highlights.append({
                "company_name": company.name,
                "ticker_code": company.ticker_code,
                "sentiment": sentiment,
            })

        # Sort by most extreme sentiment first
        highlights.sort(
            key=lambda h: abs(
                {"very_positive": 2, "positive": 1, "neutral": 0, "negative": -1, "very_negative": -2}
                .get(h["sentiment"], 0)
            ),
            reverse=True,
        )

        from app.social.templates import build_weekly_tweet
        from app.social.twitter import TwitterClient

        text = build_weekly_tweet(week_start, highlights[:5])
        twitter = TwitterClient()
        twitter.post_daily(db=db, text=text, target_date=today)

        log.info("Weekly summary tweet posted")

    except Exception as exc:
        log.error("Failed to publish weekly summary: %s", exc)
    finally:
        db.close()
