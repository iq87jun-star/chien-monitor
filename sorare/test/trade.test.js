import { test } from "node:test";
import assert from "node:assert/strict";
import { planBuys, planSells, spentInWeek } from "../src/trade.js";
import { ethKey, createSigner, buildApprovals } from "../src/sign.js";

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

test("toReceiveAmount は USD をセント、ETH を wei(gwei で丸め)にする", async () => {
  const { toReceiveAmount } = await import("../src/trade.js");
  assert.deepEqual(toReceiveAmount(6.6, "USD", { eurUsd: 1.1, ethUsd: 2000 }), { amount: "660", currency: "USD" });
  assert.deepEqual(toReceiveAmount(5, "WEI", { eurUsd: 1.1, ethUsd: 2000 }), { amount: "2500000000000000", currency: "WEI" });   // $5 / $2000 = 0.0025 ETH
  assert.throws(() => toReceiveAmount(5, "WEI", { eurUsd: 1.1, ethUsd: null }), /ETH のレート/);
});

// Sorare 公式の例(github.com/sorare/api examples/baseBankTransfer.js・solanaKeyPair.js)の鍵と、期待される署名・アドレス
const EX_KEY = "0xa9405b77d085276e4b6e35cf494e83f0533d4751fc13e2fdceb6229330ef5146";
const BASE_REQ = { __typename: "EthereumBankTransferAuthorizationRequest", contractAddress: "0xC887caC5924033340bdd4dd97812738824bCf989", deadline: "1763474595",
  amount: "1000000000000000", feeAmount: "0", proxyAddress: "0x0000000000000000000000000000000000000000", receiverAddress: "0xABd4c585d69Fe6fC7380Ad0bE9a9D932Ba74F709",
  salt: "0x1b6de9fc32e321756431d71322b1c4ed7e45ea1199b7e278dcbc8547bdc7235f", senderAddress: "0xB1a1ed82d0C7DC3f3bA7e2b2613328c64e9d9dA3" };

test("ETH(Base)の支払いの署名が Sorare の例と一致し、Solana の鍵も例のアドレスになる", async () => {
  const signer = await createSigner(` "${EX_KEY.toUpperCase().replace("0X", "0x")}"\n`);
  assert.equal(signer.solAddress, "8ixw6XQW2tuZhc1xgbhh6bq6YvL5K5nXLsN9LjrzMrxq");
  const [a] = await buildApprovals([{ fingerprint: "982b", request: BASE_REQ }], signer);
  assert.deepEqual(a, { fingerprint: "982b", ethereumBankTransferApproval: { deadline: BASE_REQ.deadline, salt: BASE_REQ.salt,
    signature: "0xc503f3f479dfc8c2a76ca8cdf336b0a270cda0ae407fe5270a87b7cdacd2efb8046ccb6e31a7853e22a7541b67f2c49a6ae8cf006673ed17d6995aeb3e624fbf1c" } });
});

test("buildApprovals は送り手のアドレスが鍵と違う・知らない種類・check の拒否で署名せずに止める", async () => {
  const signer = await createSigner(EX_KEY);
  await assert.rejects(buildApprovals([{ fingerprint: "f", request: { ...BASE_REQ, senderAddress: "0x0000000000000000000000000000000000000001" } }], signer), /アドレスが一致しない/);
  await assert.rejects(buildApprovals([{ fingerprint: "f", request: { __typename: "StarkexTransferAuthorizationRequest" } }], signer), /扱わない承認/);
  await assert.rejects(buildApprovals([{ fingerprint: "f", request: BASE_REQ }], signer, () => { throw new Error("上限"); }), /上限/);
  const sol = { __typename: "SolanaTokenTransferAuthorizationRequest", leafIndex: 5, merkleTreeAddress: "CS7kYFjkSW9iPmCZpmNv5jwyE9FmLzR95ag2bpwtM8uF",
    originator: "Dv8A8XKBz5QARFKZ5Kewdk8myCDcne9wiD7ULTanHKU", receiverAddress: "cZq5d4nCqUJoysDh49TPRBSXgFx5dsP9Ho4PVJgYEDY",
    senderAddress: "8ixw6XQW2tuZhc1xgbhh6bq6YvL5K5nXLsN9LjrzMrxq", expirationTimestamp: 1763482762, nonce: "3", transferProxyProgramAddress: "Gz9o1yxV5kVfyC53fFu7StTVeetPZWa2sohzvxJiLxMP" };
  const [b] = await buildApprovals([{ fingerprint: "d4", request: sol }], signer);
  assert.equal(b.solanaTokenTransferApproval.nonce, "3");
  assert.match(b.solanaTokenTransferApproval.signature, /^[1-9A-HJ-NP-Za-km-z]{80,90}$/);
});

test("ethKey は 0x + 64 桁にそろえ、違う形は形だけを理由にして止める", () => {
  assert.equal(ethKey(" " + EX_KEY.slice(2) + "\n"), EX_KEY);
  assert.throws(() => ethKey("0x1234"), /64 桁/);
  assert.throws(() => ethKey("abandon ".repeat(11) + "about"), /64 桁/);
});

test("pickPlan は残高に収まるプランを選び、auto は余裕があればプラスアルファ、足りなければ見送り", async () => {
  const { pickPlan } = await import("../src/trade.js");
  const P = (...prices) => ({ lineup: prices.map((p, i) => ({ id: `p${i}${p}`, price: p })) });
  const cheap = P(1, 1, 1, 1, 1), plus = P(5, 5, 5, 5, 5);
  assert.equal(pickPlan([cheap, plus], "auto", 30, 2).plan, plus);      // 25 + 2 <= 30
  assert.equal(pickPlan([cheap, plus], "auto", 20, 2).plan, cheap);     // 27 > 20 → 最安
  assert.equal(pickPlan([cheap, plus], "cheap", 100, 2).plan, cheap);
  const no = pickPlan([cheap, plus], "cheap", 5, 2);                    // 5 + 2 > 5
  assert.equal(no.plan, null);
  assert.match(no.why, /残高 \$5\.00 では足りない\(必要 \$7\.00\)/);
  assert.equal(pickPlan([cheap], "cheap", 3, 0, new Set(["p01", "p11"])).plan, cheap);   // 手持ち 2 人は数えない(3 枚 $3)
  assert.equal(pickPlan([cheap, plus], "plus", null).plan, plus);         // 残高が読めなければ絞らない
});
