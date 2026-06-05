# 51. Drive 10年で「比率×倍率」を正式確定するランブック（→ EA予算に直結）

> docs/49 は比率(v7:v4:E5)を最適化した。本書は **比率に加えて倍率(サイズ)も10年Dukascopyで確定**し、
> **Chien_Portfolio4_Optimized にそのまま入れる実予算 v7/v4/E5 %** を出すまでの手順。
> ツール: `research/colab_optimize_portfolio3_10y.py` / `notebooks/optimize_portfolio3_10y.ipynb`。
> 出力: `research/results/optimize_portfolio3_10y.json`。**数字は実行ログのみ**(docs/08規律)。

## 0. なぜ Drive が要るのか（手元だけで確定できない理由）

- 比率の最適化は **各戦略の Sharpe・テール・相関** に依存する。**v7 は Yahoo H1 が〜2年**しか取れず、
  短期サンプルだと **v7のSharpeが過大に出てE5を過小評価**する（手元実行では比率が 55:45:0 等に歪む）。
- docs/49 はこれを **Sharpeを確定10年値にアンカー**して回避し、**CALMAR 40:35:25** を得た。
  本ランブックは **アンカーでなく実10年系列そのもの**で確定する（v7も実10年H1ゆえ歪まない）。
- ⚠ ハーネスは v7系列が **60ヶ月未満なら警告**を出す。警告が出たら**まだ確定でない**＝10年H1を投入して再実行。

## 1. 準備（Drive 配置）

```
MyDrive/forex_ml/
  dukascopy_data_h1/   EURUSD_h1.csv GBPUSD_h1.csv USDJPY_h1.csv AUDUSD_h1.csv
                       USDCHF_h1.csv USDCAD_h1.csv NZDUSD_h1.csv EURJPY_h1.csv GBPJPY_h1.csv
                       (10年, UTC, 列: timestamp,open,high,low,close)
  multiasset_daily/    XAUUSD_d.csv US500_d.csv NAS100_d.csv GER40_d.csv  (無ければYahoo自動取得)
```
- v7/v4 は H1 から（v4 は日足リサンプル）、E5 は多資産日足から再構成（既存 colab と同ロジック）。

## 2. 実行

`notebooks/optimize_portfolio3_10y.ipynb` を Colab で開く →「すべて実行」。Drive をマウント。
（または `python3 research/colab_optimize_portfolio3_10y.py`）。

## 3. 出力の読み方

### (A) 比率最適 — どの比率か
`opt_max_calmar / opt_max_cagr / opt_min_fail / current_40_40_20` を確認。
- **docs/49 と一致（CALMAR≈40:35:25 近傍）なら確定**。大きくズレたら §0 のスパン警告を確認。

### (B) 倍率確定 — EAに入れる実予算（最重要）
目的別（CALMAR/CAGR/DEFENSE/BASELINE）×目標DD（−4〜−10%）の表で、各行が
**そのDDを実現する v7週次% / v4 1トレード% / E5 legRisk% と CAGR・5年失格** を与える。例（書式）:

```
◆ CALMAR_40_35_25
   目標DD  倍率   v7週次  v4/tr  E5leg   CAGR   p95DD  年失格  5年失格
   -6.0%  M.MMx  X.XXX%  Y.YYY% Z.ZZZ%  ...%   -6.x%  ...%   ...%
```

→ **採用する目的（既定=CALMAR）と、許容できる失格率の行**を選び、その **v7/v4/E5 % を EA に投入**。

## 4. EA への反映（Chien_Portfolio4_Optimized）

- **比率がdocs/49通り**なら: `InpObjective` を該当（CALMAR/CAGR/DEFENSE）にし、サイズはEAの既定倍率で開始 →
  デモ実DDを見て、(B)表の目標DD行に合うよう倍率を微調整。
- **(B)の実予算を厳密に固定**したいなら: `InpObjective=OBJ_MANUAL` にして
  `InpWeeklyRiskPct / InpV4RiskPerTradePct / InpE5LegRiskPct` に (B)の v7/v4/E5 % を直接入力。
- どちらも **−10%ガード（InpAccountFloorDDPct）が最終backstop**。E5≤25%は維持。

## 5. 確定の作法（数字を盛らない）

1. (A)で比率が docs/49 と整合することを確認（不整合なら原因＝スパン/データを潰す）。
2. (B)で **目標DD=−6%（−10%枠に4%マージン, docs/32思想）** を既定の出発点に予算を取得。
3. **デモ前進検証**（docs/29）で v7+v4+E5 併用の**実maxDD・実約定・E5のCFDスワップ/配当**を数ヶ月実測。
4. 実DDが想定内なら本番（まず守り型=低い目標DD）→ 安定後に目標DDを上げて手取りを伸ばす。

> 免責: シミュレーション。独立ブートストラップ＝失格率は上限寄り（実負相関で更に低い）。指数/金CFDの実コストは
> 未計上＝デモで確認。将来/ライブ約定を保証しない。確証はデモ前進検証で。
