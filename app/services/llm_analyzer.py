from typing import Dict, Any, Optional
import os
import json
import logging
import subprocess
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.prompts import PromptTemplate

logger = logging.getLogger(__name__)

GEMINI_BIN = os.getenv("GEMINI_BIN", "/opt/homebrew/bin/gemini")
CLI_TIMEOUT = int(os.getenv("SMARTIR_LLM_TIMEOUT", "300"))
SYSTEM_PROMPT = "あなたは企業のIR情報を分析する専門家です。"


def _llm_cli(prompt: str) -> str:
    """gemini CLI (無料枠、定額)"""
    full = f"{SYSTEM_PROMPT}\n\n{prompt}"
    env = os.environ.copy()
    home = os.path.expanduser("~")
    env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
    res = subprocess.run(
        [GEMINI_BIN, "-p", full],
        capture_output=True, text=True, timeout=CLI_TIMEOUT, env=env,
    )
    if res.returncode != 0:
        stderr = (res.stderr or "")[:500]
        stdout = (res.stdout or "")[:500]
        raise RuntimeError(f"gemini CLI exit {res.returncode}: stderr={stderr!r} stdout={stdout!r}")
    return (res.stdout or "").strip()


class LLMAnalyzer:
    """gemini CLI経由でテキストを要約・分析 (無料枠利用、API credit不要)"""

    def __init__(self):
        self.enabled = os.path.exists(GEMINI_BIN)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            chunk_overlap=200,
            length_function=len,
        )
        self.summary_template = PromptTemplate(
            input_variables=["text"],
            template="""
            以下の文章は企業のIR資料からの抜粋です。
            重要なポイントを3点にまとめ、その後に200文字程度の要約を作成してください。

            文章:
            {text}

            形式:
            重要ポイント:
            1.
            2.
            3.

            要約:
            """,
        )

    def analyze(self, text: str, doc_type: str) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            logger.warning("LLM Analyzer disabled (gemini CLI not found at %s)", GEMINI_BIN)
            return None

        try:
            chunks = self.text_splitter.split_text(text)
            results = [_llm_cli(self.summary_template.format(text=c)) for c in chunks]
            final_summary = self._combine_summaries(results)
            sentiment = self._analyze_sentiment(final_summary)
            return {
                "summary": final_summary,
                "sentiment": sentiment,
                "key_points": self._extract_key_points(final_summary),
            }
        except Exception as e:
            logger.error(f"LLM analysis failed: {str(e)}")
            return None

    def _combine_summaries(self, summaries: list) -> str:
        if len(summaries) == 1:
            return summaries[0]
        combined_text = "\n\n".join(summaries)
        return _llm_cli(
            f"以下は同じ文書の異なる部分の要約です。これらを1つの包括的な要約にまとめてください。\n\n{combined_text}"
        )

    def _analyze_sentiment(self, text: str) -> Dict[str, float]:
        prompt = (
            "以下の文章について、ポジティブ・ネガティブ・ニュートラルの度合いを0-1の数値で評価してください。"
            "合計が1になるようにしてください。JSON形式のみで、他の説明は不要です。\n\n"
            f"文章:\n{text}\n\n"
            '形式: {"positive": X.XX, "negative": X.XX, "neutral": X.XX}'
        )
        try:
            raw = _llm_cli(prompt).strip()
            if raw.startswith("```"):
                raw = raw.split("```", 2)[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip("` \n")
            start, end = raw.find("{"), raw.rfind("}")
            if start >= 0 and end > start:
                raw = raw[start : end + 1]
            return json.loads(raw)
        except Exception:
            return {"positive": 0.33, "negative": 0.33, "neutral": 0.34}

    def _extract_key_points(self, text: str) -> list:
        points = []
        for line in text.split("\n"):
            s = line.strip()
            if s.startswith("1.") or s.startswith("2.") or s.startswith("3."):
                points.append(s)
        return points
