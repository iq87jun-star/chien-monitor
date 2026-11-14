// OpenRouter のクレジット切れ(残高不足・キーの上限)かどうか。そうなら自動実行を止める
export function isFundsError(status, text = "") {
  return status === 402 || /insufficient (credits|funds|balance)|out of credits|key limit|credit limit|requires more credits/i.test(text);
}

export const FUNDS_NOTICE = `⛔ **OpenRouter のクレジットが尽きたため、AI 点検会議・新規開拓会議の自動実行を止めました。**
再開するときは、OpenRouter でクレジットを足す(またはキーの上限を上げる)→ GitHub の Actions → ai-council → 「Enable workflow」を押してください。`;
