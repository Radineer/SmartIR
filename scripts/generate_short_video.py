#!/usr/bin/env python3
"""
CLI tool to generate short-form videos from latest IR analyses.

Usage:
    python scripts/generate_short_video.py --ticker 7203 --style highlight
    python scripts/generate_short_video.py --ticker 7203 --style summary --max-duration 60
    python scripts/generate_short_video.py --latest 3 --style highlight
    python scripts/generate_short_video.py --ticker 7203 --character frontend/public/images/iris.png
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DB access (reuse pattern from run_auto_stream.py)
# ---------------------------------------------------------------------------

def get_db_connection():
    import psycopg2

    db_url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL or SUPABASE_DB_URL not set")
    return psycopg2.connect(db_url)


def fetch_company_analysis(ticker_code: str) -> dict | None:
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    ar.id, ar.summary, ar.key_points,
                    ar.sentiment_positive, ar.sentiment_negative, ar.sentiment_neutral,
                    ar.created_at,
                    c.name AS company_name, c.ticker_code
                FROM analysis_results ar
                JOIN documents d ON ar.document_id = d.id
                JOIN companies c ON d.company_id = c.id
                WHERE c.ticker_code = %s
                ORDER BY ar.created_at DESC
                LIMIT 1
            """, (ticker_code,))
            columns = [desc[0] for desc in cur.description]
            raw = cur.fetchone()
            if not raw:
                return None
            row = dict(zip(columns, raw))
            row["sentiment"] = {
                "positive": row.pop("sentiment_positive", None),
                "negative": row.pop("sentiment_negative", None),
                "neutral": row.pop("sentiment_neutral", None),
            }
            return row
    finally:
        conn.close()


def fetch_latest_analyses(limit: int = 5) -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    ar.id, ar.summary, ar.key_points,
                    ar.sentiment_positive, ar.sentiment_negative, ar.sentiment_neutral,
                    ar.created_at,
                    c.name AS company_name, c.ticker_code
                FROM analysis_results ar
                JOIN documents d ON ar.document_id = d.id
                JOIN companies c ON d.company_id = c.id
                ORDER BY ar.created_at DESC
                LIMIT %s
            """, (limit,))
            columns = [desc[0] for desc in cur.description]
            rows = []
            for raw in cur.fetchall():
                row = dict(zip(columns, raw))
                row["sentiment"] = {
                    "positive": row.pop("sentiment_positive", None),
                    "negative": row.pop("sentiment_negative", None),
                    "neutral": row.pop("sentiment_neutral", None),
                }
                rows.append(row)
            return rows
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate short-form vertical videos from IR analyses"
    )
    parser.add_argument(
        "--ticker",
        help="Company ticker code (e.g. 7203)",
    )
    parser.add_argument(
        "--latest",
        type=int,
        default=0,
        help="Generate videos for the N latest analyses",
    )
    parser.add_argument(
        "--style",
        choices=["highlight", "summary"],
        default="highlight",
        help="Video style: highlight (key points) or summary (full)",
    )
    parser.add_argument(
        "--max-duration",
        type=int,
        default=45,
        help="Maximum video duration in seconds (default: 45)",
    )
    parser.add_argument(
        "--output",
        help="Output file path (auto-generated if omitted)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: ./static/shorts)",
    )
    parser.add_argument(
        "--character",
        default=None,
        help="Path to character image (PNG) for overlay",
    )
    parser.add_argument(
        "--speaker-id",
        type=int,
        default=None,
        help="TTS speaker ID (default: from env/config)",
    )

    args = parser.parse_args()

    if not args.ticker and args.latest <= 0:
        parser.error("Either --ticker or --latest must be specified")

    from app.services.short_video_generator import ShortVideoGenerator

    generator = ShortVideoGenerator(
        speaker_id=args.speaker_id,
        output_dir=args.output_dir,
        character_image=args.character,
    )

    # 分析データ取得
    analyses = []
    if args.ticker:
        analysis = fetch_company_analysis(args.ticker)
        if analysis is None:
            logger.error(f"No analysis found for ticker: {args.ticker}")
            sys.exit(1)
        analyses = [analysis]
    elif args.latest > 0:
        analyses = fetch_latest_analyses(limit=args.latest)
        if not analyses:
            logger.error("No analyses found in database")
            sys.exit(1)

    logger.info(f"Found {len(analyses)} analysis(es) to process")

    results = []
    for analysis in analyses:
        company = analysis.get("company_name", "不明")
        ticker = analysis.get("ticker_code", "0000")
        logger.info(f"Processing: {company} ({ticker})")

        try:
            result = generator.generate(
                analysis=analysis,
                output_path=args.output if len(analyses) == 1 else None,
                style=args.style,
                max_duration=args.max_duration,
            )
            results.append(result)
            logger.info(f"  Video: {result['video_path']}")
            logger.info(f"  Duration: {result['duration']:.1f}s")
            logger.info(f"  Title: {result['title']}")
            logger.info(f"  Hashtags: {' '.join(result['hashtags'])}")
        except Exception as e:
            logger.error(f"  Failed to generate video for {ticker}: {e}")
            continue

    logger.info(f"\nDone. Generated {len(results)}/{len(analyses)} videos.")

    if results:
        print("\n--- Results ---")
        print(json.dumps(results, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
