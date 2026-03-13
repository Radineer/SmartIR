"""分析プロンプトとツールスキーマのテスト"""

import pytest
from app.services.analysis_prompts import (
    ANALYSIS_TOOL,
    QUICK_SYSTEM_PROMPT,
    FINANCIAL_REPORT_PROMPT,
    ANNUAL_REPORT_PROMPT,
    PRESENTATION_PROMPT,
    PRESS_RELEASE_PROMPT,
    DEEP_ANALYSIS_PROMPT,
    PROMPT_MAP,
    DEPTH_MODEL_MAP,
    DEPTH_MAX_TOKENS,
)


class TestAnalysisTool:
    """tool_use スキーマの整合性テスト"""

    def test_tool_name(self):
        assert ANALYSIS_TOOL["name"] == "submit_analysis"

    def test_required_fields(self):
        required = ANALYSIS_TOOL["input_schema"]["required"]
        assert "summary" in required
        assert "sentiment" in required
        assert "financial_metrics" in required
        assert "key_points" in required
        assert "stock_impact" in required
        assert "stock_impact_confidence" in required

    def test_sentiment_has_required_fields(self):
        sentiment = ANALYSIS_TOOL["input_schema"]["properties"]["sentiment"]
        assert "positive" in sentiment["properties"]
        assert "negative" in sentiment["properties"]
        assert "neutral" in sentiment["properties"]
        assert sentiment["required"] == ["positive", "negative", "neutral"]

    def test_stock_impact_enum(self):
        stock_impact = ANALYSIS_TOOL["input_schema"]["properties"]["stock_impact"]
        assert set(stock_impact["enum"]) == {"positive", "negative", "neutral"}

    def test_guidance_revision_enum(self):
        gr = ANALYSIS_TOOL["input_schema"]["properties"]["guidance_revision"]
        assert "up" in gr["enum"]
        assert "down" in gr["enum"]
        assert "unchanged" in gr["enum"]

    def test_segments_is_array(self):
        segments = ANALYSIS_TOOL["input_schema"]["properties"]["segments"]
        assert segments["type"] == "array"
        assert "name" in segments["items"]["properties"]


class TestPrompts:
    """プロンプト内容の基本テスト"""

    def test_quick_prompt_has_rules(self):
        assert "submit_analysis" in QUICK_SYSTEM_PROMPT
        assert "売買推奨" in QUICK_SYSTEM_PROMPT

    def test_financial_report_prompt_has_segments(self):
        assert "セグメント" in FINANCIAL_REPORT_PROMPT

    def test_annual_report_prompt_has_risk(self):
        assert "リスク" in ANNUAL_REPORT_PROMPT

    def test_deep_prompt_has_comparison_placeholder(self):
        assert "{comparison_context}" in DEEP_ANALYSIS_PROMPT

    def test_all_prompts_have_common_rules(self):
        for prompt in [
            QUICK_SYSTEM_PROMPT,
            FINANCIAL_REPORT_PROMPT,
            ANNUAL_REPORT_PROMPT,
            PRESENTATION_PROMPT,
            PRESS_RELEASE_PROMPT,
            DEEP_ANALYSIS_PROMPT,
        ]:
            assert "submit_analysis" in prompt


class TestPromptMap:
    """文書タイプとプロンプトのマッピングテスト"""

    def test_all_doc_types_mapped(self):
        assert "financial_report" in PROMPT_MAP
        assert "annual_report" in PROMPT_MAP
        assert "presentation" in PROMPT_MAP
        assert "press_release" in PROMPT_MAP
        assert "other" in PROMPT_MAP

    def test_other_falls_back_to_financial(self):
        assert PROMPT_MAP["other"] is PROMPT_MAP["financial_report"]


class TestDepthConfig:
    """モデル・トークン設定のテスト"""

    def test_model_map_has_all_depths(self):
        assert "quick" in DEPTH_MODEL_MAP
        assert "standard" in DEPTH_MODEL_MAP
        assert "deep" in DEPTH_MODEL_MAP

    def test_token_limits_increase_with_depth(self):
        assert DEPTH_MAX_TOKENS["quick"] < DEPTH_MAX_TOKENS["standard"]
        assert DEPTH_MAX_TOKENS["standard"] < DEPTH_MAX_TOKENS["deep"]

    def test_models_are_valid(self):
        assert "haiku" in DEPTH_MODEL_MAP["quick"]
        assert "sonnet" in DEPTH_MODEL_MAP["standard"]
        assert "opus" in DEPTH_MODEL_MAP["deep"]
