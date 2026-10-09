// 代理出品の管理。買取の値が付けられない人のアカウントを、メルルが X で紹介して買い手を探す。
// 1件ごとに管理番号(No.)を振り、DM の定型文とユーザー名に付けて、やり取りを番号でたどれるようにする。
//
//   consign   … 対象者(管理番号 = id)
//   templates … DM の定型文(集計画面で編集できる)
//   dm_log    … 定型文を使って DM を開いた記録

export { STATUSES, fillTemplate } from "../public/lib/dm.js";
import { STATUSES } from "../public/lib/dm.js";

// 定型文の初期値。{番号} などは送る時に置き換える(fillTemplate)
export const DEFAULT_TEMPLATES = [
  {
    key: "wait",
    title: "検討時間のお願い",
    body: `【No.{番号}】{名前}様
ご相談いただきありがとうございます🌸

アカウントの内容を拝見しました。
在庫や買取の状況を確認したうえでお返事したいため、恐れ入りますが {期限} まで少しお時間をいただけますでしょうか。
確認でき次第、こちらからご連絡いたします🙇‍♀️

※今後のやり取りでは「No.{番号}」とお書き添えください`,
  },
  {
    key: "propose",
    title: "代理出品のご提案",
    body: `【No.{番号}】{名前}様
お待たせいたしました。大変申し訳ないのですが、今回のアカウントは私の方での直接買取を見送らせていただくことになりました。

その代わりに、私のX(@Meruru_Genshin)で「No.{番号}」としてアカウントを紹介し、購入希望の方をお探しするお手伝いをさせていただけないでしょうか。

▼お願いしたいこと
・UIDを隠したキャラ一覧などのスクショ
・ご希望の金額

※買い手がすぐ見つかるとは限らない点だけ、ご了承ください。
もちろん今回は見送りでも大丈夫です。`,
  },
  {
    key: "posted",
    title: "出品しました(リンクとリアクションのお願い)",
    body: `【No.{番号}】{名前}様
アカウントの紹介を投稿しました✨
{投稿URL}

▼お願い
・投稿への「いいね」「リポスト」で応援いただけると、買い手が見つかりやすくなります
・確認できたら、このDMに❤️などのリアクションをお願いします

購入希望の方からご連絡があり次第、お知らせします。`,
  },
  {
    key: "sold",
    title: "成約しました",
    body: `【No.{番号}】{名前}様
購入希望の方が見つかりました🎉

お取引の進め方をご案内しますので、このDMにご返信ください。
最後まで丁寧に進めますので、よろしくお願いいたします🌸`,
  },
  {
    key: "decline",
    title: "今回は見送り",
    body: `【No.{番号}】{名前}様
ご相談いただきありがとうございました。
今回は見送りとさせていただきますが、また機会がありましたらお気軽にご相談ください🌸`,
  },
];

const clean = (s, max) => (typeof s === "string" ? s.trim().slice(0, max) : "");
export const normHandle = (h) => {
  // 全角の「＠」や英数字も読めるように半角にそろえる
  const s = clean(h, 20).normalize("NFKC").replace(/^@/, "");
  return /^[A-Za-z0-9_]{1,15}$/.test(s) ? s : null;
};
const yen = (v) => (Number.isInteger(v) && v >= 0 && v < 100_000_000 ? v : null);
const date = (v) => (typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v) ? v : null);

// 査定ページからの相談(公開)。ユーザー名・希望額は任意
export function validLead(body, games) {
  if (!body || !games.includes(body.game)) return null;
  // @ID として読めない入力(「じゃるぎ」のような表示名など)は断らず、呼び名として受け取る
  const handle = body.handle ? normHandle(body.handle) : null;
  const name = !handle && body.handle ? clean(String(body.handle), 30).replace(/^@/, "") || null : null;
  const chars = (Array.isArray(body.chars) ? body.chars : [])
    .slice(0, 60)
    .map((c) => ({ name: clean(c?.name, 30), cons: Math.min(6, Math.max(0, Number(c?.cons) | 0)), mochi: Boolean(c?.mochi) }))
    .filter((c) => c.name);
  return { game: body.game, handle, name, chars, low: yen(body.low), high: yen(body.high), wish: yen(body.wish), sid: clean(body.sid, 40) };
}

