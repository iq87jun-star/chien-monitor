// 認証アプリを失くした時の救済: SORARE_OTP_SECRET から今と次の 2 回分の 6 桁コードを作り、Discord に送って約 2 分後に消す。
// 秘密鍵そのものは出さない。ログにもコードは出さない。使い方: Actions の sorare を手動実行し「otp」にチェック
import { totp } from "./src/api.js";

const { SORARE_OTP_SECRET: secret, SORARE_DISCORD_WEBHOOK: hook } = process.env;
if (!secret || !hook) { console.error("SORARE_OTP_SECRET と SORARE_DISCORD_WEBHOOK が必要"); process.exit(1); }

const step = 30e3, now = Date.now(), start = Math.floor(now / step) * step;
const jst = (t) => new Date(t + 9 * 3600e3).toISOString().slice(11, 19);
const lines = [0, 1, 2].map((i) => `\`${totp(secret, start + i * step)}\`  ${jst(start + i * step)}〜${jst(start + (i + 1) * step)}(日本時間)`);
const content = ["**Sorare の 2 段階認証コード**(この時間帯のものを入力。約 2 分後にこのメッセージは消えます)", ...lines].join("\n");

const r = await fetch(`${hook}?wait=true`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ content }) });
if (!r.ok) { console.error(`Discord 送信失敗 HTTP ${r.status}`); process.exit(1); }
const { id } = await r.json();
console.log("コードを Discord に送った(ログには出さない)。120 秒後に消す");
await new Promise((res) => setTimeout(res, 120e3));
const d = await fetch(`${hook}/messages/${id}`, { method: "DELETE" });
console.log(d.ok ? "消した" : `削除失敗 HTTP ${d.status}(Discord で手で消してください)`);
