# API マーケット掲載情報(RapidAPI 向け・他のマーケットでも流用可)

マーケットの利用者は海外の開発者が中心なので、掲載文は英語。各項目の下に日本語訳を付けている。
「→」の右をマーケットの各欄に貼る。

## 基本情報

- **API 名** → `Japan Salary & Real Estate Calculator`
- **カテゴリ** → `Data`(候補が無ければ `Business` / `Finance`)
- **タグ** → `japan`, `salary`, `real estate`, `job listing`, `rent`, `property`, `yield`, `parser`, `japanese`
- **ロゴ** → `calc-api/listing/logo.png`(500x500)
- **仕様書(OpenAPI)** → `calc-api/src/openapi.json` をアップロード
  (公開後は `https://jp-listing-calc-api.<サブドメイン>.workers.dev/openapi.json` でも取れる)
- **Base URL** → `https://jp-listing-calc-api.<サブドメイン>.workers.dev`

## 短い説明(Short description)

```
Turn messy Japanese job and property listings into comparable numbers: annual salary, hourly pay, fixed overtime, price per m²/tsubo, monthly cost and yield.
```

> 訳: ばらばらな日本の求人・物件の記載を、比べられる数字(年収・時給・固定残業代・㎡/坪単価・月額・利回り)に変換します。

## 長い説明(Long description)

```
Japanese job and real estate listings write numbers in many different ways — 「月給25万円～＋賞与年2回（4.5ヶ月分）」, 「固定残業代40時間分を含む」, 「12.5万円」, 「1億2000万円」, 「25.3m²」, 「敷金/礼金 1ヶ月/なし」. This API reads the text exactly as written and returns clean, comparable numbers in JSON.

## Salary (/v1/salary/analyze)
Send the salary section of a Japanese job listing (and optionally the working hours / holidays section):
- Estimated annual income (monthly pay x 12 + bonus months, or the stated annual salary 年俸)
- Monthly pay range, with daily and hourly wages converted to monthly
- Hourly equivalent based on the stated working hours and annual holidays
- Fixed overtime pay (固定残業代 / みなし残業): hours, amount, and pay after removing it
- Annual income written in the listing (想定年収 / 年収例), distinguished from the company-wide average (平均年収)
- Every assumption (e.g. 8 hours/day when not stated) is returned in both English and Japanese

## Real estate (/v1/realty/analyze)
Send rent or price, area and fees as written on Japanese property pages (strings or numbers):
- Rentals: effective monthly cost (rent + management fee), rent per m² and per tsubo, minimum move-in cost estimate (deposit, key money, brokerage fee, advance rent)
- Sales: price per m² and per tsubo, monthly loan payment (custom rate and term) plus management fee and repair reserve
- Investment: gross yield ⇔ annual income, simple net yield after management fee and repair reserve

## Good for
- Job boards, recruiting and HR tools that aggregate Japanese listings
- Real estate portals, property comparison and investment analysis tools
- Scrapers and data pipelines that need normalized numbers from Japanese text

## Notes
- Handles full-width digits, 万/億 notation, ranges (～), 「ヶ月/ヵ月/カ月」 and common spelling variants.
- No data is stored. Results are estimates computed from the given text only.
- Currency is always JPY.
```

> 訳(要約): 日本の求人・物件の数字の書き方はばらばら。この API は記載をそのまま読み、比べられる数字を JSON で返す。
> 給与: 年収の目安、月給の幅(日給・時給は月額に換算)、時給換算、固定残業代とそれを除いた金額、記載の年収(会社平均と区別)、仮定の内容(英語・日本語)。
> 物件: 賃貸は実質月額・㎡/坪あたり・初期費用の目安、売買は単価・ローン返済+管理費等、投資は利回り⇔年間収入・簡易実質利回り。
> 向いている用途: 求人サイト・人事ツール、不動産ポータル・比較・投資分析、日本語の文章から数字が必要なスクレイパー。
> 注意: 全角数字・万/億・範囲・「ヶ月」の表記揺れに対応。データは保存しない。結果は概算。通貨は円。

## 料金プラン(案)

| プラン | 月額 | 回数/月 | 超過時 |
|---|---|---|---|
| BASIC | $0 | 100 | 止める(hard limit) |
| PRO | $9.99 | 10,000 | 止める |
| ULTRA | $29.99 | 100,000 | $0.0005/回 |
| MEGA | $99.99 | 1,000,000 | $0.0002/回 |

- 無料枠は試してもらうため。上限で止めて、想定外の請求が出ないようにする
- 1回あたりの Cloudflare の費用はほぼ0円(無料枠: 1日10万回。超えても100万回あたり数十円程度)
- 1秒あたりの回数制限(rate limit)は 10回/秒 程度をマーケット側で設定

## エンドポイントの説明(マーケットが OpenAPI から自動で作る。直す場合の文案)

- `POST /v1/salary/analyze` → `Analyze the salary text of a Japanese job listing. Returns estimated annual income, hourly equivalent and fixed overtime pay.`
- `POST /v1/realty/analyze` → `Analyze a Japanese property listing (rent or sale). Returns price per m²/tsubo, monthly cost, move-in cost estimate, loan payment and yield.`
- `GET /v1/health` → `Health check (no authentication).`

## 利用規約に入れる内容(マーケットの規約に追加できる場合)

```
Results are estimates computed from the text you send and are provided "as is" without warranty. Do not use them as the sole basis for employment, financial or real estate decisions. We do not store request data.
```

> 訳: 結果は送られた文章から計算した概算で、無保証。雇用・金融・不動産の判断の唯一の根拠にしないこと。リクエストの内容は保存しない。
