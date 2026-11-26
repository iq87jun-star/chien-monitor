// 代理出品の売り手ページとチャット。売り手はリンクの token だけで、自分のアカウントの紹介状況を見られる(public/dairi.html)
//   見せるのは: 呼び名・ゲーム・★5の数と完凸・進み具合・希望額・公開価格・在庫一覧への掲載・紹介ポスト・お問い合わせ数・メッセージ
//   見せないのは: メモ・査定額・連絡先の細かい情報・引き渡しのチェック・画面の sid
import { MAX_MSG, MAX_MSGS_PER_DAY } from "./portal.js";

const now = () => new Date().toISOString();
const newToken = () => [...crypto.getRandomValues(new Uint8Array(16))].map((b) => b.toString(16).padStart(2, "0")).join("");
// 進み具合: 0 ご相談 → 1 紹介の準備 → 2 紹介中 → 3 成約。見送り・重複は止まっている(-1)
export const STEP = { 新規: 0, 検討中: 0, 代理出品OK: 1, 出品中: 2, 成約: 3, 見送り: -1, 重複: -1 };
const json = (s, d) => {
  try { return s ? JSON.parse(s) : d; } catch { return d; }
};
const msgs = async (env, id) =>
  (await env.DB.prepare("SELECT id, from_me, body, at FROM consign_msg WHERE consign_id = ? ORDER BY id DESC LIMIT 200").bind(id).all()).results.reverse();

// 管理画面: リンクを作る(あれば同じものを返す)
export async function sellerToken(env, id) {
  const c = await env.DB.prepare("SELECT portal FROM consign WHERE id = ?").bind(id).first();
  if (!c) return null;
  if (c.portal) return c.portal;
  const token = newToken();
  await env.DB.prepare("UPDATE consign SET portal = ? WHERE id = ?").bind(token, id).run();
  return token;
}

// 売り手ページの中身
export async function sellerView(env, token) {
  const c = await env.DB.prepare("SELECT id, name, handle, game, chars, status, wish, pub, pub_price, post_url, asks, updated_at FROM consign WHERE portal = ?").bind(token).first();
  if (!c) return null;
  const chars = json(c.chars, []);
  return {
    no: c.id, name: c.name || (c.handle ? `@${c.handle}` : ""), game: c.game,
    star5: chars.length, c6: chars.filter((x) => x.cons === 6).map((x) => x.name),
    status: c.status, step: STEP[c.status] ?? 0, wish: c.wish, pub: Boolean(c.pub), pub_price: c.pub_price,
    post_url: c.post_url ?? "", asks: c.asks ?? 0, updated_at: c.updated_at, msgs: await msgs(env, c.id),
  };
}

const cleanBody = (v) => (typeof v === "string" ? v.trim().slice(0, MAX_MSG) : "");

// 売り手からのメッセージ。送りすぎは断る
export async function sellerPost(env, token, body) {
  const text = cleanBody(body);
  if (!text) return { ok: false, error: "メッセージを入力してください" };
  const c = await env.DB.prepare("SELECT id FROM consign WHERE portal = ?").bind(token).first();
  if (!c) return { ok: false, error: "リンクが正しくありません" };
  const since = new Date(Date.now() - 86400_000).toISOString();
  const n = await env.DB.prepare("SELECT COUNT(*) AS n FROM consign_msg WHERE consign_id = ? AND from_me = 0 AND at >= ?").bind(c.id, since).first();
  if ((n?.n ?? 0) >= MAX_MSGS_PER_DAY) return { ok: false, error: "今日はこれ以上送れません。X の DM でご連絡ください" };
  await env.DB.prepare("INSERT INTO consign_msg (consign_id, from_me, body, at) VALUES (?, 0, ?, ?)").bind(c.id, text, now()).run();
  return { ok: true };
}

// 管理画面: メッセージを見る(売り手からのものを既読にする)・送る・未読の数
export async function sellerAdminMsgs(env, id) {
  await env.DB.prepare("UPDATE consign_msg SET seen = 1 WHERE consign_id = ? AND from_me = 0 AND seen = 0").bind(id).run();
  return msgs(env, id);
}
export async function sellerAdminPost(env, id, body) {
  const text = cleanBody(body);
  if (!text) return false;
  const c = await env.DB.prepare("SELECT id FROM consign WHERE id = ?").bind(id).first();
  if (!c) return false;
  await env.DB.prepare("INSERT INTO consign_msg (consign_id, from_me, body, at, seen) VALUES (?, 1, ?, ?, 1)").bind(id, text, now()).run();
  return true;
}
export async function sellerUnread(env) {
  const { results } = await env.DB.prepare("SELECT consign_id, COUNT(*) AS n FROM consign_msg WHERE from_me = 0 AND seen = 0 GROUP BY consign_id").all();
  return Object.fromEntries(results.map((r) => [r.consign_id, r.n]));
}
