# Edge・Firefox 出品の入力項目(3つの拡張)

各ストアの画面の項目の順に並べています。「→」の右をそのまま入力・選択してください。
手順の全体は [edge-firefox.md](edge-firefox.md)。

**共通の注意**
- 説明文にサイト名を並べない(Chrome でキーワード スパムとして却下されたため。下の説明文は対策済み)
- 「連絡先メールアドレス」はご自身の連絡用のアドレスを入れてください(ストアのページで公開されます)
- 審査担当者向けの注記は英語にしてあります(審査は英語で行われることが多いため。公開はされません)
- アイコンは各拡張の `icons/icon128.png`、スクリーンショットは `store/screenshots/` の画像(どれも 1280x800)

---

## トレカ海外相場チェッカー(ポケカ・遊戯王・ワンピース)(v0.3.1)

### Microsoft Edge アドオン(パートナーセンター)

| 画面・項目 | 入力・選択 |
|---|---|
| パッケージ | `pokeca-kaigai-checker-0.3.1.zip`(Chrome と同じzip) |
| 可用性 → 表示 | パブリック(Public) |
| 可用性 → 市場 | 日本(すべての市場でも可) |
| プロパティ → カテゴリ | ショッピング |
| プロパティ → 個人情報を扱うか(Does your extension access, collect, or transmit personal information?) | いいえ(No) |
| プロパティ → プライバシーポリシーのURL | https://pokeca-kaigai.com/extension-privacy.html |
| プロパティ → Web サイトの URL | https://pokeca-kaigai.com/(空欄でも可) |
| プロパティ → サポートの連絡先 | ご自身の連絡用メールアドレス |
| プロパティ → 成人向けコンテンツ | いいえ |
| ストア掲載情報 → 言語 | 日本語 |
| ストア掲載情報 → 説明 | 下の「説明」をそのまま貼る(250文字以上必要。満たしています) |
| ストア掲載情報 → 短い説明 | フリマ・通販サイトの商品ページに、そのポケカ・遊戯王・ワンピースカードの海外相場(円換算)を表示します。 |
| ストア掲載情報 → ストア ロゴ | `extension/icons/icon128.png` |
| ストア掲載情報 → スクリーンショット | `extension/store/screenshots/1-exact.png`, `extension/store/screenshots/2-candidates.png`, `extension/store/screenshots/3-yugioh.png`, `extension/store/screenshots/4-onepiece.png` |
| ストア掲載情報 → 小さい/大きいプロモーション タイル・YouTube | 空欄でよい(任意) |
| ストア掲載情報 → 検索語句(最大7個) | ポケカ / 遊戯王 / ワンピースカード / トレカ 相場 / 海外相場 / 価格比較 / 円換算 |
| 提出 → 認定のための注記(Notes for certification・英語のまま貼る) | This extension reads the product title (h1) on marketplace product pages, matches it against trading card names locally in the browser, and shows the overseas market price (converted to JPY) in the bottom-right corner. The only network requests fetch public price data (JSON) from pokeca-kaigai.com and pocketduel.tokyo; no information about the visited page is sent. To test: open a Mercari (jp.mercari.com) product page for a Pokemon card, e.g. search for "リザードンex 201/165". The code is not minified or obfuscated. |

### Firefox アドオン(AMO)

