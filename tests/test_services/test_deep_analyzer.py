"""DeepAnalyzer 3段階分析エンジンのテスト"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from app.services.deep_analyzer import DeepAnalyzer, QUICK_TEXT_LIMIT, STANDARD_TEXT_LIMIT, DEEP_TEXT_LIMIT


@pytest.fixture
def analyzer():
    return DeepAnalyzer()


@pytest.fixture
def mock_company():
    c = MagicMock()
    c.id = 1
    c.name = "テスト株式会社"
    c.ticker_code = "9999"
    c.sector = "テクノロジー"
    return c


@pytest.fixture
def mock_doc():
    d = MagicMock()
    d.id = 10
    d.title = "2024年度第3四半期 決算短信"
    d.doc_type = MagicMock()
    d.doc_type.value = "financial_report"
    d.publish_date = "2024-01-15"
    d.raw_text = "売上高は前年同期比15%増の500億円。営業利益は80億円。" * 200
    return d


@pytest.fixture
def mock_analysis_result():
    """Claude APIのtool_useレスポンスを模倣"""
    return {
        "summary": "売上高は前年同期比15%増と好調。営業利益率も改善。",
        "sentiment": {"positive": 0.7, "negative": 0.1, "neutral": 0.2},
        "financial_metrics": {
            "revenue": 50000,
            "operating_profit": 8000,
            "net_profit": 5500,
            "revenue_yoy": 15.0,
            "op_yoy": 20.0,
            "np_yoy": 12.0,
            "fiscal_period": "Q3",
            "fiscal_year": "2024/3",
        },
        "guidance_revision": "up",
        "guidance_detail": {
            "revenue_revised": 65000,
            "revenue_previous": 60000,
            "revenue_change_pct": 8.3,
            "reason": "主力事業の好調",
        },
        "segments": [
            {"name": "ソフトウェア", "revenue": 30000, "profit": 6000, "yoy": 18.0},
            {"name": "ハードウェア", "revenue": 20000, "profit": 2000, "yoy": 10.0},
        ],
        "key_points": [
            "売上高15%増で過去最高",
            "業績予想を上方修正",
            "ソフトウェア事業が牽引",
        ],
        "risk_factors": ["原材料費の高騰", "為替リスク"],
        "growth_drivers": ["クラウド事業の拡大", "海外展開"],
        "stock_impact": "positive",
        "stock_impact_confidence": 0.75,
        "stock_impact_reasoning": "業績予想の上方修正と主力事業の成長加速はポジティブ",
    }


class TestDeepAnalyzerBuildContent:
    """_build_user_content のテスト"""

    def test_includes_company_info(self, analyzer, mock_doc, mock_company):
        content = analyzer._build_user_content(mock_doc, mock_company, "テスト本文")
        assert "テスト株式会社" in content
        assert "9999" in content
        assert "テクノロジー" in content

    def test_includes_document_info(self, analyzer, mock_doc, mock_company):
        content = analyzer._build_user_content(mock_doc, mock_company, "テスト本文")
        assert "決算短信" in content or "financial_report" in content
        assert "テスト本文" in content


class TestDeepAnalyzerQuick:
    """Phase 1: 速報分析のテスト"""

    @patch.object(DeepAnalyzer, "_call_claude")
    def test_quick_truncates_text(self, mock_call, analyzer, mock_doc, mock_company):
        mock_call.return_value = {"summary": "test", "sentiment": {}}
        analyzer.analyze_quick(mock_doc, mock_company)
        call_args = mock_call.call_args
        user_content = call_args[0][1]  # 2nd positional arg
        # raw_textは長いが、user_contentはヘッダー+トランケートテキスト
        assert len(mock_doc.raw_text) > QUICK_TEXT_LIMIT
        # トランケート後のテキスト（QUICK_TEXT_LIMIT）+ ヘッダー < 全文
        full_content = analyzer._build_user_content(mock_doc, mock_company, mock_doc.raw_text)
        assert len(user_content) < len(full_content)

    @patch.object(DeepAnalyzer, "_call_claude")
    def test_quick_returns_none_for_empty_text(self, mock_call, analyzer, mock_doc, mock_company):
        mock_doc.raw_text = ""
        result = analyzer.analyze_quick(mock_doc, mock_company)
        assert result is None
        mock_call.assert_not_called()

    @patch.object(DeepAnalyzer, "_call_claude")
    def test_quick_adds_meta(self, mock_call, analyzer, mock_doc, mock_company):
        mock_call.return_value = {"summary": "速報"}
        result = analyzer.analyze_quick(mock_doc, mock_company)
        assert result["_meta"]["depth"] == "quick"
        assert "model" in result["_meta"]
        assert "processing_time_sec" in result["_meta"]


class TestDeepAnalyzerStandard:
    """Phase 2: 標準分析のテスト"""

    @patch.object(DeepAnalyzer, "_call_claude")
    def test_standard_uses_doc_type_prompt(self, mock_call, analyzer, mock_doc, mock_company):
        mock_call.return_value = {"summary": "標準分析"}
        analyzer.analyze_standard(mock_doc, mock_company)
        system_prompt = mock_call.call_args[0][0]
        # financial_report なので決算分析プロンプトが使われる
        assert "決算" in system_prompt or "財務" in system_prompt

    @patch.object(DeepAnalyzer, "_call_claude")
    def test_standard_adds_meta(self, mock_call, analyzer, mock_doc, mock_company):
        mock_call.return_value = {"summary": "標準"}
        result = analyzer.analyze_standard(mock_doc, mock_company)
        assert result["_meta"]["depth"] == "standard"


class TestDeepAnalyzerDeep:
    """Phase 3: 深層分析のテスト"""

    @patch.object(DeepAnalyzer, "_call_claude")
    @patch.object(DeepAnalyzer, "_build_comparison_context")
    def test_deep_uses_comparison_context(self, mock_ctx, mock_call, analyzer, mock_doc, mock_company):
        mock_ctx.return_value = "## 過去の分析\n- Q2: 増収増益"
        mock_call.return_value = {"summary": "深層分析"}
        db = MagicMock()
        result = analyzer.analyze_deep(mock_doc, mock_company, db)
        assert result["_meta"]["depth"] == "deep"
        mock_ctx.assert_called_once()

    @patch.object(DeepAnalyzer, "_call_claude")
    def test_deep_with_explicit_context(self, mock_call, analyzer, mock_doc, mock_company):
        mock_call.return_value = {"summary": "深層"}
        db = MagicMock()
        result = analyzer.analyze_deep(mock_doc, mock_company, db, comparison_context="カスタムコンテキスト")
        system_prompt = mock_call.call_args[0][0]
        assert "カスタムコンテキスト" in system_prompt


class TestDeepAnalyzerSaveResult:
    """save_result のテスト"""

    def test_save_creates_new_record(self, analyzer, db_session, sample_document, mock_analysis_result):
        ar = analyzer.save_result(db_session, sample_document, mock_analysis_result)
        assert ar.id is not None
        assert ar.document_id == sample_document.id
        assert ar.summary == mock_analysis_result["summary"]
        assert ar.sentiment_positive == 0.7
        assert ar.sentiment_negative == 0.1
        assert ar.key_points == mock_analysis_result["key_points"]

    def test_save_updates_existing_record(self, analyzer, db_session, sample_document, mock_analysis_result):
        # 1回目
        ar1 = analyzer.save_result(db_session, sample_document, mock_analysis_result)
        ar1_id = ar1.id

        # 2回目（同じdocument_id）→ 更新
        mock_analysis_result["summary"] = "更新された要約"
        ar2 = analyzer.save_result(db_session, sample_document, mock_analysis_result)
        assert ar2.id == ar1_id
        assert ar2.summary == "更新された要約"

    def test_save_stores_extended_fields(self, analyzer, db_session, sample_document, mock_analysis_result):
        mock_analysis_result["_meta"] = {"depth": "standard", "model": "claude-sonnet-4-6", "processing_time_sec": 12.5}
        ar = analyzer.save_result(db_session, sample_document, mock_analysis_result)
        assert ar.analysis_depth == "standard"
        assert ar.llm_model == "claude-sonnet-4-6"
        assert ar.processing_time_sec == 12.5
        assert ar.financial_metrics is not None
        assert ar.guidance_revision == "up"
        assert ar.stock_impact_prediction == "positive"
        assert ar.stock_impact_confidence == 0.75


class TestDeepAnalyzerSavePrediction:
    """save_prediction のテスト"""

    def test_save_prediction_creates_log(self, analyzer, db_session, sample_document, sample_company, mock_analysis_result):
        mock_analysis_result["_meta"] = {"depth": "standard", "model": "claude-sonnet-4-6"}
        ar = analyzer.save_result(db_session, sample_document, mock_analysis_result)
        analyzer.save_prediction(db_session, ar, sample_company, mock_analysis_result)

        from app.models.prediction_log import PredictionLog
        logs = db_session.query(PredictionLog).all()
        assert len(logs) == 1
        assert logs[0].predicted_impact == "positive"
        assert logs[0].predicted_confidence == 0.75
        assert logs[0].company_id == sample_company.id
        assert logs[0].analysis_depth == "standard"

    def test_save_prediction_skips_without_impact(self, analyzer, db_session, sample_document, sample_company, mock_analysis_result):
        del mock_analysis_result["stock_impact"]
        ar = analyzer.save_result(db_session, sample_document, mock_analysis_result)
        analyzer.save_prediction(db_session, ar, sample_company, mock_analysis_result)

        from app.models.prediction_log import PredictionLog
        logs = db_session.query(PredictionLog).all()
        assert len(logs) == 0
