// 新規開拓会議の「受け渡し」と「検証結果の取り込み」。ここは文字列の組み立てだけで、通信しない。

// まとめ役の答えの「## 受け渡し」節を、渡す先ごとに取り出す
//   ### 研究ブランチ(①) / ### theoption(③) / ### 問い合わせ(②)
export function handoffSections(final) {
  const m = (final ?? "").match(/^##\s*受け渡し\s*$([\s\S]*?)(?=^##\s(?!#)|(?![\s\S]))/m);
  if (!m) return {};
  const out = {};
  for (const part of m[1].split(/^###\s*/m).slice(1)) {
    const [head, ...rest] = part.split("\n");
    const body = rest.join("\n").trim();
    if (!body || /^(なし|-\s*なし)$/.test(body)) continue;
    if (/研究/.test(head)) out.research = body;
    else if (/theoption/i.test(head)) out.theoption = body;
    else if (/問い合わせ/.test(head)) out.inquiry = body;
  }
  return out;
}

// Discord に出す本文からは受け渡し節を外す(指示文は別の通に出すので)
export function withoutHandoff(final) {
  return (final ?? "").replace(/^##\s*受け渡し\s*$[\s\S]*?(?=^##\s(?!#)|(?![\s\S]))/m, "").trim();
}

const WRITE_BACK = (date, branchName) =>
  `処理の結果は、main の ai-council/explored.md の「${date}」の該当行の末尾に「→ 登録(Q○○)」「→ 登録せず(理由 1 行)」「→ 合格」「→ 棄却(理由 1 行)」などの形で書き足してください(次の新規開拓会議が読みます)。main から ${branchName} ブランチを作って PR を出し、変更が explored.md だけで CI が緑ならマージしてよい(この書き戻しに限った例外)。`;

// 渡す先ごとの、そのまま貼れる指示文
export function buildHandoffs(final, date) {
  const s = handoffSections(final);
  const out = [];
  if (s.research) {
    out.push({
      to: "プロップ研究のセッション(ブランチ claude/prop-trading-new-methods-a8y3l1)",
      text: `# 週次アイデア束を登録(ユーザー「登録」)— AI 新規開拓会議 ${date} の ① CFD 候補

main の ai-council の新規開拓会議の候補です。登録の前に重複を確かめ、重複なら登録せず理由と代替案を docs/244 に書いてください: docs/244・research/queue/queue.json の既出・既棄却、紙上フォワードの CANDIDATES、別系統 fx-ea/search(ledger.json・multi/RESULTS.md。日足の寄り建て仮説はそちらの守備範囲)、Notion「1000万円ロードマップ v2」の P2・P3 の裁定。
判定は docs/244 §1 のまま(AI 側が書いた基準は参考の記録にとどめ、緩めない)。通過しても紙上フォワードの CANDIDATES に入れるだけで、EA・manifest・config は変えない。docs/244 には、これまでの「週次アイデア束」の形式で追記する。
${WRITE_BACK(date, `ai-council/handoff-${date}`)}

## 候補
${s.research}`,
    });
  }
  if (s.theoption) {
    out.push({
      to: "theoption のセッション(ブランチ claude/zaption-check-m776m7)",
      text: `# 新しい脚の候補の検証 — AI 新規開拓会議 ${date} の ③ theoption 候補

main の ai-council の新規開拓会議の候補です。README の追補・アイデア台帳・既棄却との重複、プロップ側 docs/244 §1b と分担の取り決め(2026-10-21)、規約(既存の脚と同じ時刻・通貨で逆向き=両建てにならないか)、その時刻に商品が買えるか、216・213 の拒否、1 日の掛け金上限を先に確かめてください。
問題なければ、このブランチの検証の決まり(10 年ミッド・建て時刻のミッド判定・G3・G5・LOYO・損益分岐 +3pp)で検証し、README の次の追補に書く。基準は緩めない。発注・to_config.json の変更はしない(合格してもお試し口座での確認の提案まで)。
${WRITE_BACK(date, `ai-council/handoff-theoption-${date}`)}

## 候補
${s.theoption}`,
    });
  }
  if (s.inquiry) {
    out.push({
      to: "プロップ研究のセッション(問い合わせの下書き)",
      text: `# 業者への問い合わせの下書き — AI 新規開拓会議 ${date} の ② 候補

次の確認事項を、英語の問い合わせメールにまとめて Gmail の下書きを作ってください(送信はしない。私が確認して送ります)。既存の問い合わせ(FundedNext スレッド 1a18d0f9ff646f58、FTMO チケット TJZ-LCLKF-689 など)ですでに聞いた質問・回答済みの質問は除く。既存の窓口がある会社はそのスレッドへの返信の下書きに。口座番号・パスワードは書かない(必要なら「[口座番号]」の空欄)。
${WRITE_BACK(date, `ai-council/handoff-inquiry-${date}`)}

## 確認事項
${s.inquiry}`,
    });
  }
  return out;
}

// 研究側の検証キュー(queue.json)から、最近の項目の結果を短くまとめる
export function queueFeedback(queue, limit = 40) {
  const items = (queue?.items ?? []).slice(-limit);
  const lines = items.map((it) => {
    const res = String(it.result ?? it.status ?? "").replace(/\s+/g, " ").slice(0, 160);
    return `- ${it.id}(${it.status}): ${String(it.title ?? it.slug ?? "").replace(/\s+/g, " ").slice(0, 80)}${res ? ` → ${res}` : ""}`;
  });
  const head = queue?.cumulative_cells != null ? `累積セル数 ${queue.cumulative_cells}(Bonferroni の分母)` : "";
  return [head, ...lines].filter(Boolean).join("\n");
}

// theoption の README から、最近の追補の見出し(判定が書かれている)を取り出す
export function readmeFeedback(md, limit = 10) {
  return (md ?? "")
    .split("\n")
    .filter((l) => /^##\s*追補/.test(l))
    .slice(-limit)
    .map((l) => `- ${l.replace(/^##\s*/, "")}`)
    .join("\n");
}
