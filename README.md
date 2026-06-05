# AI-IR Insight + AIVtuber

投資家や初心者が効率的かつエンタメ性をもって企業・市場情報を得られる新サービス

## プロジェクト概要

- IR資料収集・分析: TDnet/EDINET/企業HPから上場企業IR資料を取得 → LLM要約 → 分析レポート生成
- AIVtuber運用: 生成した投資・企業情報をVTuberキャラクターが配信（YouTube等）

## 主な機能

1. IR資料自動収集
   - TDnet, EDINET, 企業サイトからの自動クローリング
   - PDF/HTMLファイルの保存・管理

2. テキスト解析・要約
   - PDF → テキスト変換 (OCR対応)
   - LLMによる要約・分析

3. レポート生成
   - テンプレートベースのレポート作成
   - Webダッシュボード提供

4. AIVtuber配信
   - 投資情報のエンターテイメント配信
   - リアルタイムQ&A対応

## 技術スタック

- バックエンド: Python (FastAPI)
- フロントエンド: TypeScript + Next.js
- データベース: PostgreSQL
- AI/ML: OpenAI API
- インフラ: AWS

## 開発環境セットアップ

```bash
# 環境構築
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 開発サーバー起動
uvicorn app.main:app --reload
```

## プロジェクト構造

```
.
├── app/                    # バックエンドアプリケーション
│   ├── api/               # APIエンドポイント
│   ├── core/              # 設定、ユーティリティ
│   ├── crawler/           # クローリングモジュール
│   ├── models/            # DBモデル
│   └── services/          # ビジネスロジック
├── frontend/              # フロントエンドアプリケーション
├── tests/                 # テストコード
└── docs/                  # ドキュメント
```

## ライセンス

MIT License 