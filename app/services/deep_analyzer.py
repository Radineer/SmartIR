"""3段階決算分析エンジン。

Phase 1 (Quick):   Haiku  → 速報 (≤3分)
Phase 2 (Standard): Sonnet → 標準分析 (≤15分)
Phase 3 (Deep):     Opus   → 深層分析 (≤60分)

全フェーズで tool_use を使い、構造化された分析結果を返す。
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from typing import TYPE_CHECKING

from app.services.analysis_prompts import (
    ANALYSIS_TOOL,
    DEEP_ANALYSIS_PROMPT,
    DEPTH_MAX_TOKENS,
    DEPTH_MODEL_MAP,
    PROMPT_MAP,
    QUICK_SYSTEM_PROMPT,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.models.analysis import AnalysisResult
    from app.models.company import Company
    from app.models.document import Document

log = logging.getLogger(__name__)

# テキスト制限
QUICK_TEXT_LIMIT = 3000      # Phase 1: 先頭3000文字のみ
STANDARD_TEXT_LIMIT = 30000  # Phase 2: 先頭30000文字
DEEP_TEXT_LIMIT = 80000      # Phase 3: 全文（Opusの大コンテキスト）


class DeepAnalyzer:
    """3段階決算分析エンジン"""

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic()
            except ImportError:
                raise RuntimeError("pip install anthropic が必要です")
        return self._client

    def _call_claude(
        self,
        system: str,
        user_content: str,
        model: str,
        max_tokens: int,
    ) -> dict | None:
        """Claude API を tool_use で呼び出し、構造化結果を返す。"""
        try:
            client = self._get_client()
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                tools=[ANALYSIS_TOOL],
                tool_choice={"type": "tool", "name": "submit_analysis"},
                messages=[{"role": "user", "content": user_content}],
            )

            for block in response.content:
                if block.type == "tool_use" and block.name == "submit_analysis":
                    return block.input

            log.warning("Claude response did not contain submit_analysis")
            return None

        except Exception as e:
            log.error("Claude API call failed (%s): %s", model, e)
            return None

    def _build_user_content(
        self,
        doc: Document,
        company: Company,
        text: str,
    ) -> str:
        """分析対象のコンテキストを組み立てる。"""
        return (
            f"## 分析対象\n"
            f"企業名: {company.name}（{company.ticker_code}）\n"
            f"業種: {company.sector or '不明'}\n"
            f"書類名: {doc.title or '不明'}\n"
            f"書類種別: {doc.doc_type.value if doc.doc_type else '不明'}\n"
            f"発表日: {doc.publish_date or '不明'}\n\n"
            f"## 書類本文\n{text}\n"
        )

    def analyze_quick(
        self,
        doc: Document,
        company: Company,
    ) -> dict | None:
        """Phase 1: 速報分析 (Haiku, ≤3分)。

        1ページ目 or 先頭3000文字だけを使い、基本的な方向性を即判定。
        """
        text = (doc.raw_text or "")[:QUICK_TEXT_LIMIT]
        if not text.strip():
            log.warning("Document %s has no text for quick analysis", doc.id)
            return None

        model = os.getenv("SMARTIR_QUICK_MODEL", DEPTH_MODEL_MAP["quick"])
        max_tokens = DEPTH_MAX_TOKENS["quick"]

        user_content = self._build_user_content(doc, company, text)

        start = time.time()
        result = self._call_claude(QUICK_SYSTEM_PROMPT, user_content, model, max_tokens)
        elapsed = time.time() - start

        if result:
            result["_meta"] = {
                "depth": "quick",
                "model": model,
                "processing_time_sec": round(elapsed, 1),
            }
            log.info(
                "Quick analysis done for %s in %.1fs", company.ticker_code, elapsed
            )
        return result

    def analyze_standard(
        self,
        doc: Document,
        company: Company,
    ) -> dict | None:
        """Phase 2: 標準分析 (Sonnet, ≤15分)。

        全文テキストを使い、文書タイプ別プロンプトで詳細分析。
        """
        text = (doc.raw_text or "")[:STANDARD_TEXT_LIMIT]
        if not text.strip():
            log.warning("Document %s has no text for standard analysis", doc.id)
            return None

        # 文書タイプ別プロンプト選択
        doc_type = doc.doc_type.value if doc.doc_type else "other"
        system_prompt = PROMPT_MAP.get(doc_type, PROMPT_MAP["other"])

        model = os.getenv("SMARTIR_STANDARD_MODEL", DEPTH_MODEL_MAP["standard"])
        max_tokens = DEPTH_MAX_TOKENS["standard"]

        user_content = self._build_user_content(doc, company, text)

        start = time.time()
        result = self._call_claude(system_prompt, user_content, model, max_tokens)
        elapsed = time.time() - start

        if result:
            result["_meta"] = {
                "depth": "standard",
                "model": model,
                "processing_time_sec": round(elapsed, 1),
            }
            log.info(
                "Standard analysis done for %s in %.1fs", company.ticker_code, elapsed
            )
        return result

    def analyze_deep(
        self,
        doc: Document,
        company: Company,
        db: Session,
        comparison_context: str = "",
    ) -> dict | None:
        """Phase 3: 深層分析 (Opus, ≤60分)。

        全文 + 過去分析結果との比較 + ML予測統合。
        """
        text = (doc.raw_text or "")[:DEEP_TEXT_LIMIT]
        if not text.strip():
            log.warning("Document %s has no text for deep analysis", doc.id)
            return None

        # 過去の分析結果を比較コンテキストに組み込み
        if not comparison_context:
            comparison_context = self._build_comparison_context(company.id, db)

        system_prompt = DEEP_ANALYSIS_PROMPT.replace(
            "{comparison_context}", comparison_context or "(過去の分析データなし)"
        )

        model = os.getenv("SMARTIR_DEEP_MODEL", DEPTH_MODEL_MAP["deep"])
        max_tokens = DEPTH_MAX_TOKENS["deep"]

        user_content = self._build_user_content(doc, company, text)

        start = time.time()
        result = self._call_claude(system_prompt, user_content, model, max_tokens)
        elapsed = time.time() - start

        if result:
            result["_meta"] = {
                "depth": "deep",
                "model": model,
                "processing_time_sec": round(elapsed, 1),
            }
            log.info(
                "Deep analysis done for %s in %.1fs", company.ticker_code, elapsed
            )
        return result

    def _build_comparison_context(self, company_id: int, db: Session) -> str:
        """同一企業の過去分析結果をコンテキスト文字列に変換。"""
        from app.models.analysis import AnalysisResult
        from app.models.document import Document

        past = (
            db.query(AnalysisResult)
            .join(Document, AnalysisResult.document_id == Document.id)
            .filter(Document.company_id == company_id)
            .order_by(AnalysisResult.created_at.desc())
            .limit(4)
            .all()
        )

        if not past:
            return ""

        lines = ["## 過去の分析結果（直近4件）\n"]
        for a in past:
            metrics = a.financial_metrics or {}
            rev_yoy = metrics.get("revenue_yoy", "N/A")
            op_yoy = metrics.get("op_yoy", "N/A")
            period = metrics.get("fiscal_period", "?")
            year = metrics.get("fiscal_year", "?")

            lines.append(
                f"### {year} {period}\n"
                f"- センチメント: pos={a.sentiment_positive:.2f} neg={a.sentiment_negative:.2f}\n"
                f"- 売上YoY: {rev_yoy}%, 営利YoY: {op_yoy}%\n"
                f"- 要約: {(a.summary or '')[:150]}\n"
            )

        return "\n".join(lines)

    def save_result(
        self,
        db: Session,
        doc: Document,
        data: dict,
    ) -> AnalysisResult:
        """分析結果をAnalysisResultに保存/更新。"""
        from app.models.analysis import AnalysisResult

        meta = data.get("_meta", {})
        sentiment = data.get("sentiment", {})

        # 既存レコードがあれば更新、なければ新規作成
        existing = (
            db.query(AnalysisResult)
            .filter(AnalysisResult.document_id == doc.id)
            .first()
        )

        if existing:
            ar = existing
        else:
            ar = AnalysisResult(document_id=doc.id)
            db.add(ar)

        # 基本フィールド
        ar.summary = data.get("summary", "")
        ar.sentiment_positive = sentiment.get("positive", 0.33)
        ar.sentiment_negative = sentiment.get("negative", 0.33)
        ar.sentiment_neutral = sentiment.get("neutral", 0.34)
        ar.key_points = data.get("key_points", [])

        # 拡張フィールド（カラムが存在する場合のみ）
        for attr, key in [
            ("analysis_depth", None),
            ("llm_model", None),
            ("processing_time_sec", None),
            ("financial_metrics", "financial_metrics"),
            ("guidance_revision", "guidance_revision"),
            ("guidance_detail", "guidance_detail"),
            ("segments", "segments"),
            ("risk_factors", "risk_factors"),
            ("growth_drivers", "growth_drivers"),
            ("stock_impact_prediction", "stock_impact"),
            ("stock_impact_confidence", "stock_impact_confidence"),
            ("stock_impact_reasoning", "stock_impact_reasoning"),
            ("extracted_tables", "extracted_tables"),
        ]:
            if not hasattr(ar, attr):
                continue
            if attr == "analysis_depth":
                setattr(ar, attr, meta.get("depth", "standard"))
            elif attr == "llm_model":
                setattr(ar, attr, meta.get("model", ""))
            elif attr == "processing_time_sec":
                setattr(ar, attr, meta.get("processing_time_sec"))
            elif key:
                setattr(ar, attr, data.get(key))

        db.commit()
        log.info(
            "AnalysisResult saved: doc=%s depth=%s",
            doc.id, meta.get("depth", "?"),
        )
        return ar

    def save_prediction(
        self,
        db: Session,
        analysis_result: AnalysisResult,
        company: Company,
        data: dict,
    ) -> None:
        """株価予測をPredictionLogに記録。"""
        from app.models.prediction_log import PredictionLog

        impact = data.get("stock_impact")
        confidence = data.get("stock_impact_confidence")
        if not impact:
            return

        meta = data.get("_meta", {})

        pred = PredictionLog(
            analysis_id=analysis_result.id,
            company_id=company.id,
            predicted_impact=impact,
            predicted_confidence=confidence,
            predicted_reasoning=data.get("stock_impact_reasoning", "")[:500],
            analysis_depth=meta.get("depth"),
            llm_model=meta.get("model"),
            predicted_at=datetime.utcnow(),
        )
        db.add(pred)
        db.commit()
        log.info("PredictionLog saved for company %s", company.ticker_code)
