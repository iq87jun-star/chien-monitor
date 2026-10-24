// 引き継ぎ情報フォーム(売主が記入 → 管理画面で「引き継ぎ情報シート」にして売却先に渡す)の項目。
// form.html・sheet.html・Worker(src/sheet.js)で共通。
//   buyer: true の項目だけを売却先へのシートに載せる(取り戻しの申請で聞かれる内容)。
//   本人作成かどうか・連絡先などは当方の確認用で、シートには載せない。
export const SHEET = [
  {
    title: "アカウント",
    fields: [
      { key: "uid", label: "UIDとサーバー", hint: "例: 8xxxxxxxx(アジア)", buyer: true },
      { key: "names", label: "ゲーム内の名前(今の名前と、以前の名前)", buyer: true },
      { key: "created", label: "アカウントを作成した時期", hint: "例: 2021年3月頃", buyer: true },
      { key: "created_device", label: "作成したときの端末(機種名)", hint: "例: iPhone 12", buyer: true },
      { key: "created_region", label: "作成したときの国・地域", hint: "例: 日本・東京都", buyer: true },
      { key: "usual", label: "普段ログインしていた端末と地域", buyer: true },
    ],
  },
  {
    title: "登録情報",
    fields: [
      { key: "first_mail", label: "最初に登録したメールアドレス", buyer: true },
      { key: "now_mail", label: "現在の登録メールアドレスと、変更した時期", hint: "最初から変えていなければ「変更なし」", buyer: true },
      { key: "phone", label: "電話番号の登録", options: ["なし", "あり", "分からない"], buyer: true },
      { key: "links", label: "連携しているアカウントと、過去に連携していたもの", hint: "例: Google(現在)・X(以前に解除)", long: true, buyer: true },
    ],
  },
  {
    title: "課金",
    fields: [
      { key: "first_pay", label: "最初の課金(日付・金額・支払い方法)", hint: "例: 2021年4月頃・610円・App Store", buyer: true },
      { key: "last_pay", label: "直近の課金(日付・金額・支払い方法)", buyer: true },
      { key: "total_pay", label: "だいたいの課金総額", buyer: true },
      { key: "refund", label: "課金の返金・キャンセルをしたことがあるか", options: ["ない", "ある"], buyer: true },
    ],
  },
  {
    title: "ご本人の確認",
    fields: [
      { key: "self_made", label: "ご本人が作成したアカウントですか", options: ["はい", "いいえ(購入・譲渡で入手)"] },
      { key: "shared", label: "他の方にログイン情報を教えたことはありますか", options: ["ない", "ある"] },
      { key: "contact", label: "連絡のとれる X のユーザー名", hint: "@user" },
      { key: "note", label: "その他、伝えておきたいこと", long: true },
    ],
  },
];
export const SHEET_FIELDS = SHEET.flatMap((s) => s.fields);
export const MAX_RECEIPTS = 4;

// 売主の回答を検査して { key: 文字列 } にする。同意が無ければ null
export function validAnswers(body) {
  if (!body || typeof body !== "object" || body.agree !== true) return null;
  const out = {};
  for (const f of SHEET_FIELDS) {
    const v = typeof body[f.key] === "string" ? body[f.key].trim().slice(0, f.long ? 600 : 200) : "";
    if (f.options && v && !f.options.includes(v)) return null;
    out[f.key] = v;
  }
  return out;
}
