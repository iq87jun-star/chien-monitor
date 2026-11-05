// パソコンが毎朝書き出す口座データ(status.enc)を読む。
// リポジトリは公開なので、パソコン側で AES-256-GCM で暗号化して ai-council-status ブランチに置く。
//   status.enc = base64( nonce 12 バイト | 暗号文 | タグ 16 バイト )
//   鍵 = base64 の 32 バイト(GitHub の Secret AI_COUNCIL_STATUS_KEY とパソコンだけが持つ)
import { createDecipheriv, createCipheriv, randomBytes } from "node:crypto";

export function decryptStatus(b64, keyB64) {
  const key = Buffer.from(keyB64.trim(), "base64");
  if (key.length !== 32) throw new Error("AI_COUNCIL_STATUS_KEY は base64 の 32 バイト");
  const buf = Buffer.from(b64.trim(), "base64");
  const nonce = buf.subarray(0, 12);
  const tag = buf.subarray(buf.length - 16);
  const body = buf.subarray(12, buf.length - 16);
  const d = createDecipheriv("aes-256-gcm", key, nonce);
  d.setAuthTag(tag);
  return JSON.parse(Buffer.concat([d.update(body), d.final()]).toString("utf8"));
}

// テストと、手元で試す用(パソコン側の Python と同じ形式)
export function encryptStatus(obj, keyB64) {
  const key = Buffer.from(keyB64, "base64");
  const nonce = randomBytes(12);
  const c = createCipheriv("aes-256-gcm", key, nonce);
  const body = Buffer.concat([c.update(JSON.stringify(obj), "utf8"), c.final()]);
  return Buffer.concat([nonce, body, c.getAuthTag()]).toString("base64");
}

const usd = (x) => (x == null ? "?" : Math.round(x).toLocaleString("en-US"));

// AI に渡す文章。失格ライン・日次上限までの距離はここで計算する
export function statusText(s, now = new Date(), staleHours = 18) {
  const lines = [];
  const at = new Date(s.updatedAt);
  const ageH = (now - at) / 3600e3;
  lines.push(`取得: ${s.updatedAt}(${ageH.toFixed(1)} 時間前)`);
  if (!(ageH <= staleHours)) lines.push(`⚠️ ${staleHours} 時間以上前のデータ。パソコン側の書き出しが止まっている可能性`);
  for (const a of s.prop ?? []) {
    const toFloor = a.equity != null && a.floor != null ? a.equity - a.floor : null;
    const toDaily = a.equity != null && a.dailyLimit != null ? a.equity - a.dailyLimit : null;
    const pos = (a.positions ?? []).map((p) => `${p.symbol} ${p.side} ${p.lots}(${p.profit >= 0 ? "+" : ""}${usd(p.profit)})`);
    const dup = duplicates(a.positions ?? []);
    lines.push(
      `- ${a.name}: 残高 ${usd(a.balance)} / equity ${usd(a.equity)} / 失格まで ${usd(toFloor)} / 日次上限まで ${usd(toDaily)}` +
        (a.currency ? `(${a.currency})` : ""),
    );
    if (pos.length) lines.push(`  - 建玉: ${pos.join("、")}`);
    if (dup.length) lines.push(`  - ⚠️ 同じ銘柄・同じ向きが複数: ${dup.join("、")}`);
    if (a.notes) lines.push(`  - メモ: ${a.notes}`);
  }
  const t = s.theoption;
  if (t) {
    lines.push(`- theoption 実口座: 残高 ${t.balance == null ? "?" : `${t.balance.toLocaleString("ja-JP")} 円`}`);
    for (const r of t.recent ?? []) lines.push(`  - ${r.date} ${r.leg} ${r.result ?? ""} ${r.pnl == null ? "" : `${r.pnl >= 0 ? "+" : ""}${r.pnl} 円`}`.trimEnd());
    for (const e of t.errors ?? []) lines.push(`  - エラー: ${e}`);
    if (t.notes) lines.push(`  - メモ: ${t.notes}`);
  }
  for (const w of s.warnings ?? []) lines.push(`- ⚠️ ${w}`);
  return lines.join("\n");
}

function duplicates(positions) {
  const n = {};
  for (const p of positions) n[`${p.symbol} ${p.side}`] = (n[`${p.symbol} ${p.side}`] ?? 0) + 1;
  return Object.entries(n).filter(([, c]) => c > 1).map(([k, c]) => `${k} ×${c}`);
}
