// ステップ3: AI記事生成(Claude API)
// 集計データを構造化outputで日本語解説記事に変換し、検品ゲートを通過したものだけ公開する。
// ANTHROPIC_API_KEY が無い環境では何もせず正常終了する(データ更新だけでも価値があるため)。
import fs from "node:fs/promises";
import path from "node:path";
import { SITE_DIR, CONTENT_DIR, MAX_ARTICLES } from "./config.mjs";
import {
  collectAllowedNumbers,
  validateArticleNumbers,
  validateArticleShape,
} from "./validate.mjs";

const MODEL = process.env.CLAUDE_MODEL || "claude-opus-5";

const ARTICLE_SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: ["title", "summary", "sections", "tags"],
  properties: {
    title: { type: "string", description: "記事タイトル(日本語・40文字以内)" },
    summary: { type: "string", description: "リード文(日本語・2〜3文)" },
    sections: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["heading", "body"],
        properties: {
          heading: { type: "string" },
          body: { type: "string" },
        },
      },
    },
    tags: { type: "array", items: { type: "string" } },
  },
};

const SYSTEM_PROMPT = `あなたはファイナルファンタジーXIV(FF14)のマーケットボードを分析する日本語の市場アナリストです。渡された集計データだけを根拠に、日本語の解説記事を書きます。

厳守事項:
- データは日本DC統合リージョン(Japan)の集計値で、価格の単位はギルです。
- 数値(価格・変動率・取引量など)はデータに含まれるものだけを使う。データにない数値を絶対に書かない。
- データはUniversalisのクラウドソース集計(プレイヤーのアップロード)に基づくため、実際の相場と多少の遅延・誤差があり得る。断定を避け、その旨を踏まえた表現にする。
- 憶測で断定しない。データから直接読み取れない因果関係は「〜が要因とみられる」など推測と分かる表現にする。
- 読者は日本語圏のFF14プレイヤー。アイテム名はデータ内の日本語名をそのまま使う。
- 文体は丁寧すぎない「です・ます」調。`;

async function readJson(file, fallback = null) {
  try {
    return JSON.parse(await fs.readFile(file, "utf8"));
  } catch {
    return fallback;
  }
}

export async function generateArticles() {
  if (!process.env.ANTHROPIC_API_KEY) {
    console.log("generate: ANTHROPIC_API_KEY not set — skipping article generation");
    return;
  }

  const economy = await readJson(path.join(SITE_DIR, "economy.json"));
  const changes = await readJson(path.join(SITE_DIR, "changes.json"));
  if (!economy || !changes) throw new Error("site data missing — run aggregate first");

  await fs.mkdir(CONTENT_DIR, { recursive: true });
  const articlesPath = path.join(CONTENT_DIR, "articles.json");
  const existing = (await readJson(articlesPath, { articles: [] })).articles;

  // 生成条件: 大きな変化がある、または最後の記事から20時間以上経過
  const lastAt = existing[0] ? Date.parse(existing[0].createdAt) : 0;
  const hoursSinceLast = (Date.now() - lastAt) / 3600e3;
  if (!changes.hasSignificantChange && hoursSinceLast < 20) {
    console.log(
      `generate: no significant change and last article is ${hoursSinceLast.toFixed(1)}h old — skipping`,
    );
    return;
  }

  // 入力データ(記事の根拠として渡す範囲 = 許可数値の範囲)
  const strip = (i) => ({
    name: i.name,
    price: i.price,
    velocityPerDay: i.velocity,
    change7dPct: i.change7d,
  });
  const input = {
    region: "日本DC統合リージョン",
    expensiveTop: economy.expensive.slice(0, 8).map(strip),
    volumeTop: economy.topVolume.slice(0, 8).map(strip),
    gainers: economy.gainers.slice(0, 8).map(strip),
    losers: economy.losers.slice(0, 8).map(strip),
  };

  const { default: Anthropic } = await import("@anthropic-ai/sdk");
  const client = new Anthropic();

  const userPrompt = `以下はFF14の日本DC統合リージョンにおけるマーケットボードの最新集計データです(価格はギル、velocityPerDayは1日あたりの推定取引数、変動率は直近7日間の観測に基づく%)。
${changes.firstRun ? "今回は観測初回のため変動率データはまだ蓄積されていません。価格水準と取引量を中心に解説してください。" : ""}
このデータから、今週の市場動向解説記事を1本書いてください。セクションは2〜4個。

\`\`\`json
${JSON.stringify(input, null, 1)}
\`\`\``;

  console.log(`generate: calling ${MODEL} ...`);
  const response = await client.messages.create({
    model: MODEL,
    max_tokens: 8000,
    system: SYSTEM_PROMPT,
    messages: [{ role: "user", content: userPrompt }],
    output_config: { format: { type: "json_schema", schema: ARTICLE_SCHEMA } },
  });

  if (response.stop_reason === "refusal") {
    console.warn("generate: model refused — keeping existing articles");
    return;
  }
  const textBlock = response.content.find((b) => b.type === "text");
  let article;
  try {
    article = JSON.parse(textBlock?.text ?? "");
  } catch {
    console.warn("generate: response was not valid JSON — keeping existing articles");
    return;
  }

  // --- 検品ゲート ---
  if (!validateArticleShape(article)) {
    console.warn("generate: article failed shape validation — rejected");
    return;
  }
  const allowed = collectAllowedNumbers(input);
  const violations = validateArticleNumbers(article, allowed);
  if (violations.length > 0) {
    console.warn(
      `generate: article rejected — numbers not in source data: ${violations.join(", ")}`,
    );
    return;
  }

  const now = new Date();
  const entry = {
    id: `${now.toISOString().slice(0, 10)}-${now.getTime().toString(36)}`,
    createdAt: now.toISOString(),
    region: economy.region,
    type: "market",
    validated: true,
    ...article,
  };

  const updated = [entry, ...existing].slice(0, MAX_ARTICLES);
  await fs.writeFile(articlesPath, JSON.stringify({ articles: updated }, null, 1));
  console.log(`generate: published "${entry.title}" (${updated.length} articles total)`);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  generateArticles().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
