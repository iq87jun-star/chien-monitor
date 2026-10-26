// お客様向けの在庫一覧(public/zaiko.html)。公開にした在庫・代理出品だけを、仕入れ値・メモ・連絡先を除いて返す
const json = (s, d) => {
  try { return s ? JSON.parse(s) : d; } catch { return d; }
};
// 売れたものは、この日数だけ「売約済み」として残す
const SOLD_DAYS = 30;
const STOCK_STATE = { 未出品: "販売中", 出品中: "販売中", 商談中: "商談中", 売却済み: "売約済み" };
const CONSIGN_STATE = { 代理出品OK: "販売中", 出品中: "販売中", 成約: "売約済み" };
const chars = (s) => json(s, []).map((c) => ({ name: c.name, cons: c.cons, mochi: Boolean(c.mochi) }));

export async function listCatalog(env) {
  const since = new Date(Date.now() - SOLD_DAYS * 86400_000).toISOString();
  const [stock, consign, images] = await Promise.all([
    env.DB.prepare("SELECT id, game, chars, assets, status, price, sold_at, updated_at, pub_images, pub_note FROM stock WHERE pub = 1").all(),
    env.DB.prepare("SELECT id, game, chars, status, pub_price, post_url, updated_at, pub_note FROM consign WHERE pub = 1").all(),
    env.DB.prepare("SELECT i.id, i.owner_id FROM image i JOIN stock s ON s.id = i.owner_id WHERE i.owner = 'stock' AND s.pub = 1 AND s.pub_images = 1 ORDER BY i.id").all(),
  ]);
  const imgs = (id) => images.results.filter((i) => i.owner_id === id).map((i) => i.id);
  const recent = (r) => r.state !== "売約済み" || (r.at ?? "") >= since.slice(0, 10);
  const items = [
    ...stock.results.map((s) => ({ kind: "stock", no: s.id, game: s.game, chars: chars(s.chars), assets: s.assets ?? "", price: s.price, state: STOCK_STATE[s.status], at: s.sold_at ?? s.updated_at, note: s.pub_note ?? "", images: s.pub_images ? imgs(s.id) : [] })),
    ...consign.results.map((c) => ({ kind: "consign", no: c.id, game: c.game, chars: chars(c.chars), assets: "", price: c.pub_price, state: CONSIGN_STATE[c.status], at: c.updated_at, note: c.pub_note ?? "", post_url: c.post_url ?? "", images: [] })),
  ].filter((r) => r.state && recent(r));
  const order = { 販売中: 0, 商談中: 1, 売約済み: 2 };
  items.sort((a, b) => order[a.state] - order[b.state] || (b.price ?? 0) - (a.price ?? 0));
  return items.map(({ at, ...r }) => r);
}

// 公開した在庫の、公開してよい画像だけ
export async function catalogImage(env, id) {
  return env.DB.prepare("SELECT i.mime, i.data FROM image i JOIN stock s ON s.id = i.owner_id WHERE i.id = ? AND i.owner = 'stock' AND s.pub = 1 AND s.pub_images = 1").bind(id).first();
}
