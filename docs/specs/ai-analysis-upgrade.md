# 設計書: 決算AI分析エンジン大幅強化

## 概要

現在の「LLMAnalyzer（GPT-4, 単一プロンプト, テキストのみ）」を
「3段階分析パイプライン（Claude API, 文書タイプ別プロンプト, 構造化データ抽出）」に刷新する。

## アーキテクチャ

```
[決算短信PDF]
      ↓
[Phase 1: 速報分析 ≤3分]
  ├─ PDFメタデータ + 1ページ目のみ読み取り
  ├─ Claude Haiku で基本数値+方向性を即座に判定
  ├─ AnalysisResult (depth=quick) 保存
  └─ 速報記事 + 速報ツイート 自動発行
      ↓
[Phase 2: 標準分析 ≤15分]
  ├─ 全文テキスト抽出
  ├─ Claude Sonnet で構造化分析 (tool_use)
  │   ├─ 財務数値の自動抽出 (PL/BS/CF)
  │   ├─ セグメント別分析
  │   ├─ 前年同期比の自動計算
  │   ├─ 業績予想修正の検出
  │   └─ センチメント + キーポイント
  ├─ AnalysisResult (depth=standard) 更新
  └─ 分析記事 + 分析ツイート 自動発行
      ↓
[Phase 3: 深層分析 ≤60分]  (有料記事用)
  ├─ Claude Opus で深層分析
  │   ├─ 競合比較（同セクター過去分析との照合）
  │   ├─ 時系列変化（前四半期比較）
  │   ├─ 通期進捗率の計算
  │   ├─ リスク要因の詳細分析
  │   └─ 株価インパクト予測（ML予測統合）
  ├─ AnalysisResult (depth=deep) 更新
  └─ 有料詳細記事 自動発行
```

## コンポーネント設計

### 1. AnalysisResult スキーマ拡張

```python
class AnalysisResult(BaseModel):
    __tablename__ = "analysis_results"

    # === 既存カラム ===
    document_id = Column(Integer, ForeignKey("documents.id"), index=True)
    summary = Column(Text)
    sentiment_positive = Column(Float, default=0.0)
    sentiment_negative = Column(Float, default=0.0)
    sentiment_neutral = Column(Float, default=0.0)
    key_points = Column(JSON, default=list)

    # === 新規カラム ===
    # 分析メタデータ
    analysis_depth = Column(String(20), default="standard")  # quick/standard/deep
    llm_model = Column(String(100))                          # claude-haiku-4-5/sonnet/opus
    processing_time_sec = Column(Float)

    # 財務数値（構造化）
    financial_metrics = Column(JSON)
    # {
    #   "revenue": 1234567,          # 売上高（百万円）
    #   "operating_profit": 123456,  # 営業利益
    #   "net_profit": 98765,         # 純利益
    #   "revenue_yoy": 12.5,         # 前年同期比(%)
    #   "op_yoy": -3.2,
    #   "np_yoy": 8.7,
    #   "fiscal_period": "Q3",       # 四半期
    #   "fiscal_year": "2026/3",     # 決算期
    # }

    # 業績予想修正
    guidance_revision = Column(String(20))  # up/down/unchanged/none/new
    guidance_detail = Column(JSON)
    # {
    #   "revenue_revised": 5000000,
    #   "revenue_previous": 4800000,
    #   "revenue_change_pct": 4.2,
    #   "reason": "海外事業の好調"
    # }

    # セグメント分析
    segments = Column(JSON)
    # [
    #   {
    #     "name": "モバイル事業",
    #     "revenue": 500000,
    #     "profit": 80000,
    #     "yoy": 15.3,
    #     "highlight": "5G契約数が前年比25%増"
    #   }
    # ]

    # リスク・成長要因
    risk_factors = Column(JSON)       # ["原材料価格の高騰", "為替リスク"]
    growth_drivers = Column(JSON)     # ["DX需要の拡大", "海外展開"]

    # 前期比較
    comparison_note = Column(Text)    # 前期との比較コメント
    progress_rate = Column(Float)     # 通期予想に対する進捗率(%)

    # 株価インパクト予測
    stock_impact_prediction = Column(String(20))  # positive/negative/neutral
    stock_impact_confidence = Column(Float)        # 0-1
    stock_impact_reasoning = Column(Text)          # 予測根拠
```

### 2. 新LLM分析エンジン (`app/services/deep_analyzer.py`)

