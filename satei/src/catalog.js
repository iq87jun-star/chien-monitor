// お客様向けの在庫一覧(public/zaiko.html)。公開にした在庫・代理出品だけを、価格・仕入れ値・メモ・連絡先を除いて返す
// (価格はすべて DM で案内する)。画像は表紙1枚だけ: image に owner = 'cover_stock' / 'cover_consign'、owner_id = 番号で1枚
import { MAX_IMAGE_B64 } from "./stock.js";

const json = (s, d) => {
  try { return s ? JSON.parse(s) : d; } catch { return d; }
};
// 売れたものは、この日数だけ「売約済み」として残す
const SOLD_DAYS = 30;
const STOCK_STATE = { 未出品: "販売中", 出品中: "販売中", 商談中: "商談中", 売却済み: "売約済み" };
const CONSIGN_STATE = { 代理出品OK: "販売中", 出品中: "販売中", 成約: "売約済み" };
const chars = (s) => json(s, []).map((c) => ({ name: c.name, cons: c.cons, mochi: Boolean(c.mochi) }));
export const COVER_KINDS = { stock: "cover_stock", consign: "cover_consign" };

export async function listCatalog(env) {
  const since = new Date(Date.now() - SOLD_DAYS * 86400_000).toISOString();
  const [stock, consign, covers] = await Promise.all([
    env.DB.prepare("SELECT id, game, chars, assets, status, sold_at, updated_at, pub_note FROM stock WHERE pub = 1").all(),
    env.DB.prepare("SELECT id, game, chars, status, post_url, updated_at, pub_note FROM consign WHERE pub = 1").all(),
    env.DB.prepare("SELECT id, owner, owner_id FROM image WHERE owner IN ('cover_stock', 'cover_consign')").all(),
  ]);
  const cover = (kind, id) => covers.results.find((i) => i.owner === COVER_KINDS[kind] && i.owner_id === id)?.id ?? null;
  const recent = (r) => r.state !== "売約済み" || (r.at ?? "") >= since.slice(0, 10);
  const items = [
    ...stock.results.map((s) => ({ kind: "stock", no: s.id, game: s.game, chars: chars(s.chars), assets: s.assets ?? "", state: STOCK_STATE[s.status], at: s.sold_at ?? s.updated_at, note: s.pub_note ?? "", cover: cover("stock", s.id) })),
    ...consign.results.map((c) => ({ kind: "consign", no: c.id, game: c.game, chars: chars(c.chars), assets: "", state: CONSIGN_STATE[c.status], at: c.updated_at, note: c.pub_note ?? "", post_url: c.post_url ?? "", cover: cover("consign", c.id) })),
  ].filter((r) => r.state && recent(r));
  const order = { 販売中: 0, 商談中: 1, 売約済み: 2 };
  const c6 = (r) => r.chars.filter((c) => c.cons === 6).length;
  items.sort((a, b) => order[a.state] - order[b.state] || c6(b) - c6(a) || b.chars.length - a.chars.length);
  return items.map(({ at, ...r }) => r);
}

// 公開している在庫・代理出品の表紙だけ
export async function catalogImage(env, id) {
  return env.DB.prepare(
    `SELECT i.mime, i.data FROM image i WHERE i.id = ? AND (
       (i.owner = 'cover_stock' AND EXISTS (SELECT 1 FROM stock s WHERE s.id = i.owner_id AND s.pub = 1)) OR
       (i.owner = 'cover_consign' AND EXISTS (SELECT 1 FROM consign c WHERE c.id = i.owner_id AND c.pub = 1)))`,
  ).bind(id).first();
}

// 表紙を入れ替える(管理画面)。{ mime, data, w, h }。不正なら null
export function validCover(body) {
  if (!["image/jpeg", "image/png", "image/webp"].includes(body?.mime)) return null;
  if (typeof body.data !== "string" || !body.data || body.data.length > MAX_IMAGE_B64 || !/^[A-Za-z0-9+/=]+$/.test(body.data)) return null;
  const n = (v) => (Number.isInteger(v) && v > 0 && v < 20000 ? v : null);
  return { mime: body.mime, data: body.data, w: n(body.w), h: n(body.h) };
}
export async function setCover(env, kind, id, img) {
  const owner = COVER_KINDS[kind];
  const [, r] = await env.DB.batch([
    env.DB.prepare("DELETE FROM image WHERE owner = ? AND owner_id = ?").bind(owner, id),
    env.DB.prepare("INSERT INTO image (owner, owner_id, created_at, mime, w, h, data) VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id").bind(owner, id, new Date().toISOString(), img.mime, img.w, img.h, img.data),
  ]);
  return r.results[0].id;
}
export async function deleteCover(env, kind, id) {
  return (await env.DB.prepare("DELETE FROM image WHERE owner = ? AND owner_id = ?").bind(COVER_KINDS[kind], id).run()).meta.changes > 0;
}
export async function listCovers(env) {
  const { results } = await env.DB.prepare("SELECT id, owner, owner_id FROM image WHERE owner IN ('cover_stock', 'cover_consign')").all();
  return results;
}
