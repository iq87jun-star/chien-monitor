# Microsoft AppSource 掲載情報

利用者は日本の事務・人事・経理・不動産の担当者が中心なので、日本語を主にする(英語の欄には下の英語版)。
関数の一覧・例は `src/functions.js` と揃える(関数を足したらここも直す)。

- **アドインの名前** → `日本の計算関数(手取り・祝日・和暦)`(定義の DisplayName と同じ)
- **カテゴリ** → `Productivity`(2つ目を選べれば `Finance`)
- **対応する製品** → Excel
- **言語** → 日本語(英語の説明も追加)
- **アイコン** → `listing/icon-300.png`
- **スクリーンショット** → 自分の Excel で撮ったもの(1366x768)。手取りの内訳、営業日の計算、和暦の変換の3枚
- **プライバシーポリシー** → https://pokeca-kaigai.com/excel-addin-privacy.html
- **利用規約(使用許諾)** → https://pokeca-kaigai.com/excel-addin-terms.html
- **サポート** → https://pokeca-kaigai.com/excel-addin/help.html
- **料金** → 無料

## 短い説明(100文字まで)

```
手取り・年収・坪単価・和暦・日本の祝日と営業日を、セルに関数を書くだけで計算。入力した値を外部に送りません。
```

## 詳しい説明

```
Excel に、日本特有の計算をする関数を21個追加します。セルに =JP. と入力すると一覧が出ます。範囲を渡せばまとめて計算します。

■ 手取り(2026年度の率)
=JP.TAKEHOME(月給, 賞与, 年齢, 都道府県) で1年間の手取り、=JP.TAKEHOME_DETAIL(…) で健康保険・介護保険・子ども・子育て支援金・厚生年金・雇用保険・所得税・住民税の内訳を表示。協会けんぽの都道府県別の保険料率と、2026年の税制改正(基礎控除・給与所得控除の引き上げ)に対応。

■ 祝日・営業日
内閣府の公式データ(振替休日・国民の休日を含む)で、祝日の判定・祝日名・年間の祝日一覧。日本の祝日に対応した JP.WORKDAY・JP.NETWORKDAYS(年末年始休みや独自の休業日も指定可)。

■ 和暦
=JP.WAREKI(日付) で「令和8年9月24日」、=JP.FROM_WAREKI("R6.4.1") で日付に。平成元年・全角数字にも対応。

■ 求人・物件
求人の給与欄の文章から年収の目安・時給換算・固定残業代。「1億2000万円」「10坪」のような書き方を数値に、坪単価・住宅ローンの返済額。

■ 請求・支払
=JP.PAYMENT_DATE(取引日, "末締め翌月25日払い") で、土日・祝日を避けた支払日(前営業日・翌営業日を選べる)。=JP.WITHHOLDING(報酬の額) で報酬・料金の源泉徴収税額(10.21%・100万円を超える部分は20.42%)。=JP.IS_VALID_REGNO(番号) でインボイスの登録番号・法人番号の打ち間違いを検査(外部と通信しません)、=JP.REGNO(番号) で「T + 13桁」の形に整えます。

■ プライバシー
計算はすべて Excel の中で行い、入力した値を外部に送りません。Cookie・広告・アクセス解析もありません。

※ 計算結果は公表されている率による概算です。税務・法律の助言ではありません。
```

## 英語版(English)

Short:

```
Japanese take-home pay, holidays, business days and Japanese era dates as simple Excel functions. No data leaves Excel.
```

Long:

```
Adds 21 Japan-specific functions to Excel. Type =JP. in a cell to see them; pass a range to calculate many rows at once.

- Take-home pay (FY2026 rates): =JP.TAKEHOME and a full breakdown with =JP.TAKEHOME_DETAIL (health insurance by prefecture, nursing care, child support levy, pension, employment insurance, income tax, resident tax).
- Holidays and business days: official Cabinet Office holiday data including substitute holidays; Japanese versions of WORKDAY and NETWORKDAYS with optional year-end closure and custom closed dates.
- Japanese era (wareki): =JP.WAREKI and =JP.FROM_WAREKI ("R6.4.1", "令和6年4月1日").
- Invoices: payment date from Japanese payment terms (=JP.PAYMENT_DATE(A2, "末締め翌月25日払い"), skipping weekends and holidays) withholding tax on fees (=JP.WITHHOLDING, 10.21% / 20.42%), and offline check-digit validation of invoice registration numbers (=JP.IS_VALID_REGNO("T7000012050002")).
- Job and real estate text: annual income, hourly equivalent and fixed overtime from Japanese salary text; "1億2000万円" / "10坪" to numbers, price per tsubo, monthly loan payment.

All calculations run inside Excel. No inputs are sent anywhere; no cookies, ads or analytics.
Results are estimates and not tax or legal advice.
```

## 審査担当者へのメモ(Notes for certification)

```
This add-in only provides custom functions (namespace JP). No sign-in or account is required.

How to test:
1. Enter =JP.TAKEHOME(300000) in any cell. Expected result: 2876160.
2. Enter =JP.TAKEHOME_DETAIL(300000). Expected: an 11-row x 2-column breakdown table (spills).
3. Enter =JP.HOLIDAYS(2026). Expected: 18 rows (serial dates and holiday names in Japanese). Format column A as Date to see dates.
4. Enter =JP.WAREKI(DATE(2026,9,24)). Expected: 令和8年9月24日
5. Enter =JP.WORKDAY(DATE(2026,9,18),1) and format as Date. Expected: 2026/9/24 (skips Japanese holidays 9/21-9/23).
6. Enter =JP.PAYMENT_DATE(DATE(2026,9,15),"末締め翌月25日払い") and format as Date. Expected: 2026/10/23 (10/25 is a Sunday, so the previous business day).
7. Enter =JP.WITHHOLDING(100000). Expected: 10210.
8. Enter =JP.IS_VALID_REGNO("T7000012050002"). Expected: TRUE. With "T8000012050002" (mistyped): FALSE.
9. Enter =JP.YEN("未定"). Expected: #VALUE! with the message "金額として読めません" (invalid amount).

The task pane (help.html) is a static help page listing all functions. All calculations are performed locally in the custom functions runtime; the add-in makes no network requests after loading.
```
