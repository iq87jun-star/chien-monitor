// 登録ページから呼ぶ API(Worker の /api/*)。
//   POST   /api/subscribe      { webhookUrl }                → { key } 管理キーを発行(Discord にも管理リンクを投稿)
//   GET    /api/me                                           → { plan, limit, watches, billing }
//   POST   /api/watches        { cardKey, label, targetJpy } → 追加(同じカードなら目標額を更新)
//   DELETE /api/watches/:id
//   POST   /api/test                                          → テスト通知を送る
//   DELETE /api/me                                           → 登録をすべて削除(有料プランも解約)
//   POST   /api/checkout                                     → { url } 有料プランの申し込み(Stripe Checkout)
//   POST   /api/portal                                       → { url } お支払い方法の変更・解約(Stripe)
//   POST   /api/stripe/webhook                               ← Stripe からの通知(署名で検証)
// 認証は Authorization: Bearer <管理キー>。キーは SHA-256 だけを保存する。
import {
  parseWebhook,
  postWebhook,
  testMessage,
  webhookExists,
  welcomeMessage,
} from "./discord.js";
import {
  applyStripeEvent,
  cancelSubscription,
  createCheckout,
  createPortal,
  verifyWebhook,
} from "./billing.js";
import { limitOf } from "./plans.js";

const MAX_BODY = 4096;
const MAX_TARGET = 100_000_000;
const CARD_KEY_RE = /^(pokeca|yugioh|onepiece):.{1,150}$/s;

const json = (status, body) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
const fail = (status, error) => json(status, { error });