```python
class DeepAnalyzer:
    """3段階決算分析エンジン"""

    # Claude API with tool_use for structured output
    EXTRACT_FINANCIALS_TOOL = {
        "name": "submit_analysis",
        "description": "決算分析結果を構造化データとして提出",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "sentiment": {
                    "type": "object",
                    "properties": {
                        "positive": {"type": "number"},
                        "negative": {"type": "number"},
                        "neutral": {"type": "number"}
                    }
                },
                "financial_metrics": {
                    "type": "object",
                    "properties": {
                        "revenue": {"type": "number"},
                        "operating_profit": {"type": "number"},
                        "net_profit": {"type": "number"},
                        "revenue_yoy": {"type": "number"},
                        "op_yoy": {"type": "number"},
                        "np_yoy": {"type": "number"},
                        "fiscal_period": {"type": "string"},
                        "fiscal_year": {"type": "string"}
                    }
                },
                "guidance_revision": {
                    "type": "string",
                    "enum": ["up", "down", "unchanged", "none", "new"]
                },
                "guidance_detail": {"type": "object"},
                "segments": {"type": "array"},
                "key_points": {"type": "array", "items": {"type": "string"}},
                "risk_factors": {"type": "array", "items": {"type": "string"}},
                "growth_drivers": {"type": "array", "items": {"type": "string"}},
                "stock_impact": {
                    "type": "string",
                    "enum": ["positive", "negative", "neutral"]
                },
                "stock_impact_confidence": {"type": "number"},
                "stock_impact_reasoning": {"type": "string"}
            },
            "required": ["summary", "sentiment", "financial_metrics",
                         "key_points", "stock_impact"]
        }
    }

    async def analyze_quick(self, doc, company) -> dict:
        """Phase 1: 速報 (Haiku, ≤3分)"""
        # 1ページ目のみ or タイトル+最初の2000文字
        # → Claude Haiku で基本方向性を即判定

    async def analyze_standard(self, doc, company) -> dict:
        """Phase 2: 標準 (Sonnet, ≤15分)"""
        # 全文 → Claude Sonnet + tool_use で構造化抽出
        # 文書タイプ別プロンプトを選択

    async def analyze_deep(self, doc, company, db) -> dict:
        """Phase 3: 深層 (Opus, ≤60分)"""
        # 過去分析結果との比較
        # ML予測結果の統合
        # セクター比較
```

### 3. 文書タイプ別プロンプト (`app/services/analysis_prompts.py`)

```python
# 4種類の専門プロンプト

FINANCIAL_REPORT_PROMPT = """
決算短信を分析してください。以下に特に注目:
1. 売上高・営業利益・純利益の前年同期比
2. 業績予想の修正有無と方向性
3. セグメント別の業績（売上・利益・前年比）
4. 通期予想に対する進捗率
5. 配当・株主還元の変更有無
6. 株価への影響度（ポジティブ/ネガティブ/中立）と根拠
"""

ANNUAL_REPORT_PROMPT = """
有価証券報告書を分析してください。以下に特に注目:
1. 事業リスクの変化（新規追加・削除されたリスク）
2. 事業戦略の変更・新規事業
3. 設備投資・研究開発費の動向
4. 人材・組織の変化
5. 中長期的な成長ドライバー
"""

PRESENTATION_PROMPT = """
決算説明資料を分析してください。以下に特に注目:
1. 経営者のトーン（強気/弱気/慎重）
2. 中期経営計画の進捗
3. 具体的な数値目標
4. 新規事業・M&A計画
5. 来期以降の見通し
"""

PRESS_RELEASE_PROMPT = """
適時開示を分析してください。以下に特に注目:
1. 開示内容の種類（業績修正/M&A/増配/自社株買い等）
2. 株価へのインパクト度合い
3. 短期的な市場反応の予想
"""
```

### 4. PDF表構造化抽出 (`app/core/pdf_table_extractor.py`)

```python
class PDFTableExtractor:
    """Claude Visionを使ったPDF表の構造化抽出"""

    async def extract_financial_tables(self, pdf_url: str) -> dict:
        """
        PDFの1-3ページ目をClaude Visionに渡し、
        PL/BS/CFの数値を構造化JSONとして抽出
        """
        # 1. PDFダウンロード
        # 2. pdf2imageで画像変換（1-3ページ）
        # 3. Claude Vision API で表を読み取り
        # 4. tool_use で構造化データとして返却
```

### 5. 予測精度トラッキング (`app/models/prediction_log.py`)

```python
class PredictionLog(BaseModel):
    __tablename__ = "prediction_logs"

    analysis_id = Column(Integer, ForeignKey("analysis_results.id"))
    company_id = Column(Integer, ForeignKey("companies.id"))
    predicted_impact = Column(String(20))     # positive/negative/neutral
    predicted_confidence = Column(Float)
    predicted_at = Column(DateTime)

    # 実結果（翌営業日に自動記録）
    actual_price_change_pct = Column(Float)   # 翌日終値の変化率
    actual_direction = Column(String(20))     # up/down/flat
    was_correct = Column(Boolean)             # 的中したか
    verified_at = Column(DateTime)

    # 精度計算用
    analysis_depth = Column(String(20))
    llm_model = Column(String(100))
```

### 6. 時系列比較エンジン (`app/services/comparison_engine.py`)

