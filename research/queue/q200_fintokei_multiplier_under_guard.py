# -*- coding: utf-8 -*-
"""docs/244 Q200(診断・セル 0・2026-11-14 登録「登録して実行」): Fintokei 3 口座の月曜枠の倍率をガード込みで決め直す。
倍率 = 現行の評価中の倍率 × s(s ∈ 0.25〜1.25 の 8 段階)。V0 縮小なし / V3 = 200 日線の上にいる通貨 0.5 倍 + 損失枠比例(下限 0.5)(トパーズは SKEW の見送りも)。
場面 A: ゼロ → +6%(失格 −10%)。場面 B: 本口座 1 年(目標なし・失格 −10%・出金なし)。窓 W1 = 2021-08〜2026-07・W2 = 2016-11〜2021-07。補助: 実際の順序での年率。
モデル = Q188 の H1 経路 + Q198 の状態依存 MC(月曜レグのみ)。
使い方: cd research && python3 -W ignore queue/q200_fintokei_multiplier_under_guard.py   出力: results/q200_fintokei_multiplier_under_guard.csv・_pick.csv・_seq.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
src = open(os.path.join(HERE, "q198_weak_tilt_plus_buffer_sizing.py"), encoding="utf-8").read().split("\nrows = []\nfor a in cfg")[0]
ns = {"__name__": "q198_head", "__file__": os.path.join(HERE, "q198_weak_tilt_plus_buffer_sizing.py")}; exec(compile(src, "q198_head", "exec"), ns)
cfg, table, run_guard, account_items, paths_fac, scaled, weak_flags, states_h1, WFN, WINS, GRID, N, WEEKS, PRK = (ns[k] for k in ("cfg", "table", "run_guard", "account_items", "paths_fac", "scaled", "weak_flags", "states_h1", "WFN", "WINS", "GRID", "N", "WEEKS", "PRK"))
TARGET = {"6104739": "トパーズ", "6104736": "ルビー", "6071612": "パール"}; SCALES = (0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0, 1.25); PLAN = {"6104739": 0.75, "6104736": 1.0, "6071612": 1.0}
def mc2(T, target, mdd, smin, seed=187):
    """状態依存 MC。target=None なら 52 週の損益(失格は −mdd で確定)を返す。"""
    pnl, fired, peak = T; n = pnl.shape[1]; rng = np.random.default_rng(seed); c = np.zeros(N); alive = np.ones(N, bool); res = np.zeros(N, int); wk = np.zeros(N, int); fires = np.zeros(N, int)
    for w in range(WEEKS):
        if w % 4 == 0: fires[:] = 0
        idx = rng.integers(0, n, N)
        if smin is None: gi = np.full(N, len(GRID) - 1)
        else: s = np.clip((c + mdd) / mdd, smin, 1.0); gi = np.abs(GRID[None, :] - s[:, None]).argmin(axis=1)
        act = alive & (fires < 2); x = np.where(act, pnl[gi, idx], 0.0); pk = np.where(act, peak[gi, idx], -1.0); f = np.where(act, fired[gi, idx], 0)
        if target is not None:
            hit = alive & ((c + pk >= target) | (c + x >= target)); c = c + x; res[hit] = 1; wk[hit] = w + 1; alive &= ~hit
        else: c = c + x
        fires += f; dead = alive & (c <= -mdd); res[dead] = 2; alive &= ~dead
    if target is not None:
        ok = res == 1; return dict(reach=round(float(ok.mean()) * 100, 1), fail=round(float((res == 2).mean()) * 100, 1), weeks=(int(np.median(wk[ok])) if ok.any() else None))
    c = np.where(res == 2, -mdd, c); return dict(fail=round(float((res == 2).mean()) * 100, 1), mean=round(float(c.mean()) * 100, 1), med=round(float(np.median(c)) * 100, 1), p05=round(float(np.quantile(c, .05)) * 100, 1))
rows = []; seq = []
for a in cfg["accounts"]:
    aid, items, cap, g = account_items(a)
    if aid not in TARGET: continue
    mdd = float(a["mdd"]); tgt = float(a["targets"][1]); fx = [(s, w) for s, idxf, w in items if not idxf]; fxm = sum(w for _, w in fx); idm = sum(w for s, idxf, w in items if idxf); flags = {}; skf = {}
    for s, w in fx:
        dts = [pd.Timestamp(d) for d in table(s, False)[0].date.unique()]; hit, valid = weak_flags(s, states_h1, dts, WFN); flags[s] = {d: bool(h and v) for d, h, v in zip(dts, hit, valid)}
        pr = PRK.reindex(pd.DatetimeIndex(dts) - pd.Timedelta(days=3), method="ffill").values; skf[s] = {d: 0.0 for d, p in zip(dts, pr) if p == p and p > 0.8}
    def fac_for(tilt, skew): return {(s, False): {d: (skf[s].get(d, 1.0) if skew else 1.0) * (1.0 if (wk or not tilt) else 0.5) for d, wk in flags[s].items()} for s, w in fx}
    for wn, p0, p1 in WINS:
        for vn, tilt, skew, smin in (("V0 縮小なし", False, False, None), ("V3 2 つの縮小", True, aid == "6104739", 0.5)):
            P1_ = paths_fac(items, cap, fac_for(tilt, skew), p0, p1)
            for s_ in SCALES:
                out = {"lo": [], "cl": []}
                for lv in GRID:
                    R = run_guard(scaled(P1_, lv * s_), g)
                    for tag in ("lo", "cl"): out[tag].append(R[tag][:3])
                T = {tag: tuple(np.array([x[i] for x in out[tag]]) for i in range(3)) for tag in out}; R1 = run_guard(scaled(P1_, s_), g)
                r = dict(acct=TARGET[aid], window=wn, variant=vn, s=s_, fx_mult=round(fxm * s_, 2), idx_mult=round(idm * s_, 2), per1x_room_pct=round(g / ((fxm + idm) * s_) * 100, 2), hits_lo=int(R1["lo"][1].sum()), mean_bps_lo=round(float(R1["lo"][0].mean()) * 1e4, 1), mean_bps_cl=round(float(R1["cl"][0].mean()) * 1e4, 1))
                for tag in ("lo", "cl"):
                    A_ = mc2(T[tag], tgt, mdd, smin); B_ = mc2(T[tag], None, mdd, smin)
                    r.update({f"A_reach_{tag}": A_["reach"], f"A_fail_{tag}": A_["fail"], f"A_weeks_{tag}": A_["weeks"], f"B_fail_{tag}": B_["fail"], f"B_mean_{tag}": B_["mean"], f"B_med_{tag}": B_["med"], f"B_p05_{tag}": B_["p05"]})
                rows.append(r)
    # 補助: 実際の順序(200 日線の縮小のみ・損失枠比例なし)
    for pn, p0, p1 in (("2023-08〜2026-07", pd.Timestamp("2023-08-01"), pd.Timestamp("2026-07-31")), ("2016-11〜2021-07", pd.Timestamp("2016-11-01"), pd.Timestamp("2021-07-31"))):
        yrs = (p1 - p0).days / 365.25
        for vn, tilt, skew in (("V0 縮小なし", False, False), ("200 日線の縮小" + ("+ SKEW" if aid == "6104739" else ""), True, aid == "6104739")):
            P1_ = paths_fac(items, cap, fac_for(tilt, skew), p0, p1); ds = [p["d"] for p in P1_]
            for s_ in SCALES:
                R = run_guard(scaled(P1_, s_), g); o = dict(acct=TARGET[aid], period=pn, variant=vn, s=s_, fx_mult=round(fxm * s_, 2))
                for tag in ("lo", "cl"):
                    pnl, fired = R[tag][0], R[tag][1]; fm = {}; wk = []; nf = 0
                    for d, x, f in zip(ds, pnl, fired):
                        ym = (pd.Timestamp(d).year, pd.Timestamp(d).month)
                        if fm.get(ym, 0) >= 2: wk.append(0.0); continue
                        fm[ym] = fm.get(ym, 0) + int(f); nf += int(f); wk.append(float(x))
                    cum = np.cumsum(wk); dd = float((cum - np.maximum.accumulate(np.maximum(cum, 0))).min())
                    o.update({f"ann_{tag}": round(float(cum[-1]) / yrs * 100, 1), f"fires_{tag}": nf, f"dd_{tag}": round(dd * 100, 1)})
                seq.append(o)
    print(TARGET[aid], "done", flush=True)
D = pd.DataFrame(rows); D.to_csv("results/q200_fintokei_multiplier_under_guard.csv", index=False); Sq = pd.DataFrame(seq); Sq.to_csv("results/q200_fintokei_multiplier_under_guard_seq.csv", index=False); picks = []
for acct, g_ in D[D.variant.str.startswith("V3")].groupby("acct", sort=False):
    aid = [k for k, v in TARGET.items() if v == acct][0]; tab = []
    for s_, x in g_.groupby("s"):
        w1, w2 = x[x.window == "W1"].iloc[0], x[x.window == "W2"].iloc[0]; rmin = min(w1.A_reach_lo, w1.A_reach_cl, w2.A_reach_lo, w2.A_reach_cl); fmax = max(w1.A_fail_lo, w1.A_fail_cl, w2.A_fail_lo, w2.A_fail_cl)
        tab.append(dict(s=s_, fx_mult=w1.fx_mult, reach_min=rmin, fail_max=fmax, weeks_w2=w2.A_weeks_lo, ok=bool(w2.A_weeks_lo is not None and w2.A_weeks_lo == w2.A_weeks_lo and w2.A_weeks_lo <= 26)))
    Tb = pd.DataFrame(tab); ok = Tb[Tb.ok]; top = ok.reach_min.max(); cand = ok[ok.reach_min >= top - 1.0].sort_values(["fail_max", "reach_min"], ascending=[True, False]); best = cand.iloc[0]; plan = Tb[Tb.s == PLAN[aid]].iloc[0]
    verdict = "予定どおり" if (best.reach_min - plan.reach_min) < 2.0 else f"変更候補: s {best.s}(月曜の円クロス {best.fx_mult} 倍)"
    picks.append(dict(acct=acct, plan_s=PLAN[aid], plan_reach_min=plan.reach_min, plan_fail_max=plan.fail_max, plan_weeks_w2=plan.weeks_w2, best_s=best.s, best_fx_mult=best.fx_mult, best_reach_min=best.reach_min, best_fail_max=best.fail_max, best_weeks_w2=best.weeks_w2, verdict=verdict))
Pk = pd.DataFrame(picks); Pk.to_csv("results/q200_fintokei_multiplier_under_guard_pick.csv", index=False)
pd.set_option("display.width", 330); pd.set_option("display.max_columns", 50); pd.set_option("display.max_rows", 500)
print("\n== 推奨(場面 A・V3) ==\n" + Pk.to_string(index=False))
print("\n== 場面 A / B ==\n" + D[["acct", "window", "variant", "s", "fx_mult", "per1x_room_pct", "hits_lo", "mean_bps_lo", "A_reach_lo", "A_reach_cl", "A_fail_lo", "A_fail_cl", "A_weeks_lo", "B_fail_lo", "B_mean_lo", "B_med_lo", "B_mean_cl", "B_p05_lo"]].to_string(index=False))
print("\n== 実際の順序 ==\n" + Sq.to_string(index=False))
