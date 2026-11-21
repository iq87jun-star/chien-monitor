// フォロー候補の取り込みと判定(管理画面と Worker で共通)。
// Chrome の Claude が作った表(タブ区切り・| 区切りのどちらでも)を 1 行ずつ読み、@ID・数字・一言を取り出す
export const FOLLOW_STATUSES = ["候補", "フォロー済み", "返ってきた", "返ってこない", "外した", "除外"];
export const FOLLOW_RULES = { perDay: 20, checkDays: 14 };

const num = (s) => {
  const n = Number(String(s ?? "").replace(/[,，\s]/g, ""));
  return Number.isFinite(n) && String(s ?? "").trim() !== "" ? n : null;
};

// 1 行 → {handle, following, followers, joined, note}。@ID の無い行(見出しなど)は null
export function parseRow(line) {
  const m = /@([A-Za-z0-9_]{1,15})/.exec(line);
  if (!m || /^id$/i.test(m[1])) return null; // 見出しの「@ID」
  const cells = line.split(/\t|\s*\|\s*/).map((c) => c.trim()).filter((c) => c !== "");
  const at = cells.findIndex((c) => c.includes("@" + m[1]));
  const rest = cells.slice(at + 1);
  const nums = [];
  let i = 0;
  while (i < rest.length && nums.length < 2 && num(rest[i]) !== null) nums.push(num(rest[i++]));
  const joinedCell = rest[i] && /\d{4}\s*年|\d{4}[-/]\d{1,2}/.test(rest[i]) ? rest[i++] : null;
  return { handle: m[1], following: nums[0] ?? null, followers: nums[1] ?? null, joined: joinedCell, note: rest.slice(i).join(" ").slice(0, 200) };
}
export const parseTable = (text) => {
  const seen = new Set();
  return String(text ?? "").split(/\r?\n/).map(parseRow).filter((r) => r && !seen.has(r.handle.toLowerCase()) && seen.add(r.handle.toLowerCase()));
};

// 「2026年7月」「2026-07」→ その月の 1 日
const joinedDate = (s) => {
  const m = /(\d{4})\s*[年/-]\s*(\d{1,2})/.exec(s ?? "");
  return m ? `${m[1]}-${m[2].padStart(2, "0")}-01` : null;
};
const monthsBetween = (a, b) => (Date.parse(b) - Date.parse(a)) / (30.4 * 86400_000);

// 判定。返り値 {grade: ◎○△×, kind, reason}
export function gradeRow(r, today) {
  const note = r.note ?? "";
  const j = joinedDate(r.joined);
  // 英語の名前 + 意味のない文字列(例: FinleyDaviehnq, DonnaColli15719)= 量産ボットの形
  if (/^[A-Z][a-z]{2,}[A-Z][a-z]+[a-z0-9]{3,}$/.test(r.handle) && /[a-z]{3}$|\d{4,}$/.test(r.handle) && (!j || monthsBetween(j, today) < 12))
    return { grade: "×", kind: null, reason: "量産ボットの形" };
  if (/業者|販売|石垢|引退垢|代行/.test(note)) return { grade: "×", kind: null, reason: "業者・同業" };
  if (/関係(なし|ない)|ネタ/.test(note)) return { grade: "×", kind: null, reason: "原神と関係なし" };
  if (/FF\s*\d+\s*(⬇|↓|以下)|フォロー.{0,3}(ご)?遠慮|フォロバしません|FF100\s*↑/.test(note)) return { grade: "×", kind: null, reason: "フォローお断りの記載" };
  if (j && monthsBetween(j, today) < 3) return { grade: "△", kind: null, reason: "作られて3か月以内" };
  // 「別ゲーを引退して原神を楽しむ」のように、引退したのが原神以外
  if (/(別|他の?)ゲー.{0,6}引退/.test(note) && /原神|スタレ/.test(note)) return { grade: "○", kind: "フォロバ", reason: "原神を続けている" };
  if (/完全に引退|引退済|アプリ.{0,4}(削除|消)|引退するしか|垢.{0,4}(売|手放)/.test(note)) return { grade: "◎", kind: "売りたい", reason: "引退した・売りたい" };
  if (/引退/.test(note)) {
    if (/迷|悩|しようかな|しようかしら|かも|再開/.test(note)) return { grade: "△", kind: "売りたい", reason: "引退を迷い中" };
    return { grade: "○", kind: "売りたい", reason: "引退の投稿" };
  }
  if (/フォロバ\s*100|無言フォロー|相互|復帰|再開|楽しむ|現役/.test(note)) return { grade: "○", kind: "フォロバ", reason: "フォローバック向き" };
  // フォローとフォロワーが極端に違う人は返ってきにくい
  if (r.following != null && r.followers != null && r.followers > 1000 && r.followers > r.following * 3) return { grade: "△", kind: null, reason: "フォロワーが極端に多い" };
  return { grade: "△", kind: null, reason: "判断材料なし" };
}

const RANK = { "◎": 0, "○": 1, "△": 2, "×": 3 };
// 取り込み: 判定して ○ 以上を ◎→○ の順に perDay 人まで。既に入っている人は外す
export function pickForToday(rows, today, known = new Set(), r = FOLLOW_RULES) {
  const graded = rows.map((x) => ({ ...x, ...gradeRow(x, today) }));
  const fresh = graded.filter((x) => !known.has(x.handle.toLowerCase()));
  const take = fresh.filter((x) => RANK[x.grade] <= 1).sort((a, b) => RANK[a.grade] - RANK[b.grade]).slice(0, r.perDay);
  return { take, skipped: graded.filter((x) => !take.includes(x)) };
}

// フォローしてから checkDays 日たった人(まだ確認していない)
export const dueForCheck = (list, today, r = FOLLOW_RULES) =>
  list.filter((f) => f.status === "フォロー済み" && f.followed_on && (Date.parse(today) - Date.parse(f.followed_on)) / 86400_000 >= r.checkDays);
