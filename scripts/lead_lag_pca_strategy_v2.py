#!/usr/bin/env python3
"""
部分空間正則化付きPCA 日米業種リードラグ投資戦略 v2 (実運用版)
Based on: 中川ら (SIG-FIN-036-13)

v2 improvements:
- Individual stock baskets instead of TOPIX-17 ETFs (10x liquidity)
- Transaction cost model (spread + commission + quadratic impact)
- Adaptive lambda via rolling cross-validation
- Ensemble signal (PCA_SUB + MOM + REV)
- Sector IC filtering (drop low-IC sectors)
- VIX-based position sizing
- Weekly rebalancing option
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
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "lead_lag_pca_v2"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

START_DATE = "2010-01-01"
END_DATE = "2025-12-31"

# US Select Sector SPDR ETFs (N_U = 9)
US_TICKERS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
N_U = len(US_TICKERS)

# Japan: Individual stock baskets per TOPIX-17 sector (top 3 by market cap)
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
N_J = len(JP_SECTORS)  # 17
N = N_U + N_J           # 26

LOOKBACK = 60
K_FACTORS = 3
Q_QUANTILE = 0.3

# Adaptive lambda search grid
LAMBDA_GRID = [0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 0.95]
LAMBDA_CV_WINDOW = 20  # days for OOS evaluation in CV

# Transaction cost parameters (bps) - calibrated for JP large-cap stocks
SPREAD_BPS = 3.0       # half-spread for large-cap stocks (full spread ~6bps)
COMMISSION_BPS = 3.0   # one-way commission (institutional)
IMPACT_BPS = 5.0       # sqrt-impact coefficient (small trades)

# IC filter threshold
IC_THRESHOLD = 0.02

# Cyclical / Defensive classification
US_CYCLICAL = {"XLB", "XLE", "XLF", "XLI", "XLK"}
US_DEFENSIVE = {"XLP", "XLU", "XLV", "XLY"}

JP_CYCLICAL = {"Energy", "ElecPrecision", "Trading", "Banks"}
JP_DEFENSIVE = {"Foods", "Pharma", "Utilities", "Retail"}


# ── Data Download ──────────────────────────────────────────────────────────
def download_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series]:
    """Download US ETFs + JP individual stocks + VIX, return sector-level data."""
    jp_all_stocks = []
    for stocks in JP_SECTOR_BASKETS.values():
        jp_all_stocks.extend(stocks)

    all_tickers = US_TICKERS + jp_all_stocks + ["^VIX"]
    print(f"Downloading {len(all_tickers)} tickers ({N_U} US ETFs + {len(jp_all_stocks)} JP stocks + VIX) ...")

    raw = yf.download(all_tickers, start=START_DATE, end=END_DATE, auto_adjust=True, progress=True)

    close_raw = raw["Close"].copy()
    open_raw = raw["Open"].copy()

    # VIX
    vix = close_raw["^VIX"].copy()

    # Build sector-level returns from individual stock baskets (equal-weight average)
    # First compute stock-level returns
    stock_cc = close_raw[jp_all_stocks].pct_change()
    stock_oc = (close_raw[jp_all_stocks] / open_raw[jp_all_stocks] - 1)

    # Aggregate to sector level
    sector_cc = pd.DataFrame(index=stock_cc.index)
    sector_oc = pd.DataFrame(index=stock_oc.index)
    for sector, stocks in JP_SECTOR_BASKETS.items():
        available = [s for s in stocks if s in stock_cc.columns]
        if available:
            sector_cc[sector] = stock_cc[available].mean(axis=1)
            sector_oc[sector] = stock_oc[available].mean(axis=1)

    # US ETF returns
    us_cc = close_raw[US_TICKERS].pct_change()

    # Combine US + JP sector returns
    r_cc = pd.concat([us_cc, sector_cc], axis=1)
    r_oc_jp = sector_oc

    # Common dates: all columns non-NaN
    mask = r_cc.notna().all(axis=1) & r_oc_jp.notna().all(axis=1)
    r_cc = r_cc.loc[mask].iloc[1:]  # drop first row (NaN from pct_change)
    r_oc_jp = r_oc_jp.loc[r_cc.index]
    vix = vix.reindex(r_cc.index).ffill()

    all_cols = US_TICKERS + JP_SECTORS
    r_cc = r_cc[all_cols]

    print(f"Common trading days: {len(r_cc)} ({r_cc.index[0].date()} – {r_cc.index[-1].date()})")
    return r_cc, r_oc_jp, vix, close_raw


# ── Prior Exposures ────────────────────────────────────────────────────────
def build_prior_exposures() -> np.ndarray:
    """Build N×3 prior exposure matrix V0."""
    all_names = US_TICKERS + JP_SECTORS

    v1 = np.ones(N) / np.sqrt(N)

    v2_raw = np.array([1.0 if i < N_U else -1.0 for i in range(N)])
    v2_raw -= v2_raw.dot(v1) * v1
    v2 = v2_raw / np.linalg.norm(v2_raw)

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


# ── Target Correlation Matrix ──────────────────────────────────────────────
def build_target_matrix(C_full: np.ndarray, V0: np.ndarray) -> np.ndarray:
    """C0 from prior subspace, rescaled so diag=1."""
    inner = V0.T @ C_full @ V0
    D0 = np.diag(np.diag(inner))
    C0_raw = V0 @ D0 @ V0.T
    delta = np.sqrt(np.abs(np.diag(C0_raw)))
    delta[delta < 1e-10] = 1.0
    delta_inv = 1.0 / delta
    C0 = C0_raw * np.outer(delta_inv, delta_inv)
    return C0


# ── Adaptive Lambda Selection ─────────────────────────────────────────────
def select_lambda_cv(
    data: np.ndarray, V0: np.ndarray, t_idx: int, grid: list[float]
) -> float:
    """
    Select lambda by rolling CV: for each candidate lambda,
    evaluate 1-step-ahead prediction quality over the last CV_WINDOW days.
    """
    if t_idx < LOOKBACK + LAMBDA_CV_WINDOW:
        return 0.9  # default until enough data

    best_lam = 0.9
    best_score = -np.inf

    for lam in grid:
        score = 0.0
        count = 0
        for cv_t in range(t_idx - LAMBDA_CV_WINDOW, t_idx):
            window = data[cv_t - LOOKBACK : cv_t]
            mu = window.mean(axis=0)
            sigma = window.std(axis=0, ddof=1)
            sigma[sigma < 1e-10] = 1.0

            z_window = (window - mu) / sigma
            C_t = np.corrcoef(z_window, rowvar=False)
            if np.any(np.isnan(C_t)):
                continue

            past = data[:cv_t]
            C_exp = np.corrcoef(past, rowvar=False)
            if np.any(np.isnan(C_exp)):
                continue
            C0 = build_target_matrix(C_exp, V0)

            C_reg = (1 - lam) * C_t + lam * C0

            eigvals, eigvecs = linalg.eigh(C_reg)
            idx_sorted = np.argsort(eigvals)[::-1]
            V_K = eigvecs[:, idx_sorted[:K_FACTORS]]

            V_U = V_K[:N_U, :]
            V_J = V_K[N_U:, :]

            z_t = (data[cv_t] - mu) / sigma
            f = V_U.T @ z_t[:N_U]
            z_hat_J = V_J @ f

            # Evaluate: correlation with actual next-day JP return
            if cv_t + 1 < len(data):
                actual_next = data[cv_t + 1, N_U:]
                if not np.any(np.isnan(actual_next)) and np.std(actual_next) > 1e-10:
                    corr = np.corrcoef(z_hat_J, actual_next)[0, 1]
                    if not np.isnan(corr):
                        score += corr
                        count += 1

        if count > 0:
            avg_score = score / count
            if avg_score > best_score:
                best_score = avg_score
                best_lam = lam

    return best_lam


# ── PCA Signal Generation ─────────────────────────────────────────────────
def compute_pca_signals(
    r_cc: pd.DataFrame, V0: np.ndarray, lam: float | None = None, adaptive: bool = False
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Rolling subspace-regularized PCA.
    If adaptive=True, select lambda via CV at each step.
    Returns (signals DataFrame, lambda_series).
    """
    all_cols = US_TICKERS + JP_SECTORS
    dates = r_cc.index
    T = len(dates)
    signals = pd.DataFrame(index=dates, columns=JP_SECTORS, dtype=float)
    lambda_history = pd.Series(index=dates, dtype=float)
    data_full = r_cc[all_cols].values

    label = "adaptive" if adaptive else f"λ={lam}"
    print(f"  Computing PCA signals ({label}, L={LOOKBACK}, K={K_FACTORS}) ...")

    ADAPTIVE_REFIT_INTERVAL = 20  # refit lambda every 20 trading days
    cached_lam = 0.9

    for t_idx in range(LOOKBACK, T):
        window = data_full[t_idx - LOOKBACK : t_idx]
        mu = window.mean(axis=0)
        sigma = window.std(axis=0, ddof=1)
        sigma[sigma < 1e-10] = 1.0

        z_t = (data_full[t_idx] - mu) / sigma
        z_window = (window - mu) / sigma
        C_t = np.corrcoef(z_window, rowvar=False)

        if np.any(np.isnan(C_t)):
            continue

        # Select lambda (refit every ADAPTIVE_REFIT_INTERVAL days)
        if adaptive:
            if (t_idx - LOOKBACK) % ADAPTIVE_REFIT_INTERVAL == 0:
                cached_lam = select_lambda_cv(data_full, V0, t_idx, LAMBDA_GRID)
            current_lam = cached_lam
        else:
            current_lam = lam
        lambda_history.iloc[t_idx] = current_lam

        # C0 from expanding window
        past_data = data_full[:t_idx]
        C_exp = np.corrcoef(past_data, rowvar=False)
        if np.any(np.isnan(C_exp)):
            continue
        C0 = build_target_matrix(C_exp, V0)

        C_reg = (1 - current_lam) * C_t + current_lam * C0

        eigvals, eigvecs = linalg.eigh(C_reg)
        idx_sorted = np.argsort(eigvals)[::-1]
        V_K = eigvecs[:, idx_sorted[:K_FACTORS]]

        V_U = V_K[:N_U, :]
        V_J = V_K[N_U:, :]

        f = V_U.T @ z_t[:N_U]
        z_hat_J = V_J @ f
        signals.iloc[t_idx] = z_hat_J

    signals = signals.dropna(how="all")
    print(f"    Signal dates: {len(signals)}")
    return signals, lambda_history