// 集計画面からの更新。渡された項目だけ変える
export function validPatch(body) {
  const out = {};
  if (!body || typeof body !== "object") return out;
  if ("handle" in body) out.handle = body.handle ? normHandle(body.handle) : null;
  if ("name" in body) out.name = clean(body.name ?? "", 30) || null;
  if ("status" in body && STATUSES.includes(body.status)) out.status = body.status;
  if ("wish" in body) out.wish = body.wish === null || body.wish === "" ? null : yen(Number(body.wish));
  if ("next_at" in body) out.next_at = body.next_at ? date(body.next_at) : null;
  if ("memo" in body) out.memo = clean(body.memo ?? "", 2000);
  if ("post_url" in body) out.post_url = /^https:\/\/(x|twitter)\.com\//.test(body.post_url ?? "") ? clean(body.post_url, 300) : null;
  return out;
}

const parse = (r) => ({ ...r, chars: JSON.parse(r.chars ?? "[]") });

// 同じ人がもう一度送った相談は、新しい番号を作らず前の番号にまとめる。
// 同じゲームで、同じ画面(sid)か同じユーザー名から、この日数のうちに来た進行中の相談を同じ人とみなす
const MERGE_DAYS = 3;

async function findSame(env, lead) {
  if (!lead.sid && !lead.handle) return null;
  const since = new Date(Date.now() - MERGE_DAYS * 86400_000).toISOString();
  return env.DB.prepare(
    `SELECT id FROM consign WHERE game = ? AND created_at >= ? AND status NOT IN ('成約', '見送り', '重複')
       AND ((sid <> '' AND sid = ?) OR (handle IS NOT NULL AND handle = ?))
     ORDER BY id LIMIT 1`,
  )
    .bind(lead.game, since, lead.sid ?? "", lead.handle ?? "")
    .first();
}

// 返り値: { id, merged }(merged = 前の番号にまとめた)
export async function createLead(env, lead, source = "tool") {
  const now = new Date().toISOString();
  const same = source === "tool" ? await findSame(env, lead) : null;
  if (same) {
    // キャラと査定額は新しい方にする。ユーザー名・希望額は、新しく書かれた時だけ上書きする
    await env.DB.prepare(
      "UPDATE consign SET updated_at = ?, chars = ?, low = ?, high = ?, handle = COALESCE(?, handle), name = COALESCE(?, name), wish = COALESCE(?, wish) WHERE id = ?",
    )
      .bind(now, JSON.stringify(lead.chars), lead.low, lead.high, lead.handle, lead.name ?? null, lead.wish, same.id)
      .run();
    return { id: same.id, merged: true };
  }
  const r = await env.DB.prepare(
    "INSERT INTO consign (created_at, updated_at, handle, name, game, chars, low, high, wish, status, sid, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '新規', ?, ?) RETURNING id",
  )
    .bind(now, now, lead.handle, lead.name ?? null, lead.game, JSON.stringify(lead.chars), lead.low, lead.high, lead.wish, lead.sid ?? "", source)
    .first();
  return { id: r.id, merged: false };
}

export async function listConsign(env) {
  const { results } = await env.DB.prepare(
    `SELECT c.*, (SELECT MAX(at) FROM dm_log WHERE consign_id = c.id) AS last_dm
     FROM consign c ORDER BY CASE c.status WHEN '成約' THEN 2 WHEN '見送り' THEN 3 WHEN '重複' THEN 4 ELSE 1 END, c.id DESC LIMIT 500`,
  ).all();
  return results.map(parse);
}

export async function updateConsign(env, id, patch) {
  const keys = Object.keys(patch);
  if (!keys.length) return false;
  const r = await env.DB.prepare(`UPDATE consign SET ${keys.map((k) => `${k} = ?`).join(", ")}, updated_at = ? WHERE id = ?`)
    .bind(...keys.map((k) => patch[k]), new Date().toISOString(), id)
    .run();
  return r.meta.changes > 0;
}

export async function logDm(env, id, key) {
  await env.DB.prepare("INSERT INTO dm_log (consign_id, template, at) VALUES (?, ?, ?)").bind(id, clean(key, 40), new Date().toISOString()).run();
}

export async function getTemplates(env) {
  const { results } = await env.DB.prepare("SELECT key, title, body FROM templates ORDER BY sort").all();
  return results.length ? results : DEFAULT_TEMPLATES;
}

export async function saveTemplates(env, list) {
  const items = (Array.isArray(list) ? list : [])
    .slice(0, 20)
    .map((t, i) => ({ key: clean(t?.key, 40) || `t${i}`, title: clean(t?.title, 60), body: clean(t?.body, 3000), sort: i }))
    .filter((t) => t.title && t.body);
  if (!items.length) return 0;
  await env.DB.batch([
    env.DB.prepare("DELETE FROM templates"),
    ...items.map((t) => env.DB.prepare("INSERT INTO templates (key, title, body, sort) VALUES (?, ?, ?, ?)").bind(t.key, t.title, t.body, t.sort)),
  ]);
  return items.length;
}
