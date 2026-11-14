# -*- coding: utf-8 -*-
"""docs/244 Q171(新規 6 セル・2026-11-08 ユーザー「登録実行お願いします」): クロスアセットの先行・遅行。
信号 = X の 24h 変化(20 UTC 足始値 → 翌 20 UTC 足始値・米国引け前の最終足。CFD は 21 UTC 足が無い日が多いため)、取引 = 翌 24h の Y(21 UTC 建て → 翌 21 UTC 決済)、方向は仕組みから事前固定(全日・閾値なし)。
  1. USTBOND(米 10 年国債先物 CFD)↓ = 利回り↑ → USDJPY LONG(dir = −sign ΔUSTBOND)   2. 同 → GBPJPY
  3. WTI ↑ → CADJPY LONG(dir = +sign ΔWTI)   4. WTI ↑ → USDCAD SHORT(dir = −sign ΔWTI)
  5. US500 ↑(リスクオン)→ AUDJPY LONG(dir = +sign ΔUS500)   6. 同 → NZDJPY
コスト: 往復 3pip(q_common.trades)。データ: data_dukascopy H1(X は 2018-01〜 のため前窓は 2018-01〜2021-09)。判定: docs/244 §1 標準。
使い方: cd research && python3 queue/q171_cross_asset_leadlag.py <累積>   出力: results/q171_cross_asset_leadlag.csv"""
import sys
from q_common import *
HX, H = 20, 21
CELLS = [("USTBOND", "USDJPY", -1), ("USTBOND", "GBPJPY", -1), ("WTI", "CADJPY", +1), ("WTI", "USDCAD", -1), ("US500", "AUDJPY", +1), ("US500", "NZDJPY", +1)]
def daily_open(sym, h=H):
    o = load(sym)["open"]; o = o[o.index.hour == h]; o.index = o.index.normalize(); return o[~o.index.duplicated(keep="last")]
def cell(x, y, sgn):
    ox, oy = daily_open(x, HX), daily_open(y)
    sig = np.sign(ox.shift(-1) / ox - 1)          # 日 d の 21 UTC → d+1 の 21 UTC の変化。index = d
    sig.index = sig.index + pd.Timedelta(days=1)  # 信号が確定する日 d+1 に置く(= 取引の建て日)
    idx = sig.dropna().index.intersection(oy.index); idx = idx[idx >= PRE0]
    t_in = idx; p_in = oy.reindex(t_in).values; t_out = t_in + pd.Timedelta(days=1); p_out = oy.reindex(t_out).values
    return trades(y, t_in + pd.Timedelta(hours=H), p_in, sgn * sig.reindex(t_in).values, p_out)
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q171", cum, len(CELLS), "results/q171_cross_asset_leadlag.csv")
    for x, y, sgn in CELLS:
        selfcheck(y, load(y)); r = cell(x, y, sgn)
        R.add("クロスアセット先行", y, f"{x} 24h変化 → {y} 翌24h dir={'+' if sgn>0 else '−'}sign(X 20 UTC・Y 21 UTC)", r)
    R.finish()
    # 参考: 粗利(コスト前)と信号の強さ別(|ΔX| 上位 1/3)の平均 bps
    rows = []
    for x, y, sgn in CELLS:
        ox, oy = daily_open(x, HX), daily_open(y); dx = (ox.shift(-1) / ox - 1); dx.index = dx.index + pd.Timedelta(days=1)
        idx = dx.dropna().index.intersection(oy.index); idx = idx[idx >= PRE0]; ry = (oy.reindex(idx + pd.Timedelta(days=1)).values / oy.reindex(idx).values - 1)
        g = pd.Series(sgn * np.sign(dx.reindex(idx).values) * ry, index=idx).dropna(); big = dx.reindex(g.index).abs() >= dx.reindex(g.index).abs().quantile(2 / 3)
        for w, lo, hi in (("前窓", PRE0, IS0), ("IS", IS0, IS1), ("OOS", OOS0, END)):
            s = g[(g.index >= lo) & (g.index <= hi)]; b = s[big.reindex(s.index).fillna(False)]
            rows.append(dict(cell=f"{x}→{y}", 窓=w, n=len(s), 粗利bps=round(float(s.mean()) * 1e4, 2), 大信号n=len(b), 大信号粗利bps=round(float(b.mean()) * 1e4, 2), 相関=round(float(np.corrcoef(dx.reindex(s.index).values, ry[np.isin(idx, s.index)])[0, 1]), 3)))
    T = pd.DataFrame(rows); print("\n参考(コスト前・符号追随の粗利と ΔX↔翌日 Y の相関):"); print(T.to_string(index=False)); T.to_csv("results/q171_cross_asset_leadlag_levels.csv", index=False)
