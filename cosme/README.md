# 限定コスメ相場モニター(cosme-press.com)

クリスマスコフレ・限定コスメ・廃盤コスメ・廃盤香水の「今の二次流通価格」を
楽天市場の出品から全自動で集計し、プレミア率・騰落・出品僅少ランキングと
AI日本語解説記事を掲載する相場データサイト。確立済みパイプラインの7サイト目
(トレカ以外の新ジャンル第1弾・美容×価格データのブルーオーシャン狙い)。

**ドメイン戦略**: `cosme-press.com` は2018〜2025年に運営されていた
芸能プロダクション「COSME PRESS」(コスメ企画開発も手がけた日本語サイト)の
失効ドメインを再取得する想定。テーマ隣接の中古ドメイン効果を狙う。
**注意**: 同名の現役サイト cosmepress.jp(コスメニュース)があるため、
サイト名は「コスメプレス」ではなく「限定コスメ相場モニター」で通す。
フッターに旧運営と無関係の注記を入れてある。

## 仕組み

- データ出典: [楽天市場商品検索API](https://developers.rakuten.com/)
  (無料アプリID)。`content/watchlist.json` の各アイテムを検索し、
  出品価格の最安値・中央値・件数を記録する(空箱・サンプル等はNGワードで除外)
- **騰落率は自前の価格履歴から計算**(7日比。このAPIは現在の出品のみのため、
  毎日記録して蓄積する。稼働開始から数日で騰落ランキングが出現する)
- **プレミア率** = 定価(watchlistのmsrp)に対する最安出品の上乗せ率。
  msrpは公式情報で確認できたものだけ入れる(未設定は初回記録比で代用)
- 商品リンクは楽天アフィリエイトURL(アフィリエイトID設定時)= 収益導線
- 1日2回GitHub Actionsが自動更新
- 薬機法・YMYL対策: 効果・効能には一切触れず価格データの解説に徹する
  (AI記事のプロンプトと検品ゲートで担保)

## 構成

toreca/duel と同一構造(config / fetch-data / aggregate / generate-articles /
validate / post-x / gen-pages / run)。validate.mjs は全サイト共通。

## セットアップ(公開まで)

1. **ドメイン取得**: お名前.com等で `cosme-press.com` を取得
   (取得前に標準価格であることを確認)
2. **楽天アプリID発行**(必須・無料): [Rakuten Developers](https://developers.rakuten.com/)
   でアプリ登録 → Secretsに `COSME_RAKUTEN_APP_ID` を追加。
   あわせて楽天アフィリエイトIDを `COSME_RAKUTEN_AFFILIATE_ID` に設定すると
   商品リンクが収益化される
3. このブランチをmainにマージ
4. 公開用の空リポジトリを作成(例: `cosme-press`)
5. デプロイ用PAT(toreca用の `TORECA_DEPLOY_TOKEN`)の対象リポジトリに
   新リポジトリを**追加**(GitHub Settings → Fine-grained tokens → 編集。値は変わらない
   のでSecrets更新は不要)
6. Secretsに `COSME_DEPLOY_REPO` を `owner/repo` 形式で追加
7. workflow_dispatchで手動実行 → 新リポジトリの Settings → Pages で
   `gh-pages` を公開設定 → Custom domain に `cosme-press.com` を設定
8. お名前.comのDNSレコード設定でAレコード4つ(185.199.108〜111.153)を追加

## 運用(サイトの質を上げる3レバー)

1. **watchlist の手入れが最重要**。コフレ商戦期(9〜12月)に新作を追加し、
   検索ノイズが多いアイテムは query をブランド正式名+コレクション名で絞る
2. **msrp(税込定価)の記入**。公式発表やプレスリリースで確認できた定価を
   入れるほど「プレミア率」ランキングが充実する(サイトの看板コーナー)
3. `public/og.png` の作成(OGP画像。未作成でも動作はする)

## X速報bot(任意)

コスメbot用のXアカウントで開発者登録し、Secretsに
`COSME_X_API_KEY` / `COSME_X_API_SECRET` / `COSME_X_ACCESS_TOKEN` /
`COSME_X_ACCESS_TOKEN_SECRET` を登録すると有効化(手順はtoreca/README.md参照)。

## 注意事項

- 楽天ウェブサービスの利用規約に従い、リクエストは1秒1回以下・クレジット表記
  (Supported by Rakuten Developers)をフッターに掲載している
- 価格は楽天市場の出品価格(検索上位)からの参考値であり、公式販売価格・
  買取価格ではない旨をサイト内に明記している
- 化粧品の効果・効能を記載しない(薬機法配慮)。転売・投資の助言をしない
- 本サイトは各ブランド・楽天グループ非公式の個人サイト
