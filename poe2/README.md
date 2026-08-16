# PoE2相場モニター

Path of Exile 2 の通貨相場・ユニークアイテム騰落・公式パッチ情報を**全自動**で収集し、
AIが日本語の解説記事を生成する統計サイト。

- データ出典: [poe.ninja](https://poe.ninja)(公開エコノミーAPI)+ Steam News API(公式ニュース)
- 6時間ごとにGitHub Actionsが自動更新(パッチ検知・相場急変時はAI記事も自動生成)
- 生成記事は**数値照合ゲート**を通過したものだけ公開(データにない数値を含む記事は自動却下)

## 構成

```
poe2/
├── pipeline/
│   ├── config.mjs             # 設定(API・閾値)
│   ├── fetch-data.mjs         # ① 収集: poe.ninja + Steam News → data/raw/
│   ├── aggregate.mjs          # ② 集計・差分検知 → data/site/ + changes.json
│   ├── generate-articles.mjs  # ③ AI記事生成(Claude API・構造化出力)→ content/
│   ├── validate.mjs           #    検品ゲート(数値照合・スキーマ検証)
│   └── run.mjs                # ①→②→③ 一括実行
├── data/raw/                  # 取得した生データ(差分検知に使うためコミットする)
├── data/site/                 # サイト表示用の集計済みJSON
├── content/articles.json      # 検品を通過した生成記事
└── src/                       # サイト本体(Vite + React)
.github/workflows/poe2-auto-update.yml  # 自動更新ワークフロー
```

## セットアップ

1. **このブランチをデフォルトブランチ(main)にマージする**
   — `schedule` トリガーはデフォルトブランチのワークフローにしか効かない
2. **リポジトリの Settings → Secrets and variables → Actions** に
   `ANTHROPIC_API_KEY` を追加(未設定でもデータ更新だけは動く)
3. **Settings → Pages** で Source を「Deploy from a branch」→ `gh-pages` ブランチに設定
   (初回はActionsを手動実行 `workflow_dispatch` すると gh-pages が作られる)

## ローカル実行

```bash
cd poe2
npm install
npm run pipeline     # 収集→集計→記事生成(要 ANTHROPIC_API_KEY)
npm run dev          # 開発サーバー
npm run build        # 本番ビルド → dist/
```

## 運用コストの目安

- GitHub Actions / Pages: 無料枠内
- Claude API: 記事生成は「大きな変化があった時 or 20時間ごと」に1回のみ。
  1回あたり入力2〜3K+出力2〜3Kトークン程度 → 月数百円規模(claude-opus-5基準)。
  `CLAUDE_MODEL` 環境変数でモデル変更可。

## 収益化の想定

- フッターにAdSense等の広告ユニットを挿入(`src/App.jsx` 末尾にコメントで位置を明記)
- 独自価値: 「日本語で読めるPoE2相場+パッチ自動解説」はpoe.ninja型サイトの日本語版として空白領域

## フェーズ2(未実装)

- **ビルドメタ統計**: GGG公式ラダーAPIはOAuthクライアント登録が必要
  ([developer docs](https://www.pathofexile.com/developer/docs))。
  登録後、ラダー上位1,000キャラのクラス/スキル構成を集計して「今リーグの人気ビルド」ページを追加予定
- X(Twitter)速報bot: パッチ検知時に要約を自動ポスト
- 同一パイプラインの横展開(別ゲーム)

## 注意事項

- poe.ninjaのAPI利用ガイドラインに従い、説明的なUser-Agentを送信し、
  ポーリング間隔は最短でも6時間にしている(キャッシュは約5分)
- 本サイトはGrinding Gear Games非公式のファンサイト。ゲーム画像の利用は
  各社ガイドラインに従うこと(現状はpoe.ninja経由の公式CDN画像を参照表示のみ)
