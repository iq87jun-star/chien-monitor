# EA / トレード系ツール販売 自動化システム

MQL5/MT5 の EA・インジ・ツールを商品化し、人間の判断・承認だけで回る販売基盤を構築するプロジェクト。

## フェーズ
- **Phase 0（承認済）** — 設計：[docs/phase0-design.md](docs/phase0-design.md)
- **Phase 1（完了）** — MVP：単機能ツール `RiskGuard` 商品化 → [docs/phase1-report.md](docs/phase1-report.md)
- **Phase 2（完了）** — 販売基盤：決済→ライセンス発行・Market出品メタ・サポート自動化・主力EAスキャフォールド → [docs/phase2-report.md](docs/phase2-report.md)
- **Phase 3（完了）** — 集客自動化：SEO記事ドラフト・SNSテンプレ・投稿テキスト生成パイプライン → [docs/phase3-report.md](docs/phase3-report.md)
- **Phase 4（完了）** — 運用最適化：KPI設計・売上集計ツール・デプロイ補助 → [docs/phase4-report.md](docs/phase4-report.md)

## 👤 オーナー作業手順書（最重要）
私が作れない＝あなたにしかできない作業を実行順にまとめた **[docs/owner-action-runbook.md](docs/owner-action-runbook.md)** を参照（MT5コンパイル / 出品 / 決済・ライセンスデプロイ / 集客 / 計測）。

## 確定方針
- 販売チャネル：**二段構え**（MQL5 Market + 自前LP/Gumroad）
- 課金：**買い切りのみ**（RiskGuard **$49**、主力EA $99〜199 想定）
- 既存EAロジック流用：**全面承認**（`products/breakout-pro` で活用）
- ライセンスホスト（既定）：`https://api.riskguard.app/verify`（実デプロイ時に差し替え）

## ディレクトリ
```
ea-business/
├── docs/                     設計・報告ドキュメント（phase0-2, main-ea-plan）
├── products/
│   ├── risk-guard/           MVP商品（src / manual(ja,en) / reports）
│   └── breakout-pro/         主力EA商品化スキャフォールド
├── licensing/                ライセンス検証 + 決済Webhook発行（買い切り）
├── landing/                  自前LP
├── marketing/                コピー・SEO・Market出品メタ・記事ドラフト(content)・SNS(social)
├── support/                  サポートテンプレ・対応フロー・FAQボットKB
├── analytics/                KPI設計・売上CSV置き場（gitignore）
└── scripts/                  バックテスト資料生成・SNS投稿生成・売上集計
    licensing/deploy/          Docker/Caddy デプロイ一式（自動HTTPS）
```

## コンプライアンス（全成果物共通）
利益保証・誇大表現の禁止／全資料にリスク開示・免責／各プラットフォーム規約遵守／秘密情報のハードコード禁止／既存稼働EAの無断流用禁止。
