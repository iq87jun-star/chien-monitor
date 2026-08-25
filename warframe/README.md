# Warframe相場モニター

Warframe のプレイヤー間取引相場(プライムセット・アルケイン・Primed MOD)を**全自動**で収集し、
AIが日本語の解説記事を生成する統計サイト。`tarkov/` と同じパイプライン構成の横展開
(ゲーム相場モニター群 game-souba.com/warframe/ として配信)。

- データ出典: [warframe.market](https://warframe.market)(キー不要の公開API・日本語アイテム名対応)
- 監視対象は**全プライムセット(自動検出)**+定番のアルケイン・Primed MOD(約170品目)
- 価格は取引成立価格の**中央値**(プラチナ)、変動率は約7日比、取引量は直近7日の成立数
- APIが90日分の日次統計を持つため履歴の自前蓄積は不要。**初回から騰落ランキングが出る**
- 生成記事は**数値照合ゲート**を通過したものだけ公開(データにない数値を含む記事は自動却下)
- warframe.market側の障害時はフェイルセーフ: 既存データを保持し、初回はメンテナンス表示でビルドを継続

## 構成

```
warframe/
├── pipeline/
│   ├── config.mjs             # 設定(API・監視対象・閾値)
│   ├── fetch-data.mjs         # ① 収集: v2品目一覧→v1日次統計 → data/raw/items.json
│   ├── aggregate.mjs          # ② 集計・差分検知 → data/site/ + changes.json
│   ├── generate-articles.mjs  # ③ AI記事生成(Claude API・構造化出力)→ content/
│   ├── validate.mjs           #    検品ゲート(数値照合・スキーマ検証)
│   ├── post-x.mjs             # ④ X(Twitter)速報(任意)
│   ├── prerender.mjs          #    記事静的ページ生成(ビルド後)
│   └── run.mjs                # ①→②→③→④ 一括実行
├── data/raw/                  # 取得した生データ(コミットする)
├── data/site/                 # サイト表示用の集計済みJSON
├── content/articles.json      # 検品を通過した生成記事
└── src/                       # サイト本体(Vite + React)
```

## セットアップ

poe2 / tarkov と同じ。`.github/workflows/poe2-auto-update.yml` のサイトループに
含まれており、6時間ごとに自動更新される。

X速報を有効にする場合はSecretsに `WARFRAME_X_ACCESS_TOKEN` / `WARFRAME_X_ACCESS_TOKEN_SECRET`
(bot垢のトークン。アプリキーは共通の `X_API_KEY` / `X_API_SECRET`)を追加する。

## ローカル実行

```bash
cd warframe
npm install
npm run pipeline     # 収集→集計→記事生成(記事生成は要 ANTHROPIC_API_KEY)
npm run dev          # 開発サーバー
npm run build        # 本番ビルド → dist/
```

## 注意事項

- warframe.market APIのレート制限(約3リクエスト/秒)に収まるよう、
  同時実行2+リクエスト間350msで取得している(1実行あたり約170リクエスト・1〜2分)
- プラチナはゲーム内通貨。リアルマネー取引(RMT)を推奨しない旨をサイト内に明記している
- 本サイトはDigital Extremes・warframe.market非公式のファンサイト。
  アイテム画像はwarframe.market経由の参照表示のみ
