"""予測精度トラッキングのテスト"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date, datetime, timedelta

from app.models.document import DocumentType
from app.services.prediction_tracker import (
    _get_next_business_day,
    verify_predictions,
    get_accuracy_stats,
    FLAT_THRESHOLD,
)


class TestGetNextBusinessDay:
    """翌営業日計算のテスト"""

    def test_weekday_returns_next_day(self):
        # 月曜 → 火曜
        assert _get_next_business_day(date(2026, 3, 9)) == date(2026, 3, 10)

    def test_friday_returns_monday(self):
        # 金曜 → 月曜
        assert _get_next_business_day(date(2026, 3, 13)) == date(2026, 3, 16)

    def test_saturday_returns_monday(self):
        # 土曜 → 月曜
        assert _get_next_business_day(date(2026, 3, 14)) == date(2026, 3, 16)

    def test_sunday_returns_monday(self):
        # 日曜 → 月曜
        assert _get_next_business_day(date(2026, 3, 15)) == date(2026, 3, 16)


class TestVerifyPredictions:
    """verify_predictions のテスト"""

    def test_no_unverified_returns_zeros(self, db_session):
        result = verify_predictions(db_session, target_date=date(2026, 3, 12))
        assert result == {"verified": 0, "correct": 0, "incorrect": 0, "skipped": 0}

    @patch("app.services.prediction_tracker._fetch_price_change")
    def test_positive_prediction_hit(self, mock_fetch, db_session, sample_company):
        """positive予測 + 株価上昇 → 的中"""
        from app.models.prediction_log import PredictionLog
        from app.models.analysis import AnalysisResult
        from app.models.document import Document

        doc = Document(
            company_id=sample_company.id,
            title="決算短信",
            doc_type=DocumentType.FINANCIAL_REPORT,
            publish_date="2026-03-10",
            source_url="https://example.com/test.pdf",
        )
        db_session.add(doc)
        db_session.commit()

        ar = AnalysisResult(
            document_id=doc.id,
            summary="好決算",
            sentiment_positive=0.8,
            sentiment_negative=0.1,
            sentiment_neutral=0.1,
        )
        db_session.add(ar)
        db_session.commit()

        pred = PredictionLog(
            analysis_id=ar.id,
            company_id=sample_company.id,
            predicted_impact="positive",
            predicted_confidence=0.8,
            predicted_at=datetime(2026, 3, 10, 10, 0),
        )
        db_session.add(pred)
        db_session.commit()

        # 株価 +3% (上昇 → positive的中)
        mock_fetch.return_value = 3.0

        result = verify_predictions(db_session, target_date=date(2026, 3, 12))
        assert result["verified"] == 1
        assert result["correct"] == 1
        assert result["accuracy"] == 100.0

        # DBに結果が保存されているか
        db_session.refresh(pred)
        assert pred.was_correct is True
        assert pred.actual_direction == "up"
        assert pred.actual_price_change_pct == 3.0

    @patch("app.services.prediction_tracker._fetch_price_change")
    def test_negative_prediction_miss(self, mock_fetch, db_session, sample_company):
        """negative予測 + 株価上昇 → ミス"""
        from app.models.prediction_log import PredictionLog
        from app.models.analysis import AnalysisResult
        from app.models.document import Document

        doc = Document(
            company_id=sample_company.id,
            title="決算短信",
            doc_type=DocumentType.FINANCIAL_REPORT,
            publish_date="2026-03-10",
            source_url="https://example.com/test.pdf",
        )
        db_session.add(doc)
        db_session.commit()

        ar = AnalysisResult(
            document_id=doc.id,
            summary="悪決算",
            sentiment_positive=0.1,
            sentiment_negative=0.8,
            sentiment_neutral=0.1,
        )
        db_session.add(ar)
        db_session.commit()

        pred = PredictionLog(
            analysis_id=ar.id,
            company_id=sample_company.id,
            predicted_impact="negative",
            predicted_confidence=0.6,
            predicted_at=datetime(2026, 3, 10, 10, 0),
        )
        db_session.add(pred)
        db_session.commit()

        mock_fetch.return_value = 2.5  # 上昇 → negative予測はミス

        result = verify_predictions(db_session, target_date=date(2026, 3, 12))
        assert result["verified"] == 1
        assert result["incorrect"] == 1

        db_session.refresh(pred)
        assert pred.was_correct is False

    @patch("app.services.prediction_tracker._fetch_price_change")
    def test_flat_threshold(self, mock_fetch, db_session, sample_company):
        """±1%以内はflat扱い"""
        from app.models.prediction_log import PredictionLog
        from app.models.analysis import AnalysisResult
        from app.models.document import Document

        doc = Document(
            company_id=sample_company.id,
            title="決算短信",
            doc_type=DocumentType.FINANCIAL_REPORT,
            publish_date="2026-03-10",
            source_url="https://example.com/test.pdf",
        )
        db_session.add(doc)
        db_session.commit()

        ar = AnalysisResult(
            document_id=doc.id,
            summary="中立",
            sentiment_positive=0.3,
            sentiment_negative=0.3,
            sentiment_neutral=0.4,
        )
        db_session.add(ar)
        db_session.commit()

        pred = PredictionLog(
            analysis_id=ar.id,
            company_id=sample_company.id,
            predicted_impact="neutral",
            predicted_confidence=0.5,
            predicted_at=datetime(2026, 3, 10, 10, 0),
        )
        db_session.add(pred)
        db_session.commit()

        mock_fetch.return_value = 0.5  # ±1%以内 → flat → neutral的中

        result = verify_predictions(db_session, target_date=date(2026, 3, 12))
        assert result["correct"] == 1

    @patch("app.services.prediction_tracker._fetch_price_change")
    def test_skips_when_price_unavailable(self, mock_fetch, db_session, sample_company):
        """株価取得失敗時はスキップ"""
        from app.models.prediction_log import PredictionLog
        from app.models.analysis import AnalysisResult
        from app.models.document import Document

        doc = Document(
            company_id=sample_company.id,
            title="決算短信",
            doc_type=DocumentType.FINANCIAL_REPORT,
            publish_date="2026-03-10",
            source_url="https://example.com/test.pdf",
        )
        db_session.add(doc)
        db_session.commit()

        ar = AnalysisResult(
            document_id=doc.id,
            summary="test",
            sentiment_positive=0.5,
            sentiment_negative=0.3,
            sentiment_neutral=0.2,
        )
        db_session.add(ar)
        db_session.commit()

        pred = PredictionLog(
            analysis_id=ar.id,
            company_id=sample_company.id,
            predicted_impact="positive",
            predicted_confidence=0.7,
            predicted_at=datetime(2026, 3, 10, 10, 0),
        )
        db_session.add(pred)
        db_session.commit()

        mock_fetch.return_value = None

        result = verify_predictions(db_session, target_date=date(2026, 3, 12))
        assert result["skipped"] == 1
        assert result["verified"] == 0


class TestGetAccuracyStats:
    """精度統計のテスト"""

    def test_empty_returns_zeros(self, db_session):
        stats = get_accuracy_stats(db_session, days=30)
        assert stats["total_predictions"] == 0
        assert stats["accuracy_rate"] == 0
        assert all(d["total"] == 0 for d in stats["by_depth"].values())

    def test_counts_verified_predictions(self, db_session, sample_company):
        from app.models.prediction_log import PredictionLog
        from app.models.analysis import AnalysisResult
        from app.models.document import Document

        doc = Document(
            company_id=sample_company.id,
            title="決算短信",
            doc_type=DocumentType.FINANCIAL_REPORT,
            publish_date="2026-03-10",
            source_url="https://example.com/test.pdf",
        )
        db_session.add(doc)
        db_session.commit()

        ar = AnalysisResult(
            document_id=doc.id,
            summary="test",
            sentiment_positive=0.5,
            sentiment_negative=0.3,
            sentiment_neutral=0.2,
        )
        db_session.add(ar)
        db_session.commit()

        # 的中2件、ミス1件
        for i, (correct, depth) in enumerate([
            (True, "quick"),
            (True, "standard"),
            (False, "quick"),
        ]):
            pred = PredictionLog(
                analysis_id=ar.id,
                company_id=sample_company.id,
                predicted_impact="positive",
                predicted_confidence=0.7,
                predicted_at=datetime.utcnow(),
                was_correct=correct,
                verified_at=datetime.utcnow(),
                analysis_depth=depth,
            )
            db_session.add(pred)
        db_session.commit()

        stats = get_accuracy_stats(db_session, days=30)
        assert stats["total_predictions"] == 3
        assert stats["correct_predictions"] == 2
        assert stats["accuracy_rate"] == 66.7
        assert stats["by_depth"]["quick"]["total"] == 2
        assert stats["by_depth"]["quick"]["correct"] == 1
        assert stats["by_depth"]["standard"]["total"] == 1
        assert stats["by_depth"]["standard"]["correct"] == 1
