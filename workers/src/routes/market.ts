import { Hono } from "hono";
import type { Env } from "../lib/supabase";
import { getCached } from "../lib/kv";

const app = new Hono<{ Bindings: Env }>();

const YAHOO_FINANCE_BASE = "https://query1.finance.yahoo.com/v8/finance";

async function fetchYahooQuote(symbol: string): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(
      `${YAHOO_FINANCE_BASE}/chart/${encodeURIComponent(symbol)}?interval=1d&range=1d`,
      { headers: { "User-Agent": "SmartIR/1.0" } }
    );
    if (!res.ok) return null;
    const json = (await res.json()) as Record<string, unknown>;
    return json;
  } catch {
    return null;
  }
}

const MAJOR_INDICES: Record<string, string> = {
  "^N225": "Nikkei 225",
  "^TOPX": "TOPIX",
  "^DJI": "Dow Jones",
  "^GSPC": "S&P 500",
  "^IXIC": "NASDAQ",
};

const CURRENCY_PAIRS: Record<string, string> = {
  "JPY=X": "USD/JPY",
  "EURJPY=X": "EUR/JPY",
  "GBPJPY=X": "GBP/JPY",
};

// GET /api/market/indices
app.get("/indices", async (c) => {
  const data = await getCached(c.env.MARKET_CACHE, "indices", 3600, async () => {
    const results = [];
    for (const [symbol, name] of Object.entries(MAJOR_INDICES)) {
      const quote = await fetchYahooQuote(symbol);
      if (quote) results.push({ symbol, name, data: quote });
    }
    return results;
  });
  return c.json(data);
});

// GET /api/market/currencies
app.get("/currencies", async (c) => {
  const data = await getCached(c.env.MARKET_CACHE, "currencies", 3600, async () => {
    const results = [];
    for (const [symbol, name] of Object.entries(CURRENCY_PAIRS)) {
      const quote = await fetchYahooQuote(symbol);
      if (quote) results.push({ symbol, name, data: quote });
    }
    return results;
  });
  return c.json(data);
});

// GET /api/market/quote/:symbol
app.get("/quote/:symbol", async (c) => {
  const symbol = c.req.param("symbol");
  const data = await getCached(c.env.MARKET_CACHE, `quote:${symbol}`, 300, () =>
    fetchYahooQuote(symbol)
  );
  if (!data) return c.json({ detail: "Quote not found" }, 404);
  return c.json(data);
});

// GET /api/market/summary
app.get("/summary", async (c) => {
  const data = await getCached(c.env.MARKET_CACHE, "summary", 3600, async () => {
    const indices = [];
    for (const [symbol, name] of Object.entries(MAJOR_INDICES)) {
      const quote = await fetchYahooQuote(symbol);
      if (quote) indices.push({ symbol, name, data: quote });
    }
    const currencies = [];
    for (const [symbol, name] of Object.entries(CURRENCY_PAIRS)) {
      const quote = await fetchYahooQuote(symbol);
      if (quote) currencies.push({ symbol, name, data: quote });
    }
    return { indices, currencies };
  });
  return c.json(data);
});

// GET /api/market/search?q=...
app.get("/search", async (c) => {
  const q = c.req.query("q");
  if (!q) return c.json({ detail: "Query parameter 'q' required" }, 400);

  try {
    const res = await fetch(
      `https://query1.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(q)}&quotesCount=10&newsCount=0`,
      { headers: { "User-Agent": "SmartIR/1.0" } }
    );
    const json = await res.json();
    return c.json(json);
  } catch {
    return c.json({ detail: "Search failed" }, 500);
  }
});

export default app;
