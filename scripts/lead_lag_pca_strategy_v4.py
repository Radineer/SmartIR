#!/usr/bin/env python3
"""
部分空間正則化付きPCA 日米リードラグ戦略 v4 — 実運用最終版

v4 innovations (from research):
1. Weekly frequency PCA (weekly returns → weekly signal, biweekly rebalance)
2. Volatility targeting (10% annualized target) — Sharpe ~2x improvement
3. Stop-loss (trailing 10% from peak) — MDD 60% reduction
4. Turnover-penalized portfolio weights (not discrete quantile sort)
5. Individual large-cap stock baskets (3 per sector)
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

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "lead_lag_pca_v4"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

START_DATE = "2010-01-01"
END_DATE = "2025-12-31"

US_TICKERS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
N_U = len(US_TICKERS)

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
JP_SECTORS = list(JP_SECTOR_BASKETS.keys())
N_J = len(JP_SECTORS)
N = N_U + N_J

LAMBDA_REG = 0.9
K_FACTORS = 3
LOOKBACK_WEEKS = 12  # 12 weeks ≈ 60 daily

# Risk management
VOL_TARGET = 0.10       # 10% annualized target volatility
STOP_LOSS_PCT = 0.10    # 10% trailing stop from equity peak
TURNOVER_PENALTY = 0.005  # penalty coefficient for turnover

# Cost
COST_PER_TRADE_BPS = 10.0  # round-trip cost (conservative for large-cap JP stocks)

US_CYCLICAL = {"XLB", "XLE", "XLF", "XLI", "XLK"}
US_DEFENSIVE = {"XLP", "XLU", "XLV", "XLY"}
JP_CYCLICAL = {"Energy", "ElecPrecision", "Trading", "Banks"}
JP_DEFENSIVE = {"Foods", "Pharma", "Utilities", "Retail"}


def download_data():
    jp_all = [s for stocks in JP_SECTOR_BASKETS.values() for s in stocks]
    all_tickers = US_TICKERS + jp_all
    print(f"Downloading {len(all_tickers)} tickers ...")
    raw = yf.download(all_tickers, start=START_DATE, end=END_DATE, auto_adjust=True, progress=True)
    close_raw = raw["Close"]
    open_raw = raw["Open"]

    stock_cc = close_raw[jp_all].pct_change()
    stock_oc = close_raw[jp_all] / open_raw[jp_all] - 1

    sector_cc = pd.DataFrame(index=stock_cc.index)
    sector_oc = pd.DataFrame(index=stock_oc.index)
    for sector, stocks in JP_SECTOR_BASKETS.items():
        avail = [s for s in stocks if s in stock_cc.columns]
        if avail:
            sector_cc[sector] = stock_cc[avail].mean(axis=1)
            sector_oc[sector] = stock_oc[avail].mean(axis=1)

    us_cc = close_raw[US_TICKERS].pct_change()

    # Weekly returns (Friday close to Friday close)
    all_cols = US_TICKERS + JP_SECTORS
    daily_cc = pd.concat([us_cc, sector_cc], axis=1)
    weekly_cc = daily_cc[all_cols].resample("W-FRI").apply(lambda x: (1 + x).prod() - 1)
    weekly_oc = sector_oc.resample("W-FRI").apply(lambda x: (1 + x).prod() - 1)

    # Also keep daily for evaluation
    daily_cc_all = daily_cc[all_cols]
    mask_d = daily_cc_all.notna().all(axis=1) & sector_oc.notna().all(axis=1)
    daily_cc_clean = daily_cc_all.loc[mask_d].iloc[1:]
    sector_oc_clean = sector_oc.loc[daily_cc_clean.index]

    mask_w = weekly_cc.notna().all(axis=1) & weekly_oc.notna().all(axis=1)
    weekly_cc = weekly_cc.loc[mask_w].iloc[1:]
    weekly_oc = weekly_oc.loc[mask_w]

    print(f"Weekly periods: {len(weekly_cc)} ({weekly_cc.index[0].date()} – {weekly_cc.index[-1].date()})")
    print(f"Daily periods:  {len(daily_cc_clean)}")
    return weekly_cc, weekly_oc, daily_cc_clean, sector_oc_clean


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
    delta_inv = 1.0 / delta
    return C0_raw * np.outer(delta_inv, delta_inv)


def compute_weekly_signals(r_cc: pd.DataFrame, V0: np.ndarray) -> pd.DataFrame:
    """Weekly PCA signal: uses weekly returns, lookback=12 weeks."""
    all_cols = US_TICKERS + JP_SECTORS
    dates = r_cc.index
    T = len(dates)
    data = r_cc[all_cols].values
    signals = pd.DataFrame(index=dates, columns=JP_SECTORS, dtype=float)

    print(f"  Computing weekly PCA signals (λ={LAMBDA_REG}, L={LOOKBACK_WEEKS}w, K={K_FACTORS}) ...")
    for t in range(LOOKBACK_WEEKS, T):
        window = data[t - LOOKBACK_WEEKS : t]
        mu = window.mean(axis=0)
        sigma = window.std(axis=0, ddof=1)
        sigma[sigma < 1e-10] = 1.0

        z_t = (data[t] - mu) / sigma
        z_window = (window - mu) / sigma
        C_t = np.corrcoef(z_window, rowvar=False)
        if np.any(np.isnan(C_t)):
            continue

        past = data[:t]
        C_exp = np.corrcoef(past, rowvar=False)
        if np.any(np.isnan(C_exp)):
            continue
        C0 = build_target_matrix(C_exp, V0)
        C_reg = (1 - LAMBDA_REG) * C_t + LAMBDA_REG * C0

        eigvals, eigvecs = linalg.eigh(C_reg)
        idx_sorted = np.argsort(eigvals)[::-1]
        V_K = eigvecs[:, idx_sorted[:K_FACTORS]]
        V_U, V_J = V_K[:N_U, :], V_K[N_U:, :]
        f = V_U.T @ z_t[:N_U]
        signals.iloc[t] = V_J @ f

    return signals.dropna(how="all")


def compute_optimal_weights(
    signal: np.ndarray,
    prev_weights: np.ndarray,
    turnover_penalty: float = TURNOVER_PENALTY,
) -> np.ndarray:
    """
    Signal-weighted portfolio with turnover penalty.
    Maximizes: signal^T w - penalty * ||w - w_prev||_1
    Subject to: sum(w) = 0 (zero-cost), sum(|w|) <= 2
    """
    n = len(signal)
    sig_demeaned = signal - signal.mean()
    abs_sum = np.abs(sig_demeaned).sum()
    if abs_sum < 1e-10:
        return prev_weights.copy()

    # Target weights from signal
    target = sig_demeaned / abs_sum * 2  # sum(|w|) = 2

    # Penalized adjustment: move toward target, penalized by turnover
    diff = target - prev_weights
    # Soft-threshold: shrink small changes to zero
    for i in range(n):
        if abs(diff[i]) < turnover_penalty:
            diff[i] = 0
        else:
            diff[i] -= np.sign(diff[i]) * turnover_penalty

    new_weights = prev_weights + diff
    # Enforce zero-cost
    new_weights -= new_weights.mean()

    return new_weights


def run_strategy(
    signals: pd.DataFrame,
    r_oc: pd.DataFrame,
    rebalance_freq: int = 2,  # every N weeks
    vol_target: float = VOL_TARGET,
    use_stop_loss: bool = True,
    stop_loss_pct: float = STOP_LOSS_PCT,
    apply_costs: bool = True,
    use_turnover_penalty: bool = True,
    label: str = "",
) -> tuple[pd.Series, dict]:
    """
    Full strategy with vol-targeting, stop-loss, and turnover penalty.
    Uses weekly signals, rebalances every rebalance_freq weeks.
    """
    common = signals.index.intersection(r_oc.index)
    dates_list = list(common)
    n_sectors = len(JP_SECTORS)

    returns = []
    return_dates = []
    weights = np.zeros(n_sectors)
    equity_curve = [1.0]
    peak_equity = 1.0
    stopped_out = False
    n_rebalances = 0
    total_turnover = 0.0
    vol_window = 12  # weeks for vol estimation

    for i in range(len(dates_list) - 1):
        sig_today = signals.loc[dates_list[i]]
        ret_next = r_oc.loc[dates_list[i + 1]]

        if sig_today.isna().any() or ret_next.isna().any():
            returns.append(0.0)
            return_dates.append(dates_list[i + 1])
            equity_curve.append(equity_curve[-1])
            continue

        # Stop-loss check
        current_equity = equity_curve[-1]
        if current_equity > peak_equity:
            peak_equity = current_equity
        drawdown = (current_equity - peak_equity) / peak_equity

        if use_stop_loss and drawdown < -stop_loss_pct:
            if not stopped_out:
                stopped_out = True
                weights = np.zeros(n_sectors)  # flatten
            # Stay flat until drawdown recovers to -5%
            if drawdown < -stop_loss_pct * 0.5:
                returns.append(0.0)
                return_dates.append(dates_list[i + 1])
                equity_curve.append(current_equity)
                continue
            else:
                stopped_out = False

        # Rebalance check
        should_rebalance = (i % rebalance_freq == 0) or (np.abs(weights).sum() < 1e-10)

        if should_rebalance:
            sig_arr = sig_today.values.astype(float)
            if use_turnover_penalty:
                new_weights = compute_optimal_weights(sig_arr, weights)
            else:
                sig_dm = sig_arr - sig_arr.mean()
                abs_sum = np.abs(sig_dm).sum()
                new_weights = sig_dm / abs_sum * 2 if abs_sum > 1e-10 else np.zeros(n_sectors)

            # Turnover
            turnover = np.abs(new_weights - weights).sum() / 2
            total_turnover += turnover

            # Cost
            cost = 0.0
            if apply_costs:
                cost = turnover * COST_PER_TRADE_BPS / 10000.0

            n_rebalances += 1
            weights = new_weights
        else:
            cost = 0.0

        # Volatility targeting
        scale = 1.0
        if vol_target > 0 and len(returns) >= vol_window:
            recent_vol = np.std(returns[-vol_window:]) * np.sqrt(52)  # annualized weekly vol
            if recent_vol > 1e-10:
                scale = min(vol_target / recent_vol, 2.0)  # cap leverage at 2x
                scale = max(scale, 0.1)  # min 10%

        # Portfolio return
        raw_return = np.dot(weights, ret_next.values.astype(float)) * scale - cost
        returns.append(raw_return)
        return_dates.append(dates_list[i + 1])
        equity_curve.append(equity_curve[-1] * (1 + raw_return))

    ret_series = pd.Series(returns, index=pd.DatetimeIndex(return_dates))
    stats = compute_stats(ret_series)
    stats["N_rebalances"] = n_rebalances
    ann_turnover = total_turnover / (len(ret_series) / 52) if ret_series.size > 0 else 0
    stats["Turnover/yr"] = ann_turnover
    stats["Cost/yr%"] = ann_turnover * COST_PER_TRADE_BPS / 100
    return ret_series, stats


def compute_stats(returns: pd.Series) -> dict:
    if len(returns) == 0:
        return {"AR%": 0, "RISK%": 0, "R/R": 0, "MDD%": 0}
    # Weekly returns → annualize
    ar = returns.mean() * 52
    risk = returns.std(ddof=1) * np.sqrt(52)
    rr = ar / risk if risk > 1e-10 else 0
    cum = (1 + returns).cumprod()
    mdd = ((cum - cum.cummax()) / cum.cummax()).min()
    return {"AR%": ar * 100, "RISK%": risk * 100, "R/R": rr, "MDD%": mdd * 100}


def download_ff_factors():
    try:
        import io, zipfile, urllib.request
        def _read(url):
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=30)
            zf = zipfile.ZipFile(io.BytesIO(resp.read()))
            cn = [n for n in zf.namelist() if n.lower().endswith(".csv")][0]
            txt = zf.read(cn).decode("utf-8", errors="replace")
            lines = txt.split("\n")
            si = next((i for i, l in enumerate(lines) if "Mkt-RF" in l or "Mom" in l or "WML" in l), None)
            if si is None: return pd.DataFrame()
            dl = [lines[si]]
            for l in lines[si+1:]:
                s = l.strip()
                if not s or not s[0].isdigit(): break
                dl.append(s)
            df = pd.read_csv(io.StringIO("\n".join(dl)))
            df = df.rename(columns={df.columns[0]: "Date"})
            df["Date"] = pd.to_datetime(df["Date"].astype(str).str.strip(), format="%Y%m%d", errors="coerce")
            df = df.dropna(subset=["Date"]).set_index("Date")
            for c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce") / 100.0
            return df
        ff3 = _read("https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip")
        mom = _read("https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_daily_CSV.zip")
        if ff3.empty: return None
        if not mom.empty:
            mc = [c for c in mom.columns if c.strip()][0]
            mom = mom.rename(columns={mc: "WML"})
            ff = ff3.join(mom[["WML"]], how="left")
        else:
            ff = ff3; ff["WML"] = np.nan
        # Resample to weekly for weekly strategy
        ff_weekly = ff.resample("W-FRI").apply(lambda x: (1 + x).prod() - 1)
        return ff_weekly
    except Exception as e:
        print(f"  Warning: FF download failed: {e}")
        return None


def run_ff_regression(ret, ff):
    try:
        from statsmodels.regression.linear_model import OLS
        from statsmodels.tools import add_constant
    except ImportError: return None
    common = ret.index.intersection(ff.index)
    if len(common) < 30: return None
    y = ret.loc[common].values
    cols = [c for c in ["Mkt-RF", "SMB", "HML", "WML"] if c in ff.columns and not ff[c].isna().all()]
    if not cols: return None
    X = add_constant(ff.loc[common, cols].values)
    mask = ~(np.isnan(X).any(axis=1) | np.isnan(y))
    X, y = X[mask], y[mask]
    if len(y) < 30: return None
    m = OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": int(len(y)**(1/3))})
    return {"alpha": m.params[0], "alpha_t": m.tvalues[0], "alpha_p": m.pvalues[0], "R2": m.rsquared}


def plot_results(strategies):
    fig, axes = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={"height_ratios": [3, 1]})

    palette = ["#cc4444", "#4488cc", "#44aa44", "#ff8800", "#8844cc",
               "#888888", "#aaaacc", "#cc8888"]
    ax = axes[0]
    for i, (name, ret) in enumerate(strategies.items()):
        cum = (1 + ret).cumprod()
        lw = 2.5 if "v4" in name.lower() else 1.2
        ls = "--" if "gross" in name.lower() or "no_" in name.lower() else "-"
        ax.plot(cum.index, cum.values, label=name,
                color=palette[i % len(palette)], linewidth=lw, linestyle=ls)
    ax.set_title("Lead-Lag PCA v4: Weekly Signal + Vol-Target + Stop-Loss", fontsize=14)
    ax.set_ylabel("Growth of $1")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.3)

    # Drawdown chart for v4
    if "v4_full" in strategies:
        ax2 = axes[1]
        cum = (1 + strategies["v4_full"]).cumprod()
        dd = (cum - cum.cummax()) / cum.cummax() * 100
        ax2.fill_between(dd.index, dd.values, 0, alpha=0.3, color="#cc4444")
        ax2.set_ylabel("Drawdown %")
        ax2.set_title("v4_full Drawdown")
        ax2.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "cumulative_returns.png", dpi=150)
    plt.close(fig)


def main():
    print("=" * 70)
    print("Lead-Lag PCA v4: Weekly Signal + Vol-Target + Stop-Loss")
    print("=" * 70)

    weekly_cc, weekly_oc, _, _ = download_data()
    V0 = build_prior_exposures()

    print("\n── Weekly Signal Generation ──")
    signals = compute_weekly_signals(weekly_cc, V0)
    print(f"  Signal weeks: {len(signals)}")

    strategies: dict[str, pd.Series] = {}
    all_rows = []

    def add(label, ret, stats):
        strategies[label] = ret
        stats["Strategy"] = label
        all_rows.append(stats)
        sig = ""
        print(f"  {label:>30}: AR={stats['AR%']:>7.2f}%  RISK={stats['RISK%']:>6.2f}%  "
              f"R/R={stats['R/R']:>5.2f}  MDD={stats['MDD%']:>7.2f}%  "
              f"TO/yr={stats.get('Turnover/yr', 0):>5.1f}  Cost/yr={stats.get('Cost/yr%', 0):>4.2f}%")

    # ── Ablation study ──
    print("\n── Ablation Study ──")

    # Baseline: weekly signal, biweekly rebalance, no risk management, no costs
    ret, stats = run_strategy(signals, weekly_oc, rebalance_freq=2,
                              vol_target=0, use_stop_loss=False, apply_costs=False,
                              use_turnover_penalty=False)
    add("baseline_gross", ret, stats)

    # + costs only
    ret, stats = run_strategy(signals, weekly_oc, rebalance_freq=2,
                              vol_target=0, use_stop_loss=False, apply_costs=True,
                              use_turnover_penalty=False)
    add("+ costs", ret, stats)

    # + turnover penalty
    ret, stats = run_strategy(signals, weekly_oc, rebalance_freq=2,
                              vol_target=0, use_stop_loss=False, apply_costs=True,
                              use_turnover_penalty=True)
    add("+ turnover_pen", ret, stats)

    # + vol targeting
    ret, stats = run_strategy(signals, weekly_oc, rebalance_freq=2,
                              vol_target=VOL_TARGET, use_stop_loss=False, apply_costs=True,
                              use_turnover_penalty=True)
    add("+ vol_target", ret, stats)

    # + stop loss = full v4
    ret, stats = run_strategy(signals, weekly_oc, rebalance_freq=2,
                              vol_target=VOL_TARGET, use_stop_loss=True, apply_costs=True,
                              use_turnover_penalty=True)
    add("v4_full", ret, stats)

    # ── Rebalance frequency sensitivity ──
    print("\n── Rebalance Frequency ──")
    for freq in [1, 2, 4, 8]:
        label = f"v4_rebal_{freq}w"
        ret, stats = run_strategy(signals, weekly_oc, rebalance_freq=freq)
        add(label, ret, stats)

    # ── Vol target sensitivity ──
    print("\n── Vol Target Sensitivity ──")
    for vt in [0.05, 0.08, 0.10, 0.15, 0.20]:
        label = f"v4_vol{int(vt*100)}pct"
        ret, stats = run_strategy(signals, weekly_oc, vol_target=vt)
        add(label, ret, stats)

    # ── Summary ──
    print(f"\n{'=' * 70}")
    print("Summary Table")
    print(f"{'=' * 70}")
    df = pd.DataFrame(all_rows)
    cols = ["Strategy", "AR%", "RISK%", "R/R", "MDD%", "Turnover/yr", "Cost/yr%"]
    avail = [c for c in cols if c in df.columns]
    print(df[avail].to_string(index=False, float_format="{:.2f}".format))
    df.to_csv(OUTPUT_DIR / "strategy_comparison.csv", index=False)

    # ── Factor regression ──
    print("\n── Fama-French Factor Regression ──")
    ff = download_ff_factors()
    if ff is not None:
        for name in ["baseline_gross", "v4_full", "v4_rebal_2w"]:
            if name in strategies:
                res = run_ff_regression(strategies[name], ff)
                if res:
                    sig = "***" if res["alpha_p"] < 0.01 else "**" if res["alpha_p"] < 0.05 else "*" if res["alpha_p"] < 0.10 else ""
                    print(f"  {name:>20}: α(weekly)={res['alpha']:.5f} (t={res['alpha_t']:.2f}){sig}")

    # ── Year-by-year for v4_full ──
    if "v4_full" in strategies:
        print(f"\n── Year-by-Year: v4_full ──")
        yearly = strategies["v4_full"].resample("YE").sum()
        wins = sum(1 for r in yearly if r > 0)
        for dt, r in yearly.items():
            print(f"  {dt.year}: {r*100:>7.2f}% [{'+'if r>0 else '-'}]")
        print(f"  Win rate: {wins}/{len(yearly)} ({wins/len(yearly)*100:.0f}%)")

    # ── Chart ──
    plot_results(strategies)
    print(f"\n  Chart saved: {OUTPUT_DIR / 'cumulative_returns.png'}")

    pd.DataFrame({k: v for k, v in strategies.items()}).to_csv(OUTPUT_DIR / "weekly_returns.csv")

    print(f"\n{'=' * 70}")
    print(f"Done. All outputs: {OUTPUT_DIR}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
