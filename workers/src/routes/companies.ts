import { Hono } from "hono";
import { getSupabase, type Env } from "../lib/supabase";

const app = new Hono<{ Bindings: Env }>();

// GET /api/companies
app.get("/", async (c) => {
  const skip = Number(c.req.query("skip") || 0);
  const limit = Number(c.req.query("limit") || 100);

  const supabase = getSupabase(c.env);
  const { data, error } = await supabase
    .from("companies")
    .select("*")
    .range(skip, skip + limit - 1);

  if (error) return c.json({ detail: error.message }, 500);
  return c.json(data);
});

// GET /api/companies/:id
app.get("/:id", async (c) => {
  const id = c.req.param("id");
  const supabase = getSupabase(c.env);
  const { data, error } = await supabase
    .from("companies")
    .select("*")
    .eq("id", id)
    .single();

  if (error || !data) return c.json({ detail: "Company not found" }, 404);
  return c.json(data);
});

export default app;
