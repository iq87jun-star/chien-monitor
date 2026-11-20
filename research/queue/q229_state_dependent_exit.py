# -*- coding: utf-8 -*-
"""docs/244 Q229(改良系・5 セル・2026-11-15 登録): 200 日線 × VIX の状態を決済(保有時間)に使う。数量は変えず、決済時刻だけを建てる前の状態で決める。
月曜(基準 = 配備形 Mon4: 月曜 4/6/8/10 UTC 建て → 24h 後決済・線の下 1.0 倍・上 0.5 倍): M1 = 線の下は 48h。M2 = 線の下 かつ 前金曜 VIX > 25 は 48h。M3 = 線の上は同日 20 UTC。
水曜ロール(基準 = Roll5: 水曜 20 → 木曜 00 UTC・門 2.0pp): R1 = 線の下は木曜 06 UTC まで。R2 = 線の下 かつ 火曜 VIX > 20 は木曜 06 UTC まで。
往復 3pip・延長先の足が無い週は基準の時刻。判定 = 各基準に対して 前窓・IS・OOS の 3 つすべてで Sharpe 改善 かつ 最悪月が悪化しない。
使い方: cd research && python3 -W ignore queue/q229_state_dependent_exit.py <累積セル数>   出力: results/q229_state_dependent_exit.csv・_seg.csv"""
import sys, os
_ARGV = list(sys.argv)
from q_common import *
from q20_wed_swap_carry import rate_series
from q147_roll_rate_diff_gate import stats
from q194_mon_own_technical_state_gate import PAIRS as MON_PAIRS, states
from q205_roll5_sma200_state import PAIRS as ROLL_PAIRS, GATE, bars
from q228_roll5_vix_x_sma200_score import d200, VIX
import deployed_book as db
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END)); ALLW = WIN + (("全期間", PRE0, END),); HOURS = (4, 6, 8, 10); REF_H = (16, 18, 22)
def mon_frame():
    rows = []
    for s in MON_PAIRS:
        h = load(s); o = h["open"]; acc = {}
        for hh in HOURS:
            t = o.index[(o.index.dayofweek == 0) & (o.index.hour == hh)]; ok = (t + pd.Timedelta(hours=24)).isin(o.index); t = t[ok]; p0 = o.reindex(t).values; c = cost(s, p0)
            p24 = o.reindex(t + pd.Timedelta(hours=24)).values; p48 = o.reindex(t + pd.Timedelta(hours=48)).values; p20 = o.reindex(t.normalize() + pd.Timedelta(hours=20)).values
            r24 = p24 / p0 - 1 - c; r48 = np.where(np.isnan(p48), r24, p48 / p0 - 1 - c); r20 = np.where(np.isnan(p20), r24, p20 / p0 - 1 - c)
            d = pd.DataFrame({"r24": r24, "r48": r48, "r20": r20, "seg48": p48 / p24 - 1, "segN": p24 / p20 - 1, "n": 1.0}, index=t.normalize())
            for hx in REF_H: px = o.reindex(t.normalize() + pd.Timedelta(hours=hx)).values; d[f"r{hx}"] = np.where(np.isnan(px), r24, px / p0 - 1 - c)          # 参照用(判定に使わない)
            for k in d.columns: acc[k] = d[k] if k not in acc else acc[k].add(d[k], fill_value=0.0) if k not in ("seg48", "segN") else pd.concat([acc[k], d[k]])
        m = pd.DataFrame({k: acc[k] / len(HOURS) for k in ["r24", "r48", "r20"] + [f"r{hx}" for hx in REF_H]}).sort_index(); m["seg48"] = acc["seg48"].groupby(level=0).mean().reindex(m.index); m["segN"] = acc["segN"].groupby(level=0).mean().reindex(m.index)
        m = m[(m.index >= PRE0) & (m.index <= h.index.max())]; ref = db.mon_cell_h1(s).reindex(m.index); assert np.allclose(m.r24.values, ref.values, atol=1e-12), s          # 基準が配備形の系列と一致すること
        st = states(s).shift(1).reindex(m.index, method="ffill"); fri = pd.DatetimeIndex(m.index) - pd.Timedelta(days=3)
        m["sym"] = s; m["d200"] = st.sma200.values; m["vix"] = VIX.reindex(fri, method="ffill").values; rows.append(m)
    P = pd.concat(rows).sort_index(kind="stable"); P["f"] = np.where(P.d200.isna(), 1.0, np.where(P.d200 < 0, 1.0, 0.5)); P["below"] = (P.d200 < 0).fillna(False); P["above"] = (P.d200 >= 0).fillna(False); return P
