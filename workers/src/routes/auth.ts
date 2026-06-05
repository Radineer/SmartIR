import { Hono } from "hono";
import { SignJWT } from "jose";
import { getSupabase, type Env } from "../lib/supabase";
import { authMiddleware, type AuthEnv } from "../lib/auth";

const app = new Hono<AuthEnv>();

// POST /api/auth/register
app.post("/register", async (c) => {
  const { email, password, username } = await c.req.json();
  if (!email || !password) {
    return c.json({ detail: "Email and password required" }, 400);
  }

  const supabase = getSupabase(c.env);

  // Check existing user
  const { data: existing } = await supabase
    .from("users")
    .select("id")
    .eq("email", email)
    .single();

  if (existing) {
    return c.json({ detail: "Email already registered" }, 400);
  }

  // Hash password using Web Crypto API (bcrypt not available in Workers)
  const encoder = new TextEncoder();
  const data = encoder.encode(password + c.env.JWT_SECRET_KEY);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const hashedPassword = hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");

  const { data: user, error } = await supabase
    .from("users")
    .insert({ email, hashed_password: hashedPassword, username: username || email })
    .select("id, email, username")
    .single();

  if (error) return c.json({ detail: error.message }, 500);
  return c.json(user, 201);
});

// POST /api/auth/login
app.post("/login", async (c) => {
  const { email, password } = await c.req.json();
  if (!email || !password) {
    return c.json({ detail: "Email and password required" }, 400);
  }

  const supabase = getSupabase(c.env);

  // Hash password same way
  const encoder = new TextEncoder();
  const data = encoder.encode(password + c.env.JWT_SECRET_KEY);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const hashedPassword = hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");

  const { data: user } = await supabase
    .from("users")
    .select("id, email, username, hashed_password")
    .eq("email", email)
    .single();

  if (!user || user.hashed_password !== hashedPassword) {
    return c.json({ detail: "Invalid email or password" }, 401);
  }

  const secret = new TextEncoder().encode(c.env.JWT_SECRET_KEY);
  const token = await new SignJWT({ sub: String(user.id), email: user.email })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("24h")
    .sign(secret);

  return c.json({
    access_token: token,
    token_type: "bearer",
    user: { id: user.id, email: user.email, username: user.username },
  });
});

// GET /api/auth/me
app.get("/me", authMiddleware, async (c) => {
  const userId = c.get("userId");
  const supabase = getSupabase(c.env);

  const { data: user } = await supabase
    .from("users")
    .select("id, email, username, created_at")
    .eq("id", userId)
    .single();

  if (!user) return c.json({ detail: "User not found" }, 404);
  return c.json(user);
});

export default app;
