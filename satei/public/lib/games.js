// 扱うゲームと、紹介・相談を受ける X のアカウント(画面と Worker で共通)
// HoYo の4作品は AI 査定(chars.js)、グラブル・ウマ娘・第五人格はチェック式の査定(check.js)
export const GAMES = { "genshin-impact": "原神", houkaistarrail: "スタレ", zzz: "ゼンゼロ", wutheringwaves: "鳴潮", granblue: "グラブル", umamusume: "ウマ娘", identityv: "第五人格" };
export const X_OF = { granblue: "meruru_prop", umamusume: "meruru_prop", identityv: "meruru_prop" };
export const xOf = (game) => X_OF[game] ?? "Meruru_Genshin";
// 管理画面はアカウント(窓口の X)ごとに切り替えられる
export const ACCOUNTS = { genshin: "原神・スタレ(@Meruru_Genshin)", prop: "グラブル・ウマ娘・第五人格(@meruru_prop)" };
export const accountOf = (game) => (X_OF[game] ? "prop" : "genshin");
export const gamesOf = (acct) => Object.keys(GAMES).filter((g) => !acct || accountOf(g) === acct);