def roll_frame():
    L = {}
    for s in ROLL_PAIRS:
        o = bars(s)["open"]; t = o.index[(o.index.dayofweek == 2) & (o.index.hour == 20)]; p0 = o.reindex(t).values; p4 = o.reindex(t + pd.Timedelta(hours=4)).values; p10 = o.reindex(t + pd.Timedelta(hours=10)).values
        ok = ~np.isnan(p4) & ~np.isnan(p0); t, p0, p4, p10 = t[ok], p0[ok], p4[ok], p10[ok]; c = cost(s, p0); r4 = -(p4 / p0 - 1) - c; r10 = np.where(np.isnan(p10), r4, -(p10 / p0 - 1) - c)
        L[s] = pd.DataFrame({"r4": r4, "r10": r10, "seg06": -(p10 / p4 - 1)}, index=t.normalize())
    days = pd.DatetimeIndex(sorted(set().union(*[set(L[s].index) for s in ROLL_PAIRS]))); jp = rate_series("JPY", days); tue = days - pd.Timedelta(days=1); vix = pd.Series(VIX.reindex(tue, method="ffill").values, index=days); vix[days > VIX.index.max() + pd.Timedelta(days=1)] = np.nan; rows = []
    for s in ROLL_PAIRS:
        x = L[s].copy(); x["sym"] = s; x["g"] = pd.Series(np.asarray(rate_series(s[:3], days) - jp >= GATE, bool), index=days).reindex(x.index).values; x["d200"] = d200(s, days).reindex(x.index).values; x["vix"] = vix.reindex(x.index).values; rows.append(x)
    P = pd.concat(rows).sort_index(kind="stable"); P["below"] = (P.d200 < 0).fillna(False); return P, days
def mon_series(P, kind="base"):
    r = P.r24.values
    if kind == "M1": r = np.where(P.below, P.r48, P.r24)
    if kind == "M2": r = np.where(P.below & (P.vix > 25).fillna(False), P.r48, P.r24)
    if kind == "M3": r = np.where(P.above, P.r20, P.r24)
    return (pd.Series(r * P.f.values * 0.25, index=P.index)).groupby(level=0).sum()
def roll_series(P, days, kind="base"):
    r = P.r4.values
    if kind == "R1": r = np.where(P.below, P.r10, P.r4)
    if kind == "R2": r = np.where(P.below & (P.vix > 20).fillna(False), P.r10, P.r4)
    return (pd.Series(r * P.g.values.astype(float), index=P.index)).groupby(level=0).sum().reindex(days).fillna(0.0) / len(ROLL_PAIRS)
