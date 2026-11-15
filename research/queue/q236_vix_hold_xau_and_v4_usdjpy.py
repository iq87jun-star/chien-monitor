# -*- coding: utf-8 -*-
"""docs/244 Q236(改良系・4 セル・2026-11-16 登録): VIX の残りの未検証。
(X) 金の保有(base.hold_cell("XAUUSD"))× 前営業日の VIX: XA = VIX > 20 の日 1.0 倍・以下 0.5 倍、XB = 逆。
(V) USDJPY の逆張り v4(q206.v4_trades)× シグナルの日の VIX: VA = VIX > 20 で建てる取引 1.0 倍・以下 0.5 倍、VB = 逆。
判定 = 常時 1.0 倍に対して 前窓・IS・OOS の 3 つすべてで Sharpe 改善 かつ 最悪月が悪化しない。
使い方: cd research && python3 -W ignore queue/q236_vix_hold_xau_and_v4_usdjpy.py <累積セル数>   出力: results/q236_vix_hold_xau_and_v4_usdjpy.csv・_ref.csv"""
import sys, os
_ARGV = list(sys.argv)
from q_common import *
import q206_sma200_state_v4_usdjpy_ger40_breakout as q206
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END)); ALLW = WIN + (("全期間", PRE0, END),)
V = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data_ext", "VIX_History.csv")); V["d"] = pd.to_datetime(V["DATE"]); VIX = V.set_index("d")["CLOSE"].sort_index().astype(float)
def xau_series(kind="XA", th=20.0):
    """金の保有(日次)× 前営業日の VIX。base = 常に 1.0、XA = VIX > th の日 1.0・以下 0.5、XB = 逆。戻り値 (系列, 前営業日の VIX)"""
    r = base.hold_cell("XAUUSD"); r = r[r.index >= PRE0]; v = VIX.reindex(pd.DatetimeIndex(r.index).normalize() - pd.Timedelta(days=1), method="ffill").values; hot = v > th
    f = {"base": np.ones(len(r)), "XA": np.where(hot, 1.0, 0.5), "XB": np.where(hot, 0.5, 1.0)}[kind]; return r * f, v
_T = []
def v4_tr():
    if not _T:
        for t in q206.v4_trades("USDJPY"): t["vix"] = float(VIX.reindex([pd.Timestamp(t["sig_date"]).normalize()], method="ffill").values[0]); _T.append(t)
    return _T
def v4_series(kind="VA", th=20.0):
    """USDJPY 逆張り v4 × シグナルの日の VIX。base = 常に 1.0、VA = VIX > th の取引 1.0・以下 0.5、VB = 逆。"""
    acc = {}
    for t in v4_tr():
        hot = t["vix"] > th; f = {"base": 1.0, "VA": (1.0 if hot else 0.5), "VB": (0.5 if hot else 1.0)}[kind]
        for d, r in t["daily"].items(): acc[d] = acc.get(d, 0.0) + r * f
    s = base.clip(pd.Series(acc).sort_index()); return s[s.index >= PRE0]
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 4; rows = []; ref = []
    xb, xv = xau_series("base"); vb = v4_series("base"); chk = base.v4_cell("USDJPY"); chk = chk[chk.index >= PRE0]; assert len(vb) == len(chk) and np.allclose(vb.values, chk.values), "v4 の再構成が v4_cell と一致しない"
    for grp, b, mk, names in (("X 金の保有", xb, lambda k, th=20.0: xau_series(k, th)[0], (("XA", "XA 金の保有: VIX > 20 の日 1.0 倍・以下 0.5 倍"), ("XB", "XB 金の保有: VIX ≤ 20 の日 1.0 倍・超 0.5 倍"))),
                              ("V USDJPY の逆張り", vb, lambda k, th=20.0: v4_series(k, th), (("VA", "VA USDJPY 逆張り: VIX > 20 の取引 1.0 倍・以下 0.5 倍"), ("VB", "VB USDJPY 逆張り: VIX ≤ 20 の取引 1.0 倍・超 0.5 倍")))):
        b_ = {w: q206.stat(b, a, e) for w, a, e in WIN}
        for k, nm in names:
            x = mk(k); x_ = {w: q206.stat(x, a, e) for w, a, e in WIN}; ok = all(x_[w][0] > b_[w][0] and x_[w][1] >= b_[w][1] for w, _, _ in WIN)
            rows.append(dict(group=grp, cell=nm, base_PRE=b_["前窓"], var_PRE=x_["前窓"], base_IS=b_["IS"], var_IS=x_["IS"], base_OOS=b_["OOS"], var_OOS=x_["OOS"], verdict=("成立" if ok else "不成立")))
            y = mk(k, 25.0); ref.append(dict(kind="境目 25", cell=nm.replace("20", "25"), PRE=q206.stat(y, *WIN[0][1:]), IS=q206.stat(y, *WIN[1][1:]), OOS=q206.stat(y, *WIN[2][1:])))
    D = pd.DataFrame(rows); D.to_csv("results/q236_vix_hold_xau_and_v4_usdjpy.csv", index=False); bk = []
    G = pd.DataFrame({"r": xb.values, "vix": xv}, index=xb.index); TR = pd.DataFrame([dict(d=pd.Timestamp(t["entry_date"]), r=t["ret"], vix=t["vix"]) for t in v4_tr()]).set_index("d"); TR = TR[TR.index >= PRE0]
    for nm, X in (("金の保有(日次)", G), ("USDJPY 逆張り(取引ごと)", TR)):
        for gn, lo, hi in (("VIX 15 未満", 0, 15), ("VIX 15〜20", 15, 20), ("VIX 20〜25", 20, 25), ("VIX 25 超", 25, 999)):
            for w, a, e in ALLW:
                y = X[(X.vix >= lo) & (X.vix < hi) & (X.index >= a) & (X.index <= e)].r; bk.append(dict(leg=nm, group=gn, window=w, n=len(y), mean_bps=round(float(y.mean()) * 1e4, 1) if len(y) else None, win=round(float((y > 0).mean()) * 100, 0) if len(y) else None, t=round(float(y.mean() / y.std() * np.sqrt(len(y))), 2) if len(y) > 2 and y.std() > 0 else None))
    BK = pd.DataFrame(bk); RF = pd.DataFrame(ref); RF.to_csv("results/q236_vix_hold_xau_and_v4_usdjpy_ref.csv", index=False); BK.to_csv("results/q236_vix_hold_xau_and_v4_usdjpy_buckets.csv", index=False)
    pd.set_option("display.width", 340); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 300); pd.set_option("display.max_colwidth", 70)
    print(f"Q236: cells={N} cum_before={cum} cum_after={cum + N} passed={int((D.verdict == '成立').sum())}/{N}  (値 = Sharpe, 最悪月 %, 累積 %, 日数)"); print(D.to_string(index=False)); print("\n== 参照: 境目 25(判定に使わない) =="); print(RF.to_string(index=False))
    print("\n== VIX 別の平均 bps (本数) ==")
    for nm in ("金の保有(日次)", "USDJPY 逆張り(取引ごと)"):
        g = BK[BK.leg == nm]; order = ["VIX 15 未満", "VIX 15〜20", "VIX 20〜25", "VIX 25 超"]
        pv = (g.pivot(index="group", columns="window", values="mean_bps").reindex(order)[[w[0] for w in ALLW]].astype(str) + " (" + g.pivot(index="group", columns="window", values="n").reindex(order)[[w[0] for w in ALLW]].astype(str) + ")"); pv["t(全期間)"] = g[g.window == "全期間"].set_index("group").t.reindex(order).values; print(f"-- {nm} --"); print(pv.to_string())
