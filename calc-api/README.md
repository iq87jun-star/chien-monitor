# Japan Salary & Real Estate Calculator API(計算API)

日本の求人の給与欄・物件ページの記載を、比べられる数字に変換する API。API マーケット(RapidAPI 等)で販売する。
計算の本体はブラウザ拡張(求人 年収チェッカー・物件 単価・月額チェッカー)の `parser.js` をそのまま使う。
自分で作った計算なので、相場データのような取得元の権利の問題がない。

## 仕組み

```
開発者 ──(APIキー)──> APIマーケット ──(秘密ヘッダーを付けて転送)──> Cloudflare Worker(src/worker.js)
          キー発行・回数制限・課金は                                   秘密ヘッダーを確かめて計算(src/calc.js)
          マーケットが行う                                               └ job-extension/src/parser.js
                                                                         └ realty-extension/src/parser.js
```

| エンドポイント | 入力 | 出力 |
|---|---|---|
| `POST /v1/salary/analyze` | 給与欄の文章(`salary`)、勤務時間・休日の文章(`workConditions`・任意) | 年収の目安・月給の幅・時給換算・固定残業代とそれを除いた額・記載の年収 |
| `POST /v1/realty/analyze` | 賃料または価格・面積・管理費・敷金礼金・利回り等(文字列は物件ページの表記のまま、数値は円・㎡・%) | ㎡/坪単価・実質月額・初期費用の目安・ローン返済・利回り |
| `GET /v1/health` | なし(認証不要) | 稼働確認 |
| `GET /openapi.json` | なし(認証不要) | 仕様書。マーケットへの登録に使う |

- **直接の呼び出しを断る**: マーケットは転送時に秘密のヘッダー(RapidAPI は `X-RapidAPI-Proxy-Secret`)を付ける。
  Secret の `MARKETPLACE_SECRETS`(`ヘッダー名:値`、複数のマーケットはカンマ区切り)と一致しない呼び出しは 403。
  **未設定の間は計算を返さない(503)**ので、設定し忘れて無料で使われることはない
- **仮定の明示**: 「1日8時間と仮定」のような仮定は `assumptions` にコード・日本語・英語で返す
- **データは保存しない**: 入力を受けて計算して返すだけ。データベースは使わない
- 拡張の `parser.js` を直すと、この API の結果も変わる。そのため calc-api ワークフローは
  `job-extension/src/parser.js`・`realty-extension/src/parser.js` の変更でもテストを走らせる

## 開発

```bash
cd calc-api
npm ci
npm test            # 単体テスト(実際の求人・物件の表記。出力が仕様書と一致するかも確認)
npm run test:e2e    # ローカルの Worker を起動し、マーケット経由と同じ形で呼ぶ
npm run dev         # 手元で起動(秘密ヘッダーの確認なし)
npx @redocly/cli lint src/openapi.json   # 仕様書の検査
```

## 公開手順(RapidAPI の場合)

1. **Cloudflare**: 値下がり通知(`notify/README.md`)で登録したアカウントと GitHub の Secrets
   (`CLOUDFLARE_API_TOKEN`・`CLOUDFLARE_ACCOUNT_ID`)をそのまま使う。まだなら先にそちらの手順1〜5を行う
2. Actions →「calc-api」→「Run workflow」(main)。公開URLは `https://jp-listing-calc-api.<サブドメイン>.workers.dev`
   (この時点では秘密ヘッダー未設定なので、計算は 503 を返す)
3. **RapidAPI に登録**: https://rapidapi.com でアカウントを作り、Studio(プロバイダー画面)で「Add API Project」
   → 仕様書(`src/openapi.json`)をアップロード → Base URL に手順2の URL を設定
4. **秘密ヘッダー**: API の設定の「Gateway」(または「Security」)タブに表示される `X-RapidAPI-Proxy-Secret` の値を控え、
   GitHub の Secrets に `MARKETPLACE_SECRETS` = `x-rapidapi-proxy-secret:<控えた値>` で登録 → もう一度「Run workflow」
5. **掲載情報**: `listing/marketplace.md` の名前・説明・カテゴリ・タグ・ロゴ(`listing/logo.png`)を貼る
6. **料金プラン**: 「Monetize」タブで `listing/marketplace.md` の料金案を設定し、売上の受け取り方法を登録する
7. RapidAPI の画面の「Test Endpoint」で呼んで結果が返ることを確かめ、公開(Public)にする

他のマーケット(APILayer・Zyla 等)にも出す場合は、そのマーケットの秘密ヘッダーを
`MARKETPLACE_SECRETS` にカンマ区切りで足す(例: `x-rapidapi-proxy-secret:abc,x-zyla-secret:def`)。
ヘッダー名はマーケットごとに違うので、各マーケットの説明に従う。

## 今後

- まとめて計算するエンドポイント(1回で最大100件)。大量に使う利用者向け
- 実績(利用者数・呼び出し回数)ができたら、企業への直接販売(個別契約・API キーを自前で発行)に広げる。
  その時は値下がり通知で作った Stripe 連携とキーの仕組みを流用できる
