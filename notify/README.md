# トレカ値下がり通知(Discord 版)

ポケカ・遊戯王・ワンピースカードの**海外相場**が、利用者が決めた金額以下になったら Discord に通知するサービス。
相場データはブラウザ拡張と同じ公開 JSON(pokeca-kaigai.com・pocketduel.tokyo、1日2回更新)を使う。

狙い: 拡張は「いま見ている商品の相場」しか出せない。「欲しいカードが安くなったら知りたい」を無料3枚・
有料プラン(月額300円・50枚、Stripe)で提供する。LINE 版は後から追加する。

## 仕組み

```
利用者 ─ 登録ページ(public/)──── /api/*(src/worker.js・Cloudflare Worker)── D1(登録者・カード)
            │ 検索・現在価格は相場JSONをブラウザで直接読む                              ▲
            │                                                                          │ D1 HTTP API
GitHub Actions(notify ワークフロー・1日4回)── scripts/check.mjs ──────────────────────┘
            └ 相場JSONが前回から更新されていれば、目標額以下のカードを Discord のウェブフックに投稿
```

- **登録**: 利用者は Discord のチャンネルで作ったウェブフックURLを貼るだけ(アカウント登録なし)。
  URL は Discord に実在するかを投稿せずに確認してから登録し、管理キーを発行する。
  管理キーはブラウザの localStorage に置き、同じ内容の設定用リンク(`/#k=…`)をチャンネルにも投稿する
  (別の端末から開く用)。サーバーはキーの SHA-256 だけを保存する
- **通知**: 目標額以下になったら1回だけ通知し、相場が目標の5%超まで戻ったら次の値下がりに備える
  (`src/check.js` の `evaluate`)。登録者ごとに1メッセージ(最大10枚)にまとめる。
  送信に失敗したカードは次回また送り、ウェブフックが削除されていたら(404)その登録者を止める
- **カードの識別**: `public/prices.js` の `buildCards`。ポケカは セット-番号、遊戯王は英語名、
  ワンピースは カード番号+版(同じ番号・版の再録は最安値)
- **チェックを Worker でなく Actions で行う理由**: 相場 JSON が合計約800KBあり、
  Workers 無料プランの CPU 時間(1回10ms)では読み込めないため。Worker は登録APIだけにして軽くしている
- **プラン**: `src/plans.js` の `LIMITS`(free 3枚・pro 50枚)
- **有料プラン**(`src/billing.js`): 申し込みは Stripe Checkout、支払い方法の変更・解約は Stripe の
  カスタマーポータル。Stripe からの Webhook(`/api/stripe/webhook`・署名を検証)で
  `checkout.session.completed` → pro、`customer.subscription.updated`(未払い等)/ `deleted` → free。
  支払いの再試行中(past_due)は pro のまま。無料に戻って上限を超えた分は、先に登録した順に上限枚数だけ通知する。
  登録を削除すると契約も解約する。Stripe の設定が無ければ申し込みは表示しない

## 開発

```bash
cd notify
npm ci
npm test            # 単体テスト(API・値下がり判定・有料プラン・相場データの読み込み。DBは node:sqlite)
npm run test:e2e    # ローカルの Worker(wrangler dev)+偽の Discord・Stripe+Chromium で、
                    # 登録→追加→有料プランの申し込み・解約→通知→削除まで
npm run dev         # 手元で Worker を起動(先に npx wrangler d1 migrations apply toreca-notify --local)
```

## 公開手順(初回だけ・15分ほど)

1. **Cloudflare に登録**(無料): https://dash.cloudflare.com/sign-up
2. ダッシュボードの「Workers & Pages」を一度開き、**workers.dev のサブドメイン**を決める
   (例: `pokeca` → 公開URLは `https://toreca-notify.pokeca.workers.dev`)
3. **API トークンを作る**: 右上のアイコン →「プロフィール」→「API トークン」→「トークンを作成」→
   テンプレート「Cloudflare Workers を編集する」を選び、「権限」に **アカウント / D1 / 編集** を1行追加して作成
4. **アカウントID を控える**: 「Workers & Pages」の右側に表示される「アカウント ID」
5. GitHub のリポジトリの Settings → Secrets and variables → Actions に登録:
   - `CLOUDFLARE_API_TOKEN` … 手順3のトークン
   - `CLOUDFLARE_ACCOUNT_ID` … 手順4のID
6. Actions →「notify」→「Run workflow」(main)。deploy ジョブが D1 データベースの作成・テーブル作成・
   Worker の公開まで行う。ログの `https://toreca-notify.<サブドメイン>.workers.dev` が登録ページ

以後は `notify/` の変更を main に入れると自動で再デプロイされ、値下がりチェックは1日4回自動で動く。
Actions の「Run workflow」で「相場データが更新されていなくても値下がりチェックする」にチェックを入れると、
すぐにチェックできる(動作確認用)。

## 有料プランの公開手順(Stripe・無料プランの公開後に)

1. **Stripe に登録**: https://dashboard.stripe.com/register 。本番で決済を受けるには、事業者情報・
   本人確認・振込先口座の登録と審査が必要(数日かかることがある)。それまではテストモードで動作確認できる
2. **特定商取引法に基づく表記**: `public/tokushoho.html` の【】の箇所(氏名・メールアドレス等)を書き換えて
   main に入れる。有料で販売するには法律上この表記が必要。Stripe の審査でもこのページのURLを聞かれる
   (`https://toreca-notify.<サブドメイン>.workers.dev/tokushoho.html`)
3. **商品と価格を作る**: Stripe の「商品カタログ」→「商品を追加」→ 名前「トレカ値下がり通知 有料プラン」、
   価格「300円・継続・毎月」。作成後の価格ID(`price_…`)を控える。価格を変える時は `wrangler.toml` の
   `PRICE_LABEL` と `tokushoho.html` も合わせる
4. **カスタマーポータルを有効にする**: 「設定」→「Billing」→「カスタマーポータル」で有効化し、
   「サブスクリプションのキャンセル」を許可(「請求期間の終了時にキャンセル」を選ぶ)
5. **Webhook を登録**: 「開発者」→「Webhook」→「エンドポイントを追加」。URL は
   `https://toreca-notify.<サブドメイン>.workers.dev/api/stripe/webhook`、イベントは
   `checkout.session.completed`・`customer.subscription.updated`・`customer.subscription.deleted`。
   作成後の「署名シークレット」(`whsec_…`)を控える
6. **API キー**: 「開発者」→「API キー」のシークレットキー(`sk_live_…`。テスト中は `sk_test_…`)。
   制限付きキーにする場合は Checkout Sessions・Customer portal・Subscriptions の書き込み権限を付ける
7. GitHub の Secrets に `STRIPE_SECRET_KEY`・`STRIPE_PRICE_ID`・`STRIPE_WEBHOOK_SECRET` を登録し、
   Actions の「notify」を実行。3つ揃うと登録ページに「有料プランにする」が表示される

テストモードの鍵(`sk_test_…` と、テストモードで作った価格・Webhook)で先に一通り試し、
カード番号 `4242 4242 4242 4242` で申し込み → 解約まで確認してから本番の鍵に差し替えると安全。

## 今後

- LINE 版: LINE 公式アカウント(Messaging API)。LINE Notify は2025年3月に終了したため使えない
- 拡張のバッジに「値下がり通知を設定」リンク(カードを選んだ状態で登録ページを開く)
- 独自ドメイン(例: notify.pokeca-kaigai.com)。pokeca-kaigai.com の DNS を Cloudflare に移す必要がある
