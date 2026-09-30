# 日本の計算関数(Excel アドイン)

Excel のセルに `=JP.TAKEHOME(300000)` のように書くだけで、日本特有の計算ができる関数を21個追加するアドイン。
スプレッドシート版(`sheets-addon/`)の Excel 版で、計算の本体は計算API(`calc-api/`)と同じコード(結果も同じ)。
計算はすべて Excel の中で行い、入力した値を外部に送らない。

方針はスプレッドシート版と同じで、まず**無料で公開**して利用者と評価を集め、
大量に使う人・システムに組み込みたい人を計算API へ案内する。有料版は実績ができてから(ライセンスキーを売り場の間で共通にする。
[部品工場の手順書](../parts-factory/README.md))。

## 関数

名前はスプレッドシート版の `JP_XXX` に対して `JP.XXX`(Excel では `JP.` が付く)。

| 分類 | 関数 |
|---|---|
| 手取り(2026年度の率) | `JP.TAKEHOME(月給, 賞与, 年齢, 都道府県)` / `JP.TAKEHOME_DETAIL(…)`(内訳の表) |
| 求人の給与 | `JP.ANNUAL_INCOME(給与の文章, 勤務時間の文章, "min"/"max")` / `JP.HOURLY_EQUIVALENT` / `JP.FIXED_OVERTIME` |
| 金額・物件 | `JP.YEN("1億2000万円")` / `JP.AREA_M2("10坪")` / `JP.TSUBO_PRICE(価格, 面積)` / `JP.LOAN_PAYMENT(借入額, 年利%, 年数)` |
| 和暦 | `JP.WAREKI(日付, "long"/"short")` / `JP.FROM_WAREKI("R6.4.1")` |
| 祝日・営業日 | `JP.IS_HOLIDAY` / `JP.HOLIDAY_NAME` / `JP.HOLIDAYS(年)` / `JP.WORKDAY` / `JP.NETWORKDAYS` / `JP.IS_BUSINESS_DAY` |
| 請求・支払 | `JP.PAYMENT_DATE(取引日, "末締め翌月25日払い", "前"/"翌"/"なし", 休業日)` / `JP.WITHHOLDING(報酬の額, 税込か)`(源泉徴収税額) / `JP.IS_VALID_REGNO(番号)`・`JP.REGNO(番号)`(登録番号の検査・整形) |

- 「範囲も可」の引数に範囲(`A2:A100`)を渡すと、行ごとにまとめて計算して同じ形で返す(スピル)
- 日付を返す関数はシリアル値を返す(Excel 標準の `WORKDAY` と同じ。セルの表示形式を「日付」にする)
- 読めない値は理由つきの `#VALUE!` になる

## 仕組み

```
src/functions.js(関数の本体と説明。calc-api/src と拡張の parser.js を import)
        │ scripts/build.mjs(esbuild で1ファイルにまとめる + 説明から functions.json と使い方の画面を作る)
        ▼
dist/functions.js ・ functions.json ・ functions.html ・ help.html ・ manifest.xml ・ assets/
        │ toreca-auto-update.yml が toreca のサイトと一緒に配信(1日2回・手動でも実行可)
        ▼
https://pokeca-kaigai.com/excel-addin/  ←── Excel が manifest.xml に書かれた URL から読み込む
```

- **関数を足す・直す時は `src/functions.js` だけ**を書き換える。Excel に出る説明・使い方の画面は自動で作られる
- **関数の名前(id)は公開後に変えない**。変えると、その関数を使っているブックが `#NAME?` になる
- **`manifest.xml` の Id は変えない**(変えると別のアドインになる)。更新を出す時は `package.json` の `version` を上げる
  (定義の Version はそこから作られる)。関数の中身だけの修正なら、配信するだけで利用者に届く(再提出は不要)
