# Phase 3 — 集客自動化 報告

> ステータス：**パイプライン構築完了 → 投稿は人間（アカウント連携・最終承認）**

## 方針
コンテンツ生成〜投稿用テキスト化までを自動化し、**アカウント連携と投稿は人間**が行う（依頼文スコープ）。全コンテンツに免責を自動付与、利益保証・誇大表現は禁止。

## 成果物
### SEOコンテンツ（ドラフト）
- `marketing/content/blog-01-position-sizing-ja.md` / `-en.md`
  - front matter（title/keywords/status）付き。`status: draft → 人間承認 → publish`。
  - 末尾に免責、CTA（RiskGuard $49）コメント。
- `marketing/content/content-calendar.md` — 記事ストック（5本）＋週次投稿スケジュール＋ルール。

### SNS
- `marketing/social/templates.md` — X/note 用テンプレ（日英）＋共通免責。

### 自動化スクリプト
- `scripts/social_pipeline.py` — ドラフトMarkdown→X/note用テキストを生成。
  - front matter解析、言語自動判定、**免責を強制付与**、X文字数チェック（280）。
  - **投稿はしない**（生成のみ）。動作確認済み（ja 84字 / en 247字）。

## 運用フロー
```
記事ドラフト生成（Claude）→ 人間レビュー/承認 → social_pipeline.py で各媒体テキスト生成
 → 人間がアカウント連携・投稿 → 反応を見て次記事へ
```

## 私（人間）への ToDo
- [ ] X / note / ブログのアカウント連携・運用先決定
- [ ] ドラフト記事のレビュー・公開可否
- [ ] 投稿（手動 or 連携ツール）。自動投稿APIを使う場合は連携情報の設定

## 次（Phase 4 — 運用最適化）
- 売上・流入・CVの計測設計（どの数値を見るか）
- A/BするLP要素・価格・コピーの候補出し
- 数値に基づく改善提案（販売後のデータが前提）
