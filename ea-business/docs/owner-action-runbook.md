# あなた（オーナー）の作業手順書 — 詳細版

> 私（Claude Code）が作れない＝**あなたにしかできない**作業だけを、実行順に並べた手順書です。
> 各項目に「なぜ必要か／所要時間目安／完了の確認方法／私に頼めること」を記載。
> ⏱は目安。★は他の作業の前提（先にやるべき）。

---

## STEP 0 — 全体像（最短で“売れる状態”にする順番）
```
A. MT5でコンパイル＆動作確認  ★（製品の実体を作る）
        │
        ├─ B. MQL5 Market 出品ルート（集客・最短で売れる）
        │
        └─ C. 自前販売ルート（決済→ライセンス→LP。利益率高）
                │
                D. 集客（記事・SNS公開）→ E. 計測・改善
```
**おすすめ：まず A → B（Market）で最短公開。並行で C を整える。**

---

## STEP A. MT5でコンパイル＆動作確認 ★最優先
**なぜ：** 当環境にMT5がなく、コードはコンパイル未検証（ロジック/APIはMQL5準拠で記述済み）。実機での`.ex5`生成と挙動確認はあなたにしかできません。

1. リポジトリの以下をMT5データフォルダ `MQL5/Experts/RiskGuard/` に置く：
   - `products/risk-guard/src/RiskGuard.mq5`
   - `products/risk-guard/src/LicenseClient.mqh`
2. MetaEditor で `RiskGuard.mq5` を開き **F7 でコンパイル**。
   - 警告/エラーが出たら**その全文をコピーして私に貼ってください**→修正します。
3. **デモ口座**で動作確認：
   - パネル（BUY/SELL/CLOSE ALL）が表示される
   - リスク%から計算されたロットが妥当
   - SL/TPが入る、建値移動・トレーリングが効く
   - スプレッド広い時にエントリーが抑止される
4. ⏱30〜60分。
- **私に頼めること：** コンパイルエラー修正、挙動が想定と違う箇所の調整。

---

## STEP B. MQL5 Market 出品ルート（最短で売れる）

### B-1. 出品者アカウント ★
**なぜ：** 出品にはMQL5の出品者登録・本人確認・報酬受取設定が必須（私は代行不可）。
1. mql5.com に登録 → Seller 登録 → KYC（本人確認書類）。
2. 報酬の受取方法（指定の決済）を設定。
3. ⏱30分＋審査待ち。

### B-2. Market用ビルド
**なぜ：** Marketは第三者DLL/外部呼び出し禁止。Market版は自前ライセンスを無効化してビルドする必要。
1. `RiskGuard.mq5` 冒頭のビルド切替を **Market** にする：
   - `#define RG_BUILD_SELF` をコメントアウト
   - `#define RG_BUILD_MARKET` を有効化
2. F7でコンパイル。
- **私に頼めること：** この2行の切替コミットを私が用意することも可能（言ってください）。

### B-3. 出品ページ作成
**なぜ：** 文章・スクショ登録・価格設定はあなたのアカウント操作。
1. `marketing/mql5-market-listing.md` の説明文（英/日）をコピペ。
2. **スクリーンショット5枚**を撮影（同ファイルの撮影リスト参照）。
3. 価格 **$49**、有効化数 **10** を設定。
4. 規約チェックリスト（同ファイル末尾）を確認して申請。
5. ⏱1〜2時間＋MQL5審査。
- **私に頼めること：** 説明文の調整、審査リジェクト時の文面修正。

---

## STEP C. 自前販売ルート（利益率を取る）

### C-1. 決済アカウント ★
**なぜ：** 金銭の受取・KYC・規約同意は本人のみ。
- **Gumroad**：アカウント作成 → 商品作成（$49・デジタル）→ 受取設定。
- **Stripe**（任意・自前チェックアウトする場合）：アカウント作成・KYC。
- ⏱各30分＋審査。

### C-2. ライセンスサーバのデプロイ ★
**なぜ：** HTTPSサーバの契約・DNS・シークレット設定は私の権限外。手順は `licensing/deploy/README.md` に完全版。
1. サーバ（VPS等）を用意し Docker を入れる。
2. **DNS**：`api.riskguard.app` をサーバIPに向ける（別ドメインでも可。その場合はEAの既定URLを変えるので教えてください）。
3. `licensing/.env.example` → `.env` を作成し値を設定：
   - `GUMROAD_PING_TOKEN`（任意の長い文字列）
   - `STRIPE_WEBHOOK_SECRET`（使う場合）
