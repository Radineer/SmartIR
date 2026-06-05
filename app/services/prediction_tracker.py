"""予測精度の自動トラッキングと検証。

翌営業日の株価を取得し、予測が的中したか自動判定する。
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.prediction_log import PredictionLog
from app.models.company import Company

log = logging.getLogger(__name__)

# 株価変動の閾値（±1%以内はflat扱い）
FLAT_THRESHOLD = 1.0


def _get_next_business_day(d: date) -> date:
    """翌営業日を返す（土日スキップ）"""
    next_day = d + timedelta(days=1)
    while next_day.weekday() >= 5:  # 5=土, 6=日
        next_day += timedelta(days=1)
    return next_day


def _fetch_price_change(ticker_code: str, target_date: date) -> float | None:
    """指定日の株価変化率(%)を取得。"""
    try:
        import yfinance as yf
    except ImportError:
        log.warning("yfinance が未インストール")
        return None

    # 日本株は .T サフィックス
    symbol = f"{ticker_code}.T"
    try:
        start = target_date - timedelta(days=5)
        end = target_date + timedelta(days=3)
        data = yf.download(symbol, start=start.isoformat(), end=end.isoformat(), progress=False)

        if data.empty or len(data) < 2:
            return None

        # target_dateを含む最新2日の終値を比較
        # target_date以前の最新終値と、target_date以降の最新終値
        before = data[data.index.date <= target_date]
        if len(before) < 2:
            return None

        prev_close = float(before["Close"].iloc[-2])
        curr_close = float(before["Close"].iloc[-1])

        if prev_close == 0:
            return None

        return round((curr_close - prev_close) / prev_close * 100, 2)

    except Exception as e:
        log.warning("Price fetch failed for %s: %s", symbol, e)
        return None


def verify_predictions(db: Session, target_date: date | None = None) -> dict:
    """未検証の予測を株価実績と照合する。

    Args:
        db: Database session
        target_date: 検証対象日（デフォルト: 昨営業日）

    Returns:
        検証結果のサマリー
    """
    if target_date is None:
        # 昨営業日
        d = date.today() - timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        target_date = d

    # 未検証の予測を取得
    unverified = (
        db.query(PredictionLog)
        .join(Company, PredictionLog.company_id == Company.id)
        .filter(PredictionLog.was_correct.is_(None))
        .filter(PredictionLog.predicted_at <= datetime.combine(target_date, datetime.max.time()))
        .all()
    )

    if not unverified:
        log.info("No unverified predictions to check")
        return {"verified": 0, "correct": 0, "incorrect": 0, "skipped": 0}

    verified = 0
    correct = 0
    incorrect = 0
    skipped = 0

    for pred in unverified:
        company = db.query(Company).filter(Company.id == pred.company_id).first()
        if not company or not company.ticker_code:
            skipped += 1
            continue

        # 予測日の翌営業日の株価変化を取得
        pred_date = pred.predicted_at.date() if pred.predicted_at else target_date
        check_date = _get_next_business_day(pred_date)

        change_pct = _fetch_price_change(company.ticker_code, check_date)
        if change_pct is None:
            skipped += 1
            continue

        # 実際の方向を判定
        if change_pct > FLAT_THRESHOLD:
            actual_dir = "up"
        elif change_pct < -FLAT_THRESHOLD:
            actual_dir = "down"
        else:
            actual_dir = "flat"

        # 的中判定
        pred_impact = pred.predicted_impact
        if pred_impact == "positive":
            hit = actual_dir == "up"
        elif pred_impact == "negative":
            hit = actual_dir == "down"
        else:  # neutral
            hit = actual_dir == "flat"

        pred.actual_price_change_pct = change_pct
        pred.actual_direction = actual_dir
        pred.was_correct = hit
        pred.verified_at = datetime.utcnow()

        verified += 1
        if hit:
            correct += 1
        else:
            incorrect += 1

        log.info(
            "%s: predicted=%s actual=%s (%.2f%%) → %s",
            company.ticker_code, pred_impact, actual_dir, change_pct,
            "HIT" if hit else "MISS",
        )

    db.commit()

    return {
        "verified": verified,
        "correct": correct,
        "incorrect": incorrect,
        "skipped": skipped,
        "accuracy": round(correct / verified * 100, 1) if verified > 0 else 0,
    }


def get_accuracy_stats(db: Session, days: int = 30) -> dict:
    """過去N日間の予測精度統計を返す。"""
    since = datetime.utcnow() - timedelta(days=days)

    total = (
        db.query(PredictionLog)
        .filter(PredictionLog.verified_at >= since)
        .filter(PredictionLog.was_correct.isnot(None))
        .count()
    )

    correct = (
        db.query(PredictionLog)
        .filter(PredictionLog.verified_at >= since)
        .filter(PredictionLog.was_correct == True)
        .count()
    )

    # 深さ別
    by_depth = {}
    for depth in ("quick", "standard", "deep"):
        d_total = (
            db.query(PredictionLog)
            .filter(PredictionLog.verified_at >= since)
            .filter(PredictionLog.was_correct.isnot(None))
            .filter(PredictionLog.analysis_depth == depth)
            .count()
        )
        d_correct = (
            db.query(PredictionLog)
            .filter(PredictionLog.verified_at >= since)
            .filter(PredictionLog.was_correct == True)
            .filter(PredictionLog.analysis_depth == depth)
            .count()
        )
        by_depth[depth] = {
            "total": d_total,
            "correct": d_correct,
            "rate": round(d_correct / d_total * 100, 1) if d_total > 0 else 0,
        }

    return {
        "period_days": days,
        "total_predictions": total,
        "correct_predictions": correct,
        "accuracy_rate": round(correct / total * 100, 1) if total > 0 else 0,
        "by_depth": by_depth,
    }
