# ポケカ国内相場モニター(pokeca.tokyo)

ポケモンカードの未開封BOX(シュリンク付き)と高額シングル・プロモの国内相場を
楽天市場の出品から全自動で集計し、騰落・高額・出品僅少ランキングと
AI日本語解説記事を掲載する相場データサイト。確立済みパイプラインの8サイト目。
海外相場の pokeca-kaigai.com(toreca/)と対になる国内版で、相互リンクで送客し合う。

**ドメイン戦略**: `pokeca.tokyo` は2019〜2025年末まで運営されていたポケカまとめ
速報ブログ「ポケカミン」の失効ドメインを再取得したもの(2026-08-21取得・初年0円)。
記事URLのインデックス残存・指名検索が期待できる、テーマ完全一致の中古ドメイン。
フッターに旧ブログと無関係の注記を入れてある。
新規ドメイン(pokeca-kaigai.com)・閉店店舗中古(pocketduel.tokyo)との
3方式比較実験の3本目でもある。

## 仕組み

cosme/ と同一の楽天ウォッチリスト方式:

- データ出典: [楽天市場商品検索API](https://developers.rakuten.com/)(無料アプリID)。
  `content/watchlist.json` の各アイテム(BOX 20種+シングル12種で開始)を検索し、
  出品価格の最安値・中央値・件数を記録(サーチ済み・オリパ等はNGワードで除外)
- **騰落率は自前の価格履歴から計算**(7日比・中央値ベース)
- 商品リンクは楽天アフィリエイトURL(アフィリエイトID設定時)= 収益導線
- 1日2回GitHub Actionsが自動更新。急騰検知でX速報(任意)
- 転売・投資助言をしない方針をAI記事プロンプトと検品ゲートで担保

## セットアップ(公開まで)

1. ~~ドメイン取得~~ ✅ 済み(お名前.com・2026-08-21)。**ドメイン情報認証メールの
   リンクを2週間以内にクリックすること**(未認証だと利用制限される)
2. **楽天アプリID**(必須・無料): cosme用と同じIDが使い回せる。Secretsに
   `RAKUTEN_APP_ID`(共通)または `POKECA_RAKUTEN_APP_ID`(個別)を設定。
   アフィリエイトIDは `RAKUTEN_AFFILIATE_ID` または `POKECA_RAKUTEN_AFFILIATE_ID`
3. このブランチをmainにマージ
4. 公開用の空リポジトリを作成(例: `pokeca-tokyo`)
5. デプロイ用PAT(`TORECA_DEPLOY_TOKEN`)の対象リポジトリに新リポジトリを追加
6. Secretsに `POKECA_DEPLOY_REPO` を `owner/repo` 形式で追加
7. workflow_dispatchで手動実行 → 新リポジトリの Settings → Pages で `gh-pages` を
   公開設定 → Custom domain に `pokeca.tokyo` を設定
8. お名前.comのDNSレコード設定でAレコード4つ(185.199.108〜111.153)を追加
9. **Google Search Console に登録**(重要): 旧ポケカミンの残存被リンクが
   「リンク」レポートで確認できる。旧記事URL(/archives/…)への404流入が多ければ
   トップへの301リダイレクト導入を検討(GitHub Pagesでは404.htmlでJS転送)

## 運用

- 新弾発売のたびに watchlist.json へBOXを追加(9〜12月と新弾直後が相場の動き時)
- BOX定価(公式発表)が確認できたら msrp を記入 → プレミア率が表示される
- `public/og.png` の作成(未作成でも動作はする)

## X速報bot(任意)

Secretsに `POKECA_X_API_KEY` / `POKECA_X_API_SECRET` / `POKECA_X_ACCESS_TOKEN` /
`POKECA_X_ACCESS_TOKEN_SECRET` を登録すると有効化(手順はtoreca/README.md参照)。

## 注意事項

- 楽天ウェブサービスの規約に従い1秒1回以下・クレジット表記をフッターに掲載
- 価格は楽天市場の出品価格の参考値で、公式価格・買取価格ではない旨を明記
- 転売・投資の助言をしない。定価超え購入を促す表現をしない
- 本サイトは株式会社ポケモン・任天堂・クリーチャーズ・ゲームフリーク・
  楽天グループ非公式のファンサイト
