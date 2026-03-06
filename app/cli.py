"""SmartIR CLI for note.com publishing and X posting."""

from __future__ import annotations

import asyncio
import sys
import logging
from datetime import date, datetime

import click

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.analysis import AnalysisResult
from app.models.company import Company
from app.models.post_log import PostLog, PostPlatform, PostType

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


@click.group()
def cli():
    """SmartIR CLI"""
    pass


# ── note commands ──


@cli.group()
def note():
    """note.com アカウント管理"""
    pass


@note.command()
def login():
    """note.com にログイン"""
    from app.publish.note_client import NoteClient

    client = NoteClient()
    asyncio.run(client.login())
    click.echo("Login successful!")


@note.command()
def status():
    """ログイン状態を確認"""
    from app.publish.note_client import NoteClient

    client = NoteClient()
    result = asyncio.run(client.get_status())

    if result["logged_in"]:
        click.echo("Status: logged in")
    else:
        click.echo("Status: not logged in")
    click.echo(f"Session: {result['session_path']}")
    click.echo(f"Session exists: {result['session_exists']}")


# ── publish commands ──


@cli.group()
def publish():
    """note.com 記事投稿"""
    pass


@publish.command()
@click.argument("document_id", type=int)
@click.option("--free", is_flag=True, help="無料記事として投稿")
@click.option("--dry-run", is_flag=True, help="プレビューのみ")
def article(document_id: int, free: bool, dry_run: bool):
    """単一記事を投稿"""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            click.echo(f"Error: Document {document_id} not found", err=True)
            sys.exit(1)

        analysis = (
            db.query(AnalysisResult)
            .filter(AnalysisResult.document_id == document_id)
            .first()
        )
        if not analysis:
            click.echo(f"Error: No analysis result for document {document_id}", err=True)
            sys.exit(1)

        company = db.query(Company).filter(Company.id == doc.company_id).first()

        from app.publish.article import ArticleGenerator
        from app.publish.note_client import NoteClient

        gen = ArticleGenerator()
        art = gen.generate_analysis_article(
            document=doc, analysis=analysis, company=company, free=free
        )

        if dry_run:
            click.echo(f"\n--- Preview ---")
            click.echo(f"Title: {art.title}")
            click.echo(f"Price: {art.price} yen")
            click.echo(f"Hashtags: {', '.join(art.hashtags)}")
            click.echo(f"\n{art.body_html[:1000]}")
            click.echo(f"\n--- End Preview ---")
            return

        client = NoteClient()
        result = asyncio.run(client.ensure_logged_in())
        result = asyncio.run(
            client.create_and_publish(
                title=art.title,
                html_body=art.body_html,
                price=art.price,
                hashtags=art.hashtags,
            )
        )

        post_log = PostLog(
            platform=PostPlatform.NOTE,
            post_type=PostType.ANALYSIS,
            external_id=result.get("note_url", ""),
            document_id=document_id,
            company_id=company.id if company else None,
            content_preview=art.title[:200],
        )
        db.add(post_log)
        db.commit()

        click.echo(f"Published: {result.get('note_url')}")
    finally:
        db.close()


@publish.command()
@click.option("--date", "date_str", type=str, default=None, help="日付 (YYYY-MM-DD)")
@click.option("--free", is_flag=True)
@click.option("--dry-run", is_flag=True)
def daily(date_str: str | None, free: bool, dry_run: bool):
    """当日の全分析記事を投稿"""
    db = SessionLocal()
    try:
        target_date = (
            datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
        )
        d_str = target_date.isoformat()

        results = (
            db.query(AnalysisResult, Document, Company)
            .join(Document, AnalysisResult.document_id == Document.id)
            .join(Company, Document.company_id == Company.id)
            .filter(Document.publish_date == d_str)
            .all()
        )

        if not results:
            click.echo(f"No analyses found for {d_str}")
            return

        analyses = [(doc, analysis, company) for analysis, doc, company in results]
        click.echo(f"Found {len(analyses)} analyses for {d_str}")

        from app.publish.article import ArticleGenerator
        from app.publish.note_client import NoteClient

        gen = ArticleGenerator()
        art = gen.generate_daily_summary(target_date, analyses)

        if dry_run:
            click.echo(f"\n--- Preview ---")
            click.echo(f"Title: {art.title}")
            click.echo(f"Hashtags: {', '.join(art.hashtags)}")
            click.echo(f"\n{art.body_html[:1500]}")
            click.echo(f"\n--- End Preview ---")
            return

        client = NoteClient()
        result = asyncio.run(client.ensure_logged_in())
        result = asyncio.run(
            client.create_and_publish(
                title=art.title,
                html_body=art.body_html,
                price=0,
                hashtags=art.hashtags,
            )
        )

        post_log = PostLog(
            platform=PostPlatform.NOTE,
            post_type=PostType.DAILY_SUMMARY,
            external_id=result.get("note_url", ""),
            content_preview=art.title[:200],
        )
        db.add(post_log)
        db.commit()

        click.echo(f"Published: {result.get('note_url')}")
    finally:
        db.close()


# ── tweet commands ──


@cli.group()
def tweet():
    """X (Twitter) 投稿"""
    pass


@tweet.command()
@click.argument("document_id", type=int)
@click.option("--dry-run", is_flag=True)
def breaking(document_id: int, dry_run: bool):
    """決算速報ツイート"""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            click.echo(f"Error: Document {document_id} not found", err=True)
            sys.exit(1)

        company = db.query(Company).filter(Company.id == doc.company_id).first()

        from app.social.templates import build_breaking_tweet
        from app.social.twitter import TwitterClient

        text = build_breaking_tweet(company, doc.title)

        if dry_run:
            click.echo(f"[DRY-RUN] {text}")
            return

        twitter = TwitterClient()
        tweet_id = twitter.post(
            db=db,
            text=text,
            post_type=PostType.BREAKING,
            document_id=document_id,
            company_id=company.id if company else None,
        )
        click.echo(f"Tweet posted: {tweet_id}")
    finally:
        db.close()


@tweet.command("daily")
@click.option("--date", "date_str", type=str, default=None)
@click.option("--dry-run", is_flag=True)
def tweet_daily(date_str: str | None, dry_run: bool):
    """日次まとめツイート"""
    db = SessionLocal()
    try:
        target_date = (
            datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
        )
        d_str = target_date.isoformat()

        companies = (
            db.query(Company)
            .join(Document, Document.company_id == Company.id)
            .join(AnalysisResult, AnalysisResult.document_id == Document.id)
            .filter(Document.publish_date == d_str)
            .all()
        )

        if not companies:
            click.echo(f"No analyses found for {d_str}")
            return

        from app.social.templates import build_daily_tweet
        from app.social.twitter import TwitterClient

        text = build_daily_tweet(target_date, companies)

        if dry_run:
            click.echo(f"[DRY-RUN] {text}")
            return

        twitter = TwitterClient()
        tweet_id = twitter.post_daily(db=db, text=text, target_date=target_date)
        click.echo(f"Tweet posted: {tweet_id}")
    finally:
        db.close()


@tweet.command("weekly")
@click.option("--dry-run", is_flag=True)
def tweet_weekly(dry_run: bool):
    """週次まとめツイート"""
    from app.tasks.publish_tasks import publish_weekly_summary

    if dry_run:
        click.echo("[DRY-RUN] Would post weekly summary tweet")
        return

    publish_weekly_summary()
    click.echo("Weekly summary posted")


if __name__ == "__main__":
    cli()