| 画面・項目 | 入力・選択 |
|---|---|
| 公開方法 | このサイトで公開する(On this site) |
| アップロード | `pokeca-kaigai-checker-0.3.1-firefox.zip`(Firefox 用) |
| 対応プラットフォーム | Firefox のみにチェック(Android はチェックを外す) |
| ソースコードの提出 | いいえ(No) |
| 名前 | トレカ海外相場チェッカー(ポケカ・遊戯王・ワンピース)(zip から自動で入る) |
| アドオンの URL | `toreca-kaigai-checker` |
| 概要(Summary・250文字以内) | フリマ・通販サイトの商品ページに、そのポケカ・遊戯王・ワンピースカードの海外相場(円換算)を表示します。 |
| 説明(Description) | 下の「説明」をそのまま貼る |
| 実験的なアドオン / 支払いが必要 | どちらもチェックしない |
| カテゴリ | ショッピング(Shopping) |
| サポートメール | ご自身の連絡用メールアドレス |
| サポートサイト | https://pokeca-kaigai.com/(空欄でも可) |
| ライセンス | 著作権所有(All Rights Reserved) |
| プライバシーポリシー | 「このアドオンにはプライバシーポリシーがあります」にチェックし、下の「プライバシーポリシー(Firefox 用)」を貼る |
| 審査担当者へのメモ(Notes to Reviewer・英語のまま貼る) | This extension reads the product title (h1) on marketplace product pages, matches it against trading card names locally in the browser, and shows the overseas market price (converted to JPY) in the bottom-right corner. The only network requests fetch public price data (JSON) from pokeca-kaigai.com and pocketduel.tokyo; no information about the visited page is sent. To test: open a Mercari (jp.mercari.com) product page for a Pokemon card, e.g. search for "リザードンex 201/165". The code is not minified or obfuscated. |
| 申請後: 製品ページの編集 → 画像 | スクリーンショットに `extension/store/screenshots/1-exact.png`, `extension/store/screenshots/2-candidates.png`, `extension/store/screenshots/3-yugioh.png`, `extension/store/screenshots/4-onepiece.png` |

#### 説明(Edge・Firefox 共通)

```
フリマ・通販サイトでポケモンカード・遊戯王・ワンピースカードの商品ページを開くと、
画面右下に「そのカードが海外でいくらで取引されているか」を表示します。

■ できること
・海外の大手トレカ市場(欧州 Cardmarket・米国 TCGplayer)の相場を、最新の為替レートで円換算して表示
・出品タイトルのカード名・型番・セット名から該当カードを判定
・該当が複数ある出品では、価格幅と候補を表示
・ポケカは7日平均との比較で、海外で値上がり中/値下がり中かもわかります

■ ポケモンカード(日本語版の欧州相場・Cardmarket)
直近に発売されたセットと、151・VSTARユニバース・テラスタルフェスex・シャイニートレジャーex・
VMAXクライマックスなどの人気セット、計22セット(約4,000枚)が対象です。
型番(例: 120/080)やセット名がタイトルにあれば、該当の1枚に絞り込んで表示します。
高騰・下落ランキングは「ポケカ海外相場モニター」(pokeca-kaigai.com)で公開しています。

■ 遊戯王(英語版の欧州相場・Cardmarket)
日本語のカード名で出品を判定し、英語版(TCG)カードの欧州相場を表示します。
価格は英語版で最も安い版の相場で、日本語版やレアリティ別の価格ではありません。
英語版の相場が€0.30以上のカード(約3,000枚)が対象です。
ランキングは「遊戯王海外相場モニター」(pocketduel.tokyo)で公開しています。

■ ワンピースカード(英語版の米国相場・TCGplayer)
タイトルのカード番号(例: OP05-119)で出品を判定し、英語版カードの米国相場を表示します。
パラレル・コミパラ・SP・金SP・手配書などの版はタイトルの語から見分け、
版の語がない出品は通常版として表示します。日本語版の相場ではありません。

データは1日2回自動更新されます。

■ プライバシー
閲覧中のページの商品名はブラウザ内だけで照合し、外部に送信しません。
個人情報・閲覧履歴は一切収集しません。

■ ご注意
・表示価格は海外市場の相場を円換算した参考値で、国内の販売・買取価格ではありません。
  ゲームごとに対象の版・市場が異なります(上記の各項目を参照)。
・本拡張は株式会社ポケモン、株式会社コナミデジタルエンタテインメント、株式会社集英社、株式会社バンダイ、Cardmarket、TCGplayer、各フリマ・通販サイトとは無関係の非公式ツールです。
```

#### プライバシーポリシー(Firefox 用)

```
本アドオンは、個人を特定できる情報・閲覧履歴・入力内容を収集せず、外部に送信しません。
ページの商品名の読み取りと照合はお使いのブラウザ内だけで行います。
相場データ(カード名と価格の一覧)を pokeca-kaigai.com・pocketduel.tokyo から数時間おきに取得します。閲覧中のページの情報は送信しません。
表示のON/OFFなどの設定だけをブラウザ内(storage)に保存します。
詳しくは https://pokeca-kaigai.com/extension-privacy.html をご覧ください。
```

---

## 求人 年収チェッカー(v0.1.2)

