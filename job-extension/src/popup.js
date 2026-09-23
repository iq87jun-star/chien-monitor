// ポップアップ: 表示のON/OFF
const enabledBox = document.getElementById("enabled");
chrome.storage.sync.get("enabled").then(({ enabled = true }) => {
  enabledBox.checked = enabled;
});
enabledBox.addEventListener("change", () => {
  chrome.storage.sync.set({ enabled: enabledBox.checked });
});
