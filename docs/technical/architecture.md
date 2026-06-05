# 技術設計書

## 1. システムアーキテクチャ

### 1.1 全体構成図
```mermaid
graph TD
    subgraph データソース
        A1[TDnet]
        A2[EDINET]
        A3[企業サイト]
    end

    subgraph バックエンド
        B1[クローラー]
        B2[テキスト解析]
        B3[LLM分析]
        B4[レポート生成]
    end

    subgraph ストレージ
        C1[(PostgreSQL)]
        C2[S3/GCS]
    end

    subgraph フロントエンド
        D1[Webダッシュボード]
        D2[管理画面]
    end

    subgraph AIVtuber
        E1[台本生成]
        E2[配信管理]
    end

    A1 & A2 & A3 --> B1
    B1 --> C1 & C2
    C2 --> B2
    B2 --> B3
    B3 --> B4
    B4 --> C1
    C1 --> D1 & D2
    B3 --> E1
    E1 --> E2
```

### 1.2 技術スタック
| レイヤー | 技術 | バージョン | 用途 |
|----------|------|------------|------|
| フロントエンド | Next.js | 14.x | Webアプリケーション |
| | React | 18.x | UIコンポーネント |
| | TypeScript | 5.x | 型安全な開発 |
| バックエンド | FastAPI | 0.104.x | REST API |
| | Python | 3.11.x | バックエンド全般 |
| | SQLAlchemy | 2.0.x | ORM |
| データベース | PostgreSQL | 15.x | メインDB |
| | Redis | 7.x | キャッシュ/キュー |
| AI/ML | OpenAI API | - | LLM処理 |
| | Langchain | 0.0.335 | LLMフレームワーク |
| インフラ | AWS/GCP | - | クラウドインフラ |
| | Docker | - | コンテナ化 |
| | Kubernetes | - | オーケストレーション |

## 2. コンポーネント詳細

### 2.1 クローリングシステム
```python
# クローラーの基本構造
class BaseCrawler:
    def crawl(self) -> List[Dict]:
        """基本クローリング処理"""
        pass

class TDNetCrawler(BaseCrawler):
    def crawl(self) -> List[Dict]:
        """TDnet特有の処理"""
        pass

# スケジューラー設定
CRAWLER_SCHEDULE = {
    'tdnet': '*/10 * * * *',  # 10分おき
    'edinet': '0 */1 * * *',  # 1時間おき
    'company': '0 0 * * *'    # 1日1回
}
```

### 2.2 テキスト解析システム
```python
class PDFProcessor:
    def extract_text(self, pdf_url: str) -> str:
        """PDFからテキスト抽出"""
        pass

    def perform_ocr(self, image: bytes) -> str:
        """OCR処理"""
        pass

class TextPreprocessor:
    def clean_text(self, text: str) -> str:
        """テキストクリーニング"""
        pass
```

### 2.3 LLM分析システム
```python
class LLMAnalyzer:
    def __init__(self):
        self.client = OpenAI()
        self.prompt_template = """
        以下の文章を要約し、重要ポイントを3つ挙げてください：
        {text}
        """

    async def analyze(self, text: str) -> Dict:
        """LLM分析実行"""
        pass
```

### 2.4 レポート生成システム
```python
class ReportGenerator:
    def generate_html(self, data: Dict) -> str:
        """HTML形式のレポート生成"""
        pass

    def generate_pdf(self, html: str) -> bytes:
        """PDF形式のレポート生成"""
        pass
```

### 2.5 AIVtuber台本生成システム
```python
class ScriptGenerator:
    def generate_script(self, analysis: Dict) -> str:
        """台本生成"""
        pass

    def add_emotions(self, script: str) -> str:
        """感情表現の追加"""
        pass
```

## 3. データベース設計

### 3.1 ERD
```mermaid
erDiagram
    companies ||--o{ documents : has
    documents ||--o{ analysis_results : has
    companies ||--o{ watchlist : listed_in
    users ||--o{ watchlist : has
    users ||--o{ subscriptions : has

    companies {
        int id PK
        string name
        string ticker_code UK
        string sector
        string industry
        text description
        timestamp created_at
    }

    documents {
        int id PK
        int company_id FK
        string title
        enum doc_type
        string publish_date
        string source_url
        string storage_url
        boolean is_processed
        text raw_text
        timestamp created_at
    }

    analysis_results {
        int id PK
        int document_id FK
        text summary
        json key_points
        json sentiment
        timestamp created_at
    }

    users {
        int id PK
        string email UK
        string password_hash
        enum role
        timestamp created_at
    }

    subscriptions {
        int id PK
        int user_id FK
        enum plan_type
        timestamp start_date
        timestamp end_date
    }
```

