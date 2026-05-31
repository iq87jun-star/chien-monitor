# RiskGuard ライセンスシステム（自前販売版）

買い切り（永続）ライセンスの最小リファレンス実装。MQL5 Market 版では**不要**（プラットフォームが口座/PC紐付け・有効化を管理）。

## 構成
- `server.js` — `/verify` エンドポイント。EA（`RG_BUILD_SELF`）からの POST を検証。
- `webhook.js` — 決済（Gumroad/Stripe）→ キー自動発行。発行キーは `licenses.json` に登録し `issued-keys.log` に記録。
- `keygen.js` — 買い切りキー生成（`RG-XXXX-XXXX-XXXX`、暗号乱数）。
- `package.json` / `.env.example` — Nodeプロジェクト設定・環境変数雛形。
- EA 側：`products/risk-guard/src/LicenseClient.mqh`（`WebRequest`、DLL不使用）。

## 決済→発行フロー
1. 購入者が Gumroad/Stripe で決済。
2. プロバイダが `webhook.js` に通知（Gumroadは`?token=`、StripeはHMAC署名で検証）。
3. `keygen.js` でキー生成 → `licenses.json` 登録 → `issued-keys.log` に記録。
4. 購入者へキー送付（メール/Gumroad受信。**連携は人間の ToDo**）。
5. EA起動時に `server.js /verify` で口座紐付け・検証。

## 起動
```bash
cp .env.example .env   # 値を設定（秘密はコミットしない）
npm run verify-server  # :8080  /verify
npm run webhook        # :8090  /webhook/gumroad, /webhook/stripe
npm run keygen         # 手動でキー1個発行（テスト用）
```

## 認証フロー（買い切り）
1. 購入時にキー（例 `RG-XXXX-YYYY`）を発行し、ライセンスストアに登録。
2. 購入者が EA に `InpLicenseKey` を入力し起動。
3. EA が `{product,key,account,broker}` を HTTPS POST。
4. サーバはキーを照合し、**初回起動の口座番号に紐付け**（`LICENSE_MAX_BINDINGS` 台まで）。
5. 紐付け済み口座なら `{valid:true}`、超過/不明/失効なら `{valid:false,reason}`。

## 環境変数（秘密はコードに置かない）
| 変数 | 用途 | 既定 |
|---|---|---|
| `PORT` | 待受ポート | 8080 |
| `LICENSE_DB_PATH` | ライセンスストア（本番はDBに差し替え） | `./licenses.json` |
| `LICENSE_MAX_BINDINGS` | 1キーで紐付け可能な口座数（購入者の複数端末用） | 2 |
| `WEBHOOK_PORT` | webhook待受ポート | 8090 |
| `PRODUCT_ID` | 商品ID | risk-guard |
| `GUMROAD_PING_TOKEN` | Gumroad Ping認証トークン（URLの`?token=`と一致） | なし |
| `STRIPE_WEBHOOK_SECRET` | Stripe署名検証シークレット（`whsec_...`） | なし |

## セキュリティ要件
- **HTTPS 必須**（MT5 は WebRequest 許可URLにホスト登録が必要。HTTP運用は不可）。
- `licenses.json` や `.env` は **`.gitignore` 済み**。リポジトリに含めない。
- 本番はファイルではなくマネージドDB＋監査ログを推奨。
- レート制限・不正検知（同一キーの多数口座要求）を本番で追加すること。

## 私（人間）の ToDo
- [ ] サーバのデプロイ先（HTTPS）の用意（`api.riskguard.app` 等。EA既定URLと一致させる）
- [ ] Gumroad Ping / Stripe Webhook のエンドポイント登録＋シークレット設定
- [ ] 発行キーの購入者への送付（メール/Gumroad受信文）の連携
- [ ] 本番DB（ファイル→マネージドDB）への差し替え
