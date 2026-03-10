#!/usr/bin/env python3
"""Morning publish: auto-detect unpublished analyses and publish breaking articles.

Finds documents with analyses that haven't been published to note.com yet,
then publishes breaking/analysis articles for each.
"""

import asyncio
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.analysis import AnalysisResult
from app.models.company import Company
from app.models.post_log import PostLog, PostPlatform, PostType

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MAX_ARTICLES_PER_RUN = 10
PUBLISH_INTERVAL = 10  # seconds between posts


async def main():
    from app.publish.ai_generator import AIArticleGenerator
    from app.publish.note_client import NoteClient

    db = SessionLocal()
    try:
        # Find analyses that haven't been published to note.com yet
        published_doc_ids = (
            db.query(PostLog.document_id)
            .filter(PostLog.platform == PostPlatform.NOTE)
            .filter(PostLog.document_id.isnot(None))
            .all()
        )
        published_ids = {row[0] for row in published_doc_ids}

        unpublished = (
            db.query(AnalysisResult, Document, Company)
            .join(Document, AnalysisResult.document_id == Document.id)
            .join(Company, Document.company_id == Company.id)
            .filter(AnalysisResult.document_id.notin_(published_ids) if published_ids else True)
            .order_by(Document.publish_date.desc())
            .limit(MAX_ARTICLES_PER_RUN)
            .all()
        )

        if not unpublished:
            logger.info("No unpublished analyses found")
            return

        logger.info(f"Found {len(unpublished)} unpublished analyses")

        gen = AIArticleGenerator()
        client = NoteClient()

        async with client:
            await client.ensure_logged_in()

            for analysis, doc, company in unpublished:
                try:
                    article = gen.generate_analysis_article(
                        document=doc,
                        analysis=analysis,
                        company=company,
                        free=False,
                    )

                    result = await client.create_and_publish(
                        title=article.title,
                        html_body=article.body_html,
                        price=article.price,
                        hashtags=article.hashtags,
                        article_type="analysis",
                    )

                    note_url = result.get("note_url", "")
                    post_log = PostLog(
                        platform=PostPlatform.NOTE,
                        post_type=PostType.ANALYSIS,
                        external_id=note_url,
                        document_id=doc.id,
                        company_id=company.id,
                        content_preview=article.title[:200],
                    )
                    db.add(post_log)
                    db.commit()
                    logger.info(f"Published: {company.name} -> {note_url}")

                    await asyncio.sleep(PUBLISH_INTERVAL)

                except Exception as e:
                    logger.error(f"Failed to publish {company.name}: {e}")
                    continue

    except Exception as e:
        logger.error(f"Morning publish failed: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
