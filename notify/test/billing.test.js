import { test } from "node:test";
import assert from "node:assert/strict";
import { handleApi } from "../src/api.js";
import { billingConfig, signWebhook, verifyWebhook } from "../src/billing.js";
import { BILLING, WEBHOOK, fakeFetch, memoryDb, priceData } from "./helpers.js";

const ORIGIN = "https://notify.example";
const NOW = new Date("2026-09-24T00:00:00Z");
const nowSec = NOW.getTime() / 1000;

function client(billing = BILLING) {
  const db = memoryDb();
  const fake = fakeFetch(priceData());
  const send = async (method, path, { body, key, raw, headers = {} } = {}) => {
    if (key) headers.authorization = `Bearer ${key}`;
    const res = await handleApi(
      new Request(`${ORIGIN}${path}`, {
        method,
        headers: { "content-type": "application/json", ...headers },
        body: raw ?? (body === undefined ? undefined : JSON.stringify(body)),
      }),
      { db, fetchImpl: fake.fetchImpl, billing, now: () => NOW },
    );
    return { status: res.status, body: await res.json() };
  };
  const stripeEvent = async (event, secret = BILLING.webhookSecret, at = nowSec) => {
    const payload = JSON.stringify(event);
    return send("POST", "/api/stripe/webhook", {
      raw: payload,
      headers: { "stripe-signature": await signWebhook(payload, secret, at) },
    });
  };
  return { db, fake, send, stripeEvent };
}

const subscribe = async (send) =>
  (await send("POST", "/api/subscribe", { body: { webhookUrl: WEBHOOK } })).body.key;
const SUB_ID = "123456789012345678";
const completed = {
  type: "checkout.session.completed",
  data: {
    object: {
      mode: "subscription",
      client_reference_id: SUB_ID,
      customer: "cus_1",
      subscription: "sub_1",
    },
  },
};

test("設定が揃っていなければ有料プランは出さない", async () => {
  assert.equal(billingConfig({ STRIPE_SECRET_KEY: "sk", STRIPE_PRICE_ID: "p" }), null);
  const { send } = client(null);
  const key = await subscribe(send);
  assert.deepEqual((await send("GET", "/api/me", { key })).body.billing, { available: false });
  assert.equal((await send("POST", "/api/checkout", { key })).status, 503);
});

test("署名の検証: 正しい署名・改ざん・別の鍵・古い署名", async () => {
  const payload = '{"a":1}';
  const header = await signWebhook(payload, "whsec_x", nowSec);
  assert.equal(await verifyWebhook(payload, header, "whsec_x", nowSec), true);
  assert.equal(await verifyWebhook('{"a":2}', header, "whsec_x", nowSec), false);
  assert.equal(await verifyWebhook(payload, header, "whsec_y", nowSec), false);
  assert.equal(await verifyWebhook(payload, header, "whsec_x", nowSec + 301), false);
  assert.equal(await verifyWebhook(payload, "", "whsec_x", nowSec), false);
});

test("申し込み: Stripe Checkout を作って URL を返す", async () => {
  const { send, fake } = client();
  const key = await subscribe(send);
  const me = (await send("GET", "/api/me", { key })).body;
  assert.deepEqual(me.billing, { available: true, priceLabel: "月額300円", proLimit: 50 });
  const res = await send("POST", "/api/checkout", { key });
  assert.equal(res.body.url, "https://checkout.stripe.com/c/pay/cs_test_1");
  const req = fake.state.stripe[0];
  assert.equal(req.path, "/v1/checkout/sessions");
  assert.equal(req.auth, "Bearer sk_test_123");
  assert.equal(req.params.mode, "subscription");
  assert.equal(req.params["line_items[0][price]"], "price_123");
  assert.equal(req.params.client_reference_id, SUB_ID);
  assert.equal(req.params.success_url, `${ORIGIN}/?paid=1`);
});

test("決済完了で有料プラン(50枚)、解約・支払い失敗で無料プランに戻る", async () => {
  const { send, stripeEvent } = client();
  const key = await subscribe(send);
  assert.equal((await stripeEvent(completed)).status, 200);
  let me = (await send("GET", "/api/me", { key })).body;
  assert.equal(me.plan, "pro");
  assert.equal(me.limit, 50);
  assert.equal((await send("POST", "/api/checkout", { key })).status, 400); // 二重申し込み防止

  const updated = (status) => ({
    type: "customer.subscription.updated",
    data: { object: { id: "sub_1", status } },
  });
  await stripeEvent(updated("past_due")); // 再試行中は有料のまま
  assert.equal((await send("GET", "/api/me", { key })).body.plan, "pro");
  await stripeEvent(updated("unpaid"));
  assert.equal((await send("GET", "/api/me", { key })).body.plan, "free");
  await stripeEvent(updated("active"));
  assert.equal((await send("GET", "/api/me", { key })).body.plan, "pro");
  await stripeEvent({ type: "customer.subscription.deleted", data: { object: { id: "sub_1" } } });
  me = (await send("GET", "/api/me", { key })).body;
  assert.equal(me.plan, "free");
  assert.equal(me.limit, 3);
});

test("署名が正しくない Webhook ではプランを変えない", async () => {
  const { send, stripeEvent } = client();
  const key = await subscribe(send);
  assert.equal((await stripeEvent(completed, "whsec_wrong")).status, 400);
  assert.equal((await stripeEvent(completed, BILLING.webhookSecret, nowSec - 600)).status, 400);
  const noSig = await send("POST", "/api/stripe/webhook", { raw: JSON.stringify(completed) });
  assert.equal(noSig.status, 400);
  assert.equal((await send("GET", "/api/me", { key })).body.plan, "free");
});

test("お支払い管理(カスタマーポータル)", async () => {
  const { send, stripeEvent, fake } = client();
  const key = await subscribe(send);
  assert.equal((await send("POST", "/api/portal", { key })).status, 400); // 支払い記録なし
  await stripeEvent(completed);
  const res = await send("POST", "/api/portal", { key });
  assert.equal(res.body.url, "https://billing.stripe.com/p/session/test_1");
  assert.equal(fake.state.stripe.at(-1).params.customer, "cus_1");
});

test("有料プランのまま登録を削除すると、Stripe の契約も解約する", async () => {
  const { send, stripeEvent, fake, db } = client();
  const key = await subscribe(send);
  await stripeEvent(completed);
  assert.equal((await send("DELETE", "/api/me", { key })).status, 200);
  const req = fake.state.stripe.at(-1);
  assert.equal(req.method, "DELETE");
  assert.equal(req.path, "/v1/subscriptions/sub_1");
  assert.equal((await db.all("SELECT * FROM subscribers")).length, 0);
});
