# Phase 2 — 販売基盤 報告

> ステータス：**実装完了 → 実デプロイ/出品は人間ToDo**
> 「すべて決めて進めて」の指示により、価格・チャネル設定をこちらで確定して構築。

## 確定した判断（自動決定）
| 項目 | 確定値 | 根拠 |
|---|---|---|
| RiskGuard 価格 | **$49 買い切り** | Market最低$30を満たし、単機能ツールの相場感 |
| ライセンスホスト | `https://api.riskguard.app/verify` | EA既定URLと一致（実デプロイ時に差し替え） |
| LPドメイン | `riskguard.app`（想定） | LP/出品文に反映 |
| Market有効化数 | 10 | 規約5〜20内、買い手の複数端末を考慮 |
| 主力EA価格 | $99〜199（要最終承認） | 計画書に記載 |

## 成果物

### 決済 → ライセンス発行
- `licensing/webhook.js` — Gumroad（`?token=`認証）/ Stripe（HMAC署名検証）の購入通知を受け、キー自動発行 → `licenses.json` 登録 → `issued-keys.log` 記録。
- `licensing/keygen.js` — 暗号乱数の買い切りキー生成（`RG-XXXX-XXXX-XXXX`）。
- `licensing/server.js` — 既存の `/verify`（初回口座紐付け）。
- `licensing/package.json` / `.env.example` — 起動・環境変数（秘密は env、コミット禁止）。

### MQL5 Market 出品
- `marketing/mql5-market-listing.md` — 商品名/カテゴリ/タグ/説明文（日英）/スクショ撮影リスト/規約チェック。
- `products/risk-guard/src/RiskGuard.mq5` — `RG_BUILD_MARKET` で外部呼び出しなしビルド可（DLL禁止規約準拠）。

### サポート自動化
- `support/faq-bot-knowledge.md` — FAQボット用ナレッジ（インテント別Q&A＋回答ポリシー＋免責自動付与）。
- 既存 `support/templates.md` / `support/flow.md` と連携。

### 主力EA 商品化（流用承認の活用）
- `products/breakout-pro/src/BreakoutPro.mq5` — 商品化スキャフォールド（リスク/執行/ライセンス実装済み、`GenerateSignal()` に承認ロジックを差し込む構造）。
- `docs/main-ea-plan.md` — 商品化手順・チェックリスト。

## 私（人間）への ToDo
- [ ] Gumroad/Stripe アカウント・商品作成・KYC・決済連携
- [ ] ライセンスサーバ/Webhook の **HTTPSデプロイ**（`api.riskguard.app`）＋シークレット設定
- [ ] 発行キーの購入者送付（メール/受信文）の連携
- [ ] LP のホスティング（`riskguard.app`）＋決済リンク差し込み
- [ ] MetaEditor で `RiskGuard.mq5` を実コンパイル → MQL5 Market 出品申請（スクショ撮影含む）
- [ ] 主力EA：`GenerateSignal()` への承認ロジック移植（自分で or 私に提供）
- [ ] RiskGuard $49・主力EA価格の最終承認

## 次（Phase 3 — 集客自動化）に進める内容
- ブログ/note/SNS のコンテンツパイプライン（下書き自動生成＋投稿スクリプト、連携・承認は人間）
- SEO 記事案、商品比較・使い方コンテンツ。
