from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional

from app.core.database import get_db
from app.models.company import Company
from app.models.document import Document
from app.schemas.company import CompanyResponse
from app.schemas.document import DocumentResponse
from app.schemas.public import (
    StockListResponse,
    StockDetailResponse,
    StockAnalysisResponse,
    SectorListResponse,
    SectorStocksResponse,
)

router = APIRouter(
    prefix="/public",
    tags=["public"],
    responses={404: {"description": "Not found"}},
)


@router.get("/stocks", response_model=StockListResponse)
def get_all_stocks(
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=5000),
    sector: Optional[str] = Query(None, description="業種でフィルタ"),
    db: Session = Depends(get_db)
):
    """
    全銘柄一覧を取得（SEO用）
    - ticker_codeでソート
    - 業種フィルタ対応
    """
    query = db.query(Company)

    if sector:
        query = query.filter(Company.sector == sector)

    total = query.count()
    stocks = query.order_by(Company.ticker_code).offset(skip).limit(limit).all()

    return StockListResponse(
        total=total,
        stocks=stocks
    )


@router.get("/stocks/{ticker_code}", response_model=StockDetailResponse)
def get_stock_by_ticker(ticker_code: str, db: Session = Depends(get_db)):
    """
    証券コードで銘柄詳細を取得
    - 最新のドキュメント情報も含む
    """
    company = db.query(Company).filter(Company.ticker_code == ticker_code).first()
    if company is None:
        raise HTTPException(status_code=404, detail="Stock not found")

    # 最新のドキュメントを5件取得
    recent_documents = (
        db.query(Document)
        .filter(Document.company_id == company.id)
        .order_by(Document.publish_date.desc())
        .limit(5)
        .all()
    )

    # ドキュメントのdoc_typeをstring値に変換
    documents_data = [
        {
            "id": doc.id,
            "company_id": doc.company_id,
            "title": doc.title,
            "doc_type": doc.doc_type.value if hasattr(doc.doc_type, 'value') else str(doc.doc_type),
            "publish_date": doc.publish_date,
            "source_url": doc.source_url,
            "storage_url": doc.storage_url,
            "is_processed": doc.is_processed,
            "raw_text": doc.raw_text,
            "created_at": doc.created_at,
            "updated_at": doc.updated_at,
        }
        for doc in recent_documents
    ]

    return StockDetailResponse(
        id=company.id,
        name=company.name,
        ticker_code=company.ticker_code,
        sector=company.sector,
        industry=company.industry,
        description=company.description,
        website_url=company.website_url,
        created_at=company.created_at,
        updated_at=company.updated_at,
        recent_documents=documents_data,
        document_count=db.query(Document).filter(Document.company_id == company.id).count()
    )


@router.get("/stocks/{ticker_code}/documents")
def get_stock_documents(
    ticker_code: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    銘柄のドキュメント一覧を取得
    """
    company = db.query(Company).filter(Company.ticker_code == ticker_code).first()
    if company is None:
        raise HTTPException(status_code=404, detail="Stock not found")

    documents = (
        db.query(Document)
        .filter(Document.company_id == company.id)
        .order_by(Document.publish_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    # ドキュメントのdoc_typeをstring値に変換
    return [
        {
            "id": doc.id,
            "company_id": doc.company_id,
            "title": doc.title,
            "doc_type": doc.doc_type.value if hasattr(doc.doc_type, 'value') else str(doc.doc_type),
            "publish_date": doc.publish_date,
            "source_url": doc.source_url,
            "storage_url": doc.storage_url,
            "is_processed": doc.is_processed,
            "raw_text": doc.raw_text,
            "created_at": doc.created_at,
            "updated_at": doc.updated_at,
        }
        for doc in documents
    ]


@router.get("/stocks/{ticker_code}/analysis", response_model=Optional[StockAnalysisResponse])
def get_stock_latest_analysis(ticker_code: str, db: Session = Depends(get_db)):
    """
    銘柄の最新分析結果を取得
    - 最新のドキュメントに紐づく分析結果を返す
    """
    from app.models.analysis import AnalysisResult

    company = db.query(Company).filter(Company.ticker_code == ticker_code).first()
    if company is None:
        raise HTTPException(status_code=404, detail="Stock not found")

    # 最新のドキュメントIDを取得
    latest_document = (
        db.query(Document)
        .filter(Document.company_id == company.id)
        .order_by(Document.publish_date.desc())
        .first()
    )

    if latest_document is None:
        return None

    # 分析結果を取得
    analysis = (
        db.query(AnalysisResult)
        .filter(AnalysisResult.document_id == latest_document.id)
        .order_by(AnalysisResult.created_at.desc())
        .first()
    )

    if analysis is None:
        return None

    return StockAnalysisResponse(
        document_id=analysis.document_id,
        document_title=latest_document.title,
        publish_date=latest_document.publish_date,
        summary=analysis.summary,
        sentiment_positive=analysis.sentiment_positive,
        sentiment_negative=analysis.sentiment_negative,
        sentiment_neutral=analysis.sentiment_neutral,
        key_points=analysis.key_points,
        analyzed_at=analysis.created_at
    )


@router.get("/sectors", response_model=SectorListResponse)
def get_all_sectors(db: Session = Depends(get_db)):
    """
    全業種一覧を取得（SEO用）
    - 各業種の銘柄数も返す
    """
    sectors = (
        db.query(
            Company.sector,
            func.count(Company.id).label("stock_count")
        )
        .filter(Company.sector.isnot(None))
        .group_by(Company.sector)
        .order_by(Company.sector)
        .all()
    )

    return SectorListResponse(
        sectors=[
            {"name": sector, "stock_count": count}
            for sector, count in sectors
        ]
    )


@router.get("/sectors/{sector}", response_model=SectorStocksResponse)
def get_sector_stocks(
    sector: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """
    業種別銘柄一覧を取得
    """
    query = db.query(Company).filter(Company.sector == sector)
    total = query.count()

    if total == 0:
        raise HTTPException(status_code=404, detail="Sector not found")

    stocks = query.order_by(Company.ticker_code).offset(skip).limit(limit).all()

    return SectorStocksResponse(
        sector=sector,
        total=total,
        stocks=stocks
    )


@router.get("/ticker-codes", response_model=List[str])
def get_all_ticker_codes(db: Session = Depends(get_db)):
    """
    全証券コード一覧を取得（サイトマップ生成用）
    """
    codes = db.query(Company.ticker_code).order_by(Company.ticker_code).all()
    return [code[0] for code in codes]
