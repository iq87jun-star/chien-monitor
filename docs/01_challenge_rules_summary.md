# 成果物① FundedNext「Stellar 2-Step」($100K) 条件要約と確定事項

> 取得日: 2026-05-30 / 対象: FundedNext Stellar 2-Step Challenge, 口座サイズ $100,000, Phase1 進行中。
> 一次ソース（FundedNext Help Center / 公式モデルページ）と複数の二次解説を突き合わせて確定。末尾に出典。

## 1. 数値条件（$100K ベース）

| 項目 | 値 | 金額換算 | 失格/達成ライン |
|---|---|---|---|
| Phase1 利益目標 | +8% | $108,000 到達 | 達成で Phase2 へ |
| Phase2 利益目標 | +5% | $105,000 到達 | 達成で Funded |
| 日次損失上限 (Daily Loss) | 5% | $5,000 | 抵触で**失格** |
| 最大損失上限 (Max Loss) | 10% | フロア $90,000 | 割れば**失格** |
| 最低取引日数 | 5 日 | — | 未達だと目標到達でも不可 |
| 時間制限 | なし | — | 焦って速度を出す必要はない |
| Phase2 残高 | $100,000 にリセット | — | Phase1の余剰益は持ち越さない |

## 2. ドローダウン計算方式（最重要・ロジック反映の根拠）

確定した方式を以下に明記する。EAの全ガードはこの方式に整合させた。

- **日次損失 (Daily Loss)**
  - 基準: **当日開始時点（サーバ時間 00:00）の equity** を起点とする 5%。静的（初期残高基準で $5,000 固定と説明する資料もあるが、より厳しく当日基準でも判定されうるため、EAは「当日開始equity起点」を採用＝**より保守的**）。
  - **00:00 サーバ時間でリセット**。
  - **含み損(未実現PnL)・スワップ・手数料をすべて含む equity ベースでリアルタイム判定**。つまり「ポジションを閉じていなくても、含み損で当日−5%に触れた瞬間に失格」。
  - → EAは毎ティック equity を監視し、**−4%（$4,000）**で当日全決済＋新規停止（規則−5%の手前）。

- **最大損失 (Max Loss)**
  - **静的(static)・残高ベースのフロア $90,000**。利益で切り上がらず、出金で切り下がらない（トレーリングしない）。
  - ただし**ブレ―チ判定は equity ベース**＝含み損を含む live equity が $90,000 に触れた瞬間に失格。
  - → EAは **開始残高比 −8%（equity $92,000）**で全決済＋EA恒久停止（規則−10%の手前）。

> 設計含意: 両規則とも「**含み損を含む equity** で即時判定」かつ「日次は **00:00 サーバ時間** リセット」。
> したがってガードは確定損益ではなく **equity を毎ティック監視**する必要がある（EAはそう実装済み）。

## 3. 手法・運用に関する制約（2025–2026 時点）

- **2分未満の保有トレードがフラグ対象**（Stellar 2-Step, 2025–2026 アップデート）。
  → EAは `InpMinHoldSeconds=150`（2分超）で、TP/トレーリング/ニュース決済が早すぎないよう抑制。ハードガードによる緊急決済のみ例外。
- EA は MT4/MT5 で許可（別途 EA 利用料あり）。cTrader / Match-Trader 不可。本EAは **MT5(.mq5)**。
- CFD 口座では**含み損が日次損失にカウント**され、スワップ・手数料・各種フィーも合算される（→ コストモデル必須）。
- 初回報酬アクセスは 21 日後（Phase通過自体には時間制限なし）。

## 4. 禁止手法（本EAで実装しないもの）

HFT/ティックスキャルピング、レイテンシーアービトラージ、口座間両建て・ヘッジ、コピートレード、マーチンゲール/グリッドの暴走。
→ 本EAは **1銘柄・低頻度（1日最大3回）・1ポジ・固定%リスク・SL必須・ナンピン無し**で、これらに該当しない設計。

## 5. 不確実性についての正直な注記

- 二次ソース間で「日次損失の基準を初期残高固定 $5,000 とするか、当日開始equity基準とするか」に表現差がある。**EAはより厳しい方（当日開始equity基準かつ手前−4%）を採用**しているため、どちらの解釈でも規則違反は起こらない。
- 規約は改定されうる。**運用前に必ず最新の "FundedNext CFDs Challenge Terms" を再確認**し、数値が変わっていれば入力パラメータ（`InpDailyLossLimitPct` 等）を更新すること。

## 出典
- [What rules do I need to follow in the Stellar 2-Step Challenge? — FundedNext Help](https://help.fundednext.com/en/articles/8021076-what-rules-do-i-need-to-follow-in-the-stellar-2-step-challenge)
- [Stellar 2-Step Challenge (CFD) rules — FundedNext Help](https://help.fundednext.com/en/articles/12673362-what-rules-do-i-need-to-follow-in-the-stellar-2-step-challenge-at-fundednext-cfd)
- [Daily Loss Limit vs. Maximum Loss Limit — FundedNext Help](https://help.fundednext.com/en/articles/9941519-daily-loss-limit-vs-maximum-loss-limit)
- [How can I calculate the daily loss limit? — FundedNext Help](https://help.fundednext.com/en/articles/8019811-how-can-i-calculate-the-daily-loss-limit)
- [Stellar Challenge model page — FundedNext](https://fundednext.com/stellar-model)
- [FundedNext Drawdown Rules: Static vs Trailing EOD Explained (2026) — proptradingvibes](https://proptradingvibes.com/blog/fundednext-drawdown-rules)
- [FundedNext Review 2026 — FXEmpire](https://www.fxempire.com/prop-firms/fundednext)
