# Phase 1 — MVP 報告：RiskGuard

> ステータス：**初版実装完了 → レビュー/承認待ち**
> 商品：`RiskGuard`（MT5・リスク%ベースのロット計算＋トレード執行/管理アシスタント・買い切り）

---

## 1. 成果物

### A. 商品コード
- `products/risk-guard/src/RiskGuard.mq5` — 本体EA
  - リスク%／固定ロットのロット自動計算（銘柄スペック・SL幅から算出）
  - SL（pips）＋ R倍TP のワンクリック発注（BUY/SELL/CLOSE ALL パネル）
  - ブレイクイーブン・トレーリング・スプレッドガード
  - 3桁/5桁クォート対応、CTrade 使用、マジック識別
  - **2系統ライセンス切替**（`RG_BUILD_MARKET` / `RG_BUILD_SELF`）
- `products/risk-guard/src/LicenseClient.mqh` — ライセンス層
  - Market版：no-op（プラットフォーム管理、外部呼び出しなし＝DLL禁止規約に準拠）
  - 自前版：`WebRequest`（DLL不使用）で買い切りキーを検証

### B. ドキュメント（日英）
- マニュアル `manual/manual-ja.md` `manual-en.md`
- セットアップ `manual/setup-ja.md` `manual-en.md`
- FAQ `manual/faq-ja.md` `faq-en.md`
- すべてに**リスク開示・免責**を明記

### C. 販売基盤の素地
- 自前LP `landing/index.html`（日英・コンプラ免責入り）
- ライセンスサーバ参照実装 `licensing/server.js` ＋ `licensing/README.md`
  - 買い切り＝初回起動口座に紐付け（`LICENSE_MAX_BINDINGS` 台まで）
  - 秘密は環境変数、`licenses.json`/`.env` は `.gitignore` 済み

### D. マーケ／サポート／自動化
- セールスコピー＆SEO `marketing/risk-guard-copy.md`（日英）
- サポートテンプレ `support/templates.md`・対応フロー `support/flow.md`
- バックテスト資料の自動生成 `scripts/gen_report.py`（免責文を強制挿入）

---

## 2. 私（あなた＝依頼者）への確認事項
1. **商品コンセプトの妥当性**：MVPを「RiskGuard（リスク%ロット計算＋トレード管理）」とした方針でよいか？別の単機能ツールが良ければ差し替えます。
2. **価格**：買い切りの想定価格（例 $39 / $49）。MQL5 Marketは**最低$30**。
3. **MQL5 Market 出品**：Market版でビルド（`RG_BUILD_MARKET`）して出品申請を進めてよいか。
4. **自前LP公開先**：ドメイン/ホスティング（決め次第ライセンスURLを確定）。

## 3. 次の ToDo
### 私（人間）
- [ ] 上記コンセプト・価格の承認
- [ ] MQL5 出品アカウント／自前決済（Gumroad/Stripe）の用意・KYC
- [ ] LPのホスティング先・ドメイン、ライセンスサーバのHTTPSデプロイ先
- [ ] MetaEditor で `RiskGuard.mq5` を**実コンパイル**（当環境ではMT5未導入のため未コンパイル）

### あなた（Claude Code）— 承認後 Phase 2
- [ ] 決済→ライセンスキー発行のWebhook連携
- [ ] Market出品メタデータ（説明文・スクショ・カテゴリ）作成
- [ ] FAQボット用ナレッジの最終整形
- [ ] （流用承認済の）主力EA商品化の着手計画

---

## 4. 注意・既知の制約
- 本コードは当実行環境（MT5なし）で**コンパイル検証はしていません**。MetaEditorでのF7コンパイルが必要です。ロジック・API使用は MT5/MQL5 準拠で記述。
- 既存稼働中EAのロジックは本MVPには未使用（RiskGuardは新規・汎用ツール）。
