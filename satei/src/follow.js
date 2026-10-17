// フォロー候補の保存(判定は public/lib/follow.js)
import { FOLLOW_STATUSES, parseTable, pickForToday } from "../public/lib/follow.js";

const jstToday = () => new Date(Date.now() + 9 * 3600_000).toISOString().slice(0, 10);

export async function listFollow(env) {
  const { results } = await env.DB.prepare("SELECT * FROM follow ORDER BY found_on DESC, id").all();
  return results;
}

// 表の文字を取り込み、○ 以上を 1 日 20 人まで候補にする
export async function importFollow(env, text) {
  const rows = parseTable(String(text ?? "").slice(0, 50_000));
  const { results } = await env.DB.prepare("SELECT handle FROM follow").all();
  const known = new Set(results.map((r) => r.handle.toLowerCase()));
  const today = jstToday();
  const { take, skipped } = pickForToday(rows, today, known);
  for (const x of take) {
    await env.DB.prepare(
      "INSERT OR IGNORE INTO follow (handle, following, followers, joined, note, grade, kind, reason, status, found_on) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '候補', ?)",
    )
      .bind(x.handle, x.following, x.followers, x.joined, x.note, x.grade, x.kind, x.reason, today)
      .run();
  }
  return { added: take.map((x) => x.handle), skipped: skipped.map((x) => ({ handle: x.handle, grade: x.grade, reason: known.has(x.handle.toLowerCase()) ? "取り込み済み" : x.reason })) };
}

// 状態を変える。フォロー済み → followed_on、返ってきた/返ってこない → checked_on に今日を入れる
export async function setFollowStatus(env, id, status) {
  if (!FOLLOW_STATUSES.includes(status)) return false;
  const today = jstToday();
  const extra = status === "フォロー済み" ? ", followed_on = ?" : ["返ってきた", "返ってこない"].includes(status) ? ", checked_on = ?" : "";
  const r = await env.DB.prepare(`UPDATE follow SET status = ?${extra} WHERE id = ?`)
    .bind(...[status, ...(extra ? [today] : []), id])
    .run();
  return r.meta.changes > 0;
}
