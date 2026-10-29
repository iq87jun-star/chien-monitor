import { test } from "node:test";
import assert from "node:assert/strict";
import { generateKey, verifyLimitOrder, exportPublicKey, signAuthorizationRequest } from "@sorare/crypto";
import { planBuys, planSells, spentInWeek, buildApprovals, signable } from "../src/trade.js";

const lim = { perCardMaxUsd: 30, weeklyMaxUsd: 60 };

test("planBuys は 1 枚の上限と、使用済みを含めた週の上限を守る", () => {
  const r = planBuys([{ name: "a", price: 10 }, { name: "b", price: 31 }, { name: "c", price: 25 }, { name: "d", price: 20 }, { name: "e", price: null }], lim, 15);
  assert.deepEqual(r.map((x) => x.ok), [true, false, true, false, false]);   // 15+10+25=50、d で 70 > 60
  assert.match(r[1].why, /1枚の上限/);
  assert.match(r[3].why, /週の上限/);
});

test("spentInWeek は直近 7 日に買ったカードだけ足す", () => {
  const now = Date.parse("2026-10-29T00:00:00Z");
  assert.equal(spentInWeek([{ cost: 5, since: "2026-10-25T00:00:00Z" }, { cost: 7, since: "2026-10-01T00:00:00Z" }, { cost: null, since: "2026-10-28T00:00:00Z" }], now), 5);
});

test("planSells はラインナップ・保有期間・買値を守る", () => {
  const now = Date.parse("2026-10-29T00:00:00Z");
  const r = planSells([
    { card: "x", ask: 9, cost: 5, since: "2026-09-01T00:00:00Z" },
    { card: "y", ask: 9, cost: 5, since: "2026-10-25T00:00:00Z" },
    { card: "z", ask: 4, cost: 5, since: "2026-09-01T00:00:00Z" },
    { card: "w", ask: 9, cost: 5, since: "2026-09-01T00:00:00Z" },
    { card: "v", ask: null, cost: 5, since: "2026-09-01T00:00:00Z" },
  ], { minHoldDays: 14, neverBelowCost: true }, new Set(["w"]), now);
  assert.deepEqual(r.map((x) => [x.ok, x.price]), [[true, 9], [false, undefined], [true, 5], [false, undefined], [false, undefined]]);
  assert.match(r[1].why, /14 日以内/);
  assert.match(r[3].why, /ラインナップ/);
});

test("buildApprovals は種類ごとの承認を作り、署名は秘密鍵で検証できる", () => {
  const pk = generateKey();
  const order = { __typename: "StarkexLimitOrderAuthorizationRequest", vaultIdSell: 1, vaultIdBuy: 2, amountSell: "100", amountBuy: "200",
    tokenSell: "0x1", tokenBuy: "0x2", nonce: 3, expirationTimestamp: 438953, feeInfo: null };
  const fiat = { __typename: "MangopayWalletTransferAuthorizationRequest", amount: 660, currency: "USD", mangopayWalletId: "w1", nonce: 4, operationHash: "h" };
  const [a, b] = buildApprovals([{ fingerprint: "f1", request: order }, { fingerprint: "f2", request: fiat }], (req) => signAuthorizationRequest(pk, req));
  assert.deepEqual(Object.keys(a), ["fingerprint", "starkexLimitOrderApproval"]);
  assert.deepEqual(Object.keys(b), ["fingerprint", "mangopayWalletTransferApproval"]);
  assert.equal(b.mangopayWalletTransferApproval.nonce, 4);
  assert.ok(verifyLimitOrder(exportPublicKey(pk), signable(order), a.starkexLimitOrderApproval.signature));
  assert.equal(signable({ __typename: "StarkexTransferAuthorizationRequest", amount: "5", feeInfoUser: { feeLimit: "1" } }).feeInfoUser.feeLimit, 1n);
  assert.throws(() => buildApprovals([{ fingerprint: "f", request: { __typename: "Unknown" } }], () => ({})), /知らない承認/);
});
