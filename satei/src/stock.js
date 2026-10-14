// 在庫(メルルが持っているアカウント)と分割払いの管理。計算は public/lib/stock.js と共通
import { STOCK_STATUSES, SPLIT_STATUSES, WANT_STATUSES, SITES, HANDOVER } from "../public/lib/stock.js";

const clean = (s, max) => (typeof s === "string" ? s.trim().slice(0, max) : "");
const yen = (v) => (v === "" || v == null ? null : Number.isInteger(Number(v)) && Number(v) >= 0 && Number(v) < 100_000_000 ? Number(v) : undefined);
const date = (v) => (!v ? null : typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v) ? v : undefined);
const chars = (list) =>
  (Array.isArray(list) ? list : [])
    .slice(0, 80)
    .map((c) => ({ name: clean(c?.name, 30), cons: Math.min(6, Math.max(0, Number(c?.cons) | 0)), mochi: Boolean(c?.mochi) }))
    .filter((c) => c.name);

// 渡された項目だけを検査して返す。不正な値があれば null
function pick(body, spec) {
  if (!body || typeof body !== "object") return null;
  const out = {};
  for (const [k, f] of Object.entries(spec)) {
    if (!(k in body)) continue;
    const v = f(body[k]);
    if (v === undefined) return null;
    out[k] = v;
  }
  return out;
}
const text = (max) => (v) => clean(v ?? "", max) || null;
const oneOf = (list) => (v) => (list.includes(v) ? v : undefined);

