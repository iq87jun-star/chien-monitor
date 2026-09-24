import { test } from "node:test";
import assert from "node:assert/strict";
import { evaluate, runCheck } from "../src/check.js";
import { WEBHOOK, WEBHOOK2, fakeFetch, memoryDb, priceData } from "./helpers.js";

const NOW = () => new Date("2026-09-23T10:00:00Z");

async function setup() {
  const db = memoryDb();
  for (const [id, url] of [
    ["123456789012345678", WEBHOOK],
    ["223456789012345678", WEBHOOK2],
  ]) {
    await db.run(
      "INSERT INTO subscribers (id, webhook_url, key_hash, created_at) VALUES (?, ?, ?, ?)",
      [id, url, `hash-${id}`, "2026-09-01"],
    );
  }
  const watch = (sub, key, label, target) =>
    db.run(
      "INSERT INTO watches (subscriber_id, card_key, label, target_jpy, created_at) VALUES (?, ?, ?, ?, ?)",
      [sub, key, label, target, "2026-09-01"],
    );
  await watch("123456789012345678", "pokeca:SV2a-201", "リザードンex", 1500);
  await watch("123456789012345678", "onepiece:OP05-119:normal", "OP05-119 Monkey.D.Luffy", 1000);
  await watch("223456789012345678", "yugioh:Ash Blossom & Joyous Spring", "灰流うらら", 600);
  return db;
}
const armedOf = async (db) =>
  Object.fromEntries(
    (await db.all("SELECT card_key, armed FROM watches")).map((r) => [r.card_key, r.armed]),
  );

test("evaluate: 目標以下で通知、通知後は5%超戻るまで再通知しない", () => {
  const w = { target_jpy: 1000, armed: 1 };
  assert.equal(evaluate(w, 1000), "notify");
  assert.equal(evaluate(w, 1001), null);
  assert.equal(evaluate(w, null), null);
  const done = { target_jpy: 1000, armed: 0 };
  assert.equal(evaluate(done, 900), null);
  assert.equal(evaluate(done, 1050), null);
  assert.equal(evaluate(done, 1051), "rearm");
});

test("目標以下のカードだけ、登録者ごとにまとめて通知する", async () => {
  const db = await setup();
  const { fetchImpl, state } = fakeFetch(priceData({ pokecaEur: 8 })); // 1440円 ≤ 1500
  const stats = await runCheck({ db, fetchImpl, now: NOW });
  assert.equal(stats.notified, 2); // リザードン・うらら(ルフィは1200円 > 1000円)
  assert.equal(state.posts.length, 2);
  const first = state.posts.find((p) => p.url === WEBHOOK).body;
  assert.equal(first.embeds.length, 1);
  assert.equal(first.embeds[0].title, "リザードンex");
  assert.match(first.embeds[0].description, /1,500円\*\* 以下/);
  assert.match(first.embeds[0].description, /1,440円/);
  assert.equal(first.embeds[0].url, "https://pokeca-kaigai.com/");
  assert.deepEqual(first.allowed_mentions, { parse: [] });
  assert.deepEqual(await armedOf(db), {
    "pokeca:SV2a-201": 0,
    "onepiece:OP05-119:normal": 1,
    "yugioh:Ash Blossom & Joyous Spring": 0,
  });
});

test("データが更新されていなければ何もしない。更新後も通知済みのカードは再通知しない", async () => {
  const db = await setup();
  const { fetchImpl, state } = fakeFetch(priceData({ pokecaEur: 8 }));
  await runCheck({ db, fetchImpl, now: NOW });
  const again = await runCheck({ db, fetchImpl, now: NOW });
  assert.equal(again.skipped, true);
  state.data = priceData({ pokecaEur: 7, fetchedAt: "2026-09-23T21:00:00Z" });
  const next = await runCheck({ db, fetchImpl, now: NOW });
  assert.equal(next.skipped, false);
  assert.equal(next.notified, 0);
  assert.equal(state.posts.length, 2);
});

