# -*- coding: utf-8 -*-
"""docs/244 Q268(2026-11-17 登録「案2も登録して実行」・診断 + 改良系 4 セル): 週末をまたいだ下げを夜の指数の引き金にする。
週末の下げ = 指数 5 本それぞれの「金曜 20:00 UTC の足の始値(無ければその日の 6 時間以内の直前の足)→ 月曜 20:00 UTC の足の始値」の変化率を、データのある銘柄で平均。
D1・D2(置き換え)= VIX を使わず、下げが −1% 以下 / −2% 以下の週だけ夜の指数 5 本(合計 0.25)。
U1・U2(足す)= VIX > 25 または 下げが −1% 以下 / −2% 以下の週。
判定 = 「配備形 + いまの夜の指数(VIX 25 超)」に対する 3 窓(Sharpe が 3 窓とも上・最悪月が悪化しない)。
診断(セル 0): 前金曜の VIX の帯 × 下げの大きさで分けた月曜の夜(5 本の週平均・費用後)。
参照(判定しない): 下げを月曜 19:00 UTC までで測った場合・配備形だけに対する 3 窓。
使い方: cd research && PYTHONPATH=queue:. python3 -W ignore queue/q268_weekend_drop_trigger_for_night_index.py <累積セル数>   出力: results/q268_weekend_drop_trigger.csv・_grid.csv"""
import sys
_ARGV = list(sys.argv)
from q_common import *
from q147_roll_rate_diff_gate import stats
import q237_night_leg_after_high_vix as q237
from q240_weekend_premium_predictions import frame, series
from q265_weekend_btc_signal_and_night_index_anatomy import night_all, bundle_night, IDX5, WIN
H = pd.Timedelta(hours=1); WEEKS = pd.date_range("2016-01-04", "2026-12-28", freq="7D"); VFRI = pd.Series(q237.VIX.reindex(WEEKS - pd.Timedelta(days=3), method="ffill").values, index=WEEKS)
def drop(end_hour=20):
    cols = []
    for s in IDX5:
        o = load(s)["open"]; pf = o.reindex(WEEKS - pd.Timedelta(days=3) + 20 * H, method="ffill", tolerance=6 * H).values; pm = o.reindex(WEEKS + end_hour * H).values; cols.append(pd.Series(pm / pf - 1, index=WEEKS))
    return pd.concat(cols, axis=1).mean(axis=1, skipna=True)
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 4; rows = []; ref = []; P = frame(); B = series(P, "base"); bs = {w: stats(B, a, b) for w, a, b in WIN}; DR = drop(20); DR19 = drop(19); HOT = VFRI > 25
    NB = bundle_night(IDX5, HOT, 0.25); rs = {w: stats(B.add(NB, fill_value=0.0), a, b) for w, a, b in WIN}
    def row(part, nm, f):
        x = bundle_night(IDX5, f.fillna(False), 0.25); v = B.add(x, fill_value=0.0); vs = {w: stats(v, a, b) for w, a, b in WIN}
        ok = all(vs[w][0] > rs[w][0] and vs[w][1] >= rs[w][1] for w, _, _ in WIN); okb = all(vs[w][0] > bs[w][0] and vs[w][1] >= bs[w][1] for w, _, _ in WIN); t = float(x.mean() / x.std() * np.sqrt(len(x))) if len(x) > 2 and x.std() > 0 else 0.0
        rows.append(dict(part=part, cell=nm, 前窓=str(vs["前窓"][:3]), IS=str(vs["IS"][:3]), OOS=str(vs["OOS"][:3]), verdict=("成立" if ok else "不成立") if part == "判定" else ("(判定の基準)" if part == "基準" else f"(参照)いまの形を 3 窓で上回る = {ok}"),
                         配備形だけに対して=okb, 夜の週数=len(x), VIX25超と重なる週=int((f.fillna(False) & HOT).reindex(x.index).sum()), 束の平均bps=round(float(x.mean()) / 0.25 * 1e4, 1), t=round(t, 2), 窓ごとbps=" / ".join(f"{x[(x.index >= a) & (x.index <= b)].mean() / 0.25 * 1e4:+.0f}({int(((x.index >= a) & (x.index <= b)).sum())})" for w, a, b in WIN)))
    rows.append(dict(part="基準", cell="配備形 Mon4", 前窓=str(bs["前窓"][:3]), IS=str(bs["IS"][:3]), OOS=str(bs["OOS"][:3]), verdict=""))
    row("基準", "配備形 + いまの夜の指数(VIX > 25)", HOT)
    row("判定", "D1 週末の下げ −1% 以下の週だけ", DR <= -0.01); row("判定", "D2 週末の下げ −2% 以下の週だけ", DR <= -0.02)
    row("判定", "U1 VIX > 25 または 下げ −1% 以下", HOT | (DR <= -0.01)); row("判定", "U2 VIX > 25 または 下げ −2% 以下", HOT | (DR <= -0.02))
    row("参照", "D1 を月曜 19 UTC までの下げで", DR19 <= -0.01); row("参照", "D2 を月曜 19 UTC までの下げで", DR19 <= -0.02)
    row("参照", "VIX > 25 かつ 下げ −1% 以下", HOT & (DR <= -0.01)); row("参照", "VIX > 25 かつ 下げが −1% より小さい", HOT & (DR > -0.01)); row("参照", "VIX ≤ 25 かつ 下げ −1% 以下", (~HOT) & (DR <= -0.01)); row("参照", "VIX ≤ 25 かつ 下げ −2% 以下", (~HOT) & (DR <= -0.02))
    # 診断: VIX の帯 × 下げの大きさ(5 本の週平均・費用後)
    NA = pd.concat([night_all(s).reindex(WEEKS) for s in IDX5], axis=1).mean(axis=1, skipna=True)
    VB = (("VIX 20 以下", 0, 20), ("20〜25", 20, 25), ("25〜30", 25, 30), ("30 超", 30, 1e9), ("全体", 0, 1e9)); DB = (("−2% 以下", -9, -0.02), ("−2〜−1%", -0.02, -0.01), ("−1〜0%", -0.01, 0.0), ("プラス", 0.0, 9), ("全体", -9, 9))
    for vn, v0, v1 in VB:
        r_ = dict(前金曜のVIX=vn)
        for dn, d0, d1 in DB:
            m = ((VFRI > v0) & (VFRI <= v1) & (DR > d0) & (DR <= d1)).values; x = NA[m].dropna()
            r_[dn] = f"{x.mean() * 1e4:+.0f}(t {x.mean() / x.std() * np.sqrt(len(x)):.1f}・{len(x)})" if len(x) > 2 and x.std() > 0 else (f"{x.mean() * 1e4:+.0f}({len(x)})" if len(x) else "—")
        ref.append(r_)
    D = pd.DataFrame(rows); RF = pd.DataFrame(ref); D.to_csv("results/q268_weekend_drop_trigger.csv", index=False); RF.to_csv("results/q268_weekend_drop_trigger_grid.csv", index=False)
    pd.set_option("display.width", 380); pd.set_option("display.max_colwidth", 70); pd.set_option("display.max_rows", 100)
    print(f"\n== Q268(累積セル {cum} + {N} = {cum + N}) =="); print(D.fillna("").to_string(index=False)); print("\n== 診断: VIX の帯 × 週末の下げ(月曜の夜・5 本の週平均・費用後・bps) =="); print(RF.to_string(index=False))
    c = pd.DataFrame({"d": DR, "n": NA, "v": VFRI}).dropna(); print("\n週末の下げと月曜の夜の相関: 全体", round(c.d.corr(c.n), 2), len(c), "・VIX > 25", round(c[c.v > 25].d.corr(c[c.v > 25].n), 2), int((c.v > 25).sum()), "・VIX ≤ 25", round(c[c.v <= 25].d.corr(c[c.v <= 25].n), 2), "・VIX > 30", round(c[c.v > 30].d.corr(c[c.v > 30].n), 2), int((c.v > 30).sum()))
    for nm, f in (("D1", DR <= -0.01), ("D2", DR <= -0.02)):
        x = NA[f.fillna(False).values].dropna(); print(nm, "年ごと(bps・週数):", {int(y): (round(float(g.mean()) * 1e4), len(g)) for y, g in x.groupby(x.index.year)})
