// AI に渡す前提(自分のルール・損益分岐・経済指標)を作る。ここは計算だけで、通信しない。

// バイナリー: 払い戻し倍率 m(1,000 円賭けて当たれば m×1,000 円戻る)の損益分岐の勝率は 1/m
export function breakEvenWinRate(payoutMultiple) {
  if (!(payoutMultiple > 1)) throw new Error(`payoutMultiple は 1 より大きい数: ${payoutMultiple}`);
  return 1 / payoutMultiple;
}

// プロップ: 1 回の損失額と、日次・最大の損失上限まで何連敗できるか
export function propLimits({ accountSize, dailyLossPct, maxLossPct, riskPerTradePct }) {
  const risk = (accountSize * riskPerTradePct) / 100;
  const daily = (accountSize * dailyLossPct) / 100;
  const max = (accountSize * maxLossPct) / 100;
  return { risk, daily, max, lossesToDaily: Math.floor(daily / risk), lossesToMax: Math.floor(max / risk) };
}

const pct = (x) => `${(x * 100).toFixed(1)}%`;
const num = (x) => x.toLocaleString("en-US");

export function profileText(profile) {
  const lines = [];
  const p = profile.prop;
  if (p) {
    const l = propLimits(p);
    lines.push(
      `【プロップ】${p.firm} / 口座 ${num(p.accountSize)} ${p.currency}`,
      `- 日次損失上限 ${p.dailyLossPct}%(${num(l.daily)})、最大損失 ${p.maxLossPct}%(${num(l.max)})、利益目標 ${p.profitTargetPct}%`,
      `- 1 回のリスク ${p.riskPerTradePct}%(${num(l.risk)})→ ${l.lossesToDaily} 連敗で日次上限、${l.lossesToMax} 連敗で最大損失`,
      `- 銘柄 ${p.markets.join("・")} / 時間足 ${p.timeframes.join("・")}`,
      ...(p.rules ?? []).map((r) => `- 規約: ${r}`),
    );
  }
  const b = profile.binary;
  if (b) {
    lines.push(
      `【バイナリーオプション】${b.broker}`,
      `- 払い戻し倍率 ${b.payoutMultiple} 倍 → 損益分岐の勝率 ${pct(breakEvenWinRate(b.payoutMultiple))}`,
      `- 判定時間 ${b.expiries.join("・")} / 銘柄 ${b.markets.join("・")} / 1 回 ${num(b.stakePerTrade)} 円、1 日の損失上限 ${num(b.dailyLossLimit)} 円`,
    );
  }
  if (profile.notes) lines.push(`【メモ】${profile.notes}`);
  return lines.join("\n");
}

// 日本時間の「11/5(木) 22:30」
const WEEK = "日月火水木金土";
export function formatJST(date) {
  const j = new Date(date.getTime() + 9 * 3600e3);
  const hh = String(j.getUTCHours()).padStart(2, "0");
  const mm = String(j.getUTCMinutes()).padStart(2, "0");
  return `${j.getUTCMonth() + 1}/${j.getUTCDate()}(${WEEK[j.getUTCDay()]}) ${hh}:${mm}`;
}

export function todayJST(now = new Date()) {
  return new Date(now.getTime() + 9 * 3600e3).toISOString().slice(0, 10);
}

// Forex Factory の週間カレンダー(JSON)から、1 時間前〜hours 時間後の重要指標を選ぶ
export function pickEvents(events, { currencies, impact, hours }, now = new Date()) {
  const from = now.getTime() - 3600e3;
  const until = now.getTime() + hours * 3600e3;
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
