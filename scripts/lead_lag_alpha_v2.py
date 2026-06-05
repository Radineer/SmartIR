#!/usr/bin/env python3
"""
Alpha MVP v2: マルチファクター × PCA × 130/30 × XGBoost

4つの改善を段階的に積み上げて効果を検証:
  Step 0: Alpha+PCA baseline (v1結果の再現)
  Step 1: + ファクター追加 (低ボラ, モメンタム加速, 短期リバーサル)
  Step 2: + ユニバース拡大 (51→120銘柄)
  Step 3: + 130/30 (ショート30%追加)
  Step 4: + XGBoost加重 (ML最適化)
"""

import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import yfinance as yf
from scipy import linalg

warnings.filterwarnings("ignore")

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "lead_lag_alpha_v2"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

START_DATE = "2015-01-01"
END_DATE = "2025-12-31"

US_TICKERS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
N_U = len(US_TICKERS)

# Expanded universe: ~7 stocks per TOPIX-17 sector = ~119 stocks
JP_SECTOR_BASKETS_EXPANDED: dict[str, list[str]] = {
    "Foods":      ["2914.T","2502.T","2269.T","2802.T","2801.T","2871.T","2282.T"],
    "Energy":     ["5020.T","1605.T","5019.T","5021.T","1662.T","5011.T","3863.T"],
    "Construction":["1925.T","1928.T","1801.T","1802.T","1803.T","1812.T","1808.T"],
    "Materials":  ["4063.T","4452.T","4901.T","3407.T","4188.T","4005.T","4042.T"],
    "Pharma":     ["4519.T","4568.T","4502.T","4523.T","4578.T","4151.T","4507.T"],
    "Auto":       ["7203.T","7267.T","7261.T","7201.T","7269.T","7270.T","7272.T"],
    "Steel":      ["5802.T","5706.T","5713.T","5411.T","5801.T","5714.T","3436.T"],
    "Machinery":  ["6301.T","6367.T","6503.T","7011.T","6361.T","6302.T","6471.T"],
    "ElecPrecision":["6758.T","6861.T","6902.T","6501.T","6594.T","6762.T","6752.T"],
    "InfoComm":   ["9432.T","9984.T","9433.T","9434.T","4755.T","4689.T","3774.T"],
    "Utilities":  ["9501.T","9502.T","9503.T","9504.T","9505.T","9506.T","9531.T"],
    "Transport":  ["9020.T","9021.T","9022.T","9064.T","9147.T","9101.T","9104.T"],
    "Trading":    ["8058.T","8031.T","8001.T","8002.T","8053.T","8015.T","2768.T"],
    "Retail":     ["9983.T","3382.T","8267.T","3099.T","3088.T","7532.T","2670.T"],
    "Banks":      ["8306.T","8316.T","8411.T","8309.T","8308.T","8331.T","8354.T"],
    "Finance":    ["8766.T","8750.T","8591.T","8601.T","8604.T","8795.T","8697.T"],
    "RealEstate": ["8801.T","8802.T","8830.T","3289.T","8804.T","8803.T","3231.T"],
}

# Original small universe (first 3 per sector)
JP_SECTOR_BASKETS_SMALL = {k: v[:3] for k, v in JP_SECTOR_BASKETS_EXPANDED.items()}

JP_SECTORS = list(JP_SECTOR_BASKETS_EXPANDED.keys())
N_J = len(JP_SECTORS)
N = N_U + N_J

STOCK_TO_SECTOR = {}
for sector, stocks in JP_SECTOR_BASKETS_EXPANDED.items():
    for s in stocks:
        STOCK_TO_SECTOR[s] = sector

LOOKBACK = 60
LAMBDA_REG = 0.9
K_FACTORS = 3
COST_RT_BPS = 15.0
HARD_STOP = -0.20
TRAIL_STOP = -0.15
TP_HALF = 0.30
TP_ALL = 0.60

US_CYCLICAL = {"XLB", "XLE", "XLF", "XLI", "XLK"}
US_DEFENSIVE = {"XLP", "XLU", "XLV", "XLY"}
JP_CYCLICAL = {"Energy", "ElecPrecision", "Trading", "Banks"}
JP_DEFENSIVE = {"Foods", "Pharma", "Utilities", "Retail"}


