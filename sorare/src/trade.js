// 自動売買(SORARE_TRADE=true の時だけ実行。それ以外は「実行予定」を返すだけ)。
// 購入: prepareAcceptOffer → 秘密鍵で署名 → acceptOffer。出品: prepareOffer → 署名 → createSingleSaleOffer。
// 入力の形は API のエラーメッセージで確かめたもの。上限の判定(planBuys・planSells)は API を呼ばない純粋な関数(test/trade.test.js)。
import { randomUUID } from "node:crypto";
import { signAuthorizationRequest } from "@sorare/crypto";
import { usd } from "./api.js";

const WEEK = 7 * 864e5;

// 買う: 1 枚 perCardMaxUsd 以下、直近 7 日の購入額 + 今回の合計が weeklyMaxUsd 以下。超える分は理由付きで外す
export function planBuys(lineup, { perCardMaxUsd, weeklyMaxUsd }, spentThisWeek) {
  let spent = spentThisWeek;
  return lineup.map((c) => {
    if (c.price == null) return { ...c, ok: false, why: "価格不明" };
    if (c.price > perCardMaxUsd) return { ...c, ok: false, why: `1枚の上限 $${perCardMaxUsd} を超える` };
    if (spent + c.price > weeklyMaxUsd) return { ...c, ok: false, why: `週の上限 $${weeklyMaxUsd} を超える(使用済み $${spent.toFixed(2)})` };
    spent += c.price;
    return { ...c, ok: true };
  });
}

// 直近 7 日に買ったカードの合計額(所有履歴の最後の取引がこの 7 日以内のもの)
export function spentInWeek(cards, now = Date.now()) {
  return cards.filter((c) => c.cost && c.since && now - Date.parse(c.since) < WEEK).reduce((s, c) => s + c.cost, 0);
}

// 売る: ラインナップに入れたカード、買ってから minHoldDays 日以内のカード、出品中のカードは出さない。
// 出品価格は ask(目安)だが、買値が分かれば買値より下では出さない(値上がり以外の理由で売る時も損を確定させない)
export function planSells(cands, { minHoldDays = 14, neverBelowCost = true } = {}, inLineup = new Set(), now = Date.now()) {
  return cands.map((c) => {
    if (inLineup.has(c.card)) return { ...c, ok: false, why: "今節のラインナップに入っている" };
    if (c.since && now - Date.parse(c.since) < minHoldDays * 864e5) return { ...c, ok: false, why: `買ってから ${minHoldDays} 日以内` };
    if (c.listed) return { ...c, ok: false, why: "出品中" };
    if (c.ask == null) return { ...c, ok: false, why: "相場なし" };
    const price = neverBelowCost && c.cost ? Math.max(c.ask, c.cost) : c.ask;
    return { ...c, ok: true, price };
  });
}

// 署名ライブラリは StarkEx の金額(amountSell・amountBuy・amount・feeLimit)を BigInt で受け取る。API は文字列で返すので変換する。
// 法定通貨の送金(Mangopay)は文字列のまま連結して署名するので変えない
export function signable(request) {
  if (request.__typename === "MangopayWalletTransferAuthorizationRequest") return request;
  const r = { ...request };
  for (const k of ["amountSell", "amountBuy", "amount"]) if (r[k] != null) r[k] = BigInt(r[k]);
  for (const k of ["feeInfo", "feeInfoUser"]) if (r[k]) r[k] = { ...r[k], feeLimit: BigInt(r[k].feeLimit) };
  return r;
}

// 署名済みの承認。種類ごとに入れるフィールドが違う
export function buildApprovals(authorizations, sign) {
  return authorizations.map(({ fingerprint, request }) => {
    const signature = sign(signable(request));
    switch (request.__typename) {
      case "StarkexTransferAuthorizationRequest":
        return { fingerprint, starkexTransferApproval: { nonce: request.nonce, expirationTimestamp: request.expirationTimestamp, signature } };
      case "StarkexLimitOrderAuthorizationRequest":
        return { fingerprint, starkexLimitOrderApproval: { nonce: request.nonce, expirationTimestamp: request.expirationTimestamp, signature } };
      case "MangopayWalletTransferAuthorizationRequest":
        return { fingerprint, mangopayWalletTransferApproval: { nonce: request.nonce, signature } };
      default:
        throw new Error(`知らない承認の種類: ${request.__typename}`);
    }
  });
}

