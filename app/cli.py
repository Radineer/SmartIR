"""SmartIR CLI - unified command interface for IR analysis and publishing.

Usage:
    python -m app.cli publish daily [--date 2025-03-09] [--use-ai]
    python -m app.cli publish breaking --document-id 123
    python -m app.cli publish analysis DOCUMENT_ID [--free] [--use-ai]
    python -m app.cli publish weekly [--date 2025-03-09]
    python -m app.cli publish industry --sector "情報・通信業"
    python -m app.cli publish earnings [--date 2025-03-09]
    python -m app.cli tweet daily [--date 2025-03-09]
    python -m app.cli tweet breaking DOCUMENT_ID
    python -m app.cli tweet weekly
    python -m app.cli note status
    python -m app.cli note login

Adapted from boatrace-ai's CLI pattern.
"""

from __future__ import annotations

import asyncio
import sys
import logging
from datetime import date, datetime, timedelta

import click

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.analysis import AnalysisResult
from app.models.company import Company
from app.models.post_log import PostLog, PostPlatform, PostType

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("smartir.cli")


def _run_async(coro):
    """Run an async coroutine synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _publish_article(client, article, article_type: str) -> dict:
    """Login and publish an article with auto eyecatch."""
    await client.ensure_logged_in()
    return await client.create_and_publish(
        title=article.title,
        html_body=article.body_html,
        price=article.price,
        hashtags=article.hashtags,
        article_type=article_type,
    )


# ──────────────────────────────────────────────
# Root group
# ──────────────────────────────────────────────

@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Debug logging")
def cli(verbose: bool):
    """SmartIR - AI-Powered IR Analysis CLI"""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


# ──────────────────────────────────────────────
# note commands
# ──────────────────────────────────────────────

@cli.group()
def note():
    """note.com アカウント管理"""
    pass


@note.command()
def login():
    """note.com にログイン"""
    from app.publish.note_client import NoteClient
    client = NoteClient()
    _run_async(client.login())
    click.echo("Login successful!")


@note.command()
def status():
    """ログイン状態を確認"""
    from app.publish.note_client import NoteClient
    client = NoteClient()
    result = _run_async(client.get_status())
    if result["logged_in"]:
        click.echo("Status: logged in")
    else:
        click.echo("Status: not logged in")
    click.echo(f"Session: {result['session_path']}")
    click.echo(f"Session exists: {result['session_exists']}")


# ──────────────────────────────────────────────
# publish commands
# ──────────────────────────────────────────────

@cli.group()
def publish():
    """note.com 記事投稿"""
    pass


def _get_generator(use_ai: bool):
    """Get the appropriate article generator."""
    if use_ai:
        from app.publish.ai_generator import AIArticleGenerator
        return AIArticleGenerator()
    else:
        from app.publish.article import ArticleGenerator
        return ArticleGenerator()


@publish.command()
@click.argument("document_id", type=int)
@click.option("--free", is_flag=True, help="無料記事として投稿")
@click.option("--dry-run", is_flag=True, help="プレビューのみ")
@click.option("--use-ai/--no-ai", default=True, help="Claude APIで記事生成")
def article(document_id: int, free: bool, dry_run: bool, use_ai: bool):
    """単一銘柄の分析記事を投稿"""
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

        gen = _get_generator(use_ai)
        art = gen.generate_analysis_article(
            document=doc, analysis=analysis, company=company, free=free
        )

        if dry_run:
            click.echo(f"\n--- DRY RUN ---")
            click.echo(f"Title: {art.title}")
            click.echo(f"Price: {art.price} yen")
            click.echo(f"Hashtags: {', '.join(art.hashtags)}")
            click.echo(f"\n{art.body_html[:1000]}")
            return

        from app.publish.note_client import NoteClient
        client = NoteClient()
        result = _run_async(_publish_article(client, art, "analysis"))

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


@publish.command("breaking")
@click.argument("document_id", type=int)
@click.option("--dry-run", is_flag=True)
def publish_breaking(document_id: int, dry_run: bool):
    """決算速報記事を投稿"""
    from app.publish.ai_generator import AIArticleGenerator

    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            click.echo(f"Error: Document {document_id} not found", err=True)
            sys.exit(1)

        company = db.query(Company).filter(Company.id == doc.company_id).first()
        if not company:
            click.echo(f"Error: Company not found for document {document_id}", err=True)
            sys.exit(1)

        gen = AIArticleGenerator()
        art = gen.generate_breaking_article(doc, company)

        if dry_run:
            click.echo(f"\n--- DRY RUN ---")
            click.echo(f"Title: {art.title}")
            click.echo(f"Hashtags: {', '.join(art.hashtags)}")
            click.echo(f"\n{art.body_html[:500]}")
            return

        from app.publish.note_client import NoteClient
        client = NoteClient()
        result = _run_async(_publish_article(client, art, "breaking"))

        post_log = PostLog(
            platform=PostPlatform.NOTE,
            post_type=PostType.BREAKING,
            external_id=result.get("note_url", ""),
            document_id=document_id,
            company_id=company.id,
            content_preview=art.title[:200],
        )
        db.add(post_log)
        db.commit()
        click.echo(f"Published: {result.get('note_url')}")
    finally:
        db.close()


@publish.command()
@click.option("--date", "date_str", type=str, default=None, help="日付 (YYYY-MM-DD)")
@click.option("--dry-run", is_flag=True)
@click.option("--use-ai/--no-ai", default=True, help="Claude APIで記事生成")
def daily(date_str: str | None, dry_run: bool, use_ai: bool):
    """日次まとめ記事を投稿"""
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

        gen = _get_generator(use_ai)
        art = gen.generate_daily_summary(target_date, analyses)

        if dry_run:
            click.echo(f"\n--- DRY RUN ---")
            click.echo(f"Title: {art.title}")
            click.echo(f"Hashtags: {', '.join(art.hashtags)}")
            click.echo(f"\n{art.body_html[:1500]}")
            return

        from app.publish.note_client import NoteClient
        client = NoteClient()
        result = _run_async(_publish_article(client, art, "daily_summary"))

        post_log = PostLog(
            platform=PostPlatform.NOTE,
            post_type=PostType.DAILY_SUMMARY,
            external_id=result.get("note_url", ""),
            content_preview=art.title[:200],
            metadata_={"date": d_str, "count": len(analyses)},
        )
        db.add(post_log)
        db.commit()
        click.echo(f"Published: {result.get('note_url')}")
    finally:
        db.close()


@publish.command("weekly")
@click.option("--date", "date_str", type=str, default=None, help="週開始日 (YYYY-MM-DD)")
@click.option("--dry-run", is_flag=True)
@click.option("--use-ai/--no-ai", default=True)
def publish_weekly(date_str: str | None, dry_run: bool, use_ai: bool):
    """週次トレンドレポートを投稿"""
    from app.publish.ai_generator import AIArticleGenerator

    today = date.today()
    week_start = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else today - timedelta(days=7)

    db = SessionLocal()
    try:
        results = (
            db.query(AnalysisResult, Document, Company)
            .join(Document, AnalysisResult.document_id == Document.id)
            .join(Company, Document.company_id == Company.id)
            .filter(Document.publish_date >= week_start.isoformat())
            .filter(Document.publish_date <= today.isoformat())
            .all()
        )

        if not results:
            click.echo("No analyses found for the week")
            return

        analyses = [(doc, analysis, company) for analysis, doc, company in results]
        click.echo(f"Found {len(analyses)} analyses for the week")

        gen = AIArticleGenerator()
        art = gen.generate_weekly_trend(week_start, analyses)

        if dry_run:
            click.echo(f"\n--- DRY RUN ---")
            click.echo(f"Title: {art.title}")
            click.echo(f"Hashtags: {', '.join(art.hashtags)}")
            click.echo(f"\n{art.body_html[:1500]}")
            return

        from app.publish.note_client import NoteClient
        client = NoteClient()
        result = _run_async(_publish_article(client, art, "weekly_trend"))

        post_log = PostLog(
            platform=PostPlatform.NOTE,
            post_type=PostType.WEEKLY_SUMMARY,
            external_id=result.get("note_url", ""),
            content_preview=art.title[:200],
            metadata_={"week_start": week_start.isoformat()},
        )
        db.add(post_log)
        db.commit()
        click.echo(f"Published: {result.get('note_url')}")
    finally:
        db.close()


@publish.command("industry")
@click.option("--sector", required=True, help="業種名 (e.g. '情報・通信業')")
@click.option("--dry-run", is_flag=True)
def publish_industry(sector: str, dry_run: bool):
    """業界比較記事を投稿"""
    from app.publish.ai_generator import AIArticleGenerator

    db = SessionLocal()
    try:
        results = (
            db.query(AnalysisResult, Document, Company)
            .join(Document, AnalysisResult.document_id == Document.id)
            .join(Company, Document.company_id == Company.id)
            .filter(Company.sector == sector)
            .order_by(Document.publish_date.desc())
            .limit(20)
            .all()
        )

        if not results:
            click.echo(f"No analyses found for sector '{sector}'")
            return

        analyses = [(doc, analysis, company) for analysis, doc, company in results]
        click.echo(f"Found {len(analyses)} analyses for '{sector}'")

        gen = AIArticleGenerator()
        art = gen.generate_industry_comparison(sector, analyses)

        if dry_run:
            click.echo(f"\n--- DRY RUN ---")
            click.echo(f"Title: {art.title}")
            click.echo(f"Hashtags: {', '.join(art.hashtags)}")
            click.echo(f"\n{art.body_html[:1000]}")
            return

        from app.publish.note_client import NoteClient
        client = NoteClient()
        result = _run_async(_publish_article(client, art, "industry"))

        post_log = PostLog(
            platform=PostPlatform.NOTE,
            post_type=PostType.INDUSTRY,
            external_id=result.get("note_url", ""),
            content_preview=art.title[:200],
            metadata_={"sector": sector},
        )
        db.add(post_log)
        db.commit()
        click.echo(f"Published: {result.get('note_url')}")
    finally:
        db.close()


@publish.command("earnings")
@click.option("--date", "date_str", type=str, default=None, help="日付 (YYYY-MM-DD)")
@click.option("--dry-run", is_flag=True)
def publish_earnings(date_str: str | None, dry_run: bool):
    """決算カレンダー記事を投稿"""
    from app.publish.ai_generator import AIArticleGenerator

    d = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()

    db = SessionLocal()
    try:
        companies = (
            db.query(Company)
            .join(Document, Document.company_id == Company.id)
            .filter(Document.publish_date == d.isoformat())
            .distinct()
            .all()
        )

        if not companies:
            click.echo(f"No companies with earnings on {d.isoformat()}")
            return

        click.echo(f"Found {len(companies)} companies with earnings on {d.isoformat()}")

        gen = AIArticleGenerator()
        art = gen.generate_earnings_calendar(d, companies)

        if dry_run:
            click.echo(f"\n--- DRY RUN ---")
            click.echo(f"Title: {art.title}")
            click.echo(f"Hashtags: {', '.join(art.hashtags)}")
            click.echo(f"\n{art.body_html[:1000]}")
            return

        from app.publish.note_client import NoteClient
        client = NoteClient()
        result = _run_async(_publish_article(client, art, "earnings_calendar"))

        post_log = PostLog(
            platform=PostPlatform.NOTE,
            post_type=PostType.EARNINGS_CALENDAR,
            external_id=result.get("note_url", ""),
            content_preview=art.title[:200],
            metadata_={"date": d.isoformat(), "count": len(companies)},
        )
        db.add(post_log)
        db.commit()
        click.echo(f"Published: {result.get('note_url')}")
    finally:
        db.close()


# ──────────────────────────────────────────────
# tweet commands
# ──────────────────────────────────────────────

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
        text = build_breaking_tweet(company, doc.title or "決算発表")

        if dry_run:
            click.echo(f"[DRY-RUN] {text}")
            return

        from app.social.twitter import TwitterClient
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
@click.option("--note-url", type=str, default="", help="Published note.com URL to include")
@click.option("--dry-run", is_flag=True)
def tweet_daily(date_str: str | None, note_url: str, dry_run: bool):
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
        text = build_daily_tweet(target_date, companies, note_url)

        if dry_run:
            click.echo(f"[DRY-RUN] {text}")
            return

        from app.social.twitter import TwitterClient
        twitter = TwitterClient()
        twitter.post_daily(db=db, text=text, target_date=target_date)
        click.echo("Daily tweet posted")
    finally:
        db.close()


@tweet.command("weekly")
@click.option("--dry-run", is_flag=True)
def tweet_weekly(dry_run: bool):
    """週次まとめツイート"""
    today = date.today()
    week_start = today - timedelta(days=7)

    db = SessionLocal()
    try:
        results = (
            db.query(AnalysisResult, Company)
            .join(Document, AnalysisResult.document_id == Document.id)
            .join(Company, Document.company_id == Company.id)
            .filter(Document.publish_date >= week_start.isoformat())
            .filter(Document.publish_date <= today.isoformat())
            .all()
        )

        if not results:
            click.echo("No analyses found for the week")
            return

        highlights = []
        for analysis, company in results:
            pos = analysis.sentiment_positive or 0
            neg = analysis.sentiment_negative or 0
            if pos >= 0.7:
                sentiment = "very_positive"
            elif pos >= 0.5:
                sentiment = "positive"
            elif neg >= 0.7:
                sentiment = "very_negative"
            elif neg >= 0.5:
                sentiment = "negative"
            else:
                sentiment = "neutral"
            highlights.append({
                "company_name": company.name,
                "ticker_code": company.ticker_code,
                "sentiment": sentiment,
            })

        highlights.sort(
            key=lambda h: abs(
                {"very_positive": 2, "positive": 1, "neutral": 0,
                 "negative": -1, "very_negative": -2}.get(h["sentiment"], 0)
            ),
            reverse=True,
        )

        from app.social.templates import build_weekly_tweet
        text = build_weekly_tweet(week_start, highlights[:5])

        if dry_run:
            click.echo(f"[DRY-RUN] {text}")
            return

        from app.social.twitter import TwitterClient
        twitter = TwitterClient()
        twitter.post_daily(db=db, text=text, target_date=today, post_type=PostType.WEEKLY_SUMMARY)
        click.echo("Weekly tweet posted")
    finally:
        db.close()


@tweet.command("industry")
@click.option("--sector", required=True)
@click.option("--note-url", type=str, default="")
@click.option("--dry-run", is_flag=True)
def tweet_industry(sector: str, note_url: str, dry_run: bool):
    """業界分析ツイート"""
    from app.social.templates import build_industry_tweet
    text = build_industry_tweet(sector, note_url)

    if dry_run:
        click.echo(f"[DRY-RUN] {text}")
        return

    db = SessionLocal()
    try:
        from app.social.twitter import TwitterClient
        twitter = TwitterClient()
        twitter.post_daily(db=db, text=text, target_date=date.today(), post_type=PostType.INDUSTRY)
        click.echo("Industry tweet posted")
    finally:
        db.close()


if __name__ == "__main__":
    cli()