- 計算API の率・祝日を更新したら、このアドインも自動で新しい値になる(配信は次の toreca の自動更新で行われる)
- 配信は toreca のサイトのデプロイに含まれている。**toreca のデプロイから外すと、アドインを入れた人の関数が全部動かなくなる**
- アイコンは `listing/`(`scripts/icons.mjs` で作ったもの。デザインを変える時だけ作り直す)

## 開発

```bash
cd excel-addin
npm ci
npm test         # dist/ を作り、Excel と同じ形(範囲の2次元配列・シリアル値・省略は null)で21関数を試す
npm run build    # dist/ を作るだけ(配信先を変える時は EXCEL_ADDIN_BASE_URL=https://…/ を付ける)
```

定義ファイルの検査(Microsoft の審査と同じ検査。インターネットが必要):

```bash
npx --yes office-addin-manifest validate dist/manifest.xml   # 「The manifest is valid.」が出れば OK
```

## 公開手順

### 1. 配信する(5分)

1. このフォルダを含む PR を `main` にマージする
2. 待つだけ(マージすると `toreca-auto-update` が自動で走って配信する。急ぐ時は Actions →「toreca-auto-update」→「Run workflow」)
3. ブラウザで https://pokeca-kaigai.com/excel-addin/help.html が開けば配信できている

### 2. 自分の Excel で試す(15分)

手順2・3は Cowork に任せられる([cowork-guide.md](cowork-guide.md)。正解の値の表もそこにある)。

**Excel on the web**(無料の Microsoft アカウントで使える。いちばん簡単):

1. https://www.office.com → Excel →「空白のブック」
2. 「ホーム」→「アドイン」→「その他のアドイン」→「個人用アドイン」→「マイ アドインのアップロード」
3. `manifest.xml` を選ぶ(https://pokeca-kaigai.com/excel-addin/manifest.xml を保存したもの。
   または Claude Code に「Excel アドインの manifest.xml を送って」と頼めば添付される)
4. セルに `=JP.TAKEHOME(300000)` → **2876160** になることを確認。
   `=JP.HOLIDAYS(2026)` で祝日の表が出ることも確認
5. 掲載用のスクリーンショット(1366x768)を3枚撮る。手取りの内訳(`=JP.TAKEHOME_DETAIL(300000)`)、
   営業日の計算(`=JP.WORKDAY`)、和暦の変換(`=JP.WAREKI`)がおすすめ

Windows の Excel で試す場合は、共有フォルダに `manifest.xml` を置いて「信頼できるアドイン カタログ」に登録する方法になる
(手間が多いので、web で確認できれば十分)。

### 3. Microsoft AppSource に出す(審査に数日〜2週間ほど)

1. **Partner Center のアカウント**(無料): https://partner.microsoft.com → 「Microsoft AI Cloud Partner Program」に登録。
   個人でも登録できる。発行者の表示名は **`JP Calc Tools`**(定義の ProviderName と同じにする。
   変える場合は `scripts/build.mjs` の `PROVIDER` も同じ名前に直す)
2. Partner Center →「Marketplace offers」→「Microsoft 365 and Copilot」→「+ New offer」→「Office add-in」
3. **Packages**: `manifest.xml` をアップロード
4. **Properties**: カテゴリ・利用規約 URL(`listing/store.md`)
5. **Offer listing**: `listing/store.md` の文章と、`listing/icon-300.png`、手順2で撮ったスクリーンショット
6. **Availability**: 無料・全地域
7. **Notes for certification**: `listing/store.md` の「審査担当者へのメモ」を貼る
8. 「Review and publish」→ 審査。指摘が来たら内容を Claude Code に貼れば直す

## 有料化(実績ができてから)

AppSource はアドインの課金を代行しないので、有料版は自前のライセンスで売る。
候補は「今ある21関数は無料のまま、これから足す手間のかかる経理の部品(全銀フォーマット等)を有料の関数にする」形。
ライセンスキーの確認は通知サービス(`notify/`)の Stripe 連携を流用し、スプレッドシート版・kintone 版と共通にする
([部品工場の手順書](../parts-factory/README.md))。
