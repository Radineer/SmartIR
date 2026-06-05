#!/usr/bin/env python3
"""
部分空間正則化付きPCA 日米業種リードラグ投資戦略
Based on: 中川ら (SIG-FIN-036-13)

US sector ETFs (close-to-close) → predict Japan sector ETFs (next-day open-to-close)
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

# ── Configuration ──────────────────────────────────────────────────────────
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "lead_lag_pca"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

START_DATE = "2010-01-01"
END_DATE = "2025-12-31"

# US Select Sector SPDR ETFs (N_U = 9)
# XLRE (2015上場) と XLC (2018上場) を除外し、論文の2010年開始に対応
US_TICKERS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]

# Japan NEXT FUNDS TOPIX-17 sector ETFs (N_J = 17)
JP_TICKERS = [f"{i}.T" for i in range(1617, 1634)]

N_U = len(US_TICKERS)
N_J = len(JP_TICKERS)
N = N_U + N_J  # 28

LOOKBACK = 60       # estimation window L
LAMBDA_REG = 0.9    # regularization parameter
K_FACTORS = 3       # number of eigenvectors
Q_QUANTILE = 0.3    # long/short quantile

# Cyclical / Defensive classification
US_CYCLICAL = {"XLB", "XLE", "XLF", "XLI", "XLK"}
US_DEFENSIVE = {"XLP", "XLU", "XLV", "XLY"}

JP_CYCLICAL_CODES = {1618, 1625, 1629, 1631}
JP_DEFENSIVE_CODES = {1617, 1621, 1627, 1630}
JP_CYCLICAL = {f"{c}.T" for c in JP_CYCLICAL_CODES}
JP_DEFENSIVE = {f"{c}.T" for c in JP_DEFENSIVE_CODES}


# ── Step 1: Data Download ─────────────────────────────────────────────────
def download_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Download OHLC data for US and JP ETFs, return close/open DataFrames on common dates."""
    all_tickers = US_TICKERS + JP_TICKERS
    print(f"Downloading {len(all_tickers)} tickers from {START_DATE} to {END_DATE} ...")

    raw = yf.download(all_tickers, start=START_DATE, end=END_DATE, auto_adjust=True, progress=True)

    close = raw["Close"][all_tickers].copy()
    open_ = raw["Open"][all_tickers].copy()

    # Keep only common business days (both US and JP traded)
    mask = close.notna().all(axis=1) & open_.notna().all(axis=1)
    close = close.loc[mask]
    open_ = open_.loc[mask]

    print(f"Common trading days: {len(close)} ({close.index[0].date()} – {close.index[-1].date()})")
    return close, open_, raw


