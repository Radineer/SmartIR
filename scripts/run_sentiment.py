#!/usr/bin/env python3
"""Sentiment analysis script - replaces scheduler job for GitHub Actions."""

import asyncio
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def run():
    from app.services.market_sentiment import market_sentiment_analyzer
    from app.services.market_data import MAJOR_JP_STOCKS

    # Update Fear/Greed Index
    market_sentiment = await market_sentiment_analyzer.calculate_fear_greed_index()
    logger.info(f"Fear/Greed Index: {market_sentiment.fear_greed_index} ({market_sentiment.market_mood})")

    # Analyze sentiment for major stocks
    analyzed_count = 0
    for symbol in list(MAJOR_JP_STOCKS.keys())[:5]:
        try:
            sentiment = await market_sentiment_analyzer.analyze_news_sentiment(symbol)
            analyzed_count += 1
            logger.info(f"  {symbol}: {sentiment.overall}")
        except Exception as e:
            logger.error(f"  {symbol}: failed - {e}")

    logger.info(f"Sentiment analysis completed: {analyzed_count} stocks analyzed")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
