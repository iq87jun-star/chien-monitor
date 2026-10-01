# Cowork 用の作業指示(Stripe: トレカ値下がり通知の有料プランの設定)

この文書を Cowork にそのまま渡して使う。人が行う作業(★)と、Cowork に任せる作業を分けてある。
Cowork は「止まる」と書かれた所で必ず作業を止め、人に確認すること。
共通の決まりは [cowork/README.md](../cowork/README.md)。

**最初はすべてテストモード**で行う(お金は動かない)。本番への切り替えは、テストで申し込み→解約まで確かめてから人が行う。

| 作業 | 内容 |
|---|---|
| S1 | 商品と価格(300円・毎月)を作る |
| S2 | カスタマーポータルを有効にする |
| S3 | Webhook を登録する |
| S4 | 人が GitHub の Secrets に3つの値を登録する(★) |

## 守ること(Cowork 向け)

- 画面右上の「テストモード」(または「サンドボックス」)が **ON** であることを、作業の前と各作業の後に確かめる。OFF なら止まる
- パスワード・2段階認証・本人確認・事業者情報・銀行口座・カード番号は入力しない。その画面に来たら止まる
- 「本番環境に切り替え」「アカウントを有効化」は押さない
- **シークレットキー(`sk_…`)と署名シークレット(`whsec_…`)は表示・コピーしない**。Issue・会話・メモにも書かない(登録は人が行う)
- 価格ID(`price_…`)は秘密ではないので、報告に書いてよい

## 事前準備(★人が行う)

1. パソコンの Chrome で Stripe(https://dashboard.stripe.com)にログインし、テストモードにしておく
2. Cowork に「https://github.com/iq87jun-star/chien-monitor/blob/main/notify/cowork-stripe.md の作業をして」と伝える

## 作業S1: 商品と価格(Cowork)

1. 「商品カタログ」→「商品を追加」
2. 次を入れて保存する
   - 名前: `トレカ値下がり通知 有料プラン`
   - 説明: `登録できるカードが50枚になります(無料は3枚)。`
   - 価格: `300`・通貨 `JPY`・「継続」・請求期間「毎月」
   - 税: 「価格に税を含める」があれば「含める」(税込300円)
3. 作った価格の **価格ID(`price_` で始まる)** を控える(報告に書く)

## 作業S2: カスタマーポータル(Cowork)

1. 「設定」→「Billing」→「カスタマーポータル」を開く
2. 次を有効にして保存する
   - 「顧客による支払い方法の更新」: 許可
   - 「サブスクリプションのキャンセル」: 許可・**「請求期間の終了時にキャンセル」**
   - 「サブスクリプションの更新(プラン変更)」: 許可しない
3. 「ビジネス情報」で、利用規約・プライバシーポリシーの URL を聞かれたら次を入れる
   - 利用規約(または特定商取引法に基づく表記): `https://toreca-notify.iq87jun.workers.dev/tokushoho.html`
   - それ以外の項目は空のままでよい

## 作業S3: Webhook(Cowork)

1. 「開発者」(または「ワークベンチ」)→「Webhook」→「エンドポイントを追加」(「送信先を追加」)
2. 次を入れて保存する
   - URL: `https://toreca-notify.iq87jun.workers.dev/api/stripe/webhook`
   - イベント: `checkout.session.completed`・`customer.subscription.updated`・`customer.subscription.deleted` の3つだけ
   - API バージョンを聞かれたら既定のまま
3. 署名シークレットは**表示しない**。保存できたら止まる

## 報告(Cowork)

人に知らせるのに加えて、cowork/README.md の「報告の出し方」のとおり GitHub の Issue(「Cowork の作業報告」)に書き、
Issue の番号を人に伝える。書くこと: 各作業の結果・価格ID・テストモードだったこと・止まった所と画面の文言。
最後に人へ「S4(Secrets の登録)をお願いします」と伝える。

## 作業S4: GitHub の Secrets(★人が行う)

https://github.com/iq87jun-star/chien-monitor/settings/secrets/actions/new で、次の3つを1つずつ登録する(1行・前後に空白なし)。

| Name | Secret(値) | 取る場所 |
|---|---|---|
| `STRIPE_SECRET_KEY` | `sk_test_…` | Stripe「開発者」→「API キー」の**シークレットキー**の「表示」→コピー |
| `STRIPE_PRICE_ID` | `price_…` | S1 の価格ID(Cowork の報告にある) |
| `STRIPE_WEBHOOK_SECRET` | `whsec_…` | S3 の Webhook の画面の「署名シークレット」の「表示」→コピー |

登録したら Claude Code に「Stripe の Secrets を登録しました」と伝える。Claude Code が通知サービスを公開し直し、
テストカード(`4242 4242 4242 4242`)で申し込み→解約まで確かめる手順を案内する。
