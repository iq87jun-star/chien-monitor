# 134.【記録+事前登録】間引きDukascopy確認の結果(v4見送り/v7合格)と PD間引き版再校正の登録

## 1. Dukascopy最終確認の結果(ユーザーColab実行・2026-07-11・印字転記)

出所: `notebooks/prune_dukascopy_check.ipynb`(全ペア dukascopy_h1→D・Yahoo補完なし)。
JSON: ユーザーDrive `forex_ml/prune_dukascopy_check.json`。

| 仮説 | Dukascopy判定 | フル→間引きSharpe | 決定 |
|---|---|---|---|
| H24a v4 9→6 | **見送り** | 0.83 → 0.80(d1✗) | **現行9ペア維持** |
| H24b v7 3→2 | **合格** | 0.66 → **0.76**(d1✓・USDJPY最下位0.29=d2✓) | **2クロス化を採用**(デモ経由) |

- v4の解剖: Yahooの「負け3ペア」のうちGBPUSDはDukascopyでSh 0.67(9ペア中上位)、
  逆にYahooで生き残ったGBPJPYがDukascopyでは最下位(0.14)。**Yahoo OHLCのSL/TP再現差が
  銘柄別成績を歪めていた**と確定 — docs/132 §3-1の留保どおりで、docs/131 §4の
  「Dukascopy再確認までは実装しない」という事前規則が誤実装を防いだ。
- v7はデータ源に依らずUSDJPYが最弱で一致(Yahoo 0.29 / Dukascopy 0.29)=**構造的**。
- E5 4→2は26年耐久まで合格済み(docs/132 §2)・PortfolioE v2として確定済み(docs/133)。

## 2.【事前登録】PD間引き版(v7 2クロス+E5 2資産・v4/E-Monは現行)の倍率再校正

- 構成: v4 30%(9ペア・現行) / v7 25%(**EURJPY+GBPJPY**) / E-Mon 25%(現行) / E5 20%(**XAUUSD+NAS100**)
- 方法: `median3_calibrate_compare` の日次ブロックMC(2万パス・FN P1 +8%・fail優先・シード7)を
  **逐語再利用**し、現行PD構成と間引きPD構成を同じ土俵で「中央3ヶ月」へ倍率校正して比較。
  実行: `research/portfolio_D_pruned_recalib.py` → `results/portfolio_D_pruned_recalib.json`
- 決定規則(固定): 間引き版の**失格%(楽観・悲観とも)が現行版以下**なら採用
  (同速度でテール改善が間引きの唯一の目的)。悪化するなら見送り=現行PD維持。
- EA入力換算(採用時・固定):
  - `InpYenSymbols=EURJPY,GBPJPY` + `InpV7ShotsPerWeek=8`(4時刻×2ペア=総週次リスク1.95%を維持)
  - `InpE5Symbols=XAUUSD,NAS100` + E5レッグσは**2倍**(4→2レッグの合成スケール維持・docs/133 §3)
  - 4本のリスク入力に **倍率比(間引き校正÷現行校正)** を一律適用
- 適用先: **次のチャレンジ口座/資金化後口座のみ**。走行中のFN P1残り・P2口座は変更しない。