### Microsoft Edge アドオン(パートナーセンター)

| 画面・項目 | 入力・選択 |
|---|---|
| パッケージ | `job-salary-checker-0.1.2.zip`(Chrome と同じzip) |
| 可用性 → 表示 | パブリック(Public) |
| 可用性 → 市場 | 日本(すべての市場でも可) |
| プロパティ → カテゴリ | 生産性(Productivity) |
| プロパティ → 個人情報を扱うか(Does your extension access, collect, or transmit personal information?) | いいえ(No) |
| プロパティ → プライバシーポリシーのURL | https://pokeca-kaigai.com/job-extension-privacy.html |
| プロパティ → Web サイトの URL | https://pokeca-kaigai.com/(空欄でも可) |
| プロパティ → サポートの連絡先 | ご自身の連絡用メールアドレス |
| プロパティ → 成人向けコンテンツ | いいえ |
| ストア掲載情報 → 言語 | 日本語 |
| ストア掲載情報 → 説明 | 下の「説明」をそのまま貼る(250文字以上必要。満たしています) |
| ストア掲載情報 → 短い説明 | 求人ページの給与欄から、年収の目安・時給換算・固定残業代を自動で計算して表示します。 |
| ストア掲載情報 → ストア ロゴ | `job-extension/icons/icon128.png` |
| ストア掲載情報 → スクリーンショット | `job-extension/store/screenshots/1-annual.png`, `job-extension/store/screenshots/2-overtime.png` |
| ストア掲載情報 → 小さい/大きいプロモーション タイル・YouTube | 空欄でよい(任意) |
| ストア掲載情報 → 検索語句(最大7個) | 年収 / 年収計算 / 時給換算 / 固定残業代 / みなし残業 / 転職 / 求人 |
| 提出 → 認定のための注記(Notes for certification・英語のまま貼る) | This extension reads the salary, working hours and holidays sections of job listing pages (by looking for headings such as 給与 / 勤務時間 / 休日) and shows an estimated annual salary, hourly equivalent and fixed overtime pay in the bottom-right corner. All calculation happens locally; the extension makes no network requests. To test: open any job detail page on en-japan.com (en転職). The code is not minified or obfuscated. |

### Firefox アドオン(AMO)

| 画面・項目 | 入力・選択 |
|---|---|
| 公開方法 | このサイトで公開する(On this site) |
| アップロード | `job-salary-checker-0.1.2-firefox.zip`(Firefox 用) |
| 対応プラットフォーム | Firefox のみにチェック(Android はチェックを外す) |
| ソースコードの提出 | いいえ(No) |
| 名前 | 求人 年収チェッカー(zip から自動で入る) |
| アドオンの URL | `job-salary-checker` |
| 概要(Summary・250文字以内) | 求人ページの給与欄から、年収の目安・時給換算・固定残業代を自動で計算して表示します。 |
| 説明(Description) | 下の「説明」をそのまま貼る |
| 実験的なアドオン / 支払いが必要 | どちらもチェックしない |
| カテゴリ | その他(Other) |
| サポートメール | ご自身の連絡用メールアドレス |
| サポートサイト | https://pokeca-kaigai.com/(空欄でも可) |
| ライセンス | 著作権所有(All Rights Reserved) |
| プライバシーポリシー | 「このアドオンにはプライバシーポリシーがあります」にチェックし、下の「プライバシーポリシー(Firefox 用)」を貼る |
| 審査担当者へのメモ(Notes to Reviewer・英語のまま貼る) | This extension reads the salary, working hours and holidays sections of job listing pages (by looking for headings such as 給与 / 勤務時間 / 休日) and shows an estimated annual salary, hourly equivalent and fixed overtime pay in the bottom-right corner. All calculation happens locally; the extension makes no network requests. To test: open any job detail page on en-japan.com (en転職). The code is not minified or obfuscated. |
| 申請後: 製品ページの編集 → 画像 | スクリーンショットに `job-extension/store/screenshots/1-annual.png`, `job-extension/store/screenshots/2-overtime.png` |

#### 説明(Edge・Firefox 共通)

