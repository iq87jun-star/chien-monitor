// 複数の AI(OpenRouter 経由)に相場・アイデアを検討させ、まとめを Discord に送る。
//   OPENROUTER_API_KEY … OpenRouter の API キー(未設定なら AI を呼ばずに、渡す内容だけ表示する)
//   AI_COUNCIL_DISCORD_WEBHOOK … 送り先(未設定なら標準出力に出すだけ)
//   AI_COUNCIL_QUESTION … 相談したいこと(空なら「今日の点検」)
//   AI_COUNCIL_STATUS_KEY … パソコンが書き出す口座データ(status.enc)の鍵(未設定・ファイルなしなら使わない)
//   AI_COUNCIL_MODE … explore なら新規開拓会議(相談が空のときだけ。空なら毎朝の点検)
import { readFileSync, appendFileSync, existsSync, writeFileSync, mkdirSync } from "node:fs";
import { pickEvents, calendarText, todayJST, formatJST, legWindows, legOverlaps, overlapText, mergeEvents } from "./src/context.js";
import { runCouncil, transcript, splitMessage } from "./src/council.js";
import { decryptStatus, statusText } from "./src/status.js";
import { extractCandidates } from "./src/prompts.js";
import { buildHandoffs, withoutHandoff, queueFeedback, readmeFeedback } from "./src/handoff.js";

const config = JSON.parse(readFileSync(new URL("./config.json", import.meta.url)));
const UA = "chien-monitor-ai-council/0.1 (+https://github.com/iq87jun-star/chien-monitor)";
const key = process.env.OPENROUTER_API_KEY;
const question = (process.env.AI_COUNCIL_QUESTION ?? "").trim();
const mode = question ? "ask" : process.env.AI_COUNCIL_MODE === "explore" ? "explore" : "brief";
const exploredFile = new URL("./explored.md", import.meta.url);
const today = todayJST();

async function retry(fn, tries = 3) {
  for (let attempt = 1; ; attempt++) {
    try {
      return await fn();
    } catch (e) {
      if (attempt >= tries) throw e;
      await new Promise((r) => setTimeout(r, 5000 * attempt));
    }
  }
}

// 今週・来週の経済指標(Forex Factory)。取れなかった週は飛ばす
async function events() {
  const lists = await Promise.all(config.calendar.urls.map(async (url) => {
    try {
      return await retry(async () => {
        const res = await fetch(url, { headers: { "User-Agent": UA } });
        if (!res.ok) throw new Error(`経済指標カレンダー ${res.status}: ${url}`);
        return res.json();
      });
    } catch (e) {
      console.error(e.message);
      return null;
    }
  }));
  if (lists.every((l) => !l)) return null;
  return mergeEvents(lists.filter(Boolean));
}

