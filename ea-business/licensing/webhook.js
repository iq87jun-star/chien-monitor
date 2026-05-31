// RiskGuard — payment webhook -> license key issuance (reference)
//
// Receives purchase notifications from the payment provider, verifies them,
// mints a buy-once license key, and stores it so the verify server
// (server.js) will accept it. Issued keys are also written to an outbox file
// for delivery (email/Gumroad receipt is wired by the human — see ToDo).
//
// Endpoints:
//   POST /webhook/gumroad   (Gumroad "Ping", application/x-www-form-urlencoded)
//   POST /webhook/stripe    (Stripe event, JSON; verified via Stripe-Signature)
//   GET  /health
//
// SECURITY:
//   - All secrets come from environment variables (see .env.example). Nothing
//     is hardcoded. .env and the license store are .gitignored.
//   - Gumroad ping is authenticated by a shared secret you set in the Gumroad
//     resource URL as ?token=... and in GUMROAD_PING_TOKEN.
//   - Stripe is verified with HMAC-SHA256 over the raw body using
//     STRIPE_WEBHOOK_SECRET (the standard Stripe scheme).

import http from "node:http";
import crypto from "node:crypto";
import { readFile, writeFile, appendFile } from "node:fs/promises";
import { generateKey } from "./keygen.js";

const PORT          = process.env.WEBHOOK_PORT || 8090;
const DB_PATH       = process.env.LICENSE_DB_PATH || "./licenses.json";
const OUTBOX_PATH   = process.env.LICENSE_OUTBOX_PATH || "./issued-keys.log";
const PRODUCT       = process.env.PRODUCT_ID || "risk-guard";
const GUMROAD_TOKEN = process.env.GUMROAD_PING_TOKEN || "";
const STRIPE_SECRET = process.env.STRIPE_WEBHOOK_SECRET || "";

async function loadDb() {
  try { return JSON.parse(await readFile(DB_PATH, "utf8")); }
  catch { return {}; }
}
async function saveDb(db) { await writeFile(DB_PATH, JSON.stringify(db, null, 2), "utf8"); }

function send(res, status, obj) {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(obj));
}

async function readRaw(req) {
  let raw = "";
  for await (const c of req) raw += c;
  return raw;
}

// Mint a key, persist it to the verify store, and record it for delivery.
async function issueKey({ email, saleId, source }) {
  const db = await loadDb();
  const key = generateKey();
  db[key] = {
    product: PRODUCT,
    accounts: [],          // bound on first EA activation (server.js)
    revoked: false,
    email: email || null,
    saleId: saleId || null,
    source,
    createdAt: new Date().toISOString(),
  };
  await saveDb(db);
  await appendFile(
    OUTBOX_PATH,
    JSON.stringify({ key, email, saleId, source, at: db[key].createdAt }) + "\n",
    "utf8"
  );
  console.log(`issued ${key} for ${email || "?"} via ${source}`);
  return key;
}

function timingSafeEqual(a, b) {
  const ab = Buffer.from(a), bb = Buffer.from(b);
  return ab.length === bb.length && crypto.timingSafeEqual(ab, bb);
}

// ---- Gumroad ----
async function handleGumroad(req, res) {
  const url = new URL(req.url, "http://localhost");
  if (GUMROAD_TOKEN && !timingSafeEqual(url.searchParams.get("token") || "", GUMROAD_TOKEN))
    return send(res, 401, { ok: false, reason: "bad token" });

  const raw = await readRaw(req);
  const params = new URLSearchParams(raw);
  const email = params.get("email");
  const saleId = params.get("sale_id") || params.get("order_number");

  if (params.get("refunded") === "true" || params.get("disputed") === "true")
    return send(res, 200, { ok: true, note: "refund/dispute ignored at issue stage" });

  const key = await issueKey({ email, saleId, source: "gumroad" });
  return send(res, 200, { ok: true, key });
}

// ---- Stripe ----
function verifyStripe(raw, sigHeader, secret) {
  // Stripe-Signature: t=timestamp,v1=signature
  const parts = Object.fromEntries(
    (sigHeader || "").split(",").map((kv) => kv.split("=").map((s) => s.trim()))
  );
  if (!parts.t || !parts.v1) return false;
  const signed = `${parts.t}.${raw}`;
  const expected = crypto.createHmac("sha256", secret).update(signed).digest("hex");
  return timingSafeEqual(expected, parts.v1);
}

async function handleStripe(req, res) {
  const raw = await readRaw(req);
  if (!STRIPE_SECRET || !verifyStripe(raw, req.headers["stripe-signature"], STRIPE_SECRET))
    return send(res, 400, { ok: false, reason: "signature verification failed" });

  let event;
  try { event = JSON.parse(raw); }
  catch { return send(res, 400, { ok: false, reason: "bad json" }); }

  if (event.type !== "checkout.session.completed" && event.type !== "payment_intent.succeeded")
    return send(res, 200, { ok: true, ignored: event.type });

  const obj = event.data?.object || {};
  const email = obj.customer_details?.email || obj.receipt_email || null;
  const saleId = obj.id || event.id;

  const key = await issueKey({ email, saleId, source: "stripe" });
  return send(res, 200, { ok: true, key });
}

const server = http.createServer((req, res) => {
  if (req.method === "GET" && req.url === "/health") return send(res, 200, { ok: true });
  if (req.method === "POST" && req.url.startsWith("/webhook/gumroad")) return handleGumroad(req, res);
  if (req.method === "POST" && req.url === "/webhook/stripe") return handleStripe(req, res);
  return send(res, 404, { ok: false, reason: "not found" });
});

server.listen(PORT, () => console.log(`RiskGuard webhook on :${PORT}`));
