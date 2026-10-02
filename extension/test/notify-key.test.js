// バッジの「値下がり通知」リンクのカードの識別子が、通知サービス(notify/)の登録ページの識別子と一致すること。
// 一致しないと、リンクから開いた登録ページでカードが選ばれない
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import "../src/matcher.js";
import { buildCards } from "../../notify/public/prices.js";

const M = globalThis.PokecaMatcher;
const read = (f) => JSON.parse(fs.readFileSync(new URL(`./fixtures/${f}`, import.meta.url)));

for (const [file, game] of [
  ["cards.json", "pokeca"],
  ["yugioh.json", "yugioh"],
  ["onepiece.json", "onepiece"],
]) {
  test(`${game}: 拡張の照合結果のカードは、すべて通知サービスの登録ページにある`, () => {
    const data = read(file);
    const index = M.buildIndex(data);
    const notifyKeys = new Set(buildCards(game, data).map((c) => c.key));
    const cards = new Set(
      index.byCode ? [...index.byCode.values()].flat() : [...index.byName.values()].flat(),
    );
    assert.ok(cards.size > 0);
    for (const card of cards) {
      if (!(card.price > 0)) continue; // 価格の無いカードは通知サービスでも扱わない
      const key = M.notifyKey(index, card);
      assert.ok(notifyKeys.has(key), `${key} が登録ページに無い`);
    }
  });
}
