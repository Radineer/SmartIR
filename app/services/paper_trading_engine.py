"""
ペーパートレードエンジン
AIトレーディングチャレンジ用の仮想売買執行・ポジション管理・時価評価
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional

import yfinance as yf
from sqlalchemy.orm import Session

from app.models.paper_trading import PaperPosition, PaperTrade, PaperPortfolioSnapshot

logger = logging.getLogger(__name__)

INITIAL_CAPITAL = 100_000.0  # 10万円
COST_BPS = 10  # 取引コスト 10bps


@dataclass
class Order:
    """売買注文"""
    ticker: str
    side: str  # "buy" / "sell"
    shares: float
    company_name: str = ""
    sector: str = ""
    signal_source: str = ""
    signal_strength: float = 0.0
    reason: str = ""


@dataclass
class Portfolio:
    """現在のポートフォリオ状態"""
    cash: float = INITIAL_CAPITAL
    positions: list = field(default_factory=list)
    nav: float = INITIAL_CAPITAL
    day_number: int = 0


class PaperTradingEngine:
    """ペーパートレード執行エンジン"""

    def __init__(self, db: Session):
        self.db = db

    def get_portfolio(self) -> Portfolio:
        """現在のポートフォリオ状態を取得"""
        positions = self.db.query(PaperPosition).all()

        # 最新のスナップショットからキャッシュ残高を取得
        latest = (
            self.db.query(PaperPortfolioSnapshot)
            .order_by(PaperPortfolioSnapshot.snapshot_date.desc())
            .first()
        )

        if latest:
            cash = latest.cash
            day_number = latest.id  # スナップショット数 ≒ Day数
        else:
            cash = INITIAL_CAPITAL
            day_number = 0

        positions_value = sum(
            (p.current_price or p.avg_cost) * p.shares for p in positions
        )

        return Portfolio(
            cash=cash,
            positions=positions,
            nav=cash + positions_value,
            day_number=day_number,
        )

    def fetch_prices(self, tickers: list[str]) -> dict[str, float]:
        """yfinanceで最新終値を取得"""
        if not tickers:
            return {}

        prices = {}
        try:
            data = yf.download(tickers, period="5d", auto_adjust=True, progress=False)
            if data.empty:
                logger.warning("yfinance returned empty data")
                return prices

            close = data["Close"] if len(tickers) > 1 else data["Close"].to_frame(tickers[0])

            for ticker in tickers:
                if ticker in close.columns:
                    valid = close[ticker].dropna()
                    if not valid.empty:
                        prices[ticker] = float(valid.iloc[-1])
        except Exception as e:
            logger.error(f"Price fetch error: {e}")

        return prices

    def execute_orders(
        self, orders: list[Order], prices: Optional[dict[str, float]] = None
    ) -> list[PaperTrade]:
        """注文を仮想執行"""
        if not orders:
            return []

        # 価格取得
        if prices is None:
            tickers = list({o.ticker for o in orders})
            prices = self.fetch_prices(tickers)

        portfolio = self.get_portfolio()
        cash = portfolio.cash
        trades = []

        for order in orders:
            price = prices.get(order.ticker)
            if price is None or price <= 0:
                logger.warning(f"No price for {order.ticker}, skipping")
                continue

            cost = price * order.shares * COST_BPS / 10000

            if order.side == "buy":
                total_amount = price * order.shares + cost
                if total_amount > cash:
                    # 資金不足 → 買える分だけ買う
                    max_shares = (cash - cost) / price * (1 - COST_BPS / 10000)
                    if max_shares < 0.01:
                        logger.warning(f"Insufficient cash for {order.ticker}")
                        continue
                    order.shares = round(max_shares, 4)
                    cost = price * order.shares * COST_BPS / 10000
                    total_amount = price * order.shares + cost

                cash -= total_amount
                self._update_position_buy(order, price)
            else:  # sell
                total_amount = price * order.shares - cost
                cash += total_amount
                self._update_position_sell(order, price)

            trade = PaperTrade(
                ticker=order.ticker,
                company_name=order.company_name,
                side=order.side,
                shares=order.shares,
                price=price,
                cost=cost,
                total_amount=total_amount,
                signal_source=order.signal_source,
                signal_strength=order.signal_strength,
                reason=order.reason,
                executed_at=datetime.utcnow(),
            )
            self.db.add(trade)
            trades.append(trade)
            logger.info(
                f"Executed: {order.side.upper()} {order.shares:.4f} {order.ticker} "
                f"@ {price:.0f} (cost: {cost:.0f})"
            )

        # キャッシュを一時的にメタデータとして保持（mark_to_marketでスナップショット化）
        self._pending_cash = cash
        self.db.commit()
        return trades

    def _update_position_buy(self, order: Order, price: float):
        """買い注文によるポジション更新"""
        pos = (
            self.db.query(PaperPosition)
            .filter(PaperPosition.ticker == order.ticker)
            .first()
        )
        if pos:
            # 既存ポジションに追加 → 平均取得単価を更新
            total_cost = pos.avg_cost * pos.shares + price * order.shares
            pos.shares += order.shares
            pos.avg_cost = total_cost / pos.shares
            pos.current_price = price
            pos.peak_price = max(pos.peak_price or 0, price)
        else:
            pos = PaperPosition(
                ticker=order.ticker,
                company_name=order.company_name,
                shares=order.shares,
                avg_cost=price,
                current_price=price,
                sector=order.sector,
                signal_source=order.signal_source,
                opened_at=datetime.utcnow(),
                peak_price=price,
                metadata_={
                    "signal_strength": order.signal_strength,
                    "reason": order.reason,
                },
            )
            self.db.add(pos)

    def _update_position_sell(self, order: Order, price: float):
        """売り注文によるポジション更新"""
        pos = (
            self.db.query(PaperPosition)
            .filter(PaperPosition.ticker == order.ticker)
            .first()
        )
        if not pos:
            logger.warning(f"No position to sell for {order.ticker}")
            return

        pos.shares -= order.shares
        if pos.shares <= 0.001:
            self.db.delete(pos)
        else:
            pos.current_price = price

    def mark_to_market(
        self,
        target_date: Optional[date] = None,
        trades_today: Optional[list[PaperTrade]] = None,
    ) -> PaperPortfolioSnapshot:
        """全ポジション時価評価 + 日次スナップショット保存"""
        if target_date is None:
            target_date = date.today()

        date_str = target_date.isoformat()

        # 既存スナップショットがあれば更新
        existing = (
            self.db.query(PaperPortfolioSnapshot)
            .filter(PaperPortfolioSnapshot.snapshot_date == date_str)
            .first()
        )

        positions = self.db.query(PaperPosition).all()

        # 最新価格取得
        if positions:
            tickers = [p.ticker for p in positions]
            prices = self.fetch_prices(tickers)
            for pos in positions:
                if pos.ticker in prices:
                    pos.current_price = prices[pos.ticker]
                    pos.peak_price = max(pos.peak_price or 0, pos.current_price)
                    pos.unrealized_pnl = (pos.current_price - pos.avg_cost) * pos.shares

        positions_value = sum(
            (p.current_price or p.avg_cost) * p.shares for p in positions
        )

        # キャッシュ残高の決定
        cash = getattr(self, "_pending_cash", None)
        if cash is None:
            prev = (
                self.db.query(PaperPortfolioSnapshot)
                .order_by(PaperPortfolioSnapshot.snapshot_date.desc())
                .first()
            )
            cash = prev.cash if prev else INITIAL_CAPITAL

        total_nav = cash + positions_value

        # 前日比リターン
        prev_snapshot = (
            self.db.query(PaperPortfolioSnapshot)
            .filter(PaperPortfolioSnapshot.snapshot_date < date_str)
            .order_by(PaperPortfolioSnapshot.snapshot_date.desc())
            .first()
        )
        prev_nav = prev_snapshot.total_nav if prev_snapshot else INITIAL_CAPITAL
        daily_return = (total_nav / prev_nav - 1) * 100 if prev_nav > 0 else 0
        cumulative_return = (total_nav / INITIAL_CAPITAL - 1) * 100

        # 最大ドローダウン
        peak_nav = INITIAL_CAPITAL
        all_snapshots = (
            self.db.query(PaperPortfolioSnapshot)
            .order_by(PaperPortfolioSnapshot.snapshot_date)
            .all()
        )
        for s in all_snapshots:
            peak_nav = max(peak_nav, s.total_nav)
        peak_nav = max(peak_nav, total_nav)
        max_dd = (1 - total_nav / peak_nav) * 100 if peak_nav > 0 else 0

        # ポジション詳細
        positions_detail = [
            {
                "ticker": p.ticker,
                "company_name": p.company_name,
                "shares": p.shares,
                "avg_cost": p.avg_cost,
                "current_price": p.current_price,
                "unrealized_pnl": p.unrealized_pnl,
                "sector": p.sector,
            }
            for p in positions
        ]

        # 本日の取引
        trades_detail = []
        if trades_today:
            trades_detail = [
                {
                    "ticker": t.ticker,
                    "side": t.side,
                    "shares": t.shares,
                    "price": t.price,
                    "cost": t.cost,
                    "reason": t.reason,
                }
                for t in trades_today
            ]

        if existing:
            existing.cash = cash
            existing.positions_value = positions_value
            existing.total_nav = total_nav
            existing.daily_return_pct = daily_return
            existing.cumulative_return_pct = cumulative_return
            existing.max_drawdown_pct = max_dd
            existing.num_positions = len(positions)
            existing.positions_detail = positions_detail
            existing.trades_today = trades_detail
            snapshot = existing
        else:
            snapshot = PaperPortfolioSnapshot(
                snapshot_date=date_str,
                cash=cash,
                positions_value=positions_value,
                total_nav=total_nav,
                daily_return_pct=daily_return,
                cumulative_return_pct=cumulative_return,
                max_drawdown_pct=max_dd,
                num_positions=len(positions),
                positions_detail=positions_detail,
                trades_today=trades_detail,
            )
            self.db.add(snapshot)

        self.db.commit()
        self._pending_cash = None

        logger.info(
            f"Snapshot {date_str}: NAV=¥{total_nav:,.0f} "
            f"(daily={daily_return:+.2f}%, cum={cumulative_return:+.2f}%, "
            f"dd={max_dd:.2f}%)"
        )
        return snapshot

    def get_day_number(self) -> int:
        """現在のDay番号（スナップショット数）"""
        return self.db.query(PaperPortfolioSnapshot).count() + 1

    def get_performance_summary(self) -> dict:
        """パフォーマンスサマリーを取得"""
        snapshots = (
            self.db.query(PaperPortfolioSnapshot)
            .order_by(PaperPortfolioSnapshot.snapshot_date)
            .all()
        )
        if not snapshots:
            return {
                "total_nav": INITIAL_CAPITAL,
                "cumulative_return_pct": 0,
                "max_drawdown_pct": 0,
                "trading_days": 0,
                "total_trades": 0,
                "win_rate": 0,
            }

        latest = snapshots[-1]

        # 勝率計算
        sell_trades = (
            self.db.query(PaperTrade)
            .filter(PaperTrade.side == "sell")
            .all()
        )
        if sell_trades:
            wins = sum(1 for t in sell_trades if self._trade_is_win(t))
            win_rate = wins / len(sell_trades) * 100
        else:
            win_rate = 0

        total_trades = self.db.query(PaperTrade).count()

        return {
            "total_nav": latest.total_nav,
            "cash": latest.cash,
            "positions_value": latest.positions_value,
            "cumulative_return_pct": latest.cumulative_return_pct,
            "max_drawdown_pct": latest.max_drawdown_pct,
            "trading_days": len(snapshots),
            "total_trades": total_trades,
            "win_rate": win_rate,
            "num_positions": latest.num_positions,
        }

    def _trade_is_win(self, trade: PaperTrade) -> bool:
        """売り取引が利益だったか（簡易判定）"""
        buy_trades = (
            self.db.query(PaperTrade)
            .filter(
                PaperTrade.ticker == trade.ticker,
                PaperTrade.side == "buy",
                PaperTrade.executed_at < trade.executed_at,
            )
            .order_by(PaperTrade.executed_at.desc())
            .first()
        )
        if buy_trades:
            return trade.price > buy_trades.price
        return False
