// RiskGuard — self-hosted license verification server (reference implementation)
//
// Buy-once (perpetual) licensing for off-Market sales (own LP / Gumroad).
// The EA (LicenseClient.mqh, RG_BUILD_SELF) POSTs JSON:
//   { product, key, account, broker }
// and expects:
//   200 { "valid": true }
//   200 { "valid": false, "reason": "..." }
//
// SECURITY / SCOPE:
//  - No secrets are hardcoded. Configuration comes from environment variables.
//  - Licenses live in an external store (here: a JSON file via LICENSE_DB_PATH;
//    swap for a real DB in production). The signing/admin secret, if used to
//    mint keys, must be provided via env (LICENSE_ADMIN_SECRET) and never
//    committed.
//  - Perpetual model: a key binds to the FIRST account that activates it
//    (configurable max bindings to allow the buyer's own multiple terminals).
//
// This is a reference. Deploy behind HTTPS (the EA requires HTTPS hosts to be
// whitelisted in MT5). Do not run plain HTTP in production.

import http from "node:http";
import { readFile, writeFile } from "node:fs/promises";

const PORT        = process.env.PORT || 8080;
const DB_PATH     = process.env.LICENSE_DB_PATH || "./licenses.json";
const MAX_BIND    = Number(process.env.LICENSE_MAX_BINDINGS || 2); // buyer's terminals

// licenses.json shape:
// {
//   "RG-XXXX-YYYY": { "product": "risk-guard", "accounts": [], "revoked": false }
// }
async function loadDb() {
  try { return JSON.parse(await readFile(DB_PATH, "utf8")); }
  catch { return {}; }
}
async function saveDb(db) {
  await writeFile(DB_PATH, JSON.stringify(db, null, 2), "utf8");
}

function send(res, status, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(body);
}

async function verify(req, res) {
  let raw = "";
  for await (const chunk of req) raw += chunk;

  let payload;
  try { payload = JSON.parse(raw || "{}"); }
  catch { return send(res, 400, { valid: false, reason: "bad request" }); }

  const { product, key, account } = payload;
  if (!product || !key || !account)
    return send(res, 200, { valid: false, reason: "missing fields" });

  const db = await loadDb();
  const lic = db[key];

  if (!lic || lic.product !== product)
    return send(res, 200, { valid: false, reason: "unknown license key" });
  if (lic.revoked)
    return send(res, 200, { valid: false, reason: "license revoked" });

  const acct = String(account);
  lic.accounts = lic.accounts || [];

  if (lic.accounts.includes(acct))
    return send(res, 200, { valid: true });

  // first activation on a new account: bind if capacity remains
  if (lic.accounts.length < MAX_BIND) {
    lic.accounts.push(acct);
    await saveDb(db);
    return send(res, 200, { valid: true });
  }

  return send(res, 200, {
    valid: false,
    reason: `license already bound to ${MAX_BIND} account(s)`,
  });
}

const server = http.createServer((req, res) => {
  if (req.method === "POST" && req.url === "/verify") return verify(req, res);
  if (req.method === "GET" && req.url === "/health") return send(res, 200, { ok: true });
  return send(res, 404, { valid: false, reason: "not found" });
});

server.listen(PORT, () => console.log(`RiskGuard license server on :${PORT}`));