# ── Momentum & Reversal Signals ───────────────────────────────────────────
def compute_momentum_signals(r_cc: pd.DataFrame) -> pd.DataFrame:
    """Rolling mean of JP sector close-to-close returns."""
    return r_cc[JP_SECTORS].rolling(LOOKBACK).mean().dropna(how="all")


def compute_reversal_signals(r_cc: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    """Short-term reversal: negative of 5-day return."""
    return -r_cc[JP_SECTORS].rolling(window).mean().dropna(how="all")


def compute_ensemble_signal(
    pca_sig: pd.DataFrame, mom_sig: pd.DataFrame, rev_sig: pd.DataFrame
) -> pd.DataFrame:
    """Simple average of rank-normalized signals."""
    common = pca_sig.index.intersection(mom_sig.index).intersection(rev_sig.index)

    ensemble = pd.DataFrame(index=common, columns=JP_SECTORS, dtype=float)
    for dt in common:
        p = pca_sig.loc[dt].rank()
        m = mom_sig.loc[dt].rank()
        r = rev_sig.loc[dt].rank()
        ensemble.loc[dt] = (p + m + r) / 3.0

    return ensemble


# ── Sector IC Analysis & Filtering ────────────────────────────────────────
def compute_sector_ic(
    signals: pd.DataFrame, r_oc: pd.DataFrame, rolling_window: int = 252
) -> pd.DataFrame:
    """Compute rolling rank IC per sector."""
    common = signals.index.intersection(r_oc.index)
    dates_list = list(common)

    ic_records = []
    for sector in JP_SECTORS:
        ics = []
        for i in range(len(dates_list) - 1):
            sig_val = signals.loc[dates_list[i], sector]
            ret_val = r_oc.loc[dates_list[i + 1], sector]
            if pd.notna(sig_val) and pd.notna(ret_val):
                ics.append((sig_val, ret_val))

        if len(ics) < rolling_window:
            avg_ic = 0.0
        else:
            # Use last rolling_window pairs
            recent = ics[-rolling_window:]
            sigs, rets = zip(*recent)
            from scipy.stats import spearmanr
            corr, _ = spearmanr(sigs, rets)
            avg_ic = corr if not np.isnan(corr) else 0.0

        ic_records.append({"Sector": sector, "IC": avg_ic, "N_obs": len(ics)})

    return pd.DataFrame(ic_records)


def filter_sectors_by_ic(
    signals: pd.DataFrame, r_oc: pd.DataFrame, threshold: float = IC_THRESHOLD
) -> list[str]:
    """Return sectors with IC above threshold."""
    ic_df = compute_sector_ic(signals, r_oc)
    selected = ic_df[ic_df["IC"] >= threshold]["Sector"].tolist()
    print(f"  IC filter: {len(selected)}/{N_J} sectors pass (threshold={threshold})")
    for _, row in ic_df.iterrows():
        marker = "+" if row["IC"] >= threshold else " "
        print(f"    [{marker}] {row['Sector']:15s} IC={row['IC']:+.4f}")
    return selected


# ── Transaction Cost Model ─────────────────────────────────────────────────
def compute_transaction_cost(turnover_frac: float) -> float:
    """
    Total portfolio cost = turnover_frac * cost_per_unit_traded * 2 (round-trip).
    Only the turned-over portion incurs spread, commission, and impact.
    """
    if turnover_frac < 1e-10:
        return 0.0
    cost_per_unit_bps = SPREAD_BPS / 2 + COMMISSION_BPS + IMPACT_BPS * np.sqrt(turnover_frac)
    return turnover_frac * cost_per_unit_bps / 10000.0 * 2  # round-trip


# ── VIX-Based Position Sizing ─────────────────────────────────────────────
def vix_position_scale(vix_level: float) -> float:
    """Scale position size based on VIX level."""
    if vix_level < 20:
        return 1.0
    elif vix_level < 30:
        return 0.5
    else:
        return 0.25


# ── Portfolio Construction ─────────────────────────────────────────────────
def build_long_short_portfolio(
    signals: pd.DataFrame,
    r_oc: pd.DataFrame,
    vix: pd.Series | None = None,
    sectors_filter: list[str] | None = None,
    apply_costs: bool = False,
    weekly_rebalance: bool = False,
    q: float = Q_QUANTILE,
) -> pd.Series:
    """
    Equal-weight quantile long-short (v1-style).
    Optional: sector filter, VIX sizing, costs, weekly rebalance.
    """
    use_sectors = sectors_filter if sectors_filter else JP_SECTORS
    n_sectors = len(use_sectors)
    if n_sectors < 4:
        use_sectors = JP_SECTORS
        n_sectors = N_J

    common = signals.index.intersection(r_oc.index)
    sig_aligned = signals.loc[common, use_sectors]
    ret_aligned = r_oc.loc[common, use_sectors]

    portfolio_returns = []
    portfolio_dates = []
    prev_long = set()
    prev_short = set()
    last_rebalance_week = -1

    dates_list = list(common)
    for i in range(len(dates_list) - 1):
        sig_today = sig_aligned.loc[dates_list[i]]
        ret_tomorrow = ret_aligned.loc[dates_list[i + 1]]

        if sig_today.isna().any() or ret_tomorrow.isna().any():
            continue

        current_week = dates_list[i].isocalendar()[1]
        if weekly_rebalance and current_week == last_rebalance_week:
            if prev_long and prev_short:
                r_long = ret_tomorrow[list(prev_long)].mean()
                r_short = ret_tomorrow[list(prev_short)].mean()
                scale = 1.0
                if vix is not None and dates_list[i] in vix.index:
                    scale = vix_position_scale(vix.loc[dates_list[i]])
                portfolio_returns.append((r_long - r_short) * scale)
                portfolio_dates.append(dates_list[i + 1])
                continue
        last_rebalance_week = current_week

        n_q = max(1, int(n_sectors * q))
        ranked = sig_today.sort_values()
        short_sectors = set(ranked.index[:n_q])
        long_sectors = set(ranked.index[-n_q:])

        r_long = ret_tomorrow[list(long_sectors)].mean()
        r_short = ret_tomorrow[list(short_sectors)].mean()
        raw_return = r_long - r_short

        scale = 1.0
        if vix is not None and dates_list[i] in vix.index:
            scale = vix_position_scale(vix.loc[dates_list[i]])

        cost = 0.0
        if apply_costs:
            turnover_long = len(long_sectors.symmetric_difference(prev_long)) / max(n_q, 1)
            turnover_short = len(short_sectors.symmetric_difference(prev_short)) / max(n_q, 1)
            turnover = (turnover_long + turnover_short) / 2
            cost = compute_transaction_cost(turnover)

        prev_long = long_sectors
        prev_short = short_sectors
        portfolio_returns.append(raw_return * scale - cost)
        portfolio_dates.append(dates_list[i + 1])

    return pd.Series(portfolio_returns, index=pd.DatetimeIndex(portfolio_dates))


def build_signal_weighted_portfolio(
    signals: pd.DataFrame,
    r_oc: pd.DataFrame,
    vix: pd.Series | None = None,
    sectors_filter: list[str] | None = None,
    apply_costs: bool = False,
    turnover_cap: float = 0.30,
) -> pd.Series:
    """
    Signal-weighted long-short portfolio with turnover cap.

    Weights are proportional to demeaned signal (naturally zero-cost).
    Turnover cap limits daily weight changes to reduce transaction costs.
    This creates sticky positions that gradually adjust.
    """
    use_sectors = sectors_filter if sectors_filter else JP_SECTORS
    n_sectors = len(use_sectors)
    if n_sectors < 4:
        use_sectors = JP_SECTORS
        n_sectors = N_J

    common = signals.index.intersection(r_oc.index)
    sig_aligned = signals.loc[common, use_sectors]
    ret_aligned = r_oc.loc[common, use_sectors]

    portfolio_returns = []
    portfolio_dates = []
    prev_weights = np.zeros(n_sectors)

    dates_list = list(common)
    sector_list = list(use_sectors)

    for i in range(len(dates_list) - 1):
        sig_today = sig_aligned.loc[dates_list[i]].values.astype(float)
        ret_tomorrow = ret_aligned.loc[dates_list[i + 1]].values.astype(float)

        if np.any(np.isnan(sig_today)) or np.any(np.isnan(ret_tomorrow)):
            continue

        # Target weights: demeaned signal, normalized to sum(|w|) = 2 (1 long + 1 short)
        sig_demeaned = sig_today - sig_today.mean()
        abs_sum = np.abs(sig_demeaned).sum()
        if abs_sum < 1e-10:
            target_weights = np.zeros(n_sectors)
        else:
            target_weights = sig_demeaned / abs_sum * 2

        # Apply turnover cap: limit weight changes
        weight_diff = target_weights - prev_weights
        diff_norm = np.abs(weight_diff).sum()
        if diff_norm > turnover_cap and diff_norm > 1e-10:
            weight_diff = weight_diff * (turnover_cap / diff_norm)
        new_weights = prev_weights + weight_diff

        # Re-normalize to zero-cost (sum of weights = 0)
        new_weights -= new_weights.mean()

        # Portfolio return
        raw_return = np.dot(new_weights, ret_tomorrow)

        # VIX sizing
        scale = 1.0
        if vix is not None and dates_list[i] in vix.index:
            scale = vix_position_scale(vix.loc[dates_list[i]])

        # Transaction costs on turned-over portion
        cost = 0.0
        if apply_costs:
            turnover = np.abs(new_weights - prev_weights).sum() / 2  # one-side turnover
            cost = compute_transaction_cost(turnover)

        prev_weights = new_weights
        portfolio_returns.append(raw_return * scale - cost)
        portfolio_dates.append(dates_list[i + 1])

    return pd.Series(portfolio_returns, index=pd.DatetimeIndex(portfolio_dates))


def build_multi_tranche_portfolio(
    signals: pd.DataFrame,
    r_oc: pd.DataFrame,
    vix: pd.Series | None = None,
    sectors_filter: list[str] | None = None,
    apply_costs: bool = False,
    n_tranches: int = 3,
    q: float = Q_QUANTILE,
    smooth_span: int = 0,
) -> pd.Series:
    """
    Multi-tranche overlapping portfolio to reduce turnover.

    Runs N_TRANCHES sub-portfolios, each rebalanced every N_TRANCHES days
    on a staggered schedule. Final return = average of all tranches.
    Optional EMA smoothing of signals.
    """
    use_sectors = sectors_filter if sectors_filter else JP_SECTORS
    n_sectors = len(use_sectors)
    if n_sectors < 4:
        use_sectors = JP_SECTORS
        n_sectors = N_J

    common = signals.index.intersection(r_oc.index)
    sig_aligned = signals.loc[common, use_sectors].copy()
    ret_aligned = r_oc.loc[common, use_sectors]

    # Optional EMA smoothing
    if smooth_span > 1:
        sig_aligned = sig_aligned.ewm(span=smooth_span, adjust=False).mean()

    dates_list = list(common)
    n_q = max(1, int(n_sectors * q))

    # Each tranche has its own positions
    tranche_longs: list[set] = [set() for _ in range(n_tranches)]
    tranche_shorts: list[set] = [set() for _ in range(n_tranches)]
    tranche_prev_longs: list[set] = [set() for _ in range(n_tranches)]
    tranche_prev_shorts: list[set] = [set() for _ in range(n_tranches)]

    portfolio_returns = []
    portfolio_dates = []

    for i in range(len(dates_list) - 1):
        sig_today = sig_aligned.loc[dates_list[i]]
        ret_tomorrow = ret_aligned.loc[dates_list[i + 1]]

        if sig_today.isna().any() or ret_tomorrow.isna().any():
            continue

        # Determine which tranche to rebalance today
        rebalance_tranche = i % n_tranches
        ranked = sig_today.sort_values()
        tranche_shorts[rebalance_tranche] = set(ranked.index[:n_q])
        tranche_longs[rebalance_tranche] = set(ranked.index[-n_q:])

        # Compute return for each tranche and average
        tranche_returns = []
        total_cost = 0.0
        for t in range(n_tranches):
            if not tranche_longs[t] or not tranche_shorts[t]:
                continue
            r_l = ret_tomorrow[list(tranche_longs[t])].mean()
            r_s = ret_tomorrow[list(tranche_shorts[t])].mean()
            tranche_returns.append(r_l - r_s)

            # Cost only for the rebalanced tranche
            if apply_costs and t == rebalance_tranche:
                turnover_l = len(tranche_longs[t].symmetric_difference(tranche_prev_longs[t])) / max(n_q, 1)
                turnover_s = len(tranche_shorts[t].symmetric_difference(tranche_prev_shorts[t])) / max(n_q, 1)
                turnover = (turnover_l + turnover_s) / 2
                total_cost += compute_transaction_cost(turnover) / n_tranches

        tranche_prev_longs[rebalance_tranche] = tranche_longs[rebalance_tranche].copy()
        tranche_prev_shorts[rebalance_tranche] = tranche_shorts[rebalance_tranche].copy()

        if tranche_returns:
            raw = np.mean(tranche_returns)
            scale = 1.0
            if vix is not None and dates_list[i] in vix.index:
                scale = vix_position_scale(vix.loc[dates_list[i]])
            portfolio_returns.append(raw * scale - total_cost)
            portfolio_dates.append(dates_list[i + 1])

    return pd.Series(portfolio_returns, index=pd.DatetimeIndex(portfolio_dates))


# ── Evaluation ─────────────────────────────────────────────────────────────
def compute_metrics(returns: pd.Series) -> dict:
    """AR, RISK, R/R, MDD (annualized from monthly)."""
    if len(returns) == 0:
        return {"AR": 0, "RISK": 0, "R/R": 0, "MDD": 0}

    monthly = returns.resample("ME").sum()
    if len(monthly) < 2:
        return {"AR": 0, "RISK": 0, "R/R": 0, "MDD": 0}

    ar = monthly.mean() * 12
    risk = monthly.std(ddof=1) * np.sqrt(12)
    rr = ar / risk if risk > 1e-10 else 0.0

    cum = (1 + returns).cumprod()
    mdd = ((cum - cum.cummax()) / cum.cummax()).min()

    return {"AR": ar, "RISK": risk, "R/R": rr, "MDD": mdd}


# ── Fama-French Regression ─────────────────────────────────────────────────
def download_ff_factors() -> pd.DataFrame | None:
    """Download FF3 + Momentum from Kenneth French Data Library."""
    try:
        import io, zipfile, urllib.request

        def _read_ff_zip(url: str) -> pd.DataFrame:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=30)
            zf = zipfile.ZipFile(io.BytesIO(resp.read()))
            csv_name = [n for n in zf.namelist() if n.lower().endswith(".csv")][0]
            raw_text = zf.read(csv_name).decode("utf-8", errors="replace")
            lines = raw_text.split("\n")
            start_idx = None
            for i, line in enumerate(lines):
                if "Mkt-RF" in line or "Mom" in line or "WML" in line:
                    start_idx = i
                    break
            if start_idx is None:
                return pd.DataFrame()
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
            df = df.dropna(subset=["Date"]).set_index("Date")
            for col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce") / 100.0
            return df

        ff3 = _read_ff_zip("https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip")
        mom = _read_ff_zip("https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_daily_CSV.zip")

        if ff3.empty:
            return None
        if not mom.empty:
            mom_col = [c for c in mom.columns if c.strip()][0]
            mom = mom.rename(columns={mom_col: "WML"})
            ff = ff3.join(mom[["WML"]], how="left")
        else:
            ff = ff3
            ff["WML"] = np.nan
        return ff
    except Exception as e:
        print(f"  Warning: FF factors download failed: {e}")
        return None


