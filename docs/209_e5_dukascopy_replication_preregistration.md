# 209.【事前登録・確認研究】E5 の別ソース(Dukascopy)同窓再現 — docs/84 条件(a)

> 2026-09-03作成。費用ゼロ。docs/84 §2 は E5 を「ADOPT候補(Yahoo近似)」とし、確定条件を
> **(a) 別ソース(Dukascopy日足等)での同窓再現 または (b) デモ前進検証** と定めた。
> 本docは (a) を実行する。**Dukascopy datafeed はこのセッションから取得可能と確認済み**(2026-09-03 プローブ成功)。
> 本docのルールは`research/e5_replicate_dukascopy.py`の実行**前**に凍結した。

## 1. データ

- 取得: `research/tools/dukascopy_fetch.py --tf day`(BID 日足・年ファイル)。銘柄: XAUUSD / USA500IDXUSD / USATECHIDXUSD / DEUIDXEUR。
- **窓は Dukascopy 側の開始日で決まる**(指数 CFD は 2010年代開始)。docs/84 の 26年窓は再現不能であり、
  再現対象は **docs/40 の10年窓(2016-01〜2026-08)** と **Dukascopy で取れる最長窓** の2本とする。
- E5 の生成式は `recentfit_screen.e5_composite` を**一切変更せず**、入力データだけ差し替える
  (月次終値・4資産・(1,3,6,12)ヶ月モメンタム符号の合議・12ヶ月逆ボラ加重・翌月適用・月初コスト5bp)。

## 2. 判定(実行前固定)

docs/40 の E5 ゲート(N=6 → Bonferroni α=0.05/6=**0.0083**、年次JK max_p ≤ 0.10)を、Dukascopy 系列で再計算する。

| 条件 | 内容 |
|---|---|
| R1 再現性 | Dukascopy と Yahoo の E5 月次リターンの相関 ≥ 0.90(共通期間)。**同じものを測っている**ことの確認 |
| R2 有意性 | 最長窓の順列検定(月次符号反転・1万回) p < 0.0083 |
| R3 頑健性 | 年次ジャックナイフ max_p ≤ 0.10 |
| R4 一貫性 | 5年ブロック(切りの良い暦年)が全て正 |

- **R1〜R4 全て合格 → E5 を ADOPT に確定**(docs/84 の条件(a)充足)。
- R1 不合格 → 「同窓再現」にならない。生成式かデータの差異を記録し、判定保留。
- R2〜R4 のいずれか不合格 → **ADOPT候補のまま据え置き**(条件(b) デモへ)。
- 稼働中口座は変更しない。E5 の配置は docs/194・口座別配置案の通り(非FX+E5 / Swing 25k 案1)。

## 3. 実行物

- `research/e5_replicate_dukascopy.py` / `results/e5_replicate_dukascopy.json`
- 結果は本docの §4 として追記する