### 3.2 インデックス設計
```sql
-- 企業検索用インデックス
CREATE INDEX idx_companies_name ON companies (name);
CREATE INDEX idx_companies_ticker ON companies (ticker_code);

-- 文書検索用インデックス
CREATE INDEX idx_documents_date ON documents (publish_date);
CREATE INDEX idx_documents_type ON documents (doc_type);

-- 全文検索用インデックス
CREATE INDEX idx_documents_text ON documents USING gin(to_tsvector('japanese', raw_text));
```

## 4. API設計

### 4.1 REST API
```yaml
openapi: 3.0.0
info:
  title: AI-IR Insight API
  version: 1.0.0
paths:
  /api/reports:
    get:
      summary: レポート一覧取得
      parameters:
        - name: company_id
          in: query
          schema:
            type: integer
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/Report'
```

### 4.2 WebSocket API
```typescript
// リアルタイム通知
interface Notification {
  type: 'new_report' | 'analysis_complete';
  data: {
    id: number;
    title: string;
    timestamp: string;
  };
}
```

## 5. セキュリティ設計

### 5.1 認証・認可
```python
# JWTによる認証
class AuthHandler:
    def create_token(self, user_id: int) -> str:
        """JWTトークン生成"""
        pass

    def verify_token(self, token: str) -> Dict:
        """トークン検証"""
        pass

# ロールベースアクセス制御
ROLES = {
    'admin': ['read', 'write', 'delete'],
    'user': ['read'],
    'premium': ['read', 'export']
}
```

### 5.2 データ保護
```python
# 個人情報の暗号化
class Encryptor:
    def encrypt(self, data: str) -> str:
        """データ暗号化"""
        pass

    def decrypt(self, encrypted: str) -> str:
        """データ復号化"""
        pass
```

## 6. インフラ設計

### 6.1 AWS構成図
```mermaid
graph TD
    subgraph VPC
        subgraph Public Subnet
            ALB[Application Load Balancer]
            NAT[NAT Gateway]
        end

        subgraph Private Subnet
            ECS[ECS Fargate]
            RDS[RDS PostgreSQL]
        end
    end

    subgraph External
        R53[Route 53]
        CF[CloudFront]
        S3[S3 Bucket]
    end

    R53 --> CF
    CF --> ALB
    ALB --> ECS
    ECS --> RDS
    ECS --> S3
```

### 6.2 コンテナ設計
```yaml
# docker-compose.yml
version: '3.8'
services:
  api:
    build: ./backend
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/ir_insight
    depends_on:
      - db
    ports:
      - "8000:8000"

  db:
    image: postgres:15
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=ir_insight
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

## 7. 監視・ロギング設計

### 7.1 監視項目
1. システムメトリクス
   - CPU使用率
   - メモリ使用率
   - ディスク使用率
   - ネットワークトラフィック

2. アプリケーションメトリクス
   - API レスポンスタイム
   - エラーレート
   - アクティブユーザー数
   - クローリング成功率

3. ビジネスメトリクス
   - 新規会員登録数
   - 課金額
   - レポート生成数
   - AIVtuber視聴者数

### 7.2 ログ設計
```python
# ログ設定
LOG_CONFIG = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard'
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'app.log',
            'formatter': 'standard'
        }
    },
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        }
    }
}
```

## 8. バックアップ・リカバリ設計

### 8.1 バックアップ戦略
1. データベース
   - フルバックアップ：毎日
   - 差分バックアップ：6時間ごと
   - WALアーカイブ：継続的

2. ファイルストレージ
   - S3バージョニング有効化
   - クロスリージョンレプリケーション

### 8.2 リカバリ手順
```bash
# DBリストア手順
pg_restore -h hostname -U username -d dbname backup.dump

# S3リストア手順
aws s3 sync s3://backup-bucket/2024-01-01/ s3://main-bucket/
```

## 9. デプロイメント設計

### 9.1 CI/CD パイプライン
```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run tests
        run: |
          pip install -r requirements.txt
          pytest

  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to ECS
        run: |
          aws ecs update-service --force-new-deployment
```

### 9.2 ロールバック手順
```bash
# バージョンロールバック
kubectl rollout undo deployment/api-deployment

# データベースロールバック
pg_restore -h hostname -U username -d dbname backup_before_migration.dump
```

## 10. 開発環境設定

### 10.1 ローカル開発環境
```bash
# 環境構築
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 開発サーバー起動
uvicorn app.main:app --reload
```

### 10.2 テスト環境
```python
# テスト設定
pytest_config = {
    'test_db': 'postgresql://test:test@localhost:5432/test_db',
    'mock_openai': True,
    'mock_s3': True
}
``` 