# API マーケット掲載情報(RapidAPI 向け・他のマーケットでも流用可)

同じ Worker を、テーマごとに **5つの出品** として掲載する(検索で見つかりやすく、値段も別々に決められる)。
マーケットの利用者は海外の開発者が中心なので、掲載文は英語。各項目の下に日本語訳を付けている。

| 出品(product) | API 名 | 仕様書(登録時にアップロード) |
|---|---|---|
| `salary` | Japan Job Listing Salary Parser | `/openapi.json?product=salary` |
| `realty` | Japan Real Estate Listing Calculator | `/openapi.json?product=realty` |
| `takehome` | Japan Take-Home Pay Calculator | `/openapi.json?product=takehome` |
| `calendar` | Japan Holidays, Business Days & Wareki API | `/openapi.json?product=calendar` |
| `invoice` | Japan Invoice Payment Date & Withholding Tax API | `/openapi.json?product=invoice` |

仕様書は公開後 `https://jp-listing-calc-api.<サブドメイン>.workers.dev/openapi.json?product=…` から保存してアップロードする
(公開前なら `npm run dev` で起動して http://localhost:8787/openapi.json?product=… から保存)。

**出品ごとに秘密の値が発行される**ので、GitHub の Secrets の `MARKETPLACE_SECRETS` には出品ごとに書く:

```
x-rapidapi-proxy-secret:<salaryの値>@salary,x-rapidapi-proxy-secret:<realtyの値>@realty,x-rapidapi-proxy-secret:<takehomeの値>@takehome,x-rapidapi-proxy-secret:<calendarの値>@calendar,x-rapidapi-proxy-secret:<invoiceの値>@invoice
```

共通: ロゴ `calc-api/listing/logo.png`、Base URL `https://jp-listing-calc-api.<サブドメイン>.workers.dev`

---

## 1. Japan Job Listing Salary Parser(salary)

- **カテゴリ** → `Data`(無ければ `Business`)
- **タグ** → `japan`, `salary`, `job listing`, `recruiting`, `hr`, `parser`, `japanese`

**短い説明**

```
Parse the salary text of Japanese job listings into estimated annual income, monthly range, hourly equivalent and fixed overtime pay.
```

> 訳: 日本の求人の給与欄を、年収の目安・月給の幅・時給換算・固定残業代に変換します。

**長い説明**

```
Japanese job listings write pay in many ways — 「月給25万円～＋賞与年2回（4.5ヶ月分）」, 「年俸600万円～」, 「時給1,500円」, 「固定残業代40時間分・5万円を含む」. Send the text as written and get clean numbers in JSON:
- Estimated annual income (monthly x (12 + bonus months), or the stated annual salary)
- Monthly pay range (daily and hourly wages converted to monthly)
- Hourly equivalent from the stated working hours and annual holidays
- Fixed overtime pay (hours, amount) and pay after removing it
- Annual income written in the listing (想定年収 / 年収例), separated from the company-wide average (平均年収)
- Every assumption is returned in English and Japanese
Handles full-width digits, 万 notation, ranges and spelling variants. No data is stored.
```

## 2. Japan Real Estate Listing Calculator(realty)

- **カテゴリ** → `Data`(無ければ `Finance`)
- **タグ** → `japan`, `real estate`, `rent`, `property`, `yield`, `mortgage`, `tsubo`

**短い説明**

```
Turn Japanese property listing values (12.5万円, 25.3m², 敷金/礼金 1ヶ月/なし) into price per m²/tsubo, monthly cost, move-in cost, loan payment and yield.
```

> 訳: 日本の物件ページの値を、㎡/坪単価・月額・初期費用・ローン返済・利回りに変換します。

**長い説明**

```
Send rent or price, area and fees exactly as written on Japanese property pages (strings) or as numbers:
- Rentals: effective monthly cost (rent + management fee), rent per m² and per tsubo, minimum move-in cost estimate (deposit, key money, brokerage fee, advance rent)
- Sales: price per m² and per tsubo, monthly loan payment with your rate and term, plus management fee and repair reserve
- Investment: gross yield <-> annual income, simple net yield after management fee and repair reserve
Handles 万/億 notation, m²/㎡/坪, 「ヶ月」「なし」「-」. No data is stored.
```

## 3. Japan Take-Home Pay Calculator(takehome)

- **カテゴリ** → `Finance`
- **タグ** → `japan`, `payroll`, `take-home pay`, `income tax`, `social insurance`, `salary`, `hr`

**短い説明**

```
Japanese take-home pay from monthly salary and bonus: health insurance by prefecture, pension, employment insurance, income tax and resident tax — FY2026 official rates.
```

> 訳: 月給と賞与から日本の手取りを計算。都道府県別の健康保険、年金、雇用保険、所得税、住民税。2026年度の公式の率。

**長い説明**

```
Calculate Japanese take-home pay for company employees (Kyokai Kenpo health insurance):
- Health insurance with the official FY2026 rate of each of the 47 prefectures, nursing care insurance (age 40-64), the new child support levy (0.23%), employees' pension (18.3%) and employment insurance (0.5%)
- Standard monthly remuneration grades, pension cap, bonus caps and the official rounding rule
- Income tax with the 2026 tax reform (basic deduction up to ¥1.04M, minimum employment income deduction ¥740k) and the 2.1% reconstruction surtax
- Estimated resident tax
Returns each deduction, annual and monthly take-home pay, and the rates used. Assumes a single employee with no dependents; assumptions are listed in the response. Rates are updated every fiscal year.
```

## 4. Japan Holidays, Business Days & Wareki API(calendar)

- **カテゴリ** → `Data`(無ければ `Tools`)
- **タグ** → `japan`, `holidays`, `business days`, `calendar`, `wareki`, `japanese era`, `date`

**短い説明**

```
Japanese national holidays (official data since 1955), business day add/count with year-end closure, and Western <-> Japanese era (令和/平成) date conversion.
```

> 訳: 日本の祝日(1955年からの公式データ)、年末年始休みにも対応した営業日の加算・日数、西暦⇔和暦の変換。

**長い説明**

```
- Holidays: official Cabinet Office holiday data from 1955, including substitute holidays and citizens' holidays (e.g. 2026-09-22)
- Check a date: holiday name, weekday, business day or not, and the wareki date
- Add or subtract business days, or count business days between two dates — optionally closing Dec 29 - Jan 3, custom closed days and custom weekend days
- Wareki conversion both ways: 「令和6年4月1日」「R6.4.1」「平成元年」「H31/4/30」, full-width digits, and dates written in an era that had already ended (平成31年5月1日 -> 令和元年)
```

## 5. Japan Invoice Payment Date & Withholding Tax API(invoice)

- **カテゴリ** → `Finance`(無ければ `Business`)
- **タグ** → `japan`, `invoice`, `accounting`, `payment terms`, `withholding tax`, `business days`, `bookkeeping`

**短い説明**

```
Japanese accounting helpers: payment date from payment terms like 末締め翌月25日払い (skipping holidays), and withholding tax on fees (源泉徴収) with net payment.
```

> 訳: 日本の経理の部品。「末締め翌月25日払い」のような支払条件から休日を避けた支払日を、報酬の源泉徴収税額と差引の支払額を計算。

**長い説明**

```
- Payment date: send the transaction date and the payment terms as written in Japanese (末締め翌月25日払い, 20日締め翌々月末日支払, 休日の場合は翌営業日) or as fields (closing day, months after, payment day). Get the closing date, the scheduled date and the actual payment date moved to the previous or next business day using official Japanese holidays, with optional year-end closure and custom closed days
- Withholding tax on fees paid to individuals (writing, lectures, design, etc.): 10.21% up to ¥1,000,000 and 20.42% above, including the special reconstruction income tax, with consumption tax, invoice total and net payment. Handles tax-inclusive amounts where consumption tax is not stated separately
- Registration number check: validate invoice registration numbers (T + 13 digits) and corporate numbers (法人番号) offline by their check digit, normalize full-width / hyphenated input, and get the National Tax Agency page to confirm the registration
- Every assumption is returned in English and Japanese. No data is stored
```

---

## 料金プラン(案・出品ごと)

| プラン | salary / realty / takehome | calendar・invoice(軽い処理なので安め) |
|---|---|---|
| BASIC(無料) | 100回/月 | 500回/月 |
| PRO | $9.99・1万回/月 | $4.99・2万回/月 |
| ULTRA | $29.99・10万回/月 | $14.99・20万回/月 |
| MEGA | $99.99・100万回/月 | $49.99・200万回/月 |

- 無料枠は上限で止める(hard limit)。有料プランの超過は1回 $0.0002〜0.0005 程度
- Cloudflare の費用はほぼ0円(無料枠: 1日10万回)

## 利用規約に入れる内容(マーケットの規約に追加できる場合)

```
Results are estimates computed from your input and are provided "as is" without warranty. They are not tax, legal, financial or real estate advice. Do not use them as the sole basis for payroll, employment, financial or real estate decisions. We do not store request data.
```

> 訳: 結果は入力から計算した概算で無保証。税務・法律・金融・不動産の助言ではない。給与計算・雇用・金融・不動産の判断の唯一の根拠にしないこと。リクエストの内容は保存しない。
