// FF14マーケットモニター 砕けた口調の X 投稿(1日2回・昼/夜)
// 最新の集計データ(data/site/economy.json)から、Claude が短い雑談調ポストを1件作って投稿する。
// 型(ツッコミ・値下がり・取引量・高額品・アンケート)を日替わりで回し、同じ品目が続かないようにする。
// 数字は検品ゲート(validate.mjs)で集計データと照合し、合わなければ作り直す(最大3回)。
//
// 使い方: node pipeline/post-casual.mjs [--slot am|pm]   (省略時は日本時間15時より前を am とする)
// 必要な環境変数: ANTHROPIC_API_KEY, X_API_KEY, X_API_SECRET, FF14_X_ACCESS_TOKEN, FF14_X_ACCESS_TOKEN_SECRET
// DRY_RUN=1 なら投稿せず文面を表示するだけ(posted.json も書かない)。
import fs from "node:fs/promises";
import path from "node:path";
import { SITE_DIR } from "./config.mjs";
import { isReliable } from "./market-filter.mjs";
import { collectAllowedNumbers, validateArticleNumbers } from "./validate.mjs";
import { postTweet, xCredsFromEnv } from "./post-x.mjs";

const MODEL = process.env.CLAUDE_MODEL || "claude-opus-5-5";
const HASHTAGS = "#FF14 #マケボ";
const MAX_WEIGHT = 280; // X の文字数上限(全角は2、半角は1と数える)
const MAX_ATTEMPTS = 3;
const STALE_HOURS = 48;
const RECENT_ITEMS_KEPT = 8;

const TYPES = [
  {
    key: "gainer",
    pick: (items) => sortBy(items.filter((i) => i.change7d >= 15), (i) => -i.change7d),
    brief:
      "7日間で値上がりした品目を1つ選び、上がり幅に軽くツッコむ。「なんで?」と思わせる一言で締める。",
  },
  {
    key: "loser",
    pick: (items) => sortBy(items.filter((i) => i.change7d <= -15), (i) => i.change7d),
    brief:
      "7日間で値下がりした品目を1つ選び、「買い時かも?」「誰かが大量に流した?」くらいの軽いノリで触れる。断定はしない。",
  },
  {
    key: "volume",
    pick: (items) => sortBy(items, (i) => -i.velocity),
    brief:
      "取引量(1日あたりの推定取引数)が多い品目を1つ選び、「今週もこれが一番売れてる」「みんな何に使ってるの」系のあるあるネタにする。",
  },
  {
    key: "expensive",
    pick: (items) => sortBy(items, (i) => -i.price),
    brief:
      "高額な品目を1つ選び、値段の高さに驚く・ちょっと引く感じのリアクションにする。",
  },
  {
    key: "poll",
    pick: (items) =>
      sortBy(items.filter((i) => Math.abs(i.change7d) >= 15), (i) => -Math.abs(i.change7d)),
    brief:
      "変動の大きい品目を1つ選び、フォロワーに2〜4択のアンケートで聞く(例: 今買う/様子見/そもそも使わない)。本文は問いかけで終える。poll_options に選択肢を入れる。",
  },
];

const SYSTEM_PROMPT = `あなたは X(旧Twitter)の FF14 マーケットボード相場 bot「FF14マーケットモニター」の投稿担当です。普段は整った速報やレポートを流していますが、この投稿は合間に挟む「砕けた一言ポスト」です。

口調:
- タメ口寄りのゆるい話し言葉。ヒカセン(FF14 プレイヤー)同士の雑談のノリ。絵文字は0〜2個。
- 1〜3文の短文。改行は最大2回。
- FF14 の用語・あるある(ギル、マケボ、リテイナー、禁断、製作・採集、零式、ハウジング など)は自然な範囲で使ってよい。

厳守事項:
- 数値は渡されたデータの値だけを使う。計算・合算・換算をしない(変動率は小数1桁まで、価格はカンマ区切りのギル表記)。「万」「k」表記は使わない。
- アイテム名はデータの日本語名をそのまま使う。
- bot であることを偽らない。「自分も買った」「さっき金策した」など、人間としての体験を語らない。
- 「今すぐ買え」「確実に上がる」などの断定的な売買の勧めをしない。
- RMT、他プレイヤーや特定サーバーへの揶揄、炎上しそうな話題には触れない。
- データは Universalis のプレイヤー投稿による集計(日本DC統合)なので、因果は「〜かも」程度に留める。
- ハッシュタグと URL は書かない(システムが付ける)。`;

const SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: ["text", "item_name", "poll_options"],
  properties: {
    text: { type: "string", description: "投稿本文(ハッシュタグなし・日本語で全角110文字以内)" },
    item_name: { type: "string", description: "取り上げたアイテム名(データ内の名前そのまま)" },
    poll_options: {
      type: "array",
      items: { type: "string" },
      description: "アンケート型のときだけ2〜4個(各25文字以内)。それ以外は空配列",
    },
  },
};

function sortBy(arr, key) {
  return [...arr].sort((a, b) => key(a) - key(b));
}

async function readJson(file, fallback = null) {
  try {
    return JSON.parse(await fs.readFile(file, "utf8"));
  } catch {
    return fallback;
  }
}

// X の重み付き文字数(Latin 系は1、それ以外は2)
export function tweetWeight(text) {
  let w = 0;
  for (const ch of text) {
    const cp = ch.codePointAt(0);
    const light =
      (cp >= 0x0000 && cp <= 0x10ff) ||
      (cp >= 0x2000 && cp <= 0x200d) ||
      (cp >= 0x2010 && cp <= 0x201f) ||
      (cp >= 0x2032 && cp <= 0x2037);
    w += light ? 1 : 2;
  }
  return w;
}

function jstNow() {
  return new Date(Date.now() + 9 * 3600e3);
}

function resolveSlot(argv) {
  const i = argv.indexOf("--slot");
  if (i >= 0 && ["am", "pm"].includes(argv[i + 1])) return argv[i + 1];
  return jstNow().getUTCHours() < 15 ? "am" : "pm";
}

// 投稿案の検品。問題があれば理由の文字列、なければ null
export function checkDraft(draft, type, input) {
  if (!draft || typeof draft.text !== "string" || draft.text.trim() === "") return "本文が空";
  if (/https?:\/\/|#/.test(draft.text)) return "本文に URL かハッシュタグが入っている";
  if (!input.candidates.some((c) => c.name === draft.item_name)) {
    return `item_name「${draft.item_name}」が候補にない`;
  }
  if (!draft.text.includes(draft.item_name)) return "本文に取り上げた品目名が入っていない";
  const full = `${draft.text.trim()}\n\n${HASHTAGS}`;
  if (tweetWeight(full) > MAX_WEIGHT) return `長すぎる(重み ${tweetWeight(full)} / ${MAX_WEIGHT})`;
  const violations = validateArticleNumbers(
    { title: draft.text, summary: "", sections: [] },
    collectAllowedNumbers(input),
  );
  if (violations.length > 0) return `データにない数値: ${violations.join(", ")}`;
  const opts = draft.poll_options ?? [];
  if (type.key === "poll") {
    if (opts.length < 2 || opts.length > 4) return "アンケートの選択肢は2〜4個";
    if (opts.some((o) => !o.trim() || [...o].length > 25)) return "選択肢が空か25文字超";
    if (new Set(opts).size !== opts.length) return "選択肢が重複している";
  } else if (opts.length > 0) {
    return "アンケート型ではないのに選択肢がある";
  }
  return null;
}

async function draftPost(client, type, input) {
  let feedback = "";
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    const userPrompt = `今回の型: ${type.brief}

候補(このうち1つだけを取り上げる。価格はギル、velocityPerDay は1日あたりの推定取引数、change7dPct は直近7日の変動率%):
\`\`\`json
${JSON.stringify(input, null, 1)}
\`\`\`${feedback ? `\n\n前回の案は次の理由で不採用になった。直して書き直して: ${feedback}` : ""}`;

    const response = await client.beta.messages.create({
      model: MODEL,
      max_tokens: 16000,
      betas: ["server-side-fallback-2026-07-01"],
      fallbacks: "default",
      output_config: {
        effort: "medium",
        format: { type: "json_schema", schema: SCHEMA },
      },
      system: SYSTEM_PROMPT,
      messages: [{ role: "user", content: userPrompt }],
    });
    if (response.stop_reason === "refusal") {
      feedback = "生成が拒否された";
      console.warn(`casual: attempt ${attempt} refused`);
      continue;
    }
    const textBlock = response.content.find((b) => b.type === "text");
    let draft;
    try {
      draft = JSON.parse(textBlock?.text ?? "");
    } catch {
      feedback = "JSON として読めなかった";
      continue;
    }
    const problem = checkDraft(draft, type, input);
    if (!problem) return draft;
    console.warn(`casual: attempt ${attempt} rejected — ${problem}: ${draft.text}`);
    feedback = problem;
  }
  return null;
}