const AUTH = `authorizations { fingerprint request { __typename
  ... on StarkexLimitOrderAuthorizationRequest { vaultIdSell vaultIdBuy amountSell amountBuy tokenSell tokenBuy nonce expirationTimestamp feeInfo { feeLimit tokenId sourceVaultId } }
  ... on StarkexTransferAuthorizationRequest { amount condition expirationTimestamp nonce receiverPublicKey receiverVaultId senderVaultId token feeInfoUser { feeLimit tokenId sourceVaultId } }
  ... on MangopayWalletTransferAuthorizationRequest { amount currency mangopayWalletId nonce operationHash } } }`;

export function createTrader(gql, { privateKey, currency = "USD" }) {
  const sign = (req) => signAuthorizationRequest(privateKey, req);
  const errs = (d, what) => { if (d?.errors?.length) throw new Error(`${what}: ` + d.errors.map((e) => e.message).join(" / ")); };

  // 今出ている最安の出品を、価格を確かめ直してから買う(提案の後に値上げされていたら買わない)
  async function buy(card, maxPrice) {
    const c = (await gql(`query($s: String!) { anyCard(slug: $s) { liveSingleSaleOffer { id receiverSide { amounts { usdCents eurCents } } } } }`, { s: card })).anyCard;
    const offer = c?.liveSingleSaleOffer;
    if (!offer) throw new Error("出品が無くなった");
    const price = usd(offer.receiverSide?.amounts);
    if (price == null || price > maxPrice + 1e-9) throw new Error(`価格が変わった($${price} > 上限 $${maxPrice})`);
    const exchangeRateId = (await gql("{ config { exchangeRate { id } } }")).config.exchangeRate.id;
    const settlementInfo = { currency, paymentMethod: "WALLET", exchangeRateId };
    const p = (await gql(`mutation($input: prepareAcceptOfferInput!) { prepareAcceptOffer(input: $input) { ${AUTH} errors { message } } }`,
      { input: { offerId: offer.id, settlementInfo } }, { retries: 0 })).prepareAcceptOffer;
    errs(p, "購入の準備");
    // 念のため、法定通貨の送金額(セント)が上限を超えていないかも確かめてから署名する(手数料分 5% まで許す)
    const over = p.authorizations.find((x) => x.request.__typename === "MangopayWalletTransferAuthorizationRequest" && Number(x.request.amount) > maxPrice * 100 * 1.05);
    if (over) throw new Error(`送金額が上限を超える(${over.request.amount} ${over.request.currency} セント)`);
    const a = (await gql(`mutation($input: acceptOfferInput!) { acceptOffer(input: $input) { tokenOffer { id } errors { message } } }`,
      { input: { offerId: offer.id, settlementInfo, approvals: buildApprovals(p.authorizations, sign) } }, { retries: 0 })).acceptOffer;
    errs(a, "購入");
    return price;
  }

  // 出品額はセント単位の文字列で渡し、出品後に実際の出品額を読み直して確かめる
  async function list(card, price) {
    const c = (await gql(`query($s: String!) { anyCard(slug: $s) { assetId liveSingleSaleOffer { id } } }`, { s: card })).anyCard;
    if (c.liveSingleSaleOffer) throw new Error("すでに出品中");
    const receiveAmount = { amount: String(Math.round(price * 100)), currency };
    const p = (await gql(`mutation($input: prepareOfferInput!) { prepareOffer(input: $input) { ${AUTH} errors { message } } }`,
      { input: { sendAssetIds: [c.assetId], receiveAssetIds: [], receiveAmount, settlementCurrencies: [currency] } }, { retries: 0 })).prepareOffer;
    errs(p, "出品の準備");
    const o = (await gql(`mutation($input: createSingleSaleOfferInput!) { createSingleSaleOffer(input: $input) { tokenOffer { id } errors { message } } }`,
      { input: { dealId: randomUUID(), assetId: c.assetId, receiveAmount, settlementCurrencies: [currency], approvals: buildApprovals(p.authorizations, sign) } }, { retries: 0 })).createSingleSaleOffer;
    errs(o, "出品");
    const after = (await gql(`query($s: String!) { anyCard(slug: $s) { liveSingleSaleOffer { receiverSide { amounts { usdCents eurCents } } } } }`, { s: card })).anyCard;
    const listed = usd(after?.liveSingleSaleOffer?.receiverSide?.amounts);
    if (listed == null || Math.abs(listed - price) > Math.max(0.05, price * 0.02)) throw new Error(`出品額が想定と違う(想定 $${price.toFixed(2)} / 実際 $${listed}): アプリで確認して取り消してください`);
    return listed;
  }

  return { buy, list };
}
