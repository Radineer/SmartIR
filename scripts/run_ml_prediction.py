#!/usr/bin/env python3
"""ML prediction update script - replaces scheduler job for GitHub Actions."""

import asyncio
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def run():
    from app.services.ml_predictor import ml_predictor_service

    models = await ml_predictor_service.list_models()
    logger.info(f"Found {len(models)} trained models")

    updated_count = 0
    for model_info in models:
        ticker = model_info.ticker
        try:
            await ml_predictor_service.train_model(ticker)
            updated_count += 1
            logger.info(f"  Updated model for {ticker}")
        except Exception as e:
            logger.error(f"  Failed to update model for {ticker}: {e}")

    logger.info(f"ML prediction update completed: {updated_count}/{len(models)} models updated")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
