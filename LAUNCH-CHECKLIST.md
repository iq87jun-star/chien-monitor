# 新サイト5本 立ち上げ手作業チェックリスト

対象: cosme(cosme-press.com)/ pokeca(pokeca.tokyo・ドメイン取得済み)/
opcg(opcg-souba.com)/ duema(duema-souba.com)/ gunpla(gunpla-souba.com)

所要時間の目安: 合計1.5〜2時間(フェーズごとに分けて実施可)。
費用: ドメイン4本 合計4,000〜6,500円/年 程度。
毎朝のRoutine「新サイト立ち上げ監視」がこのリストの進捗を自動検査して報告する。

## フェーズ0: PRマージ(5分・最初にやる)

- [ ] GitHub で `claude/domain-search-monetization-alc402` → `main` のPRを作成してマージ
  (Claudeに「PRを作成して」と頼んでもよい。マージ判断のみ人間の作業)

## フェーズ1: ドメイン取得(10分・お名前.com)

- [ ] cosme-press.com を取得
- [ ] opcg-souba.com を取得
- [ ] duema-souba.com を取得
- [ ] gunpla-souba.com を取得

手順(4つとも同じ):
1. お名前.com で検索 → **標準価格(1,000〜2,000円/年)であることを確認**。
   プレミア価格(数万円)表示なら買わずに相談
2. オプションは「Whois情報公開代行(無料)」のみチェック。サーバー等の抱き合わせは全部不要
3. 購入後に届く**ドメイン情報認証メールのリンクを必ずクリック**(2週間以内)
- [ ] pokeca.tokyo の認証メールもクリック済みか確認(8/21取得分)

## フェーズ2: 楽天アプリID(10分・無料・1回だけ)

- [ ] [Rakuten Developers](https://webservice.rakuten.co.jp/) に楽天会員でログイン
  → アプリ新規作成(アプリ名例: souba-monitor、URL: https://pokeca.tokyo/)
  → 発行された **applicationId(数字20桁)** を控える
- [ ] [楽天アフィリエイト](https://affiliate.rakuten.co.jp/)で **アフィリエイトID** を控える(収益化に必要)
- [ ] GitHub → chien-monitor → Settings → Secrets and variables → Actions →
  New repository secret で2つ登録:
  - `RAKUTEN_APP_ID` = applicationId
  - `RAKUTEN_AFFILIATE_ID` = アフィリエイトID
  (この2つだけで cosme / pokeca / opcg / duema / gunpla 全サイトに共通適用される)

## フェーズ3: 公開リポジトリとデプロイ設定(25分)

- [ ] GitHubで**公開・空**リポジトリを5つ作成(README等は追加しない):
  `cosme-press` / `pokeca-tokyo` / `opcg-souba` / `duema-souba` / `gunpla-souba`
- [ ] デプロイ用PATに5リポジトリを追加:
  GitHub → Settings(個人)→ Developer settings → Personal access tokens →
  Fine-grained tokens → `TORECA_DEPLOY_TOKEN` に使っているトークンを開く →
  Repository access に上の5つを**追加**して保存(トークンの値は変わらないので
  chien-monitor 側のSecrets更新は不要)
- [ ] chien-monitor の Secrets に5つ登録:
  - `COSME_DEPLOY_REPO` = `iq87jun-star/cosme-press`
  - `POKECA_DEPLOY_REPO` = `iq87jun-star/pokeca-tokyo`
  - `OPCG_DEPLOY_REPO` = `iq87jun-star/opcg-souba`
  - `DUEMA_DEPLOY_REPO` = `iq87jun-star/duema-souba`
  - `GUNPLA_DEPLOY_REPO` = `iq87jun-star/gunpla-souba`
- [ ] chien-monitor → Actions タブ → `cosme-auto-update` 〜 `gunpla-auto-update` の
  5つを「Run workflow」で手動実行(初回。以降は自動)
- [ ] 各公開リポジトリ → Settings → Pages:
  Branch = `gh-pages` / (root) → Save → Custom domain に各ドメインを入力
  (gh-pages ブランチは上のワークフロー成功後に現れる)

## フェーズ4: DNS設定(15分・お名前.com)

5ドメインそれぞれ(pokeca.tokyo 含む):
- [ ] お名前.com Navi → ネームサーバー/DNS → DNSレコード設定 → 対象ドメイン選択 →
  **Aレコードを4つ**追加(ホスト名は空欄):
  `185.199.108.153` / `185.199.109.153` / `185.199.110.153` / `185.199.111.153`
- [ ] 反映後(数分〜1時間)、各公開リポジトリの Pages 画面で
  「Enforce HTTPS」にチェック

## フェーズ5: Search Console 登録(25分・サイト表示確認後)

5サイトそれぞれ:
- [ ] [Google Search Console](https://search.google.com/search-console) →
  プロパティ追加(「ドメイン」方式・お名前.comのDNSにTXTレコードを1つ追加して確認)
- [ ] サイトマップ送信: `https://<ドメイン>/sitemap.xml`
- [ ] **pokeca.tokyo だけ追加タスク**: 「リンク」レポートを開き、旧ブログ
  「ポケカミン」時代の残存被リンクを確認(中古ドメイン実験の効果測定データ。
  スクリーンショットをClaudeに渡せば分析します)

## 任意(急がない)

- [ ] X bot用アカウント作成+API キー登録(各サイトREADME参照)
- [ ] AdSense 申請(データが数週間貯まりサイトの体裁が整ってから)
- [ ] 各サイトの og.png 作成(OGP画像)
- [ ] GA4 計測タグ追加(toreca/duel と同様の対応)

---
完了判定はRoutineが毎朝自動チェックし、全サイト稼働を確認したら監視を自動終了する。
