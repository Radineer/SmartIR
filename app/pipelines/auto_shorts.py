"""決算Flash Auto Shorts - TDnetから決算短信を取得し、自動でショート動画を生成

Usage:
    python -m app.pipelines.auto_shorts          # 今日の決算短信からショート生成
    python -m app.pipelines.auto_shorts --days 3  # 直近3日分
    python -m app.pipelines.auto_shorts --max 5   # 最大5本
"""
import os, sys, re, logging, argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.crawler.tdnet import TDNetCrawler
from app.pipelines.quick_short import generate_quick_short, GREEN, BRAND, GOLD, RED, WHITE

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("./output/shorts")


def extract_period_from_title(title):
    """決算短信タイトルから決算期を抽出"""
    m = re.search(r'(\d{4})年(\d{1,2})月期', title)
    period = "%s年%s月期" % (m.group(1), m.group(2)) if m else ""

    if "第１四半期" in title or "第1四半期" in title:
        period += " 1Q"
    elif "第２四半期" in title or "第2四半期" in title or "中間" in title:
        period += " 2Q"
    elif "第３四半期" in title or "第3四半期" in title:
        period += " 3Q"
    else:
        period += " 通期"

    return period


def generate_shorts_from_tdnet(days=1, max_shorts=5):
    """TDnetから決算短信を取得し、ショート動画を自動生成"""

    crawler = TDNetCrawler()
    results = crawler.crawl(days=days)

    earnings = [
        r for r in results
        if "決算短信" in r.get("title", "")
        and "訂正" not in r.get("title", "")
    ]

    logger.info("TDnet: %d total, %d earnings reports" % (len(results), len(earnings)))

    if not earnings:
        logger.warning("No earnings reports found")
        return []

    earnings = earnings[:max_shorts]

    generated = []
    for i, filing in enumerate(earnings):
        company = filing.get("filer_name", "不明")
        ticker = filing.get("company_code", "0000")
        title = filing.get("title", "")
        period = extract_period_from_title(title)

        logger.info("[%d/%d] %s (%s) - %s" % (i + 1, len(earnings), company, ticker, period))

        try:
            # Hook text
            if "通期" in period:
                hook = "通期決算"
            elif "3Q" in period:
                hook = "3Q決算"
            elif "2Q" in period:
                hook = "中間決算"
            else:
                hook = "1Q決算"

            # Default to neutral (future: extract from PDF for beat/miss)
            beat_miss = "neutral"

            metrics = [
                {"label": "企業名", "value": company, "color": WHITE, "indicator": BRAND},
                {"label": "証券コード", "value": ticker, "change": "東証", "color": BRAND, "indicator": BRAND},
                {"label": "決算期", "value": period, "color": WHITE, "indicator": BRAND},
                {"label": "開示日", "value": datetime.now().strftime("%Y/%m/%d"), "change": "TDnet", "color": GOLD, "indicator": BRAND},
            ]

            script = [
                "速報。%sの%s決算が発表されました。" % (company, period),
                "証券コード%s。" % ticker,
                "決算の詳細はチャンネルをチェック。",
                "決算フラッシュ、フォローで毎日届く。",
            ]

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = str(OUTPUT_DIR / ("short_%s_%s.mp4" % (ticker, ts)))

            result = generate_quick_short(
                company_name=company,
                ticker=ticker,
                hook=hook,
                metrics=metrics,
                script_lines=script,
                output_path=out_path,
                beat_miss=beat_miss,
                period=period,
            )

            generated.append({
                "company": company,
                "ticker": ticker,
                "period": period,
            })
            generated[-1].update(result)

            logger.info("  -> %s (%.1fs)" % (result["video_path"], result["duration"]))

        except Exception as e:
            logger.error("  Failed: %s" % e)
            continue

    logger.info("\nGenerated %d/%d shorts" % (len(generated), len(earnings)))
    return generated


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=1, help="Days to look back")
    parser.add_argument("--max", type=int, default=5, help="Max shorts to generate")
    args = parser.parse_args()

    results = generate_shorts_from_tdnet(days=args.days, max_shorts=args.max)

    print("\n" + "=" * 60)
    print("Generated %d shorts:" % len(results))
    for r in results:
        print("  %s (%s) - %.1fs" % (r["company"], r["ticker"], r["duration"]))
        print("    %s" % r["video_path"])
        print("    %s" % r["title"])
