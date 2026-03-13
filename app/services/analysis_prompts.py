"""文書タイプ別の分析プロンプトと構造化ツールスキーマ。

4種類の専門プロンプト + 3段階(quick/standard/deep)の指示を提供。
"""

from __future__ import annotations

# ── tool_use スキーマ ────────────────────────────────────────

ANALYSIS_TOOL = {
    "name": "submit_analysis",
    "description": "決算分析結果を構造化データとして提出する",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "分析要約（300-500文字）",
            },
            "sentiment": {
                "type": "object",
                "properties": {
                    "positive": {"type": "number", "description": "0-1"},
                    "negative": {"type": "number", "description": "0-1"},
                    "neutral": {"type": "number", "description": "0-1"},
                },
                "required": ["positive", "negative", "neutral"],
            },
            "financial_metrics": {
                "type": "object",
                "description": "主要財務数値",
                "properties": {
                    "revenue": {"type": "number", "description": "売上高（百万円）"},
                    "operating_profit": {"type": "number", "description": "営業利益（百万円）"},
                    "net_profit": {"type": "number", "description": "純利益（百万円）"},
                    "revenue_yoy": {"type": "number", "description": "売上高前年同期比(%)"},
                    "op_yoy": {"type": "number", "description": "営業利益前年同期比(%)"},
                    "np_yoy": {"type": "number", "description": "純利益前年同期比(%)"},
                    "fiscal_period": {"type": "string", "description": "四半期 (Q1/Q2/Q3/FY)"},
                    "fiscal_year": {"type": "string", "description": "決算期 (e.g. 2026/3)"},
                },
            },
            "guidance_revision": {
                "type": "string",
                "enum": ["up", "down", "unchanged", "none", "new"],
                "description": "業績予想修正方向",
            },
            "guidance_detail": {
                "type": "object",
                "description": "業績予想修正の詳細（修正がある場合）",
                "properties": {
                    "revenue_revised": {"type": "number"},
                    "revenue_previous": {"type": "number"},
                    "revenue_change_pct": {"type": "number"},
                    "op_revised": {"type": "number"},
                    "op_previous": {"type": "number"},
                    "np_revised": {"type": "number"},
                    "np_previous": {"type": "number"},
                    "reason": {"type": "string"},
                },
            },
            "segments": {
                "type": "array",
                "description": "セグメント別分析",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "revenue": {"type": "number", "description": "百万円"},
                        "profit": {"type": "number", "description": "百万円"},
                        "yoy": {"type": "number", "description": "前年同期比(%)"},
                        "highlight": {"type": "string", "description": "注目ポイント"},
                    },
                    "required": ["name"],
                },
            },
            "key_points": {
                "type": "array",
                "items": {"type": "string"},
                "description": "重要ポイント（3-5個）",
            },
            "risk_factors": {
                "type": "array",
                "items": {"type": "string"},
                "description": "リスク要因",
            },
            "growth_drivers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "成長ドライバー",
            },
            "stock_impact": {
                "type": "string",
                "enum": ["positive", "negative", "neutral"],
                "description": "株価へのインパクト予測",
            },
            "stock_impact_confidence": {
                "type": "number",
                "description": "予測の確信度 (0-1)",
            },
            "stock_impact_reasoning": {
                "type": "string",
                "description": "株価インパクト予測の根拠（100文字以内）",
            },
        },
        "required": [
            "summary", "sentiment", "financial_metrics",
            "key_points", "stock_impact", "stock_impact_confidence",
        ],
    },
}

# ── 共通システムプロンプト ────────────────────────────────

_COMMON_RULES = """\
## 分析ルール
1. 特定銘柄の売買推奨は絶対にしない
2. 「絶対儲かる」などの断定的表現は禁止
3. 数値は百万円単位で統一（原文が千円単位なら変換）
4. 前年同期比は%で表記
5. 不明な数値は null（推測で埋めない）
6. stock_impactは決算内容のみから判断（株価チャートは見ない）

必ず submit_analysis ツールを使って結果を返すこと。
"""

# ── Phase 1: 速報プロンプト (Haiku) ─────────────────────

QUICK_SYSTEM_PROMPT = f"""\
あなたは決算速報アナリストです。決算短信の最初の部分だけを見て、
30秒以内に投資家が知るべき核心を伝えてください。

## 必須項目
- 売上高・営業利益・純利益の前年同期比
- 業績予想の上方/下方修正があるか
- 一言で「ポジティブ/ネガティブ/中立」の方向性

## スタイル
- 簡潔に（summary は200文字以内）
- key_points は3つまで
- segments, risk_factors, growth_drivers は空配列でOK

{_COMMON_RULES}
"""

# ── Phase 2: 標準プロンプト (Sonnet) ─────────────────────

