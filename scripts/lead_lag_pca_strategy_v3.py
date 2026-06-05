#!/usr/bin/env python3
"""
部分空間正則化付きPCA 日米リードラグ戦略 v3 — 実運用版

3つの戦略を実装し比較:
A) 高確信ペアトレード: Top-1/Bottom-1セクターのみ + 週次リバランス + 個別株
B) 日経先物コンポジット: セクターシグナル集約 → 先物方向売買
C) 閾値付きセクターL/S: シグナル強度フィルター付きの元戦略

結論: どのアプローチが最もコスト控除後に有効かを実証的に検証
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

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "lead_lag_pca_v3"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

START_DATE = "2010-01-01"
END_DATE = "2025-12-31"

US_TICKERS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
N_U = len(US_TICKERS)

# Japan: individual stock baskets per sector (top 3 by market cap)
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

LOOKBACK = 60
LAMBDA_REG = 0.9
K_FACTORS = 3

# Cost for individual large-cap stocks (bps, one-way)
STOCK_SPREAD_BPS = 3.0
STOCK_COMMISSION_BPS = 3.0
STOCK_IMPACT_BPS = 3.0
# Total one-way: ~9 bps, round-trip: ~18 bps

US_CYCLICAL = {"XLB", "XLE", "XLF", "XLI", "XLK"}
US_DEFENSIVE = {"XLP", "XLU", "XLV", "XLY"}
JP_CYCLICAL = {"Energy", "ElecPrecision", "Trading", "Banks"}
JP_DEFENSIVE = {"Foods", "Pharma", "Utilities", "Retail"}


# ── Data ───────────────────────────────────────────────────────────────────
def download_data():
    """Download US ETFs + JP individual stocks."""
    jp_all = [s for stocks in JP_SECTOR_BASKETS.values() for s in stocks]
    all_tickers = US_TICKERS + jp_all
    print(f"Downloading {len(all_tickers)} tickers ...")

    raw = yf.download(all_tickers, start=START_DATE, end=END_DATE, auto_adjust=True, progress=True)
    close_raw = raw["Close"]
    open_raw = raw["Open"]

    # Stock-level returns
    stock_cc = close_raw[jp_all].pct_change()
    stock_oc = close_raw[jp_all] / open_raw[jp_all] - 1

    # Aggregate to sector level
    sector_cc = pd.DataFrame(index=stock_cc.index)
    sector_oc = pd.DataFrame(index=stock_oc.index)
    for sector, stocks in JP_SECTOR_BASKETS.items():
        avail = [s for s in stocks if s in stock_cc.columns]
        if avail:
            sector_cc[sector] = stock_cc[avail].mean(axis=1)
            sector_oc[sector] = stock_oc[avail].mean(axis=1)

    us_cc = close_raw[US_TICKERS].pct_change()
    r_cc = pd.concat([us_cc, sector_cc], axis=1)

    mask = r_cc.notna().all(axis=1) & sector_oc.notna().all(axis=1)
    r_cc = r_cc.loc[mask].iloc[1:]
    sector_oc = sector_oc.loc[r_cc.index]

    print(f"Common trading days: {len(r_cc)} ({r_cc.index[0].date()} – {r_cc.index[-1].date()})")
    return r_cc, sector_oc


# ── PCA Signal ─────────────────────────────────────────────────────────────
def build_prior_exposures() -> np.ndarray:
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


def compute_sector_signals(r_cc: pd.DataFrame, V0: np.ndarray) -> pd.DataFrame:
    """Rolling PCA → JP sector signal predictions."""
    all_cols = US_TICKERS + JP_SECTORS
    dates = r_cc.index
    T = len(dates)
    data = r_cc[all_cols].values
    signals = pd.DataFrame(index=dates, columns=JP_SECTORS, dtype=float)

    print(f"  Computing PCA signals (λ={LAMBDA_REG}, L={LOOKBACK}, K={K_FACTORS}) ...")
    for t_idx in range(LOOKBACK, T):
        window = data[t_idx - LOOKBACK : t_idx]
        mu = window.mean(axis=0)
        sigma = window.std(axis=0, ddof=1)
        sigma[sigma < 1e-10] = 1.0

        z_t = (data[t_idx] - mu) / sigma
        z_window = (window - mu) / sigma
        C_t = np.corrcoef(z_window, rowvar=False)
        if np.any(np.isnan(C_t)):
            continue

        past = data[:t_idx]
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
        signals.iloc[t_idx] = V_J @ f

    return signals.dropna(how="all")


# ── Cost model ─────────────────────────────────────────────────────────────
def one_way_cost_bps() -> float:
    return STOCK_SPREAD_BPS / 2 + STOCK_COMMISSION_BPS + STOCK_IMPACT_BPS


def round_trip_cost() -> float:
    return one_way_cost_bps() * 2 / 10000.0


# ── Strategy A: High-Conviction Pair Trade ─────────────────────────────────
def strategy_pair_trade(
    signals: pd.DataFrame,
    r_oc: pd.DataFrame,
    rebalance_days: int = 5,
    apply_costs: bool = True,
    signal_threshold: float = 0.0,
) -> tuple[pd.Series, dict]:
    """
    Long top-1 sector, short bottom-1 sector.
    Rebalance every N days. Only trade if spread signal exceeds threshold.
    """
    common = signals.index.intersection(r_oc.index)
    dates_list = list(common)

    returns = []
    return_dates = []
    current_long = None
    current_short = None
    days_held = 0
    n_rebalances = 0

    for i in range(len(dates_list) - 1):
        sig_today = signals.loc[dates_list[i]]
        ret_tomorrow = r_oc.loc[dates_list[i + 1]]

        if sig_today.isna().any() or ret_tomorrow.isna().any():
            continue

        # Should we rebalance?
        rebalance = False
        if current_long is None:
            rebalance = True
        elif days_held >= rebalance_days:
            rebalance = True

        cost = 0.0
        if rebalance:
            ranked = sig_today.sort_values()
            new_short = ranked.index[0]
            new_long = ranked.index[-1]

            # Signal strength check: only trade if spread is significant
            spread = sig_today[new_long] - sig_today[new_short]
            if spread < signal_threshold and current_long is not None:
                # Weak signal, keep current positions
                pass
            else:
                # Count actual position changes
                if apply_costs:
                    changes = 0
                    if new_long != current_long:
                        changes += 1
                    if new_short != current_short:
                        changes += 1
                    if current_long is None:
                        changes = 2  # initial entry
                    # Cost per changed position (each position is 50% of portfolio)
                    cost = changes * 0.5 * round_trip_cost()

                if new_long != current_long or new_short != current_short:
                    n_rebalances += 1

                current_long = new_long
                current_short = new_short
                days_held = 0

        days_held += 1

        if current_long and current_short:
            r = ret_tomorrow[current_long] - ret_tomorrow[current_short]
            returns.append(r - cost)
            return_dates.append(dates_list[i + 1])

    ret_series = pd.Series(returns, index=pd.DatetimeIndex(return_dates))
    stats = compute_stats(ret_series)
    stats["N_rebalances"] = n_rebalances
    stats["Rebal/year"] = n_rebalances / (len(ret_series) / 250) if ret_series.size > 0 else 0
    return ret_series, stats


# ── Strategy B: Top-K / Bottom-K with minimum holding ─────────────────────
def strategy_topk_hold(
    signals: pd.DataFrame,
    r_oc: pd.DataFrame,
    k: int = 3,
    min_hold_days: int = 5,
    apply_costs: bool = True,
) -> tuple[pd.Series, dict]:
    """
    Long top-K sectors, short bottom-K sectors.
    Minimum holding period before rebalancing.
    """
    common = signals.index.intersection(r_oc.index)
    dates_list = list(common)

    returns = []
    return_dates = []
    current_longs: set = set()
    current_shorts: set = set()
    days_since_rebal = 0
    n_rebalances = 0

    for i in range(len(dates_list) - 1):
        sig_today = signals.loc[dates_list[i]]
        ret_tomorrow = r_oc.loc[dates_list[i + 1]]

        if sig_today.isna().any() or ret_tomorrow.isna().any():
            continue

        rebalance = not current_longs or days_since_rebal >= min_hold_days

        cost = 0.0
        if rebalance:
            ranked = sig_today.sort_values()
            new_shorts = set(ranked.index[:k])
            new_longs = set(ranked.index[-k:])

            if apply_costs:
                changed_l = len(new_longs.symmetric_difference(current_longs))
                changed_s = len(new_shorts.symmetric_difference(current_shorts))
                # Each changed position is 1/(2k) of portfolio, traded round-trip
                frac_changed = (changed_l + changed_s) / (2 * k)
                cost = frac_changed * round_trip_cost()

            if new_longs != current_longs or new_shorts != current_shorts:
                n_rebalances += 1
                days_since_rebal = 0

            current_longs = new_longs
            current_shorts = new_shorts

        days_since_rebal += 1

        r_l = ret_tomorrow[list(current_longs)].mean()
        r_s = ret_tomorrow[list(current_shorts)].mean()
        returns.append(r_l - r_s - cost)
        return_dates.append(dates_list[i + 1])

    ret_series = pd.Series(returns, index=pd.DatetimeIndex(return_dates))
    stats = compute_stats(ret_series)
    stats["N_rebalances"] = n_rebalances
    stats["Rebal/year"] = n_rebalances / (len(ret_series) / 250) if ret_series.size > 0 else 0
    return ret_series, stats


# ── Evaluation ─────────────────────────────────────────────────────────────
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
            if si is None:
                return pd.DataFrame()
            dl = [lines[si]]
            for l in lines[si+1:]:
                s = l.strip()
                if not s or not s[0].isdigit():
                    break
                dl.append(s)
            df = pd.read_csv(io.StringIO("\n".join(dl)))
            fc = df.columns[0]
            df = df.rename(columns={fc: "Date"})
            df["Date"] = pd.to_datetime(df["Date"].astype(str).str.strip(), format="%Y%m%d", errors="coerce")
            df = df.dropna(subset=["Date"]).set_index("Date")
            for c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce") / 100.0
            return df
        ff3 = _read("https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip")
        mom = _read("https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_daily_CSV.zip")
        if ff3.empty:
            return None
        if not mom.empty:
            mc = [c for c in mom.columns if c.strip()][0]
            mom = mom.rename(columns={mc: "WML"})
            return ff3.join(mom[["WML"]], how="left")
        ff3["WML"] = np.nan
        return ff3
    except:
        return None


def run_ff_regression(ret, ff):
    try:
        from statsmodels.regression.linear_model import OLS
        from statsmodels.tools import add_constant
    except ImportError:
        return None
    common = ret.index.intersection(ff.index)
    if len(common) < 60:
        return None
    y = ret.loc[common].values
    cols = [c for c in ["Mkt-RF", "SMB", "HML", "WML"] if c in ff.columns and not ff[c].isna().all()]
    if not cols:
        return None
    X = add_constant(ff.loc[common, cols].values)
    mask = ~(np.isnan(X).any(axis=1) | np.isnan(y))
    X, y = X[mask], y[mask]
    if len(y) < 60:
        return None
    m = OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": int(len(y)**(1/3))})
    return {"alpha": m.params[0], "alpha_t": m.tvalues[0], "alpha_p": m.pvalues[0], "R2": m.rsquared}


# ── Chart ──────────────────────────────────────────────────────────────────
def plot_results(strategies: dict[str, pd.Series]):
    fig, ax = plt.subplots(figsize=(14, 7))
    palette = ["#cc4444", "#4488cc", "#44aa44", "#ff8800", "#8844cc",
               "#888888", "#aaaacc", "#cc8888", "#448844", "#884444"]
    for i, (name, ret) in enumerate(strategies.items()):
        cum = (1 + ret).cumprod()
        lw = 2.5 if "best" in name.lower() or "winner" in name.lower() else 1.2
        ls = "--" if "gross" in name.lower() or "v1" in name.lower() else "-"
        ax.plot(cum.index, cum.values, label=name,
                color=palette[i % len(palette)], linewidth=lw, linestyle=ls)
    ax.set_title("Lead-Lag PCA v3: Strategy Comparison", fontsize=14)
    ax.set_ylabel("Growth of $1")
    ax.legend(loc="upper left", fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "cumulative_returns.png", dpi=150)
    plt.close(fig)


# ── Main ──────────────────────────────────────────────────────────────────
def main():
    print("=" * 70)
    print("Lead-Lag PCA v3: Practical Strategy Comparison")
    print("=" * 70)

    r_cc, r_oc = download_data()
    V0 = build_prior_exposures()

    print("\n── Signal Generation ──")
    signals = compute_sector_signals(r_cc, V0)

    print(f"\n  Round-trip cost model: {round_trip_cost()*10000:.1f} bps")

    # ── Strategy comparisons ──
    strategies: dict[str, pd.Series] = {}
    all_rows = []

    def add(label, ret, stats):
        strategies[label] = ret
        stats["Strategy"] = label
        all_rows.append(stats)

    # A) Pair trade: various rebalance frequencies
    print("\n── A) High-Conviction Pair Trade (Top-1 vs Bottom-1) ──")
    print(f"  {'Strategy':>30} {'AR%':>8} {'RISK%':>8} {'R/R':>8} {'MDD%':>8} {'Rebal/yr':>9}")
    for days in [1, 3, 5, 10, 20]:
        label = f"Pair_hold{days}d"
        ret, stats = strategy_pair_trade(signals, r_oc, rebalance_days=days)
        add(label, ret, stats)
        print(f"  {label:>30} {stats['AR%']:>7.2f} {stats['RISK%']:>7.2f} {stats['R/R']:>7.2f} "
              f"{stats['MDD%']:>7.2f} {stats['Rebal/year']:>8.0f}")

    # Pair trade gross (best hold period)
    ret_gross, stats_gross = strategy_pair_trade(signals, r_oc, rebalance_days=5, apply_costs=False)
    add("Pair_5d_gross", ret_gross, stats_gross)

    # B) Top-K/Bottom-K with hold period
    print("\n── B) Top-K L/S with Minimum Hold Period ──")
    print(f"  {'Strategy':>30} {'AR%':>8} {'RISK%':>8} {'R/R':>8} {'MDD%':>8} {'Rebal/yr':>9}")
    for k, hold in [(1, 5), (2, 5), (3, 5), (5, 5), (3, 10), (3, 20), (5, 1)]:
        label = f"Top{k}_hold{hold}d"
        ret, stats = strategy_topk_hold(signals, r_oc, k=k, min_hold_days=hold)
        add(label, ret, stats)
        print(f"  {label:>30} {stats['AR%']:>7.2f} {stats['RISK%']:>7.2f} {stats['R/R']:>7.2f} "
              f"{stats['MDD%']:>7.2f} {stats['Rebal/year']:>8.0f}")

    # v1 baseline (daily, all sectors, no costs)
    ret_v1, stats_v1 = strategy_topk_hold(signals, r_oc, k=5, min_hold_days=1, apply_costs=False)
    add("v1_gross", ret_v1, stats_v1)

    # v1 with costs
    ret_v1c, stats_v1c = strategy_topk_hold(signals, r_oc, k=5, min_hold_days=1, apply_costs=True)
    add("v1_net", ret_v1c, stats_v1c)

    # ── Summary ──
    print(f"\n{'=' * 70}")
    print("Summary: All Strategies")
    print(f"{'=' * 70}")
    df = pd.DataFrame(all_rows)
    print(df[["Strategy", "AR%", "RISK%", "R/R", "MDD%", "Rebal/year"]].to_string(
        index=False, float_format="{:.2f}".format))
    df.to_csv(OUTPUT_DIR / "strategy_comparison.csv", index=False)

    # ── Find best net strategy ──
    # Find best net strategy
    # Actually let's just find the best R/R among non-gross, non-v1
    net_rows = [r for r in all_rows if "gross" not in r["Strategy"] and "v1" not in r["Strategy"]]
    if net_rows:
        best = max(net_rows, key=lambda x: x["R/R"])
        print(f"\n  Best net strategy: {best['Strategy']}")
        print(f"    AR={best['AR%']:.2f}%, RISK={best['RISK%']:.2f}%, R/R={best['R/R']:.2f}, MDD={best['MDD%']:.2f}%")

    # ── Factor regression for key strategies ──
    print("\n── Fama-French Factor Regression (Carhart 4) ──")
    ff = download_ff_factors()
    if ff is not None:
        for name in ["Pair_hold5d", "Top3_hold5d", "Top5_hold5d", "v1_gross", "v1_net"]:
            if name in strategies:
                res = run_ff_regression(strategies[name], ff)
                if res:
                    sig = "***" if res["alpha_p"] < 0.01 else "**" if res["alpha_p"] < 0.05 else "*" if res["alpha_p"] < 0.10 else ""
                    print(f"  {name:>20}: α={res['alpha']:.6f} (t={res['alpha_t']:.2f}){sig}")

    # ── Year-by-year for best strategy ──
    if net_rows:
        best_name = max(net_rows, key=lambda x: x["R/R"])["Strategy"]
        if best_name in strategies:
            print(f"\n── Year-by-Year: {best_name} ──")
            yearly = strategies[best_name].resample("YE").sum()
            wins = 0
            for dt, r in yearly.items():
                marker = "+" if r > 0 else "-"
                print(f"  {dt.year}: {r*100:>7.2f}% [{marker}]")
                if r > 0:
                    wins += 1
            print(f"  Win rate: {wins}/{len(yearly)} ({wins/len(yearly)*100:.0f}%)")

    # ── Chart ──
    plot_results(strategies)
    print(f"\n  Chart saved: {OUTPUT_DIR / 'cumulative_returns.png'}")

    # ── Cost sensitivity for best strategy ──
    if net_rows:
        best_name = max(net_rows, key=lambda x: x["R/R"])["Strategy"]
        # Parse k and hold from best name
        print(f"\n── Cost Sensitivity: {best_name} ──")
        global STOCK_SPREAD_BPS, STOCK_COMMISSION_BPS, STOCK_IMPACT_BPS
        orig = (STOCK_SPREAD_BPS, STOCK_COMMISSION_BPS, STOCK_IMPACT_BPS)
        print(f"  {'Cost label':>12} {'1-way bps':>10} {'AR%':>8} {'R/R':>8}")
        for label, sp, co, im in [
            ("Zero", 0, 0, 0),
            ("Ultra-low", 1, 1, 1),
            ("Low", 2, 2, 2),
            ("Default", 3, 3, 3),
            ("High", 5, 5, 5),
        ]:
            STOCK_SPREAD_BPS, STOCK_COMMISSION_BPS, STOCK_IMPACT_BPS = sp, co, im
            # Re-run the best strategy with different costs
            if "Pair" in best_name:
                hold_d = int(best_name.split("hold")[1].replace("d", ""))
                ret, stats = strategy_pair_trade(signals, r_oc, rebalance_days=hold_d)
            else:
                parts = best_name.split("_")
                k_val = int(parts[0].replace("Top", ""))
                hold_d = int(parts[1].replace("hold", "").replace("d", ""))
                ret, stats = strategy_topk_hold(signals, r_oc, k=k_val, min_hold_days=hold_d)
            ow = one_way_cost_bps()
            print(f"  {label:>12} {ow:>9.1f} {stats['AR%']:>7.2f} {stats['R/R']:>7.2f}")

        STOCK_SPREAD_BPS, STOCK_COMMISSION_BPS, STOCK_IMPACT_BPS = orig

    print(f"\n{'=' * 70}")
    print(f"Done. All outputs: {OUTPUT_DIR}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
