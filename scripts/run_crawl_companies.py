#!/usr/bin/env python3
"""Company site crawl script - replaces Celery task for GitHub Actions."""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.crawler.company_site import CompanySiteCrawler
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
    logger.info("Starting company site crawling for all companies")

    db = SessionLocal()
    try:
        companies = db.query(Company).filter(Company.website_url.isnot(None)).all()
        logger.info(f"Found {len(companies)} companies with websites")

        crawler = CompanySiteCrawler()
        total_saved = 0

        for company in companies:
            try:
                results = crawler.crawl(
                    company_url=company.website_url,
                    company_code=company.ticker_code,
                    max_items=20,
                )
                saved = save_crawl_results(results, db)
                total_saved += saved
                logger.info(f"  {company.name}: crawled {len(results)}, saved {saved}")
            except Exception as e:
                logger.error(f"  {company.name}: failed - {e}")
                db.rollback()

        logger.info(f"Company site crawling completed. Total saved: {total_saved}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
