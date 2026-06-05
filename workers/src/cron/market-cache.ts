import type { Env } from "../lib/supabase";

const MAJOR_INDICES = ["^N225", "^TOPX", "^DJI", "^GSPC", "^IXIC"];
const CURRENCY_PAIRS = ["JPY=X", "EURJPY=X", "GBPJPY=X"];

async function fetchQuote(symbol: string): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(
      `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?interval=1d&range=1d`,
      { headers: { "User-Agent": "SmartIR/1.0" } }
    );
    if (!res.ok) return null;
    return (await res.json()) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export async function handleMarketCacheCron(env: Env): Promise<void> {
  console.log("Running market data cache refresh");
  const kv = env.MARKET_CACHE;

  // Refresh indices
  const indices = [];
  for (const symbol of MAJOR_INDICES) {
    const data = await fetchQuote(symbol);
    if (data) indices.push({ symbol, data });
  }
  await kv.put("indices", JSON.stringify(indices), { expirationTtl: 7200 });

  // Refresh currencies
  const currencies = [];
  for (const symbol of CURRENCY_PAIRS) {
    const data = await fetchQuote(symbol);
    if (data) currencies.push({ symbol, data });
  }
  await kv.put("currencies", JSON.stringify(currencies), { expirationTtl: 7200 });

  // Refresh summary
  await kv.put("summary", JSON.stringify({ indices, currencies }), {
    expirationTtl: 7200,
  });

  console.log(
    `Market cache refreshed: ${indices.length} indices, ${currencies.length} currencies`
  );
}
