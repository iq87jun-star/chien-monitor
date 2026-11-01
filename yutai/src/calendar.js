// 東証の営業日カレンダーと、優待クロスで使う日付の計算。
// 休業日は JPX の公表に合わせて毎年足す(範囲外の日付はエラーにして気付けるようにする)。

export const HOLIDAYS = new Set([
  // 2026
  '2026-01-01', '2026-01-02', '2026-01-12', '2026-02-11', '2026-02-23', '2026-03-20',
  '2026-04-29', '2026-05-04', '2026-05-05', '2026-05-06', '2026-07-20', '2026-08-11',
  '2026-09-21', '2026-09-22', '2026-09-23', '2026-10-12', '2026-11-03', '2026-11-23',
  '2026-12-31',
  // 2027
  '2027-01-01', '2027-01-11', '2027-02-11', '2027-02-23', '2027-03-22', '2027-04-29',
  '2027-05-03', '2027-05-04', '2027-05-05', '2027-07-19', '2027-08-11', '2027-09-20',
  '2027-09-23', '2027-10-11', '2027-11-03', '2027-11-23', '2027-12-31',
]);
export const CALENDAR_FIRST = '2026-01-01';
export const CALENDAR_LAST = '2027-12-31';

const DAY = 86400000;
const toMs = (d) => Date.parse(`${d}T00:00:00Z`);
const toStr = (ms) => new Date(ms).toISOString().slice(0, 10);

function check(d) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d) || Number.isNaN(toMs(d))) throw new Error(`日付の形式が不正: ${d}`);
  if (d < CALENDAR_FIRST || d > CALENDAR_LAST) {
    throw new Error(`${d} は休業日カレンダーの範囲外(${CALENDAR_FIRST}〜${CALENDAR_LAST})。src/calendar.js に休業日を足す`);
  }
}

export function isBizDay(d) {
  check(d);
  const w = new Date(toMs(d)).getUTCDay();
  return w !== 0 && w !== 6 && !HOLIDAYS.has(d);
}

export function addDays(d, n) {
  return toStr(toMs(d) + n * DAY);
}

export function daysBetween(a, b) {
  return Math.round((toMs(b) - toMs(a)) / DAY);
}

// n 営業日後(n<0 なら前)
export function addBizDays(d, n) {
  let cur = d;
  const step = n >= 0 ? 1 : -1;
  for (let left = Math.abs(n); left > 0;) {
    cur = addDays(cur, step);
    if (isBizDay(cur)) left--;
  }
  return cur;
}

// 受渡日(T+2)
export const settleDate = (tradeDate) => addBizDays(tradeDate, 2);

// 権利付最終日: 受渡日が権利確定日以前になる最後の営業日
export function lastCumDate(recordDate) {
  let t = addDays(recordDate, 0);
  if (!isBizDay(t)) t = addBizDays(t, -1);
  t = addBizDays(t, -2);
  // 念のため前後を確かめる(権利確定日が休業日でも正しく決まるように)
  while (settleDate(t) > recordDate) t = addBizDays(t, -1);
  while (settleDate(addBizDays(t, 1)) <= recordDate) t = addBizDays(t, 1);
  return t;
}

// 品貸日数(逆日歩・貸株料がかかる日数): 約定日の受渡日から翌営業日の受渡日まで
export function kashiDays(tradeDate) {
  return daysBetween(settleDate(tradeDate), settleDate(addBizDays(tradeDate, 1)));
}

// entryDate に売り建てて、権利付最終日 cum の翌営業日に現渡したときの日数
export function holdDays(entryDate, cum) {
  return daysBetween(settleDate(entryDate), settleDate(addBizDays(cum, 1)));
}

export function todayJst(now = new Date()) {
  return toStr(now.getTime() + 9 * 3600000);
}
