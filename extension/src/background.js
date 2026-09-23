// 価格データの取得とキャッシュ(service worker)。
// content script からの {type: "getData"} に応じて、ゲームごとの価格JSONを6時間キャッシュして
// 配列で返す。取得失敗時はそのゲームの前回キャッシュを返す。
const SOURCES = [
  { id: "pokeca", url: "https://pokeca-kaigai.com/api/cards.json" },
  { id: "yugioh", url: "https://pocketduel.tokyo/api/cards.json" },
];
const CACHE_TTL_MS = 6 * 3600e3; // サイト側の更新は1日2回なので6時間で十分

async function getSource({ id, url }, force) {
  const key = `cache:${id}`;
  const { [key]: cache } = await chrome.storage.local.get(key);
  if (!force && cache && Date.now() - cache.savedAt < CACHE_TTL_MS) return cache.data;
  try {
    const res = await fetch(url, { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    // サイト側のデータ欠如(available:false)では前回キャッシュを上書きしない
    if (!data.available) return cache?.data ?? null;
    await chrome.storage.local.set({ [key]: { data, savedAt: Date.now() } });
    return data;
  } catch (err) {
    console.warn(`pokeca-checker: ${id} fetch failed`, err);
    return cache?.data ?? null;
  }
}

async function getData({ force = false } = {}) {
  const all = await Promise.all(SOURCES.map((s) => getSource(s, force)));
  return all.filter(Boolean);
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type === "getData") {
    getData({ force: msg.force }).then(sendResponse);
    return true; // 非同期で sendResponse する
  }
  return false;
});