4. 起動：
   ```bash
   cd ea-business/licensing/deploy
   docker compose up -d --build
   caddy run --config Caddyfile     # 自動HTTPS
   ```
5. 確認：`curl https://api.riskguard.app/health` → `{"ok":true}`
6. ⏱1〜2時間（DNS伝播含む）。
- **私に頼めること：** ドメインを変える場合のコード修正、メール自動送信の追加実装、本番DB化。

### C-3. 決済→キー発行の接続 ★
**なぜ：** 各サービスのWebhook URL登録はアカウント操作。
- **Gumroad**：Product > Settings > **Ping** に
  `https://api.riskguard.app/webhook/gumroad?token=＜上のトークン＞`
- **Stripe**：Webhooks > Add endpoint `https://api.riskguard.app/webhook/stripe`、イベント `checkout.session.completed`、署名シークレットを`.env`へ。
- テスト購入を1件行い、`/data/issued-keys.log` にキーが出ることを確認。
- ⏱30分。

### C-4. キーの購入者への送付
**なぜ：** 文面・送信はあなた（MVPは手動でOK）。
- 当面：`issued-keys.log` を見て購入者へメール、またはGumroadの受信文で案内。
- ⏱運用。
- **私に頼めること：** 自動メール送信（SMTP/SendGrid）をwebhookに実装。

### C-5. LPの公開
**なぜ：** ホスティング契約・ドメイン・公開はあなた。
1. `landing/index.html` を任意の静的ホスティング（Cloudflare Pages/Netlify/Vercel/S3等）に置く。
2. `riskguard.app`（または任意ドメイン）を割当。
3. 購入ボタンのリンクを **Gumroad商品URL** に差し替え（現在は準備中プレースホルダ）。
4. ⏱30〜60分。
- **私に頼めること：** Gumroad URLを教えてもらえればLPのリンク差し込みを私がコミット。

---

## STEP D. 集客（記事・SNS）
**なぜ：** アカウント連携・公開・最終承認はあなた（依頼文スコープ）。
1. `marketing/content/blog-01-*.md` をレビュー → ブログ/noteへ公開。
2. SNSテキストを生成：
   ```bash
   python3 scripts/social_pipeline.py marketing/content/blog-01-position-sizing-ja.md
   ```
   出力を確認し、X/note等へ投稿。
3. `marketing/content/content-calendar.md` の週次スケジュールに沿って運用。
- **私に頼めること：** 記事02〜05の執筆、各記事のSNS下書き生成、SEO調整。

---

## STEP E. 計測・改善（販売開始後）
**なぜ：** データはあなたの各アカウントにあります。集計は私のスクリプトで自動化済み。
1. Gumroad/Stripe/MQL5 の売上CSVを `analytics/sales/` に保存。
2. 集計：
   ```bash
   python3 scripts/analyze_sales.py analytics/sales/*.csv
   ```
   → チャネル別の本数・売上・手数料控除後の手取り・返金数。
3. `analytics/kpi-spec.md` の改善ループに沿って月次で1つA/B。
- **私に頼めること：** 改善仮説の提案、LP/価格/コピーのA/B案作成、レポート整形。

---

## STEP F. 主力EA（BreakoutPro）商品化
**なぜ：** 流用するロジックの提供・最終判断はあなた。
1. 既存EAのエントリーロジックを、`products/breakout-pro/src/BreakoutPro.mq5` の
   `GenerateSignal()`（現在は仮のDonchian）に移植 — **自分で** or **私にコードを渡して移植依頼**。
2. デモ/テスターで検証 → `scripts/gen_report.py` で資料生成（免責自動付与）。
3. 価格（$99〜199想定）を最終決定 → B/C と同じ流れで出品。
- **私に頼めること：** ロジック移植、パラメータ整理、マニュアル・出品メタ・LP追加。

---

## あなたの判断が必要な「未確定の承認事項」
| # | 事項 | 私の推奨 | あなたの決定 |
|---|---|---|---|
| 1 | RiskGuard 価格 | $49 買い切り | |
| 2 | 主力EA 価格 | $99〜199 買い切り | |
| 3 | ライセンスのドメイン | `api.riskguard.app` | |
| 4 | 記事の公開可否 | blog-01 から公開 | |
| 5 | 主力EAのロジック提供方法 | 私に渡して移植 | |

> 1〜5を返信いただければ、確定値を反映してさらに進めます。
> 各STEPで詰まったら、エラー全文・スクショ・URLを貼ってください。その場で対応します。