async function openrouter(role, system, user) {
  const { model, maxTokens, reasoning } = config.roles[role];
  if (!key) {
    console.log(`\n===== ${role}(${model})に渡す内容 =====\n${user}`);
    return { text: `(試しの実行: ${model} は呼んでいません)`, cost: 0 };
  }
  return retry(async () => {
    const res = await fetch(config.endpoint, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${key}`,
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/iq87jun-star/chien-monitor",
        "X-Title": "chien-monitor ai-council",
      },
      body: JSON.stringify({
        model,
        max_tokens: maxTokens,
        messages: [
          { role: "system", content: system },
          { role: "user", content: user },
        ],
        // 考える深さ(OpenRouter が各社の設定に読み替える)。max_tokens は考えた分も含む
        ...(reasoning && { reasoning: { effort: reasoning } }),
        usage: { include: true },
      }),
      // Deep Research は何十回も検索するので数分かかる
      signal: AbortSignal.timeout(600_000),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok || body.error) throw new Error(`${model} ${res.status}: ${JSON.stringify(body.error ?? body).slice(0, 300)}`);
    const msg = body.choices?.[0]?.message ?? {};
    // 調査役(Perplexity)の出典は annotations / citations に入る
    const urls = [
      ...(body.citations ?? []),
      ...(msg.annotations ?? []).map((a) => a.url_citation?.url).filter(Boolean),
    ];
    const sources = [...new Set(urls)].slice(0, 8).map((u, i) => `[${i + 1}] ${u}`).join("\n");
    return { text: sources ? `${msg.content}\n\n出典:\n${sources}` : msg.content, cost: body.usage?.cost ?? 0 };
  }, 2);
}

const portfolio = readFileSync(new URL(config.portfolio, import.meta.url), "utf8");
const now = new Date();
const ev = await events();
const calendar = ev ? calendarText(pickEvents(ev, config.calendar, now)) : "(経済指標カレンダーを取れなかった)";
// 来週分は週末まで公開されないことがあるので、どこまで見られたかを添える
const lastEvent = ev && new Date(Math.max(...ev.map((e) => new Date(e.date).getTime())));
const overlaps = ev
  ? `${overlapText(legOverlaps(legWindows(config.legs, now, config.calendar.legHours), ev, config.calendar))}\n(カレンダーは ${formatJST(lastEvent)} までの分しか取れていない。それより後は未確認)`
  : "(経済指標カレンダーを取れなかったので未計算)";
// パソコンが毎朝書き出す最新の口座データ。ワークフローが ai-council-status ブランチから status.enc を持ってくる
function liveStatus() {
  const file = new URL("./status.enc", import.meta.url);
  const statusKey = process.env.AI_COUNCIL_STATUS_KEY;
  if (!existsSync(file)) return "(パソコンからの口座データなし。portfolio.md の 11/1 時点の数字で考える)";
  if (!statusKey) return "(口座データはあるが AI_COUNCIL_STATUS_KEY が未設定で読めない)";
  try {
    return statusText(decryptStatus(readFileSync(file, "utf8"), statusKey), now);
  } catch (e) {
    console.error(`口座データを読めない: ${e.message}`);
    return `(口座データを読めなかった: ${e.message})`;
  }
}
const live = liveStatus();
const explored = existsSync(exploredFile) ? readFileSync(exploredFile, "utf8") : "";
// 各ブランチの最新の検証結果(ワークフローが研究・theoption のブランチから取ってくる)。次の探索に生かす
function feedbackText() {
  const read = (name) => {
    const f = new URL(`./${name}`, import.meta.url);
    return existsSync(f) ? readFileSync(f, "utf8") : null;
  };
  const parts = [];
  try {
    const q = read("research_queue.json");
    if (q) parts.push(`## プロップ研究の検証キュー(docs/244、最近の項目)\n${queueFeedback(JSON.parse(q))}`);
  } catch (e) {
    console.error(`検証キューを読めない: ${e.message}`);
  }
  const r = read("theoption_README.md");
  if (r) parts.push(`## theoption の最近の追補(判定)\n${readmeFeedback(r)}`);
  return parts.join("\n\n");
}
const feedback = mode === "explore" ? feedbackText() : "";
const result = await runCouncil({ config, chat: openrouter, mode, question, portfolio, live, calendar, overlaps, explored, feedback, today });

// 新規開拓会議の候補を explored.md に足す(ワークフローがコミットする。次回からの蒸し返しを防ぐ)
if (mode === "explore" && key) {
  const found = extractCandidates(result.final);
  // まとめ役の答えが途中で切れて「候補一覧」が無いときは、候補なしと区別して記録する
  const lines = found.length
    ? found.map((c) => `- ${today} ${c}`)
    : [`- ${today} ${/##\s*候補一覧/.test(result.final ?? "") ? "(検証に回す候補なし)" : "(候補一覧を取り出せなかった。Discord の全文を見て手で記録する)"}`];
  appendFileSync(exploredFile, `${lines.join("\n")}\n`);
  console.log(`explored.md に ${found.length} 件を記録`);
}

const title = {
  brief: `AI 点検会議 ${today}`,
  explore: `AI 新規開拓会議 ${today}`,
  ask: `AI 相談 ${today}: ${question.slice(0, 40)}`,
}[mode];
const full = transcript({ title, ...result });

// 新規開拓会議の全文をリポジトリに残す(土曜午後の定期タスクが読み、研究・theoption の各セッションへ受け渡す)
if (mode === "explore" && key) {
  const dir = new URL("./explore/", import.meta.url);
  mkdirSync(dir, { recursive: true });
  writeFileSync(new URL(`${today}.md`, dir), full);
  writeFileSync(new URL("latest.md", dir), `<!-- date: ${today} -->\n${full}`);
}
const failed = result.steps.filter((s) => s.error).map((s) => `${s.label}(${s.error.slice(0, 80)})`);
const header = [
  `**${title}**`,
  result.steps.map((s) => `${s.error ? "❌" : "✅"}${s.label.replace(/^\S+\s/, "")}: ${s.model.split("/")[1]}`).join(" / "),
  failed.length ? `⚠️ 失敗: ${failed.join("、")}` : "",
].filter(Boolean).join("\n");
const handoffs = mode === "explore" ? buildHandoffs(result.final, today) : [];
const body = mode === "explore" ? withoutHandoff(result.final) : result.final;
const summary = `${header}\n\n${body || "(まとめ役が失敗したので、添付の全文を見てください)"}\n\n_全員の発言は添付ファイル。費用の目安 $${result.cost.toFixed(3)}。投資の判断はご自身で。_`;

const handoffText = handoffs.map((h) => `## 📋 ${h.to} へ貼り付け\n\n${h.text}`).join("\n\n---\n\n");
console.log(`\n${full}`);
if (handoffText) console.log(`\n# 受け渡しの指示文\n\n${handoffText}`);
if (process.env.GITHUB_STEP_SUMMARY) appendFileSync(process.env.GITHUB_STEP_SUMMARY, handoffText ? `${full}\n\n# 受け渡しの指示文\n\n${handoffText}` : full);

const webhook = process.env.AI_COUNCIL_DISCORD_WEBHOOK;
// text を 2,000 字以内に分けて送り、最後の 1 通にファイルを付ける
async function post(text, file) {
  const parts = splitMessage(text);
  for (const [i, content] of parts.entries()) {
    const form = new FormData();
    form.append("payload_json", JSON.stringify({ content, allowed_mentions: { parse: [] } }));
    if (file && i === parts.length - 1) form.append("files[0]", new Blob([file.body], { type: "text/markdown" }), file.name);
    const res = await fetch(webhook, { method: "POST", body: form });
    if (!res.ok) throw new Error(`Discord ${res.status}: ${await res.text()}`);
  }
}
if (!webhook) {
  console.log("AI_COUNCIL_DISCORD_WEBHOOK が未設定なので送っていません");
} else {
  await post(summary, { body: full, name: `ai-council-${today}.md` });
  // 受け渡しの指示文は、渡す先ごとに別の通で(長押しでコピーしやすいように)。同じ内容をファイルでも付ける
  for (const [i, h] of handoffs.entries()) {
    await post(`📋 **${h.to} へ貼り付け**\n\n${h.text}`, { body: h.text, name: `handoff-${today}-${i + 1}.md` });
  }
  console.log(`Discord に送りました(受け渡し ${handoffs.length} 件)`);
}

// 全員失敗(キーの間違い・残高切れなど)は Actions を赤にして気づけるようにする
if (key && result.steps.every((s) => s.error)) process.exit(1);
