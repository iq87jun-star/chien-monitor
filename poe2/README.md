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

## フェーズ2(実装済み・認証情報の投入で有効化)

どちらもSecrets未設定の間は自動でスキップされ、他の機能に影響しない。

### A. 人気ビルド統計(`pipeline/fetch-ladder.mjs`)

公式ラダーAPI(上位1,000キャラ)からクラス/アセンダンシー分布と上位キャラ一覧を集計し、
サイトに「人気クラス分布」カードを表示する。

**有効化手順(GGGのOAuthクライアント登録):**
1. https://www.pathofexile.com/developer/docs を確認し、案内に従って
   `oauth@grindinggear.com` 宛にOAuthクライアント登録を申請する
   (アプリ名、用途 = ladder statistics website、grant type = client_credentials、
   scope = `service:leagues:ladder` を記載)。承認まで数日〜数週間かかる場合がある
2. 発行された client_id / client_secret をリポジトリSecretsに
   `GGG_CLIENT_ID` / `GGG_CLIENT_SECRET` として登録

### B. X(Twitter)速報bot(`pipeline/post-x.mjs`)

新しいパッチ関連ニュースの検知時と、新しいAI記事の公開時に自動ポストする
(1回の実行で最大2ポスト、重複ポストは `data/site/posted.json` で防止)。

**有効化手順(X開発者登録):**
1. bot用のXアカウントでログインし https://developer.x.com/ で開発者登録(Freeプランで可。
   Freeは投稿数に月間上限があるが本botの頻度なら十分)
2. Project & App を作成 → App の「User authentication settings」で
   Read and write 権限を設定
3. 「Keys and tokens」で API Key / API Key Secret / Access Token / Access Token Secret
   の4つを生成し、リポジトリSecretsに `X_API_KEY` / `X_API_SECRET` /
   `X_ACCESS_TOKEN` / `X_ACCESS_TOKEN_SECRET` として登録

## フェーズ3(未実装)

- 同一パイプラインの横展開(別ゲーム)

## 注意事項

- poe.ninjaのAPI利用ガイドラインに従い、説明的なUser-Agentを送信し、
  ポーリング間隔は最短でも6時間にしている(キャッシュは約5分)
- 本サイトはGrinding Gear Games非公式のファンサイト。ゲーム画像の利用は
  各社ガイドラインに従うこと(現状はpoe.ninja経由の公式CDN画像を参照表示のみ)
