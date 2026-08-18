# ポケカ海外相場モニター

ポケモンカード**日本語版**カードの**海外市場価格**(Cardmarket=欧州最大のトレカ市場)を全自動で収集し、
円換算つきの高騰・下落・高額ランキングとAI日本語解説記事を掲載する統計サイト。

国内相場サイト(ポケカチ・みんなのポケカ相場等)がひしめくレッドオーシャンを避け、
「**日本語版カードが海外でいくらで取引されているか**」という空白領域を狙う。
想定読者は日本のコレクターとeBay等の輸出セラー。

- データ出典: [TCGdex](https://tcgdex.dev)(キー不要の公開API・Cardmarket/TCGplayer価格)
  + [Frankfurter](https://frankfurter.dev)(ECB為替レート・円換算用)
- 1日2回GitHub Actionsが自動更新(Cardmarket価格の更新は1日1回のため)
- 生成記事は**数値照合ゲート**を通過したものだけ公開(データにない数値を含む記事は自動却下)
- 監視対象: 直近発売の日本語版セット4つ(約600〜1,000枚)。`pipeline/config.mjs` で変更可

## 構成

poe2/tarkov/ff14 と同じパイプライン構造(確立済みの型の横展開第1号・ゲーム外ジャンル):

```
toreca/
├── pipeline/
│   ├── config.mjs             # 設定(API・監視セット数・閾値)
│   ├── fetch-data.mjs         # ① 収集: TCGdex(日本語版セット)+ ECB為替 → data/raw/
│   ├── aggregate.mjs          # ② 円換算・騰落率計算・差分検知 → data/site/ + changes.json
│   ├── generate-articles.mjs  # ③ AI記事生成(Claude API・構造化出力)→ content/
│   ├── validate.mjs           #    検品ゲート(数値照合・スキーマ検証)※4サイト共通
│   └── run.mjs                # ①→②→③ 一括実行
├── data/raw/                  # 取得した生データ(差分検知に使うためコミットする)
├── data/site/                 # サイト表示用の集計済みJSON
├── content/articles.json      # 検品を通過した生成記事
└── src/                       # サイト本体(Vite + React)
.github/workflows/toreca-auto-update.yml  # 自動更新ワークフロー
```

騰落率はCardmarketが返す期間平均(avg1/avg7/avg30)の乖離から計算するため、
自前の価格履歴の蓄積を待たずに初回から7日/30日の変動が出せる。

## セットアップ

1. **このブランチをデフォルトブランチ(main)にマージする**
   — `schedule` トリガーはデフォルトブランチのワークフローにしか効かない
2. **Settings → Secrets and variables → Actions** に `ANTHROPIC_API_KEY` を追加
   (既に他サイト用に設定済みならそのまま使われる。未設定でもデータ更新だけは動く)
3. **デプロイ先(重要)**: ジャンルが「ゲーム攻略」と異なるため、AdSense/SEOの
   テーマ一貫性の観点から **game-souba.com とは別のリポジトリ・別ドメイン**で公開する。
   1. 公開用リポジトリを新規作成(例: `toreca-kaigai`)
   2. Fine-grained PAT(対象=そのリポジトリ、Contents: Read and write)を発行し、
      本リポジトリのSecretsに `TORECA_DEPLOY_TOKEN` として登録
   3. Secretsに `TORECA_DEPLOY_REPO` を `iq87jun-star/toreca-kaigai` の形式で登録
   4. Actionsを手動実行(`workflow_dispatch`)すると公開用リポジトリに `gh-pages`
      ブランチが作られるので、そちらの Settings → Pages で公開設定(+独自ドメイン設定)

   Secrets未設定の間はデプロイだけがスキップされ、データ更新・記事生成は動き続ける。

## ローカル実行

```bash
cd toreca
npm install
npm run pipeline     # 収集→集計→記事生成(記事生成は要 ANTHROPIC_API_KEY)
npm run dev          # 開発サーバー
npm run build        # 本番ビルド → dist/
```

## 運用コストの目安

- GitHub Actions / Pages: 無料枠内
- Claude API: 記事生成は「大きな変化があった時 or 20時間ごと」に1回のみ(他サイトと同じ)
- TCGdex / Frankfurter: 無料・キー不要

## X(Twitter)速報bot(実装済み・認証情報の投入で有効化)

急騰カードの検知時(7日比+25%超の上昇率トップ)と、新しいAI記事の公開時に自動ポストする
(1回の実行で最大2ポスト、重複ポストは `data/site/posted.json` で防止)。
Secrets未設定の間は自動でスキップされ、他の機能に影響しない。

**有効化手順:**
1. bot用のXアカウントを新規作成(例: `@toreca_kaigai`。ポスト先になるアカウント)
2. そのアカウントでログインし https://developer.x.com/ で開発者登録(Freeプランで可。
   Freeは投稿数に月間上限があるが本botの頻度=1日最大4ポストなら十分)
3. Project & App を作成 → App の「User authentication settings」で
   Read and write 権限を設定
4. 「Keys and tokens」で API Key / API Key Secret / Access Token / Access Token Secret
   の4つを生成し、リポジトリSecretsに登録:
   - `TORECA_X_API_KEY` / `TORECA_X_API_SECRET` … 手順4のAPI Key側
   - `TORECA_X_ACCESS_TOKEN` / `TORECA_X_ACCESS_TOKEN_SECRET` … 手順4のAccess Token側

⚠️ ゲーム系ボット(PoE2/FF14)が使用中の `X_API_KEY` / `X_API_SECRET` は
   **上書きしないこと**(既存ボットが停止する)。torecaは `TORECA_X_API_KEY` 側を
   優先して使い、未設定の場合のみ共通キーにフォールバックする。
   Access Tokenは「そのAPI Keyを発行したアプリ」で生成したものでないと認証が通らない。

## フェーズ3(未実装)

- **マイナーTCG対応**: [JustTCG API](https://justtcg.com)(無料枠 月1,000コール)で
  ワンピースカード・Union Arena・ガンダムカードゲーム・hololiveカード等へ拡張。
  国内相場サイトが手薄な新興タイトルはほぼ競合不在
- **PSA鑑定品価格**: eBay売却実績系のデータ源が確保できれば追加

## 注意事項

- TCGdexはキー不要の公開APIだが、説明的なUser-Agentを送り、
  同時リクエスト数を絞って(6並列)1日2回の取得に留めている
- 円換算はECB公表レートによる参考値であり、実際の取引レートとは異なる
- 本サイトは株式会社ポケモン・Cardmarketと無関係の非公式ファンサイト。
  記事は投資・売買の助言ではない旨をサイト内に明記している
- カード画像はTCGdexのCDNを参照表示のみ(再配布しない)
