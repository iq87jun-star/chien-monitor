# デュエマ国内相場モニター(duema-souba.com 予定)

デュエル・マスターズの未開封BOXと高額シングルの国内相場を楽天市場の出品から
全自動で集計し、騰落・高額・出品僅少ランキングとAI日本語解説記事を掲載する
相場データサイト。pokeca/ と同一構造の横展開(楽天ウォッチリスト型・全体の12サイト目)。

- ドメイン `duema-souba.com` は空き確認済み(2026-08-25・新規取得でよい)
- データ出典: 楽天市場商品検索API。アプリIDは既存サイトと共用
  (`RAKUTEN_APP_ID` / 個別なら `DUEMA_RAKUTEN_APP_ID`)
- ウォッチリスト: BOX 3種+高額シングル7種で開始(**デュエマは高額シングルの
  入れ替わりが激しいため、環境変化のたびに watchlist の手入れが特に重要**)

## セットアップ(公開まで)

1. `duema-souba.com` を取得(標準価格確認のうえ)
2. Secrets: 楽天アプリIDは共用の `RAKUTEN_APP_ID` がそのまま使われる
3. mainへマージ → 公開用空リポジトリ作成 → `TORECA_DEPLOY_TOKEN` のPATに追加
   → Secretsに `DUEMA_DEPLOY_REPO` → workflow_dispatch実行 → Pages設定
   → カスタムドメイン `duema-souba.com` → DNSにAレコード4つ
4. Search Console 登録

## X速報bot(任意)

Secrets: `DUEMA_X_API_KEY` / `DUEMA_X_API_SECRET` / `DUEMA_X_ACCESS_TOKEN` /
`DUEMA_X_ACCESS_TOKEN_SECRET`

## 注意事項

- 楽天規約(1req/秒・クレジット表記)は pokeca/ と同一実装で遵守
- 価格は楽天市場の出品価格の参考値。転売・投資助言をしない
- 本サイトは株式会社タカラトミー・ウィザーズ・オブ・ザ・コースト・
  楽天グループ非公式のファンサイト。ドメインを第三者へ転売しない
