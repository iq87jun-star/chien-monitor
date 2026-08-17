// ステップ1: データ収集
// tarkov.dev GraphQL API からアイテム相場を取得し data/raw/ に保存する。
// APIが一時的に落ちていても既存の生データを壊さないよう、失敗時は警告のみで正常終了する。
import fs from "node:fs/promises";
import path from "node:path";
import { RAW_DIR, USER_AGENT, TARKOV_GRAPHQL, ITEMS_QUERY } from "./config.mjs";

async function fetchGraphql(query, retries = 3) {
  for (let attempt = 0; ; attempt++) {
    try {
      const res = await fetch(TARKOV_GRAPHQL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          "User-Agent": USER_AGENT,
        },
        body: JSON.stringify({ query }),
      });
      // tarkov.devはサーバー障害時にHTTPエラー+{"errors":[...]}を返すことがある
      const body = await res.json().catch(() => null);
      if (!res.ok || !body || body.errors) {
        const detail = body?.errors
          ? JSON.stringify(body.errors).slice(0, 200)
          : `HTTP ${res.status}`;
        throw new Error(`GraphQL request failed: ${detail}`);
      }
      return body;
    } catch (err) {
      if (attempt >= retries) throw err;
      const waitMs = 2000 * 2 ** attempt;
      console.warn(`fetch failed (${err.message}), retrying in ${waitMs}ms`);
      await new Promise((r) => setTimeout(r, waitMs));
    }
  }
}

export async function fetchAll() {
  await fs.mkdir(RAW_DIR, { recursive: true });

  let body;
  try {
    body = await fetchGraphql(ITEMS_QUERY);
  } catch (err) {
    // 失敗時は既存の data/raw/items.json を上書きしない(前回データでサイトを維持する)
    console.warn(`fetch: tarkov.dev unavailable — keeping existing raw data (${err.message})`);
    return { ok: false };
  }

  const items = body.data?.items;
  if (!Array.isArray(items) || items.length === 0) {
    console.warn("fetch: response had no items — keeping existing raw data");
    return { ok: false };
  }

  await fs.writeFile(
    path.join(RAW_DIR, "items.json"),
    JSON.stringify({ fetchedAt: new Date().toISOString(), items }, null, 1),
  );
  console.log(`fetch: done (${items.length} items)`);
  return { ok: true };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  fetchAll().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
