# -*- coding: utf-8 -*-
"""docs/244 Q267(2026-11-17 登録「登録して実行」・診断 + 改良系 2 セル): 夜の指数の VIX のしきい値。
ユーザー 2026-11-17「新案は無いですか」→ 案 1・2 を提示 →「登録して実行」(番号の指定なし → 案 1 だけ)。
診断(セル 0): 月曜の夜の指数 5 本(月曜 20 UTC → 火曜 13 UTC・費用後)を、前金曜の VIX の帯(15 以下・15〜20・20〜25・25〜30・30 超)で分ける。
T20 = 配備形 + 前金曜の VIX > 20 の週の夜の指数 5 本(合計 0.25)。T22 = 同じ形で VIX > 22.5。
判定 = 「配備形 + いまの夜の指数(25 超)」に対する 3 窓(Sharpe が 3 窓とも上・最悪月が悪化しない)。
参照(判定しない): 30 超だけ・20〜25 の帯だけ・配備形だけに対する 3 窓。
使い方: cd research && PYTHONPATH=queue:. python3 -W ignore queue/q267_night_index_vix_threshold.py <累積セル数>   出力: results/q267_night_vix_threshold.csv・_bands.csv"""
import sys
_ARGV = list(sys.argv)
from q_common import *
from q147_roll_rate_diff_gate import stats
import q237_night_leg_after_high_vix as q237
from q240_weekend_premium_predictions import frame, series
from q265_weekend_btc_signal_and_night_index_anatomy import night_all, bundle_night, IDX5, WIN
WEEKS = pd.date_range("2016-01-04", "2026-12-28", freq="7D"); VFRI = pd.Series(q237.VIX.reindex(WEEKS - pd.Timedelta(days=3), method="ffill").values, index=WEEKS)
def flag(lo, hi=1e9): return (VFRI > lo) & (VFRI <= hi)
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 2; rows = []; ref = []; P = frame(); B = series(P, "base"); bs = {w: stats(B, a, b) for w, a, b in WIN}
    NB = bundle_night(IDX5, flag(25), 0.25); rs = {w: stats(B.add(NB, fill_value=0.0), a, b) for w, a, b in WIN}
    def row(part, nm, f):
        x = bundle_night(IDX5, f, 0.25); v = B.add(x, fill_value=0.0); vs = {w: stats(v, a, b) for w, a, b in WIN}
        ok = all(vs[w][0] > rs[w][0] and vs[w][1] >= rs[w][1] for w, _, _ in WIN); okb = all(vs[w][0] > bs[w][0] and vs[w][1] >= bs[w][1] for w, _, _ in WIN)
        t = float(x.mean() / x.std() * np.sqrt(len(x))) if len(x) > 2 and x.std() > 0 else 0.0; yrs = (x.index.max() - x.index.min()).days / 365.25 if len(x) > 1 else 1.0
        rows.append(dict(part=part, cell=nm, 前窓=str(vs["前窓"][:3]), IS=str(vs["IS"][:3]), OOS=str(vs["OOS"][:3]), verdict=("成立" if ok else "不成立") if part == "判定" else ("(判定の基準)" if part == "基準" else f"(参照)いまの形を 3 窓で上回る = {ok}"),
                         配備形だけに対して=okb, 夜の週数=len(x), 束の平均bps=round(float(x.mean()) / 0.25 * 1e4, 1), t=round(t, 2), 窓ごとbps=" / ".join(f"{x[(x.index >= a) & (x.index <= b)].mean() / 0.25 * 1e4:+.0f}({int(((x.index >= a) & (x.index <= b)).sum())})" for w, a, b in WIN)))
    rows.append(dict(part="基準", cell="配備形 Mon4", 前窓=str(bs["前窓"][:3]), IS=str(bs["IS"][:3]), OOS=str(bs["OOS"][:3]), verdict=""))
    row("基準", "配備形 + いまの夜の指数(VIX > 25)", flag(25))
    row("判定", "T20 VIX > 20 の週", flag(20)); row("判定", "T22 VIX > 22.5 の週", flag(22.5))
    row("参照", "VIX > 30 の週だけ", flag(30)); row("参照", "20〜25 の帯だけ", flag(20, 25)); row("参照", "22.5〜25 の帯だけ", flag(22.5, 25)); row("参照", "すべての週", flag(0))
    # 診断: 帯ごと(5 本の週平均・費用後)。t は週の数で数える
    NA = pd.concat([night_all(s).reindex(WEEKS) for s in IDX5], axis=1); NA.columns = IDX5; AVG = NA.mean(axis=1, skipna=True)
    BANDS = (("15 以下", 0, 15), ("15〜20", 15, 20), ("20〜22.5", 20, 22.5), ("22.5〜25", 22.5, 25), ("20〜25", 20, 25), ("25〜30", 25, 30), ("30 超", 30, 1e9), ("25 超(いまの形)", 25, 1e9))
    for nm, lo, hi in BANDS:
        x = AVG[flag(lo, hi).values].dropna(); r_ = dict(帯=nm, 週数=len(x), 年あたり=round(len(x) / 10.6, 1), 平均bps=round(float(x.mean()) * 1e4, 1) if len(x) else None, t=round(float(x.mean() / x.std() * np.sqrt(len(x))), 2) if len(x) > 2 else None, プラスの週=f"{(x > 0).mean() * 100:.0f}%" if len(x) else "—")
        for w, a, b in WIN: y = x[(x.index >= a) & (x.index <= b)]; r_[w] = f"{y.mean() * 1e4:+.1f}({len(y)})" if len(y) else "—"
        for s in IDX5: z = NA[s][flag(lo, hi).values].dropna(); r_[s] = f"{z.mean() * 1e4:+.0f}" if len(z) else "—"
        ex = x[x.index.year != 2020]; r_["2020 年を除く"] = f"{ex.mean() * 1e4:+.1f}(t {ex.mean() / ex.std() * np.sqrt(len(ex)):.1f}・{len(ex)})" if len(ex) > 2 else "—"; ref.append(r_)
    D = pd.DataFrame(rows); RF = pd.DataFrame(ref); D.to_csv("results/q267_night_vix_threshold.csv", index=False); RF.to_csv("results/q267_night_vix_threshold_bands.csv", index=False)
    pd.set_option("display.width", 360); pd.set_option("display.max_colwidth", 70); pd.set_option("display.max_rows", 100)
    print(f"\n== Q267(累積セル {cum} + {N} = {cum + N}) =="); print(D.fillna("").to_string(index=False)); print("\n== 診断: VIX の帯ごとの月曜の夜(5 本の週平均・費用後・bps) =="); print(RF.fillna("").to_string(index=False))
    x = AVG[flag(20, 25).values].dropna(); print("\n20〜25 の帯の年ごと:", (x.groupby(x.index.year).mean() * 1e4).round(1).to_dict(), "週数", x.groupby(x.index.year).size().to_dict())
