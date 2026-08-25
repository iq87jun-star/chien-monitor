# ワンピカ国内相場モニター(opcg-souba.com 予定)

ワンピースカードゲームの未開封BOX(シュリンク付き)と高額パラレル・コミパラの
国内相場を楽天市場の出品から全自動で集計し、騰落・高額・出品僅少ランキングと
AI日本語解説記事を掲載する相場データサイト。pokeca/ と同一構造の横展開
(楽天ウォッチリスト型の3サイト目・全体の11サイト目)。

- ドメイン `opcg-souba.com` は空き確認済み(2026-08-25・新規取得でよい。
  「ONE PIECE」フル表記をドメインに含めるのは商標リスクが上がるため
  略称 OPCG を採用)
- データ出典: 楽天市場商品検索API。アプリIDは既存サイトと共用
  (`RAKUTEN_APP_ID` / 個別なら `OPCG_RAKUTEN_APP_ID`)
- ウォッチリスト: ブースターBOX 10種+高額パラレル10種で開始

## セットアップ(公開まで)

1. `opcg-souba.com` を取得(標準価格確認のうえ)
2. Secrets: 楽天アプリIDは共用の `RAKUTEN_APP_ID` がそのまま使われる
3. mainへマージ → 公開用空リポジトリ作成 → `TORECA_DEPLOY_TOKEN` のPATに追加
   → Secretsに `OPCG_DEPLOY_REPO` → workflow_dispatch実行 → Pages設定
   → カスタムドメイン `opcg-souba.com` → DNSにAレコード4つ
4. Search Console 登録

## X速報bot(任意)

Secrets: `OPCG_X_API_KEY` / `OPCG_X_API_SECRET` / `OPCG_X_ACCESS_TOKEN` /
`OPCG_X_ACCESS_TOKEN_SECRET`

## 注意事項

- 楽天規約(1req/秒・クレジット表記)は pokeca/ と同一実装で遵守
- 価格は楽天市場の出品価格の参考値。転売・投資助言をしない
- 本サイトは集英社・尾田栄一郎氏・バンダイ・楽天グループ非公式のファンサイト。
  このドメインを第三者へ転売しない(商標を含む略称のため)
- 新弾発売のたびに watchlist.json へBOXを追加。BOX定価が確認できたら msrp を記入
