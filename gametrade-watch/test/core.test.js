import { test } from "node:test";
import assert from "node:assert/strict";
import { parseExhibits, pick, nextState, runCheck, discordPayloads } from "../src/core.js";

const item = (id, name, price, prev) =>
  `<input id="exhibit_${id}_deta" name="exhibit_data" type="hidden" value="{ &quot;name&quot;: &quot;${name}&quot;, &quot;id&quot;: &quot;${id}&quot;, &quot;price&quot;: &quot;${price}&quot;, &quot;category&quot;: &quot;原神&quot; }" />` +
  `<li class="exhibit-box"><div class="game-image"><img alt="x" src="https://cdn.example/${id}.jpg" /></div><div class="detail"><h3>${name}</h3>` +
  `<div class="sub_form_values"><p>冒険者ランク：60ランク</p><p>星5キャラクターの数：30体</p></div>` +
  `<ul class="price">${prev ? `<li class="previous_price"><p>¥${prev.toLocaleString()}</p></li>` : ""}<li class="current_price"><span class="amount">${price}</span></li></ul>` +
  `<div class="link-button"><a class="exhibit-link" href="/genshin-impact/exhibits/${id}"></a></div></div></li>`;
const page = (...items) => `<html><nav></nav><ul class="exhibits clearfix">${items.join("")}</ul></div><footer><img src="/x.png" /></footer></html>`;

test("一覧から出品を取り出す", () => {
  const r = parseExhibits(page(item(200, "A &amp; B", 90000), item(150, "C", 80000, 100000)), "https://gametrade.jp");
  assert.equal(r.length, 2);
  assert.deepEqual(r[0], {
    id: "200",
    name: "A & B",
    price: 90000,
    url: "https://gametrade.jp/genshin-impact/exhibits/200",
    image: "https://cdn.example/200.jpg",
    previousPrice: null,
    info: ["冒険者ランク：60ランク", "星5キャラクターの数：30体"],
    sold: false,
  });
  assert.equal(r[1].previousPrice, 100000);
});

test("新規出品と値下げだけを選び、編集で上がってきただけの古い出品は選ばない", () => {
  const st = { maxId: "100", prices: { 50: 120000, 60: 90000 } };
  const mk = (id, price, previousPrice = null) => ({ id, price, previousPrice, name: id, info: [] });
  const r = pick(
    [
      mk("101", 80000), // 新規
      mk("102", 200000), // 新規だが価格帯外
      mk("50", 110000), // 記録より値下げ
      mk("60", 95000), // 値上げ
      mk("40", 100000), // 古い出品の編集
      mk("30", 100000, 130000), // 記録なし・元の価格あり
      mk("20", 140000, 300000), // 価格帯外から値下げで入ってきた
      mk("10", 70000, 90000), // 値下げだが価格帯外
    ],
    75000,
    150000,
    st,
  );
  assert.deepEqual(
    r.map((x) => `${x.id}:${x.kind}:${x.before ?? ""}`),
    ["101:new:", "50:drop:120000", "30:drop:130000", "20:drop:300000"],
  );
});

test("状態には最大IDと価格を残す", () => {
  const s = nextState({ maxId: "100", prices: { 90: 1 } }, [{ id: "120", price: 5 }, { id: "80", price: 7 }]);
  assert.equal(s.maxId, "120");
  assert.deepEqual(s.prices, { 120: 5, 90: 1, 80: 7 });
});

