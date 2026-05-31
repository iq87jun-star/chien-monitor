# Phase 4 — 運用最適化 報告

> ステータス：**計測基盤・分析ツール構築完了 → 実データ投入はオーナー作業**

## 方針
販売開始後の数値で改善を回す。データはオーナーの各アカウント（MQL5/Gumroad/Stripe/LP解析）にあるため、私は**集計・分析の自動化**と**改善ループの設計**を提供。

## 成果物
- `analytics/kpi-spec.md` — 見るべきKPI、データソース、月次改善ループ、A/B候補、コンプラ。
- `scripts/analyze_sales.py` — チャネル別の本数/売上/**手数料控除後の手取り**/返金数を集計。
  - 手数料モデルは実確認済みの2026レート（MQL5 20%、Gumroad 10%+$0.50、Stripe 2.9%+$0.30、BOOTH 5.6%+flat）。
  - 動作確認済み（サンプルCSVで集計表を出力）。
- `analytics/sales/` — CSV置き場（**gitignore済み＝顧客データはコミットしない**）。

## デプロイ補助（販売基盤の実行を容易化）
- `licensing/deploy/Dockerfile` `docker-compose.yml` `Caddyfile` `README.md`
  - verify(8080)/webhook(8090) をコンテナ起動、Caddyで自動HTTPS、`/data`に永続化、秘密はimageに焼かない。

## オーナー向け統合手順書
- `docs/owner-action-runbook.md` — **あなたにしかできない作業**を実行順に詳細化（STEP A〜F＋未確定の承認5件）。

## オーナーToDo（要点）
- 売上CSVを `analytics/sales/` に置く → `analyze_sales.py` で集計。
- `kpi-spec.md` の改善ループに沿って月次で1つA/B。
- 詳細は `owner-action-runbook.md` STEP E。
