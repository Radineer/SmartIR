#!/usr/bin/env python3
"""予測精度の自動検証バッチスクリプト。

翌営業日の株価を取得し、予測が的中したか自動判定する。
GitHub Actions から毎日実行。
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.services.prediction_tracker import verify_predictions, get_accuracy_stats

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    db = SessionLocal()
    try:
        # 未検証の予測を検証
        result = verify_predictions(db)
        logger.info(
            "Verification done: verified=%d correct=%d incorrect=%d skipped=%d accuracy=%.1f%%",
            result["verified"],
            result["correct"],
            result["incorrect"],
            result["skipped"],
            result.get("accuracy", 0),
        )

        # 精度統計を表示
        stats = get_accuracy_stats(db, days=30)
        logger.info(
            "30-day stats: total=%d correct=%d rate=%.1f%%",
            stats["total_predictions"],
            stats["correct_predictions"],
            stats["accuracy_rate"],
        )
        for depth, d_stats in stats["by_depth"].items():
            if d_stats["total"] > 0:
                logger.info(
                    "  %s: %d/%d (%.1f%%)",
                    depth, d_stats["correct"], d_stats["total"], d_stats["rate"],
                )

    finally:
        db.close()


if __name__ == "__main__":
    main()
