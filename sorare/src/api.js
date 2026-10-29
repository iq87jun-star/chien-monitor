// Sorare GraphQL API の呼び出し。イントロスペクションは無効なので、使うフィールドはエラーメッセージで確かめたものだけ。
// 未ログインの上限は depth 7・complexity 500(APIKEY 付きなら 13・30000)。ルートで同じフィールドを別名で並べるのも不可。
import bcrypt from "bcryptjs";
import { createHmac } from "node:crypto";

const API = "https://api.sorare.com/graphql";
const AUD = "chien-sorare";

export class SorareError extends Error {}

export function createClient({ apiKey = "", fetchImpl = fetch, sleep = (ms) => new Promise((r) => setTimeout(r, ms)) } = {}) {
  let jwt = "";
  async function gql(query, variables = {}, { retries = 4 } = {}) {
    const headers = { "content-type": "application/json" };
    if (apiKey) headers.APIKEY = apiKey;
    if (jwt) { headers.Authorization = `Bearer ${jwt}`; headers["JWT-AUD"] = AUD; }
    for (let i = 0; ; i++) {
      let body;
      try {
        const res = await fetchImpl(API, { method: "POST", headers, body: JSON.stringify({ query, variables }) });
        if (res.status === 429 || res.status >= 500) throw new Error(`HTTP ${res.status}`);
        body = await res.json();
      } catch (e) {
        if (i >= retries) throw e;
        await sleep(2000 * 2 ** i);
        continue;
      }
      if (body.errors?.length) {
        const msg = body.errors.map((e) => e.message).join(" / ");
        const transient = body.errors.some((e) => /rate|throttl|timeout/i.test(e.message));
        if (transient && i < retries) { await sleep(2000 * 2 ** i); continue; }
        if (!body.data || Object.values(body.data).every((v) => v == null)) throw new SorareError(msg);
      }
      return body.data;
    }
  }

  // パスワードは Sorare の salt で bcrypt してから送る。2段階認証は TOTP の秘密鍵から6桁を作って答える。
  async function signIn({ email, password, otpSecret = "" }) {
    const r = await fetchImpl(`https://api.sorare.com/api/v1/users/${encodeURIComponent(email)}`);
    const { salt } = await r.json();
    if (!salt) throw new SorareError("salt が取得できない(メールアドレスを確認)");
    const sel = `currentUser { slug } otpSessionChallenge jwtToken(aud: "${AUD}") { token expiredAt } errors { message }`;
    let d = (await gql(`mutation($input: signInInput!) { signIn(input: $input) { ${sel} } }`,
      { input: { email, password: bcrypt.hashSync(password, salt) } }, { retries: 0 })).signIn;
    if (d.otpSessionChallenge) {
      if (!otpSecret) throw new SorareError("2段階認証が有効: SORARE_OTP_SECRET を設定してください");
      d = (await gql(`mutation($input: signInInput!) { signIn(input: $input) { ${sel} } }`,
        { input: { otpSessionChallenge: d.otpSessionChallenge, otpAttempt: totp(otpSecret) } }, { retries: 0 })).signIn;
    }
    if (!d.jwtToken?.token) throw new SorareError("ログイン失敗: " + (d.errors || []).map((e) => e.message).join(" / "));
    jwt = d.jwtToken.token;
    return d.currentUser?.slug;
  }

  return { gql, signIn, get authed() { return !!jwt; } };
}

// 秘密鍵は base32 の文字列のほか、QR コードの中身(otpauth://...?secret=...)も受け付ける。空白・ハイフン・= は無視する。
export function normalizeOtpSecret(s) {
  const t = s.trim();
  if (/^otpauth:/i.test(t)) {
    const m = t.match(/[?&]secret=([^&]+)/i);
    if (!m) throw new SorareError("SORARE_OTP_SECRET の otpauth URL に secret= が無い");
    return normalizeOtpSecret(decodeURIComponent(m[1]));
  }
  const v = t.replace(/[\s=-]/g, "").toUpperCase();
  if (/^\d{6,8}$/.test(v)) throw new SorareError("SORARE_OTP_SECRET が数字だけ: 認証アプリの6桁のコードではなく、2段階認証を設定する時に出る英字の秘密鍵を登録してください");
  const bad = [...v].filter((c) => !"ABCDEFGHIJKLMNOPQRSTUVWXYZ234567".includes(c));
  if (bad.length) {
    const kinds = [...new Set(bad.map((c) => (/[0189]/.test(c) ? "数字の0・1・8・9" : /[A-Z0-9]/.test(c) ? c : "記号")))];
    throw new SorareError(`SORARE_OTP_SECRET に秘密鍵で使わない文字(${kinds.join("・")})が ${bad.length} 個ある(長さ ${v.length} 文字)。バックアップコードではなく、QR コードの横に出る英字の鍵か otpauth:// の URL を登録してください`);
  }
  return v;
}

export function totp(secret, now = Date.now(), step = 30, digits = 6) {
  const alpha = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const c of normalizeOtpSecret(secret)) bits += alpha.indexOf(c).toString(2).padStart(5, "0");
  const key = Buffer.from(bits.match(/.{8}/g).map((b) => parseInt(b, 2)));
  const msg = Buffer.alloc(8);
  msg.writeBigUInt64BE(BigInt(Math.floor(now / 1000 / step)));
  const h = createHmac("sha1", key).update(msg).digest();
  const o = h[h.length - 1] & 15;
  return String((h.readUInt32BE(o) & 0x7fffffff) % 10 ** digits).padStart(digits, "0");
}

// 換算レート。run.js が Sorare の config.exchangeRate で上書きする(読めない時はユーロ 1.1、ETH は換算しない)
export const rates = { eurUsd: 1.1, ethUsd: null };
export function setRates(r) {
  if (r?.eth?.usd && r?.eth?.eur) { rates.ethUsd = r.eth.usd; rates.eurUsd = r.eth.usd / r.eth.eur; }
}

// 出品価格(receiverSide.amounts)を USD に。ETH 建て(wei)は ETH のレートがある時だけ換算する
export function usd(amounts, { eurUsd, ethUsd } = rates) {
  if (!amounts) return null;
  if (amounts.usdCents) return amounts.usdCents / 100;
  if (amounts.eurCents) return (amounts.eurCents / 100) * eurUsd;
  if (amounts.wei && ethUsd) return (Number(amounts.wei) / 1e18) * ethUsd;
  return null;
}
