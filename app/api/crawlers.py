from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field
import logging

from app.core.database import get_db
from app.core.deps import get_current_active_user, require_admin
from app.models.user import User
from app.models.company import Company
from app.models.document import Document
from app.crawler.tdnet import TDNetCrawler
from app.crawler.edinet import EDINETCrawler
from app.crawler.company_site import CompanySiteCrawler

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/crawlers",
    tags=["crawlers"],
)


# リクエスト/レスポンススキーマ
class CrawlRequest(BaseModel):
    """クロールリクエスト"""
    days: int = Field(default=1, ge=1, le=30, description="取得日数")


class CompanySiteCrawlRequest(BaseModel):
    """企業サイトクロールリクエスト"""
    company_id: int = Field(..., description="企業ID")
    max_items: int = Field(default=20, ge=1, le=100, description="最大取得件数")


class CrawlResult(BaseModel):
    """クロール結果"""
    company_code: str
    title: str
    publish_date: str
    doc_type: str
    source_url: str


class CrawlResponse(BaseModel):
    """クロールレスポンス"""
    status: str
    message: str
    count: int
    results: List[CrawlResult]


class CrawlStatusResponse(BaseModel):
    """クロールステータスレスポンス"""
    tdnet: dict
    edinet: dict
    company_sites: dict


# エンドポイント
@router.post("/tdnet/run", response_model=CrawlResponse)
def run_tdnet_crawler(
    request: CrawlRequest,
    current_user: User = Depends(require_admin)
):
    """TDnetクローラーを実行（管理者のみ）"""
    try:
        crawler = TDNetCrawler()
        results = crawler.crawl(days=request.days)

        return CrawlResponse(
            status="success",
            message=f"TDnet crawling completed. Found {len(results)} documents.",
            count=len(results),
            results=[CrawlResult(**r) for r in results]
        )
    except Exception as e:
        logger.error(f"TDnet crawling failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Crawling failed: {str(e)}")


@router.post("/edinet/run", response_model=CrawlResponse)
def run_edinet_crawler(
    request: CrawlRequest,
    doc_type_codes: Optional[List[str]] = None,
    current_user: User = Depends(require_admin)
):
    """EDINETクローラーを実行（管理者のみ）"""
    try:
        crawler = EDINETCrawler()
        results = crawler.crawl(days=request.days, doc_type_codes=doc_type_codes)

        return CrawlResponse(
            status="success",
            message=f"EDINET crawling completed. Found {len(results)} documents.",
            count=len(results),
            results=[CrawlResult(**{k: v for k, v in r.items() if k in CrawlResult.model_fields}) for r in results]
        )
    except Exception as e:
        logger.error(f"EDINET crawling failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Crawling failed: {str(e)}")


@router.post("/company-site/run", response_model=CrawlResponse)
def run_company_site_crawler(
    request: CompanySiteCrawlRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """企業サイトクローラーを実行（管理者のみ）"""
    # 企業情報を取得
    company = db.query(Company).filter(Company.id == request.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    if not company.website_url:
        raise HTTPException(status_code=400, detail="Company website URL not set")

    try:
        crawler = CompanySiteCrawler()
        results = crawler.crawl(
            company_url=company.website_url,
            company_code=company.ticker_code,
            max_items=request.max_items
        )

        return CrawlResponse(
            status="success",
            message=f"Company site crawling completed. Found {len(results)} documents.",
            count=len(results),
            results=[CrawlResult(**r) for r in results]
        )
    except Exception as e:
        logger.error(f"Company site crawling failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Crawling failed: {str(e)}")


@router.post("/save-results")
def save_crawl_results(
    results: List[CrawlResult],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """クロール結果をデータベースに保存（管理者のみ）"""
    saved_count = 0
    skipped_count = 0

    for result in results:
        # 企業を検索
        company = db.query(Company).filter(
            Company.ticker_code == result.company_code
        ).first()

        if not company:
            skipped_count += 1
            continue

        # 重複チェック
        existing = db.query(Document).filter(
            Document.source_url == result.source_url
        ).first()

        if existing:
            skipped_count += 1
            continue

        # ドキュメント作成
        document = Document(
            company_id=company.id,
            title=result.title,
            doc_type=result.doc_type,
            publish_date=result.publish_date,
            source_url=result.source_url,
        )
        db.add(document)
        saved_count += 1

    db.commit()

    return {
        "status": "success",
        "saved": saved_count,
        "skipped": skipped_count
    }


@router.get("/status", response_model=CrawlStatusResponse)
def get_crawl_status(current_user: User = Depends(get_current_active_user)):
    """クローラーのステータスを取得"""
    return CrawlStatusResponse(
        tdnet={
            "name": "TDNet Crawler",
            "status": "ready",
            "last_run": None,
        },
        edinet={
            "name": "EDINET Crawler",
            "status": "ready",
            "last_run": None,
        },
        company_sites={
            "name": "Company Site Crawler",
            "status": "ready",
            "last_run": None,
        }
    )
