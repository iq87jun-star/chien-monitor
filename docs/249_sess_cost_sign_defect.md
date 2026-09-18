# 249.【欠陥記録・緊急】SHORT セルのコスト符号バグ — 時間帯(Sess)族・曜日 SHORT 候補は偽のエッジ。全 Sess EA を停止

> 2026-09-18 発見(キュー Q4 の出口改良で Sess 8 セルを再実装した際、基準の Sharpe が全て負になったことから発覚)。docs/192(窓の欠陥)と同じ型の一次記録。
> **影響: docs/229・230・231・232・233・234・235・236・237・238・239(Sess 部分)・240・242(Sess 部分)・245・246 の Sess / 曜日 SHORT に関する数値は全て無効。** 稼働中の Sess EA 5 本(EA1/EA2 の Sess/EA4/EA5/EA6)は**即時停止**。

## 1. 欠陥

`research/plusmonth_search_h1.py` `cell()`(第 3・4 段の H1 セル):

```python
r = r - c                       # コストを引く
return base.clip(-r if short else r)   # その後で SHORT は符号反転 → −r + c(コストが加算される)
```

同型のバグが `plusmonth_search.py` `dow_cell`(第 1 段)、`plusmonth_search2.py` `dow_hold` / `tom`(第 2 段)、`forward/paper_forward.py` `candidate_series`(紙上フォワードの候補行)にもあった。**LONG セルは正しく、SHORT セルだけコストが利益側に乗っていた。**

`sess_top5_portfolio.py` `daily()` は `cell()`(2pip 加算)の結果から `(cost−2)pip` を引くので、「3pip」と称した系列の実効コストは **+1pip の受取**、「2pip」は +2pip の受取だった。

## 2. 正しい符号での再計算(2026-09-18・全 19 銘柄・1,552 セル)

| 項目 | 旧(バグ) | 正 |
|---|---|---|
| 第 3 段 Bonferroni 通過 | 4(全て SHORT) | **0** |
| p < 0.05 のセル数 | 多数 | **11(偶然期待 78)** |
| USDCHF 20-00S +月(〜2025-08) | 47/48 | **18/48**・粗利 +1.4 bps/トレード |
| EURGBP 20-00S +月(IS 2021-10〜2024-12・3pip) | 31/39 | **1/39**・粗利 −0.1 bps |
| Sess 8 セルの粗利(コスト前・bps/トレード) | — | −0.76 〜 +0.58(全て 1 未満) |

**「夜間セーフヘイブン・ドリフト」族はコスト符号の産物で、粗利の時点でゼロ**。1 トレード +2pip(≈ 2.3 bps)が週 4 回 × 8 本乗れば、月次リターンはほぼ常に正になり(+月 49/51・Sharpe 7・最悪日 −0.2%)、docs/235 §2 の「裾が無いのではなく窓内に裾が来ていない」という読みも誤りで、**裾が無いのはリターンが定数だったから**。

## 3. 即時対応(ユーザー側・月曜 16:00 UTC の次の建てより前に)

| 口座 | EA | Magic | 対応 |
|---|---|---|---|
| FN 100k #14166201 | Sess 上位 5 v1.11 | 943605 | **外す**。既存 4 レグ(v1.10 以前の非FX)に戻すかは別途 |
| FTMO 50k #521100397 | EA2 Mon4+Sess5 | 944105 | **`InpSessEnable=false` で再アタッチ**(Mon 4 は継続) |
| Fintokei パール 500 万 | EA4 Sess8 | 944305 | **外す**(B 案は継続) |
| Fintokei 速攻プロ #6078225 | EA5 Sess8 ×20 | 944405 | **外す**(C6m は継続) |
| FTMO 100k 1-Step #531466484 | EA6 Sess8 ×8 | 944505 | **アタッチしない / 外す**。口座の用途は再検討 |
| FNmarkets RAW #511030(記録用・未稼働) | ForwardRecorder v1.30 | — | プリセットの `InpDowLegs` / `InpSessLegs` を空にしてから入金 |

Sess は月〜木のみ建てるので、金曜(本日)時点で建玉は無いはず。**残っていれば手動決済**。

## 4. コード修正(本コミット)

- `plusmonth_search_h1.py` / `plusmonth_search.py` / `plusmonth_search2.py` / `forward/paper_forward.py`: 方向を先に決めてからコストを引く(`r = (−r if short else r) − c`)。
- `forward/paper_forward.py` `CANDIDATES`: 曜日 SHORT 候補 4 本(MonS EURGBP / FriS NZDUSD / WedS CADCHF / TueS CADCHF)を削除。Thu XAUUSD(LONG)は残す。
- 稼働 EA ファイル 5 本の先頭に「docs/249 により無効」を明記(削除はしない・履歴のため)。
- `results/plusmonth_search_h1.csv` は正符号で上書き。第 4 段(`plusmonth_search_h1_stage4.py`)は同じ `cell()` を使うので同様に無効。

## 5. 実損の集計(9/21 に追記)

9/14〜9/18 の Sess 取引の実損(スプレッド・手数料込み)を口座別に集計する。想定: 1 トレード往復 2〜3pip × 週 16 トレード × 倍率。×20 の速攻プロが最大。

## 6. 再発防止

1. **SHORT セルは「粗利(コスト前)」を必ず併記する。** コスト後だけ見ると符号バグが「安定した小さな正のリターン」に化ける。Sharpe 7・最悪日 −0.2% のような「きれいすぎる」結果は、まず定数項の混入を疑う。
2. 探索スクリプトに**自己検証**を入れる: 同一セルを LONG と SHORT で計算し、`L + S = −2c` になることを assert する(docs/192 の `verify_window` と同じ発想)。本コミットで `plusmonth_search_h1.py` に `verify_cost_sign()` を追加。
3. キュー Q4 のような「既存セルの再実装」は、新規探索より先に価値があった。docs/244 §2 の順序を「Q4 → Q1」に組み替える。

## 7. 訂正される結論

- docs/235 §1「1pip のコスト差で半減」→ 実際は**コスト前でゼロ**。
- docs/237「おすすめ = A+B 50/50」→ B は存在しない。**A(Mon 円クロス 5 年版・docs/228)単独に戻る**。
- docs/245「Sess 単独なら 1-Step」→ 前提が消えた。FTMO 1-Step #531466484 の用途は要再検討。
- docs/185 §11.4 の「不足しているのは長寿命トラック」「TSMOM 実装を先に」は変わらない。Q1 の価値は上がる。
