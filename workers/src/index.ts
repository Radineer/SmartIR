import { Hono } from "hono";
import { cors } from "hono/cors";
import type { Env } from "./lib/supabase";

import companiesRoutes from "./routes/companies";
import documentsRoutes from "./routes/documents";
import analysisRoutes from "./routes/analysis";
import authRoutes from "./routes/auth";
import watchlistRoutes from "./routes/watchlist";
import marketRoutes from "./routes/market";
import publicRoutes from "./routes/public";
import publishRoutes from "./routes/publish";
import sentimentRoutes from "./routes/sentiment";
import notificationsRoutes from "./routes/notifications";

import { handleTDNetCron } from "./cron/tdnet";
import { handleEDINETCron } from "./cron/edinet";
import { handleWatchlistAlertCron } from "./cron/watchlist-alert";
import { handleMarketCacheCron } from "./cron/market-cache";

const app = new Hono<{ Bindings: Env }>();

// CORS
app.use(
  "*",
  cors({
    origin: ["https://smartir.pages.dev", "http://localhost:3000"],
    allowMethods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allowHeaders: ["Content-Type", "Authorization"],
  })
);

// Health check
app.get("/", (c) =>
  c.json({
    message: "Welcome to SmartIR API",
    status: "running",
    runtime: "Cloudflare Workers",
  })
);

app.get("/health", (c) =>
  c.json({ status: "healthy", version: "2.0.0" })
);

// API routes
app.route("/api/companies", companiesRoutes);
app.route("/api/documents", documentsRoutes);
app.route("/api/analysis", analysisRoutes);
app.route("/api/auth", authRoutes);
app.route("/api/watchlist", watchlistRoutes);
app.route("/api/market", marketRoutes);
app.route("/api/public", publicRoutes);
app.route("/api/publish", publishRoutes);
app.route("/api/sentiment", sentimentRoutes);
app.route("/api/notifications", notificationsRoutes);

// Note: Heavy compute routes (ml, backtest, portfolio, technical, jquants)
// remain on the Python backend for local dev / are handled by GH Actions.
// They exceed Workers' CPU limits and are not ported here.

// Cron handler
async function handleCron(
  event: ScheduledEvent,
  env: Env,
  ctx: ExecutionContext
): Promise<void> {
  const cron = event.cron;

  switch (cron) {
    case "*/10 23,0,1,2,3,4,5,6,7,8,9 * * 1-5":
      ctx.waitUntil(handleTDNetCron(env));
      break;
    case "0 0,1,2,3,4,5,6,7,8 * * 1-5":
      ctx.waitUntil(handleEDINETCron(env));
      break;
    case "*/5 * * * *":
      ctx.waitUntil(handleWatchlistAlertCron(env));
      break;
    case "0 * * * *":
      ctx.waitUntil(handleMarketCacheCron(env));
      break;
    default:
      console.log(`Unknown cron: ${cron}`);
  }
}

export default {
  fetch: app.fetch,
  scheduled: handleCron,
};