def run_factor_regression(returns: pd.Series, ff: pd.DataFrame, name: str) -> dict | None:
    """FF3 + Carhart4 with Newey-West."""
    try:
        from statsmodels.regression.linear_model import OLS
        from statsmodels.tools import add_constant
    except ImportError:
        return None

    common = returns.index.intersection(ff.index)
    if len(common) < 60:
        return None

    y = returns.loc[common].values
    results = {}

    for label, cols in [("FF3", ["Mkt-RF", "SMB", "HML"]), ("Carhart4", ["Mkt-RF", "SMB", "HML", "WML"])]:
        available = [c for c in cols if c in ff.columns and not ff[c].isna().all()]
        if not available:
            continue
        X = add_constant(ff.loc[common, available].values)
        mask = ~(np.isnan(X).any(axis=1) | np.isnan(y))
        X_clean, y_clean = X[mask], y[mask]
        if len(y_clean) < 60:
            continue

        model = OLS(y_clean, X_clean).fit(
            cov_type="HAC", cov_kwds={"maxlags": int(len(y_clean) ** (1/3))}
        )
        results[label] = {
            "alpha": model.params[0],
            "alpha_t": model.tvalues[0],
            "alpha_p": model.pvalues[0],
            "R2": model.rsquared,
            "coeffs": dict(zip(["const"] + available, model.params)),
            "tvals": dict(zip(["const"] + available, model.tvalues)),
        }

    return results if results else None


