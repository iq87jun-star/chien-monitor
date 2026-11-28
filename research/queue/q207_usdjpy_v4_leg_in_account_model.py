# -*- coding: utf-8 -*-
"""docs/244 Q207(診断・セル 0・2026-11-14 登録「登録して実行」): USDJPY の逆張り v4 を入れた口座モデルで、ルビー・パールの (a) 現行 / (b) v4 半分 / (c) v4 なし / (d) v4 なし・月曜へ振り替え を比べる。
月曜 = Q198 の H1 経路(2 つの縮小は月曜レグのみ)。v4 = account_cards.S('v4:USDJPY') の日次系列を Q190 の方法で重ねる(月曜分は経路に加算・火〜日は日次損益 ≤ −ガード で −ガード × 1.1・発動 1 回)。水曜ロールはモデル外。
場面 (i) 現在地 → +8%、(ii) ゼロ → +6%、(iii) 本口座 10 年(合意済みの月曜倍率・4 週ごとに全額出金・Q203 と同じ)。窓 W1 = 2021-08〜2026-07・W2 = 2016-11〜2021-07。
使い方: cd research && python3 -W ignore queue/q207_usdjpy_v4_leg_in_account_model.py   出力: results/q207_usdjpy_v4_leg_in_account_model.csv・_funded.csv・_pick.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
def head(fn, marker):
    src = open(os.path.join(HERE, fn), encoding="utf-8").read().split(marker)[0]; ns = {"__name__": fn[:4] + "_head", "__file__": os.path.join(HERE, fn)}; exec(compile(src, fn[:4] + "_head", "exec"), ns); return ns
n198 = head("q198_weak_tilt_plus_buffer_sizing.py", "\nrows = []\nfor a in cfg"); n190 = head("q190_add_non_monday_legs.py", "\nrows = []\nfor a in cfg")
cfg, table, run_guard, account_items, scenes, paths_fac, scaled, weak_flags, states_h1, WFN, WINS, GRID = (n198[k] for k in ("cfg", "table", "run_guard", "account_items", "scenes", "paths_fac", "scaled", "weak_flags", "states_h1", "WFN", "WINS", "GRID")); S = n190["S"]; EA_LEGS = n190["EA_LEGS"]
N, WEEKS = 20000, 52; P0, PM, P1 = pd.Timestamp("2016-11-01"), pd.Timestamp("2021-08-01"), pd.Timestamp("2026-07-31"); V4 = S("v4:USDJPY")
ACC = {"6104736": ("ルビー", True, 0.375), "6071612": ("パール", False, 0.5)}          # 名前, いまの配備に 2 つの縮小があるか, 本口座の月曜倍率 = 評価中 × s
VARS = (("(a) 現行", 1.0, 1.0), ("(b) v4 半分", 0.5, 1.0), ("(c) v4 なし", 0.0, 1.0), ("(d) v4 なし・月曜へ振り替え", 0.0, 1.0 / (1.0 - 0.304)))
def build(P1_, g, mon_s, v4_w):
    """GRID の各段階(月曜レグのみ縮小)について、v4 を重ねた週次の (損益, 発動, 最高値) を返す。"""
    out = {"lo": [], "cl": []}; dates = [pd.Timestamp(p["d"]) for p in P1_]
    days_all = [[(float(V4.get(d + pd.Timedelta(days=j), 0.0)) if v4_w else 0.0) * v4_w for j in range(7)] for d in dates]; days_all = [[0.0 if x != x else x for x in ds] for ds in days_all]
    for lv in GRID:
        P = scaled(P1_, lv * mon_s)
        for p, ds in zip(P, days_all):
            oM = ds[0]
            for tag in ("lo", "cl"): p["tot"][tag] = p["tot"][tag] + oM; p["met"][tag] = p["met"][tag] + min(0.0, oM)
            p["fin"] += oM
        R = run_guard(P, g)
        for tag in ("lo", "cl"):
            pnl, fired, peak = R[tag][:3]; wp, wf, wk = [], [], []
            for i, ds in enumerate(days_all):
                c = float(pnl[i]); f = int(fired[i]); pk = max(float(peak[i]), c)
                for x in ds[1:]:
                    if x <= -g: x = -g * 1.1; f += 1
                    c += x; pk = max(pk, c)
                wp.append(c); wf.append(f); wk.append(pk)
            out[tag].append((np.array(wp), np.array(wf), np.array(wk)))
    return {tag: tuple(np.array([x[i] for x in out[tag]]) for i in range(3)) for tag in out}, np.array(dates)
def mc3(T, start, target, mdd, smin, seed=187):
    pnl, fired, peak = T; n = pnl.shape[1]; rng = np.random.default_rng(seed); c = np.full(N, float(start)); alive = np.ones(N, bool); res = np.zeros(N, int); wk = np.zeros(N, int); fires = np.zeros(N, int)
    for w in range(WEEKS):
        if w % 4 == 0: fires[:] = 0
        idx = rng.integers(0, n, N); gi = np.full(N, len(GRID) - 1) if smin is None else np.abs(GRID[None, :] - np.clip((c + mdd) / mdd, smin, 1.0)[:, None]).argmin(axis=1)
        act = alive & (fires < 2); x = np.where(act, pnl[gi, idx], 0.0); pk = np.where(act, peak[gi, idx], -1.0); f = np.where(act, fired[gi, idx], 0)
        hit = alive & ((c + pk >= target) | (c + x >= target)); c = c + x; res[hit] = 1; wk[hit] = w + 1; alive &= ~hit; fires += f; dead = alive & (c <= -mdd); res[dead] = 2; alive &= ~dead
    ok = res == 1; return round(float(ok.mean()) * 100, 1), round(float((res == 2).mean()) * 100, 1), (int(np.median(wk[ok])) if ok.any() else None)
def funded(T, cols, mdd, smin, n_paths, weeks, seed=187):
    pnl, fired = T[0][:, cols], T[1][:, cols]; n = pnl.shape[1]; rng = np.random.default_rng(seed); c = np.zeros(n_paths); alive = np.ones(n_paths, bool); fires = np.zeros(n_paths, int); paid = np.zeros(n_paths); out = {}
    for w in range(weeks):
        if w % 4 == 0:
            fires[:] = 0
            if w > 0: pay = np.where(alive, np.maximum(c, 0.0), 0.0); paid += pay; c = c - pay
        idx = rng.integers(0, n, n_paths); gi = np.abs(GRID[None, :] - np.clip((c + mdd) / mdd, smin, 1.0)[:, None]).argmin(axis=1)
        act = alive & (fires < 2); c = c + np.where(act, pnl[gi, idx], 0.0); fires += np.where(act, fired[gi, idx], 0); alive &= ~(c <= -mdd)
        if w + 1 in (260, 520): tot = paid + np.where(alive, np.maximum(c, 0.0), 0.0); out[w + 1] = (round(float(alive.mean()) * 100, 1), round(float(tot.mean()) * 100, 1))
    return out
rows, frows, info = [], [], []
for a in cfg["accounts"]:
    aid, items, cap, g = account_items(a)
    if aid not in ACC: continue
    nm, has_shrink, sf = ACC[aid]; mdd = float(a["mdd"]); w4 = float(EA_LEGS[aid]["eval"]["v4:USDJPY"]); fx = [(s, w) for s, idxf, w in items if not idxf]; flags = {}
    for s, w in fx:
        dts = [pd.Timestamp(d) for d in table(s, False)[0].date.unique()]; hit, valid = weak_flags(s, states_h1, dts, WFN); flags[s] = {d: bool(h and v) for d, h, v in zip(dts, hit, valid)}
    def fac_for(tilt): return {(s, False): {d: (1.0 if (wk or not tilt) else 0.5) for d, wk in flags[s].items()} for s, w in fx}
    sc = scenes(a, aid)
    for wn, p0, p1 in WINS:
        vv = V4[(V4.index >= p0) & (V4.index <= p1)] * w4; info.append(dict(acct=nm, window=wn, v4_mult=round(w4, 2), v4_week_bps=round(float(vv.sum()) / ((p1 - p0).days / 7) * 1e4, 1), v4_days_le_guard=int((vv <= -g).sum()), v4_days_le_half_guard=int((vv <= -g / 2).sum()), v4_worst_day_pct=round(float(vv.min()) * 100, 2)))
        PT = {t: paths_fac(items, cap, fac_for(t), p0, p1) for t in (False, True)}
        for vn, v4s, ms in VARS:
            for snm, start, target in sc:
                tilt, smin = ((has_shrink, 0.5 if has_shrink else None) if snm.startswith("(i)") else (True, 0.5)); T, _ = build(PT[tilt], g, ms, w4 * v4s)
                r = dict(acct=nm, window=wn, scene=snm, variant=vn, mon_shrink=("2 つの縮小" if tilt else "縮小なし"), hits_lo=int(T["lo"][1][-1].sum()), hits_cl=int(T["cl"][1][-1].sum()), mean_bps_lo=round(float(T["lo"][0][-1].mean()) * 1e4, 1))
                for tag in ("lo", "cl"): r[f"reach_{tag}"], r[f"fail_{tag}"], r[f"weeks_{tag}"] = mc3(T[tag], start, target, mdd, smin)
                rows.append(r)
    # (iii) 本口座 10 年(合意済みの月曜倍率・2 つの縮小・全額出金)
    PA = paths_fac(items, cap, fac_for(True), P0, P1)
    for vn, v4s, ms in VARS:
        T, dates = build(PA, g, sf * ms, w4 * sf * v4s); call = np.arange(len(dates)); c2 = call[dates < PM]; r = dict(acct=nm, variant=vn, mon_mult=round(sum(w for _, w in fx) * sf * ms, 2), v4_mult=round(w4 * sf * v4s, 2))
        for tag in ("lo", "cl"):
            m = funded(T[tag], call, mdd, 0.5, 20000, 520); m2 = funded(T[tag], c2, mdd, 0.5, 10000, 260); r.update({f"surv5_{tag}": m[260][0], f"surv10_{tag}": m[520][0], f"mean5_{tag}": m[260][1], f"mean10_{tag}": m[520][1], f"w2_surv5_{tag}": m2[260][0], f"w2_mean5_{tag}": m2[260][1]})
        frows.append(r)
    print(nm, "done", flush=True)
D = pd.DataFrame(rows); F = pd.DataFrame(frows); I = pd.DataFrame(info); D.to_csv("results/q207_usdjpy_v4_leg_in_account_model.csv", index=False); F.to_csv("results/q207_usdjpy_v4_leg_in_account_model_funded.csv", index=False); picks = []
for (acct, scn), g_ in D.groupby(["acct", "scene"], sort=False):
    def four(vn): x = g_[g_.variant == vn]; return [float(v) for w in ("W1", "W2") for v in (x[x.window == w].reach_lo.iloc[0], x[x.window == w].reach_cl.iloc[0])], [float(v) for w in ("W1", "W2") for v in (x[x.window == w].fail_lo.iloc[0], x[x.window == w].fail_cl.iloc[0])]
    cr, cf = four("(a) 現行"); cand = []
    for vn in ("(b) v4 半分", "(c) v4 なし"):
        r_, f_ = four(vn)
        if all(y <= x for x, y in zip(cf, f_)) and all(y >= x - 1.0 for x, y in zip(cr, r_)) and (max(f_) <= max(cf) - 2.0 or min(r_) >= min(cr) + 2.0): cand.append((max(f_), -min(r_), vn))
    picks.append(dict(acct=acct, scene=scn, cur_reach_min=min(cr), cur_fail_max=max(cf), verdict=(f"変更候補: {sorted(cand)[0][2]}" if cand else "現行維持"), **{vn: f"{min(four(vn)[0]):.1f} / {max(four(vn)[1]):.1f}" for vn in [v[0] for v in VARS]}))
for acct, g_ in F.groupby("acct", sort=False):
    g_ = g_.assign(surv10=g_[["surv10_lo", "surv10_cl"]].min(axis=1), mean10=g_[["mean10_lo", "mean10_cl"]].min(axis=1)); cur = g_[g_.variant == "(a) 現行"].iloc[0]
    cand = g_[g_.variant.isin(["(b) v4 半分", "(c) v4 なし"]) & (g_.surv10 >= cur.surv10) & (g_.mean10 >= cur.mean10 - 3.0) & ((g_.surv10 >= cur.surv10 + 5.0) | (g_.mean10 >= cur.mean10 + 3.0))].sort_values("surv10", ascending=False)
    picks.append(dict(acct=acct, scene="(iii) 本口座 10 年(存続 / 累計出金)", cur_reach_min=cur.surv10, cur_fail_max=cur.mean10, verdict=(f"変更候補: {cand.iloc[0].variant}" if len(cand) else "現行維持"), **{r.variant: f"{r.surv10:.1f} / {r.mean10:.1f}" for r in g_.itertuples()}))
Pk = pd.DataFrame(picks); Pk.to_csv("results/q207_usdjpy_v4_leg_in_account_model_pick.csv", index=False)
pd.set_option("display.width", 330); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 300)
print("\n== v4 単独(口座の大きさ) ==\n" + I.to_string(index=False)); print("\n== 推奨(評価中 = 到達の最小 / 失格の最大・本口座 = 10 年存続 / 累計出金) ==\n" + Pk.to_string(index=False))
print("\n== 評価中 ==\n" + D.to_string(index=False)); print("\n== 本口座 ==\n" + F.to_string(index=False))
