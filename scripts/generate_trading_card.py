"""Day2 トレーディングチャレンジ サンプル画像を生成"""
import sys
sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright
import time

data = {
    "day": 2,
    "date": "2026-03-25",
    "nav": 102287,
    "daily_return": 2.38,
    "cumulative_return": 2.29,
    "max_dd": 0.0,
    "positions": [
        {"name": "ソフトバンクG", "ticker": "9984.T", "pnl": 1058, "pnl_pct": 7.06},
        {"name": "第一生命", "ticker": "8750.T", "pnl": 536, "pnl_pct": 3.57},
        {"name": "三井住友FG", "ticker": "8316.T", "pnl": 451, "pnl_pct": 3.01},
        {"name": "オリックス", "ticker": "8591.T", "pnl": 225, "pnl_pct": 1.50},
        {"name": "KDDI", "ticker": "9433.T", "pnl": 217, "pnl_pct": 1.45},
        {"name": "アサヒ", "ticker": "2502.T", "pnl": -109, "pnl_pct": -0.73},
    ],
}

positions_html = ""
for p in data["positions"]:
    cls = "positive" if p["pnl"] >= 0 else "negative"
    sign = "+" if p["pnl"] >= 0 else ""
    positions_html += f"""
    <div class="pos-row {cls}">
      <div><div class="pos-name">{p['name']}</div><div class="pos-ticker">{p['ticker']}</div></div>
      <div><div class="pos-pnl {cls}">{sign}¥{p['pnl']:,}</div><div class="pos-pct">{sign}{p['pnl_pct']:.2f}%</div></div>
    </div>"""

profit = data["nav"] - 100000

html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700;900&display=swap');
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  font-family: 'Noto Sans JP', sans-serif;
  width: 1080px; height: 1920px;
  background: linear-gradient(135deg, #0a0a2e 0%, #1a1a4e 50%, #0d0d35 100%);
  color: white; padding: 60px;
  display: flex; flex-direction: column;
}}
.header {{ text-align: center; margin-bottom: 40px; }}
.day-badge {{
  display: inline-block; background: linear-gradient(135deg, #6366f1, #8b5cf6);
  padding: 12px 40px; border-radius: 50px; font-size: 32px; font-weight: 700;
  margin-bottom: 20px; letter-spacing: 2px;
}}
.title {{ font-size: 42px; font-weight: 900; margin-bottom: 10px; }}
.subtitle {{ font-size: 24px; color: #94a3b8; }}
.nav-card {{
  background: linear-gradient(135deg, rgba(99,102,241,0.2), rgba(139,92,246,0.1));
  border: 1px solid rgba(99,102,241,0.3); border-radius: 24px;
  padding: 50px; text-align: center; margin-bottom: 40px;
}}
.nav-amount {{ font-size: 96px; font-weight: 900; }}
.nav-change {{ font-size: 48px; font-weight: 700; margin-top: 10px; }}
.nav-change.positive {{ color: #22c55e; }}
.nav-label {{ font-size: 24px; color: #94a3b8; margin-top: 10px; }}
.stats {{ display: flex; justify-content: space-around; margin-top: 30px; }}
.stat {{ text-align: center; }}
.stat-value {{ font-size: 36px; font-weight: 700; }}
.stat-label {{ font-size: 18px; color: #94a3b8; }}
.positions {{ flex: 1; }}
.positions h2 {{ font-size: 32px; margin-bottom: 20px; color: #c4b5fd; }}
.pos-row {{
  display: flex; justify-content: space-between; align-items: center;
  padding: 20px 24px; margin-bottom: 12px;
  background: rgba(255,255,255,0.05); border-radius: 16px;
  border-left: 4px solid;
}}
.pos-row.positive {{ border-color: #22c55e; }}
.pos-row.negative {{ border-color: #ef4444; }}
.pos-name {{ font-size: 28px; font-weight: 700; }}
.pos-ticker {{ font-size: 18px; color: #94a3b8; }}
.pos-pnl {{ font-size: 32px; font-weight: 700; text-align: right; }}
.pos-pnl.positive {{ color: #22c55e; }}
.pos-pnl.negative {{ color: #ef4444; }}
.pos-pct {{ font-size: 18px; color: #94a3b8; text-align: right; }}
.footer {{
  text-align: center; padding-top: 30px;
  border-top: 1px solid rgba(255,255,255,0.1); margin-top: 20px;
}}
.footer-brand {{ font-size: 28px; font-weight: 700; color: #8b5cf6; }}
.footer-sub {{ font-size: 18px; color: #64748b; margin-top: 8px; }}
.iris-badge {{
  display: inline-block; background: rgba(139,92,246,0.2);
  border: 1px solid rgba(139,92,246,0.4); border-radius: 12px;
  padding: 8px 20px; font-size: 20px; color: #c4b5fd; margin-top: 15px;
}}
</style></head><body>

<div class="header">
  <div class="day-badge">DAY {data['day']}</div>
  <div class="title">クオンツAI トレーディング</div>
  <div class="subtitle">{data['date']} ｜ ML予測 + PCA + テクニカル指標</div>
</div>

<div class="nav-card">
  <div class="nav-amount">¥{data['nav']:,}</div>
  <div class="nav-change positive">+{data['daily_return']:.2f}% 本日</div>
  <div class="nav-label">元手 ¥100,000 → 累積 +{data['cumulative_return']:.2f}%</div>
  <div class="stats">
    <div class="stat">
      <div class="stat-value" style="color:#22c55e">+¥{profit:,}</div>
      <div class="stat-label">含み益</div>
    </div>
    <div class="stat">
      <div class="stat-value">{len(data['positions'])}</div>
      <div class="stat-label">保有銘柄</div>
    </div>
    <div class="stat">
      <div class="stat-value">{data['max_dd']:.1f}%</div>
      <div class="stat-label">最大DD</div>
    </div>
  </div>
</div>

<div class="positions">
  <h2>保有ポートフォリオ</h2>
  {positions_html}
</div>

<div class="footer">
  <div class="footer-brand">SmartIR × Iris</div>
  <div class="footer-sub">60+テクニカル指標 × ML予測 × Lead-Lag PCA</div>
  <div class="iris-badge">🤖 完全自動運用 ｜ 人間の判断介入なし</div>
</div>

</body></html>"""

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1080, "height": 1920})
    page.set_content(html)
    page.wait_for_load_state("networkidle")
    time.sleep(2)
    page.screenshot(path="output/trading_day2_sample.png")
    browser.close()
    print("Saved: output/trading_day2_sample.png")
