# 日本の計算関数(Google スプレッドシート アドオン)

セルに `=JP_TAKEHOME(300000)` のように書くだけで、日本特有の計算ができる関数を17個追加するアドオン。
計算の本体は計算API(`calc-api/`)と同じコードで、結果も API と同じになる。計算はすべて
Apps Script の中で行い、外部とは通信しない(入力した値を送らない・API の回数制限もない)。

方針: まず**無料で公開**して利用者と評価を集め(実績作り)、大量に使う人・システムに組み込みたい人を
計算API(API マーケット)へ案内する。有料版は実績ができてから(通知サービスの Stripe 連携を流用できる)。

## 関数

| 分類 | 関数 | 内容 |
|---|---|---|
| 手取り | `JP_TAKEHOME(月給, 賞与, 年齢, 都道府県)` | 1年間の手取り(2026年度の率) |
| | `JP_TAKEHOME_DETAIL(…)` | 内訳の表(健康保険・介護・子ども・子育て支援金・厚生年金・雇用保険・所得税・住民税) |
| 求人の給与 | `JP_ANNUAL_INCOME(給与の文章, 勤務時間の文章, "min"/"max")` | 年収の目安 |
| | `JP_HOURLY_EQUIVALENT(給与の文章, 勤務時間の文章)` | 時給換算 |
| | `JP_FIXED_OVERTIME(給与の文章)` | 固定残業代 |
| 金額・物件 | `JP_YEN("1億2000万円")` | 日本語の金額 → 数値 |
| | `JP_AREA_M2("10坪")` | 面積 → ㎡ |
| | `JP_TSUBO_PRICE(価格, 面積)` | 坪単価 |
| | `JP_LOAN_PAYMENT(借入額, 年利%, 年数)` | ローンの毎月の返済額 |
| 和暦 | `JP_WAREKI(日付, "long"/"short")` / `JP_FROM_WAREKI("R6.4.1")` | 西暦 ⇔ 和暦 |
| 祝日・営業日 | `JP_IS_HOLIDAY` / `JP_HOLIDAY_NAME` / `JP_HOLIDAYS(年)` | 祝日(内閣府の公式データ) |
| | `JP_WORKDAY(日付, 日数, 年末年始休み, 休業日の範囲)` | 日本版 WORKDAY |
| | `JP_NETWORKDAYS(開始日, 終了日, 年末年始休み, 休業日の範囲)` | 日本版 NETWORKDAYS |
| | `JP_IS_BUSINESS_DAY(日付, 年末年始休み, 休業日の範囲)` | 営業日か |

1つ目の引数に範囲(`A2:A100`)を渡すと、行ごとにまとめて計算する(1セルずつ書くより速い)。

## 仕組み

```
calc-api/src/*.js ・ job-extension/src/parser.js ・ realty-extension/src/parser.js
        │ scripts/build.mjs(esbuild で1ファイルにまとめ、Apps Script で動く書き方に変換)
        ▼
dist/lib.js(グローバル JPCalc) + dist/functions.js(関数) + dist/Code.js(メニュー) + Help.html + appsscript.json
        │ clasp push、または Apps Script のエディタに貼り付け
        ▼
Apps Script プロジェクト → エディタのアドオンとして Google Workspace Marketplace に公開
```

- 計算API の率(`calc-api/src/takehome.js`)や祝日(`calc-api/src/holidays.json`)を更新したら、
  `npm run build` してアドオンにも送り直す(毎年の更新は `calc-api/README.md` の「毎年の更新」)
- 権限は「このスプレッドシートだけ」と「サイドバーの表示」の2つだけ(審査が軽い権限)

## 開発

```bash
cd sheets-addon
npm ci
npm test         # dist/ を作り、Apps Script と同じ形(日付・範囲・空のセル)で17関数を試す
npm run build    # dist/ を作るだけ
```

## 公開手順

### 1. 自分のスプレッドシートで試す(15分)

1. https://script.google.com →「新しいプロジェクト」。名前を「日本の計算関数」にする
2. コードを入れる(どちらか):
   - **貼り付け**: `dist/` の4ファイル(`lib.js`・`functions.js`・`Code.js`・`Help.html`)を、同じ名前で
     エディタに作って中身を貼る。`appsscript.json` は「プロジェクトの設定」→「appsscript.json をエディタで表示」をオンにして貼る。
     (dist のファイルは Claude Code に「アドオンのファイルを送って」と頼めば添付される)
   - **clasp**(パソコンに Node.js がある場合): `npx @google/clasp login` → `.clasp.json.example` を
     `.clasp.json` にコピーしてスクリプトIDを入れる → `npm run push`
3. 「デプロイ」→「デプロイをテスト」→ 種類「エディタのアドオン」→ テスト用のスプレッドシートを選んで実行
4. シートで `=JP_TAKEHOME(300000)` → 2,876,160 になることを確認。スクリーンショット(1280x800)を2〜3枚撮っておく

### 2. Google Workspace Marketplace に出す(審査に数日〜数週間)

1. **Google Cloud のプロジェクト**: https://console.cloud.google.com で新しいプロジェクトを作り、プロジェクト番号を控える。
   Apps Script の「プロジェクトの設定」→「Google Cloud Platform(GCP)プロジェクト」でその番号に変更
2. **OAuth 同意画面**(Cloud Console →「API とサービス」→「OAuth 同意画面」): 種類「外部」、アプリ名「日本の計算関数」、
   サポートメール、プライバシーポリシー `https://pokeca-kaigai.com/sheets-addon-privacy.html`、
   利用規約 `https://pokeca-kaigai.com/sheets-addon-terms.html`、承認済みドメイン `pokeca-kaigai.com`、
   スコープは `spreadsheets.currentonly` と `script.container.ui`。
   ※ ドメインの所有確認(Google Search Console)が求められたら、確認用の HTML ファイル名を Claude Code に貼れば
   `toreca/public/` に置いて公開する
3. Apps Script で「デプロイ」→「新しいデプロイ」→ 種類「アドオン」→ デプロイ。バージョン番号を控える
4. Cloud Console で「Google Workspace Marketplace SDK」を有効化 →「アプリの構成」:
   公開範囲「一般公開」、インストール「個人とドメインの両方」、アプリの統合「Google Workspace アドオン」ではなく
   **「エディタのアドオン」→ スプレッドシート**、スクリプトID とデプロイのバージョン、OAuth スコープ(上と同じ2つ)
5. 「ストアの掲載情報」: `listing/store.md` の内容と、`listing/` のアイコン(32・128)・バナー(220x140)・
   手順1で撮ったスクリーンショットを入れて「公開」→ 審査
