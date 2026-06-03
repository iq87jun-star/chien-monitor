# 35. 8本目探索の【事前登録 第5弾・最終】(pre-registration) — universe 拡張・断面構造

> 第1〜4弾（13候補）は全滅。最終バッチとして **universe を拡張**し、単一資産でなく
> **断面（cross-sectional）ファクター**を検定する。docs23 の多資産トレンド・edge2 の
> XSMOM(MA4=REJECT) を、専用 universe で当てに行く最後の試み。N 固定・Bonferroni。

## 固定パラメータ

- **候補数 N = 3**（J1/J2/J3）。**増やさない。これが探索の最終バッチ。**
- **有意水準 α = 0.05 / 3 = 0.0167**。
- **期間**: 2016-2025 の日足10年（Yahoo）。
- **本資金 ADOPT 条件** = 6 ゲート ∧ 分割標本 both_significant。
- 断面 L/S は概ね市場中立で低ボラ → ADOPT でも -10% 枠での縮小サイズ・必要レバを別途実測。

## 候補

| ID | universe | 事前仮説 | 駆動因子 | 既検との違い |
|----|----------|---------|----------|-------------|
| **J1** | 商品4種(金/銀/WTI/銅) | 3か月モメンタム上位 LONG・下位 SHORT、月次リバランス | 商品トレンド・ファクター | docs23 は多資産混在。これは**商品専用**の断面。 |
| **J2** | 世界株価指数5種(SPX/NDX/N225/DAX/FTSE) | 同上（断面相対モメンタム） | 株式の国際相対強弱 | 指数**専用**の断面。E6(指数MR)と逆方向の相対モメンタム。 |
| **J3** | G10 FX 7種(EUR/GBP/AUD/NZD/CAD/CHF/JPY 対USD) | 同上（対USDで断面相対モメンタム） | 通貨の相対強弱 | docs22 は少数 TSMOM。これは**広い断面 XSMOM**。 |

共通設定: lookback=63日・上位/下位 1/3・月次(21日)リバランス・往復コスト 5bp/レッグ。
プラセボ = 同じランクで **L/S を反転**（モメンタムなら反転は突出しないはず）。

## 必要データ（取得済み）

GOLD/SILVER/WTI/COPPER, SPX/NDX/N225/DAX/FTSE, EURUSD/GBPUSD/AUDUSD/NZDUSD/USDCAD/USDCHF/USDJPY（日足）。

## 実行（★承認後）

```bash
python3 research/edge16_xs_commodity_mom_10y.py
python3 research/edge17_xs_index_mom_10y.py
python3 research/edge18_xs_fx_mom_10y.py
```

判定後 docs/36 に確定値を記録し、探索を締める。

---

## ★承認待ち（最終バッチ）

この **N=3・α=0.0167・J1/J2/J3** で確定してよいか確認してください。差し替えは検定前の今だけ。
