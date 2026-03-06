"""API endpoints for note.com publishing and X (Twitter) posting."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel as PydanticBase
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User
from app.models.document import Document
from app.models.analysis import AnalysisResult
from app.models.company import Company
from app.models.post_log import PostLog, PostPlatform, PostType
from app.publish.note_client import NoteClient, NoteAuthError, NotePublishError
from app.publish.article import ArticleGenerator
from app.social.twitter import TwitterClient
from app.social.templates import (
    build_breaking_tweet,
    build_analysis_tweet,
    build_daily_tweet,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/publish", tags=["publish"])

article_gen = ArticleGenerator()


class PublishRequest(PydanticBase):
    free: bool = False
    dry_run: bool = False


class TweetRequest(PydanticBase):
    dry_run: bool = False


class DailyRequest(PydanticBase):
    date: str | None = None
    dry_run: bool = False


@router.post("/note/article/{document_id}")
async def publish_note_article(
    document_id: int,
    req: PublishRequest = PublishRequest(),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """note.comに分析記事を投稿"""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    analysis = (
        db.query(AnalysisResult)
        .filter(AnalysisResult.document_id == document_id)
        .first()
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis result not found")

    company = db.query(Company).filter(Company.id == doc.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Check duplicate
    existing = (
        db.query(PostLog)
        .filter(
            PostLog.platform == PostPlatform.NOTE,
            PostLog.document_id == document_id,
            PostLog.post_type == PostType.ANALYSIS,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Already published")

    article = article_gen.generate_analysis_article(
        document=doc, analysis=analysis, company=company, free=req.free
    )

    if req.dry_run:
        return {
            "dry_run": True,
            "title": article.title,
            "price": article.price,
            "hashtags": article.hashtags,
            "body_preview": article.body_html[:500],
        }

    client = NoteClient()
    await client.ensure_logged_in()
    result = await client.create_and_publish(
        title=article.title,
        html_body=article.body_html,
        price=article.price,
        hashtags=article.hashtags,
    )

    post_log = PostLog(
        platform=PostPlatform.NOTE,
        post_type=PostType.ANALYSIS,
        external_id=result.get("note_url", ""),
        document_id=document_id,
        company_id=company.id,
        content_preview=article.title[:200],
    )
    db.add(post_log)
    db.commit()

    return {
        "note_url": result.get("note_url"),
        "title": article.title,
        "price": article.price,
    }


@router.post("/note/daily")
async def publish_daily_summary(
    req: DailyRequest = DailyRequest(),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """日次まとめ記事を投稿"""
    target_date = (
        datetime.strptime(req.date, "%Y-%m-%d").date() if req.date else date.today()
    )
    date_str = target_date.isoformat()

    results = (
        db.query(AnalysisResult, Document, Company)
        .join(Document, AnalysisResult.document_id == Document.id)
        .join(Company, Document.company_id == Company.id)
        .filter(Document.publish_date == date_str)
        .all()
    )

    if not results:
        raise HTTPException(status_code=404, detail=f"No analyses found for {date_str}")

    analyses = [(doc, analysis, company) for analysis, doc, company in results]
    article = article_gen.generate_daily_summary(target_date, analyses)

    if req.dry_run:
        return {
            "dry_run": True,
            "title": article.title,
            "article_count": len(analyses),
            "body_preview": article.body_html[:500],
        }

    client = NoteClient()
    await client.ensure_logged_in()
    result = await client.create_and_publish(
        title=article.title,
        html_body=article.body_html,
        price=0,
        hashtags=article.hashtags,
    )

    post_log = PostLog(
        platform=PostPlatform.NOTE,
        post_type=PostType.DAILY_SUMMARY,
        external_id=result.get("note_url", ""),
        content_preview=article.title[:200],
        metadata_={"date": date_str, "count": len(analyses)},
    )
    db.add(post_log)
    db.commit()

    return {
        "note_url": result.get("note_url"),
        "article_count": len(analyses),
    }


@router.post("/tweet/breaking/{document_id}")
async def post_breaking_tweet(
    document_id: int,
    req: TweetRequest = TweetRequest(),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """決算速報ツイート"""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    company = db.query(Company).filter(Company.id == doc.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    text = build_breaking_tweet(company, doc.title)
    twitter = TwitterClient()
    tweet_id = twitter.post(
        db=db,
        text=text,
        post_type=PostType.BREAKING,
        document_id=document_id,
        company_id=company.id,
        dry_run=req.dry_run,
    )

    if tweet_id is None and not req.dry_run:
        raise HTTPException(status_code=409, detail="Already tweeted")

    return {"tweet_id": tweet_id, "text": text, "dry_run": req.dry_run}


@router.post("/tweet/daily")
async def post_daily_tweet(
    req: DailyRequest = DailyRequest(),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """日次まとめツイート"""
    target_date = (
        datetime.strptime(req.date, "%Y-%m-%d").date() if req.date else date.today()
    )
    date_str = target_date.isoformat()

    results = (
        db.query(Company)
        .join(Document, Document.company_id == Company.id)
        .join(AnalysisResult, AnalysisResult.document_id == Document.id)
        .filter(Document.publish_date == date_str)
        .all()
    )

    if not results:
        raise HTTPException(status_code=404, detail=f"No analyses found for {date_str}")

    text = build_daily_tweet(target_date, results)
    twitter = TwitterClient()
    tweet_id = twitter.post_daily(
        db=db, text=text, target_date=target_date, dry_run=req.dry_run
    )

    return {"tweet_id": tweet_id, "text": text, "dry_run": req.dry_run}


@router.get("/logs")
async def get_post_logs(
    platform: str | None = None,
    post_type: str | None = None,
    limit: int = Query(default=50, le=100),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """投稿ログ取得"""
    query = db.query(PostLog).order_by(PostLog.posted_at.desc())

    if platform:
        query = query.filter(PostLog.platform == platform)
    if post_type:
        query = query.filter(PostLog.post_type == post_type)

    logs = query.limit(limit).all()

    return [
        {
            "id": log_entry.id,
            "platform": log_entry.platform.value if log_entry.platform else None,
            "post_type": log_entry.post_type.value if log_entry.post_type else None,
            "external_id": log_entry.external_id,
            "document_id": log_entry.document_id,
            "company_id": log_entry.company_id,
            "content_preview": log_entry.content_preview,
            "posted_at": log_entry.posted_at.isoformat() if log_entry.posted_at else None,
        }
        for log_entry in logs
    ]


@router.get("/note/status")
async def note_status(
    current_user: User = Depends(require_admin),
):
    """note.comのログイン状態を確認"""
    client = NoteClient()
    status = await client.get_status()
    return status
