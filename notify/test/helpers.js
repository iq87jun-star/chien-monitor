// テスト用: node:sqlite で D1 と同じ口のデータベースを作り、相場データと Discord を偽装する
import { DatabaseSync } from "node:sqlite";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

export function memoryDb() {
  const raw = new DatabaseSync(":memory:");
  for (const f of fs.readdirSync(path.join(ROOT, "migrations")).sort()) {
    raw.exec(fs.readFileSync(path.join(ROOT, "migrations", f), "utf8"));
  }
  return {
    raw,
    async all(sql, params = []) {
      return raw
        .prepare(sql)
        .all(...params)
        .map((r) => ({ ...r }));
    },
    async run(sql, params = []) {
      return Number(raw.prepare(sql).run(...params).changes);
    },
  };
}

// 3ゲーム分の小さな相場データ(実データと同じ形式)
export function priceData({ pokecaEur = 10, fetchedAt = "2026-09-23T09:00:00Z" } = {}) {
  return {
    "https://pokeca-kaigai.com/api/cards.json": {
      v: 1,
      available: true,
      fetchedAt,
      eurJpy: 180,
      sets: [{ id: "SV2a", name: "ポケモンカード151", cardCount: 165 }],
      cards: [
        ["SV2a", "201", "リザードンex", pokecaEur, 11, 12],
        ["SV2a", "006", "リザードンex", 2, 2, 2],
        ["SV2a", "025", "ピカチュウ", 0.5, null, null],
      ],
    },
    "https://pocketduel.tokyo/api/cards.json": {
      v: 1,
      available: true,
      game: "yugioh",
      fetchedAt,
      eurJpy: 180,
      sets: [],
      cards: [
        [
          "",
          "",
          ["『灰流うらら』", "『はるうらら』"],
          3,
          null,
          null,
          '"Ash Blossom & Joyous Spring"',
        ],
        ["", "", ["セブン"], 0.4, null, null, '"7"'],
      ],
    },
    "https://pokeca-kaigai.com/api/onepiece.json": {
      v: 1,
      available: true,
      game: "onepiece",
      fetchedAt,
      rateJpy: 150,
      sets: [],
      variantLabels: { normal: "通常版", parallel: "パラレル" },
      cards: [
        ["", "OP05-119", "Monkey.D.Luffy", 10, null, null, null, "normal"],
        ["", "OP05-119", "Monkey.D.Luffy", 8, null, null, null, "normal"],
        ["", "OP05-119", "Monkey.D.Luffy", 300, null, null, null, "parallel"],
      ],
    },
  };
}

// 相場データの URL と Discord のウェブフックに応答する偽の fetch。
// discord.status で Discord の応答を変えられ、posts に投稿内容が残る
export function fakeFetch(data) {
  const state = { data, posts: [], discord: { status: 204, exists: true }, stripe: [] };
  const fetchImpl = async (url, init = {}) => {
    if (state.data[url]) return Response.json(state.data[url]);
    if (url.startsWith("https://api.stripe.com/")) {
      const path = url.slice("https://api.stripe.com".length);
      state.stripe.push({
        method: init.method,
        path,
        auth: init.headers?.authorization,
        params: Object.fromEntries(new URLSearchParams(init.body ?? "")),
      });
      if (path === "/v1/checkout/sessions") {
        return Response.json({ url: "https://checkout.stripe.com/c/pay/cs_test_1" });
      }
      if (path === "/v1/billing_portal/sessions") {
        return Response.json({ url: "https://billing.stripe.com/p/session/test_1" });
      }
      if (path.startsWith("/v1/subscriptions/")) return Response.json({ status: "canceled" });
      return Response.json({ error: { message: "unknown" } }, { status: 404 });
    }
    if (url.startsWith("https://discord.com/api/webhooks/")) {
      if ((init.method ?? "GET") === "GET") {
        return new Response(state.discord.exists ? "{}" : "", {
          status: state.discord.exists ? 200 : 404,
        });
      }
      state.posts.push({ url, body: JSON.parse(init.body) });
      return new Response(null, { status: state.discord.status });
    }
    return new Response("not found", { status: 404 });
  };
  return { fetchImpl, state };
}

export const WEBHOOK =
  "https://discord.com/api/webhooks/123456789012345678/abcdefghijklmnopqrstuvwxyz0123456789ABCD";
export const WEBHOOK2 =
  "https://discord.com/api/webhooks/223456789012345678/bbcdefghijklmnopqrstuvwxyz0123456789ABCD";

export const BILLING = {
  secretKey: "sk_test_123",
  priceId: "price_123",
  webhookSecret: "whsec_test",
  priceLabel: "月額300円",
  apiOrigin: "https://api.stripe.com",
};
