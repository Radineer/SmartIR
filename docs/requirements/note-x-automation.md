# 要件定義: note自動投稿・販売 & X自動運用

## 概要

SmartIRのIR分析パイプライン（TDnet/EDINET クロール → LLM分析 → VTuber動画生成 → YouTube配信）に、
note.com記事の自動投稿・有料販売とX(Twitter)の自動運用を追加する。

boatrace-ai プロジェクトの `publish/` `social/` モジュールをベースに、IR分析ドメインに適応させる。

## ユーザーストーリー

### US-1: note記事の自動投稿
AS A SmartIR運営者
I WANT TO IR分析結果をnote.comに自動投稿したい
SO THAT 手作業なしでコンテンツを継続的に発信できる

### US-2: 有料記事の販売
AS A SmartIR運営者
I WANT TO 詳細分析を有料記事として販売したい
SO THAT IR分析サービスを収益化できる

### US-3: X自動運用
AS A SmartIR運営者
I WANT TO 決算速報・分析結果をXに自動投稿したい
SO THAT フォロワーを獲得し、noteへの流入を増やす

## 受入条件

### 機能要件

#### note.com投稿
- [ ] note.comへのログイン（Playwright）とセッション永続化
- [ ] ログイン状態の確認コマンド
- [ ] IR分析結果から記事HTML自動生成（無料/有料の2パターン）
- [ ] 無料記事: 決算サマリー（銘柄名・売上/利益の前年比・AI一言コメント）
- [ ] 有料記事: 詳細分析（セグメント分析・業績トレンド・投資ポイント・VTuber動画リンク）
- [ ] `<pay>` タグによる無料/有料部分の分離
- [ ] ハッシュタグ自動付与（銘柄名・セクター・決算関連タグ）
- [ ] 有料記事の価格設定（デフォルト500円）
- [ ] 投稿ログのDB保存（重複防止）
- [ ] dry-runモード対応

#### X (Twitter) 投稿
- [ ] tweepy経由のX API v2連携
- [ ] 決算速報ツイート: 新着IR検知時に自動投稿
- [ ] 分析完了ツイート: AI分析結果の要約投稿（note記事リンク付き）
- [ ] 日次まとめツイート: 当日の決算発表銘柄一覧
- [ ] 週次まとめツイート: 週間の注目決算ランキング
- [ ] ツイートテンプレート（複数パターンからランダム選択）
- [ ] 投稿ログのDB保存（重複防止）
- [ ] dry-runモード対応

#### CLI コマンド
- [ ] `python -m app.cli note login` - note.comログイン
- [ ] `python -m app.cli note status` - ログイン状態確認
- [ ] `python -m app.cli publish article <document_id>` - 単一記事投稿
- [ ] `python -m app.cli publish daily [--date DATE]` - 当日の全分析記事投稿
- [ ] `python -m app.cli publish daily --free` - 無料記事として投稿
- [ ] `python -m app.cli publish daily --dry-run` - プレビューのみ
- [ ] `python -m app.cli tweet breaking <document_id>` - 決算速報ツイート
- [ ] `python -m app.cli tweet daily [--date DATE]` - 日次まとめツイート
- [ ] `python -m app.cli tweet weekly` - 週次まとめツイート
- [ ] `python -m app.cli tweet daily --dry-run` - プレビューのみ

#### 自動化スケジュール
- [ ] 新着IR検知時 → 速報ツイート（Celeryタスク連携）
- [ ] 分析完了時 → note記事投稿 + 分析完了ツイート（Celeryタスク連携）
- [ ] 毎日 20:00 → 日次まとめツイート（Celery Beat）
- [ ] 毎週日曜 10:00 → 週次まとめツイート（Celery Beat）

### 非機能要件
- パフォーマンス: note投稿間隔 2秒以上（レート制限対策）
- セキュリティ: API キー・パスワードは環境変数管理、セッションファイルは600パーミッション
- 信頼性: 投稿失敗時のリトライ（最大3回、指数バックオフ）
- 可観測性: 全投稿のログ記録、エラー時のSlack通知

## 制約事項
- フレームワーク: FastAPI（既存）+ Click CLI
- データ永続化: PostgreSQL（既存のSQLAlchemy）
- note.com: 公式APIなし → Playwright + 非公式API のハイブリッド方式
- X: tweepy (v2 API) を使用
- 既存のCelery Beat スケジューラーに統合

## アーキテクチャ

### 新規ファイル構成
```
app/
  social/
    __init__.py
    config.py          # SNS関連の設定・バリデーション
    twitter.py         # X投稿クライアント
    templates.py       # ツイートテンプレート
  publish/
    __init__.py
    note_client.py     # note.com APIクライアント（boatrace-aiベース）
    article.py         # IR分析記事生成
  cli.py               # CLIエントリーポイント（Click）
  models.py            # 既存に PostLog テーブル追加
```

### DB追加テーブル
```sql
-- 投稿ログ（note + X 共用）
CREATE TABLE post_logs (
    id SERIAL PRIMARY KEY,
    platform VARCHAR(20) NOT NULL,       -- 'note' | 'twitter'
    post_type VARCHAR(50) NOT NULL,      -- 'breaking' | 'analysis' | 'daily' | 'weekly'
    external_id VARCHAR(255),            -- note URL or tweet ID
    document_id INTEGER REFERENCES documents(id),
    company_id INTEGER REFERENCES companies(id),
    content_preview TEXT,                -- 先頭200文字
    posted_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);
```

### データフロー
```
[既存] TDnet/EDINET クロール
  → Document 保存
  → [新規] 速報ツイート (twitter.py)

[既存] LLM分析完了
  → AnalysisResult 保存
  → [新規] note記事生成 (article.py) → note投稿 (note_client.py)
  → [新規] 分析完了ツイート (twitter.py, note URLリンク付き)

[新規] Celery Beat
  → 20:00 日次まとめツイート
  → 日曜 10:00 週次まとめツイート
```

## 参考: boatrace-ai からの流用

| boatrace-ai | SmartIR | 変更点 |
|-------------|---------|--------|
| `publish/note_client.py` | `publish/note_client.py` | ほぼそのまま流用。パス・設定のみ変更 |
| `publish/article.py` | `publish/article.py` | IR分析ドメインの記事テンプレートに書き換え |
| `social/twitter.py` | `social/twitter.py` | ほぼそのまま流用。DBテーブル名変更 |
| `social/templates.py` | `social/templates.py` | IR分析用のツイートテンプレートに書き換え |
| `config.py` | `social/config.py` | 既存のSmartIR設定に統合 |

## 収益モデル

```
無料（集客）               有料（収益）
────────────────           ──────────────────
X 速報ツイート        →    note 詳細分析記事 (500円/本)
X 日次/週次まとめ     →    note 月額マガジン (980円/月, 将来)
note 無料サマリー     →    note 有料記事への誘導
YouTube VTuber動画    →    note 有料記事への誘導
```
