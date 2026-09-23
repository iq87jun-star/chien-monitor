import { test } from "node:test";
import assert from "node:assert/strict";
import { handleApi } from "../src/api.js";
import { WEBHOOK, WEBHOOK2, fakeFetch, memoryDb, priceData } from "./helpers.js";

const ORIGIN = "https://notify.example";

function client() {
  const db = memoryDb();
  const fake = fakeFetch(priceData());
  const call = async (method, path, { body, key } = {}) => {
    const headers = { "content-type": "application/json" };
    if (key) headers.authorization = `Bearer ${key}`;
    const res = await handleApi(
      new Request(`${ORIGIN}${path}`, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
      }),
      { db, fetchImpl: fake.fetchImpl },
    );
    return { status: res.status, body: await res.json() };
  };
  return { db, fake, call };
}

const subscribe = async (call, url = WEBHOOK) =>
  (await call("POST", "/api/subscribe", { body: { webhookUrl: url } })).body.key;

test("登録: ウェブフックを確認して管理キーを発行し、管理リンクをDiscordに投稿する", async () => {
  const { call, fake, db } = client();
  const res = await call("POST", "/api/subscribe", { body: { webhookUrl: ` ${WEBHOOK}/ ` } });
  assert.equal(res.status, 200);
  assert.match(res.body.key, /^[\w-]{32}$/);
  assert.equal(fake.state.posts.length, 1);
  assert.ok(fake.state.posts[0].body.content.includes(`${ORIGIN}/#k=${res.body.key}`));
  const [sub] = await db.all("SELECT * FROM subscribers");
  assert.equal(sub.webhook_url, WEBHOOK);
  assert.notEqual(sub.key_hash, res.body.key); // キーそのものは保存しない
});

test("登録: 形式違い・存在しないウェブフックは断る", async () => {
  const { call, fake } = client();
  for (const bad of ["https://example.com/api/webhooks/1/2", "", "discord.com/api/webhooks/x/y"]) {
    assert.equal((await call("POST", "/api/subscribe", { body: { webhookUrl: bad } })).status, 400);
  }
  fake.state.discord.exists = false;
  const res = await call("POST", "/api/subscribe", { body: { webhookUrl: WEBHOOK } });
  assert.equal(res.status, 400);
  assert.match(res.body.error, /見つかりません/);
  assert.equal(fake.state.posts.length, 0);
});

test("同じウェブフックで登録し直すと、登録済みのカードはそのままで新しいキーになる", async () => {
  const { call } = client();
  const k1 = await subscribe(call);
  await call("POST", "/api/watches", {
    key: k1,
    body: { cardKey: "pokeca:SV2a-201", label: "リザードンex", targetJpy: 1500 },
  });
  const k2 = await subscribe(call);
  assert.notEqual(k1, k2);
  assert.equal((await call("GET", "/api/me", { key: k1 })).status, 401);
  assert.equal((await call("GET", "/api/me", { key: k2 })).body.watches.length, 1);
});

test("カードの追加・目標額の更新・削除", async () => {
  const { call } = client();
  const key = await subscribe(call);
  const add = (cardKey, targetJpy) =>
    call("POST", "/api/watches", { key, body: { cardKey, label: "カード", targetJpy } });
  assert.equal((await add("pokeca:SV2a-201", 1500)).status, 200);
  assert.equal((await add("pokeca:SV2a-201", 1400.4)).status, 200); // 同じカードは更新
  let me = (await call("GET", "/api/me", { key })).body;
  assert.equal(me.plan, "free");
  assert.equal(me.limit, 3);
  assert.equal(me.watches.length, 1);
  assert.equal(me.watches[0].targetJpy, 1400);
  assert.equal((await call("DELETE", `/api/watches/${me.watches[0].id}`, { key })).status, 200);
  me = (await call("GET", "/api/me", { key })).body;
  assert.equal(me.watches.length, 0);
});

test("無料プランは3枚まで(既に登録済みのカードの更新は数えない)", async () => {
  const { call } = client();
  const key = await subscribe(call);
  const add = (cardKey) =>
    call("POST", "/api/watches", { key, body: { cardKey, label: "カード", targetJpy: 100 } });
  for (const k of ["pokeca:A-1", "pokeca:A-2", "pokeca:A-3"])
    assert.equal((await add(k)).status, 200);
  const over = await add("pokeca:A-4");
  assert.equal(over.status, 403);
  assert.match(over.body.error, /3枚まで/);
  assert.equal((await add("pokeca:A-2")).status, 200);
});

test("入力の検査", async () => {
  const { call } = client();
  const key = await subscribe(call);
  const add = (body) => call("POST", "/api/watches", { key, body });
  assert.equal((await add({ cardKey: "mtg:x", label: "a", targetJpy: 1 })).status, 400);
  assert.equal((await add({ cardKey: "pokeca:A-1", label: "", targetJpy: 1 })).status, 400);
  assert.equal((await add({ cardKey: "pokeca:A-1", label: "a", targetJpy: 0 })).status, 400);
  assert.equal((await add({ cardKey: "pokeca:A-1", label: "a", targetJpy: "abc" })).status, 400);
  const big = await call("POST", "/api/watches", {
    key,
    body: { cardKey: "pokeca:A-1", label: "x".repeat(5000), targetJpy: 1 },
  });
  assert.equal(big.status, 400);
});

test("他人のカードは削除できない・キーが無ければ401", async () => {
  const { call } = client();
  const k1 = await subscribe(call, WEBHOOK);
  const k2 = await subscribe(call, WEBHOOK2);
  await call("POST", "/api/watches", {
    key: k1,
    body: { cardKey: "pokeca:A-1", label: "a", targetJpy: 1 },
  });
  const id = (await call("GET", "/api/me", { key: k1 })).body.watches[0].id;
  assert.equal((await call("DELETE", `/api/watches/${id}`, { key: k2 })).status, 404);
  assert.equal((await call("GET", "/api/me")).status, 401);
  assert.equal((await call("GET", "/api/me", { key: "x".repeat(32) })).status, 401);
});

test("テスト通知と登録の削除", async () => {
  const { call, fake, db } = client();
  const key = await subscribe(call);
  assert.equal((await call("POST", "/api/test", { key })).status, 200);
  assert.match(fake.state.posts.at(-1).body.content, /テスト通知/);
  fake.state.discord.status = 404;
  const gone = await call("POST", "/api/test", { key });
  assert.equal(gone.status, 502);
  assert.equal((await call("GET", "/api/me", { key })).body.active, false);
  await call("POST", "/api/watches", {
    key,
    body: { cardKey: "pokeca:A-1", label: "a", targetJpy: 1 },
  });
  assert.equal((await call("DELETE", "/api/me", { key })).status, 200);
  assert.equal((await db.all("SELECT * FROM watches")).length, 0);
  assert.equal((await db.all("SELECT * FROM subscribers")).length, 0);
});
