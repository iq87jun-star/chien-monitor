# Cowork 用の作業指示(Excel アドイン「日本の計算関数」を試す・AppSource 申請の準備)

この文書を Cowork にそのまま渡して使う。人が行う作業(★)と、Cowork に任せる作業を分けてある。
Cowork は「止まる」と書かれた所で必ず作業を止め、人に確認すること。

| 作業 | 内容 | 必要な時間 |
|---|---|---|
| A | Excel on the web にアドインを読み込む | 5分 |
| B | 19の関数を試して、正解の値と比べる | 15分 |
| C | ストア用のスクリーンショットを撮る | 5分 |
| D(後日) | Partner Center(AppSource)への申請の準備 | 30分〜 |

## 守ること(Cowork 向け)

- Microsoft アカウントのパスワード・2段階認証コードを入力しない(ログインは人が行う)
- **審査への提出・公開のボタンは押さない**。規約への同意・支払い情報・本人確認の画面が出たら止まって人に知らせる
- 試すのは新しく作ったブックだけ。人の既存のファイルは開かない・変更しない
- アドインの定義ファイル(`manifest.xml`)は下の URL から取ったものを**そのまま**使う。自分で書き換えない

## 事前準備(★人が行う)

1. `excel-addin/` を含む PR が `main` にマージされ、配信済みであること(マージで `toreca-auto-update` が自動で走る)
   (https://pokeca-kaigai.com/excel-addin/help.html が開けば OK)
2. Chrome で https://www.office.com に Microsoft アカウントでログインしておく(無料のアカウントでよい)
3. Cowork に「https://github.com/iq87jun-star/chien-monitor/blob/main/excel-addin/cowork-guide.md の作業を
   A〜C までして」と伝える

## 作業A: Excel on the web にアドインを読み込む(Cowork)

1. https://pokeca-kaigai.com/excel-addin/manifest.xml を開き、「名前を付けて保存」で `manifest.xml` として保存する
2. https://www.office.com → Excel →「空白のブック」。ブックの名前を「日本の計算関数 テスト」にする
3. 「ホーム」→「アドイン」→「その他のアドイン」(または「挿入」→「アドイン」→「Office アドイン」)を開く
4. 「個人用アドイン」→「マイ アドインのアップロード」→ 手順1の `manifest.xml` を選んで「アップロード」。
   **ファイルを選ぶ画面を操作できない場合は止まり**、人に選んでもらう
5. エラーが出たら**止まる**: エラーの文言をそのまま人に報告する

## 作業B: 19の関数を試す(Cowork)

A 列に下の「入力する式」を1行に1つずつ入れ、B 列に「正解」を書き写す。表示された値が正解と一致するか確かめる。
初回は読み込みに数秒かかることがある(`#BUSY!` の表示は待つ)。
日付を返す式(13・17・18・23・24)は数値(シリアル値)で出るので、そのセルの表示形式を「日付」にしてから比べる。

| # | 入力する式 | 正解 |
|---|---|---|
| 1 | `=JP.TAKEHOME(300000)` | 2876160 |
| 2 | `=JP.TAKEHOME(400000, 1000000, 45, "大阪府")` | 4459312 |
| 3 | `=JP.TAKEHOME_DETAIL(300000)`(下に11行・右に2列の表が出る) | 1行目「額面(年) 3600000」… 最後の2行「手取り(年) 2876160」「手取り(月平均) 239680」 |
| 4 | `=JP.ANNUAL_INCOME("月給25万円～＋賞与年2回（計4.5ヵ月分）")` | 4125000 |
| 5 | `=JP.HOURLY_EQUIVALENT("月給30万円", "実働8時間 年間休日125日")` | 1875 |
| 6 | `=JP.FIXED_OVERTIME("月給30万円（固定残業代40時間分・5万円を含む）")` | 50000 |
| 7 | `=JP.YEN("1億2000万円")` | 120000000 |
| 8 | `=JP.AREA_M2("10坪")` | 33.06 |
| 9 | `=JP.TSUBO_PRICE("4,980万円", "70.12㎡")` | 2347805 |
| 10 | `=JP.LOAN_PAYMENT("3000万円")` | 84686 |
| 11 | `=JP.WAREKI(DATE(2026,9,24))` | 令和8年9月24日 |
| 12 | `=JP.WAREKI(DATE(2026,9,24), "short")` | R8.9.24 |
| 13 | `=JP.FROM_WAREKI("R6.4.1")` | 45383(日付の表示で 2024/4/1) |
| 14 | `=JP.IS_HOLIDAY(DATE(2026,9,22))` | TRUE |
| 15 | `=JP.HOLIDAY_NAME(DATE(2026,9,21))` | 敬老の日 |
| 16 | `=JP.IS_BUSINESS_DAY(DATE(2026,9,24))` | TRUE |
| 17 | `=JP.WORKDAY(DATE(2026,9,18), 1)` | 2026/9/24 |
| 18 | `=JP.WORKDAY(DATE(2026,12,28), 1, TRUE)` | 2027/1/4 |
| 19 | `=JP.NETWORKDAYS(DATE(2026,9,1), DATE(2026,9,30))` | 19 |
| 20 | `=ROWS(JP.HOLIDAYS(2026))` | 18 |
| 21 | 別の列に 200000 / 300000 / 400000 を縦に3つ入れ、`=JP.TAKEHOME(その3セルの範囲)` | 3つまとめて計算される(2つ目が 2876160) |
| 22 | `=JP.YEN("未定")` | `#VALUE!`(セルを選ぶと「金額として読めません」の説明が出る) |
| 23 | `=JP.PAYMENT_DATE(DATE(2026,9,15), "末締め翌月25日払い")` | 2026/10/23(10/25 が日曜なので前営業日) |
| 24 | `=JP.PAYMENT_DATE(DATE(2026,9,15), "末締め翌月25日払い", "翌")` | 2026/10/26 |
| 25 | `=JP.WITHHOLDING(100000)` | 10210 |
| 26 | `=JP.WITHHOLDING(1500000)` | 204200 |

さらに次を確かめる。

- セルに `=JP.` と打った時、関数の候補と日本語の説明が出るか
- 「ホーム」→「アドイン」に「日本の計算関数」があり、押すと右に使い方の画面(関数の一覧)が出るか

**報告**: 次の表を、Issue の「報告の表」に書く(一致しないものは、表示された値やエラーの文言をそのまま書く)。

| # | 表示された値 | 正解と一致? | エラーの文言(あれば) |
|---|---|---|---|

## 作業C: ストア用のスクリーンショットを撮る(Cowork)

作業Bで**すべて一致した場合だけ**行う。ブラウザの窓を 1366x768 にして、次の3枚を撮って保存する。
画面に個人の情報(他のファイル名・メールアドレス・アカウントの名前等)が写らないようにする。

1. 手取りの内訳: A1 に「月給」、B1 に 300000、A3 に `=JP.TAKEHOME_DETAIL(B1)` を入れた画面
2. 営業日: 日付の列と `=JP.WORKDAY(…, 3)`(表示形式は日付)・`=JP.HOLIDAY_NAME(…)` の列が並んだ画面(9月の連休をまたぐ日付を数行)
3. 和暦: 西暦の日付の列と `=JP.WAREKI(…)` の列が並んだ画面

保存したファイルの場所を人に報告する。

## 作業D(後日): Partner Center への申請の準備(Cowork・★の所は人)

作業A〜Cが問題なく終わってから行う。細かい手順は `excel-addin/README.md` の「3. Microsoft AppSource に出す」。

1. ★ https://partner.microsoft.com で「Microsoft AI Cloud Partner Program」に登録する(規約への同意・本人確認は人)。
   発行者の表示名は `JP Calc Tools`
2. Cowork: 「Marketplace offers」→「Microsoft 365 and Copilot」→「+ New offer」→「Office add-in」。
   オファー名は「日本の計算関数」
3. Cowork: 「Packages」に `manifest.xml`(作業Aで保存したもの)をアップロードする
4. Cowork: 「Properties」「Offer listing」「Availability」を `excel-addin/listing/store.md` のとおりに入力する。
   アイコンは `excel-addin/listing/icon-300.png`(「Code」→「Download ZIP」で取る)、スクリーンショットは作業Cで撮ったもの
5. Cowork: 「Notes for certification」に `listing/store.md` の「審査担当者へのメモ」を貼る
6. **止まる**: 「Review and publish」は押さずに、入力した内容と警告を人に報告する

## 報告(Cowork)

作業が終わった時・止まった時は、人に知らせるのに加えて、[cowork/README.md](../cowork/README.md) の
「報告の出し方」のとおり GitHub の Issue(「Cowork の作業報告」)に結果と報告の表を書き、Issue の番号を人に伝える。

## 最終確認(★人が行う)

作業Bの報告で一致しないものがあれば、Claude Code に「Issue #番号 に報告を出しました」と伝えて修正を依頼する。
作業Dの報告を確認し、問題がなければ Partner Center で「Review and publish」を押して審査に出す(数日〜2週間ほど)。
