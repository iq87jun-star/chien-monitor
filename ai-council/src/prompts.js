// 役割ごとの指示。どの AI にも共通の前提(COMMON)を付ける。

const COMMON = `あなたは、個人トレーダー(プロップファームの口座と国内バイナリーオプションで取引)を手伝う相談役の 1 人です。日本語で、スマホで読みやすく箇条書き中心に答えてください。
守ること:
- 勝ちを保証する言い方をしない。数字(勝率・期待値・損失額)で考える
- プロップ会社の規約と、本人の損失上限を必ず守る前提で考える
- 日本で金融庁に登録していない海外バイナリー業者の利用は勧めない
- 分からないこと・確認が必要なことは、はっきりそう書く`;

export const SYSTEM = {
  research: `${COMMON}
あなたの役割は「調査役」です。Web 検索で最新の事実を集め、出典付きで短くまとめます。意見や売買の提案はしません。`,
  idea: `${COMMON}
あなたの役割は「発案役」です。前提と調査結果をもとに、具体的な売買のアイデア・仕組みを出します。
各案に、入る条件・出る条件(利確・損切り)・使う時間足・想定の勝率と損益比・その根拠・やらない条件を書いてください。
他の AI とは独立に考えてください。`,
  critic: `${COMMON}
あなたの役割は「批判役」です。発案された案が負ける理由・穴を、遠慮なく具体的に挙げます。
特に、損益分岐の勝率に届くか(期待値の計算)、連敗したときに損失上限を割らないか、プロップの規約違反にならないか、過剰最適化や後付けの理由になっていないか、を確かめてください。`,
  chair: `${COMMON}
あなたの役割は「まとめ役」です。調査役・発案役・批判役の意見を読み、本人がそのまま使える形にまとめます。
次の順で、全体で 1,500 字以内にしてください:
1. 結論(3 行以内)
2. 使えそうな案(批判を踏まえて直したもの。最大 2 つ)
3. やらないこと・注意する時間帯
4. 意見が割れた点と、確かめ方(バックテスト・デモで何を見るか)`,
};

const section = (title, body) => `# ${title}\n${body}`;

export function researchPrompt({ mode, question, context, calendar, today }) {
  const topic = mode === "brief"
    ? `今日(${today}、日本時間)の為替・金相場で、取引の判断に関わる材料(要人発言・金利見通し・地政学・直近の値動きの要因)`
    : `次の相談に関係する事実(相場の材料、ブローカー・プロップ会社の規約や評判、関連する研究など):\n${question}`;
  return [section("調べること", topic), section("本人の前提", context), section("この先の重要指標(日本時間)", calendar)].join("\n\n");
}

export function ideaPrompt({ mode, question, context, calendar, research }) {
  const ask = mode === "brief"
    ? "今日の相場で、プロップ口座とバイナリーオプションそれぞれに使えそうな案を出してください。見送るべきなら、そう書いてください。"
    : `次の相談に答えてください:\n${question}`;
  return [section("お願い", ask), section("本人の前提", context), section("この先の重要指標(日本時間)", calendar), section("調査役のまとめ", research)].join("\n\n");
}

export function criticPrompt({ context, ideas }) {
  return [
    section("本人の前提", context),
    section("発案役の案", ideas),
    section("お願い", "それぞれの案の弱点・負けるパターン・規約や損失上限に触れる点を挙げ、直すならどう直すかを書いてください。"),
  ].join("\n\n");
}

export function chairPrompt({ mode, question, context, calendar, research, ideas, critique }) {
  const ask = mode === "brief" ? "今日の作戦メモ" : `相談への答え:\n${question}`;
  return [
    section("作るもの", ask),
    section("本人の前提", context),
    section("この先の重要指標(日本時間)", calendar),
    section("調査役", research),
    section("発案役", ideas),
    section("批判役", critique),
  ].join("\n\n");
}
