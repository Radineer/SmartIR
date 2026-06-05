#!/usr/bin/env python3
"""Weekly publish script (X) - replaces Celery task for GitHub Actions."""

import os
import sys
import logging
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.analysis import AnalysisResult
from app.models.company import Company

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    if os.getenv("PUBLISH_AUTO_TWEET", "true").lower() != "true":
        logger.info("Auto tweet disabled, skipping")
        return

    today = date.today()
    week_start = today - timedelta(days=7)

    logger.info(f"Publishing weekly summary for {week_start} - {today}")

    db = SessionLocal()
    try:
        results = (
            db.query(AnalysisResult, Company)
            .join(Document, AnalysisResult.document_id == Document.id)
            .join(Company, Document.company_id == Company.id)
            .filter(Document.publish_date >= week_start.isoformat())
            .filter(Document.publish_date <= today.isoformat())
            .all()
        )

        if not results:
            logger.info("No analyses found for the week, skipping")
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
        logger.info("Weekly summary tweet posted")

    except Exception as e:
        logger.error(f"Weekly publish failed: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
