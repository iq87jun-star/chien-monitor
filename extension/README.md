# ポケカ海外相場チェッカー(Chrome拡張)

メルカリ・ヤフオク・ラクマ・駿河屋の商品ページで、そのポケカ(日本語版)の
**海外相場(Cardmarket・円換算)** を画面右下に表示するブラウザ拡張。
データは toreca/(pokeca-kaigai.com)のパイプラインが1日2回更新するものを流用する。

狙い: 国内のフリマ閲覧中に「海外ではいくらか」を出すツールは見当たらない空白領域。
拡張自体は無料で、バッジのリンクから pokeca-kaigai.com へ送客する(サイト側の広告・
アフィリエイトで収益化)。将来は値下がり通知などを有料機能にする余地を残す。

## 仕組み

```
toreca パイプライン(1日2回)
  └ npm run build → dist/api/cards.json(22セット約4,000枚・200KB)を pokeca-kaigai.com に配信
                                   │ 6時間キャッシュで取得
拡張 background.js(service worker)┘
  └ content.js: 商品ページの h1 を読み取り → matcher.js でカード名と照合 → バッジ表示
```

- **照合**: 表記揺れ(全角・ひらがな・空白)を正規化し、長いカード名から優先して一致判定。
  タイトルに型番(`120/080`)やセット略号・セット名があれば1枚に絞り込む。
  絞り込めない場合は同名カードの価格幅と上位候補を出す
- **誤表示対策**: 「ポケカ」等の語・型番・セット名のいずれもないタイトル(ぬいぐるみ等の
  同名グッズ)、サプライ・未開封BOX・オリパ、4種以上のカード名を含むまとめ売り、
  3文字未満のカード名は表示しない。タイトルのセットに該当カードが無い場合(監視外セットの
  同名カード)も別セットの価格を出さない
- **セット名の略称**: 「151」「テラスタルフェス」のように略された書き方でもセットを判定する
- **プライバシー**: 商品名の照合はブラウザ内で完結し、外部に送るのは相場JSONの取得リクエストだけ
- 形式を変える時は `toreca/pipeline/export-ext.mjs` と `src/matcher.js` の `FORMAT_VERSION` を揃える

## 開発

```bash
cd extension
npm ci
npm test                      # 単体テスト(照合ロジック・実データのスナップショットで検証)
npm run test:e2e              # 実Chromiumに拡張を読み込んでモックの商品ページで表示確認
npm run test:e2e -- --shots   # 上記+ストア用スクリーンショットを store/screenshots/ に更新
npm run pack                  # ストア提出用zipを dist/ に作成
npm run icons                 # アイコンを再生成
```

手元のChromeで試す: `chrome://extensions` → デベロッパーモードON →
「パッケージ化されていない拡張機能を読み込む」→ この `extension/` フォルダを選択。
※ 相場データ `pokeca-kaigai.com/api/cards.json` は toreca の自動更新(1日2回)で更新される。
監視セットは `toreca/pipeline/config.mjs` の `MONITOR_SETS`(直近の自動選択数)と
`EXTRA_SETS`(常に監視する人気セット)で変える。

## 公開手順

### 初回だけ手作業(30分〜1時間)

1. **toreca 側を先に反映**: このブランチをmainにマージし、`toreca-auto-update` を
   workflow_dispatch で実行。次の2つが開けることを確認する
   - https://pokeca-kaigai.com/api/cards.json
   - https://pokeca-kaigai.com/extension-privacy.html(ストア審査で必要)
2. **デベロッパー登録**: [Chrome Web Store デベロッパーダッシュボード](https://chrome.google.com/webstore/devconsole)
   で登録料5ドルを支払う(2段階認証が必須)
3. **zipを作る**: `npm run pack`(またはActionsの `extension-publish` を手動実行して
   Artifact の `extension-zip` をダウンロード)
4. **新しいアイテム**としてzipをアップロードし、`store/listing.md` の内容を各欄に貼る。
   スクリーンショットは `store/screenshots/*.png`、アイコンは `icons/icon128.png`
5. 審査に提出(通常数日)

### 2回目以降は自動(タグをpushするだけ)

1. Google Cloud Console でプロジェクトを作り「Chrome Web Store API」を有効化 →
   OAuthクライアントID(種類: デスクトップ)を作成し、リフレッシュトークンを取得する。
   手順は [chrome-webstore-upload の説明](https://github.com/fregante/chrome-webstore-upload-keys) が簡潔
2. リポジトリの Secrets に登録: `CWS_EXTENSION_ID`(初回出品で発行されたID)/
   `CWS_CLIENT_ID` / `CWS_CLIENT_SECRET` / `CWS_REFRESH_TOKEN`
3. リリース時は `manifest.json` と `package.json` の version を上げてコミットし、
   同じ番号のタグをpush:
   ```bash
   git tag ext-v0.1.1 && git push origin ext-v0.1.1
   ```
   → テスト → zip作成 → アップロード → 公開申請 まで自動(審査はGoogle側)

## 今後の拡張案

- 対応ジャンル追加: duel/(遊戯王)も同じ形式のJSONを出せば照合ロジックは流用可能
- 有料機能: 気になるカードの値下がり通知(LINE/Discord)、価格履歴グラフ
- 対応サイト追加: カードラッシュ・晴れる屋等のショップ(商品名の取得箇所が h1 なら追加はmanifestのみ)
