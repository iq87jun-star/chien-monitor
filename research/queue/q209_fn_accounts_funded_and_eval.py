# -*- coding: utf-8 -*-
"""docs/244 Q209(診断・セル 0・2026-11-14 登録「登録して実行」): FN の 3 口座の本番後(5 年・10 年)と、14166201 の評価中。
(1) FN 14074882: 月曜 3 通貨(4.0 倍 × s)× {縮小なし, 2 つの縮小} × {金の保有 0.4 倍, なし}・静的床・4 週ごとに全額出金。
(2) FN 14166201: UK100 1.09 + WTI 0.34 倍の保有 × {0, 0.5, 1.0} + 水曜ロール 4.5 倍。評価中(+4.40% → +8%・ゼロ → +5%)も。
(3) FN Instant 11988011: 建値ロックの失格線 min(最高残高 − 6%, 額面)・4 週ごとに残高 +5% 以上なら額面の 2% を出金・月曜の倍率 × s。
モデルは Q203 / Q208 と同じ流儀。使い方: cd research && python3 -W ignore queue/q209_fn_accounts_funded_and_eval.py   出力: results/q209_fn_accounts_funded_and_eval.csv・_pick.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
_src = open(os.path.join(HERE, "q208_funded_non_monday_legs.py"), encoding="utf-8").read().split("\nrows = []\nfor a in cfg")[0]; n8 = {"__name__": "q208_head", "__file__": os.path.join(HERE, "q208_funded_non_monday_legs.py")}; exec(compile(_src, "q208_head", "exec"), n8)
cfg, table, run_guard, account_items, paths_fac, scaled, weak_flags, states_h1, WFN, GRID, PRK, S, ROLL, XAU, build, funded, P0, PM, P1 = (n8[k] for k in ("cfg", "table", "run_guard", "account_items", "paths_fac", "scaled", "weak_flags", "states_h1", "WFN", "GRID", "PRK", "S", "ROLL", "XAU", "build", "funded", "P0", "PM", "P1"))
UK, WTI = S("hold:UK100"), S("hold:WTI"); SC = (0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0, 1.25); rows = []
def acct(key): return [a for a in cfg["accounts"] if key in a["name"]][0]
def state(fx, skew):
    flags, skf = {}, {}
    for s, w in fx:
        dts = [pd.Timestamp(d) for d in table(s, False)[0].date.unique()]; hit, valid = weak_flags(s, states_h1, dts, WFN); flags[s] = {d: bool(h and v) for d, h, v in zip(dts, hit, valid)}
        if skew:
            pr = PRK.reindex(pd.DatetimeIndex(dts) - pd.Timedelta(days=3), method="ffill").values; skf[s] = {d: 0.0 for d, p in zip(dts, pr) if p == p and p > 0.8}
    return lambda tilt: {(s, False): {d: skf.get(s, {}).get(d, 1.0) * (1.0 if (wk or not tilt) else 0.5) for d, wk in flags[s].items()} for s, w in fx}
def add(r, m, m2, tag): r.update({f"surv5_{tag}": m[260][0], f"surv10_{tag}": m[520][0], f"mean5_{tag}": m[260][1], f"mean10_{tag}": m[520][1], f"w2_surv5_{tag}": m2[260][0]})
# ---- (1) FN 14074882 ----
a = acct("14074882"); aid, items, cap, g = account_items(a); mdd = float(a["mdd"]); sw = float(a.get("swap_xau_bps_m", 0.0) or 0.0); fx = [(s, w) for s, idxf, w in items if not idxf]; fxm = sum(w for _, w in fx); facf = state(fx, True)
for cn, tilt, smin in (("縮小なし", False, None), ("2 つの縮小", True, 0.5)):
    PA = paths_fac(items, cap, facf(tilt), P0, P1)
    for s_ in SC:
        for gold in (0.4, 0.0):
            O = (XAU * gold + gold * sw / 1e4 / 21.0) if gold else None; T, dates = build(lambda lv: scaled(PA, lv * s_), g, O); call = np.arange(len(dates)); c2 = call[dates < PM]
            r = dict(acct="FN 14074882", part="本口座", comp=cn, mon_mult=round(fxm * s_, 2), s=s_, other=(f"金の保有 {gold} 倍" if gold else "なし"), plan=bool(s_ == 1.0 and not tilt and gold == 0.4))
            for tag in ("lo", "cl"): add(r, funded(T[tag], call, mdd, smin, False, 0.0, 20000, 520), funded(T[tag], c2, mdd, smin, False, 0.0, 10000, 260), tag)
            rows.append(r)
print("FN 14074882 done", flush=True)
# ---- (2) FN 14166201(月曜レグなし) ----
a = acct("14166201"); mdd = float(a["mdd"]); g = 0.04; mondays = pd.date_range(P0, P1, freq="W-MON"); mdt = np.array(mondays); L = len(GRID)
def weekly(hold_s, roll_w=4.5):
    O = (UK * 1.09 + WTI * 0.34) * hold_s; O = O.add(ROLL * roll_w, fill_value=0) if roll_w else O; wp, wf, wk = [], [], []
    for d in mondays:
        c = 0.0; f = 0; pk = 0.0
        for j in range(7):
            x = float(O.get(d + pd.Timedelta(days=j), 0.0)); x = 0.0 if x != x else x
            if x <= -g: x = -g * 1.1; f += 1
            c += x; pk = max(pk, c)
        wp.append(c); wf.append(f); wk.append(pk)
    return np.array(wp), np.array(wf), np.array(wk), O
def mc1(pnl, fired, peak, start, target, mdd, n=20000, weeks=52, seed=187):
    rng = np.random.default_rng(seed); c = np.full(n, float(start)); alive = np.ones(n, bool); res = np.zeros(n, int); wk = np.zeros(n, int); fires = np.zeros(n, int)
    for w in range(weeks):
        if w % 4 == 0: fires[:] = 0
        idx = rng.integers(0, len(pnl), n); act = alive & (fires < 2); x = np.where(act, pnl[idx], 0.0); pk = np.where(act, peak[idx], -1.0)
        hit = alive & ((c + pk >= target) | (c + x >= target)); c = c + x; fires += np.where(act, fired[idx], 0); res[hit] = 1; wk[hit] = w + 1; alive &= ~hit; dead = alive & (c <= -mdd); res[dead] = 2; alive &= ~dead
    ok = res == 1; return round(float(ok.mean()) * 100, 1), round(float((res == 2).mean()) * 100, 1), (int(np.median(wk[ok])) if ok.any() else None)
for hs, lab in ((0.0, "保有 × 0(ロールのみ)"), (0.5, "保有 × 0.5 + ロール"), (1.0, "保有 × 1.0 + ロール(予定)"), (1.0, "参考: 保有 × 1.0 のみ(ロールなし)")):
    wp, wf, wk, O = weekly(hs, 0.0 if "ロールなし" in lab else 4.5); T = (np.tile(wp, (L, 1)), np.tile(wf, (L, 1))); call = np.arange(len(wp)); c2 = call[mdt < np.datetime64(PM)]
    x = O[(O.index >= P0) & (O.index <= P1)]; m = funded(T, call, mdd, None, False, 0.0, 20000, 520); m2 = funded(T, c2, mdd, None, False, 0.0, 10000, 260)
    r = dict(acct="FN 14166201", part="本口座", comp="—", mon_mult=0.0, s=hs, other=lab, plan=bool("予定" in lab), week_bps=round(float(x.sum()) / ((P1 - P0).days / 7) * 1e4, 1), days_le_guard=int((x <= -g).sum())); add(r, m, m2, "lo"); add(r, m, m2, "cl")
    for wn, sel in (("W1", mdt >= np.datetime64(PM)), ("W2", mdt < np.datetime64(PM))):
        for snm, st, tg in (("i", 104397.42 / 1e5 - 1, 0.08), ("ii", 0.0, 0.05)): r[f"eval_{snm}_{wn}"] = "{} / {} ・{} 週".format(*mc1(wp[sel], wf[sel], wk[sel], st, tg, mdd))
    rows.append(r)
print("FN 14166201 done", flush=True)
# ---- (3) FN Instant ----
a = acct("11988011"); aid, items, cap, g = account_items(a); mdd = float(a["mdd"]); fx = [(s, w) for s, idxf, w in items if not idxf]; fxm = sum(w for s, i, w in items); facf = state(fx, False); START = 20338.37 / 2e4 - 1
def instant(T, cols, smin, n_paths, weeks, seed=187):
    pnl, fired = T[0][:, cols], T[1][:, cols]; n = pnl.shape[1]; rng = np.random.default_rng(seed); c = np.full(n_paths, START); hwm = np.full(n_paths, max(START, 0.0)); alive = np.ones(n_paths, bool); fires = np.zeros(n_paths, int); paid = np.zeros(n_paths); out = {}
    for w in range(weeks):
        if w % 4 == 0:
            fires[:] = 0
            if w > 0: el = alive & (c >= 0.05); paid += np.where(el, 0.02, 0.0); c = c - np.where(el, 0.02, 0.0)
        floor = np.minimum(hwm - mdd, 0.0); idx = rng.integers(0, n, n_paths)
        gi = np.full(n_paths, len(GRID) - 1) if smin is None else np.abs(GRID[None, :] - np.clip((c - floor) / mdd, smin, 1.0)[:, None]).argmin(axis=1)
        act = alive & (fires < 2); c = c + np.where(act, pnl[gi, idx], 0.0); fires += np.where(act, fired[gi, idx], 0); alive &= ~(c <= floor); hwm = np.maximum(hwm, c)
        if w + 1 in (52, 260, 520): out[w + 1] = (round(float(alive.mean()) * 100, 1), round(float(paid.mean()) * 100, 1))
    return out
for cn, tilt, smin in (("縮小なし", False, None), ("2 つの縮小", True, 0.5)):
    fac = facf(tilt)
    for s_ in SC:
        T, dates = build(lambda lv: paths_fac([(sy, ix, w * lv * s_) for sy, ix, w in items], cap, fac, P0, P1), g, None); call = np.arange(len(dates)); c2 = call[dates < PM]
        r = dict(acct="FN Instant", part="本番中", comp=cn, mon_mult=round(fxm * s_, 2), s=s_, other="—", plan=bool(s_ == 1.0 and not tilt))
        for tag in ("lo", "cl"):
            m = instant(T[tag], call, smin, 20000, 520); m2 = instant(T[tag], c2, smin, 10000, 260); add(r, m, m2, tag); r[f"surv1_{tag}"] = m[52][0]; r[f"mean1_{tag}"] = m[52][1]
        rows.append(r)
print("FN Instant done", flush=True)
D = pd.DataFrame(rows)
for k in ("surv5", "surv10", "mean5", "mean10", "w2_surv5"): D[k] = D[[f"{k}_lo", f"{k}_cl"]].min(axis=1)
D["ok"] = (D.surv10 >= 75.0) & (D.w2_surv5 >= 65.0); D.to_csv("results/q209_fn_accounts_funded_and_eval.csv", index=False); picks = []
for acct_ in ("FN 14074882", "FN Instant"):
    g_ = D[D.acct == acct_]; plan = g_[g_.plan].iloc[0]; ok = g_[g_.ok]
    if ok.empty: verdict = "条件を満たす組み合わせなし"; best = None
    else:
        top = ok.mean10.max(); best = ok[ok.mean10 >= top - 3.0].sort_values(["surv10", "mean10"], ascending=[False, False]).iloc[0]
        verdict = "予定どおり" if (bool(plan.ok) and best.mean10 - plan.mean10 < 5.0) else f"変更候補: {best.comp}・月曜 {best.mon_mult} 倍・{best.other}"
    picks.append(dict(acct=acct_, plan=f"{plan.comp}・{plan.mon_mult} 倍・{plan.other}: {plan.surv10:.1f} / {plan.w2_surv5:.1f} / {plan.mean10:.1f}", best=(f"{best.surv10:.1f} / {best.w2_surv5:.1f} / {best.mean10:.1f}" if best is not None else "—"), verdict=verdict))
g_ = D[D.acct == "FN 14166201"]; plan = g_[g_.plan].iloc[0]; low = g_[g_.other.isin(["保有 × 0(ロールのみ)", "保有 × 0.5 + ロール"])]; cand = low[(low.surv10 >= plan.surv10 + 5.0) & (low.mean10 >= plan.mean10 - 3.0)].sort_values(["surv10", "mean10"], ascending=[False, False])
picks.append(dict(acct="FN 14166201", plan=f"{plan.other}: {plan.surv10:.1f} / {plan.w2_surv5:.1f} / {plan.mean10:.1f}", best=(f"{cand.iloc[0].surv10:.1f} / {cand.iloc[0].w2_surv5:.1f} / {cand.iloc[0].mean10:.1f}" if len(cand) else "—"), verdict=(f"変更候補: {cand.iloc[0].other}" if len(cand) else "予定どおり")))
Pk = pd.DataFrame(picks); Pk.to_csv("results/q209_fn_accounts_funded_and_eval_pick.csv", index=False)
pd.set_option("display.width", 330); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 300)
print("\n== 推奨(10 年存続 / W2 の 5 年存続 / 10 年累計出金) ==\n" + Pk.to_string(index=False))
print("\n== FN 14074882 ==\n" + D[D.acct == "FN 14074882"][["comp", "mon_mult", "other", "plan", "ok", "surv5", "surv10", "w2_surv5", "mean5", "mean10"]].to_string(index=False))
print("\n== FN 14166201 ==\n" + D[D.acct == "FN 14166201"][["other", "week_bps", "days_le_guard", "surv5", "surv10", "w2_surv5", "mean5", "mean10", "eval_i_W1", "eval_i_W2", "eval_ii_W1", "eval_ii_W2"]].to_string(index=False))
print("\n== FN Instant ==\n" + D[D.acct == "FN Instant"][["comp", "mon_mult", "plan", "ok", "surv1_lo", "mean1_lo", "surv5", "surv10", "w2_surv5", "mean5", "mean10"]].to_string(index=False))
