import assert from 'node:assert/strict';
import test from 'node:test';
import { evaluate, scorePaper } from '../src/cost.js';
import { estimateMaxRate, parseShina, toSlimCsv, fromSlimCsv } from '../src/jsf.js';

const cfg = { seidoLendingRate: 0.0115, ippanLendingRate: 0.039, commissionYenPerLeg: 0, dividendTaxRate: 0.20315, maxRateStress: 2, minProfitYen: 500 };
const base = { code: '1111', name: 'テスト', recordDate: '2026-11-30', shares: 100, value: 3000, dividend: 20, ippanStock: 'なし', ippanEntry: null, price: 2000 };

test('最高料率の推定(貸借値段の0.2%を0.2円単位に切り上げ・下限1円)', () => {
  assert.equal(estimateMaxRate(4155), 8.4);
  assert.equal(estimateMaxRate(2045), 4.2);
  assert.equal(estimateMaxRate(300), 1);
  assert.equal(estimateMaxRate(600), 1.2);
});

test('制度信用: 品貸日数1日なら最悪でもプラス', () => {
  const e = evaluate(base, { cfg });
  assert.equal(e.cum, '2026-11-26');
  assert.equal(e.kashiDays, 1);
  assert.equal(e.maxRate, 4); // 2000 * 0.2%
  assert.equal(e.gyakuWorst, 400);
  // 3000 - 20*100*0.20315(406) - 2000*100*0.0115/365(6) - 400*2
  assert.equal(e.seidoNetStress, 1787);
  assert.match(e.verdict, /^制度信用で入る/);
});

test('年末年始(品貸日数5日)の高い銘柄は見送り', () => {
  const e = evaluate({ ...base, recordDate: '2026-12-31', price: 9000 }, { cfg });
  assert.equal(e.kashiDays, 5);
  assert.equal(e.verdict, '見送り');
});

test('一般在庫ありなら一般信用', () => {
  const e = evaluate({ ...base, ippanStock: 'あり', ippanEntry: '2026-11-16' }, { cfg });
  assert.equal(e.verdict, '一般信用で入る');
  assert.equal(e.holdDays, 13);
});

test('新規売り停止なら制度は不可', () => {
  const shina = new Map([['1111', { maxRate: 4, restrict: '停止', excess: 100 }]]);
  const e = evaluate(base, { cfg, shina });
  assert.equal(e.verdict, '見送り');
});

test('紙上採点: 当日品貸料率×株数が実際の逆日歩', () => {
  const e = evaluate(base, { cfg });
  const s = scorePaper(e, { rate: 1.5 });
  assert.equal(s.gyakuActual, 150);
  assert.equal(s.withinWorst, true);
  assert.equal(s.seidoNetActual, e.seidoNetNoGyaku - 150);
});

test('品貸料率一覧の読み取りと保存形式の往復', () => {
  const text = [
    '品貸料率一覧,,,,,,,,,,,,,,,',
    '貸借申込日,決済日,コード,銘柄名,取引所区分,決算事由,決算等,貸借値段（円）,貸株超過株数,最高料率（円）,当日品貸料率（円）,当日品貸日数,前日品貸料率（円）,備考,制限,応札倍率ランク',
    '20261029,20261102,1377,サカタのタネ,東証,決算,20261130,4155.00,3800,8.40,0.20,2,0.10,,,F',
    '20261029,20261102,1306,ＮＦＴＯＰＩＸ,東証,決算,20270710,421.30,0,6.00,*****,*****,*****,満額,,',
  ].join('\n');
  const rows = parseShina(text);
  assert.equal(rows.length, 2);
  assert.deepEqual([rows[0].date, rows[0].eventDate, rows[0].maxRate, rows[0].rate, rows[0].days], ['2026-10-29', '2026-11-30', 8.4, 0.2, 2]);
  assert.equal(rows[1].rate, 0);
  assert.deepEqual(fromSlimCsv(toSlimCsv(rows))[0].maxRate, 8.4);
});
