# 設計書: note自動投稿・販売 & X自動運用

## 1. モジュール構成

```
app/
  publish/
    __init__.py
    note_client.py      # note.com Playwright + API クライアント
    article.py          # IR分析記事HTML生成
  social/
    __init__.py
    twitter.py          # X投稿クライアント (tweepy)
    templates.py        # ツイートテンプレート
  models/
    post_log.py         # PostLog モデル (新規)
  api/
    publish.py          # note/X投稿API (新規)
  tasks/
    publish_tasks.py    # Celery非同期タスク (新規)
  cli.py               # CLIエントリーポイント (新規)
```

## 2. データモデル

### PostLog テーブル

```python
# app/models/post_log.py

class PostPlatform(str, enum.Enum):
    NOTE = "note"
    TWITTER = "twitter"

class PostType(str, enum.Enum):
    BREAKING = "breaking"         # 決算速報
    ANALYSIS = "analysis"         # 分析記事
    DAILY_SUMMARY = "daily"       # 日次まとめ
    WEEKLY_SUMMARY = "weekly"     # 週次まとめ

class PostLog(BaseModel):
    __tablename__ = "post_logs"

    platform = Column(SQLEnum(PostPlatform), nullable=False)
    post_type = Column(SQLEnum(PostType), nullable=False)
    external_id = Column(String(500))           # note URL or tweet ID
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    content_preview = Column(Text)              # 先頭200文字
    posted_at = Column(DateTime, default=func.now())
    metadata_ = Column("metadata", JSONB, default={})

    document = relationship("Document", backref="post_logs")
    company = relationship("Company", backref="post_logs")
```

### マイグレーション

```python
# migrations/versions/xxx_add_post_logs.py
def upgrade():
    op.create_table(
        "post_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("platform", sa.Enum("note", "twitter", name="postplatform"), nullable=False),
        sa.Column("post_type", sa.Enum("breaking", "analysis", "daily", "weekly", name="posttype"), nullable=False),
        sa.Column("external_id", sa.String(500)),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id")),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id")),
        sa.Column("content_preview", sa.Text()),
        sa.Column("posted_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
```

## 3. note.com クライアント設計

### NoteClient クラス

```python
# app/publish/note_client.py
# boatrace-ai の note_client.py をベースに SmartIR 用に適応

class NoteClient:
    """note.com ハイブリッドクライアント (API + Playwright)"""

    SESSION_PATH = Path.home() / ".smartir" / "note_session.json"

    async def login(self, email: str, password: str) -> bool:
        """Playwrightでログイン → Cookie保存"""

    async def check_session(self) -> bool:
        """保存済みセッションの有効性確認"""

    async def publish(
        self,
        title: str,
        body_html: str,
        hashtags: list[str] | None = None,
        price: int = 0,
        dry_run: bool = False,
    ) -> str | None:
        """記事投稿。price > 0 で有料記事。戻り値は記事URL"""

    def _load_session(self) -> dict | None:
        """セッションファイル読み込み"""

    def _save_session(self, cookies: list[dict]) -> None:
        """セッションファイル保存 (600 permission)"""
```

### 認証フロー
```
1. login() → Playwright起動 → note.com/login にアクセス
2. CAPTCHA チェック → /api/v3/challenges?via=login
3. メール・パスワード入力 → ログインボタンクリック
4. Cookie取得 → SESSION_PATH に保存 (chmod 600)
5. 以降は保存Cookieで API コール
```

### 投稿フロー
```
1. check_session() → 有効ならスキップ、無効なら再ログイン
2. POST /api/v1/text_notes → ドラフト作成 (key取得)
3. POST /api/v1/text_notes/draft_save → 本文・タイトル保存
4. Playwright → editor.note.com/notes/{key}/edit/ を開く
5. ハッシュタグ設定 → 有料設定 (price > 0 の場合) → 投稿ボタンクリック
6. 投稿完了URL取得 → PostLog に記録
```

## 4. 記事生成設計

### ArticleGenerator クラス

