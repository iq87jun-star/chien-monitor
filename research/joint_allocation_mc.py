# -*- coding: utf-8 -*-
"""
joint_allocation_mc.py — 【実験】口座横断のセル割り付け(docs/201の実装)。

問い: 各口座が独立に選抜する現行(INDEP)に対し、順次選抜で他口座との重複を避ける
(JOINT_EXCL / JOINT_EXCL_SYM / JOINT_PEN)と、ブック全体の同時失格(CB)と資金化期待値はどう変わるか。

評価: docs/199の同時失格MCを拡張し資金化も追跡。全口座に同一ブートストラップ・ブロック。
出力: results/joint_allocation_mc.json → docs/201 §9
⚠ 季節RG3(FN100k #14074882)は再構築不可のため含まれない。A案は別EAのため固定。
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recentfit_screen as base
base.DATA = os.path.join(HERE, "data_202609")
import recentfit_nonfx_screen as nfx
import deployed_book as db

SEED = 7; N_MC = 10000; BLOCK = 5; HORIZON = 250; CB_WINDOW = 30
W_CAP = 0.40
DATES = ["2025-09-30", "2025-12-31", "2026-03-31", "2026-05-29", "2026-06-30", "2026-08-31"]
NFX_UNIVERSE = ["UK100", "FR40", "WTI", "NATGAS", "BTCUSD", "ETHUSD"]     # docs/182 FN適合

# docs/201 §3 の口座別規則(順序=リスク寄与降順・docs/201 §4.1)
ORDER = ["Fintokei_Sokkou2000_6078225", "FTMO50k_531407058", "FTMO50k_521100397",
         "FN100k_14166201", "Fintokei_Pearl500", "FN_Instant20k_11988011"]
ACCTS = {
    "Fintokei_Sokkou2000_6078225": dict(sel_m=6, conf=("months", 3), min_active=8, universe="base",
                                        excl_family={"Hold"}, day=0.015, floor=0.024, cap=6.0),
    "FTMO50k_531407058":           dict(sel_m=6, conf=("months", 3), min_active=8, universe="base",
                                        day=0.04, floor=0.08, cap=6.0),
    "FTMO50k_521100397":           dict(sel_m=3, conf=("weeks", 6), min_active=5, universe="base",
                                        day=0.04, floor=0.08, cap=6.0),
    "FN100k_14166201":             dict(sel_m=12, conf=("months", 6), min_active=15, universe="nfx",
                                        day=0.04, floor=0.08, cap=6.0),
    "Fintokei_Pearl500":           dict(sel_m=12, conf=("months", 6), min_active=15, universe="base",
                                        excl_family={"Hold"}, day=0.04, floor=0.08, cap=6.0),
    "FN_Instant20k_11988011":      dict(sel_m=12, conf=("months", 6), min_active=15, universe="base",
                                        excl_symbol={"JP225"}, day=0.04, floor=0.048, cap=4.0),
}
FIXED = ["FTMO100k_531343523"]
FN_PAIR = ("FN_Instant20k_11988011", "FN100k_14166201")        # 同一銘柄禁止(docs/161 §4③)
CB_NEW_SET = {"FTMO100k_531343523", "Fintokei_Pearl500", "FTMO50k_531407058",
              "FTMO50k_521100397", "FN100k_14166201"}          # docs/200 §2.1
# 業者規則(docs/199 §3)
MC_RULES = {
    "FTMO100k_531343523":  dict(kind="2step", p1=0.10, p2=0.05, dd=0.10, guard=0.04),
    "FTMO50k_531407058":   dict(kind="2step", p1=0.10, p2=0.05, dd=0.10, guard=0.04),
    "FTMO50k_521100397":   dict(kind="2step", p1=0.10, p2=0.05, dd=0.10, guard=0.04),
    "FN100k_14166201":     dict(kind="2step", p1=0.08, p2=0.05, dd=0.10, guard=0.04),
    "Fintokei_Pearl500":   dict(kind="2step", p1=0.08, p2=0.06, dd=0.10, guard=0.04),
    "FN_Instant20k_11988011": dict(kind="trail", trail=0.06, guard=0.04),
    "Fintokei_Sokkou2000_6078225": dict(kind="1step", p1=0.06, dd=0.03, guard=0.015, deadline=60),
}


def wnd(s, a, b): return s[(s.index >= a) & (s.index <= b)]


def build_cells():
    cells = {}
    for nm in base.MON_FX + base.MON_IDX:
        cells[f"Mon_{nm}"] = dict(family="Mon", symbol=nm, s=base.mon_cell(nm), uni={"base"})
    for nm in base.HOLD_SYMS:
        cells[f"Hold_{nm}"] = dict(family="Hold", symbol=nm, s=base.hold_cell(nm), uni={"base"})
    for p in base.V4_PAIRS:
        cells[f"v4_{p}"] = dict(family="v4", symbol=p, s=base.v4_cell(p), uni={"base"})
    for nm in NFX_UNIVERSE:                       # 非FXユニバース(docs/182)
        for fam, fn in (("Mon", base.mon_cell), ("Hold", base.hold_cell), ("v4", nfx.v4_cell_nonfx)):
            k = f"{fam}_{nm}"
            if k in cells:
                cells[k]["uni"].add("nfx")
            else:
                cells[k] = dict(family=fam, symbol=nm, s=fn(nm), uni={"nfx"})
    return cells


def stats(s, t, sel_m, conf):
    sel0 = t - pd.DateOffset(months=sel_m) + pd.Timedelta(days=1)
    c0 = (t - pd.DateOffset(months=conf[1]) if conf[0] == "months"
          else t - pd.Timedelta(weeks=conf[1])) + pd.Timedelta(days=1)
    w12 = t - pd.DateOffset(months=12) + pd.Timedelta(days=1)
    ss, sc, s12 = wnd(s, sel0, t), wnd(s, c0, t), wnd(s, w12, t)
    a = ss[ss != 0.0]; n = int(len(a)); sd = float(a.std()) if n > 2 else float("nan")
    score = float(a.mean() / sd * np.sqrt(n)) if (n > 2 and sd > 0) else None
    return dict(n=n, cum_sel=float((1 + ss).prod() - 1), cum_conf=float((1 + sc).prod() - 1),
                score=score, sd=sd, sel0=sel0, w12=w12)


def corr(a, b, lo, hi):
    j = pd.concat([wnd(a, lo, hi).rename("a"), wnd(b, lo, hi).rename("b")], axis=1).dropna()
    if len(j) < 20 or j["a"].std() == 0 or j["b"].std() == 0: return 0.0
    c = float(j["a"].corr(j["b"])); return 0.0 if not np.isfinite(c) else c


def cap_norm(raw):
    tot = sum(raw.values())
    if tot <= 0: return {}
    w = {k: min(v / tot, W_CAP) for k, v in raw.items()}; t2 = sum(w.values())
    return {k: v / t2 for k, v in w.items()}


def composite(cells, w, lo, hi):
    idx = sorted(set().union(*[set(wnd(cells[k]["s"], lo, hi).index) for k in w]))
    out = pd.Series(0.0, index=pd.DatetimeIndex(idx))
    for k, x in w.items():
        out = out.add(wnd(cells[k]["s"], lo, hi).reindex(out.index).fillna(0.0) * x, fill_value=0.0)
    return out


def mstar(s, day, floor):
    if len(s) == 0 or float(s.min()) >= 0: return 12.0
    best = 0.05
    for m in np.arange(0.05, 12.01, 0.05):
        wd, wdd = base.worst_stats(s * m)
        if wd >= -day and wdd >= -floor: best = m
        else: break
    return best


def select_account(cells, acct, t, excl_cells=set(), excl_syms=set(), pen_ref=None, lam=0.0):
    r = ACCTS[acct]
    cand = []
    for k, v in cells.items():
        if r["universe"] not in v["uni"]: continue
        if v["family"] in r.get("excl_family", set()): continue
        if v["symbol"] in r.get("excl_symbol", set()): continue
        if k in excl_cells or v["symbol"] in excl_syms: continue
        st = stats(v["s"], t, r["sel_m"], r["conf"])
        if st["score"] is None or st["n"] < r["min_active"] or st["cum_sel"] <= 0 \
           or st["cum_conf"] <= 0 or not np.isfinite(st["sd"]) or st["sd"] <= 0: continue
        sc = st["score"]
        if lam > 0 and pen_ref is not None:
            sc *= (1.0 - lam * max(0.0, corr(v["s"], pen_ref, st["sel0"], t)))
        cand.append((k, v, st, sc))
    cand.sort(key=lambda x: -x[3])
    picked, fam_ct, sym_used, sds = [], {}, set(), {}
    for k, v, st, _ in cand:
        if v["symbol"] in sym_used or fam_ct.get(v["family"], 0) >= 2: continue
        picked.append(k); sym_used.add(v["symbol"]); fam_ct[v["family"]] = fam_ct.get(v["family"], 0) + 1
        sds[k] = st["sd"]
        if len(picked) == 4: break
    w = cap_norm({k: 1.0 / sds[k] for k in picked})
    if not w: return {}, 0.0, None
    comp = composite(cells, w, base.W_ALL0, t)
    sel0 = t - pd.DateOffset(months=r["sel_m"]) + pd.Timedelta(days=1)
    w12 = t - pd.DateOffset(months=12) + pd.Timedelta(days=1)
    m = min(0.8 * min(mstar(wnd(comp, sel0, t), r["day"], r["floor"]),
                      mstar(wnd(comp, w12, t), r["day"], r["floor"])), r["cap"])
    return w, round(m, 2), comp


def allocate(cells, t, arm):
    """docs/201 §4: INDEP / JOINT_EXCL / JOINT_EXCL_SYM / JOINT_PEN"""
    res = {}; used_cells, used_syms = set(), set(); pen_parts = []
    for acct in ORDER:
        ec, es, ref, lam = set(), set(), None, 0.0
        if arm != "INDEP":
            ec = set(used_cells)
            if arm == "JOINT_EXCL_SYM": es = set(used_syms)
            # FN同一取引禁止: Instant は非FX口座の銘柄を持たない(順序上、非FXが先)
            if acct == FN_PAIR[0] and FN_PAIR[1] in res:
                es |= {cells[k]["symbol"] for k in res[FN_PAIR[1]]["w"]}
            if arm == "JOINT_PEN" and pen_parts:
                idx = sorted(set().union(*[set(p.index) for p in pen_parts]))
                ref = pd.Series(0.0, index=pd.DatetimeIndex(idx))
                for p in pen_parts: ref = ref.add(p.reindex(ref.index).fillna(0.0), fill_value=0.0)
                lam = 1.0
        w, m, comp = select_account(cells, acct, t, ec, es, ref, lam)
        res[acct] = dict(w=w, mult=m, comp=comp)
        if w:
            used_cells |= set(w); used_syms |= {cells[k]["symbol"] for k in w}
            if comp is not None: pen_parts.append(comp)
    return res


# ---------------- MC(資金化も追跡) ----------------
def sim(kind, paths, mult, ru):
    n, T = paths.shape
    eq = np.ones(n); ref = np.ones(n); hwm = np.ones(n); phase = np.zeros(n, int)
    failed = np.zeros(n, bool); funded = np.zeros(n, bool); fday = np.full(n, -1)
    g = ru["guard"]
    for t in range(T):
        alive = ~(failed | funded)
        if not alive.any(): break
        eq = np.where(alive, eq * (1 + np.clip(paths[:, t] * mult, -g, None)), eq)
        if kind == "2step":
            rel = eq / ref - 1
            nf = alive & (rel <= -ru["dd"]); failed |= nf; fday[nf] = t + 1
            alive = ~(failed | funded)
            hit = alive & (rel >= np.where(phase == 0, ru["p1"], ru["p2"]))
            h1 = hit & (phase == 0); ref[h1] = eq[h1]; phase[h1] = 1
            funded |= hit & (phase == 1)
        elif kind == "trail":
            hwm = np.maximum(hwm, eq)
            nf = alive & (eq <= hwm - ru["trail"]); failed |= nf; fday[nf] = t + 1
        else:  # 1step
            rel = eq - 1
            nf = alive & (rel <= -ru["dd"]); failed |= nf; fday[nf] = t + 1
            alive = ~(failed | funded)
            funded |= alive & (rel >= ru["p1"])
            if t + 1 == ru["deadline"]:
                to = ~(failed | funded); failed |= to; fday[to] = t + 1; break
    if kind == "trail": funded = ~failed        # Instant: 地平まで生存=成功
    return funded, failed, fday


def mc_book(series, mults, rng):
    keys = list(series)
    df = pd.concat([series[k].rename(k) for k in keys], axis=1).fillna(0.0)
    R = df.values; nb = len(R) - BLOCK + 1
    st = rng.integers(0, nb, size=(N_MC, HORIZON // BLOCK + 1))
    idxs = (st[:, :, None] + np.arange(BLOCK)[None, None, :]).reshape(N_MC, -1)[:, :HORIZON]
    F = np.zeros((N_MC, len(keys)), bool); X = np.zeros((N_MC, len(keys)), bool); D = np.full((N_MC, len(keys)), -1)
    for j, k in enumerate(keys):
        ru = MC_RULES[k]
        f, x, d = sim(ru["kind"], R[idxs, j], mults[k], ru)
        F[:, j], X[:, j], D[:, j] = f, x, d
    def cb(mask):
        out = np.zeros(N_MC, bool)
        for i in np.where((X & mask).sum(axis=1) >= 2)[0]:
            d = np.sort(D[i][X[i] & mask])
            if np.any(d[1:] - d[:-1] <= CB_WINDOW): out[i] = True
        return float(out.mean()) * 100
    new_mask = np.array([k in CB_NEW_SET for k in keys])
    return dict(P_CB_new=round(cb(new_mask), 2), P_CB_old=round(cb(np.ones(len(keys), bool)), 2),
                E_funded=round(float(F.sum(axis=1).mean()), 3), E_failed=round(float(X.sum(axis=1).mean()), 3),
                funded={k: round(float(F[:, j].mean()) * 100, 1) for j, k in enumerate(keys)},
                failed={k: round(float(X[:, j].mean()) * 100, 1) for j, k in enumerate(keys)})


def diagnostics(cells, alloc, t):
    ks = [k for k in alloc if alloc[k]["comp"] is not None]
    lo = t - pd.DateOffset(months=12) + pd.Timedelta(days=1)
    pairs_hi, pairs_dup = 0, 0
    for i in range(len(ks)):
        for j in range(i + 1, len(ks)):
            rho = corr(alloc[ks[i]]["comp"], alloc[ks[j]]["comp"], lo, t)
            if rho > 0.7: pairs_hi += 1
            if set(alloc[ks[i]]["w"]) == set(alloc[ks[j]]["w"]): pairs_dup += 1
    fn_viol = 0
    if all(k in alloc and alloc[k]["w"] for k in FN_PAIR):
        s0 = {cells[k]["symbol"] for k in alloc[FN_PAIR[0]]["w"]}
        s1 = {cells[k]["symbol"] for k in alloc[FN_PAIR[1]]["w"]}
        fn_viol = len(s0 & s1)
    return dict(pairs_rho_gt_0_7=pairs_hi, pairs_identical=pairs_dup, fn_symbol_violations=fn_viol)


def main():
    base.W_ALL1 = pd.Timestamp("2026-08-31")
    print("[1/3] セル構築")
    cells = build_cells()
    base.verify_window([v["s"] for v in cells.values()])
    print(f"  セル数 {len(cells)}")
    fixed_series = {k: db.account_composite(k) for k in FIXED}
    fixed_mult = {k: db.BOOK[k]["mult"] for k in FIXED}
    ARMS = ["INDEP", "JOINT_EXCL", "JOINT_EXCL_SYM", "JOINT_PEN"]
    out = {"meta": dict(purpose="口座横断のセル割り付け docs/201", seed=SEED, dates=DATES, order=ORDER,
                        fixed=FIXED, excluded="FN100k_14074882(季節RG3・再構築不可)",
                        cb_new_set=sorted(CB_NEW_SET)), "by_date": {}, "aggregate": {}}

    print("[2/3] 基準日 × アーム")
    for d in DATES:
        t = pd.Timestamp(d); out["by_date"][d] = {}
        for arm in ARMS:
            alloc = allocate(cells, t, arm)
            series = {k: v[v.index <= t] for k, v in fixed_series.items()}
            mults = dict(fixed_mult)
            for k, a in alloc.items():
                if a["comp"] is not None:
                    series[k] = a["comp"]; mults[k] = a["mult"]
            mc = mc_book(series, mults, np.random.default_rng(SEED))
            # 選抜なし(=配備しない)の口座は 資金化0/失格0 として集計に残す(docs/201 §5)
            mc["no_selection"] = [k for k, a in alloc.items() if not a["w"]]
            for k in mc["no_selection"]:
                mc["funded"][k] = 0.0; mc["failed"][k] = 0.0
            mc["diag"] = diagnostics(cells, alloc, t)
            mc["alloc"] = {k: dict(w={c: round(x, 3) for c, x in a["w"].items()}, mult=a["mult"]) for k, a in alloc.items()}
            out["by_date"][d][arm] = mc
            print(f"  {d} {arm:14s} CB_new={mc['P_CB_new']:5.2f}% CB_old={mc['P_CB_old']:5.2f}% "
                  f"E_funded={mc['E_funded']:.3f} E_failed={mc['E_failed']:.3f} "
                  f"ρ>0.7={mc['diag']['pairs_rho_gt_0_7']} 同一={mc['diag']['pairs_identical']} FN違反={mc['diag']['fn_symbol_violations']}"
              + (f" 選抜なし={mc['no_selection']}" if mc["no_selection"] else ""))

    print("[3/3] 集計・判定(docs/201 §6)")
    for arm in ARMS:
        g = [out["by_date"][d][arm] for d in DATES]
        keys = list(g[0]["funded"])
        out["aggregate"][arm] = dict(
            P_CB_new=round(float(np.mean([x["P_CB_new"] for x in g])), 2),
            P_CB_old=round(float(np.mean([x["P_CB_old"] for x in g])), 2),
            E_funded=round(float(np.mean([x["E_funded"] for x in g])), 3),
            E_failed=round(float(np.mean([x["E_failed"] for x in g])), 3),
            funded={k: round(float(np.mean([x["funded"][k] for x in g])), 1) for k in keys},
            failed={k: round(float(np.mean([x["failed"][k] for x in g])), 1) for k in keys},
            diag={k: round(float(np.mean([x["diag"][k] for x in g])), 2) for k in g[0]["diag"]},
            no_selection_events=int(sum(len(x["no_selection"]) for x in g)))
    z = out["aggregate"]["INDEP"]; verdict = {}
    for arm in ARMS[1:]:
        a = out["aggregate"][arm]
        rel = (a["P_CB_new"] - z["P_CB_new"]) / z["P_CB_new"] * 100 if z["P_CB_new"] > 0 else 0.0
        verdict[arm] = dict(rel_cb_new_pct=round(rel, 1), d_E_funded=round(a["E_funded"] - z["E_funded"], 3),
                            adopt_candidate=bool(rel <= -20 and a["E_funded"] >= z["E_funded"]),
                            tradeoff=bool(rel <= -20 and a["E_funded"] < z["E_funded"]))
    out["verdict"] = verdict
    for arm in ARMS:
        a = out["aggregate"][arm]
        print(f"  {arm:14s} CB_new={a['P_CB_new']:5.2f}% CB_old={a['P_CB_old']:5.2f}% E_funded={a['E_funded']:.3f} "
              f"E_failed={a['E_failed']:.3f} ρ>0.7={a['diag']['pairs_rho_gt_0_7']} 同一={a['diag']['pairs_identical']}")
    for arm, v in verdict.items(): print(f"  {arm:14s} {v}")
    fp = os.path.join(HERE, "results", "joint_allocation_mc.json")
    with open(fp, "w") as f: json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("saved:", fp)


if __name__ == "__main__":
    main()
