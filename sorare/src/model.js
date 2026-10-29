// 予想スコアとラインナップの選び方(API を呼ばない純粋な関数。test/model.test.js)。

export const POSITIONS = ["Goalkeeper", "Defender", "Midfielder", "Forward"];

// 直近の試合からチームの 1 試合あたり得点・失点
export function teamForm(name, games) {
  let gf = 0, ga = 0, n = 0;
  for (const g of games) {
    if (g.homeGoals == null || g.awayGoals == null) continue;
    const home = g.homeTeam.name === name;
    gf += home ? g.homeGoals : g.awayGoals;
    ga += home ? g.awayGoals : g.homeGoals;
    n++;
  }
  return n ? { gf: gf / n, ga: ga / n, n } : { gf: 0, ga: 0, n: 0 };
}

// スタメン率 = 直近の試合で 60 分以上出た割合
export function startRate(scores) {
  if (!scores?.length) return 0;
  return scores.filter((s) => (s.playerGameStats?.minsPlayed || 0) >= 60).length / scores.length;
}

// 予想 = L15 × 出場の確実さ × 相手の補正(守備側は相手の得点、攻撃側は相手の失点。±15% に収め、ホーム +3%)
export function project(p, { form, next, avgGf }) {
  const m = next[p.club];
  if (!m || !form[m.opp] || !form[p.club] || !avgGf) return { ...p, proj: 0 };
  const o = form[m.opp], me = form[p.club];
  const clamp = (x) => Math.max(0.85, Math.min(1.15, x));
  let f = ["Goalkeeper", "Defender"].includes(p.pos)
    ? clamp(1 + (0.5 * (avgGf - o.gf)) / avgGf + (0.25 * (avgGf - me.ga)) / avgGf)
    : clamp(1 + (0.5 * (o.ga - avgGf)) / avgGf + (0.25 * (me.gf - avgGf)) / avgGf);
  f *= m.home ? 1.03 : 0.97;
  return { ...p, opp: m.opp, home: m.home, factor: f, proj: p.l15 * f * (0.3 + 0.7 * p.start) };
}

// GK・DF・MF・FW・エクストラ(GK 以外)の 5 枚。同じクラブは maxPerClub 人まで、budget があれば price の合計がその範囲。
// 候補はポジションごとに上位 topN に絞って総当たりする。返り値の lineup はこの順(Sorare の index 0〜4)。
export function bestLineup(cands, { maxPerClub = 2, budget = Infinity, topN = 8 } = {}) {
  const ok = cands.filter((c) => c.proj > 0 && (budget === Infinity || c.price != null));
  const by = Object.fromEntries(POSITIONS.map((pos) => [pos, ok.filter((c) => c.pos === pos).sort((a, b) => b.proj - a.proj).slice(0, topN)]));
  const extras = ok.filter((c) => c.pos !== "Goalkeeper").sort((a, b) => b.proj - a.proj).slice(0, topN * 3);
  let best = null;
  for (const gk of by.Goalkeeper) for (const d of by.Defender) for (const m of by.Midfielder) for (const f of by.Forward) for (const e of extras) {
    const L = [gk, d, m, f, e];
    if (new Set(L.map((x) => x.id)).size < 5) continue;
    const clubs = {};
    if (L.some((x) => (clubs[x.club] = (clubs[x.club] || 0) + 1) > maxPerClub)) continue;
    const cost = L.reduce((s, x) => s + (x.price || 0), 0);
    if (cost > budget) continue;
    const pts = L.reduce((s, x) => s + x.proj, 0);
    if (!best || pts > best.pts) best = { pts, cost, lineup: L };
  }
  if (!best) return null;
  // キャプテンは予想が一番高い選手
  const cap = best.lineup.reduce((a, b) => (b.proj > a.proj ? b : a));
  return { ...best, captain: cap.id };
}

// 売り候補: 年齢が高い、またはスタメンから外れてきたカード
export function sellCandidates(cards, { maxAge = 31, minStartRate = 0.5 } = {}) {
  return cards
    .map((c) => ({ ...c, reasons: [c.age > maxAge && `${c.age}歳`, c.start < minStartRate && `スタメン率${Math.round(c.start * 100)}%`].filter(Boolean) }))
    .filter((c) => c.reasons.length);
}
