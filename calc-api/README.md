# Japan Salary, Tax & Calendar Calculator API(計算API)

日本特有の計算をまとめた API。API マーケット(RapidAPI 等)で、テーマごとに4つの出品として販売する。
給与・物件の計算はブラウザ拡張(求人 年収チェッカー・物件 単価・月額チェッカー)の `parser.js` をそのまま使う。
どれも自分で作った計算か、再配布が自由な公的データ(内閣府の祝日・協会けんぽ等の料率)なので、取得元の権利の問題がない。

## 仕組み

```
開発者 ──(APIキー)──> APIマーケット ──(秘密ヘッダーを付けて転送)──> Cloudflare Worker(src/worker.js)
          キー発行・回数制限・課金は                                   秘密ヘッダーを確かめて計算(src/calc.js)
          マーケットが行う                                               └ job-extension/src/parser.js
                                                                         └ realty-extension/src/parser.js
```

| 出品 | エンドポイント | 入力 → 出力 |
|---|---|---|
| salary | `POST /v1/salary/analyze` | 給与欄の文章 → 年収の目安・月給の幅・時給換算・固定残業代・記載の年収 |
| realty | `POST /v1/realty/analyze` | 賃料/価格・面積・管理費等(表記のまま or 数値) → ㎡/坪単価・実質月額・初期費用・ローン・利回り |
| takehome | `POST /v1/takehome/calculate` | 月給・賞与・年齢・都道府県 → 社会保険料(内訳)・所得税・住民税・手取り(2026年度の率) |
| calendar | `POST /v1/calendar/day` | 日付 → 祝日名・曜日・営業日か・和暦 |
| calendar | `POST /v1/calendar/holidays` | 年 → その年の祝日一覧 |
| calendar | `POST /v1/calendar/add-business-days` | 日付・日数 → ○営業日後(前)の日付(年末年始・独自の休業日・曜日の指定可) |
| calendar | `POST /v1/calendar/count-business-days` | 期間 → 営業日数・期間中の祝日 |
| calendar | `POST /v1/wareki/convert` | 西暦 ⇔ 和暦(「令和6年4月1日」「R6.4.1」「平成元年」等) |
| — | `GET /v1/health` | 稼働確認(認証不要) |
| — | `GET /openapi.json[?product=…]` | 仕様書(出品ごとに絞れる。認証不要) |

- **直接の呼び出しを断る**: マーケットは転送時に秘密のヘッダー(RapidAPI は `X-RapidAPI-Proxy-Secret`)を付ける。
  Secret の `MARKETPLACE_SECRETS`(`ヘッダー名:値`、複数はカンマ区切り)と一致しない呼び出しは 403。
  マーケットは出品ごとに別の値を発行するので、`ヘッダー名:値@takehome` のように使える出品を付けておくと、
  ある出品の利用者が別の出品の計算を呼ぶことはできない
  **未設定の間は計算を返さない(503)**ので、設定し忘れて無料で使われることはない
- **仮定の明示**: 「1日8時間と仮定」のような仮定は `assumptions` にコード・日本語・英語で返す
- **データは保存しない**: 入力を受けて計算して返すだけ。データベースは使わない
- 拡張の `parser.js` を直すと、この API の結果も変わる。そのため calc-api ワークフローは
  `job-extension/src/parser.js`・`realty-extension/src/parser.js` の変更でもテストを走らせる

## 毎年の更新(大事)

手取りの計算は率・控除額が毎年変わる。**古い率のまま売ると信用を失う**ので、毎年この順に更新する。

| 時期 | 更新するもの | 場所 |
|---|---|---|
| 2〜3月 | 協会けんぽの都道府県別の健康保険料率・介護保険料率・子ども・子育て支援金率(3月分から) | `src/takehome.js` の `RATES` |
| 3〜4月 | 雇用保険料率(4月から) | 同上 |
| 12月〜翌春 | 税制改正(基礎控除・給与所得控除)。国税庁の「年末調整のしかた」 | 同上と `salaryIncomeForIncomeTax2026` |
| 毎月自動 | 祝日(内閣府が例年2月ごろ翌年分を追加)。ワークフローが赤くなったら `npm run holidays` | `src/holidays.json` |

新しい年度は `RATES` に年を足し、`DEFAULT_YEAR` を進め、テストの手計算の例も新しい率で作り直す。

## 開発

```bash
cd calc-api
npm ci
npm test            # 単体テスト(実際の求人・物件の表記、手取りの手計算例、祝日・和暦。出力が仕様書と一致するかも確認)
npm run holidays    # 内閣府の祝日データを取り込み直す
npm run test:e2e    # ローカルの Worker を起動し、マーケット経由と同じ形で呼ぶ
npm run dev         # 手元で起動(秘密ヘッダーの確認なし)
npx @redocly/cli lint src/openapi.json   # 仕様書の検査
```

## 公開手順(RapidAPI の場合)

1. **Cloudflare**: 値下がり通知(`notify/README.md`)で登録したアカウントと GitHub の Secrets
   (`CLOUDFLARE_API_TOKEN`・`CLOUDFLARE_ACCOUNT_ID`)をそのまま使う。まだなら先にそちらの手順1〜5を行う
2. Actions →「calc-api」→「Run workflow」(main)。公開URLは `https://jp-listing-calc-api.<サブドメイン>.workers.dev`
   (この時点では秘密ヘッダー未設定なので、計算は 503 を返す)
3. **RapidAPI に登録**: https://rapidapi.com でアカウントを作り、Studio(プロバイダー画面)で出品ごとに「Add API Project」
   → その出品の仕様書(`/openapi.json?product=takehome` 等を保存したもの)をアップロード → Base URL に手順2の URL を設定。
   まずは1つ(例: takehome)から始め、慣れたら残りを足すとよい
4. **秘密ヘッダー**: 出品ごとに「Gateway」(または「Security」)タブに表示される `X-RapidAPI-Proxy-Secret` の値を控え、
   GitHub の Secrets に `MARKETPLACE_SECRETS` = `x-rapidapi-proxy-secret:<控えた値>@takehome`(出品が複数ならカンマ区切りで追加)
   で登録 → もう一度「Run workflow」
5. **掲載情報**: `listing/marketplace.md` の出品ごとの名前・説明・カテゴリ・タグ・ロゴ(`listing/logo.png`)を貼る
6. **料金プラン**: 「Monetize」タブで `listing/marketplace.md` の料金案を設定し、売上の受け取り方法を登録する
7. RapidAPI の画面の「Test Endpoint」で呼んで結果が返ることを確かめ、公開(Public)にする

他のマーケット(APILayer・Zyla 等)にも出す場合は、そのマーケットの秘密ヘッダーを
`MARKETPLACE_SECRETS` にカンマ区切りで足す(例: `x-rapidapi-proxy-secret:abc,x-zyla-secret:def`)。
ヘッダー名はマーケットごとに違うので、各マーケットの説明に従う。

## 今後

- まとめて計算するエンドポイント(1回で最大100件)。大量に使う利用者向け
- 実績(利用者数・呼び出し回数)ができたら、企業への直接販売(個別契約・API キーを自前で発行)に広げる。
  その時は値下がり通知で作った Stripe 連携とキーの仕組みを流用できる
