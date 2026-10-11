// 在庫と分割払いの計算(管理画面と Worker で共通)。日付はすべて日本時間の YYYY-MM-DD
export const STOCK_STATUSES = ["未出品", "出品中", "商談中", "売却済み"];
export const SPLIT_STATUSES = ["支払い中", "完済", "引き渡し済み", "中止"];
export const SITES = ["ゲームトレード", "ゲームクラブ", "ならむ鯖", "ぱるる鯖", "X", "その他"];
// 引き渡しのチェック(分割は完済してから引き渡す)
export const HANDOVER = { mail: "メールアドレスの変更", link: "連携(SNS など)の解除", pass: "パスワードの変更" };

// 値下げと巡回の目安
export const RULES = { priceDays: 7, priceRate: 0.05, checkDays: 3, remindDays: 1 };

const DAY = 86400_000;
export const days = (from, to) => Math.round((Date.parse(to) - Date.parse(from)) / DAY);
export const addDays = (d, n) => new Date(Date.parse(d) + n * DAY).toISOString().slice(0, 10);

// 毎月 day 日の n 回分の予定。start の月から始める(月末を超える日は月末にする)
export function monthly(start, n, amount, day = Number(start.slice(8, 10))) {
  const [y, m] = start.split("-").map(Number);
  return Array.from({ length: n }, (_, i) => {
    const yy = y + Math.floor((m - 1 + i) / 12);
    const mm = ((m - 1 + i) % 12) + 1;
    const last = new Date(Date.UTC(yy, mm, 0)).getUTCDate();
    return { due_on: `${yy}-${String(mm).padStart(2, "0")}-${String(Math.min(day, last)).padStart(2, "0")}`, amount };
  });
}

// 分割1件の状況。pays は [{due_on, amount, paid_on}]
export function splitState(split, pays, today) {
  const sorted = [...pays].sort((a, b) => a.due_on.localeCompare(b.due_on));
  const paid = sorted.filter((p) => p.paid_on).reduce((n, p) => n + p.amount, 0);
  const open = sorted.filter((p) => !p.paid_on);
  const late = open.filter((p) => p.due_on < today);
  return {
    paid,
    remaining: Math.max(0, split.total - paid),
    count: [sorted.length - open.length, sorted.length],
    next: open[0] ?? null,
    late: late.length ? { n: late.length, days: days(late[0].due_on, today), amount: late.reduce((n, p) => n + p.amount, 0) } : null,
    // 予定の合計が総額と合わない時に知らせる
    mismatch: sorted.reduce((n, p) => n + p.amount, 0) !== split.total,
  };
}

// 値下げの目安: 出品中で、価格を決めてから priceDays 日たったら priceRate 下げる(千円単位・下限まで)
export function priceDown(s, today, r = RULES) {
  if (s.status !== "出品中" || !s.price || !s.price_at || days(s.price_at, today) < r.priceDays) return null;
  const to = Math.max(s.floor ?? 0, Math.floor((s.price * (1 - r.priceRate)) / 1000) * 1000);
  return to < s.price ? { from: s.price, to } : null;
}

// 出品先で、checkDays 日以上確認していないもの
export const staleListings = (s, today, r = RULES) =>
  s.status === "出品中" || s.status === "商談中" ? (s.listings ?? []).filter((l) => !l.checked_on || days(l.checked_on, today) >= r.checkDays) : [];

// 今日やること(管理画面の一番上に出す)
export function todos(stocks, splits, today, r = RULES) {
  const out = [];
  for (const sp of splits) {
    if (sp.status !== "支払い中") {
      if (sp.status === "完済") out.push({ kind: "split", id: sp.id, level: 2, text: `分割 No.${sp.id} ${sp.buyer}さんが完済しました。引き渡しを進めてください` });
      continue;
    }
    const st = splitState(sp, sp.pays ?? [], today);
    if (st.late) out.push({ kind: "split", id: sp.id, level: 3, text: `分割 No.${sp.id} ${sp.buyer}さんの支払いが ${st.late.days}日遅れています(${st.late.amount.toLocaleString()}円)` });
    else if (st.next && days(today, st.next.due_on) <= r.remindDays)
      out.push({ kind: "split", id: sp.id, level: 2, text: `分割 No.${sp.id} ${sp.buyer}さんの支払日です(${st.next.due_on.slice(5).replace("-", "/")} ${st.next.amount.toLocaleString()}円)` });
    if (!st.next && !st.late) out.push({ kind: "split", id: sp.id, level: 2, text: `分割 No.${sp.id} は予定の入金がすべて済みました。「完済」にしてください` });
  }
  for (const s of stocks) {
    const pd = priceDown(s, today, r);
    if (pd) out.push({ kind: "stock", id: s.id, level: 1, text: `在庫 No.${s.id} 値下げの時期です(${(pd.from / 10000).toFixed(1)}万 → ${(pd.to / 10000).toFixed(1)}万)` });
    const stale = staleListings(s, today, r);
    if (stale.length) out.push({ kind: "stock", id: s.id, level: 1, text: `在庫 No.${s.id} ${stale.map((l) => l.site).join("・")} を確認してください` });
  }
  return out.sort((a, b) => b.level - a.level);
}
