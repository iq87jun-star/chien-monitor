// コメントの選別と返答テキストの検品
// poe1/poe2のvalidate.mjsと同じ思想: 生成物は検品ゲートを通過したものだけ外に出す。
import {
  COMMENT_MAX_CHARS,
  REPLY_MAX_CHARS,
  NG_WORDS,
  USER_COOLDOWN_MS,
} from "./config.mjs";

const lastRepliedAt = new Map(); // authorChannelId -> 最終返答時刻

const URL_RE = /https?:\/\//i;
// 電話番号・メールアドレスらしき並び(個人情報の読み上げ事故を防ぐ)
const PII_RE = /([0-9]{2,4}-[0-9]{2,4}-[0-9]{3,4}|[\w.+-]+@[\w-]+\.[\w.]+)/;

export function containsNgWord(text) {
  return NG_WORDS.some((w) => text.includes(w));
}

// 返事の対象にするコメントか判定。skipする理由を返す(nullなら返事の対象)
export function skipReason(msg, ownChannelId) {
  if (ownChannelId && msg.authorChannelId === ownChannelId) return "own message";
  if (msg.text.startsWith("!")) return "command";
  if (msg.text.length > COMMENT_MAX_CHARS) return "too long";
  if (URL_RE.test(msg.text)) return "contains url";
  if (PII_RE.test(msg.text)) return "possible pii";
  if (containsNgWord(msg.text)) return "ng word";
  const last = lastRepliedAt.get(msg.authorChannelId) || 0;
  if (Date.now() - last < USER_COOLDOWN_MS) return "user cooldown";
  return null;
}

export function markReplied(authorChannelId) {
  lastRepliedAt.set(authorChannelId, Date.now());
}

// 生成された返答の検品。通過しなければ配信に載せない
export function validateReply(text) {
  if (!text || !text.trim()) return "empty";
  if (text.length > REPLY_MAX_CHARS * 2) return "too long";
  if (containsNgWord(text)) return "ng word";
  if (URL_RE.test(text)) return "contains url";
  return null;
}
