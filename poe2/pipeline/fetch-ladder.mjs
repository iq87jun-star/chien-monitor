// フェーズ2-A: 公式ラダーAPIからビルドメタ統計を生成
// GGGのOAuthクライアント(client_credentials)が必要。未設定なら何もせず正常終了する。
// 必要な環境変数: GGG_CLIENT_ID, GGG_CLIENT_SECRET
import fs from "node:fs/promises";
import path from "node:path";
import { SITE_DIR, USER_AGENT } from "./config.mjs";

const TOKEN_URL = "https://www.pathofexile.com/oauth/token";
const API_BASE = "https://api.pathofexile.com";

async function readJson(file, fallback = null) {
  try {
    return JSON.parse(await fs.readFile(file, "utf8"));
  } catch {
    return fallback;
  }
}

async function getToken(clientId, clientSecret) {
  const res = await fetch(TOKEN_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      "User-Agent": USER_AGENT,
    },
    body: new URLSearchParams({
      client_id: clientId,
      client_secret: clientSecret,
      grant_type: "client_credentials",
      scope: "service:leagues:ladder",
    }),
  });
  if (!res.ok) throw new Error(`OAuth token request failed: HTTP ${res.status}`);
  return (await res.json()).access_token;
}

async function fetchLadderPage(token, league, offset, limit = 500) {
  const url = `${API_BASE}/league/${encodeURIComponent(league)}/ladder?realm=poe2&limit=${limit}&offset=${offset}`;
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}`, "User-Agent": USER_AGENT },
  });
  if (!res.ok) throw new Error(`ladder request failed: HTTP ${res.status}`);
  return res.json();
}

export async function fetchLadder() {
  const { GGG_CLIENT_ID, GGG_CLIENT_SECRET } = process.env;
  if (!GGG_CLIENT_ID || !GGG_CLIENT_SECRET) {
    console.log("ladder: GGG_CLIENT_ID/SECRET not set — skipping build meta");
    return;
  }

  const economy = await readJson(path.join(SITE_DIR, "economy.json"));
  const league = economy?.league;
  if (!league) throw new Error("economy.json missing — run aggregate first");

  const token = await getToken(GGG_CLIENT_ID, GGG_CLIENT_SECRET);

  // 上位1,000キャラ(500件×2ページ)。レート制限に配慮して間隔を空ける
  const entries = [];
  for (const offset of [0, 500]) {
    const page = await fetchLadderPage(token, league, offset);
    entries.push(...(page.ladder?.entries ?? []));
    if ((page.ladder?.entries ?? []).length < 500) break;
    await new Promise((r) => setTimeout(r, 1500));
  }
  if (entries.length === 0) throw new Error("ladder returned no entries");

  // クラス(アセンダンシー)分布
  const classCounts = new Map();
  for (const e of entries) {
    const cls = e.character?.class ?? "Unknown";
    classCounts.set(cls, (classCounts.get(cls) ?? 0) + 1);
  }
  const classes = [...classCounts.entries()]
    .map(([name, count]) => ({
      name,
      count,
      pct: Math.round((count / entries.length) * 1000) / 10,
    }))
    .sort((a, b) => b.count - a.count);

  // 上位キャラ一覧
  const top = entries.slice(0, 20).map((e) => ({
    rank: e.rank,
    name: e.character?.name ?? "?",
    class: e.character?.class ?? "?",
    level: e.character?.level ?? 0,
    dead: Boolean(e.dead),
  }));

  const builds = {
    available: true,
    league,
    generatedAt: new Date().toISOString(),
    totalEntries: entries.length,
    classes,
    top,
  };
  await fs.writeFile(
    path.join(SITE_DIR, "builds.json"),
    JSON.stringify(builds, null, 1),
  );
  console.log(
    `ladder: done (${entries.length} entries, top class: ${classes[0]?.name} ${classes[0]?.pct}%)`,
  );
}

if (import.meta.url === `file://${process.argv[1]}`) {
  fetchLadder().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
