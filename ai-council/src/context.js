// AI に渡す前提(経済指標・各手法の保有時間との重なり)を作る。ここは計算だけで、通信しない。

const H = 3600e3;
const JST = 9 * H;
const WEEK = "日月火水木金土";

// 日本時間の「11/5(木) 22:30」
export function formatJST(date) {
  const j = new Date(date.getTime() + JST);
  const hh = String(j.getUTCHours()).padStart(2, "0");
  const mm = String(j.getUTCMinutes()).padStart(2, "0");
  return `${j.getUTCMonth() + 1}/${j.getUTCDate()}(${WEEK[j.getUTCDay()]}) ${hh}:${mm}`;
}

export function todayJST(now = new Date()) {
  return new Date(now.getTime() + JST).toISOString().slice(0, 10);
}

// ゴトー日: 5・10・15・20・25 日と月末。土日なら前の金曜へ(日本の祝日の前倒しは未対応)
export function isGotobi(y, m, d) {
  const last = new Date(Date.UTC(y, m, 0)).getUTCDate(); // m は 1〜12
  const dow = (dd) => new Date(Date.UTC(y, m - 1, dd)).getUTCDay();
  if (dow(d) === 0 || dow(d) === 6) return false;
  const targets = [5, 10, 15, 20, 25, last];
  return targets.some((t) => {
    let x = t;
    while (dow(x) === 0 || dow(x) === 6) x--;
    return x === d;
  });
}

// now から hours 時間以内に始まる、各手法の保有時間(日本時間の曜日・時刻で定義)
export function legWindows(legs, now, hours) {
  const out = [];
  const startDay = new Date(now.getTime() + JST);
  for (let i = -2; i <= Math.ceil(hours / 24) + 1; i++) {
    const day = new Date(Date.UTC(startDay.getUTCFullYear(), startDay.getUTCMonth(), startDay.getUTCDate() + i));
    const [y, m, d, dow] = [day.getUTCFullYear(), day.getUTCMonth() + 1, day.getUTCDate(), day.getUTCDay()];
    for (const leg of legs) {
      const hit = leg.days === "gotobi" ? isGotobi(y, m, d) : leg.days.includes(dow);
      if (!hit) continue;
      const [hh, mm] = leg.start.split(":").map(Number);
      const from = new Date(Date.UTC(y, m - 1, d, hh, mm) - JST);
      const to = new Date(from.getTime() + leg.hours * H);
      if (to > now && from.getTime() <= now.getTime() + hours * H) out.push({ leg, from, to });
    }
  }
  return out.sort((a, b) => a.from - b.from);
}

// 保有時間(開始の margin 分前から終了まで)に、関係する通貨の重要指標・祝日が入るもの。祝日はその時刻から 24 時間とみなす
export function legOverlaps(windows, events, { legImpact, marginMinutes }) {
  return windows
    .map((w) => {
      const from = w.from.getTime() - marginMinutes * 60e3;
      const hits = events.filter((e) => {
        const t = new Date(e.date).getTime();
        const end = e.impact === "Holiday" ? t + 24 * H : t;
        return legImpact.includes(e.impact) && w.leg.currencies.includes(e.country) && end >= from && t <= w.to.getTime();
      });
      return { ...w, hits };
    })
    .filter((w) => w.hits.length);
}

export function overlapText(overlaps) {
  if (!overlaps.length) return "(この先の保有時間に重なる重要指標・祝日はなし)";
  return overlaps
    .map((o) => {
      const head = `- ${o.leg.name}: ${formatJST(o.from)}〜${formatJST(o.to)}`;
      const hits = o.hits.map((e) => `  - ${formatJST(new Date(e.date))} [${e.country}] ${e.title}${e.impact === "Holiday" ? "(祝日)" : ""}`);
      return [head, ...hits].join("\n");
    })
    .join("\n");
}

// 1 時間前〜hours 時間後の重要指標
export function pickEvents(events, { currencies, impact, hours }, now = new Date()) {
  const from = now.getTime() - H;
  const until = now.getTime() + hours * H;
  return events
    .map((e) => ({ ...e, at: new Date(e.date) }))
    .filter((e) => currencies.includes(e.country) && impact.includes(e.impact))
    .filter((e) => e.at.getTime() >= from && e.at.getTime() <= until)
    .sort((a, b) => a.at - b.at);
}

export function calendarText(events) {
  if (!events.length) return "(この先の重要指標はなし)";
  return events
    .map((e) => {
      const fp = [e.forecast && `予想 ${e.forecast}`, e.previous && `前回 ${e.previous}`].filter(Boolean).join(" / ");
      return `- ${formatJST(e.at)} [${e.country}] ${e.title}${fp ? `(${fp})` : ""}`;
    })
    .join("\n");
}

// 2 週分のカレンダーを重複なしでまとめる
export function mergeEvents(lists) {
  const seen = new Set();
  return lists.flat().filter((e) => {
    const k = `${e.date}|${e.country}|${e.title}`;
    return seen.has(k) ? false : seen.add(k);
  });
}
