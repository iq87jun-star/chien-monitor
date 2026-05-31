# EA / トレード系ツール販売 自動化システム

MQL5/MT5 の EA・インジ・ツールを商品化し、人間の判断・承認だけで回る販売基盤を構築するプロジェクト。

## フェーズ
- **Phase 0（承認済）** — 設計：[docs/phase0-design.md](docs/phase0-design.md)
- **Phase 1（進行中）** — MVP：単機能ツール `RiskGuard` の商品化（コード＋マニュアル＋LP＋ライセンス）→ [docs/phase1-report.md](docs/phase1-report.md)
- Phase 2 — 販売基盤（ライセンス・決済・サポート整備）
- Phase 3 — 集客自動化（コンテンツ／SNS）
- Phase 4 — 運用最適化

## 確定方針（2026-05-31 承認）
- 販売チャネル：**二段構え**（MQL5 Market + 自前LP/Gumroad）
- 課金：**買い切りのみ**
- 既存EAロジック流用：**全面承認**（Phase 2 以降の主力EAで活用）

## ディレクトリ
```
ea-business/
├── docs/                     設計・報告ドキュメント
├── products/risk-guard/      MVP商品（src / manual(ja,en) / reports）
├── licensing/                自前ライセンスサーバ（買い切り・WebRequest）
├── landing/                  自前LP
├── marketing/                セールスコピー・SEO
├── support/                  サポートテンプレ・対応フロー
└── scripts/                  バックテスト資料 自動生成
```

## コンプライアンス（全成果物共通）
利益保証・誇大表現の禁止／全資料にリスク開示・免責／各プラットフォーム規約遵守／秘密情報のハードコード禁止／既存稼働EAの無断流用禁止。
