#!/usr/bin/env python3
"""3段階決算分析バッチスクリプト。

Quick(Haiku) → Standard(Sonnet) → Deep(Opus) の3フェーズで分析を実行。
GitHub Actions から呼び出される。
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.core.pdf_utils import PDFExtractor
from app.services.deep_analyzer import DeepAnalyzer
from app.models.document import Document
from app.models.company import Company

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    batch_size = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    depth = sys.argv[2] if len(sys.argv) > 2 else "standard"  # quick / standard / deep

    if depth not in ("quick", "standard", "deep"):
        logger.error("Invalid depth: %s (use quick/standard/deep)", depth)
        sys.exit(1)

    db = SessionLocal()
    analyzer = DeepAnalyzer()

    try:
        documents = (
            db.query(Document)
            .filter(
                Document.is_processed == False,
                Document.source_url.isnot(None),
            )
            .limit(batch_size)
            .all()
        )

        logger.info("Found %d unprocessed documents (depth=%s)", len(documents), depth)

        success_count = 0

        for doc in documents:
            try:
                # テキスト未抽出なら抽出
                if not doc.raw_text:
                    text = PDFExtractor.extract_from_url(doc.source_url)
                    if not text:
                        logger.warning("Document %s: text extraction failed", doc.id)
                        continue
                    doc.raw_text = text
                    db.commit()

                company = db.query(Company).filter(Company.id == doc.company_id).first()
                if not company:
                    logger.warning("Document %s: company not found", doc.id)
                    continue

                # PDF表抽出（standard以上で実行）
                table_data = None
                if depth in ("standard", "deep") and doc.source_url:
                    try:
                        import asyncio
                        from app.core.pdf_table_extractor import extract_financial_tables
                        table_data = asyncio.run(extract_financial_tables(doc.source_url))
                        if table_data:
                            logger.info("Document %s: PDF table extraction succeeded", doc.id)
                    except Exception as e:
                        logger.warning("Document %s: PDF table extraction failed: %s", doc.id, e)

                # 分析実行
                if depth == "quick":
                    result = analyzer.analyze_quick(doc, company)
                elif depth == "standard":
                    result = analyzer.analyze_standard(doc, company)
                else:
                    result = analyzer.analyze_deep(doc, company, db)

                if not result:
                    logger.warning("Document %s: analysis returned no result", doc.id)
                    continue

                # PDF表データをマージ
                if table_data:
                    result["extracted_tables"] = table_data

                # 保存
                ar = analyzer.save_result(db, doc, result)
                analyzer.save_prediction(db, ar, company, result)

                doc.is_processed = True
                db.commit()

                success_count += 1
                logger.info(
                    "Document %s (%s): analyzed [%s] impact=%s conf=%.2f",
                    doc.id,
                    company.ticker_code,
                    depth,
                    result.get("stock_impact", "?"),
                    result.get("stock_impact_confidence", 0),
                )

            except Exception as e:
                logger.error("Document %s: failed - %s", doc.id, e)
                db.rollback()

        logger.info("Analysis completed. %d/%d succeeded (depth=%s)", success_count, len(documents), depth)

    finally:
        db.close()


if __name__ == "__main__":
    main()
