// ゲームのアイテム(CS2・Dota 2・Rust・TF2 など、Skinport で売買できるもの)の模擬売買(お金は動かさない)の、銘柄選び。API を呼ばない純粋な関数だけ(test/cs2.test.js)。
// 相場は Skinport の公開 API(鍵なし): /v1/items(今の最安出品)と /v1/sales/history(直近 7・30・90 日の取引の中央値と件数)。
// 売買の進め方(値洗い・利確・損切り)は src/paper.js の step / buy / summary をそのまま使う。

// items と history を名前でまとめる。最安出品が無い(出品 0)品は除く
export function joinMarket(items, history) {
  const h = new Map((history || []).map((x) => [x.market_hash_name, x]));
  const out = [];
  for (const it of items || []) {
    const s = h.get(it.market_hash_name);
    if (!s || it.min_price == null || !it.quantity) continue;
    out.push({ id: it.market_hash_name, name: it.market_hash_name, card: it.item_page, ask: it.min_price, qty: it.quantity,
      med7: s.last_7_days?.median, vol7: s.last_7_days?.volume || 0, med30: s.last_30_days?.median, med90: s.last_90_days?.median });
  }
  return out;
}

// 今売るといくらか(値洗い用): 最安出品と直近 7 日の中央値の安い方(高い出品が残っているだけの見かけの値上がりを除く)
export const sellRef = (c) => (c.med7 != null ? Math.min(c.ask, c.med7) : c.ask);

// 仮に買う候補: よく売れていて(7 日で minVolume 件以上)、価格が minPrice〜maxPrice、
// 上昇中(7 日の中央値 ÷ 30 日の中央値が minTrend 以上、30 日 ≥ 90 日)、今の最安出品が 7 日の中央値の maxPremium 倍以下(急騰の直後は買わない)。
// 持っている品と、売ってから cooldownDays 日たっていない品は除く。上昇の強い順に slots 個まで
export function pickItems(market, held, { minVolume = 10, minPrice = 1, maxPrice = 15, minTrend = 1.05, maxPremium = 1.05, slots = 2, cooldownDays = 7, closed = [], now = Date.now() } = {}) {
  const skip = new Set(held.map((p) => p.id));
  for (const c of closed) if (c.soldAt && now - Date.parse(c.soldAt) < cooldownDays * 864e5) skip.add(c.id);
  return market
    .filter((c) => c.med7 && c.med30 && c.med90 && c.vol7 >= minVolume && c.ask >= minPrice && c.ask <= maxPrice && !skip.has(c.id))
    .map((c) => ({ ...c, price: c.ask, m: { ratio: c.med7 / c.med30 } }))
    .filter((c) => c.m.ratio >= minTrend && c.med30 >= c.med90 && c.ask <= c.med7 * maxPremium)
    .sort((a, b) => b.m.ratio - a.m.ratio)
    .slice(0, slots);
}

// ゲームの名前 → 記録のファイル名などに使う短い名前("Dota 2" → "dota-2")
export const slug = (name) => String(name).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");

// 模擬売買するゲームの一覧。config.items の各ゲーム({ name, appId, ...上書きする決まり })を、config.cs2 の決まり(既定値)に重ねる。
// items が無ければ CS2 だけ。記録は state/items-<短い名前>.json。CS2 は前の記録 state/cs2.json を引き継ぐ(legacyState)。
// enabled: false のゲーム(または cs2.enabled: false で全部)は除く
export function gameList(cfg = {}) {
  const base = cfg.cs2 || {};
  const list = Array.isArray(cfg.items) && cfg.items.length ? cfg.items : [{ name: "CS2", appId: 730 }];
  return list
    .map((g) => ({ ...base, ...g, key: slug(g.name), file: `items-${slug(g.name)}.json`, legacyState: g.legacyState ?? (g.appId === 730 ? "cs2.json" : null) }))
    .filter((g) => g.enabled !== false && g.appId);
}

// 呼ぶ間隔を gapMs 以上あける(Skinport は 5 分に 8 回まで)。sleep・clock はテスト用に差し替えられる
export function throttle(gapMs, sleep = (ms) => new Promise((ok) => setTimeout(ok, ms)), clock = Date.now) {
  let last = -Infinity;
  return async () => {
    const wait = last + gapMs - clock();
    if (wait > 0) await sleep(wait);
    last = clock();
  };
}