# ── Step 2: Return Calculation ─────────────────────────────────────────────
def compute_returns(close: pd.DataFrame, open_: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    r_cc: close-to-close return (all tickers, for estimation)
    r_oc: open-to-close return (JP tickers only, for strategy evaluation)
    """
    r_cc = close.pct_change().dropna()
    r_oc = (close[JP_TICKERS] / open_[JP_TICKERS] - 1).loc[r_cc.index]
    return r_cc, r_oc


# ── Step 3: Prior Exposure Matrix V0 ──────────────────────────────────────
def build_prior_exposures() -> np.ndarray:
    """Build N×3 prior exposure matrix V0 with Gram-Schmidt orthogonalization."""
    all_tickers = US_TICKERS + JP_TICKERS

    # v1: global (equal weight, normalized)
    v1 = np.ones(N) / np.sqrt(N)

    # v2: country spread (+1 US, -1 JP), orthogonalized to v1
    v2_raw = np.array([1.0 if t in US_TICKERS else -1.0 for t in all_tickers])
    v2_raw -= v2_raw.dot(v1) * v1
    v2 = v2_raw / np.linalg.norm(v2_raw)

    # v3: cyclical/defensive spread, orthogonalized to v1 and v2
    v3_raw = np.zeros(N)
    for i, t in enumerate(all_tickers):
        if t in US_CYCLICAL or t in JP_CYCLICAL:
            v3_raw[i] = 1.0
        elif t in US_DEFENSIVE or t in JP_DEFENSIVE:
            v3_raw[i] = -1.0
        # else: 0 (neutral)
    v3_raw -= v3_raw.dot(v1) * v1
    v3_raw -= v3_raw.dot(v2) * v2
    norm = np.linalg.norm(v3_raw)
    v3 = v3_raw / norm if norm > 1e-10 else v3_raw

    V0 = np.column_stack([v1, v2, v3])
    return V0


# ── Step 4: Target Correlation Matrix C0 ──────────────────────────────────
def build_target_matrix(C_full: np.ndarray, V0: np.ndarray) -> np.ndarray:
    """
    C0 from prior subspace:
    D0 = diag(V0^T C_full V0), C0_raw = V0 D0 V0^T,
    then rescale so diag(C0) = 1.
    """
    inner = V0.T @ C_full @ V0
    D0 = np.diag(np.diag(inner))
    C0_raw = V0 @ D0 @ V0.T
    delta = np.sqrt(np.diag(C0_raw))
    delta[delta < 1e-10] = 1.0
    delta_inv = 1.0 / delta
    C0 = C0_raw * np.outer(delta_inv, delta_inv)
    return C0


# ── Step 5-6: Rolling PCA Signal ──────────────────────────────────────────
def compute_pca_signals(r_cc: pd.DataFrame, V0: np.ndarray, lam: float) -> pd.DataFrame:
    """
    For each day t, using window [t-L, t-1]:
    1. Standardize returns
    2. Compute sample correlation C_t
    3. Regularize: C_t^reg = (1-λ)C_t + λ C_0
    4. Eigen-decompose, take top K eigenvectors
    5. Split into US/JP blocks, compute f = V_U^T z_U, signal = V_J f
    Returns predicted z-scores for JP tickers.
    """
    all_tickers = US_TICKERS + JP_TICKERS
    dates = r_cc.index
    T = len(dates)
    signals = pd.DataFrame(index=dates, columns=JP_TICKERS, dtype=float)
    data_full = r_cc[all_tickers].values

    print(f"Computing rolling PCA signals (L={LOOKBACK}, λ={lam}, K={K_FACTORS}) ...")
    for t_idx in range(LOOKBACK, T):
        window = data_full[t_idx - LOOKBACK : t_idx]  # (L, N)
        mu = window.mean(axis=0)
        sigma = window.std(axis=0, ddof=1)
        sigma[sigma < 1e-10] = 1.0

        # Today's standardized return
        z_t = (data_full[t_idx] - mu) / sigma

        # Sample correlation matrix from window
        z_window = (window - mu) / sigma
        C_t = np.corrcoef(z_window, rowvar=False)

        # Handle NaN in correlation matrix
        if np.any(np.isnan(C_t)):
            continue

        # C0 from expanding window (past data only, no look-ahead)
        past_data = data_full[:t_idx]
        C_expanding = np.corrcoef(past_data, rowvar=False)
        C0 = build_target_matrix(C_expanding, V0)

        # Regularize
        C_reg = (1 - lam) * C_t + lam * C0

        # Eigen-decomposition (descending order)
        eigvals, eigvecs = linalg.eigh(C_reg)
        idx_sorted = np.argsort(eigvals)[::-1]
        V_K = eigvecs[:, idx_sorted[:K_FACTORS]]  # (N, K)

        # Split US / JP blocks
        V_U = V_K[:N_U, :]       # (N_U, K)
        V_J = V_K[N_U:, :]       # (N_J, K)

        # Factor scores from US returns
        z_U = z_t[:N_U]
        f = V_U.T @ z_U           # (K,)

        # Predicted JP signal
        z_hat_J = V_J @ f         # (N_J,)
        signals.iloc[t_idx] = z_hat_J

    signals = signals.dropna(how="all")
    print(f"  Signal dates: {len(signals)}")
    return signals


# ── Step 7: Long-Short Portfolio ──────────────────────────────────────────
def build_long_short_portfolio(
    signals: pd.DataFrame, r_oc: pd.DataFrame, q: float = Q_QUANTILE
) -> pd.Series:
    """
    Equal-weight long-short portfolio based on signal quantile.
    Top q → long, bottom q → short, evaluated on next-day open-to-close return.
    """
    common_dates = signals.index.intersection(r_oc.index)
    # Signal at t predicts t+1 return → shift
    sig_aligned = signals.loc[common_dates]
    ret_aligned = r_oc.loc[common_dates]

    portfolio_returns = []
    portfolio_dates = []

    dates_list = list(common_dates)
    for i in range(len(dates_list) - 1):
        sig_today = sig_aligned.loc[dates_list[i]]
        ret_tomorrow = ret_aligned.loc[dates_list[i + 1]]

        if sig_today.isna().any() or ret_tomorrow.isna().any():
            continue

        n_q = max(1, int(N_J * q))
        ranked = sig_today.sort_values()
        short_tickers = ranked.index[:n_q]
        long_tickers = ranked.index[-n_q:]

        r_long = ret_tomorrow[long_tickers].mean()
        r_short = ret_tomorrow[short_tickers].mean()
        portfolio_returns.append(r_long - r_short)
        portfolio_dates.append(dates_list[i + 1])

    return pd.Series(portfolio_returns, index=pd.DatetimeIndex(portfolio_dates), name="PCA_SUB")


# ── Baselines ─────────────────────────────────────────────────────────────
def compute_momentum_signals(r_cc: pd.DataFrame) -> pd.DataFrame:
    """MOM baseline: rolling mean of JP close-to-close returns."""
    return r_cc[JP_TICKERS].rolling(LOOKBACK).mean().dropna(how="all")


def build_double_sort(
    mom_signals: pd.DataFrame,
    pca_signals: pd.DataFrame,
    r_oc: pd.DataFrame,
    q: float = Q_QUANTILE,
) -> pd.Series:
    """DOUBLE: 2×2 sort on MOM × PCA_SUB signals."""
    common = mom_signals.index.intersection(pca_signals.index).intersection(r_oc.index)
    mom_sig = mom_signals.loc[common]
    pca_sig = pca_signals.loc[common]
    ret = r_oc.loc[common]

    portfolio_returns = []
    portfolio_dates = []
    dates_list = list(common)

    for i in range(len(dates_list) - 1):
        m = mom_sig.loc[dates_list[i]]
        p = pca_sig.loc[dates_list[i]]
        r_next = ret.loc[dates_list[i + 1]]

        if m.isna().any() or p.isna().any() or r_next.isna().any():
            continue

        # Median split on each signal → 2×2
        m_med = m.median()
        p_med = p.median()

        long_mask = (m > m_med) & (p > p_med)   # high-high
        short_mask = (m <= m_med) & (p <= p_med) # low-low

        if long_mask.sum() == 0 or short_mask.sum() == 0:
            continue

        r_long = r_next[long_mask].mean()
        r_short = r_next[short_mask].mean()
        portfolio_returns.append(r_long - r_short)
        portfolio_dates.append(dates_list[i + 1])

    return pd.Series(portfolio_returns, index=pd.DatetimeIndex(portfolio_dates), name="DOUBLE")


# ── Evaluation Metrics ────────────────────────────────────────────────────
def compute_metrics(returns: pd.Series) -> dict:
    """AR (annualized), RISK, R/R, MDD."""
    r = returns.values
    T = len(r)
    if T == 0:
        return {"AR": 0, "RISK": 0, "R/R": 0, "MDD": 0}

    # Approximate monthly by grouping ~21 trading days
    monthly = returns.resample("ME").sum()
    n_months = len(monthly)
    if n_months < 2:
        return {"AR": 0, "RISK": 0, "R/R": 0, "MDD": 0}

    ar = monthly.mean() * 12
    risk = monthly.std(ddof=1) * np.sqrt(12)
    rr = ar / risk if risk > 1e-10 else 0.0

    # Max drawdown from daily cumulative
    cum = (1 + returns).cumprod()
    running_max = cum.cummax()
    dd = (cum - running_max) / running_max
    mdd = dd.min()

    return {"AR": ar, "RISK": risk, "R/R": rr, "MDD": mdd}


def print_basic_stats(r_cc: pd.DataFrame) -> None:
    """Table 1: Basic statistics of sector ETF returns."""
    all_tickers = US_TICKERS + JP_TICKERS
    stats = []
    for t in all_tickers:
        s = r_cc[t]
        monthly = s.resample("ME").sum()
        stats.append({
            "Ticker": t,
            "Ret%": monthly.mean() * 12 * 100,
            "Vol%": monthly.std(ddof=1) * np.sqrt(12) * 100,
            "Ret/Vol": (monthly.mean() * 12) / (monthly.std(ddof=1) * np.sqrt(12)) if monthly.std() > 0 else 0,
            "Skew": s.skew(),
            "Kurt": s.kurtosis(),
        })
    df = pd.DataFrame(stats)
    print("\n" + "=" * 70)
    print("Table 1: Basic Statistics of Sector ETF Returns")
    print("=" * 70)
    print(df.to_string(index=False, float_format="{:.4f}".format))
    df.to_csv(OUTPUT_DIR / "table1_basic_stats.csv", index=False)


# ── Fama-French Factor Regression ─────────────────────────────────────────
def download_ff_factors() -> pd.DataFrame | None:
    """Download Fama-French 3 factors + Momentum from Kenneth French Data Library."""
    try:
        # Use pandas_datareader if available, otherwise download CSV directly
        import io
        import zipfile
        import urllib.request

        # FF 3 factors (daily)
        url_ff3 = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip"
        url_mom = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_daily_CSV.zip"

        def _read_ff_zip(url: str) -> pd.DataFrame:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=30)
            zf = zipfile.ZipFile(io.BytesIO(resp.read()))
            csv_name = [n for n in zf.namelist() if n.endswith(".CSV") or n.endswith(".csv")][0]
            raw_text = zf.read(csv_name).decode("utf-8", errors="replace")

            # Find header row
            lines = raw_text.split("\n")
            start_idx = None
            for i, line in enumerate(lines):
                if "Mkt-RF" in line or "Mom" in line or "WML" in line:
                    start_idx = i
                    break
            if start_idx is None:
                return pd.DataFrame()

            # Find end of data
            data_lines = [lines[start_idx]]
            for line in lines[start_idx + 1:]:
                stripped = line.strip()
                if not stripped or not stripped[0].isdigit():
                    break
                data_lines.append(stripped)

            df = pd.read_csv(io.StringIO("\n".join(data_lines)))
            first_col = df.columns[0]
            df = df.rename(columns={first_col: "Date"})
            df["Date"] = pd.to_datetime(df["Date"].astype(str).str.strip(), format="%Y%m%d", errors="coerce")
            df = df.dropna(subset=["Date"])
            df = df.set_index("Date")
            # Convert from percentage to decimal
            for col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce") / 100.0
            return df

        ff3 = _read_ff_zip(url_ff3)
        mom = _read_ff_zip(url_mom)

        if ff3.empty:
            print("  Warning: Could not parse FF3 data")
            return None

        # Rename momentum column
        if not mom.empty:
            mom_col = [c for c in mom.columns if c.strip()][0]
            mom = mom.rename(columns={mom_col: "WML"})
            ff = ff3.join(mom[["WML"]], how="left")
        else:
            ff = ff3
            ff["WML"] = np.nan

        return ff

    except Exception as e:
        print(f"  Warning: Failed to download FF factors: {e}")
        return None


def run_factor_regression(returns: pd.Series, ff: pd.DataFrame, name: str) -> dict | None:
    """Run Fama-French 3 + Carhart 4 factor regression with Newey-West t-stats."""
    try:
        from statsmodels.regression.linear_model import OLS
        from statsmodels.tools import add_constant
    except ImportError:
        print("  statsmodels not installed, skipping factor regression")
        return None

    common = returns.index.intersection(ff.index)
    if len(common) < 60:
        print(f"  Not enough overlapping dates for {name}: {len(common)}")
        return None

    y = returns.loc[common].values
    factors_3 = ["Mkt-RF", "SMB", "HML"]
    factors_4 = factors_3 + ["WML"]

    results = {}

    for label, factor_cols in [("FF3", factors_3), ("Carhart4", factors_4)]:
        available = [c for c in factor_cols if c in ff.columns and not ff[c].isna().all()]
        if not available:
            continue
        X = add_constant(ff.loc[common, available].values)
        if np.any(np.isnan(X)) or np.any(np.isnan(y)):
            mask = ~(np.isnan(X).any(axis=1) | np.isnan(y))
            X, y_clean = X[mask], y[mask]
        else:
            y_clean = y

        model = OLS(y_clean, X).fit(cov_type="HAC", cov_kwds={"maxlags": int(len(y_clean) ** (1/3))})
        results[label] = {
            "alpha": model.params[0],
            "alpha_t": model.tvalues[0],
            "alpha_p": model.pvalues[0],
            "R2": model.rsquared,
            "coeffs": dict(zip(["const"] + available, model.params)),
            "tvals": dict(zip(["const"] + available, model.tvalues)),
        }

    return results


# ── Cumulative Return Chart ───────────────────────────────────────────────
def plot_cumulative_returns(strategy_returns: dict[str, pd.Series]) -> None:
    """Plot cumulative returns for all strategies."""
    fig, ax = plt.subplots(figsize=(12, 6))

    colors = {"MOM": "#888888", "PCA_PLAIN": "#4488cc", "PCA_SUB": "#cc4444", "DOUBLE": "#44aa44"}
    for name, ret in strategy_returns.items():
        cum = (1 + ret).cumprod()
        ax.plot(cum.index, cum.values, label=name, color=colors.get(name, "#000000"), linewidth=1.2)

    ax.set_title("Cumulative Returns: Lead-Lag PCA Strategies (JP Sector ETFs)", fontsize=13)
    ax.set_ylabel("Cumulative Return (Growth of $1)")
    ax.set_xlabel("")
    ax.legend(loc="upper left")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "cumulative_returns.png", dpi=150)
    plt.close(fig)
    print(f"\n  Chart saved: {OUTPUT_DIR / 'cumulative_returns.png'}")


# ── Main ──────────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 70)
    print("Subspace-Regularized PCA Lead-Lag Strategy")
    print("US Sectors → JP Sectors (Nakagawa et al., SIG-FIN-036-13)")
    print("=" * 70)

    # 1. Data
    close, open_, _ = download_data()
    r_cc, r_oc = compute_returns(close, open_)

    # Table 1
    print_basic_stats(r_cc)

    # 2. Prior exposures
    V0 = build_prior_exposures()

    # 3. PCA_SUB (λ=0.9)
    print("\n── PCA_SUB (λ=0.9) ──")
    pca_sub_signals = compute_pca_signals(r_cc, V0, lam=LAMBDA_REG)
    pca_sub_ret = build_long_short_portfolio(pca_sub_signals, r_oc)

    # 4. PCA_PLAIN (λ=0)
    print("\n── PCA_PLAIN (λ=0) ──")
    pca_plain_signals = compute_pca_signals(r_cc, V0, lam=0.0)
    pca_plain_ret = build_long_short_portfolio(pca_plain_signals, r_oc)
    pca_plain_ret.name = "PCA_PLAIN"

    # 5. MOM baseline
    print("\n── MOM ──")
    mom_signals = compute_momentum_signals(r_cc)
    mom_ret = build_long_short_portfolio(mom_signals, r_oc)
    mom_ret.name = "MOM"

    # 6. DOUBLE sort
    print("\n── DOUBLE (MOM × PCA_SUB) ──")
    double_ret = build_double_sort(mom_signals, pca_sub_signals, r_oc)

    # Table 2: Strategy summary
    strategies = {"MOM": mom_ret, "PCA_PLAIN": pca_plain_ret, "PCA_SUB": pca_sub_ret, "DOUBLE": double_ret}
    print("\n" + "=" * 70)
    print("Table 2: Strategy Summary Statistics")
    print("=" * 70)
    rows = []
    for name, ret in strategies.items():
        m = compute_metrics(ret)
        rows.append({
            "Strategy": name,
            "AR%": m["AR"] * 100,
            "RISK%": m["RISK"] * 100,
            "R/R": m["R/R"],
            "MDD%": m["MDD"] * 100,
            "N_days": len(ret),
        })
    df_summary = pd.DataFrame(rows)
    print(df_summary.to_string(index=False, float_format="{:.4f}".format))
    df_summary.to_csv(OUTPUT_DIR / "table2_strategy_summary.csv", index=False)

    # Fama-French factor regression
    print("\n── Downloading Fama-French factors ──")
    ff = download_ff_factors()

    if ff is not None:
        print("\n" + "=" * 70)
        print("Table 3-4: Factor Regression Results")
        print("=" * 70)
        regression_rows = []
        for name, ret in strategies.items():
            result = run_factor_regression(ret, ff, name)
            if result is None:
                continue
            for model_name, res in result.items():
                row = {"Strategy": name, "Model": model_name}
                row["Alpha(daily)"] = res["alpha"]
                row["Alpha_t"] = res["alpha_t"]
                row["Alpha_p"] = res["alpha_p"]
                row["R2"] = res["R2"]
                for k, v in res["coeffs"].items():
                    if k != "const":
                        row[k] = v
                for k, v in res["tvals"].items():
                    if k != "const":
                        row[f"{k}_t"] = v
                regression_rows.append(row)
            sig_label = "***" if result.get("Carhart4", result.get("FF3", {})).get("alpha_p", 1) < 0.01 else \
                        "**" if result.get("Carhart4", result.get("FF3", {})).get("alpha_p", 1) < 0.05 else \
                        "*" if result.get("Carhart4", result.get("FF3", {})).get("alpha_p", 1) < 0.10 else ""
            print(f"  {name}: α_daily = {result.get('Carhart4', result.get('FF3', {})).get('alpha', 0):.6f} "
                  f"(t={result.get('Carhart4', result.get('FF3', {})).get('alpha_t', 0):.2f}){sig_label}")

        if regression_rows:
            df_reg = pd.DataFrame(regression_rows)
            print()
            print(df_reg.to_string(index=False, float_format="{:.4f}".format))
            df_reg.to_csv(OUTPUT_DIR / "table3_4_factor_regression.csv", index=False)

    # Cumulative return chart
    plot_cumulative_returns(strategies)

    # Save daily returns
    all_returns = pd.DataFrame(strategies)
    all_returns.to_csv(OUTPUT_DIR / "daily_returns.csv")
    print(f"\n  Daily returns saved: {OUTPUT_DIR / 'daily_returns.csv'}")

    print("\n" + "=" * 70)
    print("Done. All outputs saved to:", OUTPUT_DIR)
    print("=" * 70)


if __name__ == "__main__":
    main()
