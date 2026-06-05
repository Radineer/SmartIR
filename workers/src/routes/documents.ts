import { Hono } from "hono";
import { getSupabase, type Env } from "../lib/supabase";

const app = new Hono<{ Bindings: Env }>();

// GET /api/documents
app.get("/", async (c) => {
  const skip = Number(c.req.query("skip") || 0);
  const limit = Number(c.req.query("limit") || 100);
  const companyId = c.req.query("company_id");
  const days = Number(c.req.query("days") || 7);

  const supabase = getSupabase(c.env);
  let query = supabase.from("documents").select("*");

  if (companyId) {
    query = query.eq("company_id", companyId);
  }

  if (days) {
    const dateFrom = new Date();
    dateFrom.setDate(dateFrom.getDate() - days);
    query = query.gte("publish_date", dateFrom.toISOString().slice(0, 10));
  }

  const { data, error } = await query
    .order("publish_date", { ascending: false })
    .range(skip, skip + limit - 1);

  if (error) return c.json({ detail: error.message }, 500);
  return c.json(data);
});

// GET /api/documents/:id
app.get("/:id", async (c) => {
  const id = c.req.param("id");
  const supabase = getSupabase(c.env);
  const { data, error } = await supabase
    .from("documents")
    .select("*")
    .eq("id", id)
    .single();

  if (error || !data) return c.json({ detail: "Document not found" }, 404);
  return c.json(data);
});

// POST /api/documents
app.post("/", async (c) => {
  const body = await c.req.json();
  const supabase = getSupabase(c.env);
  const { data, error } = await supabase
    .from("documents")
    .insert(body)
    .select()
    .single();

  if (error) return c.json({ detail: error.message }, 500);
  return c.json(data, 201);
});

export default app;
