// 複数の AI を順番に呼ぶ: 調査役 → 点検役 A・B(同時に、互いの答えは見せない)→ 批判役 → まとめ役
// chat(role, system, user) は外から渡す(本番は OpenRouter、テストは偽物)。1 人が失敗しても残りは続ける。
// portfolio … 運用の現状(portfolio.md) calendar … 重要指標 overlaps … 手法の保有時間との重なり
// explored … 過去の新規開拓会議の候補(explore のときだけ使う)
import { systemFor, researchPrompt, ideaPrompt, criticPrompt, chairPrompt } from "./prompts.js";

export const ORDER = ["research", "ideaA", "ideaB", "critic", "chair"];

export async function runCouncil({ config, chat, mode, question, portfolio, live = "", calendar, overlaps, explored = "", today }) {
  const steps = {};
  const call = async (role, user) => {
    const system = systemFor(mode, role);
    const { model } = config.roles[role];
    const label = (mode === "explore" && config.exploreLabels?.[role]) || config.roles[role].label;
    const step = { role, label, model, text: "", cost: 0 };
    try {
      const r = await chat(role, system, user);
      step.text = (r.text ?? "").trim();
      step.cost = r.cost ?? 0;
      if (!step.text) step.error = "空の返事";
    } catch (e) {
      step.error = e.message;
    }
    steps[role] = step;
    return step;
  };
  const textOf = (s) => (s.error ? `(${s.label} は失敗: ${s.error})` : s.text);
  const base = { mode, question, portfolio, live, calendar, overlaps, explored, today };

  const research = await call("research", researchPrompt(base));
  const ideaSteps = await Promise.all(
    ["ideaA", "ideaB"].map((role) => call(role, ideaPrompt({ ...base, research: textOf(research) }))),
  );
  const ideas = ideaSteps.map((s) => `## ${s.label}(${s.model})\n${textOf(s)}`).join("\n\n");
  const critique = await call("critic", criticPrompt({ ...base, ideas }));
  const chair = await call("chair", chairPrompt({ ...base, research: textOf(research), ideas, critique: textOf(critique) }));

  const list = ORDER.map((r) => steps[r]);
  const cost = list.reduce((s, x) => s + x.cost, 0);
  return { steps: list, final: chair.error ? null : chair.text, cost };
}

// 全員の発言を 1 つの Markdown に(Discord の添付・Actions のまとめ用)
export function transcript({ title, steps, cost }) {
  const body = steps
    .map((s) => `## ${s.label} — ${s.model}\n\n${s.error ? `⚠️ 失敗: ${s.error}` : s.text}`)
    .join("\n\n---\n\n");
  return `# ${title}\n\n${body}\n\n---\n\n費用の目安: $${cost.toFixed(4)}\n`;
}

// Discord の 1 通は 2,000 字まで。なるべく行の切れ目で分ける
export function splitMessage(text, limit = 1900) {
  const out = [];
  let cur = "";
  for (const line of text.split("\n")) {
    let rest = line;
    do {
      const piece = rest.slice(0, limit);
      rest = rest.slice(limit);
      if (cur && cur.length + 1 + piece.length > limit) {
        out.push(cur);
        cur = piece;
      } else {
        cur = cur ? `${cur}\n${piece}` : piece;
      }
    } while (rest);
  }
  if (cur) out.push(cur);
  return out;
}
