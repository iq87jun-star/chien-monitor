// ポップアップ: 表示のON/OFFとデータ更新日時の確認
const enabledBox = document.getElementById("enabled");
const statusEl = document.getElementById("status");

const GAME_NAMES = { pokeca: "ポケカ", yugioh: "遊戯王", onepiece: "ワンピース" };

function showStatus(all) {
  if (!all?.length) {
    statusEl.textContent = "データを取得できませんでした(通信状況を確認してください)";
    return;
  }
  statusEl.textContent = all
    .map((data) => {
      const game = GAME_NAMES[data.game ?? "pokeca"] ?? data.game;
      const when = new Date(data.fetchedAt).toLocaleString("ja-JP");
      return `${game}: ${data.cards.length.toLocaleString()}枚(${when}時点)`;
    })
    .join(" / ");
}

chrome.storage.sync.get("enabled").then(({ enabled = true }) => {
  enabledBox.checked = enabled;
});
enabledBox.addEventListener("change", () => {
  chrome.storage.sync.set({ enabled: enabledBox.checked });
});
chrome.runtime.sendMessage({ type: "getData" }).then(showStatus);
document.getElementById("refresh").addEventListener("click", async () => {
  statusEl.textContent = "取得中…";
  showStatus(await chrome.runtime.sendMessage({ type: "getData", force: true }));
});
