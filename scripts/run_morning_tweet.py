#!/usr/bin/env python3
"""Morning tweet: post breaking news tweets for recently published articles."""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.company import Company
from app.models.post_log import PostLog, PostPlatform, PostType

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    from app.social.templates import build_analysis_tweet
    from app.social.twitter import TwitterClient
    from app.models.analysis import AnalysisResult

    db = SessionLocal()
    try:
        # Find note articles published today that haven't been tweeted
        from datetime import date, datetime
        today = date.today()

        note_logs = (
            db.query(PostLog)
            .filter(PostLog.platform == PostPlatform.NOTE)
            .filter(PostLog.post_type == PostType.ANALYSIS)
            .filter(PostLog.posted_at >= datetime.combine(today, datetime.min.time()))
            .all()
        )

        tweeted_doc_ids = {
            row[0] for row in
            db.query(PostLog.document_id)
            .filter(PostLog.platform == PostPlatform.TWITTER)
            .filter(PostLog.document_id.isnot(None))
            .filter(PostLog.posted_at >= datetime.combine(today, datetime.min.time()))
            .all()
        }

        twitter = TwitterClient()

        for log_entry in note_logs:
            if log_entry.document_id in tweeted_doc_ids:
                continue

            doc = db.query(Document).get(log_entry.document_id)
            if not doc:
                continue

            company = db.query(Company).get(doc.company_id)
            if not company:
                continue

            analysis = db.query(AnalysisResult).filter_by(document_id=doc.id).first()
            if not analysis:
                continue

            note_url = log_entry.external_id or ""
            text = build_analysis_tweet(company, analysis, note_url)

            try:
                twitter.post(
                    db=db,
                    text=text,
                    post_type=PostType.ANALYSIS,
                    document_id=doc.id,
                    company_id=company.id,
                )
                logger.info(f"Tweeted: {company.name}")
            except Exception as e:
                logger.error(f"Tweet failed for {company.name}: {e}")

    except Exception as e:
        logger.error(f"Morning tweet failed: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
