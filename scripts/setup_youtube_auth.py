#!/usr/bin/env python3
"""
YouTube OAuth 初回認証ヘルパー

ブラウザでGoogleログイン → youtube_tokens.json を生成。
一度だけ実行すればOK（以降はトークン自動リフレッシュ）。

Usage:
    python scripts/setup_youtube_auth.py
    python scripts/setup_youtube_auth.py --credentials path/to/client_secrets.json
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")


def main():
    parser = argparse.ArgumentParser(description="YouTube OAuth Setup")
    parser.add_argument(
        "--credentials",
        default="client_secrets.json",
        help="Path to OAuth client_secrets.json from Google Cloud Console",
    )
    parser.add_argument(
        "--token-output",
        default="youtube_tokens.json",
        help="Output path for token file",
    )
    args = parser.parse_args()

    creds_path = Path(args.credentials)
    if not creds_path.exists():
        print(f"❌ {creds_path} が見つかりません。")
        print()
        print("セットアップ手順:")
        print("1. Google Cloud Console → APIs & Services → Credentials")
        print("2. OAuth 2.0 Client ID を作成（Desktop app）")
        print("3. JSON をダウンロードして client_secrets.json として保存")
        print("4. YouTube Data API v3 を有効化")
        print("5. このスクリプトを再実行")
        sys.exit(1)

    from app.services.youtube_live import YouTubeLiveService

    print("🔐 ブラウザが開きます。Googleアカウントでログインしてください...")
    yt = YouTubeLiveService()
    yt.authenticate(credentials_path=str(creds_path))
    yt.save_credentials(token_path=args.token_output)

    print(f"✅ トークンを {args.token_output} に保存しました。")
    print("   以降は自動リフレッシュされるため、再実行は不要です。")


if __name__ == "__main__":
    main()
