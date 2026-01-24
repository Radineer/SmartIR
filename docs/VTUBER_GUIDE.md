# イリスVTuber配信システム 運用ガイド

## システム概要

IR資料からAIが台本を生成し、3DVTuber「イリス」が解説する動画を自動生成・配信するシステム。

## アーキテクチャ

```
IR資料 → AI分析 → 台本生成 → TTS音声 → VRM制御 → 動画生成 → YouTube配信
```

## セットアップ

### 1. 必要なソフトウェア

- Node.js 20+
- Python 3.11+
- VOICEVOX（TTS用）
- PostgreSQL（データベース）

### 2. 環境変数設定

`.env` ファイルに以下を設定:

```env
# データベース
DATABASE_URL=postgresql://user:pass@localhost:5432/smartir

# OpenAI
OPENAI_API_KEY=sk-xxx

# VOICEVOX
VOICEVOX_HOST=http://localhost:50021

# YouTube API
YOUTUBE_CLIENT_ID=xxx
YOUTUBE_CLIENT_SECRET=xxx
```

### 3. VRMモデル配置

`frontend/public/models/vrm/` にVRMファイルを配置

推奨入手先:
- VRoid Hub: https://hub.vroid.com/
- BOOTH: https://booth.pm/

## 使用方法

### 台本生成

1. `/vtuber` ページにアクセス
2. IR資料を選択
3. 「台本を生成」ボタンをクリック
4. 生成完了後「音声を生成」で音声プレビュー

### 動画生成

```bash
cd frontend
npm run remotion:render
```

出力: `out/video.mp4`

### YouTube配信

1. Google Cloud ConsoleでOAuth設定
2. `client_secrets.json` を配置
3. POST `/api/broadcast/schedule` でスケジュール

## トラブルシューティング

### VOICEVOXに接続できない
- VOICEVOXが起動しているか確認
- ポート50021が開いているか確認

### VRMモデルが表示されない
- ブラウザコンソールでエラー確認
- モデルパスが正しいか確認

### 動画生成が遅い
- GPUアクセラレーション有効化
- Remotionのコンカレンシー設定確認

## 定期配信設定

```bash
# 毎日20:00に自動配信
POST /api/broadcast/daily/setup
{
  "hour": 20,
  "minute": 0
}
```

## 技術スタック

| レイヤー | 技術 |
|----------|------|
| フロントエンド | Next.js 16, React, Tailwind CSS |
| 3D表示 | @pixiv/three-vrm, React Three Fiber |
| 動画生成 | Remotion |
| TTS | VOICEVOX |
| バックエンド | FastAPI, Python |
| DB | PostgreSQL |
| 配信 | YouTube Data API v3 |

## ライセンス・クレジット

- VOICEVOX使用時はクレジット表記必須
- VRMモデルは各モデルのライセンスに従う
