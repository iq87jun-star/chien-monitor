// 在庫一覧(お客様向け)の表紙画像を、管理画面のカードから入れる・外す(admin.html・stock.html で共通)
// 表紙は在庫・代理出品に1枚ずつ。UID が写っていない画像にする
export const coverField = (kind, id, coverId) => `<div class="cover-field" data-cover-kind="${kind}" data-cover-id="${id}">
  <span class="muted">🖼 一覧の表紙(1枚・UIDなし)</span>
  ${coverId ? `<img data-cover-img="${coverId}" alt="表紙" style="width:96px;border-radius:6px;border:1px solid var(--line);vertical-align:middle" />` : `<span class="muted">未設定(文字の表紙になります)</span>`}
  <label class="muted" style="display:inline-block;cursor:pointer;text-decoration:underline">${coverId ? "入れ替える" : "画像を選ぶ"}<input type="file" accept="image/*" data-cover-file hidden /></label>
  ${coverId ? `<button type="button" class="sub" data-cover-del style="font-size:12px;padding:4px 8px">外す</button>` : ""}
</div>`;

async function shrink(file) {
  const bmp = await createImageBitmap(file);
  const scale = Math.min(1, 1200 / Math.max(bmp.width, bmp.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bmp.width * scale);
  canvas.height = Math.round(bmp.height * scale);
  canvas.getContext("2d").drawImage(bmp, 0, 0, canvas.width, canvas.height);
  return { mime: "image/jpeg", data: canvas.toDataURL("image/jpeg", 0.88).split(",")[1], w: canvas.width, h: canvas.height };
}

// root の中の表紙欄を動かす。fetchAuth(path, init) は合言葉つきの fetch、done は保存後に呼ぶ
export function bindCovers(root, fetchAuth, done, toast) {
  root.addEventListener("change", async (e) => {
    const input = e.target.closest("[data-cover-file]");
    if (!input?.files?.[0]) return;
    const f = input.closest("[data-cover-kind]");
    try {
      const res = await fetchAuth(`/api/cover/${f.dataset.coverKind}/${f.dataset.coverId}`, { method: "PUT", body: JSON.stringify(await shrink(input.files[0])) });
      if (!(await res.json()).ok) throw new Error(res.status);
      toast("表紙を入れました");
      await done();
    } catch (err) { toast(`表紙を入れられませんでした(${err.message})`); }
  });
  root.addEventListener("click", async (e) => {
    if (!e.target.closest("[data-cover-del]")) return;
    const f = e.target.closest("[data-cover-kind]");
    if (!confirm("表紙を外しますか?")) return;
    await fetchAuth(`/api/cover/${f.dataset.coverKind}/${f.dataset.coverId}`, { method: "DELETE" });
    toast("表紙を外しました");
    await done();
  });
}
// 表示した後に、表紙の画像を合言葉つきで読み込む
export async function loadCoverImages(root, fetchAuth) {
  for (const img of root.querySelectorAll("[data-cover-img]:not([src])")) {
    const res = await fetchAuth(`/api/image/${img.dataset.coverImg}`);
    if (res.ok) img.src = URL.createObjectURL(await res.blob());
  }
}
