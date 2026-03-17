#!/usr/bin/env python3
"""TDnet crawl script - replaces Celery task for GitHub Actions."""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.crawler.tdnet import TDNetCrawler
from app.models.company import Company
from app.models.document import Document

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def save_crawl_results(results: list, db) -> int:
    saved_count = 0
    for result in results:
        company = db.query(Company).filter(
            Company.ticker_code == result.get("company_code")
        ).first()
        if not company:
            continue

        existing = db.query(Document).filter(
            Document.source_url == result.get("source_url")
        ).first()
        if existing:
            continue

        document = Document(
            company_id=company.id,
            title=result.get("title", ""),
            doc_type=result.get("doc_type", "other"),
            publish_date=result.get("publish_date", ""),
            source_url=result.get("source_url", ""),
        )
        db.add(document)
        saved_count += 1

    db.commit()
    return saved_count


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    logger.info(f"Starting TDnet crawling for {days} days")

    crawler = TDNetCrawler()
    results = crawler.crawl(days=days)

    db = SessionLocal()
    try:
        saved_count = save_crawl_results(results, db)
        logger.info(f"TDnet crawling completed. Crawled: {len(results)}, Saved: {saved_count}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
