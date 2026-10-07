// 査定ツールの利用記録。個人を特定できる情報(画像・IP・UID)は残さない。
//   kind: read(AIで読み取った)/ estimate(買取額を出した)/ dm(「この金額で売りたい」を押した)
//   sid : 画面を開くたびに作るランダムな ID(同じ人の一連の操作をまとめるためだけに使う)

const KINDS = ["read", "estimate", "dm"];
const MAX_CHARS = 60;

const clean = (s, max) => (typeof s === "string" ? s.trim().slice(0, max) : "");

// 画面から届いた記録を確かめ、保存できる形にする(不正なら null)
export function validEvent(body, games) {
  if (!body || !KINDS.includes(body.kind) || !games.includes(body.game)) return null;
  const sid = clean(body.sid, 40);
  if (!/^[A-Za-z0-9_-]{8,40}$/.test(sid)) return null;
  const chars = (Array.isArray(body.chars) ? body.chars : [])
    .slice(0, MAX_CHARS)
    .map((c) => ({ name: clean(c?.name, 30), cons: Math.min(6, Math.max(0, Number(c?.cons) | 0)), mochi: Boolean(c?.mochi) }))
    .filter((c) => c.name);
  const yen = (v) => (Number.isInteger(v) && v >= 0 && v < 10_000_000 ? v : null);
  return { kind: body.kind, game: body.game, sid, chars, low: yen(body.low), high: yen(body.high), ok: body.ok === false ? 0 : 1 };
}

export async function record(env, ev) {
  await env.DB.prepare("INSERT INTO events (at, kind, game, sid, ok, chars, n, low, high) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)")
    .bind(new Date().toISOString(), ev.kind, ev.game, ev.sid, ev.ok, JSON.stringify(ev.chars), ev.chars.length, ev.low, ev.high)
    .run();
}

// 同じ日に同じ内容(種類・ゲーム・キャラ・査定額)の記録は1件にまとめる(同じ人が何度も押した分を数えない)。
// キャラが無い記録(読み取りの失敗など)は、別の人のものをまとめないよう画面ごと(sid)に分ける
const DAY = "substr(datetime(at, '+9 hours'), 1, 10)";
const UNIQUE = `SELECT MAX(at) AS at, ${DAY} AS day, kind, game, MAX(sid) AS sid, MIN(ok) AS ok, chars, MAX(n) AS n, low, high, COUNT(*) AS times
  FROM events WHERE at >= ?
  GROUP BY day, kind, game, chars, low, high, CASE WHEN n = 0 THEN sid ELSE '' END`;

// 集計(日本時間の日ごと・直近の記録・よく出るキャラ)
export async function stats(env, days = 30) {
  const since = new Date(Date.now() - days * 86400_000).toISOString();
  const [daily, visitors, recent, chars] = await env.DB.batch([
    env.DB.prepare(
      `SELECT day, SUM(kind = 'read') AS reads, SUM(kind = 'estimate') AS estimates, SUM(kind = 'dm') AS dms
       FROM (${UNIQUE}) GROUP BY day ORDER BY day DESC`,
    ).bind(since),
    env.DB.prepare(`SELECT ${DAY} AS day, COUNT(DISTINCT sid) AS visitors FROM events WHERE at >= ? GROUP BY day`).bind(since),
    env.DB.prepare(`SELECT at, kind, game, sid, ok, chars, n, low, high, times FROM (${UNIQUE}) ORDER BY at DESC LIMIT 100`).bind(since),
    env.DB.prepare(
      `SELECT game, json_extract(c.value, '$.name') AS name, COUNT(*) AS n,
        SUM(json_extract(c.value, '$.cons') = 6) AS c6
       FROM (${UNIQUE}) AS u, json_each(u.chars) AS c
       WHERE kind = 'estimate' GROUP BY game, name ORDER BY n DESC LIMIT 40`,
    ).bind(since),
  ]);
  const v = Object.fromEntries(visitors.results.map((r) => [r.day, r.visitors]));
  return {
    days,
    daily: daily.results.map((r) => ({ ...r, visitors: v[r.day] ?? 0 })),
    recent: recent.results.map((r) => ({ ...r, chars: JSON.parse(r.chars ?? "[]") })),
    chars: chars.results,
  };
}
