# EA / トレード系ツール販売 自動化システム

MQL5/MT5 の EA・インジ・ツールを商品化し、人間の判断・承認だけで回る販売基盤を構築するプロジェクト。

## フェーズ
- **Phase 0（承認済）** — 設計：[docs/phase0-design.md](docs/phase0-design.md)
- **Phase 1（完了）** — MVP：単機能ツール `RiskGuard` 商品化 → [docs/phase1-report.md](docs/phase1-report.md)
- **Phase 2（完了）** — 販売基盤：決済→ライセンス発行・Market出品メタ・サポート自動化・主力EAスキャフォールド → [docs/phase2-report.md](docs/phase2-report.md)
- **Phase 3（次）** — 集客自動化（コンテンツ／SNS）
- Phase 4 — 運用最適化

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
├── marketing/                セールスコピー・SEO・Market出品メタ
├── support/                  サポートテンプレ・対応フロー・FAQボットKB
└── scripts/                  バックテスト資料 自動生成
```

## コンプライアンス（全成果物共通）
利益保証・誇大表現の禁止／全資料にリスク開示・免責／各プラットフォーム規約遵守／秘密情報のハードコード禁止／既存稼働EAの無断流用禁止。
