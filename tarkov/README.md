# タルコフ相場モニター

Escape from Tarkov のフリーマーケット相場(高騰・下落・高額アイテム)を**全自動**で収集し、
AIが日本語の解説記事を生成する統計サイト。`poe2/` と同じパイプライン構成の横展開。

- データ出典: [tarkov.dev](https://tarkov.dev)(公開GraphQL API・日本語アイテム名対応)
- 価格は24時間平均(₽)、変動率は直近48時間(`changeLast48hPercent`)
- 生成記事は**数値照合ゲート**を通過したものだけ公開(データにない数値を含む記事は自動却下)
- tarkov.dev 側の障害時はフェイルセーフ: 既存データを保持し、初回はメンテナンス表示でビルドを継続

## 構成

```
tarkov/
├── pipeline/
│   ├── config.mjs             # 設定(API・閾値)
│   ├── fetch-data.mjs         # ① 収集: tarkov.dev GraphQL → data/raw/items.json
│   ├── aggregate.mjs          # ② 集計・差分検知 → data/site/ + changes.json
│   ├── generate-articles.mjs  # ③ AI記事生成(Claude API・構造化出力)→ content/
│   ├── validate.mjs           #    検品ゲート(数値照合・スキーマ検証)
│   └── run.mjs                # ①→②→③ 一括実行
├── data/raw/                  # 取得した生データ(差分検知に使うためコミットする)
├── data/site/                 # サイト表示用の集計済みJSON
├── content/articles.json      # 検品を通過した生成記事
└── src/                       # サイト本体(Vite + React)
```

## セットアップ

poe2 と同じ手順。

1. リポジトリの **Settings → Secrets and variables → Actions** に
   `ANTHROPIC_API_KEY` を追加(未設定でもデータ更新だけは動く)
2. 自動更新用のワークフローを追加する場合は poe2 のワークフローを参考に
   `tarkov/` ディレクトリで `npm ci && npm run pipeline && npm run build` を実行する

## ローカル実行

```bash
cd tarkov
npm install
npm run pipeline     # 収集→集計→記事生成(記事生成は要 ANTHROPIC_API_KEY)
npm run dev          # 開発サーバー
npm run build        # 本番ビルド → dist/
```

## 注意事項

- tarkov.dev API は無償の公開APIのため、説明的なUser-Agentを送信し、
  ポーリング間隔は最短でも数時間にすること
- 本サイトはBattlestate Games非公式のファンサイト。アイテム画像はtarkov.dev経由の参照表示のみ
