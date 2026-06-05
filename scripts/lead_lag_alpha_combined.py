#!/usr/bin/env python3
"""
Lead-Lag PCA × Alpha MVP 統合バックテスト

Alpha MVPのバリュー/テクニカルスコアリングに、PCAリードラグのセクタータイミングを
第6ファクターとして追加。PCAを単独で売買するのではなく、バリュー株の
エントリータイミングの精度向上に使う。

比較:
  A) Alpha Only: バリュー+テクニカルのみ (Score ≥ 2 で買い)
  B) Alpha + PCA: 上記 + PCAセクタータイミング (Score ≥ 2 かつ PCA+ で買い)
  C) PCA Only: v1のセクターL/S (参考)

共通リスク管理 (Alpha準拠):
  - -20% ハードストップ
  - -15% トレイリングストップ (高値更新から)
  - +30% 半分利確
  - +60% 全利確
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

warnings.filterwarnings("ignore", category=FutureWarning)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "lead_lag_alpha"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

START_DATE = "2015-01-01"
END_DATE = "2025-12-31"

# US sector ETFs for PCA signal
US_TICKERS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
N_U = len(US_TICKERS)

# JP stocks grouped by TOPIX-17 sector
JP_SECTOR_BASKETS: dict[str, list[str]] = {
    "Foods":         ["2914.T", "2502.T", "2269.T"],
    "Energy":        ["5020.T", "1605.T", "5019.T"],
    "Construction":  ["5401.T", "1925.T", "1928.T"],
    "Materials":     ["4063.T", "4452.T", "4901.T"],
    "Pharma":        ["4519.T", "4568.T", "4502.T"],
    "Auto":          ["7203.T", "7267.T", "7261.T"],
    "Steel":         ["5802.T", "5706.T", "5713.T"],
    "Machinery":     ["6301.T", "6367.T", "6503.T"],
    "ElecPrecision": ["6758.T", "6861.T", "6902.T"],
    "InfoComm":      ["9432.T", "9984.T", "9433.T"],
    "Utilities":     ["9501.T", "9502.T", "9503.T"],
    "Transport":     ["9020.T", "9021.T", "9022.T"],
    "Trading":       ["8058.T", "8031.T", "8001.T"],
    "Retail":        ["9983.T", "3382.T", "8267.T"],
    "Banks":         ["8306.T", "8316.T", "8411.T"],
    "Finance":       ["8766.T", "8750.T", "8591.T"],
    "RealEstate":    ["8801.T", "8802.T", "8830.T"],
}

# Stock → sector mapping
STOCK_TO_SECTOR = {}
for sector, stocks in JP_SECTOR_BASKETS.items():
    for s in stocks:
        STOCK_TO_SECTOR[s] = sector

JP_SECTORS = list(JP_SECTOR_BASKETS.keys())
JP_STOCKS = [s for stocks in JP_SECTOR_BASKETS.values() for s in stocks]
N_J = len(JP_SECTORS)
N = N_U + N_J

LOOKBACK = 60
LAMBDA_REG = 0.9
K_FACTORS = 3

# Alpha risk management parameters
HARD_STOP = -0.20
TRAIL_STOP = -0.15
TP_HALF = 0.30
TP_ALL = 0.60

# Position sizing
MAX_POSITIONS = 10
POSITION_SIZE = 1.0 / MAX_POSITIONS  # 10% per position

# Transaction cost (round-trip, bps)
COST_RT_BPS = 15.0

# Cyclical/Defensive for PCA
US_CYCLICAL = {"XLB", "XLE", "XLF", "XLI", "XLK"}
US_DEFENSIVE = {"XLP", "XLU", "XLV", "XLY"}
JP_CYCLICAL = {"Energy", "ElecPrecision", "Trading", "Banks"}
JP_DEFENSIVE = {"Foods", "Pharma", "Utilities", "Retail"}


# ── Data ───────────────────────────────────────────────────────────────────
def download_data():
    all_tickers = US_TICKERS + JP_STOCKS
    print(f"Downloading {len(all_tickers)} tickers ...")
    raw = yf.download(all_tickers, start=START_DATE, end=END_DATE, auto_adjust=True, progress=True)
    close = raw["Close"]

    # Sector-level CC returns for PCA
    sector_cc = pd.DataFrame(index=close.index)
    for sector, stocks in JP_SECTOR_BASKETS.items():
        avail = [s for s in stocks if s in close.columns]
        if avail:
            sector_cc[sector] = close[avail].pct_change().mean(axis=1)

    us_cc = close[US_TICKERS].pct_change()
    r_cc_pca = pd.concat([us_cc, sector_cc], axis=1)

    # Stock-level data
    stock_close = close[JP_STOCKS]

    # Common dates
    mask = r_cc_pca.notna().all(axis=1) & stock_close.notna().all(axis=1)
    r_cc_pca = r_cc_pca.loc[mask].iloc[1:]
    stock_close = stock_close.loc[r_cc_pca.index]

    print(f"Trading days: {len(r_cc_pca)} ({r_cc_pca.index[0].date()} – {r_cc_pca.index[-1].date()})")
    return r_cc_pca, stock_close


# ── PCA Sector Signals ─────────────────────────────────────────────────────
def build_prior_exposures():
    v1 = np.ones(N) / np.sqrt(N)
    v2_raw = np.array([1.0 if i < N_U else -1.0 for i in range(N)])
    v2_raw -= v2_raw.dot(v1) * v1
    v2 = v2_raw / np.linalg.norm(v2_raw)
    all_names = US_TICKERS + JP_SECTORS
    v3_raw = np.zeros(N)
    for i, name in enumerate(all_names):
        if name in US_CYCLICAL or name in JP_CYCLICAL:
            v3_raw[i] = 1.0
        elif name in US_DEFENSIVE or name in JP_DEFENSIVE:
            v3_raw[i] = -1.0
    v3_raw -= v3_raw.dot(v1) * v1
    v3_raw -= v3_raw.dot(v2) * v2
    norm = np.linalg.norm(v3_raw)
    v3 = v3_raw / norm if norm > 1e-10 else v3_raw
    return np.column_stack([v1, v2, v3])


def build_target_matrix(C, V0):
    inner = V0.T @ C @ V0
    D0 = np.diag(np.diag(inner))
    C0_raw = V0 @ D0 @ V0.T
    delta = np.sqrt(np.abs(np.diag(C0_raw)))
    delta[delta < 1e-10] = 1.0
    return C0_raw * np.outer(1.0 / delta, 1.0 / delta)


def compute_pca_sector_signals(r_cc: pd.DataFrame, V0: np.ndarray) -> pd.DataFrame:
    """Returns DataFrame of JP sector predicted z-scores."""
    all_cols = US_TICKERS + JP_SECTORS
    data = r_cc[all_cols].values
    T = len(data)
    signals = pd.DataFrame(index=r_cc.index, columns=JP_SECTORS, dtype=float)

    print("  Computing PCA sector signals ...")
    for t in range(LOOKBACK, T):
        w = data[t - LOOKBACK : t]
        mu, sig = w.mean(0), w.std(0, ddof=1)
        sig[sig < 1e-10] = 1.0
        z_t = (data[t] - mu) / sig
        z_w = (w - mu) / sig
        C_t = np.corrcoef(z_w, rowvar=False)
        if np.any(np.isnan(C_t)):
            continue
        C_exp = np.corrcoef(data[:t], rowvar=False)
        if np.any(np.isnan(C_exp)):
            continue
        C0 = build_target_matrix(C_exp, V0)
        C_reg = (1 - LAMBDA_REG) * C_t + LAMBDA_REG * C0
        evals, evecs = linalg.eigh(C_reg)
        idx = np.argsort(evals)[::-1]
        V_K = evecs[:, idx[:K_FACTORS]]
        f = V_K[:N_U, :].T @ z_t[:N_U]
        signals.iloc[t] = V_K[N_U:, :] @ f

    return signals.dropna(how="all")


def pca_sector_is_positive(signals_row: pd.Series, sector: str, q: float = 0.30) -> bool:
    """Is this sector in the top q of PCA predictions?"""
    if signals_row.isna().any():
        return False
    ranked = signals_row.rank(pct=True)
    return ranked[sector] >= (1.0 - q)


# ── Alpha-Style Stock Scoring ─────────────────────────────────────────────
def compute_alpha_scores(stock_close: pd.DataFrame) -> pd.DataFrame:
    """
    Simplified Alpha scoring using price-only factors:
    ① Contrarian Value: 6M return < 0 (mean-reversion candidate) → +1
    ② Trend: 50DMA > 200DMA (uptrend confirmation) → +1
    ③ Relative Strength: 1M return > sector median → +1
    """
    scores = pd.DataFrame(index=stock_close.index, columns=JP_STOCKS, dtype=float)

    ret_1m = stock_close.pct_change(21)
    ret_6m = stock_close.pct_change(126)
    ma50 = stock_close.rolling(50).mean()
    ma200 = stock_close.rolling(200).mean()

    for stock in JP_STOCKS:
        sector = STOCK_TO_SECTOR[stock]
        sector_stocks = JP_SECTOR_BASKETS[sector]
        avail = [s for s in sector_stocks if s in stock_close.columns]

        s = pd.Series(0.0, index=stock_close.index)

        # ① Contrarian: 6M return < 0
        s += (ret_6m[stock] < 0).astype(float)

        # ② Trend: MA50 > MA200
        s += (ma50[stock] > ma200[stock]).astype(float)

        # ③ Relative strength: 1M return > sector median
        if len(avail) > 1:
            sector_median = ret_1m[avail].median(axis=1)
            s += (ret_1m[stock] > sector_median).astype(float)

        scores[stock] = s

    return scores.dropna(how="all")


# ── Portfolio Simulation ───────────────────────────────────────────────────
class Position:
    def __init__(self, stock: str, entry_price: float, entry_date):
        self.stock = stock
        self.entry_price = entry_price
        self.entry_date = entry_date
        self.high_watermark = entry_price
        self.half_taken = False

    def update_hwm(self, price: float):
        self.high_watermark = max(self.high_watermark, price)

    def pnl_pct(self, price: float) -> float:
        return (price - self.entry_price) / self.entry_price

    def trail_dd(self, price: float) -> float:
        if self.high_watermark <= 0:
            return 0
        return (price - self.high_watermark) / self.high_watermark


def simulate_portfolio(
    stock_close: pd.DataFrame,
    alpha_scores: pd.DataFrame,
    pca_signals: pd.DataFrame | None,
    use_pca: bool = False,
    min_alpha_score: float = 2.0,
    pca_top_q: float = 0.30,
    apply_costs: bool = True,
    label: str = "",
) -> tuple[pd.Series, dict]:
    """
    Simulate a long-only portfolio with Alpha scoring + optional PCA timing.

    Entry: alpha_score >= min_alpha_score (and PCA sector positive if use_pca)
    Exit: Hard stop, trailing stop, or profit-taking
    """
    common = alpha_scores.index
    if pca_signals is not None:
        common = common.intersection(pca_signals.index)
    common = common.intersection(stock_close.index)
    dates = list(common)

    positions: dict[str, Position] = {}
    portfolio_returns = []
    portfolio_dates = []
    n_buys = 0
    n_sells = 0

    for i in range(1, len(dates)):
        today = dates[i]
        yesterday = dates[i - 1]

        daily_pnl = 0.0
        cost_today = 0.0

        # Update existing positions
        closed = []
        for stock, pos in list(positions.items()):
            price = stock_close.loc[today, stock]
            if pd.isna(price):
                continue

            pos.update_hwm(price)
            pnl = pos.pnl_pct(price)
            trail = pos.trail_dd(price)

            # Exit checks (Alpha risk management)
            exit_reason = None
            if pnl <= HARD_STOP:
                exit_reason = "STOP"
            elif trail <= TRAIL_STOP:
                exit_reason = "TRAIL"
            elif not pos.half_taken and pnl >= TP_HALF:
                # Half profit-taking
                pos.half_taken = True
                daily_pnl += POSITION_SIZE * 0.5 * (price / pos.entry_price - 1)
                if apply_costs:
                    cost_today += POSITION_SIZE * 0.5 * COST_RT_BPS / 10000
                continue  # keep remaining half
            elif pnl >= TP_ALL:
                exit_reason = "TP_ALL"

            if exit_reason:
                weight = POSITION_SIZE * (0.5 if pos.half_taken else 1.0)
                daily_pnl += weight * (price / pos.entry_price - 1)
                if apply_costs:
                    cost_today += weight * COST_RT_BPS / 10000
                closed.append(stock)
                n_sells += 1
            else:
                # Mark-to-market
                prev_price = stock_close.loc[yesterday, stock]
                if pd.notna(prev_price) and prev_price > 0:
                    weight = POSITION_SIZE * (0.5 if pos.half_taken else 1.0)
                    daily_pnl += weight * (price - prev_price) / prev_price

        for stock in closed:
            del positions[stock]

        # New entries (if slots available)
        if len(positions) < MAX_POSITIONS:
            scores_today = alpha_scores.loc[yesterday] if yesterday in alpha_scores.index else None
            pca_today = pca_signals.loc[yesterday] if (pca_signals is not None and yesterday in pca_signals.index) else None

            if scores_today is not None:
                # Rank stocks by score, pick best available
                candidates = []
                for stock in JP_STOCKS:
                    if stock in positions:
                        continue
                    score = scores_today.get(stock, 0)
                    if pd.isna(score):
                        continue
                    if score < min_alpha_score:
                        continue

                    # PCA filter
                    if use_pca and pca_today is not None:
                        sector = STOCK_TO_SECTOR[stock]
                        if not pca_sector_is_positive(pca_today, sector, pca_top_q):
                            continue

                    candidates.append((stock, score))

                # Sort by score descending
                candidates.sort(key=lambda x: -x[1])

                for stock, _ in candidates[:MAX_POSITIONS - len(positions)]:
                    price = stock_close.loc[today, stock]
                    if pd.isna(price) or price <= 0:
                        continue
                    positions[stock] = Position(stock, price, today)
                    n_buys += 1
                    if apply_costs:
                        cost_today += POSITION_SIZE * COST_RT_BPS / 10000

        portfolio_returns.append(daily_pnl - cost_today)
        portfolio_dates.append(today)

    ret = pd.Series(portfolio_returns, index=pd.DatetimeIndex(portfolio_dates))
    stats = compute_stats(ret)
    stats["N_buys"] = n_buys
    stats["N_sells"] = n_sells
    stats["Trades/yr"] = (n_buys + n_sells) / (len(ret) / 250) if len(ret) > 0 else 0
    return ret, stats


def compute_stats(returns: pd.Series) -> dict:
    if len(returns) == 0:
        return {"AR%": 0, "RISK%": 0, "R/R": 0, "MDD%": 0}
    monthly = returns.resample("ME").sum()
    if len(monthly) < 2:
        return {"AR%": 0, "RISK%": 0, "R/R": 0, "MDD%": 0}
    ar = monthly.mean() * 12
    risk = monthly.std(ddof=1) * np.sqrt(12)
    rr = ar / risk if risk > 1e-10 else 0
    cum = (1 + returns).cumprod()
    mdd = ((cum - cum.cummax()) / cum.cummax()).min()
    return {"AR%": ar * 100, "RISK%": risk * 100, "R/R": rr, "MDD%": mdd * 100}


def plot_results(strategies):
    fig, axes = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={"height_ratios": [3, 1]})
    palette = ["#cc4444", "#4488cc", "#44aa44", "#ff8800", "#888888"]
    ax = axes[0]
    for i, (name, ret) in enumerate(strategies.items()):
        cum = (1 + ret).cumprod()
        lw = 2.5 if "Alpha+PCA" in name else 1.2
        ax.plot(cum.index, cum.values, label=name, color=palette[i % len(palette)], linewidth=lw)
    ax.set_title("Alpha MVP + PCA Lead-Lag Integration", fontsize=14)
    ax.set_ylabel("Growth of $1")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.3)

    # Drawdown comparison
    ax2 = axes[1]
    for i, (name, ret) in enumerate(strategies.items()):
        if "Alpha" not in name:
            continue
        cum = (1 + ret).cumprod()
        dd = (cum - cum.cummax()) / cum.cummax() * 100
        ax2.plot(dd.index, dd.values, label=name, color=palette[i % len(palette)], alpha=0.7)
    ax2.set_ylabel("Drawdown %")
    ax2.legend(loc="lower left")
    ax2.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "cumulative_returns.png", dpi=150)
    plt.close(fig)


def main():
    print("=" * 70)
    print("Alpha MVP + PCA Lead-Lag Integration Backtest")
    print("=" * 70)

    r_cc_pca, stock_close = download_data()
    V0 = build_prior_exposures()

    # PCA sector signals
    print("\n── PCA Sector Signals ──")
    pca_signals = compute_pca_sector_signals(r_cc_pca, V0)

    # Alpha scores
    print("\n── Alpha Scores ──")
    alpha_scores = compute_alpha_scores(stock_close)
    print(f"  Score dates: {len(alpha_scores)}")

    # Strategy variants
    strategies: dict[str, pd.Series] = {}
    all_rows = []

    def add(label, ret, stats):
        strategies[label] = ret
        stats["Strategy"] = label
        all_rows.append(stats)
        print(f"  {label:>25}: AR={stats['AR%']:>7.2f}%  RISK={stats['RISK%']:>6.2f}%  "
              f"R/R={stats['R/R']:>5.2f}  MDD={stats['MDD%']:>7.2f}%  "
              f"Trades/yr={stats.get('Trades/yr', 0):>5.0f}")

    print("\n── Strategy Comparison ──")

    # A) Alpha Only (score ≥ 2)
    ret, stats = simulate_portfolio(stock_close, alpha_scores, None,
                                     use_pca=False, min_alpha_score=2.0)
    add("Alpha Only (≥2)", ret, stats)

    # B) Alpha + PCA (score ≥ 2 AND PCA sector positive)
    ret, stats = simulate_portfolio(stock_close, alpha_scores, pca_signals,
                                     use_pca=True, min_alpha_score=2.0, pca_top_q=0.30)
    add("Alpha+PCA (≥2,top30%)", ret, stats)

    # C) Alpha + PCA with top 50%
    ret, stats = simulate_portfolio(stock_close, alpha_scores, pca_signals,
                                     use_pca=True, min_alpha_score=2.0, pca_top_q=0.50)
    add("Alpha+PCA (≥2,top50%)", ret, stats)

    # D) Alpha only with higher threshold
    ret, stats = simulate_portfolio(stock_close, alpha_scores, None,
                                     use_pca=False, min_alpha_score=3.0)
    add("Alpha Only (≥3)", ret, stats)

    # E) Buy & hold equal weight all JP stocks
    bh_ret = stock_close.pct_change().mean(axis=1).loc[strategies["Alpha Only (≥2)"].index]
    strategies["JP Equal-Weight B&H"] = bh_ret
    bh_stats = compute_stats(bh_ret)
    bh_stats["Strategy"] = "JP Equal-Weight B&H"
    bh_stats["Trades/yr"] = 0
    all_rows.append(bh_stats)
    print(f"  {'JP Equal-Weight B&H':>25}: AR={bh_stats['AR%']:>7.2f}%  RISK={bh_stats['RISK%']:>6.2f}%  "
          f"R/R={bh_stats['R/R']:>5.2f}  MDD={bh_stats['MDD%']:>7.2f}%")

    # Summary
    print(f"\n{'=' * 70}")
    print("Summary")
    print(f"{'=' * 70}")
    df = pd.DataFrame(all_rows)
    print(df[["Strategy", "AR%", "RISK%", "R/R", "MDD%", "Trades/yr"]].to_string(
        index=False, float_format="{:.2f}".format))
    df.to_csv(OUTPUT_DIR / "strategy_comparison.csv", index=False)

    # Year-by-year comparison
    print(f"\n── Year-by-Year: Alpha Only vs Alpha+PCA ──")
    a_only = strategies["Alpha Only (≥2)"]
    a_pca = strategies["Alpha+PCA (≥2,top30%)"]
    yearly_a = a_only.resample("YE").sum()
    yearly_ap = a_pca.resample("YE").sum()
    print(f"  {'Year':>6} {'Alpha':>10} {'Alpha+PCA':>10} {'Diff':>10}")
    wins = 0
    for dt in yearly_a.index:
        ra = yearly_a.loc[dt] * 100
        if dt in yearly_ap.index:
            rp = yearly_ap.loc[dt] * 100
        else:
            rp = 0
        diff = rp - ra
        if diff > 0:
            wins += 1
        print(f"  {dt.year:>6} {ra:>9.2f}% {rp:>9.2f}% {diff:>+9.2f}%")
    total_years = len(yearly_a)
    print(f"  PCA improves: {wins}/{total_years} years ({wins/total_years*100:.0f}%)")

    # Chart
    plot_results(strategies)
    print(f"\n  Chart saved: {OUTPUT_DIR / 'cumulative_returns.png'}")

    # Save
    pd.DataFrame({k: v for k, v in strategies.items()}).to_csv(OUTPUT_DIR / "daily_returns.csv")

    print(f"\n{'=' * 70}")
    print(f"Done. All outputs: {OUTPUT_DIR}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
