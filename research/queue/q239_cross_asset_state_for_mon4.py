# -*- coding: utf-8 -*-
"""docs/244 Q239(改良系・6 セル・2026-11-16 登録「登録して実行」): 別銘柄の値動きを月曜の円クロス(配備形 Mon4)の判断に加える。数量は配備形のまま(S1 を除く)。
C1 = 金曜の US500 日次 ≤ −1% の週は 24h・それ以外は同日 20 UTC。C2 = 金曜の VIX 前日比 ≥ +2pt の週は 24h。C3 = VIX > 25 または 金曜 US500 ≤ −1% の週は 24h。
D1 = 月曜 13 → 20 UTC の US500 がマイナスなら 24h・プラスなら 20 UTC(H1 が無い週は 24h)。D2 = その通貨の月曜の建玉が 20 UTC 時点でマイナスなら 24h・プラスなら 20 UTC。S1 = 金曜 US500 ≥ +1% の週は月曜の円クロス × 0.5。
判定 = 配備形 Mon4 に対して 前窓・IS・OOS の 3 つすべてで Sharpe 改善 かつ 最悪月が悪化しない。E1(VIX > 25 の週だけ 24h)を 3 窓の Sharpe で上回るかを併記。
金曜の US500 = CFD の H1 から作った日足(終値 → 終値)。H1 が無い期間は日足ファイルで補う。
使い方: cd research && python3 -W ignore queue/q239_cross_asset_state_for_mon4.py <累積セル数>   出力: results/q239_cross_asset_state_for_mon4.csv・_parts.csv"""
import sys, os
_ARGV = list(sys.argv)
from q_common import *
from q147_roll_rate_diff_gate import stats
from q194_mon_own_technical_state_gate import daily_close
from q238_late_entry_after_high_vix_and_short_nights import fx_frame
from q237_night_leg_after_high_vix import VIX, TH
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END)); ALLW = WIN + (("全期間", PRE0, END),)
def signals(dates):
    """月曜の日付ごとの手がかり。spx_fri = 月曜より前の最後の営業日の US500 日次、dvix = 同 VIX の前日比(pt)、spx_mon = 月曜 13 → 20 UTC の US500、jp_am = 月曜 04 UTC の JP225 の金曜終値比。"""
    d = pd.DatetimeIndex(dates); c1 = daily_close("US500").pct_change(); c0 = base.load_daily("US500")["close"].pct_change(); r = pd.concat([c0[c0.index < c1.dropna().index.min()], c1.dropna()]).sort_index()
    o = load("US500")["open"]; m13 = o.reindex(d + pd.Timedelta(hours=13)).values; m20 = o.reindex(d + pd.Timedelta(hours=20)).values
    hj = load("JP225"); jc = hj["close"]; jo = hj["open"]; jfri = jc.reindex(d - pd.Timedelta(hours=1), method="ffill").values; jam = jo.reindex(d + pd.Timedelta(hours=4)).values; jage = (d - pd.Timedelta(hours=1)) - pd.DatetimeIndex(jc.index.to_series().reindex(d - pd.Timedelta(hours=1), method="ffill").values)
    jp = np.where(np.asarray(jage) <= np.timedelta64(4, "D"), jam / jfri - 1, np.nan)
    return pd.DataFrame({"spx_fri": r.reindex(d - pd.Timedelta(days=1), method="ffill").values, "dvix": VIX.diff().reindex(d - pd.Timedelta(days=1), method="ffill").values, "spx_mon": m20 / m13 - 1, "jp_am": jp}, index=d)
def frame():
    P = fx_frame(); S = signals(sorted(set(P.index)))
    for c in S.columns: P[c] = S[c].reindex(P.index).values
    return P
def hold_mask(P, kind):
    if kind == "base": return np.ones(len(P), bool)
    if kind == "E1": return P.hot.values
    if kind == "C1": return (P.spx_fri <= -0.01).fillna(False).values
    if kind == "C2": return (P.dvix >= 2.0).fillna(False).values
    if kind == "C3": return P.hot.values | (P.spx_fri <= -0.01).fillna(False).values
    if kind == "D1": return ~(P.spx_mon > 0).fillna(False).values          # プラスのときだけ 20 UTC。H1 なし(NaN)は 24h
    if kind == "D2": return (P.r20 < 0).values
    if kind == "D2m": return (P.r20 > 0).values                            # 参照: 鏡像
    if kind == "D1m": return (P.spx_mon > 0).fillna(True).values           # 参照: 鏡像
    raise ValueError(kind)
def series(P, kind):
    if kind == "S1": f = P.f.values * np.where((P.spx_fri >= 0.01).fillna(False).values, 0.5, 1.0); return pd.Series(P.r24.values * f * 0.25, index=P.index).groupby(level=0).sum()
    h = hold_mask(P, kind); return pd.Series(np.where(h, P.r24, P.r20) * P.f.values * 0.25, index=P.index).groupby(level=0).sum()
