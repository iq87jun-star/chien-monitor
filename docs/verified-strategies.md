# 検証済み戦略台帳(原本突合済み)

**突合日**: 2026-07-03
**原本**: Google Drive(Colabノートブック+結果JSON)および Notion「1000万円ロードマップ v2 — ポートフォリオ最適化 (2026-06-11)」
**文脈**: FundedNext 等プロップチャレンジ向け MT5 EA ポートフォリオ。評価は v7standard 9ゲート
(G1 10年 / G2 no-lookahead+コスト / G3 permutation×Bonferroni / G4 プラセボ / G5 jackknife /
G6 IS-OOS / G7 walk-forward / G8 コスト感度 / G9 DD適合)。

## コア戦略(ポートフォリオ配備済み)

| 戦略 | 機序 | 市場・頻度 | 判定 | 原本 |
|---|---|---|---|---|
| **v4** | 日次平均回帰 | FXメジャー・日次 | 検証済み(Dukascopy再検証済み)| `v4_revalidation_dukascopy.json` |
| **v7** | JPY週初(月曜)効果 | JPYペア・日次 | STRONG-LEAD(net+29%/10y, Sharpe0.78, maxDD-6.2%, perm_p0.007。曜日プラセボ: Mon のみ有意) | `validate_all_v7standard.json` |
| **v9** | v7派生(保有期間変更版) | JPYペア・日次 | STRONG-LEAD(net+17.9%, Sharpe0.76, maxDD-5.0%) | 同上・`v9_holdcompare_validation.json` |
| **E5** | クロスアセット月次モメンタム | 金・株指数・暗号資産等・月次 | STRONG-LEAD(WF5/5)。**逆ボラ正規化拡張版(+BTC/WTI/TLT)へ差し替え推奨**(Dukascopy確認条件付き) | `validate_all_v7standard.json`・`e5_basket_expansion` |
| **E-Mon** | 曜日季節性(月曜) | 株指数・日次 | STRONG-LEAD(net+87%/10y, maxDD-14.9%) | `parallel_emon_notebook.json` |

**配分(2026-06-11 正式化)**: max_calmar — v7 .24 / v4 .43 / E5 .04 / E-Mon .29。
**口座構成**: Book A = v4+v7 / Book B = E-Mon+E5(2口座ジョイントMCで両損0%・Pass≥1 96.4%)。

## 採用済みオーバーレイ

| オーバーレイ | 内容 | 判定 | 原本 |
|---|---|---|---|
| **S-Jul** | 月季節性(7月) | 常設(Book B)。これでPass率は飽和(≈96.5%) | ロードマップv2 |
| **FOMCドリフト** | FOMC前日ドリフト(US500) | **ADOPT(6/6ゲート)**。perm_p0.005, n=79 | `edge12_indices_gold_h1.json` |
| **ToM** | 月末月初 株指数LONG | **保留** — Pass率寄与ゼロだが Calmar 2.08→2.63 改善。ファンド獲得後の小サイズ常設候補(Dukascopy+デモ確認待ち) | ロードマップv2 P2 |

## 既知の弱点・運用ゲート

- v7 / v9 / E5 は 9ゲート中 **G3(Bonferroni)/ G5(Jackknife)未達**のSTRONG-LEAD。デモ・フォワードで埋めるまで本番ロット据え置き。
- サーキットブレーカー既設: 3連敗→翌日停止(-25%ロット)/ 5連敗→1週間停止 / DD-10万→ロット半減 / DD-20万→全停止。
- **P4分析の結論**: 到達速度の律速は口座多重化(N)。新規EA探索より並走数増加が効く。
- **試行回数カウンタ運用中**: `trial_counter.json`(多重検定の管理)。

## 用語対応

- 「検証済み5本」= v4・v7・v9・E5・E-Mon(配備4本+v9)。
- 「F2の教訓」該当事項(原本より): 符号反転プラセボは「平均が正なら自動的にp≈0」になる欠陥があり
  **循環シフト(シグナル↔リターン整合破壊)200本**に刷新済み。プラセボはこの方式を標準とする。