```python
# app/publish/article.py

class ArticleGenerator:
    """IR分析結果からnote.com記事HTMLを生成"""

    def generate_analysis_article(
        self,
        document: Document,
        analysis: AnalysisResult,
        company: Company,
        free: bool = False,
    ) -> ArticleContent:
        """単一銘柄の分析記事生成"""

    def generate_daily_summary(
        self,
        date: date,
        analyses: list[tuple[Document, AnalysisResult, Company]],
    ) -> ArticleContent:
        """日次まとめ記事（無料）"""

    def _build_free_section(self, company, analysis) -> str:
        """無料部分HTML: 銘柄名・決算概要・前年比"""

    def _build_paid_section(self, document, analysis, company) -> str:
        """有料部分HTML: 詳細分析・セグメント・投資ポイント"""

    def _generate_hashtags(self, company) -> list[str]:
        """ハッシュタグ: 銘柄名・セクター・決算関連"""


@dataclass
class ArticleContent:
    title: str
    body_html: str
    hashtags: list[str]
    price: int  # 0 = 無料
```

### 記事テンプレート

#### 有料記事（個別銘柄分析）
```
タイトル: 【AI分析】{会社名}({証券コード}) {期} 決算 - SmartIR

── 無料部分 ──
<h2>決算サマリー</h2>
<p>{会社名}({証券コード})の{期}決算が発表されました。</p>
<ul>
  <li>売上高: {売上}億円（前年比 {増減}%）</li>
  <li>営業利益: {利益}億円（前年比 {増減}%）</li>
  <li>純利益: {純利益}億円（前年比 {増減}%）</li>
</ul>
<h3>AIの一言</h3>
<p>{sentiment_summary}</p>

<pay>

── 有料部分 (500円) ──
<h2>詳細AI分析</h2>
<p>{analysis_summary}</p>

<h2>セグメント別分析</h2>
{segments_html}

<h2>業績トレンド</h2>
{trend_html}

<h2>投資ポイント</h2>
<ul>
  <li>{key_point_1}</li>
  <li>{key_point_2}</li>
  <li>{key_point_3}</li>
</ul>

<h2>VTuber解説動画</h2>
<p>Irisによる解説はこちら: {youtube_url}</p>

<hr>
<p>SmartIR - AI搭載IR分析サービス</p>
```

#### 無料記事（日次まとめ）
```
タイトル: 【決算まとめ】{日付} 発表{N}社のAI分析 - SmartIR

<h2>{日付} 決算発表まとめ</h2>
<p>本日{N}社の決算が発表されました。AIによる分析結果をお届けします。</p>

{各社のサマリー (無料部分のみ)}

<hr>
<p>詳細分析は各銘柄の有料記事をご覧ください。</p>
```

## 5. X (Twitter) 設計

### TwitterClient クラス

```python
# app/social/twitter.py

class TwitterClient:
    """X投稿クライアント (tweepy v2)"""

    def __init__(self):
        self._client: tweepy.Client | None = None

    @property
    def client(self) -> tweepy.Client:
        """遅延初期化"""

    async def post(
        self,
        text: str,
        post_type: PostType,
        document_id: int | None = None,
        company_id: int | None = None,
        dry_run: bool = False,
        db: Session = None,
    ) -> str | None:
        """ツイート投稿。重複チェック → 投稿 → ログ保存。戻り値はtweet_id"""

    def _is_duplicate(self, db: Session, post_type: PostType,
                      document_id: int | None, date: date) -> bool:
        """PostLogで重複チェック"""
```

### ツイートテンプレート

```python
# app/social/templates.py

def build_breaking_tweet(company: Company, document: Document) -> str:
    """決算速報ツイート"""
    # 【速報】{会社名}({証券コード}) {期}決算を発表
    # 売上高: {売上}億円（前年比+{X}%）
    # 営業利益: {利益}億円（前年比+{X}%）
    # AI分析はこちら → {note_url}
    # #決算 #{証券コード} #IR分析

def build_analysis_tweet(company: Company, analysis: AnalysisResult,
                         note_url: str) -> str:
    """分析完了ツイート"""
    # 【AI分析】{会社名}({証券コード})
    # {sentiment_emoji} {一言サマリー}
    # 詳細分析 → {note_url}
    # #決算分析 #{セクター}

def build_daily_tweet(date: date, companies: list[Company],
                      note_url: str | None = None) -> str:
    """日次まとめツイート"""
    # 【{日付} 決算まとめ】
    # 本日{N}社の決算を分析しました
    # 注目: {top3銘柄}
    # まとめ → {note_url}
    # #決算 #IR

def build_weekly_tweet(week_start: date, highlights: list[dict]) -> str:
    """週次まとめツイート"""
    # 【週間決算ハイライト】{week_start}〜
    # {top5銘柄の一言サマリー}
    # #週間決算 #IR分析
```