# ── Cumulative Return Chart ───────────────────────────────────────────────
def plot_cumulative_returns(strategy_dict: dict[str, pd.Series], title_suffix: str = "") -> None:
    """Plot cumulative returns."""
    fig, ax = plt.subplots(figsize=(14, 7))

    palette = ["#cc4444", "#4488cc", "#44aa44", "#ff8800", "#8844cc",
               "#cc8888", "#888888", "#aaaacc", "#448844", "#884444"]
    colors = {}
    for i, name in enumerate(strategy_dict):
        colors[name] = palette[i % len(palette)]

    for name, ret in strategy_dict.items():
        cum = (1 + ret).cumprod()
        ls = "--" if "gross" in name or name.startswith("v1") or name == "MOM" else "-"
        lw = 2.0 if name in ("v2_best", "Ensemble") else 1.2
        ax.plot(cum.index, cum.values, label=name,
                color=colors.get(name, "#000000"), linewidth=lw, linestyle=ls)

    ax.set_title(f"Cumulative Returns: Lead-Lag PCA v2{title_suffix}", fontsize=13)
    ax.set_ylabel("Growth of $1")
    ax.legend(loc="upper left", fontsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "cumulative_returns.png", dpi=150)
    plt.close(fig)
    print(f"  Chart saved: {OUTPUT_DIR / 'cumulative_returns.png'}")


