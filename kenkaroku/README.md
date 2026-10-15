# 剣華録（けんかろく）

架空の戦国「八洲」で、少女剣士「剣華」たちを率いて鬼の首魁・酒呑の封印を目指す放置RPGです。
スマホ縦画面（幅360〜430px）向けに作っています。PCでは中央に540px幅で表示します。

## 起動方法

```bash
cd kenkaroku
npm install
npm run dev        # 開発サーバー（http://localhost:5173）
npm test           # ユニットテスト（Vitest）
npm run build      # 型チェック＋本番ビルド（dist/）
npm run preview    # ビルド結果の確認
```

Node.js 20 以上を想定しています。

## 遊び方

| 画面 | できること |
|---|---|
| 出陣 | 編成リーダーとの会話、放置報酬（最大12時間・高速放置1日2回）、ステージへ出陣 |
| 編成 | 前列2・後列3。通常攻撃はまず前列が狙われます |
| 剣華 | 一覧と詳細。レベル上げ・開花（★上げ）、プロフィール、台詞、縁 |
| 花結び | 召喚。UR3%（うちピックアップ50%）・SSR15%・SR82%、十連でSSR以上確定、80回で天井 |
| 任務 | 開花任務（花片集め・1日3回）と初心者任務 |
| ⚙ | 演出のオン／オフ、戦闘速度、データ初期化 |

課金機能はありません（花玉の表示のみ）。

## ディレクトリ

```
src/
  data/        キャラ・台詞・敵・ステージ・任務・花結びの定義（コードと分離）
  core/        画面に依存しない純粋ロジック
    battle/    戦闘エンジン（シードを受け取る純関数）
    gacha.ts   花結び（召喚）
    economy.ts レベル・開花コスト、放置報酬
    game.ts    セーブデータへの操作（レベル上げ・出陣など）
    dialogue.ts 時間帯・ホーム台詞・掛け合い
  state/       Zustand ストア、SaveRepository（保存先の抽象）、セーブ移行
  ui/
    theme/     デザイントークン（tokens.ts → CSS変数）とCSS
    components/ 共通部品（立ち絵、カード、カットイン、花結び演出 など）
    screens/   各画面
  art/         SVG 立ち絵のパーツ（和柄・髪型・武器・紋・レア枠）
tests/         ユニットテスト
docs/art-brief.md  イラスト発注用ブリーフ
```

## データの追加方法

### 剣華を追加する
1. `src/data/characters.ts` の `CHARACTERS` に1件追加します。
   - `hair`（髪型）・`weaponShape`（武器）・`motif`（紋）は既存の種類から選ぶと、SVGの仮立ち絵が自動で描かれます。新しい形を作る場合は `src/art/silhouette.tsx` / `src/art/motifs.tsx` に追加してください。
   - 本番イラストができたら `imageUrl` に画像のパスを入れると差し替わります（例：`public/chars/hisame.png` を置いて `imageUrl: "./chars/hisame.png"`）。
   - 能力値は役割・レアから自動計算されます。個性を出したいときだけ `statMod`（例：`{ spd: 1.1 }`）。
2. `src/data/voices.ts` の `VOICES` に台詞（編成・スキル・勝利・敗北・開花・ホーム・朝昼夜）を追加します。
3. 掛け合いを入れるなら `BANTERS` に追加します（`leader` が編成の先頭のとき、`partner` を所持していれば表示）。
4. `npm test` で台詞の抜けや存在しないキャラへの参照がないか確認できます。

花結びの排出対象はレアごとに自動で入ります。ピックアップは `src/data/banners.ts` の `CURRENT_BANNER` を書き換えます。

### 敵・ステージを追加する
- 敵：`src/data/enemies.ts`（`desc` に特徴文を必ず書く）
- ステージ：`src/data/stages.ts` の `LAYOUTS`（5枠の配置）と `LEVELS`（敵レベル）・`RECOMMENDED`（推奨Lv）
- 開花任務：同ファイルの `TRIALS` / `TRIAL_LEVELS`

### 任務を追加する
`src/data/missions.ts` の `BEGINNER_MISSIONS` に追加します。条件の種類は `MissionCond` を参照してください。

## 設計メモ

- **戦闘は再現可能**：`simulateBattle({ allies, enemies, seed })` は純関数で、同じシードなら必ず同じ結果になります。結果（イベント列）を画面が再生するだけなので、バランス調整やサーバー側での検証にそのまま使えます。
- **保存先の抽象化**：`SaveRepository` を実装すればサーバー同期に差し替えられます（今は `LocalStorageSaveRepository`）。
- **セーブ移行**：`src/state/migrate.ts`。保存形式を変えたら `SAVE_VERSION` を上げ、`MIGRATIONS` に旧→新の変換を1つ足します。
- **デザイントークン**：色・余白・角丸・影は `src/ui/theme/tokens.ts` だけで定義し、起動時に `--k-*` のCSS変数として流し込みます。
- **演出**：スキルカットイン（×2以上で短縮・設定でオフ）、花結び、開花、ホームの時間帯。`prefers-reduced-motion` では動きを省きます。
