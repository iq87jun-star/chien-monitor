# CS2スキン相場モニター

Counter-Strike 2 のスキン相場(高騰・下落・高額スキン)を**全自動**で収集し、
AIが日本語の解説記事を生成する統計サイト。`tarkov/` と同じパイプライン構成の横展開
(ゲーム相場モニター群 game-souba.com/cs2/ として配信)。

- データ出典: [Skinport](https://skinport.com)(キー不要の公開API・全2.5万スキンの
  出品価格を1リクエストで取得)+ [Frankfurter](https://frankfurter.dev)(ECB為替)
- 表示価格は出品の**中央値**を優先(最安値は板の薄いスキンで振れやすいため)。円換算つき
- **騰落率は自前の価格履歴から計算**(このAPIは現在の出品状況のみのため、$5以上・出品2件以上の
  約1万スキンを毎日記録して7日比を算出。稼働開始から数日で騰落ランキングが出現する)
- 独自コーナー: ★付き(ナイフ・グローブ)の高額ランキング
- 生成記事は**数値照合ゲート**を通過したものだけ公開(データにない数値を含む記事は自動却下)
- Skinport側の障害時はフェイルセーフ: 既存データを保持し、初回はメンテナンス表示でビルドを継続

## 構成

```
cs2/
├── pipeline/
│   ├── config.mjs             # 設定(API・閾値)
│   ├── fetch-data.mjs         # ① 収集: Skinport API → data/raw/items.json + 履歴蓄積
│   ├── aggregate.mjs          # ② 集計・差分検知 → data/site/ + changes.json
│   ├── generate-articles.mjs  # ③ AI記事生成(Claude API・構造化出力)→ content/
│   ├── validate.mjs           #    検品ゲート(数値照合・スキーマ検証)
│   ├── post-x.mjs             # ④ X(Twitter)速報(任意)
│   ├── prerender.mjs          #    記事静的ページ生成(ビルド後)
│   └── run.mjs                # ①→②→③→④ 一括実行
├── data/raw/                  # 取得した生データ+価格履歴(コミットする)
├── data/site/                 # サイト表示用の集計済みJSON
├── content/articles.json      # 検品を通過した生成記事
└── src/                       # サイト本体(Vite + React)
```

## セットアップ

poe2 / tarkov と同じ。`.github/workflows/poe2-auto-update.yml` のサイトループに
含まれており、6時間ごとに自動更新される。

X速報を有効にする場合はSecretsに `CS2_X_ACCESS_TOKEN` / `CS2_X_ACCESS_TOKEN_SECRET`
(bot垢のトークン。アプリキーは共通の `X_API_KEY` / `X_API_SECRET`)を追加する。

## ローカル実行

```bash
cd cs2
npm install
npm run pipeline     # 収集→集計→記事生成(記事生成は要 ANTHROPIC_API_KEY)
npm run dev          # 開発サーバー
npm run build        # 本番ビルド → dist/
```

## 注意事項

- Skinport APIのレート制限は8リクエスト/5分。取得は1実行1リクエストに留めること
- 本サイトはValve・Skinport非公式のファンサイト。
  記事は投資・売買の助言ではない旨をサイト内に明記している