test("相場が目標の5%超まで戻ったら、次の値下がりでまた通知する", async () => {
  const db = await setup();
  const { fetchImpl, state } = fakeFetch(priceData({ pokecaEur: 8 }));
  await runCheck({ db, fetchImpl, now: NOW });
  state.data = priceData({ pokecaEur: 9, fetchedAt: "2026-09-24T09:00:00Z" }); // 1620円 > 1575円
  assert.equal((await runCheck({ db, fetchImpl, now: NOW })).rearmed, 1);
  state.data = priceData({ pokecaEur: 8, fetchedAt: "2026-09-24T21:00:00Z" });
  const s = await runCheck({ db, fetchImpl, now: NOW });
  assert.equal(s.notified, 1);
  assert.equal(state.posts.at(-1).body.embeds[0].title, "リザードンex");
});

test("送信に失敗したら通知済みにしない(次回また送る)", async () => {
  const db = await setup();
  const { fetchImpl, state } = fakeFetch(priceData({ pokecaEur: 8 }));
  state.discord.status = 500;
  const s = await runCheck({ db, fetchImpl, now: NOW });
  assert.equal(s.notified, 0);
  assert.equal(s.failed, 2);
  assert.equal((await armedOf(db))["pokeca:SV2a-201"], 1);
});

test("ウェブフックが削除されていたら登録者を停止する", async () => {
  const db = await setup();
  const { fetchImpl, state } = fakeFetch(priceData({ pokecaEur: 8 }));
  state.discord.status = 404;
  const s = await runCheck({ db, fetchImpl, now: NOW });
  assert.equal(s.gone, 2);
  assert.deepEqual(
    (await db.all("SELECT active FROM subscribers")).map((r) => r.active),
    [0, 0],
  );
  state.discord.status = 204;
  state.data = priceData({ pokecaEur: 7, fetchedAt: "2026-09-24T09:00:00Z" });
  await runCheck({ db, fetchImpl, now: NOW });
  assert.equal(state.posts.length, 2); // 停止した登録者には送らない
});

test("11件以上は10件ずつに分けて送る", async () => {
  const db = memoryDb();
  await db.run(
    "INSERT INTO subscribers (id, webhook_url, key_hash, plan, created_at) VALUES ('1', ?, 'h', 'pro', 'x')",
    [WEBHOOK],
  );
  const data = priceData();
  const cards = data["https://pokeca-kaigai.com/api/cards.json"].cards;
  for (let i = 0; i < 12; i++) {
    cards.push(["SV2a", String(100 + i), `カード${i}`, 1, null, null]);
    await db.run(
      "INSERT INTO watches (subscriber_id, card_key, label, target_jpy, created_at) VALUES ('1', ?, ?, 1000, 'x')",
      [`pokeca:SV2a-${100 + i}`, `カード${i}`],
    );
  }
  const { fetchImpl, state } = fakeFetch(data);
  const s = await runCheck({ db, fetchImpl, now: NOW });
  assert.equal(s.notified, 12);
  assert.deepEqual(
    state.posts.map((p) => p.body.embeds.length),
    [10, 2],
  );
});

test("有料プランを解約して上限を超えたら、先に登録した3枚だけ通知する", async () => {
  const db = memoryDb();
  await db.run(
    "INSERT INTO subscribers (id, webhook_url, key_hash, plan, created_at) VALUES ('1', ?, 'h', 'free', 'x')",
    [WEBHOOK],
  );
  const data = priceData();
  const cards = data["https://pokeca-kaigai.com/api/cards.json"].cards;
  for (let i = 0; i < 5; i++) {
    cards.push(["SV2a", String(100 + i), `カード${i}`, 1, null, null]);
    await db.run(
      "INSERT INTO watches (subscriber_id, card_key, label, target_jpy, created_at) VALUES ('1', ?, ?, 1000, 'x')",
      [`pokeca:SV2a-${100 + i}`, `カード${i}`],
    );
  }
  const { fetchImpl, state } = fakeFetch(data);
  const s = await runCheck({ db, fetchImpl, now: NOW });
  assert.equal(s.notified, 3);
  assert.deepEqual(
    state.posts[0].body.embeds.map((e) => e.title),
    ["カード0", "カード1", "カード2"],
  );
});
