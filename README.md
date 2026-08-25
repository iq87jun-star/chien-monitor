# chien-monitor — 全自動 相場モニター サイト群

外部APIから市場データを定期取得し、差分検知 → AI記事生成(数値照合ゲート付き)→
静的サイトビルド → 自動デプロイ → X速報までを全自動で回すサイト群のモノレポ。

## サイト一覧(10サイト)

### ゲーム相場モニター群(game-souba.com・このリポジトリのgh-pagesに一括デプロイ)

| ディレクトリ | サイト | データ源 | 更新 |
|---|---|---|---|
| `portal/` | ポータル(トップ) | — | — |
| `poe2/` | PoE2相場モニター | poe.ninja / GGG API | 6時間ごと |
| `poe1/` | PoE1相場モニター | poe.ninja `/poe1/` | 6時間ごと |
| `tarkov/` | タルコフ相場モニター | tarkov.dev GraphQL | 6時間ごと |
| `ff14/` | FF14マーケットモニター | Universalis | 6時間ごと |
| `cs2/` | CS2スキン相場モニター | Skinport | 6時間ごと |
| `warframe/` | Warframe相場モニター | warframe.market | 6時間ごと |

ワークフロー: `.github/workflows/poe2-auto-update.yml`(全ゲームサイトを一括処理)

### トレカ海外相場群(サイトごとに独自ドメイン・外部リポジトリへデプロイ)

| ディレクトリ | サイト | ドメイン | データ源 | ワークフロー |
|---|---|---|---|---|
| `toreca/` | ポケカ海外相場モニター | pokeca-kaigai.com | TCGdex | `toreca-auto-update.yml` |
| `duel/` | 遊戯王海外相場モニター | pocketduel.tokyo | YGOPRODeck | `duel-auto-update.yml` |
| `mtg/` | MTG海外相場モニター | mtg-kaigai.com(予定) | Scryfall | `mtg-auto-update.yml` |

### その他

- `twa/` — poe2のAndroid(TWA)アプリ用マニフェスト
- `scripts/generate-sitemap.mjs` — game-souba.com 全体のsitemap生成
- ルートの `src/` / `index.html` — 旧chien-monitor(開発用)

## 共通アーキテクチャ

各サイトは同一のパイプライン構成(`pipeline/` 以下):

```
fetch-data → aggregate(差分検知)→ generate-articles(Claude API+数値照合ゲート)
→ post-x(X速報・任意)→ vite build → 記事静的ページ生成(prerender / gen-pages)
```

- 認証情報が未設定の機能は自動スキップ(データ更新だけでも動く)
- データ源の障害時は既存データを保持してビルド継続(フェイルセーフ)
- 生成記事は「データにない数値を含む記事を自動却下」する検品ゲートを通過したものだけ公開

新サイトを追加する場合は、TCG系なら `duel/`、ゲーム系なら `tarkov/` か `warframe/` を
コピーして `pipeline/config.mjs` とfetch層を差し替えるのが最短。