export function validStock(body, games) {
  return pick(body, {
    game: oneOf(games),
    chars: (v) => JSON.stringify(chars(v)),
    assets: text(500),
    cost: yen,
    source: text(60),
    bought_at: date,
    status: oneOf(STOCK_STATUSES),
    price: yen,
    floor: yen,
    price_at: date,
    listings: (v) =>
      JSON.stringify(
        (Array.isArray(v) ? v : [])
          .slice(0, 10)
          .map((l) => ({ site: SITES.includes(l?.site) ? l.site : "その他", url: /^https:\/\//.test(l?.url ?? "") ? clean(l.url, 300) : "", checked_on: date(l?.checked_on) ?? null })),
      ),
    sold_price: yen,
    sold_at: date,
    memo: text(2000),
  });
}

export function validSplit(body, games) {
  return pick(body, {
    game: oneOf(games),
    chars: (v) => JSON.stringify(chars(v)),
    assets: text(500),
    buyer: (v) => clean(v ?? "", 40) || undefined,
    contact: text(60),
    middle: text(60),
    total: (v) => yen(v) ?? undefined,
    due_day: (v) => (v === "" || v == null ? null : Number(v) >= 1 && Number(v) <= 31 ? Number(v) : undefined),
    status: oneOf(SPLIT_STATUSES),
    handover: (v) => JSON.stringify(Object.fromEntries(Object.keys(HANDOVER).map((k) => [k, Boolean(v?.[k])]))),
    memo: text(2000),
  });
}

export function validPay(body) {
  return pick(body, { due_on: (v) => date(v) ?? undefined, amount: (v) => yen(v) ?? undefined, paid_on: date, memo: text(200) });
}

const now = () => new Date().toISOString();
const json = (s, d) => {
  try {
    return JSON.parse(s ?? "") ?? d;
  } catch {
    return d;
  }
};

async function insert(env, table, row) {
  const keys = Object.keys(row);
  const r = await env.DB.prepare(`INSERT INTO ${table} (${keys.join(", ")}) VALUES (${keys.map(() => "?").join(", ")}) RETURNING id`)
    .bind(...keys.map((k) => row[k]))
    .first();
  return r.id;
}
async function update(env, table, id, patch, stamp = true) {
  const keys = Object.keys(patch);
  if (!keys.length) return false;
  const sets = keys.map((k) => `${k} = ?`).concat(stamp ? ["updated_at = ?"] : []);
  const r = await env.DB.prepare(`UPDATE ${table} SET ${sets.join(", ")} WHERE id = ?`)
    .bind(...keys.map((k) => patch[k]), ...(stamp ? [now()] : []), id)
    .run();
  return r.meta.changes > 0;
}

export const createStock = (env, row) => insert(env, "stock", { status: "未出品", ...row, created_at: now(), updated_at: now() });
export const updateStock = (env, id, patch) => update(env, "stock", id, patch);

export async function listStock(env) {
  const { results } = await env.DB.prepare("SELECT * FROM stock ORDER BY CASE status WHEN '売却済み' THEN 2 ELSE 1 END, id").all();
  return results.map((r) => ({ ...r, chars: json(r.chars, []), listings: json(r.listings, []) }));
}

// pays: [{due_on, amount, paid_on?}](分割の予定。作る時にまとめて入れる)
export async function createSplit(env, row, pays = []) {
  const id = await insert(env, "split", { status: "支払い中", ...row, created_at: now(), updated_at: now() });
  for (const p of pays) await insert(env, "split_pay", { ...p, split_id: id });
  return id;
}
export const updateSplit = (env, id, patch) => update(env, "split", id, patch);
export const addPay = (env, splitId, p) => insert(env, "split_pay", { ...p, split_id: splitId });
export const updatePay = (env, id, patch) => update(env, "split_pay", id, patch, false);
export async function deletePay(env, id) {
  return (await env.DB.prepare("DELETE FROM split_pay WHERE id = ?").bind(id).run()).meta.changes > 0;
}

export async function listSplit(env) {
  const [{ results: splits }, { results: pays }] = await env.DB.batch([
    env.DB.prepare("SELECT * FROM split ORDER BY CASE status WHEN '支払い中' THEN 1 WHEN '完済' THEN 0 ELSE 2 END, id"),
    env.DB.prepare("SELECT * FROM split_pay ORDER BY due_on, id"),
  ]);
  return splits.map((s) => ({ ...s, chars: json(s.chars, []), handover: json(s.handover, {}), pays: pays.filter((p) => p.split_id === s.id) }));
}

// ── 画像 ──
export const MAX_IMAGE_B64 = 1_400_000; // D1 の1つの値の上限(2MB)より小さく
export const MAX_IMAGES = 30; // 1件あたり
const MIMES = ["image/jpeg", "image/png", "image/webp"];

export function validImage(body) {
  if (!body || !["stock", "split"].includes(body.owner) || !Number.isInteger(body.owner_id) || !MIMES.includes(body.mime)) return null;
  if (typeof body.data !== "string" || !body.data || body.data.length > MAX_IMAGE_B64 || !/^[A-Za-z0-9+/=]+$/.test(body.data)) return null;
  const n = (v) => (Number.isInteger(v) && v > 0 && v < 20000 ? v : null);
  return { owner: body.owner, owner_id: body.owner_id, mime: body.mime, data: body.data, w: n(body.w), h: n(body.h) };
}

export async function addImage(env, img) {
  const r = await env.DB.prepare("SELECT COUNT(*) AS n FROM image WHERE owner = ? AND owner_id = ?").bind(img.owner, img.owner_id).first();
  if ((r?.n ?? 0) >= MAX_IMAGES) return null;
  return insert(env, "image", { ...img, created_at: now() });
}
export async function listImages(env) {
  const { results } = await env.DB.prepare("SELECT id, owner, owner_id, w, h, created_at FROM image ORDER BY id").all();
  return results;
}
export const getImage = (env, id) => env.DB.prepare("SELECT mime, data FROM image WHERE id = ?").bind(id).first();
// 黒塗りした画像で上書きする
export async function replaceImage(env, id, { mime, data, w, h }) {
  const r = await env.DB.prepare("UPDATE image SET mime = ?, data = ?, w = ?, h = ? WHERE id = ?").bind(mime, data, w, h, id).run();
  return r.meta.changes > 0;
}
export async function deleteImage(env, id) {
  return (await env.DB.prepare("DELETE FROM image WHERE id = ?").bind(id).run()).meta.changes > 0;
}

// ── 購入希望 ──
export function validWant(body, games) {
  return pick(body, {
    name: (v) => clean(v ?? "", 40) || undefined,
    contact: text(60),
    game: oneOf(games),
    wants: (v) => JSON.stringify(chars(v).map(({ name, cons }) => ({ name, cons }))),
    budget: yen,
    split: (v) => (v ? 1 : 0),
    status: oneOf(WANT_STATUSES),
    proposed: text(200),
    next_at: date,
    memo: text(2000),
  });
}
export const createWant = (env, row) => insert(env, "want", { status: "希望中", ...row, created_at: now(), updated_at: now() });
export const updateWant = (env, id, patch) => update(env, "want", id, patch);
export async function listWants(env) {
  const { results } = await env.DB.prepare("SELECT * FROM want ORDER BY CASE status WHEN '成約' THEN 2 WHEN '見送り' THEN 3 ELSE 1 END, id DESC").all();
  return results.map((r) => ({ ...r, wants: json(r.wants, []), split: Boolean(r.split) }));
}
