// 有料プラン(Stripe)。Workers で動かすため SDK を使わず REST API を fetch で呼ぶ。
//   申し込み: Stripe Checkout(サブスクリプション)→ Webhook の checkout.session.completed で plan='pro'
//   解約・支払い失敗: Webhook の customer.subscription.updated / deleted で plan='free'
//   支払い方法の変更・解約: Stripe のカスタマーポータル
// 設定(Worker の Secrets): STRIPE_SECRET_KEY / STRIPE_PRICE_ID / STRIPE_WEBHOOK_SECRET。
// 未設定なら有料プランの申し込みは表示しない。

const STRIPE_API = "https://api.stripe.com";
// 契約が続いているとみなす状態(past_due は Stripe が支払いを再試行している間なので有料のまま)
const PAID_STATUSES = new Set(["active", "trialing", "past_due"]);
const TOLERANCE_SEC = 300;

export function billingConfig(env) {
  if (!env.STRIPE_SECRET_KEY || !env.STRIPE_PRICE_ID || !env.STRIPE_WEBHOOK_SECRET) return null;
  return {
    secretKey: env.STRIPE_SECRET_KEY,
    priceId: env.STRIPE_PRICE_ID,
    webhookSecret: env.STRIPE_WEBHOOK_SECRET,
    priceLabel: env.PRICE_LABEL ?? "",
    apiOrigin: env.STRIPE_API_ORIGIN ?? STRIPE_API, // テストでは偽の Stripe に向ける
  };
}

async function stripe(cfg, fetchImpl, method, path, params = {}) {
  const res = await fetchImpl(`${cfg.apiOrigin}${path}`, {
    method,
    headers: {
      authorization: `Bearer ${cfg.secretKey}`,
      "content-type": "application/x-www-form-urlencoded",
    },
    body: method === "GET" ? undefined : new URLSearchParams(params).toString(),
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new Error(`Stripe ${path}: ${body?.error?.message ?? `HTTP ${res.status}`}`);
  return body;
}

export async function createCheckout(cfg, fetchImpl, { sub, origin }) {
  const params = {
    mode: "subscription",
    "line_items[0][price]": cfg.priceId,
    "line_items[0][quantity]": "1",
    client_reference_id: sub.id,
    "subscription_data[metadata][subscriber_id]": sub.id,
    success_url: `${origin}/?paid=1`,
    cancel_url: `${origin}/`,
    locale: "ja",
  };
  if (sub.stripe_customer_id) params.customer = sub.stripe_customer_id;
  return (await stripe(cfg, fetchImpl, "POST", "/v1/checkout/sessions", params)).url;
}

export async function createPortal(cfg, fetchImpl, { customer, origin }) {
  return (
    await stripe(cfg, fetchImpl, "POST", "/v1/billing_portal/sessions", {
      customer,
      return_url: `${origin}/`,
    })
  ).url;
}

export async function cancelSubscription(cfg, fetchImpl, subscriptionId) {
  await stripe(cfg, fetchImpl, "DELETE", `/v1/subscriptions/${encodeURIComponent(subscriptionId)}`);
}

async function hmacHex(secret, text) {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(text));
  return [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function safeEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

// Stripe-Signature ヘッダー(t=時刻,v1=署名,…)を検証する。5分より古い署名は受け付けない
export async function verifyWebhook(payload, header, secret, nowSec = Date.now() / 1000) {
  const parts = String(header ?? "")
    .split(",")
    .map((p) => p.trim().split("="));
  const t = parts.find(([k]) => k === "t")?.[1];
  const sigs = parts.filter(([k]) => k === "v1").map(([, v]) => v);
  if (!t || sigs.length === 0 || Math.abs(nowSec - Number(t)) > TOLERANCE_SEC) return false;
  const expected = await hmacHex(secret, `${t}.${payload}`);
  return sigs.some((s) => safeEqual(s, expected));
}

// テスト用: 正しい署名ヘッダーを作る
export async function signWebhook(payload, secret, nowSec = Math.floor(Date.now() / 1000)) {
  return `t=${nowSec},v1=${await hmacHex(secret, `${nowSec}.${payload}`)}`;
}

// Webhook のイベントでプランを切り替える。対象外のイベントは何もしない
export async function applyStripeEvent(db, event) {
  const obj = event?.data?.object ?? {};
  if (event.type === "checkout.session.completed") {
    if (obj.mode !== "subscription" || !obj.client_reference_id || !obj.subscription) return false;
    await db.run(
      `UPDATE subscribers SET plan = 'pro', stripe_customer_id = ?, stripe_subscription_id = ?
       WHERE id = ?`,
      [obj.customer ?? null, obj.subscription, obj.client_reference_id],
    );
    return true;
  }
  if (
    event.type === "customer.subscription.updated" ||
    event.type === "customer.subscription.deleted"
  ) {
    const paid = event.type === "customer.subscription.updated" && PAID_STATUSES.has(obj.status);
    await db.run("UPDATE subscribers SET plan = ? WHERE stripe_subscription_id = ?", [
      paid ? "pro" : "free",
      obj.id,
    ]);
    return true;
  }
  return false;
}