def download_all_data():
    """Download US ETFs + all JP stocks."""
    all_jp = list({s for stocks in JP_SECTOR_BASKETS_EXPANDED.values() for s in stocks})
    all_tickers = US_TICKERS + all_jp
    print(f"Downloading {len(all_tickers)} tickers ...")
    raw = yf.download(all_tickers, start=START_DATE, end=END_DATE, auto_adjust=True, progress=True)
    close = raw["Close"]
    # Filter to available tickers
    available_jp = [t for t in all_jp if t in close.columns and close[t].notna().sum() > 250]
    print(f"  Available JP stocks: {len(available_jp)}/{len(all_jp)}")
    return close, available_jp


def build_sector_cc(close, jp_stocks):
    """Build sector-level CC returns for PCA."""
    sector_cc = pd.DataFrame(index=close.index)
    for sector in JP_SECTORS:
        stocks_in_sector = [s for s in JP_SECTOR_BASKETS_EXPANDED.get(sector, []) if s in jp_stocks]
        if stocks_in_sector:
            sector_cc[sector] = close[stocks_in_sector].pct_change().mean(axis=1)
    us_cc = close[US_TICKERS].pct_change()
    r_cc = pd.concat([us_cc, sector_cc], axis=1)
    mask = r_cc.notna().all(axis=1)
    return r_cc.loc[mask].iloc[1:]


# ── PCA ────────────────────────────────────────────────────────────────────
def build_V0():
    v1 = np.ones(N) / np.sqrt(N)
    v2_raw = np.array([1.0 if i < N_U else -1.0 for i in range(N)])
    v2_raw -= v2_raw.dot(v1) * v1; v2 = v2_raw / np.linalg.norm(v2_raw)
    names = US_TICKERS + JP_SECTORS
    v3_raw = np.zeros(N)
    for i, n in enumerate(names):
        if n in US_CYCLICAL | JP_CYCLICAL: v3_raw[i] = 1.0
        elif n in US_DEFENSIVE | JP_DEFENSIVE: v3_raw[i] = -1.0
    v3_raw -= v3_raw.dot(v1)*v1; v3_raw -= v3_raw.dot(v2)*v2
    norm = np.linalg.norm(v3_raw)
    v3 = v3_raw/norm if norm>1e-10 else v3_raw
    return np.column_stack([v1, v2, v3])

def build_C0(C, V0):
    inner = V0.T@C@V0; D0 = np.diag(np.diag(inner)); C0r = V0@D0@V0.T
    d = np.sqrt(np.abs(np.diag(C0r))); d[d<1e-10]=1.0
    return C0r * np.outer(1/d, 1/d)

def compute_pca_signals(r_cc, V0):
    cols = US_TICKERS + JP_SECTORS; data = r_cc[cols].values; T = len(data)
    sigs = pd.DataFrame(index=r_cc.index, columns=JP_SECTORS, dtype=float)
    for t in range(LOOKBACK, T):
        w = data[t-LOOKBACK:t]; mu,sig = w.mean(0), w.std(0,ddof=1); sig[sig<1e-10]=1
        z_t = (data[t]-mu)/sig; z_w = (w-mu)/sig
        Ct = np.corrcoef(z_w, rowvar=False)
        if np.any(np.isnan(Ct)): continue
        Ce = np.corrcoef(data[:t], rowvar=False)
        if np.any(np.isnan(Ce)): continue
        C0 = build_C0(Ce, V0); Cr = (1-LAMBDA_REG)*Ct + LAMBDA_REG*C0
        ev, evec = linalg.eigh(Cr); idx = np.argsort(ev)[::-1]
        VK = evec[:,idx[:K_FACTORS]]
        sigs.iloc[t] = VK[N_U:,:] @ (VK[:N_U,:].T @ z_t[:N_U])
    return sigs.dropna(how="all")


