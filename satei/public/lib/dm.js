// 代理出品の DM の定型文を埋める(集計画面と Worker で共通)
export const STATUSES = ["新規", "検討中", "代理出品OK", "出品中", "成約", "見送り"];
const GAMES = { "genshin-impact": "原神", houkaistarrail: "スタレ", zzz: "ゼンゼロ", wutheringwaves: "鳴潮" };

// 定型文の {番号} などを、対象者の情報で置き換える
export function fillTemplate(body, c) {
  const chars = (c.chars ?? [])
    .slice(0, 6)
    .map((x) => `${x.name}${x.cons === 6 ? "完凸" : x.cons ? `${x.cons}凸` : ""}`)
    .join("・");
  const man = (v) => (v == null ? "" : `${(v / 10000).toFixed(1).replace(/\.0$/, "")}万円`);
  const [y, m, d] = (c.next_at ?? "").split("-");
  const values = {
    番号: String(c.id),
    // 呼び名(プロフィール名)があればそれを、無ければ @ユーザー名
    名前: c.name || (c.handle ? `@${c.handle}` : "お客"),
    ゲーム: GAMES[c.game] ?? "",
    キャラ: chars,
    査定額: c.low != null ? `${man(c.low)}〜${man(c.high)}` : "",
    希望額: man(c.wish),
    投稿URL: c.post_url ?? "",
    期限: y ? `${Number(m)}月${Number(d)}日` : "数日後",
  };
  return body.replace(/\{(番号|名前|ゲーム|キャラ|査定額|希望額|投稿URL|期限)\}/g, (_, k) => values[k]);
}

