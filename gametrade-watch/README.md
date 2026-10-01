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

## 設定

1. Discord で通知したいチャンネルの「設定 → 連携サービス → ウェブフック → 新しいウェブフック」で URL をコピー
2. GitHub のリポジトリ「Settings → Secrets and variables → Actions」に `GAMETRADE_DISCORD_WEBHOOK` として登録
3. このフォルダと `.github/workflows/gametrade-watch.yml` が main に入ると10分ごとに動きます
   (「Actions → gametrade-watch → Run workflow」で手動実行も可)

## ローカルで試す

```sh
node gametrade-watch/watch.mjs --dry-run   # 通知も保存もせず、通知対象を表示
```
