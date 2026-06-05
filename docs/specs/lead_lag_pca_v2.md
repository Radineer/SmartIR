# 設計: Lead-Lag PCA Strategy v2

## アーキテクチャ

```
scripts/lead_lag_pca_strategy_v2.py (単一スクリプト)

┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│ Data Layer   │────▶│ Signal Layer │────▶│ Portfolio    │
│              │     │              │     │ Layer        │
│ - yfinance   │     │ - PCA_SUB    │     │ - コスト控除 │
│ - 個別株     │     │ - MOM        │     │ - IC選別     │
│ - VIX        │     │ - REV        │     │ - VIXサイジング│
│ - FF factors │     │ - Ensemble   │     │ - 週次リバランス│
└─────────────┘     │ - 適応λ      │     └──────┬───────┘
                    └──────────────┘            │
                                         ┌──────▼───────┐
                                         │ Evaluation   │
                                         │ - AR/RISK/RR │
                                         │ - MDD        │
                                         │ - FF回帰     │
                                         │ - 累積チャート│
                                         └──────────────┘
```

## データフロー

1. US ETF 9銘柄 + JP個別株 51銘柄(17セクター×3) + VIX → yfinance
2. JP個別株 → セクター等ウェイト平均でセクターリターン合成
3. CC/OCリターン計算 → 共通営業日フィルタ
4. ローリングウィンドウ(L=60) → 標準化 → 相関行列
5. 適応的λ選択 → 正則化PCA → ファクタースコア → JPシグナル
6. MOM/REVシグナル生成 → アンサンブル(単純平均)
7. セクター別IC計算 → 低ICセクター除外
8. ロングショートポートフォリオ → コスト控除 → VIXサイジング
9. 評価指標 + FF回帰 + チャート出力

## コストモデル

```
cost_per_trade = spread/2 + commission + impact_coeff * sqrt(trade_size/ADV)

デフォルト:
  spread = 5bps (大型株)
  commission = 5bps (片道)
  impact_coeff = 10bps (二次インパクト簡易版)
  → 片道 ~15-20bps、往復 ~30-40bps
```

## 出力

- `output/lead_lag_pca_v2/` 配下
- table1_sector_ic.csv: セクター別IC分析
- table2_strategy_comparison.csv: v1 vs v2戦略比較
- table3_factor_regression.csv: FF3/Carhart4回帰
- cumulative_returns.png: コスト控除前後の累積リターン
- daily_returns.csv: 全戦略日次リターン
