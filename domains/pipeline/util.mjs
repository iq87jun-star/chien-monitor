// 共通ユーティリティ(全ステップ共有)
import fs from "node:fs/promises";
import path from "node:path";
import { USER_AGENT } from "./config.mjs";

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function readJson(file, fallback = null) {
  try {
    return JSON.parse(await fs.readFile(file, "utf8"));
  } catch {
    return fallback;
  }
}

export async function writeJson(file, data, space = 1) {
  await fs.mkdir(path.dirname(file), { recursive: true });
  await fs.writeFile(file, JSON.stringify(data, null, space));
}

// 入力ファイル(1行1ドメイン、#以降はコメント)を読む。無ければ空配列
export async function readLines(file) {
  let text;
  try {
    text = await fs.readFile(file, "utf8");
  } catch {
    return [];
  }
  return text
    .split("\n")
    .map((l) => l.replace(/#.*$/, "").trim().toLowerCase())
    .filter(Boolean);
}

// リトライ付きfetch。404は「未登録」の判定に使うため正常応答として返し、
// 429/5xxとネットワークエラーのみ指数バックオフで再試行する
export async function fetchWithRetry(url, opts = {}, retries = 2) {
  for (let attempt = 0; ; attempt++) {
    try {
      const res = await fetch(url, {
        ...opts,
        headers: { "User-Agent": USER_AGENT, ...(opts.headers ?? {}) },
      });
      if (res.ok || res.status === 404) return res;
      if (attempt >= retries || (res.status < 500 && res.status !== 429)) {
        throw new Error(`HTTP ${res.status} for ${url}`);
      }
    } catch (err) {
      if (attempt >= retries) throw err;
    }
    await sleep(1500 * 2 ** attempt);
  }
}

// 同時実行数を絞ったmap。fnが投げてもnullに落として全体を続行する
export async function mapLimit(items, limit, fn) {
  const results = new Array(items.length);
  let next = 0;
  async function worker() {
    while (next < items.length) {
      const i = next++;
      try {
        results[i] = await fn(items[i], i);
      } catch (err) {
        console.warn(`  skip ${items[i]?.domain ?? items[i]}: ${err.message}`);
        results[i] = null;
      }
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, worker));
  return results;
}
