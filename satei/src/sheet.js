// 引き継ぎ情報フォーム。項目は public/lib/sheet.js と共通
//   管理画面(合言葉): リンクを作る・回答を見る・消す
//   売主(リンクの token だけ): 何を書くフォームかを見る・1回だけ記入する(回答は返さない)
import { validAnswers, MAX_RECEIPTS } from "../public/lib/sheet.js";
import { MAX_IMAGE_B64 } from "./stock.js";

const now = () => new Date().toISOString();
const clean = (s, max) => (typeof s === "string" ? s.trim().slice(0, max) : "");
// 推測できない長さのランダムな文字列(リンクに入れる)
const newToken = () => [...crypto.getRandomValues(new Uint8Array(16))].map((b) => b.toString(16).padStart(2, "0")).join("");

export function validSheet(body, games) {
  if (!body || typeof body !== "object") return null;
  const consign_id = body.consign_id == null || body.consign_id === "" ? null : Number(body.consign_id);
  if (consign_id !== null && !(Number.isInteger(consign_id) && consign_id > 0)) return null;
  const game = body.game ? (games.includes(body.game) ? body.game : undefined) : null;
  if (game === undefined) return null;
  return { consign_id, game, label: clean(body.label, 60) || null };
}

export async function createSheet(env, row) {
  const token = newToken();
  const r = await env.DB.prepare("INSERT INTO sheet (token, consign_id, label, game, created_at) VALUES (?, ?, ?, ?, ?) RETURNING id")
    .bind(token, row.consign_id, row.label, row.game, now())
    .first();
  return { id: r.id, token };
}

export async function listSheets(env) {
  const { results } = await env.DB.prepare("SELECT id, token, consign_id, label, game, created_at, submitted_at FROM sheet ORDER BY id DESC").all();
  return results;
}

export async function getSheet(env, id) {
  const s = await env.DB.prepare("SELECT * FROM sheet WHERE id = ?").bind(id).first();
  if (!s) return null;
  const { results } = await env.DB.prepare("SELECT id FROM image WHERE owner = 'sheet' AND owner_id = ? ORDER BY id").bind(id).all();
  return { ...s, data: s.data ? JSON.parse(s.data) : null, images: results.map((r) => r.id) };
}

export async function deleteSheet(env, id) {
  const [, r] = await env.DB.batch([
    env.DB.prepare("DELETE FROM image WHERE owner = 'sheet' AND owner_id = ?").bind(id),
    env.DB.prepare("DELETE FROM sheet WHERE id = ?").bind(id),
  ]);
  return r.meta.changes > 0;
}

// 売主の画面に出す分だけ(回答は返さない)
export async function formInfo(env, token) {
  return env.DB.prepare("SELECT id, label, game, submitted_at FROM sheet WHERE token = ?").bind(token).first();
}

// 売主の記入。{ answers, receipts: [{ mime, data, w, h }] }。不正なら null
export function validSubmit(body) {
  const answers = validAnswers(body?.answers);
  if (!answers) return null;
  const list = Array.isArray(body.receipts) ? body.receipts : [];
  if (list.length > MAX_RECEIPTS) return null;
  const receipts = [];
  for (const im of list) {
    if (!["image/jpeg", "image/png", "image/webp"].includes(im?.mime)) return null;
    if (typeof im.data !== "string" || !im.data || im.data.length > MAX_IMAGE_B64 || !/^[A-Za-z0-9+/=]+$/.test(im.data)) return null;
    const n = (v) => (Number.isInteger(v) && v > 0 && v < 20000 ? v : null);
    receipts.push({ mime: im.mime, data: im.data, w: n(im.w), h: n(im.h) });
  }
  return { answers, receipts };
}

// 1回だけ記入できる。記入済み・リンク違いは false
export async function submitSheet(env, token, { answers, receipts }) {
  const s = await formInfo(env, token);
  if (!s || s.submitted_at) return false;
  const at = now();
  const r = await env.DB.prepare("UPDATE sheet SET data = ?, submitted_at = ? WHERE id = ? AND submitted_at IS NULL").bind(JSON.stringify(answers), at, s.id).run();
  if (r.meta.changes === 0) return false;
  for (const im of receipts) {
    await env.DB.prepare("INSERT INTO image (owner, owner_id, created_at, mime, w, h, data) VALUES ('sheet', ?, ?, ?, ?, ?, ?)").bind(s.id, at, im.mime, im.w, im.h, im.data).run();
  }
  return true;
}