def mon4_cross_asset(kind="C3"):
    """紙上候補用。index = 月曜。"""
    return series(frame(), kind)
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 6; P = frame(); B = series(P, "base"); E1 = series(P, "E1"); bs = {w: stats(B, a, b) for w, a, b in WIN}; es = {w: stats(E1, a, b) for w, a, b in WIN}; rows = []; parts = []
    LAB = {"C1": "C1 金曜の US500 ≤ −1% の週は 24h・それ以外は 20 UTC", "C2": "C2 金曜の VIX が前日比 +2pt 以上の週は 24h・それ以外は 20 UTC", "C3": "C3 VIX > 25 または 金曜 US500 ≤ −1% の週は 24h", "D1": "D1 月曜 13 → 20 UTC の US500 がマイナスなら 24h・プラスなら 20 UTC", "D2": "D2 通貨の月曜の建玉が 20 UTC 時点でマイナスなら 24h・プラスなら 20 UTC", "S1": "S1 金曜 US500 ≥ +1% の週は月曜の円クロス × 0.5"}
    for k in ("C1", "C2", "C3", "D1", "D2", "S1"):
        v = series(P, k); vs = {w: stats(v, a, b) for w, a, b in WIN}; share = (float(hold_mask(P, k).mean()) if k != "S1" else float((P.spx_fri >= 0.01).mean()))
        rows.append(dict(cell=LAB[k], share=round(share, 3), base_PRE=bs["前窓"], var_PRE=vs["前窓"], base_IS=bs["IS"], var_IS=vs["IS"], base_OOS=bs["OOS"], var_OOS=vs["OOS"], verdict=("成立" if all(vs[w][0] > bs[w][0] and vs[w][1] >= bs[w][1] for w, _, _ in WIN) else "不成立"), beats_E1_sharpe_3win=bool(all(vs[w][0] > es[w][0] for w, _, _ in WIN))))
    D = pd.DataFrame(rows); D.to_csv("results/q239_cross_asset_state_for_mon4.csv", index=False)
    ref = [dict(variant="参照 E1(VIX > 25 の週だけ 24h)", share=round(float(P.hot.mean()), 3), PRE=es["前窓"], IS=es["IS"], OOS=es["OOS"])]
    for k, nm in (("D1m", "参照 D1 の鏡像(US500 がプラスなら 24h)"), ("D2m", "参照 D2 の鏡像(建玉がプラスなら 24h)")):
        v = series(P, k); ref.append(dict(variant=nm, share=round(float(hold_mask(P, k).mean()), 3), PRE=stats(v, *WIN[0][1:]), IS=stats(v, *WIN[1][1:]), OOS=stats(v, *WIN[2][1:])))
    RF = pd.DataFrame(ref)
    G = [("金曜 US500 ≤ −1%", (P.spx_fri <= -0.01).fillna(False)), ("金曜 US500 −1〜+1%", ((P.spx_fri > -0.01) & (P.spx_fri < 0.01)).fillna(False)), ("金曜 US500 ≥ +1%", (P.spx_fri >= 0.01).fillna(False)), ("金曜 VIX 前日比 ≥ +2pt", (P.dvix >= 2.0).fillna(False)), ("金曜 VIX 前日比 < +2pt", (P.dvix < 2.0).fillna(False)),
         ("VIX ≤ 25 かつ 金曜 US500 ≤ −1%", (~P.hot) & (P.spx_fri <= -0.01).fillna(False)), ("VIX > 25 かつ 金曜 US500 > −1%", P.hot & (P.spx_fri > -0.01).fillna(False)), ("VIX > 25 かつ 金曜 US500 ≤ −1%", P.hot & (P.spx_fri <= -0.01).fillna(False)),
         ("月曜 13 → 20 UTC の US500 マイナス", (P.spx_mon < 0).fillna(False)), ("月曜 13 → 20 UTC の US500 プラス", (P.spx_mon > 0).fillna(False)), ("通貨の建玉が 20 UTC でマイナス", P.r20 < 0), ("通貨の建玉が 20 UTC でプラス", P.r20 > 0),
         ("月曜 04 UTC の日経が金曜比 −1% 以下", (P.jp_am <= -0.01).fillna(False)), ("月曜 04 UTC の日経が金曜比 −1〜+1%", ((P.jp_am > -0.01) & (P.jp_am < 0.01)).fillna(False)), ("月曜 04 UTC の日経が金曜比 +1% 以上", (P.jp_am >= 0.01).fillna(False))]
    for gn, m in G:
        for w, a, b in ALLW:
            x = P[m.values & (P.index >= a) & (P.index <= b)]
            for col, cn in (("rN", "夜(20 UTC → 元の決済)"), ("r24", "24 時間")):
                y = x[col]; parts.append(dict(group=gn, part=cn, window=w, n=len(y), mean_bps=round(float(y.mean()) * 1e4, 1) if len(y) else None, t=round(float(y.mean() / y.std() * np.sqrt(len(y))), 2) if len(y) > 2 and y.std() > 0 else None))
    PT = pd.DataFrame(parts); PT.to_csv("results/q239_cross_asset_state_for_mon4_parts.csv", index=False)
    pd.set_option("display.width", 360); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 400); pd.set_option("display.max_colwidth", 80)
    print(f"Q239: cells={N} cum_before={cum} cum_after={cum + N} passed={int((D.verdict == '成立').sum())}/{N}  (値 = Sharpe, 最悪月 %, 累積 %, 週数)"); print(D.to_string(index=False)); print("\n== 参照 =="); print(RF.to_string(index=False))
    print("\n== 条件ごとの平均 bps (本数)・コスト込み =="); order = [g[0] for g in G]
    for cn in ("夜(20 UTC → 元の決済)", "24 時間"):
        g = PT[PT.part == cn]; pv = (g.pivot(index="group", columns="window", values="mean_bps").reindex(order)[[w[0] for w in ALLW]].astype(str) + " (" + g.pivot(index="group", columns="window", values="n").reindex(order)[[w[0] for w in ALLW]].astype(str) + ")"); pv["t(全期間)"] = g[g.window == "全期間"].set_index("group").t.reindex(order).values; print(f"-- {cn} --"); print(pv.to_string())
