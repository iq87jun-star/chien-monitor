# -*- coding: utf-8 -*-
"""docs/244 Q235(改良系・7 セル・2026-11-16 登録「登録して実行」): VIX の横展開。
(I) 月曜の指数 5 本(US30・JP225・UK100・NAS100・US500・13 UTC 建て・常時 1.0 倍): 前金曜の VIX ≤ 25 の週は同日 20 UTC 決済、25 超は 24h。判定 = 常時 24h に対して 3 窓 + 累積 1/2 規則。
(G) GER40 のブレイクアウト(donchian 120・trail2ATR)× 前営業日の VIX: GA = VIX > 20 の日 1.0・以下 0.5、GB = 逆。判定 = 配備形に対して 3 窓。
使い方: cd research && python3 -W ignore queue/q235_vix_exit_mon_index_and_ger40_breakout.py <累積セル数>   出力: results/q235_vix_exit_mon_index_and_ger40_breakout.csv・_ref.csv・_night.csv"""
import sys, os
_ARGV = list(sys.argv)
from q_common import *
from q114_mon_index_intraday import stats
from q231_near_miss_rotation_and_state_exit import idx_frame, f_series, IDX
import q206_sma200_state_v4_usdjpy_ger40_breakout as q206
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END)); ALLW = WIN + (("全期間", PRE0, END),)
V = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data_ext", "VIX_History.csv")); V["d"] = pd.to_datetime(V["DATE"]); VIX = V.set_index("d")["CLOSE"].sort_index().astype(float)
def idx_vix_frame(s):
    x = idx_frame(s).copy(); x["vix"] = VIX.reindex(pd.DatetimeIndex(x.index) - pd.Timedelta(days=3), method="ffill").values; return x
def idx_series(s, kind="E1"):
    """kind = base(常時 24h)/ E1(前金曜 VIX ≤ 25 は同日 20 UTC・25 超は 24h)/ all20(常に 20 UTC)/ FE(Q231 の F に E1 を重ねる: 数量は線の下 1.0・上 0.5、24h は線の下 かつ VIX > 25 だけ)"""
    x = idx_vix_frame(s); hot = (x.vix > 25).fillna(False).values; lo = (x.d200 < 0).values
    r = {"base": x.r24.values, "E1": np.where(hot, x.r24, x.r20), "all20": x.r20.values, "FE": np.where(lo, 1.0, 0.5) * np.where(lo & hot, x.r24, x.r20)}[kind]; return pd.Series(r, index=x.index)
