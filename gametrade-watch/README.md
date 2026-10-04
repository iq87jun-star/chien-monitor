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

ゲームトレードはクラウドのサーバー(GitHub Actions・Cloudflare)からのアクセスを 403 で拒否するため、
取得と判定を分けています。

1. **取得**: Claude の定期実行(Routine、1時間ごと)が `relay.mjs` で一覧ページを取得し、Worker に送る
2. **判定・通知**: Cloudflare Worker(`src/worker.js`)の `POST /ingest` が出品を判定して Discord に通知し、状態(最大ID・価格)を D1 に保存

- `/ingest` には合言葉が必要です。合言葉は Routine の指示文にだけあり、`wrangler.toml` には SHA-256 だけを置いています
- `https://gametrade-watch.iq87jun.workers.dev/status` で最後の実行結果を確認できます
- 判定などの本体は `src/core.js`(テストは `npm test`)

## ゲームクラブ(gameclub.jp)

ゲームクラブはクラウドのサーバーからのアクセスにボット対策の確認画面を返すため、**自宅の PC** から送ります。

- `pc/gameclub-relay.ps1`: 一覧(`config.gameclub.json` の URL・価格帯。毎回 GitHub から読むので変更に再インストールは不要)の全ページを取得し、Worker の `POST /ingest` に `{"site": "gameclub", ...}` で送る
- `pc/install-gameclub.ps1 -Token <合言葉>`: `C:\chien\gameclub` にスクリプトを置き、毎日 22:40 のタスク `gameclub_watch` を登録して1回実行(ログは `relay.log`)
- 判定は `config.gameclub.json` と `src/core.js` の `parseGameclub`。価格帯の出品を毎回すべて見ているので、記録のない古い出品が現れたら【価格変更】として通知する(価格帯の外から入ってきた)
- 状態は価格帯ごとに保存する(価格帯を変えた次の回は記録のみ)。実行結果は `https://gametrade-watch.iq87jun.workers.dev/status?site=gameclub`

## 設定

1. Discord で通知したいチャンネルの「設定 → 連携サービス → ウェブフック → 新しいウェブフック」で URL をコピー
2. GitHub のリポジトリ「Settings → Secrets and variables → Actions」に `GAMETRADE_DISCORD_WEBHOOK` として登録
3. `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID` は notify と共用(追加の権限は不要)
4. main に入ると Worker がデプロイされます(「Actions → gametrade-watch → Run workflow」で再デプロイ)

## 手元で試す

```sh
cd gametrade-watch
node watch.mjs --dry-run   # 通知も保存もせず、通知対象を表示
npm test
```
