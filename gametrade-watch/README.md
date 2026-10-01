# gametrade-watch

ゲームトレード(gametrade.jp)の出品一覧を10分ごとに確認し、次の2つを Discord に通知します。

- **新規出品**: 新しく作られた出品(出品IDが前回までに見た最大IDより大きいもの)
- **値下げ**: 記録していた価格より下がった出品、または一覧に「元の価格」が表示されている出品
  (価格帯の外から値下げで入ってきた出品も含む)

古い出品が説明文の編集などで一覧の上に来ただけのものは通知しません。

- 監視するURL・表示名は `config.json` で変更できます(価格は URL の `low_price` / `high_price` で絞り込み)。
  サイト側が価格の絞り込みを無視することがあるため、スクリプト側でも同じ価格帯で絞り込みます。
- 一覧の先頭 `pages` ページ(既定 3ページ ≒ 120件)を確認します。
- 初回実行は現在の出品と価格を記録するだけで、通知はしません。

## 仕組み

- Cloudflare Worker(`src/worker.js`)が10分ごとに一覧を確認し、状態(最大ID・価格)を D1 に保存します。
  GitHub Actions のサーバーからはサイトに接続できない(403・応答なし)ため Cloudflare で動かしています。
- `https://gametrade-watch.<サブドメイン>.workers.dev/status` で最後の実行結果を確認できます。
- 判定などの本体は `src/core.js`(テストは `npm test`)。

## 設定

1. Discord で通知したいチャンネルの「設定 → 連携サービス → ウェブフック → 新しいウェブフック」で URL をコピー
2. GitHub のリポジトリ「Settings → Secrets and variables → Actions」に `GAMETRADE_DISCORD_WEBHOOK` として登録
3. `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID` は notify と共用(追加の権限は不要)
4. main に入るとデプロイされ、10分ごとに動きます(「Actions → gametrade-watch → Run workflow」で再デプロイ)

## 手元で試す

```sh
cd gametrade-watch
node watch.mjs --dry-run   # 通知も保存もせず、通知対象を表示
npm test
```
