import { Hono } from "hono";
import { getSupabase, type Env } from "../lib/supabase";
import { authMiddleware, type AuthEnv } from "../lib/auth";

const app = new Hono<AuthEnv>();

// POST /api/watchlist - create watchlist
app.post("/", authMiddleware, async (c) => {
  const userId = c.get("userId");
  const { name, description } = await c.req.json();
  const supabase = getSupabase(c.env);

  const { data, error } = await supabase
    .from("watchlists")
    .insert({ user_id: userId, name, description })
    .select()
    .single();

  if (error) return c.json({ detail: error.message }, 500);
  return c.json(data, 201);
});

// GET /api/watchlist - get user's watchlists
app.get("/", authMiddleware, async (c) => {
  const userId = c.get("userId");
  const supabase = getSupabase(c.env);

  const { data, error } = await supabase
    .from("watchlists")
    .select("*, watchlist_items(*, price_alerts(*))")
    .eq("user_id", userId)
    .order("created_at", { ascending: false });

  if (error) return c.json({ detail: error.message }, 500);
  return c.json(data);
});

// GET /api/watchlist/:id
app.get("/:id", authMiddleware, async (c) => {
  const id = c.req.param("id");
  const userId = c.get("userId");
  const supabase = getSupabase(c.env);

  const { data, error } = await supabase
    .from("watchlists")
    .select("*, watchlist_items(*, price_alerts(*))")
    .eq("id", id)
    .eq("user_id", userId)
    .single();

  if (error || !data) return c.json({ detail: "Watchlist not found" }, 404);
  return c.json(data);
});

// DELETE /api/watchlist/:id
app.delete("/:id", authMiddleware, async (c) => {
  const id = c.req.param("id");
  const userId = c.get("userId");
  const supabase = getSupabase(c.env);

  const { error } = await supabase
    .from("watchlists")
    .delete()
    .eq("id", id)
    .eq("user_id", userId);

  if (error) return c.json({ detail: error.message }, 500);
  return c.json({ status: "deleted" });
});

// POST /api/watchlist/:id/items - add item to watchlist
app.post("/:id/items", authMiddleware, async (c) => {
  const watchlistId = c.req.param("id");
  const body = await c.req.json();
  const supabase = getSupabase(c.env);

  const { data, error } = await supabase
    .from("watchlist_items")
    .insert({ watchlist_id: watchlistId, ...body })
    .select()
    .single();

  if (error) return c.json({ detail: error.message }, 500);
  return c.json(data, 201);
});

// PUT /api/watchlist/items/:item_id
app.put("/items/:item_id", authMiddleware, async (c) => {
  const itemId = c.req.param("item_id");
  const body = await c.req.json();
  const supabase = getSupabase(c.env);

  const { data, error } = await supabase
    .from("watchlist_items")
    .update(body)
    .eq("id", itemId)
    .select()
    .single();

  if (error) return c.json({ detail: error.message }, 500);
  return c.json(data);
});

// DELETE /api/watchlist/items/:item_id
app.delete("/items/:item_id", authMiddleware, async (c) => {
  const itemId = c.req.param("item_id");
  const supabase = getSupabase(c.env);

  const { error } = await supabase
    .from("watchlist_items")
    .delete()
    .eq("id", itemId);

  if (error) return c.json({ detail: error.message }, 500);
  return c.json({ status: "deleted" });
});

// POST /api/watchlist/items/:item_id/alerts
app.post("/items/:item_id/alerts", authMiddleware, async (c) => {
  const itemId = c.req.param("item_id");
  const body = await c.req.json();
  const supabase = getSupabase(c.env);

  const { data, error } = await supabase
    .from("price_alerts")
    .insert({ watchlist_item_id: itemId, ...body })
    .select()
    .single();

  if (error) return c.json({ detail: error.message }, 500);
  return c.json(data, 201);
});

// DELETE /api/watchlist/alerts/:alert_id
app.delete("/alerts/:alert_id", authMiddleware, async (c) => {
  const alertId = c.req.param("alert_id");
  const supabase = getSupabase(c.env);

  const { error } = await supabase
    .from("price_alerts")
    .delete()
    .eq("id", alertId);

  if (error) return c.json({ detail: error.message }, 500);
  return c.json({ status: "deleted" });
});

export default app;
