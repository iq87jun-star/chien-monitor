# -*- coding: utf-8 -*-
"""docs/244 Q237(改良系・5 セル・2026-11-16 登録「登録して実行」): 荒れた後の「夜だけ」を取るレグを配備形 Mon4 に足す。
夜のレグ = 前営業日の VIX > 25 の日に 20:00 UTC 買い → 翌日決済(円クロス 07:00 UTC・指数 13:00 UTC)。建ては月〜木。往復コスト q_common.cost。
A1 = Mon4 + 円クロス 4 本の火〜木の夜(各 0.25)。A2 = + NAS100・US500 の月曜の夜(合計 0.25)。A3 = + NAS100・US500 の月〜木の夜(合計 0.25)。A4 = + 指数 5 本の月〜木の夜(合計 0.25)。A5 = A1 + A3。
判定 = 配備形 Mon4(線の下 1.0・上 0.5・24h)の週次の系列に対して 前窓・IS・OOS の 3 つすべてで Sharpe 改善 かつ 最悪月が悪化しない。指数を含む形は指数の H1 がある期間だけで比べる。
使い方: cd research && python3 -W ignore queue/q237_night_leg_after_high_vix.py <累積セル数>   出力: results/q237_night_leg_after_high_vix.csv・_ref.csv・_legs.csv"""
import sys, os
_ARGV = list(sys.argv)
from q_common import *
from q147_roll_rate_diff_gate import stats
from q229_state_dependent_exit import mon_frame, mon_series, MON_PAIRS
from q232_mon4_exit_switch_vix_other_ma import frame as frame232, series as series232
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END)); ALLW = WIN + (("全期間", PRE0, END),); TH = 25.0
IDX5 = ["US30", "JP225", "UK100", "NAS100", "US500"]; IDX2 = ["NAS100", "US500"]
V = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data_ext", "VIX_History.csv")); V["d"] = pd.to_datetime(V["DATE"]); VIX = V.set_index("d")["CLOSE"].sort_index().astype(float)
_N = {}
def night(sym, exit_hour):
    """20:00 UTC 買い → 翌日 exit_hour UTC 決済(月〜木に建てる全日)。列: r(コスト後)・dow・vix(前営業日の終値)・week(その週の月曜)。index = 建て日。"""
    if (sym, exit_hour) not in _N:
        o = load(sym)["open"]; t = o.index[(o.index.hour == 20) & (o.index.dayofweek <= 3)]; t2 = t.normalize() + pd.Timedelta(days=1, hours=exit_hour); p0 = o.reindex(t).values; p1 = o.reindex(t2).values; ok = ~np.isnan(p1) & ~np.isnan(p0)
        d = t.normalize()[ok]; x = pd.DataFrame({"r": p1[ok] / p0[ok] - 1 - cost(sym, p0[ok]), "dow": d.dayofweek, "vix": VIX.reindex(d - pd.Timedelta(days=1), method="ffill").values, "week": d - pd.to_timedelta(d.dayofweek, unit="D")}, index=d)
        _N[(sym, exit_hour)] = x[x.index >= PRE0]
    return _N[(sym, exit_hour)]
def night_weekly(syms, exit_hour, dows, w_each):
    """VIX > 25 の夜だけ建てたときの週次の損益(その週の月曜の日付)。"""
    out = None
    for s in syms:
        x = night(s, exit_hour); x = x[(x.vix > TH) & x.dow.isin(dows)]; y = (x.r * w_each).groupby(x.week).sum(); out = y if out is None else out.add(y, fill_value=0.0)
    return out
def variants():
    P = mon_frame(); B = mon_series(P); E1 = series232(frame232(), "E1")
    fx = night_weekly(MON_PAIRS, 7, [1, 2, 3], 0.25); i2m = night_weekly(IDX2, 13, [0], 0.125); i2 = night_weekly(IDX2, 13, [0, 1, 2, 3], 0.125); i5 = night_weekly(IDX5, 13, [0, 1, 2, 3], 0.05)
    start_i2 = max(night(s, 13).index.min() for s in IDX2); start_i5 = max(night(s, 13).index.min() for s in IDX5)
    def add(b, x): return b.add(x.reindex(b.index).fillna(0.0), fill_value=0.0)
    return B, E1, {"A1": (add(B, fx), PRE0, "A1 + 円クロス 4 本の火〜木の夜(各 0.25)"), "A2": (add(B, i2m), start_i2, "A2 + NAS100・US500 の月曜の夜(合計 0.25)"), "A3": (add(B, i2), start_i2, "A3 + NAS100・US500 の月〜木の夜(合計 0.25)"),
                   "A4": (add(B, i5), start_i5, "A4 + 指数 5 本の月〜木の夜(合計 0.25)"), "A5": (add(add(B, fx), i2), start_i2, "A5 = A1 + A3")}, {"fx": fx, "i2m": i2m, "i2": i2, "i5": i5}