```
求人サイトの求人ページを開くと、画面右下に「この求人の年収はいくらくらいか」を自動で計算して表示します。

■ できること
・月給・日給・時給から年収の目安を計算(賞与の月数が書かれていれば含めて計算)
・求人に書かれた年収例・想定年収をまとめて表示(会社全体の平均年収は区別して表示)
・所定労働時間と年間休日から、時給に換算した金額を表示
・固定残業代(みなし残業代)を含む求人を警告し、それを除いた月給・時給を計算

■ 広告について
計算結果の下に、「PR」と明記した転職サービスの紹介リンク(広告)を表示する場合があります。
リンクはクリックした時だけ移動し、閲覧中のページ内のリンクを書き換えることはありません。

■ プライバシー
計算はすべてお使いのブラウザ内で行い、閲覧内容は外部に送信しません。
個人情報・閲覧履歴は一切収集しません。

■ ご注意
・表示する金額は求人の記載から機械的に計算した概算です。実際の条件は求人元に確認してください。
・勤務時間・休日の記載がない場合は「1日8時間・年間休日120日」と仮定して計算します(表示内に明記)。
・本拡張は各求人サイトの運営会社とは無関係の非公式ツールです。
```

#### プライバシーポリシー(Firefox 用)

```
本アドオンは、個人を特定できる情報・閲覧履歴・入力内容を収集せず、外部に送信しません。
ページの読み取りと計算はお使いのブラウザ内だけで行います。
外部のサーバーとの通信は一切行いません。
計算結果の下に「PR」と明記した紹介リンク(広告)を表示する場合があります。リンクはクリックした時だけ移動します。
表示のON/OFFなどの設定だけをブラウザ内(storage)に保存します。
詳しくは https://pokeca-kaigai.com/job-extension-privacy.html をご覧ください。
```

---

## 物件 単価・月額チェッカー(v0.1.0)

### Microsoft Edge アドオン(パートナーセンター)

| 画面・項目 | 入力・選択 |
|---|---|
| パッケージ | `realty-price-checker-0.1.0.zip`(Chrome と同じzip) |
| 可用性 → 表示 | パブリック(Public) |
| 可用性 → 市場 | 日本(すべての市場でも可) |
| プロパティ → カテゴリ | 生産性(Productivity) |
| プロパティ → 個人情報を扱うか(Does your extension access, collect, or transmit personal information?) | いいえ(No) |
| プロパティ → プライバシーポリシーのURL | https://pokeca-kaigai.com/realty-extension-privacy.html |
| プロパティ → Web サイトの URL | https://pokeca-kaigai.com/(空欄でも可) |
| プロパティ → サポートの連絡先 | ご自身の連絡用メールアドレス |
| プロパティ → 成人向けコンテンツ | いいえ |
| ストア掲載情報 → 言語 | 日本語 |
| ストア掲載情報 → 説明 | 下の「説明」をそのまま貼る(250文字以上必要。満たしています) |
| ストア掲載情報 → 短い説明 | 物件ページの記載から、㎡・坪単価、実質の月額、初期費用の目安、ローン返済額、利回りを計算して表示します。 |
| ストア掲載情報 → ストア ロゴ | `realty-extension/icons/icon128.png` |
| ストア掲載情報 → スクリーンショット | `realty-extension/store/screenshots/1-rent.png`, `realty-extension/store/screenshots/2-sale.png`, `realty-extension/store/screenshots/3-investment.png` |
| ストア掲載情報 → 小さい/大きいプロモーション タイル・YouTube | 空欄でよい(任意) |
| ストア掲載情報 → 検索語句(最大7個) | 坪単価 / 家賃 / 初期費用 / 住宅ローン / 利回り / 不動産 / 賃貸 |
| 提出 → 認定のための注記(Notes for certification・英語のまま貼る) | This extension reads real estate listing pages (headings such as 賃料 / 価格 / 専有面積) and shows price per square meter, effective monthly cost, estimated move-in cost, loan payment and yield in the bottom-right corner. All calculation happens locally; the extension makes no network requests. To test: open a rental property detail page on suumo.jp. The code is not minified or obfuscated. |

### Firefox アドオン(AMO)

