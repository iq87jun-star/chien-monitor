# 遊戯王海外相場モニター(pocketduel.tokyo)

遊戯王カード(海外版TCG)の海外市場価格を全自動で収集し、円換算つきの高額・騰落ランキングと
AI日本語解説記事を掲載する統計サイト。確立済みパイプラインの6サイト目(トレカ第2弾)。

**ドメイン戦略の実験台**: `pocketduel.tokyo` は秋葉原の遊戯王系デュエルカフェ
(POCKET DUEL Cafe&Bar・2022年閉店)の旧ドメインを再取得したもの。テーマが一致する
中古ドメインの効果を、新規ドメインのポケカサイト(pokeca-kaigai.com)と比較する。

- データ出典: [YGOPRODeck](https://ygoprodeck.com)(キー不要の公開API・全1.4万枚の
  Cardmarket €/TCGplayer $価格)+ [Frankfurter](https://frankfurter.dev)(ECB為替)
- 1日2回GitHub Actionsが自動更新
- **騰落率は自前の価格履歴から計算**(このAPIは現在価格のみのため、€0.30以上の
  約3,000枚を毎日記録して7日比を算出。稼働開始から数日で騰落ランキングが出現する)
- 独自コーナー: 海外(TCG)リミットレギュレーション対象カードの価格一覧
- カード名は英語(TCG)表記 — eBay等の海外取引で実際に使う名称のため、輸出セラーには
  むしろ実用的

## 構成

toreca/ と同一構造(config / fetch-data / aggregate / generate-articles / validate /
post-x / gen-pages / run)。validate.mjs は全サイト共通。

## セットアップ(公開まで)

1. このブランチをmainにマージ
2. 公開用の空リポジトリを作成(例: `pocketduel`)
3. デプロイ用PAT(toreca用の `TORECA_DEPLOY_TOKEN`)の対象リポジトリに
   新リポジトリを**追加**(GitHub Settings → Fine-grained tokens → 編集。値は変わらない
   のでSecrets更新は不要)
4. Secretsに `DUEL_DEPLOY_REPO` を `owner/repo` 形式で追加
5. workflow_dispatchで手動実行 → 新リポジトリの Settings → Pages で
   `gh-pages` を公開設定 → Custom domain に `pocketduel.tokyo` を設定
6. お名前.comのDNSレコード設定でAレコード4つ(185.199.108〜111.153)を追加

## X速報bot(任意)

遊戯王bot用のXアカウントで開発者登録し、Secretsに
`DUEL_X_API_KEY` / `DUEL_X_API_SECRET` / `DUEL_X_ACCESS_TOKEN` /
`DUEL_X_ACCESS_TOKEN_SECRET` を登録すると有効化(手順はtoreca/README.md参照)。

## 注意事項

- YGOPRODeckのガイドラインに従い、全カード取得は1リクエスト・1日2回に留め、
  カード画像はホットリンクしない(本サイトは画像非表示)
- 本サイトはKONAMI・Cardmarket・TCGplayer非公式のファンサイト。
  記事は投資・売買の助言ではない旨をサイト内に明記している