def night_added(kind="A3"):
    """紙上候補用: 配備形 Mon4 + 夜のレグ。index = 月曜。"""
    B, E1, Vs, _ = variants(); return Vs[kind][0]
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 5; B, E1, Vs, parts = variants(); rows = []; ref = []
    def st(x, a, b, s0): a = max(a, s0); return stats(x, a, b) if a <= b else (0.0, 0.0, 0.0, 0)
    for k, (v, s0, nm) in Vs.items():
        bs = {w: st(B, a, b, s0) for w, a, b in WIN}; vs = {w: st(v, a, b, s0) for w, a, b in WIN}
        rows.append(dict(cell=nm, from_date=str(pd.Timestamp(s0).date()), base_PRE=bs["前窓"], var_PRE=vs["前窓"], base_IS=bs["IS"], var_IS=vs["IS"], base_OOS=bs["OOS"], var_OOS=vs["OOS"], sharpe_up_3win=bool(all(vs[w][0] > bs[w][0] for w, _, _ in WIN)), verdict=("成立" if all(vs[w][0] > bs[w][0] and vs[w][1] >= bs[w][1] for w, _, _ in WIN) else "不成立")))
        e = E1.add(v - B, fill_value=0.0); es = {w: st(E1, a, b, s0) for w, a, b in WIN}; ev = {w: st(e, a, b, s0) for w, a, b in WIN}; ref.append(dict(variant="基準を E1 に置いた場合: " + nm, E1_PRE=es["前窓"], var_PRE=ev["前窓"], E1_IS=es["IS"], var_IS=ev["IS"], E1_OOS=es["OOS"], var_OOS=ev["OOS"]))
    D = pd.DataFrame(rows); D.to_csv("results/q237_night_leg_after_high_vix.csv", index=False); RF = pd.DataFrame(ref); RF.to_csv("results/q237_night_leg_after_high_vix_ref.csv", index=False)
    for nm, x in (("夜のレグ単独(週次): 円クロス 4 本・火〜木", parts["fx"]), ("夜のレグ単独(週次): NAS100・US500・月曜", parts["i2m"]), ("夜のレグ単独(週次): NAS100・US500・月〜木", parts["i2"]), ("夜のレグ単独(週次): 指数 5 本・月〜木", parts["i5"])):
        y = x.reindex(B.index).fillna(0.0); ref.append(dict(variant=nm, E1_PRE=None, var_PRE=stats(y, *WIN[0][1:]), E1_IS=None, var_IS=stats(y, *WIN[1][1:]), E1_OOS=None, var_OOS=stats(y, *WIN[2][1:])))
    RF = pd.DataFrame(ref); RF.to_csv("results/q237_night_leg_after_high_vix_ref.csv", index=False); legs = []
    for s, eh in [(s, 7) for s in MON_PAIRS] + [(s, 13) for s in IDX5]:
        x = night(s, eh)
        for dn, dm in (("月曜", x.dow == 0), ("火〜木", x.dow >= 1)):
            for vn, vm in (("VIX 25 超", x.vix > TH), ("VIX 25 以下", x.vix <= TH)):
                for w, a, b in ALLW:
                    y = x[dm & vm & (x.index >= a) & (x.index <= b)].r; legs.append(dict(symbol=s, days=dn, vix=vn, window=w, n=len(y), mean_bps=round(float(y.mean()) * 1e4, 1) if len(y) else None, win=round(float((y > 0).mean()) * 100, 0) if len(y) else None, t=round(float(y.mean() / y.std() * np.sqrt(len(y))), 2) if len(y) > 2 and y.std() > 0 else None))
    L = pd.DataFrame(legs); L.to_csv("results/q237_night_leg_after_high_vix_legs.csv", index=False)
    pd.set_option("display.width", 340); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 400); pd.set_option("display.max_colwidth", 70)
    print(f"Q237: cells={N} cum_before={cum} cum_after={cum + N} passed={int((D.verdict == '成立').sum())}/{N}  (値 = Sharpe, 最悪月 %, 累積 %, 建てた週)"); print(D.to_string(index=False)); print("\n== 参照(判定に使わない) =="); print(RF.to_string(index=False))
    print("\n== 夜のレグ単独(コスト後・平均 bps (本数)・全期間の t) ==")
    for dn in ("月曜", "火〜木"):
        for vn in ("VIX 25 超", "VIX 25 以下"):
            g = L[(L.days == dn) & (L.vix == vn)]; order = list(MON_PAIRS) + IDX5
            pv = (g.pivot(index="symbol", columns="window", values="mean_bps").reindex(order)[[w[0] for w in ALLW]].astype(str) + " (" + g.pivot(index="symbol", columns="window", values="n").reindex(order)[[w[0] for w in ALLW]].astype(str) + ")"); pv["t(全期間)"] = g[g.window == "全期間"].set_index("symbol").t.reindex(order).values; print(f"-- {dn}・{vn} --"); print(pv.to_string())