### センチメント絵文字マッピング
```python
SENTIMENT_EMOJI = {
    "very_positive": "📈",    # 大幅増益
    "positive": "⬆️",         # 増益
    "neutral": "➡️",          # 横ばい
    "negative": "⬇️",         # 減益
    "very_negative": "📉",    # 大幅減益
}
```

## 6. Celeryタスク設計

```python
# app/tasks/publish_tasks.py

@celery_app.task
def publish_breaking_tweet(document_id: int):
    """新着IR検知時 → 速報ツイート"""
    # 1. Document + Company 取得
    # 2. build_breaking_tweet() でテキスト生成
    # 3. TwitterClient.post() で投稿

@celery_app.task
def publish_analysis_article(document_id: int, free: bool = False):
    """分析完了時 → note記事投稿 + 分析完了ツイート"""
    # 1. Document + AnalysisResult + Company 取得
    # 2. ArticleGenerator.generate_analysis_article() で記事生成
    # 3. NoteClient.publish() で投稿 → note_url 取得
    # 4. build_analysis_tweet(note_url) で分析完了ツイート
    # 5. TwitterClient.post() で投稿

@celery_app.task
def publish_daily_summary(date_str: str | None = None):
    """日次まとめ (Celery Beat 毎日20:00)"""
    # 1. 当日の全 AnalysisResult 取得
    # 2. ArticleGenerator.generate_daily_summary() で記事生成
    # 3. NoteClient.publish(free=True) で無料記事投稿
    # 4. build_daily_tweet(note_url) でまとめツイート
    # 5. TwitterClient.post() で投稿

@celery_app.task
def publish_weekly_summary():
    """週次まとめ (Celery Beat 毎週日曜10:00)"""
    # 1. 過去7日の AnalysisResult 取得
    # 2. build_weekly_tweet() でまとめツイート
    # 3. TwitterClient.post() で投稿
```

### Celery Beat スケジュール追加

```python
# app/celery_app.py に追加

"publish-daily-summary": {
    "task": "app.tasks.publish_tasks.publish_daily_summary",
    "schedule": crontab(hour=20, minute=0),  # 毎日20:00 JST
},
"publish-weekly-summary": {
    "task": "app.tasks.publish_tasks.publish_weekly_summary",
    "schedule": crontab(hour=10, minute=0, day_of_week=0),  # 毎週日曜10:00
},
```

### 既存タスクとの連携

```python
# app/tasks/analysis_tasks.py (既存) に追記

def analyze_document(document_id: int):
    # ... 既存の分析処理 ...

    # 分析完了後、自動投稿タスクを発行
    from app.tasks.publish_tasks import publish_analysis_article
    publish_analysis_article.delay(document_id)
```

```python
# app/tasks/crawler_tasks.py (既存) に追記

def crawl_tdnet():
    # ... 既存のクロール処理 ...
    for doc in new_documents:
        # 新着IR検知時、速報ツイートタスクを発行
        from app.tasks.publish_tasks import publish_breaking_tweet
        publish_breaking_tweet.delay(doc.id)
```

## 7. CLI設計

