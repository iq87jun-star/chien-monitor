// 価格データの取得とキャッシュ(service worker)。
// content script からの {type: "getData"} に応じて、6時間キャッシュした
// pokeca-kaigai.com の価格JSONを返す。取得失敗時は前回キャッシュを返す。
const DATA_URL = "https://pokeca-kaigai.com/api/cards.json";
const CACHE_TTL_MS = 6 * 3600e3; // サイト側の更新は1日2回なので6時間で十分

async function getData({ force = false } = {}) {
  const { cache } = await chrome.storage.local.get("cache");
  if (!force && cache && Date.now() - cache.savedAt < CACHE_TTL_MS) return cache.data;
  try {
    const res = await fetch(DATA_URL, { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    // サイト側のデータ欠如(available:false)では前回キャッシュを上書きしない
    if (!data.available) return cache?.data ?? null;
    await chrome.storage.local.set({ cache: { data, savedAt: Date.now() } });
    return data;
  } catch (err) {
    console.warn("pokeca-checker: fetch failed", err);
    return cache?.data ?? null;
  }
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type === "getData") {
    getData({ force: msg.force }).then(sendResponse);
    return true; // 非同期で sendResponse する
  }
  return false;
});
