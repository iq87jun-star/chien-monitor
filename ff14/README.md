# FF14マーケットモニター

FF14(ファイナルファンタジーXIV)日本リージョンのマーケットボード相場を**全自動**で収集し、
AIが日本語の解説記事を生成する統計サイト。poe2/ と同一構成の横展開。

- データ出典: [Universalis](https://universalis.app)(クラウドソースのマーケットボード集計API)
- 対象: 日本DC統合リージョン(Japan)・約100アイテムのウォッチリスト(`data/watchlist.json`)
- 変動率(7日)は `data/history.json` に各実行時の価格を蓄積して算出(観測開始から蓄積される)
- 生成記事は**数値照合ゲート**を通過したものだけ公開(データにない数値を含む記事は自動却下)

## 構成

```
ff14/
├── pipeline/
│   ├── config.mjs             # 設定(API・閾値)
│   ├── fetch-data.mjs         # ① 収集: Universalis集計API → data/raw/market.json
│   ├── aggregate.mjs          # ② 集計・履歴更新・差分検知 → data/site/ + data/history.json
│   ├── generate-articles.mjs  # ③ AI記事生成(Claude API・構造化出力)→ content/
│   ├── validate.mjs           #    検品ゲート(数値照合・スキーマ検証)
│   └── run.mjs                # ①→②→③ 一括実行
├── data/watchlist.json        # 追跡アイテム(id + 日本語名・APIで検証済み)
├── data/history.json          # 価格履歴(7日窓・変動率の根拠。コミットする)
├── data/raw/                  # 取得した生データ
├── data/site/                 # サイト表示用の集計済みJSON
├── content/articles.json      # 検品を通過した生成記事
└── src/                       # サイト本体(Vite + React)
```

## ローカル実行

```bash
cd ff14
npm install
npm run pipeline     # 収集→集計→記事生成(記事生成は要 ANTHROPIC_API_KEY、無ければスキップ)
npm run dev          # 開発サーバー
npm run build        # 本番ビルド → dist/
```

## 注意事項

- UniversalisのAPIには説明的なUser-Agentを送信し、1回の実行あたり数リクエストに抑えている
- 本サイトは株式会社スクウェア・エニックス非公式のファンサイト。
  FF14の著作物は株式会社スクウェア・エニックスに帰属する
