# -*- coding: utf-8 -*-
"""docs/244 Q269(2026-11-17 登録「登録して実行」・改良系 2 セル): 夜の指数の大きさを VIX の帯で変える。
A = 前金曜の VIX が 25〜30 の週は合計 0.25(いまと同じ)・30 超の週は合計 0.50。B = 25〜30 の週は合計 0.125・30 超の週は合計 0.50。
判定 = 「配備形 + いまの夜の指数(25 超・一律 0.25)」に対する 3 窓(Sharpe が 3 窓とも上・最悪月が悪化しない)。
30 の線は Q267 の帯の表を見て出てきた区切り(後づけ)。口座モデルは q269b。
使い方: cd research && PYTHONPATH=queue:. python3 -W ignore queue/q269_night_index_size_by_vix_band.py <累積セル数>   出力: results/q269_night_size_by_band.csv"""
import sys
_ARGV = list(sys.argv)
from q_common import *
from q147_roll_rate_diff_gate import stats
import q237_night_leg_after_high_vix as q237
from q240_weekend_premium_predictions import frame, series
from q265_weekend_btc_signal_and_night_index_anatomy import bundle_night, IDX5, WIN
WEEKS = pd.date_range("2016-01-04", "2026-12-28", freq="7D"); VFRI = pd.Series(q237.VIX.reindex(WEEKS - pd.Timedelta(days=3), method="ffill").values, index=WEEKS)
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 2; rows = []; P = frame(); B = series(P, "base"); bs = {w: stats(B, a, b) for w, a, b in WIN}; LO = (VFRI > 25) & (VFRI <= 30); HI = VFRI > 30
    def night(wl, wh): return bundle_night(IDX5, LO, wl).add(bundle_night(IDX5, HI, wh), fill_value=0.0) if wl > 0 else bundle_night(IDX5, HI, wh)
    rs = {w: stats(B.add(night(0.25, 0.25), fill_value=0.0), a, b) for w, a, b in WIN}
    def row(part, nm, wl, wh):
        x = night(wl, wh); v = B.add(x, fill_value=0.0); vs = {w: stats(v, a, b) for w, a, b in WIN}; ok = all(vs[w][0] > rs[w][0] and vs[w][1] >= rs[w][1] for w, _, _ in WIN); okb = all(vs[w][0] > bs[w][0] and vs[w][1] >= bs[w][1] for w, _, _ in WIN)
        mdd = float(((1 + v).cumprod() / (1 + v).cumprod().cummax() - 1).min()) * 100; wk = float(v.min()) * 100
        rows.append(dict(part=part, cell=nm, 前窓=str(vs["前窓"][:3]), IS=str(vs["IS"][:3]), OOS=str(vs["OOS"][:3]), verdict=("成立" if ok else "不成立") if part == "判定" else ("(判定の基準)" if part == "基準" else f"(参照)いまの形を 3 窓で上回る = {ok}"), 配備形だけに対して=okb, 全期間Sharpe=stats(v, PRE0, END)[0], 全期間累積=stats(v, PRE0, END)[2], 最大の下げ幅=round(mdd, 2), 最悪の週=round(wk, 2), 夜の最悪の週=round(float(x.min()) * 100, 2)))
    rows.append(dict(part="基準", cell="配備形 Mon4", 前窓=str(bs["前窓"][:3]), IS=str(bs["IS"][:3]), OOS=str(bs["OOS"][:3]), verdict="", 全期間Sharpe=stats(B, PRE0, END)[0], 全期間累積=stats(B, PRE0, END)[2]))
    row("基準", "配備形 + いまの夜の指数(一律 0.25)", 0.25, 0.25)
    row("判定", "A 25〜30 は 0.25・30 超は 0.50", 0.25, 0.50); row("判定", "B 25〜30 は 0.125・30 超は 0.50", 0.125, 0.50)
    row("参照", "30 超だけ 0.25", 0.0, 0.25); row("参照", "30 超だけ 0.50", 0.0, 0.50); row("参照", "25〜30 は 0.25・30 超は 0.375", 0.25, 0.375); row("参照", "25〜30 は 0.25・30 超は 0.75", 0.25, 0.75); row("参照", "一律 0.50(全体を 2 倍)", 0.50, 0.50)
    D = pd.DataFrame(rows); D.to_csv("results/q269_night_size_by_band.csv", index=False); pd.set_option("display.width", 380); pd.set_option("display.max_colwidth", 60)
    print(f"\n== Q269(累積セル {cum} + {N} = {cum + N}) =="); print(D.fillna("").to_string(index=False))
