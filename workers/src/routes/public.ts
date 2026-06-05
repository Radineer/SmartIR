import { Hono } from "hono";
import { getSupabase, type Env } from "../lib/supabase";

const app = new Hono<{ Bindings: Env }>();

// GET /api/public/stocks
app.get("/stocks", async (c) => {
  const sector = c.req.query("sector");
  const supabase = getSupabase(c.env);

  let query = supabase.from("companies").select("*").order("ticker_code");
  if (sector) {
    query = query.eq("sector", sector);
  }

  const { data, error } = await query;
  if (error) return c.json({ detail: error.message }, 500);
  return c.json(data);
});

// GET /api/public/stocks/:ticker_code
app.get("/stocks/:ticker_code", async (c) => {
  const tickerCode = c.req.param("ticker_code");
  const supabase = getSupabase(c.env);

  const { data: company } = await supabase
    .from("companies")
    .select("*")
    .eq("ticker_code", tickerCode)
    .single();

  if (!company) return c.json({ detail: "Stock not found" }, 404);

  const { data: documents } = await supabase
    .from("documents")
    .select("*")
    .eq("company_id", company.id)
    .order("publish_date", { ascending: false })
    .limit(10);

  return c.json({ ...company, recent_documents: documents || [] });
});

// GET /api/public/stocks/:ticker_code/documents
app.get("/stocks/:ticker_code/documents", async (c) => {
  const tickerCode = c.req.param("ticker_code");
  const skip = Number(c.req.query("skip") || 0);
  const limit = Number(c.req.query("limit") || 20);
  const supabase = getSupabase(c.env);

  const { data: company } = await supabase
    .from("companies")
    .select("id")
    .eq("ticker_code", tickerCode)
    .single();

  if (!company) return c.json({ detail: "Stock not found" }, 404);

  const { data, error } = await supabase
    .from("documents")
    .select("*")
    .eq("company_id", company.id)
    .order("publish_date", { ascending: false })
    .range(skip, skip + limit - 1);

  if (error) return c.json({ detail: error.message }, 500);
  return c.json(data);
});

// GET /api/public/stocks/:ticker_code/analysis
app.get("/stocks/:ticker_code/analysis", async (c) => {
  const tickerCode = c.req.param("ticker_code");
  const supabase = getSupabase(c.env);

  const { data: company } = await supabase
    .from("companies")
    .select("id")
    .eq("ticker_code", tickerCode)
    .single();

  if (!company) return c.json({ detail: "Stock not found" }, 404);

  const { data } = await supabase
    .from("analysis_results")
    .select("*, documents(title, publish_date, doc_type)")
    .eq("documents.company_id", company.id)
    .order("created_at", { ascending: false })
    .limit(1)
    .single();

  if (!data) return c.json({ detail: "No analysis found" }, 404);
  return c.json(data);
});

// GET /api/public/sectors
app.get("/sectors", async (c) => {
  const supabase = getSupabase(c.env);
  const { data, error } = await supabase
    .from("companies")
    .select("sector");

  if (error) return c.json({ detail: error.message }, 500);

  const sectorCounts: Record<string, number> = {};
  for (const row of data || []) {
    const s = row.sector || "Other";
    sectorCounts[s] = (sectorCounts[s] || 0) + 1;
  }

  const sectors = Object.entries(sectorCounts).map(([name, count]) => ({
    name,
    count,
  }));
  sectors.sort((a, b) => b.count - a.count);

  return c.json(sectors);
});

// GET /api/public/sectors/:sector
app.get("/sectors/:sector", async (c) => {
  const sector = c.req.param("sector");
  const supabase = getSupabase(c.env);

  const { data, error } = await supabase
    .from("companies")
    .select("*")
    .eq("sector", sector)
    .order("ticker_code");

  if (error) return c.json({ detail: error.message }, 500);
  return c.json(data);
});

// GET /api/public/ticker-codes
app.get("/ticker-codes", async (c) => {
  const supabase = getSupabase(c.env);
  const { data, error } = await supabase
    .from("companies")
    .select("ticker_code")
    .order("ticker_code");

  if (error) return c.json({ detail: error.message }, 500);
  return c.json((data || []).map((r: any) => r.ticker_code));
});

export default app;