# ── Factor Computation ─────────────────────────────────────────────────────
def compute_all_factors(close, jp_stocks, pca_sigs):
    """Compute 8 factors for all stocks (vectorized, fast)."""
    stock_close = close[jp_stocks].copy()
    ret_1w = stock_close.pct_change(5)
    ret_1m = stock_close.pct_change(21)
    ret_3m = stock_close.pct_change(63)
    ret_6m = stock_close.pct_change(126)
    ret_12m = stock_close.pct_change(252)
    ma50 = stock_close.rolling(50).mean()
    ma200 = stock_close.rolling(200).mean()
    vol_60d = stock_close.pct_change().rolling(60).std()
    fwd_ret = stock_close.shift(-21) / stock_close - 1

    # Monthly sampling for speed (use month-end dates)
    dates = stock_close.index[252:]
    monthly_dates = dates[::21]  # every ~21 trading days
    print(f"    Sampling {len(monthly_dates)} monthly dates from {len(dates)} daily ...")

    # PCA sector ranks (precompute)
    pca_ranks = pca_sigs.rank(axis=1, pct=True) if pca_sigs is not None else None

    # Sector median 1M returns (precompute per sector)
    sector_med_1m = {}
    for sector, stocks_in_sec in JP_SECTOR_BASKETS_EXPANDED.items():
        avail = [s for s in stocks_in_sec if s in jp_stocks]
        if avail:
            sector_med_1m[sector] = ret_1m[avail].median(axis=1)

    rows = []
    for dt in monthly_dates:
        for stock in jp_stocks:
            sector = STOCK_TO_SECTOR.get(stock)
            if not sector:
                continue
            c = stock_close.loc[dt, stock]
            if pd.isna(c):
                continue

            r6 = ret_6m.loc[dt, stock]
            r1 = ret_1m.loc[dt, stock]
            r12 = ret_12m.loc[dt, stock]
            r1w = ret_1w.loc[dt, stock]
            r3 = ret_3m.loc[dt, stock]
            m50 = ma50.loc[dt, stock]
            m200 = ma200.loc[dt, stock]
            v = vol_60d.loc[dt, stock]

            pca_val = 0.5
            if pca_ranks is not None and dt in pca_ranks.index:
                pca_val = pca_ranks.loc[dt].get(sector, 0.5)
                if pd.isna(pca_val):
                    pca_val = 0.5

            rel = 0.0
            if sector in sector_med_1m and pd.notna(r1):
                sm = sector_med_1m[sector].loc[dt] if dt in sector_med_1m[sector].index else np.nan
                rel = (r1 - sm) if pd.notna(sm) else 0.0

            rows.append({
                "date": dt, "stock": stock, "sector": sector,
                "value": -r6 if pd.notna(r6) else 0,
                "trend": 1.0 if (pd.notna(m50) and pd.notna(m200) and m50 > m200) else 0.0,
                "rel_strength": rel,
                "pca": pca_val,
                "low_vol": -v if pd.notna(v) else 0,
                "momentum": (r12 - r1) if (pd.notna(r12) and pd.notna(r1)) else 0,
                "reversal": -r1w if pd.notna(r1w) else 0,
                "accel": (r3 - (r6 - r3)) if (pd.notna(r3) and pd.notna(r6)) else 0,
                "fwd_ret": fwd_ret.loc[dt, stock] if dt in fwd_ret.index else np.nan,
            })

    df = pd.DataFrame(rows)
    print(f"  Factor matrix: {len(df)} stock-date observations")
    return df


# ── Portfolio Simulation ───────────────────────────────────────────────────
class Position:
    def __init__(self, stock, entry_price, direction=1):
        self.stock = stock
        self.entry_price = entry_price
        self.direction = direction  # +1 long, -1 short
        self.hwm = entry_price
        self.half_taken = False

    def update(self, price):
        if self.direction == 1:
            self.hwm = max(self.hwm, price)
        else:
            self.hwm = min(self.hwm, price)

    def pnl(self, price):
        return self.direction * (price / self.entry_price - 1)

    def trail_dd(self, price):
        if self.direction == 1:
            return (price - self.hwm) / self.hwm if self.hwm > 0 else 0
        else:
            return -(price - self.hwm) / self.hwm if self.hwm > 0 else 0


