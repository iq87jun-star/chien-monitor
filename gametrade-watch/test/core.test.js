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
