from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import time
import logging

from app.core.database import get_db
from app.core.pdf_utils import PDFExtractor
from app.services.llm_analyzer import LLMAnalyzer
from app.models.document import Document
from app.models.company import Company
from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisResponse,
    SentimentScore,
    DocumentAnalysisRequest,
    PipelineRequest,
    PipelineResponse,
)
from app.schemas.pdf import (
    PDFExtractionRequest,
    PDFExtractionResponse,
    ExtractionMethod,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/analysis",
    tags=["analysis"],
    responses={404: {"description": "Not found"}},
)

# サービスのインスタンス
llm_analyzer = LLMAnalyzer()


@router.post("/extract-pdf", response_model=PDFExtractionResponse)
def extract_pdf(request: PDFExtractionRequest):
    """PDFからテキストを抽出"""
    start_time = time.time()

    text = PDFExtractor.extract_from_url(request.url)

    if text is None:
        raise HTTPException(status_code=400, detail="PDF extraction failed")

    processing_time = time.time() - start_time

    return PDFExtractionResponse(
        text=text,
        source_url=request.url,
        extraction_method=ExtractionMethod.DIRECT,
        processing_time=round(processing_time, 2)
    )


@router.post("/analyze", response_model=AnalysisResponse)
def analyze_text(request: AnalysisRequest):
    """テキストを分析（要約・センチメント）"""
    start_time = time.time()

    result = llm_analyzer.analyze(request.text, request.doc_type)

    if result is None:
        raise HTTPException(status_code=500, detail="Analysis failed")

    processing_time = time.time() - start_time

    return AnalysisResponse(
        summary=result["summary"],
        sentiment=SentimentScore(**result["sentiment"]),
        key_points=result["key_points"],
        processing_time=round(processing_time, 2)
    )


@router.post("/analyze-document", response_model=AnalysisResponse)
def analyze_document(request: DocumentAnalysisRequest, db: Session = Depends(get_db)):
    """ドキュメントIDを指定して分析"""
    start_time = time.time()

    # ドキュメント取得
    document = db.query(Document).filter(Document.id == request.document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # テキストがない場合はPDFから抽出
    text = document.raw_text
    if not text and document.source_url:
        text = PDFExtractor.extract_from_url(document.source_url)
        if text:
            # 抽出したテキストを保存
            document.raw_text = text
            document.is_processed = True
            db.commit()

    if not text:
        raise HTTPException(status_code=400, detail="No text available for analysis")

    # 分析実行
    result = llm_analyzer.analyze(text, document.doc_type.value)

    if result is None:
        raise HTTPException(status_code=500, detail="Analysis failed")

    processing_time = time.time() - start_time

    return AnalysisResponse(
        summary=result["summary"],
        sentiment=SentimentScore(**result["sentiment"]),
        key_points=result["key_points"],
        processing_time=round(processing_time, 2)
    )


@router.post("/pipeline", response_model=PipelineResponse)
def run_pipeline(request: PipelineRequest, db: Session = Depends(get_db)):
    """統合パイプライン: PDF抽出 → 分析"""
    start_time = time.time()

    # 企業存在確認
    company = db.query(Company).filter(Company.id == request.company_id).first()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    # PDF抽出
    text = PDFExtractor.extract_from_url(request.pdf_url)
    if text is None:
        raise HTTPException(status_code=400, detail="PDF extraction failed")

    # 分析実行
    result = llm_analyzer.analyze(text, request.doc_type)
    if result is None:
        raise HTTPException(status_code=500, detail="Analysis failed")

    processing_time = time.time() - start_time

    return PipelineResponse(
        extracted_text=text,
        analysis=AnalysisResponse(
            summary=result["summary"],
            sentiment=SentimentScore(**result["sentiment"]),
            key_points=result["key_points"],
            processing_time=None
        ),
        processing_time=round(processing_time, 2)
    )