def ger_series(kind="GA", th=20.0):
    """GER40 ブレイクアウト(日次損益)× 前営業日の VIX。GA = VIX > th の日 1.0・以下 0.5、GB = 逆、base = 常に 1.0。"""
    r = q206.donchian("GER40", 120, "trail2ATR"); v = VIX.reindex(pd.DatetimeIndex(r.index).normalize() - pd.Timedelta(days=1), method="ffill").values; hot = v > th
    f = {"base": np.ones(len(r)), "GA": np.where(hot, 1.0, 0.5), "GB": np.where(hot, 0.5, 1.0)}[kind]; return r * f, v
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 7; rows = []; ref = []; night = []
    for s in IDX:
        b = idx_series(s, "base"); v = idx_series(s, "E1"); b_ = {w: stats(b, a, e) for w, a, e in WIN}; v_ = {w: stats(v, a, e) for w, a, e in WIN}
        ok = all(v_[w][0] > b_[w][0] and v_[w][1] >= b_[w][1] for w, _, _ in WIN); cum_ok = bool(v_["IS"][2] >= 0.5 * b_["IS"][2] and v_["OOS"][2] >= 0.5 * b_["OOS"][2])
        rows.append(dict(group="I 月曜の指数", cell=f"I {s}: VIX ≤ 25 の週は同日 20 UTC・25 超は 24h", base_PRE=b_["前窓"], var_PRE=v_["前窓"], base_IS=b_["IS"], var_IS=v_["IS"], base_OOS=b_["OOS"], var_OOS=v_["OOS"], verdict=("成立" if ok and cum_ok else ("成立だが累積 1/2 未満" if ok else "不成立"))))
        for kk, kn in (("all20", "常に 20 UTC"), ("FE", "F + E1(数量は線で・24h は線の下 × VIX > 25 だけ)")):
            x = idx_series(s, kk); ref.append(dict(kind=kn, symbol=s, PRE=stats(x, *WIN[0][1:]), IS=stats(x, *WIN[1][1:]), OOS=stats(x, *WIN[2][1:])))
        x = f_series(s, "F"); ref.append(dict(kind="F(Q231: 線の下 1.0・24h / 上 0.5・20 UTC)", symbol=s, PRE=stats(x, *WIN[0][1:]), IS=stats(x, *WIN[1][1:]), OOS=stats(x, *WIN[2][1:])))
        X = idx_vix_frame(s); X = X.assign(seg=(1 + X.r24) / (1 + X.r20) - 1)          # 夜の部分(20 UTC → 24h 後)。往復コストは両方に入っているので差し引きで消える
        for gn, m in (("VIX 15 未満", X.vix < 15), ("VIX 15〜20", (X.vix >= 15) & (X.vix < 20)), ("VIX 20〜25", (X.vix >= 20) & (X.vix < 25)), ("VIX 25 超", X.vix >= 25), ("VIX 25 以下", X.vix < 25)):
            for w, a, e in ALLW:
                y = X[m.values & (X.index >= a) & (X.index <= e)].seg; night.append(dict(symbol=s, group=gn, window=w, n=len(y), mean_bps=round(float(y.mean()) * 1e4, 1) if len(y) else None, t=round(float(y.mean() / y.std() * np.sqrt(len(y))), 2) if len(y) > 2 and y.std() > 0 else None))
    gb, gv = ger_series("base"); gb_ = {w: q206.stat(gb, a, e) for w, a, e in WIN}
    for k, nm in (("GA", "GA GER40 ブレイクアウト: VIX > 20 の日 1.0 倍・以下 0.5 倍"), ("GB", "GB GER40 ブレイクアウト: VIX ≤ 20 の日 1.0 倍・超 0.5 倍")):
        x, _ = ger_series(k); x_ = {w: q206.stat(x, a, e) for w, a, e in WIN}; ok = all(x_[w][0] > gb_[w][0] and x_[w][1] >= gb_[w][1] for w, _, _ in WIN)
        rows.append(dict(group="G GER40 ブレイクアウト", cell=nm, base_PRE=gb_["前窓"], var_PRE=x_["前窓"], base_IS=gb_["IS"], var_IS=x_["IS"], base_OOS=gb_["OOS"], var_OOS=x_["OOS"], verdict=("成立" if ok else "不成立")))
    G = pd.DataFrame({"r": gb.values, "vix": gv}, index=gb.index); G = G[G.r != 0]
    for gn, m in (("VIX 15 未満", G.vix < 15), ("VIX 15〜20", (G.vix >= 15) & (G.vix < 20)), ("VIX 20〜25", (G.vix >= 20) & (G.vix < 25)), ("VIX 25 超", G.vix >= 25)):
        for w, a, e in ALLW:
            y = G[m.values & (G.index >= a) & (G.index <= e)].r; night.append(dict(symbol="GER40 ブレイクアウト(日次・建玉のある日)", group=gn, window=w, n=len(y), mean_bps=round(float(y.mean()) * 1e4, 1) if len(y) else None, t=round(float(y.mean() / y.std() * np.sqrt(len(y))), 2) if len(y) > 2 and y.std() > 0 else None))
    D = pd.DataFrame(rows); D.to_csv("results/q235_vix_exit_mon_index_and_ger40_breakout.csv", index=False); RF = pd.DataFrame(ref); RF.to_csv("results/q235_vix_exit_mon_index_and_ger40_breakout_ref.csv", index=False); NG = pd.DataFrame(night); NG.to_csv("results/q235_vix_exit_mon_index_and_ger40_breakout_night.csv", index=False)
    pd.set_option("display.width", 340); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 400); pd.set_option("display.max_colwidth", 70)
    print(f"Q235: cells={N} cum_before={cum} cum_after={cum + N} passed={int((D.verdict == '成立').sum())}/{N}  (値 = Sharpe, 最悪月 %, 累積 %[, 日数])"); print(D.to_string(index=False)); print("\n== 参照(判定に使わない) =="); print(RF.sort_values(["symbol", "kind"]).to_string(index=False))
    print("\n== VIX 別の平均 bps (本数): 指数 = 夜の部分(月曜 20 UTC → 24h 後)、GER40 = 建玉のある日の日次損益 ==")
    for s in list(IDX) + ["GER40 ブレイクアウト(日次・建玉のある日)"]:
        g = NG[NG.symbol == s]; order = [x for x in ("VIX 15 未満", "VIX 15〜20", "VIX 20〜25", "VIX 25 超", "VIX 25 以下") if x in set(g.group)]
        pv = (g.pivot(index="group", columns="window", values="mean_bps").reindex(order)[[w[0] for w in ALLW]].astype(str) + " (" + g.pivot(index="group", columns="window", values="n").reindex(order)[[w[0] for w in ALLW]].astype(str) + ")"); pv["t(全期間)"] = g[g.window == "全期間"].set_index("group").t.reindex(order).values; print(f"-- {s} --"); print(pv.to_string())