# ── Main ──────────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 70)
    print("Lead-Lag PCA Strategy v2 (Practical Implementation)")
    print("US Sectors → JP Individual Stock Baskets")
    print("=" * 70)

    # 1. Data
    r_cc, r_oc, vix, _ = download_data()
    V0 = build_prior_exposures()

    # 2. Signals
    print("\n── Signal Generation ──")

    print("\n[PCA_SUB fixed λ=0.9]")
    pca_fixed_sig, _ = compute_pca_signals(r_cc, V0, lam=0.9)

    print("\n[PCA_SUB adaptive λ]")
    pca_adapt_sig, lam_hist = compute_pca_signals(r_cc, V0, adaptive=True)

    print("\n[PCA_PLAIN λ=0]")
    pca_plain_sig, _ = compute_pca_signals(r_cc, V0, lam=0.0)

    print("\n[MOM]")
    mom_sig = compute_momentum_signals(r_cc)

    print("\n[REV]")
    rev_sig = compute_reversal_signals(r_cc)

    print("\n[Ensemble (PCA_SUB + MOM + REV)]")
    ensemble_sig = compute_ensemble_signal(pca_adapt_sig, mom_sig, rev_sig)

    # 3. Sector IC analysis & filtering
    print("\n── Sector IC Analysis ──")
    selected_sectors = filter_sectors_by_ic(pca_adapt_sig, r_oc)

    ic_df = compute_sector_ic(pca_adapt_sig, r_oc)
    ic_df.to_csv(OUTPUT_DIR / "table1_sector_ic.csv", index=False)

    # 4. Build all strategy variants
    print("\n── Portfolio Construction ──")
    strategies: dict[str, pd.Series] = {}

    # --- Baselines ---
    print("\n  [v1_gross] quantile L/S, daily, no costs")
    strategies["v1_gross"] = build_long_short_portfolio(pca_fixed_sig, r_oc)

    print("  [v1_net] quantile L/S, daily, with costs")
    strategies["v1_net"] = build_long_short_portfolio(pca_fixed_sig, r_oc, apply_costs=True)

    print("  [MOM] momentum baseline")
    strategies["MOM"] = build_long_short_portfolio(mom_sig, r_oc)

    # --- v2: Multi-tranche (key innovation: reduce turnover by N) ---
    for nt in [3, 5]:
        print(f"  [MT{nt}] multi-tranche({nt}), costs")
        strategies[f"MT{nt}"] = build_multi_tranche_portfolio(
            pca_fixed_sig, r_oc, apply_costs=True, n_tranches=nt,
        )
        print(f"  [MT{nt}_gross] multi-tranche({nt}), no costs")
        strategies[f"MT{nt}_gross"] = build_multi_tranche_portfolio(
            pca_fixed_sig, r_oc, apply_costs=False, n_tranches=nt,
        )

    # --- v2: Multi-tranche + EMA smoothing ---
    for ema in [3, 5]:
        print(f"  [MT5_ema{ema}] 5-tranche + EMA({ema}), costs")
        strategies[f"MT5_ema{ema}"] = build_multi_tranche_portfolio(
            pca_fixed_sig, r_oc, apply_costs=True, n_tranches=5, smooth_span=ema,
        )

    # --- v2: Best combo: multi-tranche + IC filter + VIX ---
    print("  [v2_best] MT5 + EMA5 + IC filter + VIX, costs")
    strategies["v2_best"] = build_multi_tranche_portfolio(
        pca_fixed_sig, r_oc, vix=vix, sectors_filter=selected_sectors,
        apply_costs=True, n_tranches=5, smooth_span=5,
    )

    print("  [v2_best_gross] same, no costs")
    strategies["v2_best_gross"] = build_multi_tranche_portfolio(
        pca_fixed_sig, r_oc, vix=vix, sectors_filter=selected_sectors,
        apply_costs=False, n_tranches=5, smooth_span=5,
    )

    # --- Ensemble: multi-tranche ---
    print("  [Ensemble] PCA+MOM+REV, IC filter, VIX, MT5+EMA5, costs")
    strategies["Ensemble"] = build_multi_tranche_portfolio(
        ensemble_sig, r_oc, vix=vix, sectors_filter=selected_sectors,
        apply_costs=True, n_tranches=5, smooth_span=5,
    )

    # 5. Evaluation
    print("\n" + "=" * 70)
    print("Table 2: Strategy Comparison (v1 vs v2)")
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
    df_summary.to_csv(OUTPUT_DIR / "table2_strategy_comparison.csv", index=False)

    # 6. Factor regression
    print("\n── Downloading Fama-French factors ──")
    ff = download_ff_factors()
    if ff is not None:
        print("\n" + "=" * 70)
        print("Table 3: Factor Regression (Carhart 4-Factor)")
        print("=" * 70)
        reg_rows = []
        for name, ret in strategies.items():
            result = run_factor_regression(ret, ff, name)
            if result is None:
                continue
            res = result.get("Carhart4", result.get("FF3", {}))
            sig = "***" if res.get("alpha_p", 1) < 0.01 else "**" if res.get("alpha_p", 1) < 0.05 else "*" if res.get("alpha_p", 1) < 0.10 else ""
            print(f"  {name:25s}: α={res.get('alpha', 0):.6f} (t={res.get('alpha_t', 0):.2f}){sig}")

            row = {"Strategy": name, "Model": "Carhart4"}
            row.update({k: v for k, v in res.items() if k not in ("coeffs", "tvals")})
            reg_rows.append(row)

        if reg_rows:
            pd.DataFrame(reg_rows).to_csv(OUTPUT_DIR / "table3_factor_regression.csv", index=False)

    # 7. Cost sensitivity analysis
    print("\n" + "=" * 70)
    print("Table 4: Cost Sensitivity (MT5, λ=0.9, all sectors)")
    print("=" * 70)
    print(f"{'Spread':>8} {'Comm':>6} {'Impact':>8} {'AR%(net)':>10} {'R/R':>8} {'MDD%':>8}")
    global SPREAD_BPS, COMMISSION_BPS, IMPACT_BPS
    orig_spread, orig_comm, orig_impact = SPREAD_BPS, COMMISSION_BPS, IMPACT_BPS

    cost_scenarios = [
        ("Ultra-low",  1.0, 1.0, 1.0),   # HFT-level (unrealistic for retail)
        ("Instit.",    2.0, 2.0, 2.0),   # Top-tier institutional
        ("Default",    3.0, 3.0, 5.0),   # Our current default
        ("Retail",     5.0, 5.0, 10.0),  # Retail broker
        ("High",      10.0, 8.0, 15.0),  # ETF trading with wide spreads
    ]
    sensitivity_rows = []
    for label, sp, co, im in cost_scenarios:
        SPREAD_BPS, COMMISSION_BPS, IMPACT_BPS = sp, co, im
        ret = build_multi_tranche_portfolio(pca_fixed_sig, r_oc, apply_costs=True, n_tranches=5)
        m = compute_metrics(ret)
        print(f"  {label:10s} {sp:5.1f}  {co:5.1f}  {im:7.1f}  {m['AR']*100:9.2f}  {m['R/R']:7.2f}  {m['MDD']*100:7.2f}")
        sensitivity_rows.append({
            "Scenario": label, "Spread": sp, "Commission": co, "Impact": im,
            "AR%": m["AR"] * 100, "R/R": m["R/R"], "MDD%": m["MDD"] * 100,
        })

    SPREAD_BPS, COMMISSION_BPS, IMPACT_BPS = orig_spread, orig_comm, orig_impact
    pd.DataFrame(sensitivity_rows).to_csv(OUTPUT_DIR / "table4_cost_sensitivity.csv", index=False)

    # 8. Adaptive lambda summary
    valid_lam = lam_hist.dropna()
    if len(valid_lam) > 0:
        print(f"\n── Adaptive λ Summary ──")
        print(f"  Mean: {valid_lam.mean():.3f}, Std: {valid_lam.std():.3f}")
        print(f"  Min:  {valid_lam.min():.3f}, Max: {valid_lam.max():.3f}")

    # 8. Chart
    plot_cumulative_returns(strategies)

    # 9. Save returns
    all_ret = pd.DataFrame({k: v for k, v in strategies.items()})
    all_ret.to_csv(OUTPUT_DIR / "daily_returns.csv")

    print(f"\n{'=' * 70}")
    print(f"Done. All outputs: {OUTPUT_DIR}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