```python
class ComparisonEngine:
    """過去の分析結果との時系列比較"""

    def compare_with_previous(self, company_id, current_analysis) -> dict:
        """前四半期の分析結果と比較"""
        # 1. 同一企業の過去AnalysisResultを取得
        # 2. financial_metricsのYoY変化を算出
        # 3. セグメント別のトレンド変化を検出
        # 4. センチメント変化を追跡

    def calculate_progress_rate(self, current_metrics, full_year_guidance) -> float:
        """通期予想に対する進捗率を計算"""

    def get_sector_comparison(self, sector, period) -> list:
        """同セクター企業との横比較"""
```

## パイプライン全体フロー

```
GitHub Actions スケジュール:
┌─────────────────────────────────────────────────────┐
│ crawl.yml (15分ごと)                                │
│   → 新規Document検出                                │
│   → analyze.yml をトリガー                          │
├─────────────────────────────────────────────────────┤
│ analyze.yml (新Document検出時)                       │
│                                                     │
│   [Step 1] Phase 1 速報分析 (Haiku, 全Document)     │
│     → AnalysisResult (depth=quick) 保存             │
│     → 速報記事 + 速報ツイート 発行                    │
│                                                     │
│   [Step 2] Phase 2 標準分析 (Sonnet, 全Document)    │
│     → AnalysisResult (depth=standard) 更新          │
│     → 分析記事 + 分析ツイート 発行                    │
│                                                     │
│   [Step 3] Phase 3 深層分析 (Opus, 注目銘柄のみ)     │
│     → AnalysisResult (depth=deep) 更新              │
│     → 有料記事 発行                                  │
├─────────────────────────────────────────────────────┤
│ verify_predictions.yml (毎営業日15:30 JST)          │
│   → 前日の予測結果を株価実績と照合                    │
│   → PredictionLog.was_correct を更新                │
│   → 週次で精度レポート生成                           │
└─────────────────────────────────────────────────────┘
```

## API設計

### 分析結果取得 (拡張)
```
GET /api/v1/analysis/{document_id}
Response: {
  "summary": "...",
  "sentiment": {"positive": 0.7, "negative": 0.1, "neutral": 0.2},
  "financial_metrics": {...},
  "segments": [...],
  "guidance_revision": "up",
  "stock_impact_prediction": "positive",
  "stock_impact_confidence": 0.82,
  "analysis_depth": "deep",
  "comparison_note": "前四半期比で営業利益率が2.3pt改善",
  "progress_rate": 78.5
}
```

### 予測精度取得 (新規)
```
GET /api/v1/predictions/accuracy
Response: {
  "total_predictions": 342,
  "correct_predictions": 246,
  "accuracy_rate": 71.9,
  "by_depth": {
    "quick": {"total": 342, "correct": 198, "rate": 57.9},
    "standard": {"total": 342, "correct": 232, "rate": 67.8},
    "deep": {"total": 120, "correct": 96, "rate": 80.0}
  },
  "by_period": [
    {"month": "2026-02", "rate": 73.2},
    {"month": "2026-03", "rate": 70.5}
  ]
}
```

## コスト見積もり

| Phase | モデル | 入力トークン | 出力 | 単価/回 | 月想定回数 | 月額 |
|-------|--------|------------|------|---------|-----------|------|
| Quick | Haiku 4.5 | ~2K | ~500 | ~¥0.5 | 500 | ¥250 |
| Standard | Sonnet 4.6 | ~10K | ~2K | ~¥15 | 500 | ¥7,500 |
| Deep | Opus 4.6 | ~20K | ~4K | ~¥100 | 50 | ¥5,000 |
| Vision | Sonnet 4.6 | ~5K(img) | ~1K | ~¥10 | 200 | ¥2,000 |
| **合計** | | | | | | **¥14,750** |

※ Deep分析は注目銘柄（ウォッチリスト+大型株）のみに限定してコスト管理

## ファイル構成（新規・変更）

```
app/
  services/
    deep_analyzer.py          # 新規: 3段階分析エンジン
    analysis_prompts.py       # 新規: 文書タイプ別プロンプト
    comparison_engine.py      # 新規: 時系列比較
    prediction_tracker.py     # 新規: 予測精度トラッキング
    llm_analyzer.py           # 既存: フォールバック用に残す
  core/
    pdf_table_extractor.py    # 新規: Claude Vision表抽出
    pdf_utils.py              # 既存: テキスト抽出(そのまま)
  models/
    analysis.py               # 変更: カラム大幅追加
    prediction_log.py         # 新規: 予測ログモデル
scripts/
  run_analysis.py             # 変更: DeepAnalyzer使用に切替
  run_verify_predictions.py   # 新規: 予測検証バッチ
migrations/
  versions/
    expand_analysis_results.py  # 新規: スキーマ拡張
    add_prediction_logs.py      # 新規: prediction_logsテーブル
.github/workflows/
  analyze.yml                 # 変更: 3段階分析パイプライン
  verify.yml                  # 新規: 予測検証ワークフロー
```
