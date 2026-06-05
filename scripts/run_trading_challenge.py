"""
AIトレーディングチャレンジ 日次オーケストレーター
シグナル生成 → 売買判断 → ペーパートレード執行 → レポート投稿
"""

import asyncio
import argparse
import logging
import sys
from datetime import date, datetime

# プロジェクトルートをパスに追加
sys.path.insert(0, ".")

from app.core.database import SessionLocal
from app.services.portfolio_manager import PortfolioManager
from app.services.paper_trading_engine import PaperTradingEngine, Order

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def run_daily(target_date: date, dry_run: bool = False, publish: bool = True):
    """日次トレーディングチャレンジを実行"""
    db = SessionLocal()
    try:
        engine = PaperTradingEngine(db)
        manager = PortfolioManager()

        day_number = engine.get_day_number()
        logger.info(f"=== AI Trading Challenge Day {day_number} ({target_date}) ===")

        # 1. 現在のポートフォリオ状態
        portfolio = engine.get_portfolio()
        logger.info(
            f"Portfolio: NAV=¥{portfolio.nav:,.0f}, Cash=¥{portfolio.cash:,.0f}, "
            f"Positions={len(portfolio.positions)}"
        )

        # 2. シグナル生成
        logger.info("Step 1: Generating signals...")
        signals = await manager.generate_signals()
        logger.info(f"  {len(signals)} signals above threshold")

        for sig in signals[:10]:
            logger.info(
                f"  {sig.ticker} ({sig.company_name}): "
                f"ML={sig.ml_signal:+.2f} PCA={sig.pca_signal:+.2f} "
                f"Tech={sig.tech_signal:+.2f} → Combined={sig.combined:+.2f} "
                f"[{sig.confidence}]"
            )

        # 3. 売買注文生成
        logger.info("Step 2: Computing orders...")
        orders = manager.compute_orders(
            signals,
            portfolio.positions,
            portfolio.cash,
            portfolio.nav,
        )

        if not orders:
            logger.info("  No orders to execute")
        else:
            for order in orders:
                logger.info(
                    f"  {order.side.upper()} {order.ticker} ({order.company_name}) "
                    f"- {order.reason}"
                )

        if dry_run:
            logger.info("=== DRY RUN - No trades executed ===")
            # ドライランでもmark-to-marketは実行（価格更新のみ）
            snapshot = engine.mark_to_market(target_date, trades_today=[])
            _print_snapshot(snapshot, day_number)
            return

        # 4. 価格取得 & 株数確定
        logger.info("Step 3: Fetching prices and executing orders...")
        if orders:
            buy_tickers = [o.ticker for o in orders if o.side == "buy" and o.shares == 0]
            all_tickers = list({o.ticker for o in orders})
            prices = engine.fetch_prices(all_tickers)

            # 金額ベース注文を株数に変換
            orders = manager.resolve_share_counts(orders, prices, portfolio.nav)

            # 5. ペーパートレード執行
            trades = engine.execute_orders(orders, prices)
            logger.info(f"  Executed {len(trades)} trades")
        else:
            trades = []

        # 6. 時価評価 + スナップショット
        logger.info("Step 4: Mark to market...")
        snapshot = engine.mark_to_market(target_date, trades_today=trades)
        _print_snapshot(snapshot, day_number)

        # 7. レポート投稿
        if publish and trades:
            logger.info("Step 5: Publishing report...")
            await _publish_report(db, snapshot, trades, day_number, signals)
        elif publish:
            logger.info("Step 5: Publishing daily update (no trades)...")
            await _publish_report(db, snapshot, [], day_number, signals)

    except Exception as e:
        logger.error(f"Trading challenge failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


def _print_snapshot(snapshot, day_number: int):
    """スナップショット情報をログ出力"""
    logger.info("=" * 60)
    logger.info(f"Day {day_number} Summary:")
    logger.info(f"  NAV:        ¥{snapshot.total_nav:>10,.0f}")
    logger.info(f"  Cash:       ¥{snapshot.cash:>10,.0f}")
    logger.info(f"  Positions:  ¥{snapshot.positions_value:>10,.0f}")
    logger.info(f"  Daily:      {snapshot.daily_return_pct:>+8.2f}%")
    logger.info(f"  Cumulative: {snapshot.cumulative_return_pct:>+8.2f}%")
    logger.info(f"  Max DD:     {snapshot.max_drawdown_pct:>8.2f}%")
    logger.info(f"  Holdings:   {snapshot.num_positions}")

    if snapshot.positions_detail:
        logger.info("  Positions:")
        for pos in snapshot.positions_detail:
            pnl = pos.get("unrealized_pnl", 0) or 0
            logger.info(
                f"    {pos['ticker']} ({pos.get('company_name', '')}): "
                f"{pos['shares']:.4f}株 @ ¥{pos.get('current_price', 0):,.0f} "
                f"(P&L: ¥{pnl:+,.0f})"
            )

    if snapshot.trades_today:
        logger.info("  Trades today:")
        for t in snapshot.trades_today:
            logger.info(
                f"    {t['side'].upper()} {t['shares']:.4f} {t['ticker']} "
                f"@ ¥{t['price']:,.0f} - {t.get('reason', '')}"
            )
    logger.info("=" * 60)


async def _publish_report(db, snapshot, trades, day_number, signals):
    """note.com + Twitter にレポート投稿"""
    try:
        from app.publish.trading_report import TradingReportGenerator
        generator = TradingReportGenerator(db)
        await generator.publish(snapshot, trades, day_number, signals)
    except ImportError:
        logger.warning("TradingReportGenerator not yet implemented, skipping publish")
    except Exception as e:
        logger.error(f"Report publish failed: {e}", exc_info=True)


def main():
    parser = argparse.ArgumentParser(description="AI Trading Challenge")
    parser.add_argument("--date", type=str, default=None, help="Target date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Dry run (no trades)")
    parser.add_argument("--no-publish", action="store_true", help="Skip publishing")
    args = parser.parse_args()

    target_date = (
        datetime.strptime(args.date, "%Y-%m-%d").date()
        if args.date
        else date.today()
    )

    asyncio.run(run_daily(target_date, dry_run=args.dry_run, publish=not args.no_publish))


if __name__ == "__main__":
    main()
