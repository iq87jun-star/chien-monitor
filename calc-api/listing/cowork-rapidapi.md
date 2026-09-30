# Cowork 用の作業指示(RapidAPI: 計算API「手取り計算」の出品の入力)

この文書を Cowork にそのまま渡して使う。人が行う作業(★)と、Cowork に任せる作業を分けてある。
Cowork は「止まる」と書かれた所で必ず作業を止め、人に確認すること。

出品(プロジェクト)「**Japan Take-Home Pay Calculator**」は人が作成済み。Cowork はその中身を入力する。
入力する文章はすべて [marketplace.md](marketplace.md) の「3. Japan Take-Home Pay Calculator(takehome)」と「料金プラン」にある。

| 作業 | 内容 |
|---|---|
| R1 | 掲載情報(説明・カテゴリ・タグ・ロゴ・利用規約) |
| R2 | 仕様書(OpenAPI)の読み込み |
| R3 | Base URL の設定と、秘密の値(Proxy Secret)を GitHub の Secrets に登録 |
| R4 | 料金プランの入力 |

## 守ること(Cowork 向け)

- パスワード・2段階認証・**支払いの受け取り情報(Payout)・税務フォーム(W-8BEN 等)は入力しない**。その画面に来たら止まる
- **公開(Public にする・Publish)は押さない**。最後に人が行う
- 秘密の値(Proxy Secret)は、RapidAPI の画面から GitHub の画面へ貼るだけにする。Issue・会話・メモに書き出さない
- 文章は marketplace.md の ``` で囲まれた部分だけを使い、自分で文章を作らない
- ほかの出品(プロジェクト)は作らない・変えない

## 事前準備(★人が行う)

1. パソコンの Chrome で RapidAPI(https://rapidapi.com)と GitHub にログインしておく
2. Cowork に「https://github.com/iq87jun-star/chien-monitor/blob/main/calc-api/listing/cowork-rapidapi.md の作業をして」と伝える

## 作業R1: 掲載情報(Cowork)

1. https://rapidapi.com/studio を開き、「Japan Take-Home Pay Calculator」を開く
2. 「General」タブ:
   - Short Description(または Description): marketplace.md の takehome の**短い説明**に置き換える(今は URL が入っていることがある)
   - Long Description: **長い説明**
   - Category: `Finance`
   - Tags(あれば): `japan`, `payroll`, `take-home pay`, `income tax`, `social insurance`, `salary`, `hr`
   - Website(任意): `https://jp-listing-calc-api.iq87jun.workers.dev/openapi.json?product=takehome`
   - Terms of Use(あれば): marketplace.md の「利用規約に入れる内容」の英文
   - Logo: `calc-api/listing/logo.png`(https://github.com/iq87jun-star/chien-monitor/raw/main/calc-api/listing/logo.png を保存してアップロード)。
     ファイルを選ぶ画面を操作できなければ飛ばし、報告に書く
3. 保存(Save)を押す

## 作業R2: 仕様書の読み込み(Cowork)

1. 「Definitions」タブで、OpenAPI の読み込み(Import / Upload OpenAPI)を選ぶ
2. URL から読み込めるなら `https://jp-listing-calc-api.iq87jun.workers.dev/openapi.json?product=takehome` を入れる。
   ファイルだけなら、この URL をブラウザで開いて `takehome.json` として保存し、そのファイルを選ぶ
3. 既存のエンドポイントを置き換えるか聞かれたら「置き換える」
4. 読み込み後、エンドポイント `POST /v1/takehome/calculate` と `GET /v1/health` があることを確かめる。エラーが出たら**止まる**(文言をそのまま報告)

## 作業R3: Base URL と秘密の値(Cowork)

1. 「Gateway」タブ(または「Settings」)の Base URL(Target URL)に `https://jp-listing-calc-api.iq87jun.workers.dev` を入れて保存
2. 同じタブの「Security」あたりにある **X-RapidAPI-Proxy-Secret** の値をコピーする
3. https://github.com/iq87jun-star/chien-monitor/settings/secrets/actions/new を開き、次を登録する
   - Name: `MARKETPLACE_SECRETS`(半角で入力)
   - Secret: `x-rapidapi-proxy-secret:` + コピーした値 + `@takehome`(1行・空白なし)
   - `MARKETPLACE_SECRETS` が既にある場合は**止まる**(上書きせず人に知らせる)
4. **止まる**: 人に「秘密の値を登録しました。Claude Code に公開し直してもらってください」と伝える

## 作業R4: 料金プラン(Cowork・R3 の後、人の了承があってから)

「Monetize」タブで、Public Plans を次のとおり作る(ドル建て・月額)。

| プラン | 月額 | 回数/月 | 上限を超えた時 |
|---|---|---|---|
| BASIC | 無料 | 100 | 止める(Hard limit) |
| PRO | $9.99 | 10,000 | 1回 $0.0005 |
| ULTRA | $29.99 | 100,000 | 1回 $0.0003 |
| MEGA | $99.99 | 1,000,000 | 1回 $0.0002 |

- 回数の対象はすべてのエンドポイント(Requests)
- 支払いの受け取り情報や税務フォームの入力を求められたら**止まる**
- **止まる**: 「Public にする」は押さずに、入力した内容を人に報告する

## 報告(Cowork)

作業が終わった時・止まった時は、人に知らせるのに加えて、[cowork/README.md](../../cowork/README.md) の
「報告の出し方」のとおり GitHub の Issue(「Cowork の作業報告」)に結果を書き、Issue の番号を人に伝える
(秘密の値は書かない)。

## 最終(★人が行う)

- Claude Code が公開し直し、RapidAPI の「Test Endpoint」で呼べることを確かめる
- 支払いの受け取り情報(Payout)と税務フォームを入力する
- 出品を Public にする