function newKey() {
  const bytes = crypto.getRandomValues(new Uint8Array(24));
  return btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

async function sha256(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function readBody(request) {
  const text = await request.text();
  if (text.length > MAX_BODY) return null;
  try {
    const body = JSON.parse(text || "{}");
    return body && typeof body === "object" ? body : null;
  } catch {
    return null;
  }
}

async function authorize(request, db) {
  const m = /^Bearer\s+([\w-]{20,64})$/.exec(request.headers.get("authorization") ?? "");
  if (!m) return null;
  const rows = await db.all("SELECT * FROM subscribers WHERE key_hash = ?", [await sha256(m[1])]);
  return rows[0] ?? null;
}

// deps: { db, fetchImpl, discordOrigin, billing(src/billing.js の billingConfig。未設定なら null), now }
export async function handleApi(request, deps) {
  const { db, fetchImpl = fetch, discordOrigin, billing = null, now = () => new Date() } = deps;
  const url = new URL(request.url);
  const route = `${request.method} ${url.pathname.replace(/\/+$/, "")}`;

  if (route === "POST /api/subscribe") {
    const body = await readBody(request);
    const hook = parseWebhook(body?.webhookUrl);
    if (!hook) return fail(400, "Discord のウェブフックURLの形式ではありません");
    if (!(await webhookExists(fetchImpl, hook.url, discordOrigin))) {
      return fail(400, "このウェブフックは Discord に見つかりませんでした。URLを確認してください");
    }
    const key = newKey();
    await db.run(
      `INSERT INTO subscribers (id, webhook_url, key_hash, created_at) VALUES (?, ?, ?, ?)
       ON CONFLICT(id) DO UPDATE SET webhook_url = excluded.webhook_url,
         key_hash = excluded.key_hash, active = 1`,
      [hook.id, hook.url, await sha256(key), now().toISOString()],
    );
    // 管理リンクをチャンネルにも残す(ブラウザを変えても設定を開けるように)。キーは # 以降に置き、サーバーに送られないようにする
    await postWebhook(
      fetchImpl,
      hook.url,
      welcomeMessage(`${url.origin}/#k=${key}`),
      discordOrigin,
    );
    return json(200, { key });
  }

  if (route === "POST /api/stripe/webhook") {
    if (!billing) return fail(503, "有料プランは準備中です");
    const payload = await request.text();
    if (payload.length > 65536) return fail(400, "too large");
    const ok = await verifyWebhook(
      payload,
      request.headers.get("stripe-signature"),
      billing.webhookSecret,
      now().getTime() / 1000,
    );
    if (!ok) return fail(400, "invalid signature");
    await applyStripeEvent(db, JSON.parse(payload));
    return json(200, { received: true });
  }

  const sub = await authorize(request, db);
  if (!sub) return fail(401, "管理キーが正しくありません。登録し直してください");
  const limit = limitOf(sub.plan);

  if (route === "GET /api/me") {
    const watches = await db.all(
      `SELECT id, card_key AS cardKey, label, target_jpy AS targetJpy, armed, notified_at AS notifiedAt
       FROM watches WHERE subscriber_id = ? ORDER BY id`,
      [sub.id],
    );
    return json(200, {
      plan: sub.plan,
      limit,
      active: sub.active === 1,
      watches,
      billing: billing
        ? { available: true, priceLabel: billing.priceLabel, proLimit: limitOf("pro") }
        : { available: false },
    });
  }

  if (route === "POST /api/watches") {
    const body = await readBody(request);
    const cardKey = typeof body?.cardKey === "string" ? body.cardKey : "";
    const label = typeof body?.label === "string" ? body.label.trim().slice(0, 120) : "";
    const target = Math.round(Number(body?.targetJpy));
    if (!CARD_KEY_RE.test(cardKey) || !label) return fail(400, "カードの指定が正しくありません");
    if (!(target >= 1 && target <= MAX_TARGET))
      return fail(400, "目標額は1円以上で入力してください");
    const existing = await db.all(
      "SELECT id FROM watches WHERE subscriber_id = ? AND card_key = ?",
      [sub.id, cardKey],
    );
    if (existing.length === 0) {
      const [{ n }] = await db.all("SELECT COUNT(*) AS n FROM watches WHERE subscriber_id = ?", [
        sub.id,
      ]);
      if (n >= limit) {
        return fail(403, `登録できるカードは${limit}枚までです。不要なカードを削除してください`);
      }
    }
    await db.run(
      `INSERT INTO watches (subscriber_id, card_key, label, target_jpy, created_at) VALUES (?, ?, ?, ?, ?)
       ON CONFLICT(subscriber_id, card_key) DO UPDATE SET label = excluded.label,
         target_jpy = excluded.target_jpy, armed = 1`,
      [sub.id, cardKey, label, target, now().toISOString()],
    );
    return json(200, { ok: true });
  }

  const del = /^DELETE \/api\/watches\/(\d+)$/.exec(route);
  if (del) {
    const changes = await db.run("DELETE FROM watches WHERE id = ? AND subscriber_id = ?", [
      Number(del[1]),
      sub.id,
    ]);
    return changes ? json(200, { ok: true }) : fail(404, "見つかりません");
  }

  if (route === "POST /api/test") {
    const r = await postWebhook(fetchImpl, sub.webhook_url, testMessage(), discordOrigin);
    if (r.gone) await db.run("UPDATE subscribers SET active = 0 WHERE id = ?", [sub.id]);
    return r.ok
      ? json(200, { ok: true })
      : fail(
          502,
          r.gone ? "ウェブフックが削除されています。登録し直してください" : "送信に失敗しました",
        );
  }

  if (route === "POST /api/checkout") {
    if (!billing) return fail(503, "有料プランは準備中です");
    if (sub.plan === "pro") return fail(400, "すでに有料プランです");
    return json(200, {
      url: await createCheckout(billing, fetchImpl, { sub, origin: url.origin }),
    });
  }

  if (route === "POST /api/portal") {
    if (!billing || !sub.stripe_customer_id) return fail(400, "お支払いの記録がありません");
    return json(200, {
      url: await createPortal(billing, fetchImpl, {
        customer: sub.stripe_customer_id,
        origin: url.origin,
      }),
    });
  }

  if (route === "DELETE /api/me") {
    // 登録を消しても課金が続かないよう、有料プランの契約を先に解約する
    if (billing && sub.plan === "pro" && sub.stripe_subscription_id) {
      await cancelSubscription(billing, fetchImpl, sub.stripe_subscription_id);
    }
    await db.run("DELETE FROM watches WHERE subscriber_id = ?", [sub.id]);
    await db.run("DELETE FROM subscribers WHERE id = ?", [sub.id]);
    return json(200, { ok: true });
  }

  return fail(404, "not found");
}
