import assert from 'node:assert/strict';
import test from 'node:test';
import { addBizDays, holdDays, isBizDay, kashiDays, lastCumDate, settleDate } from '../src/calendar.js';

test('営業日', () => {
  assert.equal(isBizDay('2026-11-03'), false); // 文化の日
  assert.equal(isBizDay('2026-11-02'), true);
  assert.equal(addBizDays('2026-10-30', 1), '2026-11-02');
  assert.equal(settleDate('2026-10-29'), '2026-11-02');
});

test('品貸日数は日証金データと一致する(申込日 10/29 → 2 日)', () => {
  assert.equal(kashiDays('2026-10-29'), 2);
});

test('権利付最終日', () => {
  assert.equal(lastCumDate('2026-11-30'), '2026-11-26');
  assert.equal(lastCumDate('2027-03-31'), '2027-03-29');
  // 権利確定日が休業日(12/31)
  assert.equal(lastCumDate('2026-12-31'), '2026-12-28');
  assert.equal(kashiDays('2026-12-28'), 5); // 年末年始をまたぐ
});

test('一般信用の保有日数', () => {
  assert.equal(holdDays('2026-11-26', '2026-11-26'), 1);
  assert.equal(holdDays('2026-11-16', '2026-11-26'), 13); // 受渡 11/18 → 12/1
});

test('カレンダー範囲外はエラー', () => {
  assert.throws(() => isBizDay('2028-01-05'), /範囲外/);
});
