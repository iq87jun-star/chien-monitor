# メルル査定(satei)

原神・崩壊スターレイルのアカウントを、キャラ一覧のスクショから買取査定する Web ページ。
@Meruru_Genshin への買取相談の入口として使う。

- 画面: `public/index.html`(Cloudflare Worker の静的アセット)。スクショを選ぶ → AI が星5キャラ・凸数・餅を読む →
  利用者が確認・修正 → 買取額の目安を **幅で** 表示 → X の DM・シェア・画像保存
- 画像の読み取り: `src/worker.js` の `POST /api/read`。Claude にスクショを渡し、決まった JSON の形で返してもらう。
  画像は保存しない。1日の回数に上限がある(1人5回・全体200回。`wrangler.toml` の vars)
- 値付け: `public/lib/estimate.js`。`public/model.json`(学習済みの重み)で売れた相場を出し、
  **× 0.55(買取の割合)** と、交差検証の誤差の 25%〜75% 点の幅をかける

## 値付けモデルの学習

学習データは gametrade-watch が貯めている「ゲームトレードで売れたアカウント」(D1 の `sold`)。

```sh
cd satei
GAMETRADE_INGEST_TOKEN=<合言葉> npm run train   # public/model.json を書き直す → コミット
```

- 特徴量: タイトル・説明文から読んだキャラごとの所持・凸数・モチーフ武器(`public/lib/features.js`)と星5の数
- モデル: log(売値) のリッジ回帰(`public/lib/model.js`)
- 査定では、値段に効く上位 `topK` 人だけを数える(出品タイトルに書かれるのは目玉の数人なので、手持ち全員を足すと高く出すぎる)
- 買取の割合は `scripts/train.mjs` の `BUY_RATE`、ゲームごとの補正(実際の買取の感覚に合わせる)は `ADJUST`
- 新キャラが出たら `public/lib/chars.js` に名前と別名を足してから学習し直す

## 設定

1. Anthropic の API キーを作り、GitHub の「Settings → Secrets and variables → Actions」に `SATEI_ANTHROPIC_API_KEY` として登録
   (未設定でも手入力の査定は動く)
2. `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID` は notify と共用
3. main に入ると `https://satei.<アカウント>.workers.dev` にデプロイされる
4. Discord の招待リンクができたら `public/index.html` の `DISCORD_URL` に入れる

## 手元で試す

```sh
cd satei
npm test
npx wrangler d1 migrations apply satei --local && npx wrangler dev   # http://localhost:8787
```