# 決算短信用
FINANCIAL_REPORT_PROMPT = f"""\
あなたは機関投資家向けの決算分析アナリストです。
決算短信を徹底分析してください。

## 重点分析項目
1. **財務数値**: 売上高・営業利益・純利益の絶対値と前年同期比
2. **業績予想修正**: 上方/下方修正の有無、修正前後の数値と変化率、修正理由
3. **セグメント分析**: 全セグメントの売上・利益・前年比・注目ポイント
4. **通期進捗率**: 通期予想に対する累計実績の進捗率
5. **配当・株主還元**: 増配/減配/自社株買いの有無
6. **株価インパクト**: 決算内容が株価にポジティブ/ネガティブか、根拠付きで判断

## 分析の深さ
- summary は400文字程度
- key_points は5つ
- segments は全セグメントを記載
- risk_factors と growth_drivers を各2-3個

{_COMMON_RULES}
"""

# 有価証券報告書用
ANNUAL_REPORT_PROMPT = f"""\
あなたは中長期投資の分析アナリストです。
有価証券報告書を分析してください。

## 重点分析項目
1. **事業リスク**: 新規追加/削除されたリスク項目
2. **事業戦略**: 中期経営計画の進捗、新規事業
3. **設備投資・R&D**: 投資の方向性と規模
4. **人的資本**: 人員計画、人材戦略
5. **ガバナンス**: コーポレートガバナンスの変更

## 分析の深さ
- 中長期的な視点で分析
- risk_factors を重点的に（5個以上）
- growth_drivers を重点的に（5個以上）
- 財務数値は通期実績を記載

{_COMMON_RULES}
"""

# 決算説明資料用
PRESENTATION_PROMPT = f"""\
あなたは決算説明会を傍聴するアナリストです。
決算説明資料を分析してください。

## 重点分析項目
1. **経営者のトーン**: 強気/弱気/慎重の判定
2. **中計進捗**: 中期経営計画に対する進捗
3. **数値目標**: 具体的なKPI目標とその達成度
4. **新規事業・M&A**: 新たな取り組み
5. **来期見通し**: 経営陣の見立て

## 分析の深さ
- 経営者の意図を読み取る定性分析を重視
- 将来の成長ストーリーを評価

{_COMMON_RULES}
"""

# 適時開示用
PRESS_RELEASE_PROMPT = f"""\
あなたは適時開示を即座に評価するアナリストです。
開示内容を分析してください。

## 重点分析項目
1. **開示種類**: 業績修正/M&A/増配/自社株買い/株式分割/その他
2. **インパクト度**: 株価への影響度合い（大/中/小）
3. **市場反応予想**: 短期的にどう反応するか

## 分析の深さ
- 簡潔かつインパクト重視
- summary は200文字程度
- stock_impact_confidence を高めに設定

{_COMMON_RULES}
"""

# ── Phase 3: 深層プロンプト (Opus) ───────────────────────

DEEP_ANALYSIS_PROMPT = f"""\
あなたは最上位のエクイティリサーチアナリストです。
決算資料を深層分析し、プロ投資家が意思決定に使える品質のレポートを作成してください。

## 重点分析項目
1. **全財務数値の精査**: PL/BS/CFの主要項目と前年比
2. **セグメント深掘り**: 各事業の成長性・収益性・構造変化
3. **ガイダンス評価**: 会社予想の達成可能性（保守的/妥当/楽観的）
4. **競合との位置づけ**: 同セクター内での相対評価
5. **リスクシナリオ**: ダウンサイドリスクの具体的シナリオ
6. **成長シナリオ**: アップサイドのカタリスト
7. **バリュエーション示唆**: 割安/割高の定性的判断

## 追加コンテキスト
以下に過去の分析結果がある場合、時系列変化に注目してください:
{{comparison_context}}

## 分析の深さ
- summary は500文字以上
- key_points は5-7つ
- segments は全セグメントを詳細に
- risk_factors と growth_drivers を各5個以上
- stock_impact_reasoning は詳細に（200文字以上）

{_COMMON_RULES}
"""

# ── ドキュメントタイプ → プロンプトのマッピング ──────────

PROMPT_MAP = {
    "financial_report": FINANCIAL_REPORT_PROMPT,
    "annual_report": ANNUAL_REPORT_PROMPT,
    "presentation": PRESENTATION_PROMPT,
    "press_release": PRESS_RELEASE_PROMPT,
    "other": FINANCIAL_REPORT_PROMPT,  # デフォルト
}

# ── モデル選択 ──────────────────────────────────────────

DEPTH_MODEL_MAP = {
    "quick": "claude-haiku-4-5-20251001",
    "standard": "claude-sonnet-4-6",
    "deep": "claude-opus-4-6",
}

DEPTH_MAX_TOKENS = {
    "quick": 1024,
    "standard": 4096,
    "deep": 8192,
}
