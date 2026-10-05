import { test } from "node:test";
import assert from "node:assert/strict";
import { listUrl, parseSold, parseDetail, soldRecord, validRecords } from "../src/sold.js";

const item = (id, name, price, sold) =>
  `<input id="exhibit_${id}_deta" name="exhibit_data" type="hidden" value="{ &quot;name&quot;: &quot;${name}&quot;, &quot;id&quot;: &quot;${id}&quot;, &quot;price&quot;: &quot;${price}&quot; }" />` +
  `<li class="exhibit-box"><div class="game-image"><img alt="x" src="https://cdn.example/${id}.jpg" />` +
  (sold ? `<div class="sales-done-layer"><div class="sales-done"><p>SOLD</p></div></div>` : "") +
  `</div><div class="detail"><h3>${name}</h3><div class="sub_form_values"><p>星5キャラクターの数：30体</p></div>` +
  `<div class="link-button"><a class="exhibit-link" href="/genshin-impact/exhibits/${id}"></a></div></div></li>`;
const page = (...items) => `<html><ul class="exhibits clearfix">${items.join("")}</ul></div><footer></footer></html>`;

test("一覧の URL は全ての商品・新着順・価格帯", () => {
  const u = new URL(listUrl("houkaistarrail", { low: 10000, high: 500000 }));
  assert.equal(u.pathname, "/houkaistarrail/exhibits");
  assert.equal(u.searchParams.get("filter"), "all");
  assert.equal(u.searchParams.get("sort"), "new");
  assert.equal(u.searchParams.get("low_price"), "10000");
  assert.equal(u.searchParams.get("high_price"), "500000");
});

test("一覧から売れた出品(SOLD)だけを取り出す", () => {
  const r = parseSold(page(item(3, "フリーナ完凸", 55000, true), item(2, "販売中", 40000, false), item(1, "ニコ完凸", 50000, true)));
  assert.deepEqual(r.map((it) => it.id), ["3", "1"]);
  assert.deepEqual(soldRecord(r[0]), {
    id: "3",
    name: "フリーナ完凸",
    price: 55000,
    url: "https://gametrade.jp/genshin-impact/exhibits/3",
    image: "https://cdn.example/3.jpg",
    info: ["星5キャラクターの数：30体"],
  });
});

test("出品ページから説明文の全文と原寸の画像を取り出す(関連する出品の小さい画像は除く)", () => {
  const html =
    `<img src="https://cdn.gametrade.jp/0/exhibit_image/file/10/aa-bb.jpg"><a href="https://cdn.gametrade.jp/0/exhibit_image/file/10/aa-bb.jpg">` +
    `<img src="https://cdn.gametrade.jp/0/exhibit_image/file/11/cc-dd.png"><p class="done">取引が終了しました</p>` +
    `<div class="item-description"><p>画像の通りです。
<br />即購入OK</p>

<p>夜蘭 &amp; フリーナ</p></div>` +
    `<img src="https://cdn.gametrade.jp/0/exhibit_image/file/99/small_thumb_ee-ff.jpg">`;
  assert.deepEqual(parseDetail(html), {
    description: "画像の通りです。\n即購入OK\n\n夜蘭 & フリーナ",
    images: ["https://cdn.gametrade.jp/0/exhibit_image/file/10/aa-bb.jpg", "https://cdn.gametrade.jp/0/exhibit_image/file/11/cc-dd.png"],
    done: true,
  });
});

test("Worker は形の正しい記録だけを受け付ける", () => {
  const ok = { id: "5", name: "a", price: 1000, url: "u", image: null, info: ["x"] };
  assert.deepEqual(validRecords([ok, { ...ok, id: "x" }, { ...ok, price: "1000" }, { ...ok, info: [1] }, null]), [ok]);
  assert.deepEqual(validRecords("x"), []);
});
