import { Hono } from "hono";
import { getSupabase, type Env } from "../lib/supabase";

const app = new Hono<{ Bindings: Env }>();

// GET /api/analysis - read-only: heavy LLM analysis runs in GH Actions
// This route provides analysis results stored in Supabase

// GET /api/analysis/:document_id
app.get("/:document_id", async (c) => {
  const documentId = c.req.param("document_id");
  const supabase = getSupabase(c.env);

  const { data, error } = await supabase
    .from("analysis_results")
    .select("*, documents(*), companies(*)")
    .eq("document_id", documentId)
    .single();

  if (error || !data) return c.json({ detail: "Analysis not found" }, 404);
  return c.json(data);
});

// GET /api/analysis - list recent analyses
app.get("/", async (c) => {
  const skip = Number(c.req.query("skip") || 0);
  const limit = Number(c.req.query("limit") || 20);

  const supabase = getSupabase(c.env);
  const { data, error } = await supabase
    .from("analysis_results")
    .select("*, documents(title, publish_date, doc_type), companies(name, ticker_code)")
    .order("created_at", { ascending: false })
    .range(skip, skip + limit - 1);

  if (error) return c.json({ detail: error.message }, 500);
  return c.json(data);
});

export default app;