test("初回は記録だけ、2回目に新規と値下げを Discord に送る", async () => {
  const pages = [page(item(100, "old", 90000)), page(item(101, "new", 80000), item(100, "old", 85000))];
  let call = 0;
  const posts = [];
  const fetchImpl = async (url, init) => {
    if (String(url).startsWith("https://discord.test")) {
      posts.push(JSON.parse(init.body));
      return new Response(null, { status: 204 });
    }
    return new Response(String(url).includes("page=1") ? pages[call] : page());
  };
  const config = { url: "https://gametrade.jp/genshin-impact/exhibits?low_price=75000&high_price=150000&sort=new", pages: 2, label: "テスト" };
  const opts = { config, webhook: "https://discord.test/hook", fetchImpl, sleep: async () => {} };

  const first = await runCheck({ ...opts, state: null });
  assert.equal(first.first, true);
  assert.equal(posts.length, 0);

  call = 1;
  const second = await runCheck({ ...opts, state: first.state });
  assert.deepEqual(second.hits.map((h) => h.kind), ["new", "drop"]);
  assert.equal(posts.length, 1);
  assert.equal(posts[0].content, "🆕 テスト: 新規出品 1件 / 値下げ 1件");
  assert.equal(posts[0].embeds[1].description.split("\n")[0], "¥90,000 → **¥85,000**(6%OFF)");
});

test("11件以上は10件ずつに分けて送る", () => {
  const items = Array.from({ length: 12 }, (_, i) => ({ id: String(i), name: "x", price: 1, info: [], kind: "new" }));
  assert.deepEqual(discordPayloads(items, "L").map((p) => p.embeds.length), [10, 2]);
});

const gcItem = (id, name, price, { sold = false, type = "引退垢" } = {}) =>
  `<div class="item-row "><div class="item-row-top"><span class="item-status status10">アカウント販売・RMT</span>` +
  `<span class="item-status status account-type">${type}</span>${sold ? '<div class="product-statuses sold">SOLD</div>' : ""}</div>` +
  `<div class="item-row-middle"><div class="item-row-images"><a href="/genshin-impact/${id}"><img\n src="https://cdn.gameclub.jp/${id}.jpg" alt="x" class="item-thumb"></a></div>` +
  `<div class="item-row-content"><div class="title"><h3>\n<a href="/genshin-impact/${id}">${name}</a></h3></div>` +
  `<div class="game-title"><span><i class="fas fa-history"></i>2026/10/03 18:19</span></div>` +
  `<div class="item-status"><div class="item-status-item"><div class="item-title">冒険者ランク</div>\n<div class="item-content">60</div></div></div>` +
  `<div class="item-price"><div class="price-box"><div class="price">&yen;${price.toLocaleString("en-US")}</div></div></div></div></div></div>`;

test("ゲームクラブの一覧から出品を取り出す(販売済みは除く)", async () => {
  const { parseGameclub } = await import("../src/core.js");
  const r = parseGameclub(gcItem(300, "A &amp; B", 111111) + gcItem(301, "売れた", 90000, { sold: true }), "https://gameclub.jp");
  assert.deepEqual(r, [
    {
      id: "300",
      name: "A & B",
      price: 111111,
      url: "https://gameclub.jp/genshin-impact/300",
      image: "https://cdn.gameclub.jp/300.jpg",
      previousPrice: null,
      info: ["種類：引退垢", "出品・更新：2026/10/03 18:19", "冒険者ランク：60"],
    },
  ]);
});

test("ゲームクラブ: 新規・値下げに加え、記録のない古い出品が価格帯に現れたら価格変更として通知する", async () => {
  const pages1 = [gcItem(100, "a", 120000) + gcItem(90, "b", 100000)];
  const pages2 = [gcItem(101, "new", 80000) + gcItem(100, "a", 110000) + gcItem(90, "b", 100000) + gcItem(50, "old", 140000)];
  const posts = [];
  const fetchImpl = async (url, init) => {
    posts.push(JSON.parse(init.body));
    return new Response(null, { status: 204 });
  };
  const config = {
    site: "gameclub",
    username: "ゲームクラブ新着",
    label: "GC",
    url: "https://gameclub.jp/genshin-impact?search%5BpriceMin%5D=75000&search%5BpriceMax%5D=150000",
  };
  const opts = { config, webhook: "https://discord.test/hook", fetchImpl, sleep: async () => {} };
  const first = await runCheck({ ...opts, state: null, pages: pages1 });
  assert.equal(posts.length, 0);
  const second = await runCheck({ ...opts, state: first.state, pages: pages2 });
  assert.deepEqual(second.hits.map((h) => `${h.id}:${h.kind}`), ["101:new", "100:drop", "50:changed"]);
  assert.equal(posts[0].username, "ゲームクラブ新着");
  assert.equal(posts[0].content, "🆕 GC: 新規出品 1件 / 値下げ 1件 / 価格変更で該当 1件");
  assert.deepEqual(posts[0].embeds.map((e) => e.title), ["【新規】new", "【値下げ】a", "【価格変更】old"]);
});

