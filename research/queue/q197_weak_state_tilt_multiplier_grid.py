# -*- coding: utf-8 -*-
"""docs/244 Q197(診断・セル 0・2026-11-13 登録「登録して実行」): 200 日線の状態で数量を変える形 × 全体の倍率の再調整。
口座モデル = Q188。寄せ方 T0 現行(1.0 / 1.0)・T1 減らすだけ(弱い 1.0 / それ以外 0.5)・T2 寄せる(1.5 / 0.5)× 全体の倍率 s ∈ {1.0..2.0}(月曜レグ全体)。
窓 W1 = 2021-08-01〜2026-07-31(規則を作った期間と重なる)・W2 = 2016-11-01〜2021-07-31(独立の確認)。
判定: 同じ (寄せ方, s) が両窓で、安値・終値の両判定について 到達率 ≥ 現行 + 2pt・失格率 ≤ 現行・中央週数 ≤ 現行の 1.5 倍 → 変更候補。
使い方: cd research && python3 -W ignore queue/q197_weak_state_tilt_multiplier_grid.py   出力: results/q197_weak_state_tilt_multiplier_grid.csv・_pick.csv・_guard_by_state.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
src = open(os.path.join(HERE, "q188_skew_gate_guard_model.py"), encoding="utf-8").read().split('if __name__ == "__main__":')[0]
ns = {"__name__": "q188_head", "__file__": os.path.join(HERE, "q188_skew_gate_guard_model.py")}; exec(compile(src, "q188_head", "exec"), ns)
cfg, table, us_dst, G, K, run_guard, account_items, scenes, mc, skew_gate_dates = (ns[k] for k in ("cfg", "table", "us_dst", "G", "K", "run_guard", "account_items", "scenes", "mc", "skew_gate_dates"))
from q196_weak_state_only_near_miss import weak_flags, states_h1, RULES
WFN = RULES[0][1]; assert RULES[0][0] == "終値 < SMA200"
WINS = (("W1 2021-08〜2026-07", pd.Timestamp("2021-08-01"), pd.Timestamp("2026-07-31")), ("W2 2016-11〜2021-07", pd.Timestamp("2016-11-01"), pd.Timestamp("2021-07-31")))
TILTS = (("T0 現行", 1.0, 1.0), ("T1 減らすだけ(1.0 / 0.5)", 1.0, 0.5), ("T2 寄せる(1.5 / 0.5)", 1.5, 0.5)); SCALES = (1.0, 1.2, 1.4, 1.6, 1.8, 2.0)
SKEW_ON = {"531343523", "531466484", "14074882"}; PRK = skew_gate_dates()
def paths_fac(items, cap, fac, p0, p1):
    parts = []
    for s, idxf, w in items:
        Mt, res = table(s, idxf); Rk = res[K]; p = Mt.copy(); p["w"] = w / p.nshots
        if (s, idxf) in fac: p["w"] = p.w * p.date.map(lambda d: fac[(s, idxf)].get(d, 1.0)).values
        p["risk_w"] = p.w * Rk["risk"]; p["stop"] = Rk["stop"]; p["i"] = np.arange(len(p)); p["key"] = f"{s}|{idxf}"; parts.append(p)
    S = pd.concat(parts); S = S[(S.date >= p0) & (S.date <= p1)].sort_values(["date", "t"]).reset_index(drop=True); f = np.ones(len(S))
    if cap:
        C, V = cap
        for d, g in S.groupby("date"):
            used = []
            for i in g.index:
                r = S.risk_w[i]
                if r <= 0: f[i] = 0.0; continue
                room = C - sum(x for stp, x in used if V == "B" or stp > S.off[i]); fi = 1.0 if r <= room else (room / r if room >= 0.1 * r else 0.0); f[i] = fi; used.append((S.stop[i], r * fi))
    S["wf"] = S.w * f; out = []
    for d, g in S.groupby("date"):
        gb = (21 if us_dst(d) else 22) - 4; tot = {"lo": np.zeros(G), "cl": np.zeros(G)}; met = {"lo": np.zeros(G), "cl": np.zeros(G)}
        for key, gg in g.groupby("key"):
            s, idxs = key.split("|"); Rk = table(s, idxs == "True")[1][K]
            for i, wf, off, stp in zip(gg.i.values, gg.wf.values, gg.off.values, gg.stop.values):
                if wf == 0: continue
                close = int(min(stp, off + 24))
                for tag, arr in (("lo", Rk["worst"][i]), ("cl", Rk["mark"][i])):
                    a = arr * wf; tot[tag] += a; bb = a.copy()
                    if close < gb: bb[gb:] = 0.0
                    met[tag] += bb
        out.append(dict(d=d, gb=gb, tot=tot, met=met, fin=float(tot["cl"][-1])))
    return out
def scaled(P, s): return [dict(d=p["d"], gb=p["gb"], tot={k: v * s for k, v in p["tot"].items()}, met={k: v * s for k, v in p["met"].items()}, fin=p["fin"] * s) for p in P]
rows = []; gs = []
for a in cfg["accounts"]:
    aid, items, cap, g = account_items(a); fx = [(s, w) for s, idxf, w in items if not idxf]; sc = scenes(a, aid)
    if not fx or not sc: continue
    mdd = float(a["mdd"]); flags = {}; skf = {}
    for s, w in fx:
        dts = [pd.Timestamp(d) for d in table(s, False)[0].date.unique()]; hit, valid = weak_flags(s, states_h1, dts, WFN); flags[s] = {d: bool(h and v) for d, h, v in zip(dts, hit, valid)}
        if aid in SKEW_ON:
            pr = PRK.reindex(pd.DatetimeIndex(dts) - pd.Timedelta(days=3), method="ffill").values; skf[s] = {d: 0.0 for d, p in zip(dts, pr) if p == p and p > 0.8}
    def fac_for(hi, lo): return {(s, False): {d: skf.get(s, {}).get(d, 1.0) * (hi if wk else lo) for d, wk in flags[s].items()} for s, w in fx}
    for wn, p0, p1 in WINS:
        for tn, hi, lo in TILTS:
            fac = fac_for(hi, lo); P1_ = None if cap else paths_fac(items, cap, fac, p0, p1)
            for s_ in SCALES:
                P = scaled(P1_, s_) if P1_ is not None else paths_fac([(sy, ix, w * s_) for sy, ix, w in items], cap, fac, p0, p1)
                R = run_guard(P, g); base = dict(acct=a["name"][:20], window=wn, tilt=tn, scale=s_, guard_pct=round(g * 100, 1), mondays=len(P))
                for tag in ("lo", "cl"): base[f"mean_bps_{tag}"] = round(float(R[tag][0].mean()) * 1e4, 1); base[f"hits_{tag}"] = int(R[tag][1].sum())
                for nm, start, target in sc:
                    r = dict(base, scen=nm)
                    for tag in ("lo", "cl"):
                        rng = np.random.default_rng(187); reach, fail, med, r8 = mc(R[tag][0], R[tag][1], R[tag][2], start, target, -mdd, rng); r.update({f"reach_{tag}": reach, f"fail_{tag}": fail, f"weeks_{tag}": med})
                    rows.append(r)
                if tn.startswith("T0") and s_ == 1.0:                 # 診断: ガード発動を弱い状態の月曜 / それ以外に分ける
                    wsum = sum(w for _, w in fx); share = np.array([sum(w for s, w in fx if flags[s].get(p["d"], False)) / wsum for p in P]); wk = share >= 0.5
                    for tag in ("lo", "cl"):
                        fr = R[tag][1].astype(bool); pn = R[tag][0]
                        gs.append(dict(acct=a["name"][:20], window=wn, judge=tag, mondays=len(P), weak_mondays=int(wk.sum()), hits_weak=int(fr[wk].sum()), hits_other=int(fr[~wk].sum()), hit_rate_weak=round(float(fr[wk].mean()) * 100, 1) if wk.any() else np.nan, hit_rate_other=round(float(fr[~wk].mean()) * 100, 1),
                                       mean_weak_bps=round(float(pn[wk].mean()) * 1e4, 1) if wk.any() else np.nan, mean_other_bps=round(float(pn[~wk].mean()) * 1e4, 1), worst_weak_pct=round(float(pn[wk].min()) * 100, 2) if wk.any() else np.nan, worst_other_pct=round(float(pn[~wk].min()) * 100, 2)))
    print(a["name"][:20], "done", flush=True)
D = pd.DataFrame(rows); D.to_csv("results/q197_weak_state_tilt_multiplier_grid.csv", index=False); GS = pd.DataFrame(gs); GS.to_csv("results/q197_weak_state_tilt_multiplier_grid_guard_by_state.csv", index=False)
W1n, W2n = WINS[0][0], WINS[1][0]; picks = []
def okrow(x, cur): return bool(x.reach_lo >= cur.reach_lo + 2 and x.reach_cl >= cur.reach_cl + 2 and x.fail_lo <= cur.fail_lo and x.fail_cl <= cur.fail_cl and x.weeks_lo is not None and cur.weeks_lo is not None and x.weeks_lo <= 1.5 * cur.weeks_lo)
for (acct, scn), g_ in D.groupby(["acct", "scen"], sort=False):
    res = {}; cur = {}
    for wn in (W1n, W2n):
        gw = g_[g_.window == wn]; cur[wn] = gw[(gw.tilt.str.startswith("T0")) & (gw.scale == 1.0)].iloc[0]; res[wn] = {(x.tilt, x.scale): x for x in gw.itertuples() if okrow(x, cur[wn])}
    both = [k for k in res[W1n] if k in res[W2n]]; best = max(both, key=lambda k: res[W2n][k].reach_lo) if both else None
    def bestof(wn): return max(res[wn].values(), key=lambda x: x.reach_lo) if res[wn] else None
    b1, b2 = bestof(W1n), bestof(W2n)
    picks.append(dict(acct=acct, scen=scn, cur_W1=f"{cur[W1n].reach_lo}/{cur[W1n].reach_cl} f{cur[W1n].fail_lo}/{cur[W1n].fail_cl} w{cur[W1n].weeks_lo}", cur_W2=f"{cur[W2n].reach_lo}/{cur[W2n].reach_cl} f{cur[W2n].fail_lo}/{cur[W2n].fail_cl} w{cur[W2n].weeks_lo}",
                      verdict=("変更候補" if best else ("参考(片方の窓のみ)" if (b1 or b2) else "現行維持")), combo=(f"{best[0]} × {best[1]}" if best else "—"),
                      combo_W1=(f"{res[W1n][best].reach_lo}/{res[W1n][best].reach_cl} f{res[W1n][best].fail_lo}/{res[W1n][best].fail_cl} w{res[W1n][best].weeks_lo}" if best else "—"), combo_W2=(f"{res[W2n][best].reach_lo}/{res[W2n][best].reach_cl} f{res[W2n][best].fail_lo}/{res[W2n][best].fail_cl} w{res[W2n][best].weeks_lo}" if best else "—"),
                      n_ok_W1=len(res[W1n]), n_ok_W2=len(res[W2n]), best_W1=(f"{b1.tilt} × {b1.scale}: {b1.reach_lo}/{b1.reach_cl} f{b1.fail_lo}/{b1.fail_cl}" if b1 else "—"), best_W2=(f"{b2.tilt} × {b2.scale}: {b2.reach_lo}/{b2.reach_cl} f{b2.fail_lo}/{b2.fail_cl}" if b2 else "—")))
Pk = pd.DataFrame(picks); Pk.to_csv("results/q197_weak_state_tilt_multiplier_grid_pick.csv", index=False)
pd.set_option("display.width", 400); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 800); pd.set_option("display.max_colwidth", 70)
print("\n== 判定 ==\n" + Pk.to_string(index=False)); print("\n== ガード発動(現行・弱い状態の月曜 / それ以外) ==\n" + GS.to_string(index=False))
print("\n== 全行 ==\n" + D[["acct", "window", "scen", "tilt", "scale", "mean_bps_lo", "hits_lo", "reach_lo", "reach_cl", "fail_lo", "fail_cl", "weeks_lo"]].to_string(index=False))
