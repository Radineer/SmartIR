from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models.document import Document
from app.schemas.document import DocumentCreate, DocumentResponse

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
    responses={404: {"description": "Not found"}},
)

@router.get("/", response_model=List[DocumentResponse])
def get_documents(
    skip: int = 0,
    limit: int = 100,
    company_id: int = None,
    days: int = 7,
    db: Session = Depends(get_db)
):
    """ドキュメント一覧を取得"""
    query = db.query(Document)
    
    if company_id:
        query = query.filter(Document.company_id == company_id)
    
    # 指定日数分のドキュメントを取得
    if days:
        date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        query = query.filter(Document.publish_date >= date_from)
    
    return query.order_by(Document.publish_date.desc()).offset(skip).limit(limit).all()

@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: int, db: Session = Depends(get_db)):
    """指定したIDのドキュメントを取得"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document

@router.post("/", response_model=DocumentResponse)
def create_document(document: DocumentCreate, db: Session = Depends(get_db)):
    """新規ドキュメントを作成"""
    db_document = Document(**document.model_dump())
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    return db_document 