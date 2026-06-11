# AI-IR Insight + AIVtuber

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-14-000000?logo=nextdotjs&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

上場企業のIR資料・市場データを自動で収集・分析し、結果を **AI VTuber が配信** するところまでを一気通貫で扱う、投資情報プラットフォームです。クローリング → LLM分析 → 定量予測 → ペーパートレード検証 → 配信、というパイプライン全体を 1 リポジトリで実装しています。

> 投資家・初心者が、効率とエンタメ性を両立して企業・市場情報を得られることを狙ったプロダクト。

## 主な機能

### 1. IR・市場データ収集（`app/crawler`, `app/services/market_data.py`, `jquants_service.py`）
- TDnet / EDINET / 企業サイトからの IR 資料自動クローリング（PDF / HTML 保存）
- J-Quants をはじめとする市場データソース連携

### 2. LLM 分析・要約（`app/services/llm_analyzer.py`, `deep_analyzer.py`, `analysis_prompts.py`）
- PDF → テキスト変換（OCR 対応）
- LLM による要約・深掘り分析・レポート生成

### 3. 定量分析・予測（`app/services/`）
- テクニカル指標算出（`technical_indicators.py`）・市場センチメント（`market_sentiment.py`）
- 機械学習による予測（`ml_predictor.py`）と予測精度トラッキング（`prediction_tracker.py`）
- バックテスト（`backtest_service.py`）／ペーパートレード検証（`paper_trading_engine.py`）
- ポートフォリオ／ウォッチリスト管理（`portfolio_manager.py`, `portfolio_analyzer.py`, `watchlist_service.py`）

### 4. AI VTuber 配信（`app/services/vtuber_script.py`, `youtube_live.py`, `youtube_uploader.py`, `broadcast_scheduler.py`）
- 分析結果からの配信台本生成、YouTube Live 連携・アップロード、配信スケジューリング

### 5. SNS 連携（`app/social`, `app/publish`）
- note / X への記事生成・publish パイプライン（`docs/specs/note-x-automation.md` 参照）

## アーキテクチャ

```
データソース (TDnet / EDINET / 企業サイト / J-Quants)
        │
        ▼
  クローラー ──► PostgreSQL / オブジェクトストレージ
        │
        ▼
  LLM分析 ─┬─► 分析レポート ──► Webダッシュボード (Next.js)
           └─► 配信台本 ──► AI VTuber 配信 (YouTube)
        │
        ▼
  定量予測 / バックテスト / ペーパートレード ──► 予測精度トラッキング
```

非同期処理は **Celery**（`app/celery_app.py`, `app/tasks/`）、定期実行は `scheduler_service.py` が担います。詳細な設計（mermaid 図・データモデル）は [`docs/technical/architecture.md`](docs/technical/architecture.md) を参照してください。

## 技術スタック

| レイヤー | 技術 |
|----------|------|
| バックエンド | Python 3.11 / FastAPI / Celery / SQLAlchemy + Alembic |
| フロントエンド | TypeScript / Next.js 14 / React |
| データベース | PostgreSQL |
| AI / ML | LLM（OpenAI 等）、機械学習による予測モデル |
| 配信 | YouTube Live / Data API、SadTalker |
| インフラ | Docker / GitHub Actions (CI) |

## 開発環境セットアップ

```bash
# バックエンド
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # 各種APIキー・DB接続を設定
alembic upgrade head              # DBマイグレーション
uvicorn app.main:app --reload     # 開発サーバー

# フロントエンド
cd frontend && npm install && npm run dev
```

Docker を使う場合は同梱の `Dockerfile` を参照してください。

## プロジェクト構造

```
.
├── app/                    # バックエンド (FastAPI)
│   ├── api/                # APIエンドポイント
│   ├── core/               # 設定・共通ユーティリティ
│   ├── crawler/            # IR/市場データクローラー
│   ├── models/             # DBモデル (SQLAlchemy)
│   ├── schemas/            # Pydanticスキーマ
│   ├── services/           # 分析・予測・配信などのビジネスロジック
│   ├── publish/ , social/  # note/X publish パイプライン
│   ├── tasks/ , celery_app.py  # 非同期タスク (Celery)
│   └── cli.py              # CLIエントリポイント
├── frontend/               # フロントエンド (Next.js)
├── migrations/             # Alembic マイグレーション
├── tests/                  # テストコード (pytest)
├── docs/                   # 要件・設計・運用ドキュメント
└── .github/                # CI ワークフロー
```

## テスト

```bash
pytest                    # バックエンドのユニット/結合テスト (tests/)
```

CI は `.github/` のワークフローで自動実行されます。

## ライセンス

MIT License
