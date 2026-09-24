# Google Workspace Marketplace 掲載情報

利用者は日本の事務・人事・経理・不動産の担当者が中心なので、日本語を主にする(英語の欄があれば下の英語版)。

- **アプリ名** → `日本の計算関数(手取り・祝日・和暦)`
- **カテゴリ** → `ビジネスツール`(無ければ `仕事効率化`)
- **言語** → 日本語
- **アイコン** → `listing/icon32.png`・`listing/icon128.png`
- **カードのバナー** → `listing/banner-220x140.png`
- **スクリーンショット** → テスト用のシートで撮ったもの(1280x800)。手取りの内訳の表、営業日の計算、和暦の変換の3枚がおすすめ
- **プライバシーポリシー** → https://pokeca-kaigai.com/sheets-addon-privacy.html
- **利用規約** → https://pokeca-kaigai.com/sheets-addon-terms.html
- **サポート** → ご自身の連絡用メールアドレス(公開される)
- **料金** → 無料

## 短い説明

```
手取り・年収・坪単価・和暦・日本の祝日と営業日を、セルに関数を書くだけで計算できます。
```

## 詳しい説明

```
Google スプレッドシートに、日本特有の計算をする関数を17個追加します。セルに関数を書くだけで使え、範囲を渡せばまとめて計算します。

■ 手取り(2026年度の率)
=JP_TAKEHOME(月給, 賞与, 年齢, 都道府県) で1年間の手取り、=JP_TAKEHOME_DETAIL(…) で健康保険・介護保険・子ども・子育て支援金・厚生年金・雇用保険・所得税・住民税の内訳を表示。協会けんぽの都道府県別の保険料率と、2026年の税制改正(基礎控除・給与所得控除の引き上げ)に対応。

■ 祝日・営業日
内閣府の公式データ(振替休日・国民の休日を含む)で、祝日の判定・祝日名・年間の祝日一覧。日本の祝日に対応した WORKDAY・NETWORKDAYS(年末年始休みや独自の休業日も指定可)。

■ 和暦
=JP_WAREKI(日付) で「令和8年9月24日」、=JP_FROM_WAREKI("R6.4.1") で日付に。平成元年・全角数字にも対応。

■ 求人・物件
求人の給与欄の文章から年収の目安・時給換算・固定残業代。「1億2000万円」「10坪」のような書き方を数値に、坪単価・住宅ローンの返済額。

■ プライバシー
計算はすべてスプレッドシートの中(Apps Script)で行い、入力した値を外部に送りません。

■ ご注意
結果は概算で、税務・法律の助言ではありません。手取りは会社員(協会けんぽ)・独身で扶養なしとして計算します。
```

## 英語版(英語の欄がある場合)

```
Adds 17 Japan-specific functions to Google Sheets: take-home pay with FY2026 social insurance and tax rates, Japanese national holidays and business days (WORKDAY / NETWORKDAYS for Japan), Western <-> Japanese era (wareki) dates, annual income from Japanese job listing text, and real estate helpers (tsubo price, loan payment, 1億2000万円 -> 120000000). All calculations run inside Apps Script; no data leaves your spreadsheet.
```
