#!/usr/bin/env python3
"""EDINET crawl script - replaces Celery task for GitHub Actions."""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.crawler.edinet import EDINETCrawler
from app.models.company import Company
from app.models.document import Document, DocumentType

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def save_crawl_results(results: list, db) -> int:
    saved_count = 0
    for result in results:
        company_code = result.get("company_code")
        if not company_code:
            continue

        company = db.query(Company).filter(
            Company.ticker_code == company_code
        ).first()

        # 企業が未登録の場合は自動作成
        if not company:
            company = Company(
                ticker_code=company_code,
                name=result.get("filer_name") or f"企業{company_code}",
            )
            db.add(company)
            db.flush()
            logger.info(f"New company registered: {company_code} - {company.name}")

        existing = db.query(Document).filter(
            Document.source_url == result.get("source_url")
        ).first()
        if existing:
            continue

        doc_type_str = result.get("doc_type", "other")
        try:
            doc_type = DocumentType(doc_type_str)
        except ValueError:
            doc_type = DocumentType.OTHER

        document = Document(
            company_id=company.id,
            title=result.get("title", ""),
            doc_type=doc_type,
            publish_date=result.get("publish_date", ""),
            source_url=result.get("source_url", ""),
        )
        db.add(document)
        saved_count += 1

    db.commit()
    return saved_count


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    logger.info(f"Starting EDINET crawling for {days} days")

    crawler = EDINETCrawler()
    results = crawler.crawl(days=days)

    db = SessionLocal()
    try:
        saved_count = save_crawl_results(results, db)
        logger.info(f"EDINET crawling completed. Crawled: {len(results)}, Saved: {saved_count}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
