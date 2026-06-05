import { Hono } from "hono";
import { getSupabase, type Env } from "../lib/supabase";
import { authMiddleware, type AuthEnv } from "../lib/auth";

const app = new Hono<AuthEnv>();

// GET /api/publish/logs - read-only (actual publishing done via GH Actions)
app.get("/logs", authMiddleware, async (c) => {
  const limit = Number(c.req.query("limit") || 50);
  const platform = c.req.query("platform");
  const supabase = getSupabase(c.env);

  let query = supabase
    .from("post_logs")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(limit);

  if (platform) {
    query = query.eq("platform", platform);
  }

  const { data, error } = await query;
  if (error) return c.json({ detail: error.message }, 500);
  return c.json(data);
});

export default app;
