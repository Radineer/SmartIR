import { Hono } from "hono";
import { getSupabase, type Env } from "../lib/supabase";
import { getCached } from "../lib/kv";

const app = new Hono<{ Bindings: Env }>();

// GET /api/sentiment/fear-greed
app.get("/fear-greed", async (c) => {
  const data = await getCached(c.env.MARKET_CACHE, "fear-greed", 3600, async () => {
    // Simplified fear/greed calculation based on market data
    const res = await fetch(
      "https://query1.finance.yahoo.com/v8/finance/chart/^N225?interval=1d&range=5d",
      { headers: { "User-Agent": "SmartIR/1.0" } }
    );
    if (!res.ok) return { fear_greed_index: 50, market_mood: "neutral" };

    const json = (await res.json()) as {
      chart?: {
        result?: Array<{
          indicators?: { quote?: Array<{ close?: number[] }> };
        }>;
      };
    };

    const closes = json.chart?.result?.[0]?.indicators?.quote?.[0]?.close?.filter(Boolean) || [];
    if (closes.length < 2) return { fear_greed_index: 50, market_mood: "neutral" };

    const latest = closes[closes.length - 1]!;
    const prev = closes[closes.length - 2]!;
    const change = ((latest - prev) / prev) * 100;

    let index = 50 + change * 10;
    index = Math.max(0, Math.min(100, index));

    let mood = "neutral";
    if (index >= 75) mood = "extreme_greed";
    else if (index >= 55) mood = "greed";
    else if (index <= 25) mood = "extreme_fear";
    else if (index <= 45) mood = "fear";

    return { fear_greed_index: Math.round(index), market_mood: mood };
  });

  return c.json(data);
});

// GET /api/sentiment/market/overview
app.get("/market/overview", async (c) => {
  const data = await getCached(c.env.MARKET_CACHE, "market-sentiment", 3600, async () => {
    return { message: "Market sentiment data - updated by GH Actions sentiment job" };
  });
  return c.json(data);
});

// GET /api/sentiment/:ticker - stored sentiment from DB
app.get("/:ticker", async (c) => {
  const ticker = c.req.param("ticker");
  const supabase = getSupabase(c.env);

  // Look up company and latest analysis sentiment
  const { data: company } = await supabase
    .from("companies")
    .select("id")
    .eq("ticker_code", ticker)
    .single();

  if (!company) return c.json({ detail: "Ticker not found" }, 404);

  const { data: analysis } = await supabase
    .from("analysis_results")
    .select("sentiment_positive, sentiment_negative, sentiment_neutral, created_at")
    .eq("document_id", company.id)
    .order("created_at", { ascending: false })
    .limit(1)
    .single();

  return c.json(analysis || { message: "No sentiment data available" });
});

export default app;
