import { getSupabase, type Env } from "../lib/supabase";

export async function handleWatchlistAlertCron(env: Env): Promise<void> {
  console.log("Running watchlist alert check");
  const supabase = getSupabase(env);

  // Get all active (non-triggered) alerts with their watchlist items
  const { data: alerts, error } = await supabase
    .from("price_alerts")
    .select("*, watchlist_items(ticker_code, watchlist_id)")
    .eq("is_triggered", false);

  if (error || !alerts?.length) {
    console.log("No active alerts to check");
    return;
  }

  // Collect unique tickers
  const tickers = [...new Set(alerts.map((a: any) => a.watchlist_items?.ticker_code).filter(Boolean))];

  // Fetch current prices
  const prices: Record<string, number> = {};
  for (const ticker of tickers as string[]) {
    try {
      const res = await fetch(
        `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ticker + ".T")}?interval=1d&range=1d`,
        { headers: { "User-Agent": "SmartIR/1.0" } }
      );
      if (res.ok) {
        const json = (await res.json()) as {
          chart?: { result?: Array<{ meta?: { regularMarketPrice?: number } }> };
        };
        const price = json.chart?.result?.[0]?.meta?.regularMarketPrice;
        if (price) prices[ticker as string] = price;
      }
    } catch (e) {
      console.error(`Failed to fetch price for ${ticker}: ${e}`);
    }
  }

  // Check each alert
  let triggeredCount = 0;
  for (const alert of alerts) {
    const ticker = alert.watchlist_items?.ticker_code;
    if (!ticker || !prices[ticker as string]) continue;

    const currentPrice = prices[ticker as string];
    let triggered = false;

    if (alert.alert_type === "above" && currentPrice >= alert.target_price) {
      triggered = true;
    } else if (alert.alert_type === "below" && currentPrice <= alert.target_price) {
      triggered = true;
    }

    if (triggered) {
      await supabase
        .from("price_alerts")
        .update({
          is_triggered: true,
          triggered_at: new Date().toISOString(),
          current_price: currentPrice,
        })
        .eq("id", alert.id);
      triggeredCount++;
    }
  }

  console.log(`Watchlist alert check completed. Triggered: ${triggeredCount}`);
}
