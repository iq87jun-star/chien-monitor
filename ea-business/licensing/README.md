# RiskGuard ライセンスシステム（自前販売版）

買い切り（永続）ライセンスの最小リファレンス実装。MQL5 Market 版では**不要**（プラットフォームが口座/PC紐付け・有効化を管理）。

## 構成
- `server.js` — `/verify` エンドポイント。EA（`RG_BUILD_SELF`）からの POST を検証。
- EA 側：`products/risk-guard/src/LicenseClient.mqh`（`WebRequest`、DLL不使用）。

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
| `LICENSE_ADMIN_SECRET` | キー発行用の管理シークレット（使う場合のみ・**コミット禁止**） | なし |

## セキュリティ要件
- **HTTPS 必須**（MT5 は WebRequest 許可URLにホスト登録が必要。HTTP運用は不可）。
- `licenses.json` や `.env` は **`.gitignore` 済み**。リポジトリに含めない。
- 本番はファイルではなくマネージドDB＋監査ログを推奨。
- レート制限・不正検知（同一キーの多数口座要求）を本番で追加すること。

## 私（人間）の ToDo
- [ ] サーバのデプロイ先（HTTPS）の用意
- [ ] 決済（Gumroad/Stripe）→ キー発行の連携（Webhook）
- [ ] 本番DBの選定
