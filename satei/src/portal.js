// 分割払いのお客様ページとチャット。お客様はリンクの token だけで自分の分割を見られる(public/shiharai.html)
//   見せるのは: 呼び名・ゲーム・総額・支払い済み・残り・予定(日付・金額・入金済みか)・メッセージ
//   見せないのは: 連絡先・仲介・メモ・予定のメモ・引き渡しのチェック
import { splitState } from "../public/lib/stock.js";

const now = () => new Date().toISOString();
const newToken = () => [...crypto.getRandomValues(new Uint8Array(16))].map((b) => b.toString(16).padStart(2, "0")).join("");
export const MAX_MSG = 1000; // 1通の文字数
export const MAX_MSGS_PER_DAY = 40; // お客様が1日に送れる数
const today = () => new Date(Date.now() + 9 * 3600_000).toISOString().slice(0, 10);

const msgs = async (env, splitId) =>
  (await env.DB.prepare("SELECT id, from_me, body, at FROM split_msg WHERE split_id = ? ORDER BY id DESC LIMIT 200").bind(splitId).all()).results.reverse();

// 管理画面: リンクを作る(あれば同じものを返す)
export async function portalToken(env, splitId) {
  const s = await env.DB.prepare("SELECT portal FROM split WHERE id = ?").bind(splitId).first();
  if (!s) return null;
  if (s.portal) return s.portal;
  const token = newToken();
  await env.DB.prepare("UPDATE split SET portal = ? WHERE id = ?").bind(token, splitId).run();
  return token;
}

// お客様ページの中身
export async function portalView(env, token) {
  const s = await env.DB.prepare("SELECT id, buyer, game, total, due_day, status FROM split WHERE portal = ?").bind(token).first();
  if (!s) return null;
  const { results: pays } = await env.DB.prepare("SELECT due_on, amount, paid_on FROM split_pay WHERE split_id = ? ORDER BY due_on, id").bind(s.id).all();
  const st = splitState(s, pays, today());
  return {
    buyer: s.buyer, game: s.game, total: s.total, due_day: s.due_day, status: s.status,
    paid: st.paid, remaining: st.remaining, count: st.count, next: st.next ? { due_on: st.next.due_on, amount: st.next.amount } : null,
    late: st.late, pays, msgs: await msgs(env, s.id), today: today(),
  };
}

const cleanBody = (v) => (typeof v === "string" ? v.trim().slice(0, MAX_MSG) : "");

// お客様からのメッセージ。送りすぎは false
export async function portalPost(env, token, body) {
  const text = cleanBody(body);
  if (!text) return { ok: false, error: "メッセージを入力してください" };
  const s = await env.DB.prepare("SELECT id FROM split WHERE portal = ?").bind(token).first();
  if (!s) return { ok: false, error: "リンクが正しくありません" };
  const since = new Date(Date.now() - 86400_000).toISOString();
  const n = await env.DB.prepare("SELECT COUNT(*) AS n FROM split_msg WHERE split_id = ? AND from_me = 0 AND at >= ?").bind(s.id, since).first();
  if ((n?.n ?? 0) >= MAX_MSGS_PER_DAY) return { ok: false, error: "今日はこれ以上送れません。X の DM でご連絡ください" };
  await env.DB.prepare("INSERT INTO split_msg (split_id, from_me, body, at) VALUES (?, 0, ?, ?)").bind(s.id, text, now()).run();
  return { ok: true };
}

// 管理画面: メッセージを見る(お客様からのものを既読にする)・送る
export async function adminMsgs(env, splitId) {
  await env.DB.prepare("UPDATE split_msg SET seen = 1 WHERE split_id = ? AND from_me = 0 AND seen = 0").bind(splitId).run();
  return msgs(env, splitId);
}
export async function adminPost(env, splitId, body) {
  const text = cleanBody(body);
  if (!text) return false;
  const s = await env.DB.prepare("SELECT id FROM split WHERE id = ?").bind(splitId).first();
  if (!s) return false;
  await env.DB.prepare("INSERT INTO split_msg (split_id, from_me, body, at, seen) VALUES (?, 1, ?, ?, 1)").bind(splitId, text, now()).run();
  return true;
}
// まだ読んでいないお客様からのメッセージの数 { split_id: n }
export async function unreadCounts(env) {
  const { results } = await env.DB.prepare("SELECT split_id, COUNT(*) AS n FROM split_msg WHERE from_me = 0 AND seen = 0 GROUP BY split_id").all();
  return Object.fromEntries(results.map((r) => [r.split_id, r.n]));
}
