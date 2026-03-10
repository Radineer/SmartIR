#!/usr/bin/env python3
"""Daily publish script (note.com + X) - replaces Celery task for GitHub Actions."""

import asyncio
import os
import sys
import logging
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.analysis import AnalysisResult
from app.models.company import Company
from app.models.post_log import PostLog, PostPlatform, PostType

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def should_auto_tweet() -> bool:
    return os.getenv("PUBLISH_AUTO_TWEET", "true").lower() == "true"


def should_auto_note() -> bool:
    return os.getenv("PUBLISH_AUTO_NOTE", "true").lower() == "true"


def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else None
    target_date = date.fromisoformat(date_str) if date_str else date.today()
    d_str = target_date.isoformat()

    logger.info(f"Publishing daily summary for {d_str}")

    db = SessionLocal()
    try:
        results = (
            db.query(AnalysisResult, Document, Company)
            .join(Document, AnalysisResult.document_id == Document.id)
            .join(Company, Document.company_id == Company.id)
            .filter(Document.publish_date == d_str)
            .all()
        )

        if not results:
            logger.info(f"No analyses found for {d_str}, skipping")
            return

        analyses = [(doc, analysis, company) for analysis, doc, company in results]
        companies = [company for _, _, company in analyses]
        logger.info(f"Found {len(analyses)} analyses for {d_str}")

        # Daily tweet
        if should_auto_tweet():
            from app.social.templates import build_daily_tweet
            from app.social.twitter import TwitterClient

            text = build_daily_tweet(target_date, companies)
            twitter = TwitterClient()
            twitter.post_daily(db=db, text=text, target_date=target_date)
            logger.info("Daily tweet posted")

        # Daily note article
        if should_auto_note():
            from app.publish.ai_generator import AIArticleGenerator
            from app.publish.note_client import NoteClient

            gen = AIArticleGenerator()
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
                        article_type="daily_summary",
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
            logger.info(f"Daily note article published: {note_url}")

    except Exception as e:
        logger.error(f"Daily publish failed: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
