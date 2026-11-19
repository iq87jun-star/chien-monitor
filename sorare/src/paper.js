// 模擬売買(お金は動かさない)。値上がりしそうなカードを仮に買い、毎日の最安出品で値洗いして、決まりに沿って仮に売る。
// ここは API を呼ばない純粋な関数だけ(test/paper.test.js)。記録は state/paper.json、動かすのは paper.js。

export function emptyPaper(bank = 100) { return { cash: bank, start: bank, open: [], closed: [], lastDay: null }; }

const mean = (a) => (a.length ? a.reduce((s, x) => s + x, 0) / a.length : 0);

// 勢い: 直近 recent 試合(出場した試合)の平均 ÷ 直近 10 試合(出場した試合)の平均。scores は新しい順
export function momentum(scores, recent = 3) {
  const played = (scores || []).filter((s) => s > 0);
  if (played.length < 5) return null;
  const all = mean(played), now = mean(played.slice(0, recent));
  return all > 0 ? { ratio: now / all, recentAvg: now, played: played.length } : null;
}

// 仮に買う候補: 勢いが minRatio 以上、直近平均が minAvg 以上、価格が minPrice〜maxPrice、持っていない選手。勢いの強い順に slots 枚まで
// closed と now を渡すと、売ってから cooldownDays 日たっていない選手は買わない(売った直後の買い直し=高値つかみを防ぐ)
export function pickBuys(cands, held, { minRatio = 1.25, minAvg = 30, minPrice = 1, maxPrice = 15, slots = 3, cooldownDays = 7, closed = [], now = Date.now() } = {}) {
  const have = new Set(held.map((p) => p.id));
  for (const c of closed) if (c.soldAt && now - Date.parse(c.soldAt) < cooldownDays * 864e5) have.add(c.id);
  return cands
    .map((c) => ({ ...c, m: momentum(c.scores) }))
    .filter((c) => c.m && c.m.ratio >= minRatio && c.m.recentAvg >= minAvg && c.price != null && c.price >= minPrice && c.price <= maxPrice && !have.has(c.id))
    .sort((a, b) => b.m.ratio - a.m.ratio)
    .slice(0, slots);
}

// 1 日分すすめる: 持っている仮のカードを今の最安出品で値洗いし、決まりに当てはまれば仮に売る(手数料 feePct% を引く)。
//   minHoldDays 日たつまでは売らない(CS2 の取引保護で、買ってすぐは売れないため)
//   利確: 手取りが買値から +takePct% 以上 / 下がり始め: 最高値から dropPct% 下がり、手取りがまだ買値以上 / 損切り: 買値から -stopPct% 以下 / 期限: maxDays 日
// 売れたお金は cash に戻す。prices は 選手 id → 今の最安出品(無ければ値洗いしない)
export function step(paper, prices, now, { feePct = 5, takePct = 20, dropPct = 10, stopPct = 20, maxDays = 21, minHoldDays = 0 } = {}) {
  const open = [], closed = [...paper.closed];
  let cash = paper.cash;
  for (const p of paper.open) {
    const px = prices[p.id];
    if (px == null) { open.push(p); continue; }
    const peak = Math.max(p.peak ?? p.buy, px), net = px * (1 - feePct / 100);
    const days = (now - Date.parse(p.at)) / 864e5;
    const why = days < minHoldDays ? null
      : net >= p.buy * (1 + takePct / 100) ? "利確"
      : px <= peak * (1 - dropPct / 100) && net >= p.buy && peak > p.buy ? "下がり始め"
      : net <= p.buy * (1 - stopPct / 100) ? "損切り"
      : days >= maxDays ? "期限" : null;
    if (why) { cash += net; closed.push({ ...p, sell: +net.toFixed(2), soldAt: new Date(now).toISOString(), why, pnl: +(net - p.buy).toFixed(2) }); }
    else open.push({ ...p, last: px, peak });
  }
  return { ...paper, cash: +cash.toFixed(2), open, closed: closed.slice(-200) };
}

// 仮に買う(cash の範囲で、1 枚ずつ)
export function buy(paper, picks, now) {
  let cash = paper.cash; const open = [...paper.open], bought = [];
  for (const c of picks) {
    if (c.price > cash) continue;
    cash -= c.price;
    const p = { id: c.id, name: c.name, sport: c.sport, card: c.card, buy: c.price, last: c.price, peak: c.price, at: new Date(now).toISOString(), ratio: +c.m.ratio.toFixed(2) };
    open.push(p); bought.push(p);
  }
  return { paper: { ...paper, cash: +cash.toFixed(2), open }, bought };
}

// 成績: 資産(現金 + 持っている分の手取り見込み)、始めからの増減、勝ち数・負け数
export function summary(paper, feePct = 5) {
  const held = paper.open.reduce((s, p) => s + (p.last ?? p.buy) * (1 - feePct / 100), 0);
  const total = paper.cash + held;
  const wins = paper.closed.filter((c) => c.pnl > 0).length, losses = paper.closed.filter((c) => c.pnl <= 0).length;
  return { total: +total.toFixed(2), pct: +((total / paper.start - 1) * 100).toFixed(1), wins, losses, realized: +paper.closed.reduce((s, c) => s + c.pnl, 0).toFixed(2) };
}
