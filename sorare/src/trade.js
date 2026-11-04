// 自動売買(SORARE_TRADE=true の時だけ実行。それ以外は「実行予定」を返すだけ)。
// 購入: prepareAcceptOffer → 秘密鍵で署名(src/sign.js) → acceptOffer。出品: prepareOffer → 署名 → createSingleSaleOffer。
// 入力の形は API のエラーメッセージで確かめたもの。上限の判定(planBuys・planSells)は API を呼ばない純粋な関数(test/trade.test.js)。
import { randomUUID } from "node:crypto";
import { createSigner, buildApprovals, AUTH } from "./sign.js";
import { usd, rates, setRates } from "./api.js";

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

// 出品額(USD)を、出品する通貨の receiveAmount に。USD・EUR はセント、ETH は wei(gwei 単位で丸める)
export function toReceiveAmount(priceUsd, currency, { eurUsd, ethUsd } = rates) {
  if (currency === "USD") return { amount: String(Math.round(priceUsd * 100)), currency };
  if (currency === "EUR") return { amount: String(Math.round((priceUsd / eurUsd) * 100)), currency };
  if (currency === "WEI") {
    if (!ethUsd) throw new Error("ETH のレートが読めない");
    return { amount: (BigInt(Math.round((priceUsd / ethUsd) * 1e9)) * 10n ** 9n).toString(), currency };
  }
  throw new Error(`扱わない通貨: ${currency}`);
}

export function createTrader(gql, { privateKey: rawKey, currency = "USD" }) {
  // 鍵(Ethereum の秘密鍵)から署名用の鍵を 1 回だけ作る。形が違えば、最初の売買で理由を出して止まる
  let signer = null;
  const getSigner = async () => (signer ??= await createSigner(rawKey));
  const errs = (d, what) => { if (d?.errors?.length) throw new Error(`${what}: ` + d.errors.map((e) => e.message).join(" / ")); };

  // 今出ている最安の出品を、価格を確かめ直してから買う(提案の後に値上げされていたら買わない)
  async function buy(card, maxPrice) {
    const sig = await getSigner();
    // 決済に使うレートを先に取り、同じレートで出品価格を USD にして上限と比べる
    const ex = (await gql("{ config { exchangeRate { id rates } } }")).config.exchangeRate;
    setRates(ex.rates);
    const exchangeRateId = ex.id;
    const c = (await gql(`query($s: String!) { anyCard(slug: $s) { liveSingleSaleOffer { id settlementCurrencies receiverSide { amounts { usdCents eurCents wei } } } } }`, { s: card })).anyCard;
    const offer = c?.liveSingleSaleOffer;
    if (!offer) throw new Error("出品が無くなった");
    if (offer.settlementCurrencies && !offer.settlementCurrencies.includes(currency)) throw new Error(`この出品は ${currency} で買えない(売り手の受け取り: ${offer.settlementCurrencies.join("・")})`);
    const price = usd(offer.receiverSide?.amounts);
    // ユーロ・ETH 建ての出品は、換算レートが少し動くだけで USD の額が変わる。値上げだけを止めるよう、2%(最低 2 セント)までの差は許す
    const limit = maxPrice + Math.max(0.02, maxPrice * 0.02);
    if (price == null || price > limit) throw new Error(`価格が変わった($${price?.toFixed(2)} > 上限 $${limit.toFixed(2)})`);
    const settlementInfo = { currency, paymentMethod: "WALLET", exchangeRateId };
    const p = (await gql(`mutation($input: prepareAcceptOfferInput!) { prepareAcceptOffer(input: $input) { ${AUTH} errors { message } } }`,
      { input: { offerId: offer.id, settlementInfo } }, { retries: 0 })).prepareAcceptOffer;
    errs(p, "購入の準備");
    // 念のため、支払う ETH(手数料込み)が上限を超えていないかを、同じレートで USD にして確かめてから署名する(5% まで許す)
    const approvals = await buildApprovals(p.authorizations, sig, (r) => {
      if (r.__typename !== "EthereumBankTransferAuthorizationRequest") return;
      const paid = usd({ wei: (BigInt(r.amount) + BigInt(r.feeAmount || 0)).toString() });
      if (paid == null || paid > maxPrice * 1.05) throw new Error(`支払額が上限を超える($${paid?.toFixed(2)} > $${maxPrice})`);
    });
    const a = (await gql(`mutation($input: acceptOfferInput!) { acceptOffer(input: $input) { tokenOffer { id } errors { message } } }`,
      { input: { offerId: offer.id, settlementInfo, approvals } }, { retries: 0 })).acceptOffer;
    errs(a, "購入");
    return price;
  }

  // 出品額は通貨の最小単位(セント・wei)の文字列で渡し、出品後に実際の出品額を読み直して確かめる
  async function list(card, price) {
    const sig = await getSigner();
    const c = (await gql(`query($s: String!) { anyCard(slug: $s) { assetId liveSingleSaleOffer { id } } }`, { s: card })).anyCard;
    if (c.liveSingleSaleOffer) throw new Error("すでに出品中");
    const receiveAmount = toReceiveAmount(price, currency);
    const p = (await gql(`mutation($input: prepareOfferInput!) { prepareOffer(input: $input) { ${AUTH} errors { message } } }`,
      { input: { type: "SINGLE_SALE_OFFER", sendAssetIds: [c.assetId], receiveAssetIds: [], receiveAmount, settlementCurrencies: [currency] } }, { retries: 0 })).prepareOffer;
    errs(p, "出品の準備");
    const o = (await gql(`mutation($input: createSingleSaleOfferInput!) { createSingleSaleOffer(input: $input) { tokenOffer { id } errors { message } } }`,
      { input: { dealId: randomUUID(), assetId: c.assetId, receiveAmount, settlementCurrencies: [currency], approvals: await buildApprovals(p.authorizations, sig) } }, { retries: 0 })).createSingleSaleOffer;
    errs(o, "出品");
    const after = (await gql(`query($s: String!) { anyCard(slug: $s) { liveSingleSaleOffer { receiverSide { amounts { usdCents eurCents wei } } } } }`, { s: card })).anyCard;
    const listed = usd(after?.liveSingleSaleOffer?.receiverSide?.amounts);
    if (listed == null || Math.abs(listed - price) > Math.max(0.05, price * 0.02)) throw new Error(`出品額が想定と違う(想定 $${price.toFixed(2)} / 実際 $${listed}): アプリで確認して取り消してください`);
    return listed;
  }

  return { buy, list };
}
