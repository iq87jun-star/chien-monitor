// Cloudflare Worker: /api/* は登録API、それ以外は public/ の登録ページ(静的アセット)を返す。
// 値下がりのチェック自体は Worker ではなく GitHub Actions(scripts/check.mjs)で行う
// (相場データの JSON が数百KBあり、Workers 無料プランの CPU 時間では足りないため)。
import { handleApi } from "./api.js";
import { fromD1 } from "./db.js";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname.startsWith("/api/")) {
      try {
        return await handleApi(request, { db: fromD1(env.DB), discordOrigin: env.DISCORD_ORIGIN });
      } catch (err) {
        console.error(err);
        return new Response(JSON.stringify({ error: "サーバーでエラーが起きました" }), {
          status: 500,
          headers: { "content-type": "application/json; charset=utf-8" },
        });
      }
    }
    return env.ASSETS.fetch(request);
  },
};
