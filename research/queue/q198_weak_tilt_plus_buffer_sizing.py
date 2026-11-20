# -*- coding: utf-8 -*-
"""docs/244 Q198(診断・セル 0・2026-11-13 登録「組み合わせ確認できますか」): 『減らすだけ(200 日線)』と『損失枠の残りに比例する縮小』の併用。
V0 現行 / V1 減らすだけ(円クロス・通貨ごと・SMA200 の下 1.0・それ以外 0.5)/ V2 損失枠比例(s = clamp((c − floor)/mdd, 0.5, 1)・0.125 刻み)/ V3 併用 / 参照 V3 × 1.2。
口座モデル = Q188 の経路 + Q192 の状態依存 MC。窓 W1 = 2021-08〜2026-07・W2 = 2016-11〜2021-07。
使い方: cd research && python3 -W ignore queue/q198_weak_tilt_plus_buffer_sizing.py   出力: results/q198_weak_tilt_plus_buffer_sizing.csv・_pick.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
src = open(os.path.join(HERE, "q188_skew_gate_guard_model.py"), encoding="utf-8").read().split('if __name__ == "__main__":')[0]
ns = {"__name__": "q188_head", "__file__": os.path.join(HERE, "q188_skew_gate_guard_model.py")}; exec(compile(src, "q188_head", "exec"), ns)
cfg, table, us_dst, G, K, run_guard, account_items, scenes, skew_gate_dates = (ns[k] for k in ("cfg", "table", "us_dst", "G", "K", "run_guard", "account_items", "scenes", "skew_gate_dates"))
from q196_weak_state_only_near_miss import weak_flags, states_h1, RULES
WFN = RULES[0][1]; assert RULES[0][0] == "終値 < SMA200"
WINS = (("W1", pd.Timestamp("2021-08-01"), pd.Timestamp("2026-07-31")), ("W2", pd.Timestamp("2016-11-01"), pd.Timestamp("2021-07-31")))
N, WEEKS = 20000, 52; GRID = np.array([0.5, 0.625, 0.75, 0.875, 1.0]); SKEW_ON = {"531343523", "531466484", "14074882"}; PRK = skew_gate_dates()
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
def mc_state(T, start, target, floor, mdd, smin, seed=187):
    """Q192 と同じ状態依存 MC。T = (pnl[L,n], fired[L,n], peak[L,n])(L = GRID の段階)。smin=None なら固定 1.0(最後の段階)。"""
    pnl, fired, peak = T; n = pnl.shape[1]; rng = np.random.default_rng(seed)
    c = np.full(N, start); alive = np.ones(N, bool); res = np.zeros(N, int); wk = np.zeros(N, int); fires = np.zeros(N, int); ssum = np.zeros(N); scnt = np.zeros(N)
    for w in range(WEEKS):
        if w % 4 == 0: fires[:] = 0
        idx = rng.integers(0, n, N)
        if smin is None: gi = np.full(N, len(GRID) - 1)
        else: s = np.clip((c - floor) / mdd, smin, 1.0); gi = np.abs(GRID[None, :] - s[:, None]).argmin(axis=1)
        act = alive & (fires < 2); x = np.where(act, pnl[gi, idx], 0.0); pk = np.where(act, peak[gi, idx], -1.0); f = np.where(act, fired[gi, idx], 0)
        ssum += np.where(act, GRID[gi], 0.0); scnt += act
        hit = alive & ((c + pk >= target) | (c + x >= target)); c = c + x; fires += f
        res[hit] = 1; wk[hit] = w + 1; alive &= ~hit
        dead = alive & (c <= floor); res[dead] = 2; alive &= ~dead
    ok = res == 1
    return dict(reach=round(float(ok.mean()) * 100, 1), fail=round(float((res == 2).mean()) * 100, 1), weeks=(int(np.median(wk[ok])) if ok.any() else None), size=round(float((ssum / np.maximum(scnt, 1)).mean()), 2))
rows = []
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
        TB = {}
        for tn, lo_ in (("none", 1.0), ("tilt", 0.5)):
            fac = fac_for(1.0, lo_); P1_ = None if cap else paths_fac(items, cap, fac, p0, p1)
            for mult in (1.0, 1.2):
                if mult == 1.2 and tn == "none": continue
                out = {"lo": [], "cl": []}
                for lv in GRID:
                    P = scaled(P1_, lv * mult) if P1_ is not None else paths_fac([(sy, ix, w * lv * mult) for sy, ix, w in items], cap, fac, p0, p1); R = run_guard(P, g)
                    for tag in ("lo", "cl"): out[tag].append(R[tag][:3])
                TB[(tn, mult)] = {tag: tuple(np.array([x[i] for x in out[tag]]) for i in range(3)) for tag in out}
        VAR = (("V0 現行", ("none", 1.0), None), ("V1 減らすだけ", ("tilt", 1.0), None), ("V2 損失枠比例", ("none", 1.0), 0.5), ("V3 併用", ("tilt", 1.0), 0.5), ("参照 V3 × 1.2", ("tilt", 1.2), 0.5))
        for nm, start, target in sc:
            for vn, key, smin in VAR:
                r = dict(acct=a["name"][:20], window=wn, scen=nm, variant=vn)
                for tag in ("lo", "cl"):
                    m = mc_state(TB[key][tag], start, target, -mdd, mdd, smin); r.update({f"reach_{tag}": m["reach"], f"fail_{tag}": m["fail"], f"weeks_{tag}": m["weeks"], f"size_{tag}": m["size"]})
                rows.append(r)
    print(a["name"][:20], "done", flush=True)
D = pd.DataFrame(rows); D.to_csv("results/q198_weak_tilt_plus_buffer_sizing.csv", index=False); picks = []
for (acct, scn), g_ in D.groupby(["acct", "scen"], sort=False):
    cur = {w: g_[(g_.window == w) & (g_.variant == "V0 現行")].iloc[0] for w in ("W1", "W2")}; cand = []
    for vn in ("V1 減らすだけ", "V2 損失枠比例", "V3 併用"):
        x = {w: g_[(g_.window == w) & (g_.variant == vn)].iloc[0] for w in ("W1", "W2")}
        ok = all(x[w][f"fail_{t}"] <= cur[w][f"fail_{t}"] and x[w][f"reach_{t}"] >= cur[w][f"reach_{t}"] - 1.0 for w in ("W1", "W2") for t in ("lo", "cl")) and all(x[w].weeks_lo is not None and cur[w].weeks_lo is not None and x[w].weeks_lo <= 2 * cur[w].weeks_lo for w in ("W1", "W2"))
        if ok: cand.append((max(x[w][f"fail_{t}"] for w in ("W1", "W2") for t in ("lo", "cl")), -x["W2"].reach_lo, vn))
    best = sorted(cand)[0][2] if cand else None
    def f(vn, w): x = g_[(g_.window == w) & (g_.variant == vn)].iloc[0]; return f"{x.reach_lo:.0f}/{x.reach_cl:.0f} f{x.fail_lo:.0f}/{x.fail_cl:.0f} w{x.weeks_lo}"
    picks.append(dict(acct=acct, scen=scn, pick=(best or "現行維持"), ok_variants="・".join(v for _, _, v in sorted(cand)) or "—", **{f"{v[:2]}_{w}": f(v, w) for v in ("V0 現行", "V1 減らすだけ", "V2 損失枠比例", "V3 併用", "参照 V3 × 1.2") for w in ("W1", "W2")}))
Pk = pd.DataFrame(picks); Pk.to_csv("results/q198_weak_tilt_plus_buffer_sizing_pick.csv", index=False)
pd.set_option("display.width", 400); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 400); pd.set_option("display.max_colwidth", 60)
print("\n== 推奨(到達 安値/終値・失格 安値/終値・中央週) ==\n" + Pk.to_string(index=False))
