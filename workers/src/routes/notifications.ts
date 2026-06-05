import { Hono } from "hono";
import { getSupabase, type Env } from "../lib/supabase";
import { authMiddleware, type AuthEnv } from "../lib/auth";

const app = new Hono<AuthEnv>();

// GET /api/notifications/settings
app.get("/settings", authMiddleware, async (c) => {
  const userId = c.get("userId");
  const supabase = getSupabase(c.env);

  const { data, error } = await supabase
    .from("notification_settings")
    .select("*")
    .eq("user_id", userId)
    .single();

  if (error || !data) return c.json({ detail: "No settings found" }, 404);
  return c.json(data);
});

// POST /api/notifications/settings
app.post("/settings", authMiddleware, async (c) => {
  const userId = c.get("userId");
  const body = await c.req.json();
  const supabase = getSupabase(c.env);

  const { data, error } = await supabase
    .from("notification_settings")
    .upsert({ user_id: userId, ...body }, { onConflict: "user_id" })
    .select()
    .single();

  if (error) return c.json({ detail: error.message }, 500);
  return c.json(data);
});

// DELETE /api/notifications/settings
app.delete("/settings", authMiddleware, async (c) => {
  const userId = c.get("userId");
  const supabase = getSupabase(c.env);

  const { error } = await supabase
    .from("notification_settings")
    .delete()
    .eq("user_id", userId);

  if (error) return c.json({ detail: error.message }, 500);
  return c.json({ status: "deleted" });
});

// GET /api/notifications/logs
app.get("/logs", authMiddleware, async (c) => {
  const userId = c.get("userId");
  const limit = Number(c.req.query("limit") || 50);
  const supabase = getSupabase(c.env);

  const { data, error } = await supabase
    .from("notification_logs")
    .select("*")
    .eq("user_id", userId)
    .order("created_at", { ascending: false })
    .limit(limit);

  if (error) return c.json({ detail: error.message }, 500);
  return c.json(data);
});

export default app;
