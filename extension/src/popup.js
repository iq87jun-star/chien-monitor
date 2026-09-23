// ポップアップ: 表示のON/OFFとデータ更新日時の確認
const enabledBox = document.getElementById("enabled");
const statusEl = document.getElementById("status");

function showStatus(data) {
  if (!data) {
    statusEl.textContent = "データを取得できませんでした(通信状況を確認してください)";
    return;
  }
  const when = new Date(data.fetchedAt).toLocaleString("ja-JP");
  statusEl.textContent = `${data.cards.length.toLocaleString()}枚のデータ(${when}時点)`;
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
