from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.company import Company
from app.models.document import Document
from app.crawler.tdnet import TDNetCrawler
from app.crawler.edinet import EDINETCrawler
from app.crawler.company_site import CompanySiteCrawler
import logging

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def crawl_tdnet(self, days: int = 1):
    """TDnetクローリングタスク"""
    try:
        logger.info(f"Starting TDnet crawling for {days} days")
        crawler = TDNetCrawler()
        results = crawler.crawl(days=days)

        # 結果をDBに保存
        saved_count = save_crawl_results(results)

        logger.info(f"TDnet crawling completed. Saved {saved_count} documents.")
        return {"status": "success", "crawled": len(results), "saved": saved_count}

    except Exception as e:
        logger.error(f"TDnet crawling failed: {str(e)}")
        self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def crawl_edinet(self, days: int = 1):
    """EDINETクローリングタスク"""
    try:
        logger.info(f"Starting EDINET crawling for {days} days")
        crawler = EDINETCrawler()
        results = crawler.crawl(days=days)

        # 結果をDBに保存
        saved_count = save_crawl_results(results)

        logger.info(f"EDINET crawling completed. Saved {saved_count} documents.")
        return {"status": "success", "crawled": len(results), "saved": saved_count}

    except Exception as e:
        logger.error(f"EDINET crawling failed: {str(e)}")
        self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def crawl_company_site(self, company_id: int, max_items: int = 20):
    """企業サイトクローリングタスク"""
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company or not company.website_url:
            return {"status": "skipped", "reason": "No company or website URL"}

        logger.info(f"Starting company site crawling for {company.name}")
        crawler = CompanySiteCrawler()
        results = crawler.crawl(
            company_url=company.website_url,
            company_code=company.ticker_code,
            max_items=max_items
        )

        # 結果をDBに保存
        saved_count = save_crawl_results(results, db)

        logger.info(f"Company site crawling completed for {company.name}. Saved {saved_count} documents.")
        return {"status": "success", "company": company.name, "crawled": len(results), "saved": saved_count}

    except Exception as e:
        logger.error(f"Company site crawling failed for company_id={company_id}: {str(e)}")
        self.retry(exc=e, countdown=60)
    finally:
        db.close()


@celery_app.task
def crawl_all_company_sites():
    """全企業サイトをクローリング"""
    db = SessionLocal()
    try:
        companies = db.query(Company).filter(Company.website_url.isnot(None)).all()
        logger.info(f"Starting crawling for {len(companies)} company sites")

        for company in companies:
            # 各企業のクローリングを別タスクとして実行
            crawl_company_site.delay(company.id)

        return {"status": "started", "companies": len(companies)}

    finally:
        db.close()


def save_crawl_results(results: list, db=None) -> int:
    """クロール結果をデータベースに保存"""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    saved_count = 0

    try:
        for result in results:
            # 企業を検索
            company = db.query(Company).filter(
                Company.ticker_code == result.get("company_code")
            ).first()

            if not company:
                continue

            # 重複チェック
            existing = db.query(Document).filter(
                Document.source_url == result.get("source_url")
            ).first()

            if existing:
                continue

            # ドキュメント作成
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

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save crawl results: {str(e)}")
        raise

    finally:
        if close_db:
            db.close()

    return saved_count
