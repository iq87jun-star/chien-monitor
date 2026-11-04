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
  const avail = availability(p);
  if (!avail) return { ...p, opp: m.opp, home: m.home, proj: 0 };
  const o = form[m.opp], me = form[p.club];
  const clamp = (x) => Math.max(0.85, Math.min(1.15, x));
  let f = ["Goalkeeper", "Defender"].includes(p.pos)
    ? clamp(1 + (0.5 * (avgGf - o.gf)) / avgGf + (0.25 * (avgGf - me.ga)) / avgGf)
    : clamp(1 + (0.5 * (o.ga - avgGf)) / avgGf + (0.25 * (me.gf - avgGf)) / avgGf);
  f *= m.home ? 1.03 : 0.97;
  return { ...p, opp: m.opp, home: m.home, factor: f, proj: p.l15 * f * (0.3 + 0.7 * p.start) * avail };
}

// 出られる見込み: 出場停止・ケガで欠場なら 0、出場が微妙(doubtful・GTD など)なら 0.7、それ以外は 1
export function availability(p) {
  if (p.suspended) return 0;
  if (!p.injury) return 1;
  return /doubt|question|gtd|day.?to.?day|probable/i.test(p.injury) ? 0.7 : 0;
}

// 入れ替え: 値上がりしたカードを売り、似た働きの安い選手のカードに替える。
// 売る側: 買値から gainPct% 以上値上がり(今の最安出品で判定)し、買ってから minHoldDays 日を過ぎたもの。
// 代わり: 手持ちに無い同じポジションの選手(NBA は星が売る側以下)で、ケガ・出場停止が無く、移籍して newJoinDays 日以上たち、
// 予想が売る側の minProjRatio 倍以上、価格が売る側の最安出品の maxPriceRatio 倍以下。
// 手元に残る額 = 売値 × (1 - feePct%) - 代わりの価格 が minProfitUsd 以上のものだけ、得の大きい順に。代わりの選手は 1 回だけ使う
export function swapCandidates(owned, market, { gainPct = 20, minProjRatio = 0.9, maxPriceRatio = 0.6, minProfitUsd = 1, feePct = 5, minHoldDays = 14, newJoinDays = 30 } = {}, now = Date.now()) {
  const have = new Set(owned.map((c) => c.id));
  const out = [], used = new Set();
  const sells = owned.filter((c) => c.cost && c.floor != null && c.proj > 0 && (c.floor / c.cost - 1) * 100 >= gainPct
    && !(c.since && now - Date.parse(c.since) < minHoldDays * 864e5));
  const pairs = [];
  for (const s of sells) {
    for (const m of market) {
      if (have.has(m.id) || m.price == null || !m.card || m.proj <= 0 || availability(m) < 1) continue;
      if (m.joined && now - Date.parse(m.joined) < newJoinDays * 864e5) continue;
      if (s.stars != null ? (m.stars == null || m.stars > s.stars) : m.pos !== s.pos) continue;
      if (m.proj < s.proj * minProjRatio || m.price > s.floor * maxPriceRatio) continue;
      const profit = s.floor * (1 - feePct / 100) - m.price;
      if (profit >= minProfitUsd) pairs.push({ sell: s, sub: m, profit, gain: (s.floor / s.cost - 1) * 100 });
    }
  }
  pairs.sort((a, b) => b.profit - a.profit || b.sub.proj - a.sub.proj);
  for (const p of pairs) {
    if (used.has(p.sell.id) || used.has(p.sub.id)) continue;
    used.add(p.sell.id); used.add(p.sub.id);
    out.push(p);
  }
  return out;
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

// 売り候補: 年齢が高い、スタメンから外れてきた、または買値から gainPct% 以上値上がりしたカード(値上がりは今の最安出品で判定)
export function sellCandidates(cards, { maxAge = 31, minStartRate = 0.5, gainPct = 30 } = {}) {
  return cards
    .map((c) => {
      const gain = c.cost && c.floor != null ? (c.floor / c.cost - 1) * 100 : null;
      return { ...c, gain, reasons: [c.age > maxAge && `${c.age}歳`, c.start < minStartRate && `スタメン率${Math.round(c.start * 100)}%`,
        gain != null && gain >= gainPct && `値上がり +${Math.round(gain)}%(買値 $${c.cost.toFixed(2)})`].filter(Boolean) };
    })
    .filter((c) => c.reasons.length);
}

// 出品価格の目安: 今の最安出品から undercutPct% 下げた額(セント単位で切り捨て、最低 $0.01)。最安出品が無ければ null
export function sellPrice(floor, undercutPct = 0) {
  if (floor == null) return null;
  return Math.max(0.01, Math.floor(+(floor * (100 - undercutPct)).toFixed(6)) / 100);
}

// NBA: 節の中で一番良い 1 試合 × カードのボーナスが得点。予想 = 直近 10 試合の平均 + ばらつき × 試合数に応じた上振れ
// (n 試合の最大値の期待値 ≒ 平均 + 標準偏差 × 係数)。節に試合が無い・欠場(OUT)なら 0、出場未定(GTD)は 0.7 倍
const MAX_OF_N = [0, 0, 0.56, 0.85, 1.03, 1.16];
export function nbaProject(p, gamesByTeam) {
  const n = gamesByTeam[p.club] || 0;
  if (!n || p.injury === "OUT") return { ...p, games: n, proj: 0 };
  const played = (p.scores || []).filter((s) => s > 0);
  const mean = p.l15 || (played.length ? played.reduce((a, b) => a + b, 0) / played.length : 0);
  const sd = played.length > 1 ? Math.sqrt(played.reduce((a, b) => a + (b - mean) ** 2, 0) / played.length) : 0;
  const proj = (mean + sd * MAX_OF_N[Math.min(n, 5)]) * (p.injury === "GTD" ? 0.7 : 1);
  return { ...p, games: n, proj };
}

// NBA のラインナップ: 位置の決まりなしで 5 枚。星の合計が starCap 以下、budget があれば価格の合計がその範囲。
// 予想の高い順に並べ、残りを全部足しても今の最良に届かない枝は切る(候補は上位 topN まで)
export function bestNbaLineup(cands, { starCap = Infinity, budget = Infinity, topN = 60 } = {}) {
  const c = cands.filter((x) => x.proj > 0 && x.stars != null && (budget === Infinity || x.price != null))
    .sort((a, b) => b.proj - a.proj).slice(0, topN);
  let best = null;
  const pick = [];
  (function dfs(i, pts, stars, cost) {
    if (pick.length === 5) { if (!best || pts > best.pts) best = { pts, cost, lineup: [...pick] }; return; }
    for (let j = i; j < c.length; j++) {
      const need = 5 - pick.length;
      let bound = pts;
      for (let k = j; k < j + need && k < c.length; k++) bound += c[k].proj;
      if (best && bound <= best.pts) return;
      const x = c[j];
      if (stars + x.stars > starCap || cost + (x.price || 0) > budget) continue;
      pick.push(x); dfs(j + 1, pts + x.proj, stars + x.stars, cost + (x.price || 0)); pick.pop();
    }
  })(0, 0, 0, 0);
  if (!best) return null;
  return { ...best, stars: best.lineup.reduce((s, x) => s + x.stars, 0), captain: null };
}
