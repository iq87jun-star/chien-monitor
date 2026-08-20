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

const SYSTEM_PROMPT = `あなたは遊戯王カード(遊戯王OCG/TCG)の「海外市場」の日本語アナリストです。渡された集計データだけを根拠に、日本語の解説記事を書きます。

対象データの前提(記事内でも正しく扱うこと):
- 価格は海外版(TCG)カードの「海外市場価格」。Cardmarket(欧州最大のトレカマーケット)のユーロ建て価格と、その円換算値(参考値)。priceUsdはTCGplayer(米国)のドル建て価格。日本国内のショップ買取・販売価格ではない。
- change7dPct は約7日前の価格との比較(%)。
- カード名はTCG(英語)表記。読者は日本の遊戯王プレイヤー・コレクター・eBay等で海外販売するセラーで、英語カード名は海外取引で実際に使う名前としてそのまま載せる価値がある。
- banは海外(TCG)のリミットレギュレーション(Banned=禁止/Limited=制限)。日本(OCG)とは異なる場合がある。

厳守事項:
- 数値の計算・合算・平均などの加工をしない。データの値をそのまま記載する(丸める場合も小数1桁までの四捨五入に留める)。
- 「万」「k」などの単位換算表記を使わない。大きな数はカンマ区切り(例: 21,896)でそのまま書く。
- 数値(価格・変動率・為替など)はデータに含まれるものだけを使う。データにない数値を絶対に書かない。
- 通貨単位を必ず明記する(ユーロは€、ドルは$、円換算は「約◯円」のように参考値と分かる書き方)。
- カード名はデータ内の英語表記をそのまま使う(勝手に和訳しない。よく知られたカードなら「(和名:◯◯)と呼ばれる」程度の補足は可だが、確信がなければ書かない)。
- 憶測で断定しない。データから直接読み取れない因果関係(大会環境・再録・規制改訂等)は「〜が要因とみられる」など推測と分かる表現にする。
- 投資・売買の推奨をしない。「買うべき」「売り時」のような断定的助言は書かず、事実の記述に徹する。
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

  if (economy.available === false) {
    console.log("generate: economy data unavailable (maintenance) — skipping");
    return;
  }

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
  const pick = (c) => ({
    name: c.name,
    cardType: c.type,
    priceEur: c.eur,
    priceUsd: c.usd,
    priceJpyApprox: c.jpy,
    change7dPct: c.change7d,
    ban: c.ban,
  });
  const input = {
    gainers: economy.gainers.slice(0, 8).map(pick),
    losers: economy.losers.slice(0, 8).map(pick),
    expensive: economy.expensive.slice(0, 8).map(pick),
    bannedHighValue: (economy.banned ?? []).slice(0, 6).map(pick),
    fxEurJpy: economy.fx?.eurJpy ?? null,
    totals: economy.totals,
  };

  const { default: Anthropic } = await import("@anthropic-ai/sdk");
  const client = new Anthropic();

  const userPrompt = `以下は遊戯王カード(海外版TCG)の海外市場の最新集計データです(priceEurはCardmarketのユーロ建て価格、priceUsdはTCGplayerのドル建て価格、priceJpyApproxはECB為替レートによる円換算の参考値、change7dPctは約7日前の価格との比較%、banは海外TCGのリミットレギュレーション)。
このデータから、今の海外市場動向の解説記事を1本書いてください。セクションは2〜4個。gainers/losersが空の場合は価格ランキングと禁止カード価格を中心に書いてください。

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
