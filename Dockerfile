FROM python:3.11-slim

# 必要なパッケージのインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    tesseract-ocr \
    tesseract-ocr-jpn \
    && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリの設定
WORKDIR /app

# 依存関係ファイルのコピー
COPY requirements.txt .

# 依存関係のインストール
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションのコピー
COPY . .

# 環境変数の設定
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# ポートの公開
EXPOSE 8000

# サーバーの起動
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 