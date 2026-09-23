// ポップアップ: 表示のON/OFFとローン試算の条件
const DEFAULTS = { enabled: true, loanRate: 1.0, loanYears: 35 };
const $ = (id) => document.getElementById(id);

chrome.storage.sync.get(DEFAULTS).then((v) => {
  $("enabled").checked = v.enabled;
  $("loanRate").value = v.loanRate;
  $("loanYears").value = v.loanYears;
});
$("enabled").addEventListener("change", (e) =>
  chrome.storage.sync.set({ enabled: e.target.checked }),
);
for (const id of ["loanRate", "loanYears"]) {
  $(id).addEventListener("change", (e) => {
    const n = Number(e.target.value);
    if (Number.isFinite(n) && n >= Number(e.target.min) && n <= Number(e.target.max)) {
      chrome.storage.sync.set({ [id]: n });
    }
  });
}
