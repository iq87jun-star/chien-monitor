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

// 集計(日本時間の日ごと・直近の記録・よく出るキャラ)
export async function stats(env, days = 30) {
  const since = new Date(Date.now() - days * 86400_000).toISOString();
  const [daily, recent, chars] = await env.DB.batch([
    env.DB.prepare(
      `SELECT substr(datetime(at, '+9 hours'), 1, 10) AS day,
        SUM(kind = 'read') AS reads, SUM(kind = 'estimate') AS estimates, SUM(kind = 'dm') AS dms,
        COUNT(DISTINCT sid) AS visitors
       FROM events WHERE at >= ? GROUP BY day ORDER BY day DESC`,
    ).bind(since),
    env.DB.prepare("SELECT at, kind, game, sid, ok, chars, n, low, high FROM events ORDER BY id DESC LIMIT 100"),
    env.DB.prepare(
      `SELECT game, json_extract(c.value, '$.name') AS name, COUNT(*) AS n,
        SUM(json_extract(c.value, '$.cons') = 6) AS c6
       FROM events, json_each(events.chars) AS c
       WHERE kind = 'estimate' AND at >= ? GROUP BY game, name ORDER BY n DESC LIMIT 40`,
    ).bind(since),
  ]);
  return {
    days,
    daily: daily.results,
    recent: recent.results.map((r) => ({ ...r, chars: JSON.parse(r.chars ?? "[]") })),
    chars: chars.results,
  };
}
