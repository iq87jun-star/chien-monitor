# -*- coding: utf-8 -*-
"""docs/244 Q202(診断・セル 0・2026-11-14 登録「登録して実行」): 1-Step 531466484 の損失枠比例の縮小 + 倍率を、追随型の失格線で確かめる。
失格線 S = 固定 −10%(Q201 の再現)/ T = 追随型(min(HWM, +10%) − 10%・週末の残高で更新)/ T1 = 追随型 + EA の全停止線(床 + 1%)。主判定 T1。
構成 V0 縮小なし / V2 損失枠比例(下限 0.5)/ 参考 V3。倍率 = 現行 × s(9 段階)。場面 C1 = 現在地(残高 +2.72%・HWM +2.81%)→ +10%、C0 = ゼロ → +10%(参考)。
使い方: cd research && python3 -W ignore queue/q202_ftmo1step_trailing_floor_buffer_sizing.py   出力: results/q202_ftmo1step_trailing_floor_buffer_sizing.csv・_pick.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
src = open(os.path.join(HERE, "q198_weak_tilt_plus_buffer_sizing.py"), encoding="utf-8").read().split("\nrows = []\nfor a in cfg")[0]
ns = {"__name__": "q198_head", "__file__": os.path.join(HERE, "q198_weak_tilt_plus_buffer_sizing.py")}; exec(compile(src, "q198_head", "exec"), ns)
cfg, table, run_guard, account_items, paths_fac, weak_flags, states_h1, WFN, WINS, GRID, N, WEEKS, PRK = (ns[k] for k in ("cfg", "table", "run_guard", "account_items", "paths_fac", "weak_flags", "states_h1", "WFN", "WINS", "GRID", "N", "WEEKS", "PRK"))
AID = "531466484"; SCALES = (0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0, 1.25, 1.5); MDD = 0.10; TGT = 0.10
START, HWM0 = 102722.34 / 1e5 - 1, 102813.25 / 1e5 - 1            # 残高・EA ログの EOD 最高 equity(2026-11-12)
FLOORS = (("S 固定", False, 0.0), ("T 追随", True, 0.0), ("T1 追随 + 全停止線", True, 0.01)); VARS = (("V0 縮小なし", False, None), ("V2 損失枠比例", False, 0.5), ("V3 2 つの縮小(参考)", True, 0.5))
def mc_trail(T, start, hwm0, trail, pad, smin, seed=187):
    pnl, fired, peak = T; n = pnl.shape[1]; rng = np.random.default_rng(seed); c = np.full(N, float(start)); hwm = np.full(N, float(hwm0)); alive = np.ones(N, bool); res = np.zeros(N, int); wk = np.zeros(N, int); fires = np.zeros(N, int); ssum = np.zeros(N); scnt = np.zeros(N)
    for w in range(WEEKS):
        if w % 4 == 0: fires[:] = 0
        idx = rng.integers(0, n, N); floor = (np.minimum(hwm, TGT) - MDD) if trail else np.full(N, -MDD)
        if smin is None: gi = np.full(N, len(GRID) - 1)
        else: s = np.clip((c - floor) / MDD, smin, 1.0); gi = np.abs(GRID[None, :] - s[:, None]).argmin(axis=1)
        act = alive & (fires < 2); x = np.where(act, pnl[gi, idx], 0.0); pk = np.where(act, peak[gi, idx], -1.0); f = np.where(act, fired[gi, idx], 0); ssum += np.where(act, GRID[gi], 0.0); scnt += act
        hit = alive & ((c + pk >= TGT) | (c + x >= TGT)); c = c + x; fires += f; res[hit] = 1; wk[hit] = w + 1; alive &= ~hit
        dead = alive & (c <= floor + pad); res[dead] = 2; alive &= ~dead; hwm = np.maximum(hwm, c)
    ok = res == 1
    return dict(reach=round(float(ok.mean()) * 100, 1), fail=round(float((res == 2).mean()) * 100, 1), weeks=(int(np.median(wk[ok])) if ok.any() else None), size=round(float((ssum / np.maximum(scnt, 1)).mean()), 2))
a = [x for x in cfg["accounts"] if AID in x["name"]][0]; aid, items, cap, g = account_items(a); assert aid == AID and cap is not None
fx = [(s, w) for s, idxf, w in items if not idxf]; fxm = sum(w for _, w in fx); flags = {}; skf = {}
for s, w in fx:
    dts = [pd.Timestamp(d) for d in table(s, False)[0].date.unique()]; hit, valid = weak_flags(s, states_h1, dts, WFN); flags[s] = {d: bool(h and v) for d, h, v in zip(dts, hit, valid)}
    pr = PRK.reindex(pd.DatetimeIndex(dts) - pd.Timedelta(days=3), method="ffill").values; skf[s] = {d: 0.0 for d, p in zip(dts, pr) if p == p and p > 0.8}
def fac_for(tilt): return {(s, False): {d: skf[s].get(d, 1.0) * (1.0 if (wk or not tilt) else 0.5) for d, wk in flags[s].items()} for s, w in fx}
rows = []
for wn, p0, p1 in WINS:
    for tilt in (False, True):
        fac = fac_for(tilt)
        for s_ in SCALES:
            out = {"lo": [], "cl": []}
            for lv in GRID:
                R = run_guard(paths_fac([(sy, ix, w * lv * s_) for sy, ix, w in items], cap, fac, p0, p1), g)
                for tag in ("lo", "cl"): out[tag].append(R[tag][:3])
            T = {tag: tuple(np.array([x[i] for x in out[tag]]) for i in range(3)) for tag in out}
            for vn, vt, smin in VARS:
                if vt != tilt: continue
                for fn, trail, pad in FLOORS:
                    for sn, st, h0 in (("C1 現在地", START, HWM0), ("C0 ゼロ", 0.0, 0.0)):
                        r = dict(window=wn, variant=vn, floor=fn, scene=sn, s=s_, fx_mult=round(fxm * s_, 2))
                        for tag in ("lo", "cl"):
                            m = mc_trail(T[tag], st, h0, trail, pad, smin); r.update({f"reach_{tag}": m["reach"], f"fail_{tag}": m["fail"], f"weeks_{tag}": m["weeks"], f"size_{tag}": m["size"]})
                        rows.append(r)
        print(wn, "tilt" if tilt else "none", "done", flush=True)
D = pd.DataFrame(rows); D.to_csv("results/q202_ftmo1step_trailing_floor_buffer_sizing.csv", index=False)
P = D[(D.floor == "T1 追随 + 全停止線") & (D.scene == "C1 現在地") & (~D.variant.str.startswith("V3"))]; tab = []
for (vn, s_), x in P.groupby(["variant", "s"], sort=False):
    w1, w2 = x[x.window == "W1"].iloc[0], x[x.window == "W2"].iloc[0]
    tab.append(dict(variant=vn, s=s_, fx_mult=w1.fx_mult, r=[w1.reach_lo, w1.reach_cl, w2.reach_lo, w2.reach_cl], f=[w1.fail_lo, w1.fail_cl, w2.fail_lo, w2.fail_cl], wk=[w1.weeks_lo, w2.weeks_lo]))
cur = [t for t in tab if t["variant"].startswith("V0") and t["s"] == 1.0][0]; cand = []
for t in tab:
    if t is cur or any(x is None or x != x for x in t["wk"]): continue
    dom = all(a_ >= b_ for a_, b_ in zip(t["r"], cur["r"])) and all(a_ <= b_ for a_, b_ in zip(t["f"], cur["f"])) and all(a_ <= b_ for a_, b_ in zip(t["wk"], cur["wk"]))
    if dom and (min(t["r"]) >= min(cur["r"]) + 2.0 or max(t["f"]) <= 0.5 * max(cur["f"])): cand.append(t)
cand.sort(key=lambda t: (max(t["f"]), -min(t["r"])))
Pk = pd.DataFrame([dict(role="現行", variant=cur["variant"], s=1.0, fx_mult=cur["fx_mult"], reach_min=min(cur["r"]), fail_max=max(cur["f"]), weeks_w1=cur["wk"][0], weeks_w2=cur["wk"][1], verdict=("変更候補あり" if cand else "現行維持"))] + [dict(role=("推奨" if i == 0 else "候補"), variant=t["variant"], s=t["s"], fx_mult=t["fx_mult"], reach_min=min(t["r"]), fail_max=max(t["f"]), weeks_w1=t["wk"][0], weeks_w2=t["wk"][1], verdict="") for i, t in enumerate(cand)])
Pk.to_csv("results/q202_ftmo1step_trailing_floor_buffer_sizing_pick.csv", index=False)
pd.set_option("display.width", 300); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 700)
print("\n== 推奨(場面 C1・失格線 T1) ==\n" + Pk.to_string(index=False))
D["r"] = [f"{a_:.1f}/{b_:.1f} f{c_:.1f}/{d_:.1f} w{e_ if e_ == e_ else '-'} sz{z:.2f}" for a_, b_, c_, d_, e_, z in zip(D.reach_lo, D.reach_cl, D.fail_lo, D.fail_cl, D.weeks_lo, D.size_lo)]
for sn in ("C1 現在地", "C0 ゼロ"):
    for vn in [v[0] for v in VARS]:
        x = D[(D.scene == sn) & (D.variant == vn)]; print(f"\n== {sn}・{vn} ==\n" + x.pivot_table(index=["s", "fx_mult"], columns=["window", "floor"], values="r", aggfunc="first").to_string())