test("Discord に拒否された1件だけを飛ばし、残りは届ける(https でない画像は最初から付けない)", async () => {
  const pages1 = [gcItem(100, "a", 120000)];
  const pages2 = [gcItem(101, "ok1", 80000) + gcItem(102, "bad", 90000) + gcItem(103, "ok2", 95000) + gcItem(100, "a", 120000)];
  // 102 の画像を相対パスにする
  pages2[0] = pages2[0].replace("https://cdn.gameclub.jp/102.jpg", "/img/noimage.png");
  const posts = [];
  const fetchImpl = async (url, init) => {
    const body = JSON.parse(init.body);
    posts.push(body);
    // 偽 Discord: タイトルに "ok2" を含む埋め込みは理由なく拒否、https でない URL も拒否
    const badIdx = body.embeds.findIndex(
      (e) => e.title.includes("ok2") || (e.thumbnail && !e.thumbnail.url.startsWith("https://")),
    );
    if (badIdx >= 0) return new Response(JSON.stringify({ embeds: [String(badIdx)] }), { status: 400 });
    return new Response(null, { status: 204 });
  };
  const config = {
    site: "gameclub",
    username: "GC",
    label: "GC",
    url: "https://gameclub.jp/genshin-impact?search%5BpriceMin%5D=70000&search%5BpriceMax%5D=200000",
  };
  const opts = { config, webhook: "https://discord.test/hook", fetchImpl, sleep: async () => {} };
  const first = await runCheck({ ...opts, state: null, pages: pages1 });
  const second = await runCheck({ ...opts, state: first.state, pages: pages2 });
  assert.equal(second.notified, true);
  // 相対パスの画像は付けずに送られる
  assert.equal(posts[0].embeds.find((e) => e.title.includes("bad")).thumbnail, undefined);
  // まとめて送って拒否 → 1件ずつ: ok1 と bad は届き、ok2 だけ飛ばされる
  assert.deepEqual(second.skipped.map((x) => x.title), ["【新規】ok2"]);
  const delivered = posts.slice(1).filter((p) => !p.embeds.some((e) => e.title.includes("ok2"))).flatMap((p) => p.embeds.map((e) => e.title));
  assert.deepEqual(delivered, ["【新規】ok1", "【新規】bad"]);
  // 見出しは最初に届いた投稿にだけ付く
  assert.ok(posts[1].content);
  assert.equal(posts.at(-1).content, undefined);
});

test("ゲームクラブ: 全ページを読めていない(complete=false)時は【価格変更】を出さない", async () => {
  const config = {
    site: "gameclub",
    url: "https://gameclub.jp/zenless?search%5BpriceMin%5D=70000&search%5BpriceMax%5D=200000",
  };
  const opts = { config, webhook: "https://discord.test/hook", fetchImpl: async () => new Response(null, { status: 204 }), sleep: async () => {} };
  const first = await runCheck({ ...opts, state: null, pages: [gcItem(100, "a", 120000)], complete: false });
  const pages2 = [gcItem(101, "new", 80000) + gcItem(100, "a", 110000) + gcItem(50, "old", 140000)];
  const partial = await runCheck({ ...opts, state: first.state, pages: pages2, complete: false });
  assert.deepEqual(partial.hits.map((h) => `${h.id}:${h.kind}`), ["101:new", "100:drop"]);
  const full = await runCheck({ ...opts, state: first.state, pages: pages2, complete: true });
  assert.deepEqual(full.hits.map((h) => `${h.id}:${h.kind}`), ["101:new", "100:drop", "50:changed"]);
  assert.deepEqual(full.summary, { pages: 1, complete: true, inRange: 3, priceMin: 80000, priceMax: 140000 });
});
