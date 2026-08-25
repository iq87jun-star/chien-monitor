# MTG海外相場モニター(mtg-kaigai.com 予定)

MTG(マジック:ザ・ギャザリング)英語版カードの海外市場価格を**全自動**で収集し、
円換算つきの高額・騰落ランキングとAI日本語解説記事を掲載する統計サイト。
確立済みパイプラインの7サイト目(トレカ第3弾)。duel/ と同一構造の横展開。

- データ出典: [Scryfall](https://scryfall.com)(キー不要の公開API・TCGplayer $/Cardmarket €価格)
  + [Frankfurter](https://frankfurter.dev)(ECB為替)
- 監視対象は**紙で発売済みの直近4セット**(エキスパンション/コア/マスターズ等)。
  発売直後で価格未整備のセットは自動スキップし、次の候補に繰り下げる
- 1日2回GitHub Actionsが自動更新
- **騰落率は自前の価格履歴から計算**(Scryfallは現在価格のみのため、$0.50以上のカードを
  毎日記録して7日比を算出。稼働開始から数日で騰落ランキングが出現する)
- 通常版価格が無いカードはFoil版価格を採用し「Foil」表示で区別

## 構成

toreca/・duel/ と同一構造(config / fetch-data / aggregate / generate-articles / validate /
post-x / gen-pages / run)。validate.mjs は全サイト共通。

## セットアップ(公開まで)

1. このブランチをmainにマージ
2. ドメイン `mtg-kaigai.com` を取得(別ドメインにする場合は
   `pipeline/config.mjs` 周辺ではなく `pipeline/gen-pages.mjs` / `pipeline/post-x.mjs` の
   `SITE_URL`、`index.html` のcanonical/OGP、`public/robots.txt`、
   ワークフローの `cname` を書き換える)
3. 公開用の空リポジトリを作成(例: `mtg-kaigai`)
4. デプロイ用PAT(toreca用の `TORECA_DEPLOY_TOKEN`)の対象リポジトリに
   新リポジトリを**追加**(GitHub Settings → Fine-grained tokens → 編集。値は変わらない
   のでSecrets更新は不要)
5. Secretsに `MTG_DEPLOY_REPO` を `owner/repo` 形式で追加
6. workflow_dispatchで手動実行 → 新リポジトリの Settings → Pages で
   `gh-pages` を公開設定 → Custom domain に `mtg-kaigai.com` を設定
7. DNSレコード設定でAレコード4つ(185.199.108〜111.153)を追加
8. OGP画像 `public/og.png`(1200×630)を用意して追加(未追加でも動作はする)

## X速報bot(任意)

MTG bot用のXアカウントで開発者登録し、Secretsに
`MTG_X_API_KEY` / `MTG_X_API_SECRET` / `MTG_X_ACCESS_TOKEN` /
`MTG_X_ACCESS_TOKEN_SECRET` を登録すると有効化(手順はtoreca/README.md参照)。

## ローカル実行

```bash
cd mtg
npm install
npm run pipeline     # 収集→集計→記事生成(記事生成は要 ANTHROPIC_API_KEY)
npm run dev          # 開発サーバー
npm run build        # 本番ビルド → dist/
```

## 注意事項

- Scryfallのガイドラインに従い、リクエスト間隔は100ms程度を空け、
  説明的なUser-Agentを送信する。カード画像はホットリンクしない(本サイトは画像非表示)
- 本サイトはWizards of the Coast・TCGplayer・Cardmarket・Scryfall非公式のファンサイト。
  記事は投資・売買の助言ではない旨をサイト内に明記している
