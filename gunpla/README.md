# ガンプラ相場モニター(gunpla-souba.com 予定)

ガンプラの人気キット・プレ値キットの相場を楽天市場の出品から全自動で集計し、
騰落・高額・出品僅少ランキングとAI日本語解説記事を掲載する相場データサイト。
pokeca/ と同一構造の横展開(楽天ウォッチリスト型・全体の13サイト目)。

- ドメイン `gunpla-souba.com` は空き確認済み(2026-08-25・新規取得でよい)
- データ出典: 楽天市場商品検索API。アプリIDは既存サイトと共用
  (`RAKUTEN_APP_ID` / 個別なら `GUNPLA_RAKUTEN_APP_ID`)
- ウォッチリスト: MGEX/PG/MG/RG/HGの人気・プレ値定番20種で開始。
  完成品・塗装済み・ジャンクはNGワードで除外し「新品キット」の相場に限定
- **ガンプラ固有の注意**: 再販が頻繁にあり、プレ値は再販発表で急落する。
  記事プロンプトに「再販で相場が下がることも頻繁にある」前提を組み込み済み。
  バンダイの再販スケジュール発表に合わせて watchlist を手入れすると価値が上がる

## セットアップ(公開まで)

1. `gunpla-souba.com` を取得(標準価格確認のうえ)
2. Secrets: 楽天アプリIDは共用の `RAKUTEN_APP_ID` がそのまま使われる
3. mainへマージ → 公開用空リポジトリ作成 → `TORECA_DEPLOY_TOKEN` のPATに追加
   → Secretsに `GUNPLA_DEPLOY_REPO` → workflow_dispatch実行 → Pages設定
   → カスタムドメイン `gunpla-souba.com` → DNSにAレコード4つ
4. Search Console 登録

## X速報bot(任意)

Secrets: `GUNPLA_X_API_KEY` / `GUNPLA_X_API_SECRET` / `GUNPLA_X_ACCESS_TOKEN` /
`GUNPLA_X_ACCESS_TOKEN_SECRET`

## 注意事項

- 楽天規約(1req/秒・クレジット表記)は pokeca/ と同一実装で遵守
- 価格は楽天市場の出品価格の参考値。転売・投資助言をしない。
  定価超え購入を促す表現をしない
- 本サイトは株式会社BANDAI SPIRITS・創通・サンライズ・楽天グループ非公式の
  ファンサイト。「ガンプラ」はバンダイの登録商標のため、このドメインを
  第三者へ転売しない