| 画面・項目 | 入力・選択 |
|---|---|
| 公開方法 | このサイトで公開する(On this site) |
| アップロード | `realty-price-checker-0.1.0-firefox.zip`(Firefox 用) |
| 対応プラットフォーム | Firefox のみにチェック(Android はチェックを外す) |
| ソースコードの提出 | いいえ(No) |
| 名前 | 物件 単価・月額チェッカー(zip から自動で入る) |
| アドオンの URL | `realty-price-checker` |
| 概要(Summary・250文字以内) | 物件ページの記載から、㎡・坪単価、実質の月額、初期費用の目安、ローン返済額、利回りを計算して表示します。 |
| 説明(Description) | 下の「説明」をそのまま貼る |
| 実験的なアドオン / 支払いが必要 | どちらもチェックしない |
| カテゴリ | その他(Other) |
| サポートメール | ご自身の連絡用メールアドレス |
| サポートサイト | https://pokeca-kaigai.com/(空欄でも可) |
| ライセンス | 著作権所有(All Rights Reserved) |
| プライバシーポリシー | 「このアドオンにはプライバシーポリシーがあります」にチェックし、下の「プライバシーポリシー(Firefox 用)」を貼る |
| 審査担当者へのメモ(Notes to Reviewer・英語のまま貼る) | This extension reads real estate listing pages (headings such as 賃料 / 価格 / 専有面積) and shows price per square meter, effective monthly cost, estimated move-in cost, loan payment and yield in the bottom-right corner. All calculation happens locally; the extension makes no network requests. To test: open a rental property detail page on suumo.jp. The code is not minified or obfuscated. |
| 申請後: 製品ページの編集 → 画像 | スクリーンショットに `realty-extension/store/screenshots/1-rent.png`, `realty-extension/store/screenshots/2-sale.png`, `realty-extension/store/screenshots/3-investment.png` |

#### 説明(Edge・Firefox 共通)

```
不動産ポータルの物件ページを開くと、画面右下に「広さあたりいくらか」「毎月いくらかかるか」を自動で計算して表示します。

■ 賃貸物件
・賃料と管理費・共益費を合わせた実質の月額
・1㎡あたり・1坪あたりの月額(広さの違う部屋どうしを比べやすく)
・敷金・礼金・仲介手数料・前家賃から、初期費用の最低限の目安

■ 購入物件
・1㎡あたり・1坪あたりの価格
・ローン返済額に管理費・修繕積立金を足した、月々の支払いの目安
  (金利と返済期間は拡張機能のボタンから変更できます)

■ 投資物件
・表面利回りと年間収入(どちらか一方の記載から、もう一方を計算)
・管理費・修繕積立金を差し引いた簡易の実質利回り

■ 広告について
計算結果の下に、「PR」と明記した引越し・保険・住宅ローン等のサービスの紹介リンク(広告)を表示する場合があります。
リンクはクリックした時だけ移動し、閲覧中のページ内のリンクを書き換えることはありません。

■ プライバシー
計算はすべてお使いのブラウザ内で行い、閲覧内容は外部に送信しません。
個人情報・閲覧履歴は一切収集しません。

■ ご注意
・表示する金額・利回りは物件ページの記載から機械的に計算した概算です。実際の条件は不動産会社に確認してください。
・初期費用には保証会社・火災保険・鍵交換等の費用は含みません。
・簡易の実質利回りには固定資産税・空室・修繕費等は含みません。
・本拡張は各不動産ポータルの運営会社とは無関係の非公式ツールです。
```

#### プライバシーポリシー(Firefox 用)

```
本アドオンは、個人を特定できる情報・閲覧履歴・入力内容を収集せず、外部に送信しません。
ページの読み取りと計算はお使いのブラウザ内だけで行います。
外部のサーバーとの通信は一切行いません。
計算結果の下に「PR」と明記した紹介リンク(広告)を表示する場合があります。リンクはクリックした時だけ移動します。
表示のON/OFFなどの設定だけをブラウザ内(storage)に保存します。
詳しくは https://pokeca-kaigai.com/realty-extension-privacy.html をご覧ください。
```

---

## 審査で質問・却下が来たら

届いたメールや画面の文言を、そのまま Claude Code のセッションに貼ってください。修正版の zip を作ります。
Firefox のアドオンID(`toreca-checker@pokeca-kaigai.com`・`job-salary-checker@pokeca-kaigai.com`・`realty-price-checker@pokeca-kaigai.com`)は一度公開したら変えません。