```python
# app/cli.py

import click

@click.group()
def cli():
    """SmartIR CLI"""

# ── note コマンド ──
@cli.group()
def note():
    """note.com アカウント管理"""

@note.command()
def login():
    """note.com にログイン"""

@note.command()
def status():
    """ログイン状態を確認"""

# ── publish コマンド ──
@cli.group()
def publish():
    """note.com 記事投稿"""

@publish.command()
@click.argument("document_id", type=int)
@click.option("--free", is_flag=True, help="無料記事として投稿")
@click.option("--dry-run", is_flag=True, help="プレビューのみ")
def article(document_id, free, dry_run):
    """単一記事を投稿"""

@publish.command()
@click.option("--date", type=str, default=None, help="日付 (YYYY-MM-DD)")
@click.option("--free", is_flag=True)
@click.option("--dry-run", is_flag=True)
def daily(date, free, dry_run):
    """当日の全分析記事を投稿"""

# ── tweet コマンド ──
@cli.group()
def tweet():
    """X (Twitter) 投稿"""

@tweet.command()
@click.argument("document_id", type=int)
@click.option("--dry-run", is_flag=True)
def breaking(document_id, dry_run):
    """決算速報ツイート"""

@tweet.command("daily")
@click.option("--date", type=str, default=None)
@click.option("--dry-run", is_flag=True)
def tweet_daily(date, dry_run):
    """日次まとめツイート"""

@tweet.command("weekly")
@click.option("--dry-run", is_flag=True)
def tweet_weekly(dry_run):
    """週次まとめツイート"""
```

## 8. API エンドポイント設計

```python
# app/api/publish.py

router = APIRouter(prefix="/publish", tags=["publish"])

@router.post("/note/article/{document_id}")
async def publish_note_article(
    document_id: int,
    free: bool = False,
    dry_run: bool = False,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """note.com に分析記事を投稿"""

@router.post("/note/daily")
async def publish_daily_summary(
    date: str | None = None,
    dry_run: bool = False,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """日次まとめ記事を投稿"""

@router.post("/tweet/breaking/{document_id}")
async def post_breaking_tweet(
    document_id: int,
    dry_run: bool = False,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """決算速報ツイート"""

@router.post("/tweet/daily")
async def post_daily_tweet(
    date: str | None = None,
    dry_run: bool = False,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """日次まとめツイート"""

@router.get("/logs")
async def get_post_logs(
    platform: str | None = None,
    limit: int = 50,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    """投稿ログ取得"""
```

## 9. 環境変数追加

```bash
# .env に追加

# note.com
NOTE_EMAIL=your-email@example.com
NOTE_PASSWORD=your-password
NOTE_DEFAULT_PRICE=500

# X (Twitter)
TWITTER_API_KEY=xxx
TWITTER_API_SECRET=xxx
TWITTER_ACCESS_TOKEN=xxx
TWITTER_ACCESS_SECRET=xxx
TWITTER_BEARER_TOKEN=xxx

# 投稿制御
PUBLISH_AUTO_NOTE=true        # 分析完了時にnote自動投稿
PUBLISH_AUTO_TWEET=true       # 新着IR時に速報ツイート自動投稿
PUBLISH_NOTE_INTERVAL=2       # note投稿間隔(秒)
```

## 10. 依存パッケージ追加

```
# requirements.txt に追加
tweepy>=4.14
playwright>=1.40
click>=8.1
```

## 11. 状態遷移図

```
                    ┌─────────────┐
                    │  TDnet/     │
                    │  EDINET     │
                    │  クロール    │
                    └──────┬──────┘
                           │ 新着IR検知
                    ┌──────▼──────┐     ┌─────────────┐
                    │  Document   │────►│ 速報ツイート  │
                    │  保存       │     │ (Twitter)    │
                    └──────┬──────┘     └─────────────┘
                           │ 30分バッチ
                    ┌──────▼──────┐
                    │  LLM分析    │
                    │  実行       │
                    └──────┬──────┘
                           │ 分析完了
              ┌────────────┼────────────┐
              ▼                         ▼
    ┌─────────────┐           ┌─────────────┐
    │ note記事投稿 │           │ 分析ツイート  │
    │ (有料/無料)  │──URL──────►│ (noteリンク) │
    └─────────────┘           └─────────────┘

    ┌─────────────┐           ┌─────────────┐
    │ Celery Beat │           │ Celery Beat │
    │ 毎日 20:00  │           │ 毎週日 10:00│
    └──────┬──────┘           └──────┬──────┘
           ▼                         ▼
    ┌─────────────┐           ┌─────────────┐
    │ 日次まとめ   │           │ 週次まとめ   │
    │ note+tweet  │           │ tweet       │
    └─────────────┘           └─────────────┘
```
