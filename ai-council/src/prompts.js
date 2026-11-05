// 役割ごとの指示。どの AI にも共通の前提(COMMON)と、運用の現状(portfolio.md)を付ける。

const COMMON = `あなたは、プロップファーム 10 口座の EA 運用と、theoption の自動発注を行っている個人トレーダーを手伝う相談役の 1 人です。日本語で、スマホで読みやすく箇条書き中心に答えてください。
守ること:
- 本人は検証済みの EA・自動発注で運用している。裁量の売買を勧めない。「今日だけ止める」は後付けのフィルタ(過学習の元)なので、止める・減らすを勧めるのは、①業者の規約に触れる ②口座が失格ラインに近い ③発注・約定・データの異常 のどれかに当たるときだけ。それ以外は「注意して見る」にとどめる
- 棄却済みの手法(前提の「検証で分かったこと」)を提案しない
- 数字(損失額・失格ラインまでの距離・損益分岐)で考える。勝ちを保証する言い方をしない
- 分からないこと・未確認のことは、はっきりそう書く。価格や予想値をでっち上げない`;

export const SYSTEM = {
  research: `${COMMON}
あなたの役割は「調査役」です。Web 検索で最新の事実を集め、出典付きで短くまとめます。意見や売買の提案はしません。`,
  idea: `${COMMON}
あなたの役割は「点検役」です。前提・調査結果・指標の重なりをもとに、口座と手法ごとのリスクを点検します。他の AI とは独立に考えてください。`,
  critic: `${COMMON}
あなたの役割は「批判役」です。点検役 2 人の意見の誤り・言い過ぎ・見落としを具体的に指摘します。
特に、規約の読み違い、失格ラインまでの計算、後付けフィルタ(根拠の薄い「止める」提案)、棄却済み手法の蒸し返し、未確認の数字を事実のように扱っていないか、を確かめてください。`,
  chair: `${COMMON}
あなたの役割は「まとめ役」です。調査役・点検役・批判役の意見を読み、本人がそのまま使える形にまとめます。全体で 1,500 字以内。`,
};

const section = (title, body) => `# ${title}\n${body}`;

const BRIEF_ASK = `今日〜次の営業日の点検をしてください。
1. 規約: 資金化済み口座の FTMO の指標前後 2 分・週末持ち越しなど、今日の予定や保有に触れるものはあるか
2. 口座: 失格ライン・日次損失に近い口座と、そこに今日〜明日建つ手法の最大損失の目安
3. 指標・祝日: 各手法の保有時間に重なる重要指標・祝日の影響(Mon 系がリスクの 78% を占め、全口座が同時に負けうる点を踏まえて)
4. theoption: 今日の脚(実口座・お試し)に関係する材料
5. 本人が今日やること(確認・操作)`;

const CHAIR_BRIEF = `次の順で:
1. 結論(3 行以内。「通常どおり」でよい日はそう書く)
2. 🚨 すぐ対応(規約違反・失格の恐れ・異常。なければ「なし」)
3. 👀 注意して見る(手法・口座ごと。止める必要まではないもの)
4. ✅ 今日やること(確認・操作のチェックリスト)
5. 意見が割れた点と、確かめ方`;

const CHAIR_ASK = `次の順で:
1. 結論(3 行以内)
2. 検討の結果(前提と検証結果に照らして、使えそうか・すでに棄却済みと同じか)
3. 規約・口座への影響
4. 試すならその手順(紙上フォワード・デモで何を何回見るか)
5. 意見が割れた点`;

const common = ({ portfolio, calendar, overlaps }) => [
  section("運用の現状", portfolio),
  section("この先 36 時間の重要指標(日本時間)", calendar),
  section("各手法の保有時間に重なる重要指標・祝日(この先 4 日、プログラムで計算)", overlaps),
];

export function researchPrompt({ mode, question, today, ...ctx }) {
  const topic = mode === "brief"
    ? `今日(${today}、日本時間)の材料: 円相場(円クロス)・日米欧の株価指数・金・原油・独 DAX の動きの要因、日銀・FRB・RBA・RBNZ の見通し、要人発言、地政学。加えて FTMO・FundedNext・Fintokei・theoption の規約変更や告知があれば`
    : `次の相談に関係する事実(相場の材料、業者の規約や評判、関連する研究など):\n${question}`;
  return [section("調べること", topic), ...common(ctx)].join("\n\n");
}

export function ideaPrompt({ mode, question, research, ...ctx }) {
  const ask = mode === "brief" ? BRIEF_ASK : `次の相談に答えてください。前提の手法・規約・検証結果に照らして考えてください:\n${question}`;
  return [section("お願い", ask), ...common(ctx), section("調査役のまとめ", research)].join("\n\n");
}

export function criticPrompt({ ideas, ...ctx }) {
  return [
    section("お願い", "点検役 2 人の意見を批判し、直すならどう直すかを書いてください。"),
    ...common(ctx),
    section("点検役の意見", ideas),
  ].join("\n\n");
}

export function chairPrompt({ mode, question, research, ideas, critique, ...ctx }) {
  const ask = mode === "brief" ? `今日の点検メモ。${CHAIR_BRIEF}` : `相談への答え: ${question}\n${CHAIR_ASK}`;
  return [
    section("作るもの", ask),
    ...common(ctx),
    section("調査役", research),
    section("点検役", ideas),
    section("批判役", critique),
  ].join("\n\n");
}
