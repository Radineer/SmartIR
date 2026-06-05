from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.pdf_utils import PDFExtractor
from app.services.llm_analyzer import LLMAnalyzer
from app.services.vtuber_script import VTuberScriptGenerator
from app.models.document import Document
from app.models.company import Company
import logging

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def extract_document_text(self, document_id: int):
    """ドキュメントからテキストを抽出"""
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return {"status": "error", "reason": "Document not found"}

        if document.raw_text:
            return {"status": "skipped", "reason": "Text already extracted"}

        if not document.source_url:
            return {"status": "error", "reason": "No source URL"}

        logger.info(f"Extracting text from document {document_id}")
        text = PDFExtractor.extract_from_url(document.source_url)

        if text:
            document.raw_text = text
            document.is_processed = True
            db.commit()
            logger.info(f"Text extraction completed for document {document_id}")
            return {"status": "success", "document_id": document_id, "text_length": len(text)}
        else:
            return {"status": "error", "reason": "Text extraction failed"}

    except Exception as e:
        logger.error(f"Text extraction failed for document {document_id}: {str(e)}")
        self.retry(exc=e, countdown=60)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def analyze_document(self, document_id: int):
    """ドキュメントを分析"""
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return {"status": "error", "reason": "Document not found"}

        # テキストがなければ抽出
        if not document.raw_text:
            if document.source_url:
                text = PDFExtractor.extract_from_url(document.source_url)
                if text:
                    document.raw_text = text
                    db.commit()
                else:
                    return {"status": "error", "reason": "Text extraction failed"}
            else:
                return {"status": "error", "reason": "No text available"}

        logger.info(f"Analyzing document {document_id}")
        analyzer = LLMAnalyzer()
        result = analyzer.analyze(document.raw_text, document.doc_type.value)

        if result:
            logger.info(f"Analysis completed for document {document_id}")
            return {
                "status": "success",
                "document_id": document_id,
                "summary": result.get("summary", "")[:200],  # 要約の先頭200文字
                "sentiment": result.get("sentiment", {}),
            }
        else:
            return {"status": "error", "reason": "Analysis failed"}

    except Exception as e:
        logger.error(f"Analysis failed for document {document_id}: {str(e)}")
        self.retry(exc=e, countdown=120)
    finally:
        db.close()


@celery_app.task
def analyze_unprocessed_documents(batch_size: int = 10):
    """未処理ドキュメントをバッチ分析"""
    db = SessionLocal()
    try:
        # 未処理のドキュメントを取得
        documents = db.query(Document).filter(
            Document.is_processed == False,
            Document.source_url.isnot(None)
        ).limit(batch_size).all()

        logger.info(f"Found {len(documents)} unprocessed documents")

        for doc in documents:
            # 各ドキュメントの分析を別タスクとして実行
            analyze_document.delay(doc.id)

        return {"status": "started", "documents": len(documents)}

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def generate_vtuber_script(self, document_id: int):
    """ドキュメントからVTuber台本を生成"""
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return {"status": "error", "reason": "Document not found"}

        company = db.query(Company).filter(Company.id == document.company_id).first()
        if not company:
            return {"status": "error", "reason": "Company not found"}

        # テキストがなければ抽出
        if not document.raw_text:
            if document.source_url:
                text = PDFExtractor.extract_from_url(document.source_url)
                if text:
                    document.raw_text = text
                    db.commit()
                else:
                    return {"status": "error", "reason": "Text extraction failed"}
            else:
                return {"status": "error", "reason": "No text available"}

        logger.info(f"Generating VTuber script for document {document_id}")

        # まず分析を実行
        analyzer = LLMAnalyzer()
        analysis_result = analyzer.analyze(document.raw_text, document.doc_type.value)

        if not analysis_result:
            return {"status": "error", "reason": "Analysis failed"}

        # 台本生成
        company_info = {
            "name": company.name,
            "ticker_code": company.ticker_code,
            "sector": company.sector or "不明",
        }

        generator = VTuberScriptGenerator()
        script_result = generator.generate_script(analysis_result, company_info)

        if script_result:
            logger.info(f"VTuber script generated for document {document_id}")
            return {
                "status": "success",
                "document_id": document_id,
                "company_name": company.name,
                "script_length": len(script_result.get("script", "")),
            }
        else:
            return {"status": "error", "reason": "Script generation failed"}

    except Exception as e:
        logger.error(f"Script generation failed for document {document_id}: {str(e)}")
        self.retry(exc=e, countdown=120)
    finally:
        db.close()