def simulate(
    factor_df: pd.DataFrame,
    close: pd.DataFrame,
    score_col: str = "composite",
    max_long: int = 15,
    max_short: int = 0,
    apply_costs: bool = True,
    label: str = "",
):
    """Monthly rebalance, top-N long, bottom-M short, with Alpha risk mgmt."""
    dates = sorted(factor_df["date"].unique())
    all_returns = []
    all_dates = []
    n_trades = 0
    longs = set()
    shorts = set()

    for i in range(len(dates) - 1):
        dt, next_dt = dates[i], dates[i + 1]
        snapshot = factor_df[factor_df["date"] == dt]
        if snapshot.empty:
            continue

        ranked = snapshot.sort_values(score_col, ascending=False)
        new_longs = set(ranked.head(max_long)["stock"].tolist())
        new_shorts = set(ranked.tail(max_short)["stock"].tolist()) if max_short > 0 else set()

        # Count trades
        n_trades += len(new_longs.symmetric_difference(longs))
        n_trades += len(new_shorts.symmetric_difference(shorts))
        longs, shorts = new_longs, new_shorts

        # Period return (dt → next_dt)
        all_stocks = list(longs | shorts)
        if not all_stocks:
            continue

        avail = [s for s in all_stocks if s in close.columns]
        if not avail:
            continue

        # Find daily dates in this period
        daily_in_period = close.index[(close.index > dt) & (close.index <= next_dt)]
        if len(daily_in_period) == 0:
            continue

        for d_dt in daily_in_period:
            pnl = 0.0
            prev_idx = close.index.get_loc(d_dt)
            if prev_idx == 0:
                continue

            n_pos = len(longs) + len(shorts)
            weight = 1.0 / max(n_pos, 1)

            for stock in longs:
                if stock not in close.columns:
                    continue
                p = close.iloc[prev_idx][stock]
                p_prev = close.iloc[prev_idx - 1][stock]
                if pd.notna(p) and pd.notna(p_prev) and p_prev > 0:
                    pnl += weight * (p - p_prev) / p_prev

            for stock in shorts:
                if stock not in close.columns:
                    continue
                p = close.iloc[prev_idx][stock]
                p_prev = close.iloc[prev_idx - 1][stock]
                if pd.notna(p) and pd.notna(p_prev) and p_prev > 0:
                    pnl -= weight * (p - p_prev) / p_prev

            all_returns.append(pnl)
            all_dates.append(d_dt)

    # Apply costs at rebalance points (spread across period)
    ret = pd.Series(all_returns, index=pd.DatetimeIndex(all_dates))
    if apply_costs and len(dates) > 1:
        cost_per_period = n_trades * COST_RT_BPS / 10000 / len(dates)
        # Distribute cost across all daily returns
        ret -= cost_per_period / 21  # ~21 days per monthly period

    monthly = ret.resample("ME").sum()
    ar = monthly.mean() * 12
    risk = monthly.std(ddof=1) * np.sqrt(12)
    rr = ar / risk if risk > 1e-10 else 0
    cum = (1 + ret).cumprod()
    mdd = ((cum - cum.cummax()) / cum.cummax()).min()

    return ret, {
        "AR%": ar*100, "RISK%": risk*100, "R/R": rr, "MDD%": mdd*100,
        "Trades/yr": n_trades / (len(ret)/250) if len(ret) > 0 else 0,
    }


