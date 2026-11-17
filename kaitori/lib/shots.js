// 査定ページ(index.html・check.html)で相談番号を出したあと、査定に使ったスクショをメルルに送る。
// 本人が「スクショも送る」にチェックしたときだけ。1枚ずつ送り、送れた枚数を返す(失敗しても相談番号はそのまま使える)
export const SHOTS_LABEL = "査定に使ったスクショもメルルに送る(UIDが写っていても、メルルの管理画面だけで使います)";

export async function sendShots(api, no, sid, images) {
  let sent = 0;
  for (const im of images.slice(0, 6)) {
    try {
      const res = await fetch(`${api}/api/lead/${no}/shot`, {
        method: "POST",
        headers: { "content-type": "text/plain" },
        body: JSON.stringify({ sid, mime: im.media_type, data: im.data }),
      });
      if ((await res.json()).ok) sent++;
    } catch {}
  }
  return sent;
}