def state_exit(kind):
    """紙上候補用: kind = M1 / M2 / M3(月曜・index = 月曜)または R1 / R2(ロール・index = 水曜)。"""
    if kind.startswith("M"): return mon_series(mon_frame(), kind)
    P, days = roll_frame(); return roll_series(P, days, kind)
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 5; PM = mon_frame(); PR, days = roll_frame(); rows = []
    LAB = {"M1": "M1 月曜: 線の下は 48 時間後に決済", "M2": "M2 月曜: 線の下 かつ 前金曜 VIX > 25 は 48 時間後", "M3": "M3 月曜: 線の上は同日 20 UTC に決済", "R1": "R1 ロール: 線の下は木曜 06 UTC まで", "R2": "R2 ロール: 線の下 かつ 火曜 VIX > 20 は木曜 06 UTC まで"}
    BM = mon_series(PM); BR = roll_series(PR, days); bsm = {w: stats(BM, a, b) for w, a, b in WIN}; bsr = {w: stats(BR, a, b) for w, a, b in WIN}
    for k in ("M1", "M2", "M3", "R1", "R2"):
        mon = k.startswith("M"); v = mon_series(PM, k) if mon else roll_series(PR, days, k); bs = bsm if mon else bsr; vs = {w: stats(v, a, b) for w, a, b in WIN}
        if mon: ch = float(((PM.below if k == "M1" else PM.below & (PM.vix > 25) if k == "M2" else PM.above)).mean())
        else: gg = PR[PR.g.astype(bool)]; ch = float((gg.below if k == "R1" else gg.below & (gg.vix > 20)).mean())
        rows.append(dict(cell=LAB[k], share_changed=round(ch, 3), base_PRE=bs["前窓"], var_PRE=vs["前窓"], base_IS=bs["IS"], var_IS=vs["IS"], base_OOS=bs["OOS"], var_OOS=vs["OOS"], sharpe_up_3win=bool(all(vs[w][0] > bs[w][0] for w, _, _ in WIN)), improved=bool(all(vs[w][0] > bs[w][0] and vs[w][1] >= bs[w][1] for w, _, _ in WIN))))
    D = pd.DataFrame(rows); D.to_csv("results/q229_state_dependent_exit.csv", index=False); pd.set_option("display.width", 340); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 500)
    print(f"Q229: cells={N} cum_before={cum} cum_after={cum + N} improved={int(D.improved.sum())}/{N}  月曜の末尾 {PM.index.max().date()}・ロールの末尾 {days.max().date()}  (値 = Sharpe, 最悪月 %, 累積 %, 建てた週)"); print("基準 月曜(配備形):", bsm); print("基準 ロール:", bsr); print(D.to_string(index=False))
    ref = []          # 参照(判定に使わない): M3 の決済時刻の前後と、全通貨を 20 UTC で決済する形
    for nm, rr in [(f"線の上は同日 {hx} UTC", np.where(PM.above, PM[f"r{hx}"], PM.r24)) for hx in (16, 18)] + [("線の上は同日 20 UTC(M3)", np.where(PM.above, PM.r20, PM.r24)), ("線の上は同日 22 UTC", np.where(PM.above, PM.r22, PM.r24)), ("全通貨を同日 20 UTC", PM.r20.values), ("線の下だけ同日 20 UTC(鏡像)", np.where(PM.below, PM.r20, PM.r24))]:
        v = pd.Series(rr * PM.f.values * 0.25, index=PM.index).groupby(level=0).sum(); ref.append(dict(variant=nm, PRE=stats(v, *WIN[0][1:]), IS=stats(v, *WIN[1][1:]), OOS=stats(v, *WIN[2][1:])))
    RF = pd.DataFrame(ref); RF.to_csv("results/q229_state_dependent_exit_ref.csv", index=False); print("\n== 参照(判定に使わない): 月曜・決済時刻の前後 ==\n" + RF.to_string(index=False))
    yr = pd.DataFrame({"base": BM, "M3": mon_series(PM, "M3")}); yr["y"] = yr.index.year; print("\n== 年ごとの累積 %(基準 / M3)と週次の標準偏差 bps ==\n" + yr.groupby("y").apply(lambda x: pd.Series({"base_%": round(float(((1 + x.base).prod() - 1) * 100), 2), "M3_%": round(float(((1 + x.M3).prod() - 1) * 100), 2), "base_sd": round(float(x.base.std() * 1e4), 1), "M3_sd": round(float(x.M3.std() * 1e4), 1)})).to_string())
    LB = [("線の上", lambda d: d >= 0), ("線の下 0〜3%", lambda d: (d < 0) & (d >= -0.03)), ("線の下 3% 超", lambda d: d < -0.03)]; VB = [("VIX 15 未満", 0, 15), ("15〜20", 15, 20), ("20〜25", 20, 25), ("25 超", 25, 999), ("全 VIX", 0, 999)]; seg = []
    SEGS = (("月曜: 24h 後 → 48h 後(買い)", PM, "seg48"), ("月曜: 20 UTC → 24h 後(買い・夜)", PM, "segN"), ("ロール 門あり: 木曜 00 → 06 UTC(売り)", PR[PR.g.astype(bool)], "seg06"), ("ロール 門なし: 木曜 00 → 06 UTC(売り)", PR, "seg06"))
    for nm, X, c in SEGS:
        X = X.dropna(subset=["d200", "vix", c])
        for w, a, b in ALLW:
            x = X[(X.index >= a) & (X.index <= b)]
            for ln, lf in LB + [("全通貨", lambda d: d == d)]:
                for vn, lo, hi in VB:
                    y = x[lf(x.d200) & (x.vix >= lo) & (x.vix < hi)][c]; seg.append(dict(segment=nm, window=w, line=ln, vix=vn, n=len(y), mean_bps=round(float(y.mean()) * 1e4, 1) if len(y) else None, win=round(float((y > 0).mean()) * 100, 0) if len(y) else None, sd_bps=round(float(y.std()) * 1e4, 1) if len(y) > 1 else None, t=round(float(y.mean() / y.std() * np.sqrt(len(y))), 2) if len(y) > 2 and y.std() > 0 else None))
    SG = pd.DataFrame(seg); SG.to_csv("results/q229_state_dependent_exit_seg.csv", index=False); print("\n== 数値化: 延長区間だけの値動き(コストなし。平均 bps (本数)) ==")
    for nm, _, _ in SEGS:
        for w in ("前窓", "IS", "OOS", "全期間"):
            g = SG[(SG.segment == nm) & (SG.window == w)]; idx = [l[0] for l in LB] + ["全通貨"]; cols = [v[0] for v in VB]; print(f"-- {nm}・{w} --")
            print((g.pivot(index="line", columns="vix", values="mean_bps").reindex(idx)[cols].astype(str) + " (" + g.pivot(index="line", columns="vix", values="n").reindex(idx)[cols].astype(str) + ")").to_string())
    print("\n== 全期間の t 値(行 = 線、列 = VIX) ==")
    for nm, _, _ in SEGS:
        g = SG[(SG.segment == nm) & (SG.window == "全期間")]; print(f"-- {nm} --"); print(g.pivot(index="line", columns="vix", values="t").reindex([l[0] for l in LB] + ["全通貨"])[[v[0] for v in VB]].to_string())