def main():
    print("=" * 70)
    print("Alpha v2: Multi-Factor × PCA × 130/30 × XGBoost")
    print("=" * 70)

    close, available_jp = download_all_data()
    V0 = build_V0()

    # PCA signals
    print("\n── PCA Sector Signals ──")
    small_stocks = [s for s in sum(JP_SECTOR_BASKETS_SMALL.values(), []) if s in available_jp]
    r_cc = build_sector_cc(close, small_stocks)
    pca_sigs = compute_pca_signals(r_cc, V0)

    # Factor computation
    print("\n── Factor Computation ──")

    # Small universe (51 stocks)
    print("  [Small universe: ~51 stocks]")
    factor_small = compute_all_factors(close, small_stocks, pca_sigs)

    # Expanded universe (~120 stocks)
    print("  [Expanded universe: ~120 stocks]")
    factor_large = compute_all_factors(close, available_jp, pca_sigs)

    # ── Scoring ──
    factor_cols = ["value", "trend", "rel_strength", "pca", "low_vol", "momentum", "reversal", "accel"]

    def add_simple_score(df, cols):
        """Rank each factor cross-sectionally, then average ranks."""
        for dt in df["date"].unique():
            mask = df["date"] == dt
            for col in cols:
                df.loc[mask, f"{col}_rank"] = df.loc[mask, col].rank(pct=True)
        rank_cols = [f"{c}_rank" for c in cols]
        df["composite"] = df[rank_cols].mean(axis=1)
        return df

    def add_xgb_score(df, cols):
        """Walk-forward XGBoost: retrain yearly, predict monthly."""
        try:
            from xgboost import XGBRegressor
        except ImportError:
            print("  XGBoost not available, using simple score")
            return add_simple_score(df, cols)

        df["xgb_score"] = 0.5
        dates = sorted(df["date"].unique())
        retrain_every = 12  # months

        for i, dt in enumerate(dates):
            # Use all past data for training
            train = df[df["date"] < dt].dropna(subset=cols + ["fwd_ret"])
            if len(train) < 200:
                # Not enough data, use simple rank
                mask = df["date"] == dt
                df.loc[mask, "xgb_score"] = df.loc[mask, cols].rank(pct=True).mean(axis=1)
                continue

            if i % retrain_every == 0:
                X_train = train[cols].values
                y_train = train["fwd_ret"].values
                model = XGBRegressor(
                    max_depth=3, n_estimators=200, learning_rate=0.05,
                    min_child_weight=30, subsample=0.8, colsample_bytree=0.8,
                    verbosity=0, random_state=42,
                )
                model.fit(X_train, y_train)

            mask = df["date"] == dt
            test = df.loc[mask, cols]
            if len(test) > 0 and 'model' in dir():
                df.loc[mask, "xgb_score"] = model.predict(test.values)

        return df

    # ── Step 0: Alpha+PCA baseline (small universe, 3 basic factors + PCA) ──
    print("\n── Step-by-Step Improvement ──")
    strategies = {}
    all_rows = []

    def add(label, ret, stats):
        strategies[label] = ret
        stats["Strategy"] = label
        all_rows.append(stats)
        print(f"  {label:>35}: AR={stats['AR%']:>7.2f}%  R/R={stats['R/R']:>5.2f}  "
              f"MDD={stats['MDD%']:>7.2f}%  Trades/yr={stats.get('Trades/yr',0):>5.0f}")

    # Step 0: Baseline (3 factors + PCA, small universe)
    f0 = factor_small.copy()
    f0 = add_simple_score(f0, ["value", "trend", "rel_strength", "pca"])
    ret, stats = simulate(f0, close, max_long=10, label="Step0")
    add("Step0: Alpha+PCA (51 stocks)", ret, stats)

    # Step 1: + More factors (8 factors, small universe)
    f1 = factor_small.copy()
    f1 = add_simple_score(f1, factor_cols)
    ret, stats = simulate(f1, close, max_long=10, label="Step1")
    add("Step1: +3 factors (51 stocks)", ret, stats)

    # Step 2: + Expanded universe (8 factors, 120 stocks)
    f2 = factor_large.copy()
    f2 = add_simple_score(f2, factor_cols)
    ret, stats = simulate(f2, close, max_long=15, label="Step2")
    add("Step2: +universe (120 stocks)", ret, stats)

    # Step 3: + 130/30 (8 factors, 120 stocks, long 15 + short 5)
    f3 = factor_large.copy()
    f3 = add_simple_score(f3, factor_cols)
    ret, stats = simulate(f3, close, max_long=15, max_short=5, label="Step3")
    add("Step3: +130/30", ret, stats)

    # Step 4: + XGBoost (ML scoring)
    print("  Computing XGBoost scores (walk-forward) ...")
    f4 = factor_large.copy()
    f4 = add_xgb_score(f4, factor_cols)
    ret, stats = simulate(f4, close, score_col="xgb_score", max_long=15, max_short=5, label="Step4")
    add("Step4: +XGBoost", ret, stats)

    # Step 4 gross
    ret_g, stats_g = simulate(f4, close, score_col="xgb_score", max_long=15, max_short=5,
                               apply_costs=False, label="Step4_gross")
    add("Step4 gross (no costs)", ret_g, stats_g)

    # Benchmark: equal-weight all JP stocks
    bh = close[available_jp].pct_change().mean(axis=1)
    bh = bh.loc[strategies["Step0: Alpha+PCA (51 stocks)"].index[0]:]
    strategies["JP B&H"] = bh
    bh_stats = {"AR%": bh.resample("ME").sum().mean()*1200, "RISK%": bh.resample("ME").sum().std(ddof=1)*np.sqrt(12)*100,
                "R/R": 0, "MDD%": 0, "Trades/yr": 0}
    bh_stats["R/R"] = bh_stats["AR%"]/bh_stats["RISK%"] if bh_stats["RISK%"]>0 else 0
    cum_bh = (1+bh).cumprod(); bh_stats["MDD%"] = ((cum_bh-cum_bh.cummax())/cum_bh.cummax()).min()*100
    bh_stats["Strategy"] = "JP B&H"
    all_rows.append(bh_stats)
    print(f"  {'JP B&H':>35}: AR={bh_stats['AR%']:>7.2f}%  R/R={bh_stats['R/R']:>5.2f}  MDD={bh_stats['MDD%']:>7.2f}%")

    # ── Summary ──
    print(f"\n{'='*70}")
    print("Summary: Incremental Improvement")
    print(f"{'='*70}")
    df_sum = pd.DataFrame(all_rows)
    print(df_sum[["Strategy","AR%","RISK%","R/R","MDD%","Trades/yr"]].to_string(
        index=False, float_format="{:.2f}".format))
    df_sum.to_csv(OUTPUT_DIR / "strategy_comparison.csv", index=False)

    # ── XGBoost feature importance ──
    try:
        from xgboost import XGBRegressor
        train = f4.dropna(subset=factor_cols+["fwd_ret"])
        model = XGBRegressor(max_depth=3, n_estimators=200, learning_rate=0.05,
                             min_child_weight=30, verbosity=0)
        model.fit(train[factor_cols].values, train["fwd_ret"].values)
        imp = pd.Series(model.feature_importances_, index=factor_cols).sort_values(ascending=False)
        print(f"\n── XGBoost Feature Importance ──")
        for f, v in imp.items():
            bar = "#" * int(v * 50)
            print(f"  {f:>15}: {v:.3f} {bar}")
    except Exception:
        pass

    # ── Year-by-year for best strategy ──
    best_name = max(all_rows[:-1], key=lambda x: x["R/R"])["Strategy"]
    if best_name in strategies:
        print(f"\n── Year-by-Year: {best_name} ──")
        yearly = strategies[best_name].resample("YE").sum()
        wins = sum(1 for r in yearly if r > 0)
        for dt, r in yearly.items():
            print(f"  {dt.year}: {r*100:>7.2f}% [{'+'if r>0 else '-'}]")
        print(f"  Win rate: {wins}/{len(yearly)} ({wins/len(yearly)*100:.0f}%)")

    # ── 250万円シミュレーション ──
    if best_name in strategies:
        best_ar = [r for r in all_rows if r["Strategy"]==best_name][0]["AR%"] / 100
        capital = 2_500_000
        print(f"\n── 250万円運用シミュレーション (年率{best_ar*100:.1f}%) ──")
        for y in [1, 2, 3, 5, 10]:
            total = capital * (1 + best_ar) ** y
            profit = total - capital
            print(f"  {y}年後: {total/10000:>8.0f}万円 (利益 +{profit/10000:>7.0f}万円)")

    # ── Chart ──
    fig, ax = plt.subplots(figsize=(14, 7))
    palette = ["#888888", "#aaaacc", "#4488cc", "#44aa44", "#cc4444", "#ff8800", "#cccccc"]
    for i, (name, ret) in enumerate(strategies.items()):
        cum = (1 + ret).cumprod()
        lw = 2.5 if "Step4:" in name else 1.2
        ls = "--" if "gross" in name or "B&H" in name else "-"
        ax.plot(cum.index, cum.values, label=name, color=palette[i%len(palette)], linewidth=lw, linestyle=ls)
    ax.set_title("Alpha v2: Step-by-Step Improvement", fontsize=14)
    ax.set_ylabel("Growth of ¥1")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "cumulative_returns.png", dpi=150)
    plt.close(fig)
    print(f"\n  Chart: {OUTPUT_DIR / 'cumulative_returns.png'}")

    print(f"\n{'='*70}")
    print(f"Done. Outputs: {OUTPUT_DIR}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
