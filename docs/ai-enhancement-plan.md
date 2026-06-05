# SmartIR AI強化設計案

## S29: センチメント分析 (OpenClaw Gateway経由)
- analysis.ts の INSERT 前に POST http://127.0.0.1:18789/v1/messages
- プロンプト: "IR文書のセンチメントを positive/negative/neutral の0-1スコアで分析"
- 結果を sentiment_positive/negative/neutral に保存

## S30: 決算短信テーブル抽出
- documents テーブルに doc_type='earnings' でフィルタ
- 数値項目(売上/営業利益/経常利益/純利益)を前期比で差分計算
- JSON形式で analysis_results.key_points に保存

## S32: Cloudflare Workers AI
```toml
# wrangler.toml に追加
[ai]
binding = "AI"
```
- Workers AI の @cf/huggingface/distilbert-sst-2-int8 (無料) でセンチメント分類
- OpenClaw Gateway不要、エッジ推論で低レイテンシ
