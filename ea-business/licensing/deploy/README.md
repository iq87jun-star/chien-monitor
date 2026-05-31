# ライセンスサーバ デプロイ手順（HTTPS必須）

> MT5 の `WebRequest` は **HTTPS** のホストにしか安全に使えず、購入者はそのURLを許可リストに登録します。よって本番は必ずHTTPS。
> 秘密情報（`.env`）はコミットしない。

## 構成
- `Dockerfile` — Node22 イメージ（秘密は焼かない／`/data` にライセンスストア）
- `docker-compose.yml` — `verify`(8080) と `webhook`(8090) を起動、named volume で永続化
- `Caddyfile` — 自動HTTPSのリバースプロキシ（`api.riskguard.app`）

## 手順（あなたの作業）
1. **DNS**：`api.riskguard.app` の A/AAAA をサーバIPに向ける。
2. **.env 作成**：`ea-business/licensing/.env.example` を `.env` にコピーし値を設定
   - `GUMROAD_PING_TOKEN`（任意の長い文字列。Gumroad側URLの`?token=`と一致させる）
   - `STRIPE_WEBHOOK_SECRET`（Stripeダッシュボードの Webhook 署名シークレット `whsec_...`）
   - `LICENSE_MAX_BINDINGS`（既定2＝購入者の端末数）
3. **起動**：
   ```bash
   cd ea-business/licensing/deploy
   docker compose up -d --build       # verify:8080 / webhook:8090
   caddy run --config Caddyfile       # 別プロセス or systemd で常駐
   ```
4. **疎通確認**：
   ```bash
   curl https://api.riskguard.app/health        # {"ok":true}
   ```
5. **決済側の登録**：
   - Gumroad：Product > Settings > **Ping** に `https://api.riskguard.app/webhook/gumroad?token=＜GUMROAD_PING_TOKEN＞`
   - Stripe：Developers > Webhooks > Add endpoint `https://api.riskguard.app/webhook/stripe`、イベント `checkout.session.completed`（または `payment_intent.succeeded`）。署名シークレットを `.env` に設定。
6. **キー送付**：発行キーは `/data/issued-keys.log` に記録される。購入者への送付は
   - Gumroad：商品の「Content / receipt」で案内、またはログを見て手動送付（MVP）。
   - 将来：メール送信を webhook に追加（私が実装可）。

## 動作テスト（本番前）
```bash
# ローカルでverifyを起動して紐付けを確認
cd ea-business/licensing && cp .env.example .env
npm run keygen                       # テストキー生成
node -e "import('./keygen.js')"      # 動作確認
# verify をローカル起動し、EA(self build)からキー＋口座で検証
```