export async function postCasual(argv = []) {
  const dryRun = !!process.env.DRY_RUN;
  if (!process.env.ANTHROPIC_API_KEY) {
    console.log("casual: ANTHROPIC_API_KEY not set — skipping");
    return;
  }
  const creds = xCredsFromEnv();
  if (!creds && !dryRun) {
    console.log("casual: X API credentials not set — skipping");
    return;
  }

  const economy = await readJson(path.join(SITE_DIR, "economy.json"));
  if (!economy) throw new Error("economy.json missing");
  const ageH = (Date.now() - Date.parse(economy.generatedAt)) / 3600e3;
  if (!(ageH <= STALE_HOURS)) {
    console.log(`casual: data is ${ageH.toFixed(1)}h old — skipping (stale)`);
    return;
  }

  const statePath = path.join(SITE_DIR, "posted.json");
  const state = await readJson(statePath, { articleIds: [] });
  state.casualSlots ??= [];
  state.casualRecentItems ??= [];

  const today = jstNow().toISOString().slice(0, 10);
  const slot = resolveSlot(argv);
  const slotKey = `${today}-${slot}`;
  if (state.casualSlots.includes(slotKey) && !dryRun) {
    console.log(`casual: ${slotKey} already posted — skipping`);
    return;
  }

  // 型は日付と時間帯で決める(1日2件 × 5種類で、同じ型が同じ時間帯に固定されない)
  const dayIndex = Math.floor(Date.parse(today) / 86400e3);
  const reliable = economy.items.filter(isReliable);
  const recent = new Set(state.casualRecentItems);
  let type = null;
  let candidates = [];
  for (let k = 0; k < TYPES.length && candidates.length === 0; k++) {
    type = TYPES[(dayIndex * 2 + (slot === "pm" ? 1 : 0) + k) % TYPES.length];
    candidates = type
      .pick(reliable)
      .filter((i) => !recent.has(i.name))
      .slice(0, 5);
  }
  if (candidates.length === 0) {
    console.log("casual: no usable items — skipping");
    return;
  }

  const input = {
    region: "日本DC統合リージョン",
    candidates: candidates.map((i) => ({
      name: i.name,
      price: i.price,
      velocityPerDay: i.velocity,
      change7dPct: i.change7d,
    })),
  };

  const { default: Anthropic } = await import("@anthropic-ai/sdk");
  const client = new Anthropic();
  console.log(`casual: ${slotKey} type=${type.key} calling ${MODEL} ...`);
  const draft = await draftPost(client, type, input);
  if (!draft) throw new Error(`no acceptable draft after ${MAX_ATTEMPTS} attempts`);

  const body = { text: `${draft.text.trim()}\n\n${HASHTAGS}` };
  if (type.key === "poll") {
    body.poll = { options: draft.poll_options.map((o) => o.trim()), duration_minutes: 1440 };
  }

  if (dryRun) {
    console.log("casual: DRY_RUN — would post:\n" + JSON.stringify(body, null, 1));
    return;
  }
  const result = await postTweet(body, creds);
  console.log(`casual: posted ${type.key} (tweet id: ${result.data?.id})`);

  state.casualSlots = [...state.casualSlots, slotKey].slice(-20);
  state.casualRecentItems = [...state.casualRecentItems, draft.item_name].slice(-RECENT_ITEMS_KEPT);
  await fs.writeFile(statePath, JSON.stringify(state, null, 1));
}

if (import.meta.url === `file://${process.argv[1]}`) {
  postCasual(process.argv.slice(2)).catch((err) => {
    console.error("casual:", err.message);
    process.exit(1);
  });
}
