# -*- coding: utf-8 -*-
"""docs/244 Q203(診断・セル 0・2026-11-14 登録「登録して実行」): 本口座(資金化後)の月曜枠の倍率と、口座に残す金額を口座ごとに決める。
倍率 = 評価中 × s(8 段階・1-Step は予定の 0.4167 も)。残す金額 B ∈ {0, 3, 5, 8%}(4 週ごとに B を超える利益だけ出金)。失格後は買い直さない。出金は分配前・額面比。
構成 = 2 つの縮小(1-Step は縮小なし / 損失枠比例・追随型 + EA の全停止線)。抽選: 全期間 2016-11〜2026-07(20,000 本 × 520 週)・W1 / W2 のみ(10,000 本 × 260 週)。補助: 実際の順序。
使い方: cd research && python3 -W ignore queue/q203_funded_multiplier_and_retained_buffer.py   出力: results/q203_funded_multiplier_and_retained_buffer.csv・_pick.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
src = open(os.path.join(HERE, "q198_weak_tilt_plus_buffer_sizing.py"), encoding="utf-8").read().split("\nrows = []\nfor a in cfg")[0]
ns = {"__name__": "q198_head", "__file__": os.path.join(HERE, "q198_weak_tilt_plus_buffer_sizing.py")}; exec(compile(src, "q198_head", "exec"), ns)
cfg, table, run_guard, account_items, paths_fac, scaled, weak_flags, states_h1, WFN, GRID, PRK = (ns[k] for k in ("cfg", "table", "run_guard", "account_items", "paths_fac", "scaled", "weak_flags", "states_h1", "WFN", "GRID", "PRK"))
P0, PM, P1 = pd.Timestamp("2016-11-01"), pd.Timestamp("2021-08-01"), pd.Timestamp("2026-07-31"); SC = (0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0, 1.25); BUF = (0.0, 0.03, 0.05, 0.08)
# 口座: (表示名, 予定の s, SKEW, 追随型, 構成 [(名前, 200 日線の縮小, 損失枠比例の下限)], 予定の構成)
ACC = {"521100397": ("FTMO 50k ×2", 1.0, False, False, [("2 つの縮小", True, 0.5)]), "531343523": ("宝くじ", 0.625, True, False, [("2 つの縮小", True, 0.5)]),
       "531466484": ("1-Step", round(1.25 / 3.0, 4), True, True, [("縮小なし", False, None), ("損失枠比例", False, 0.5)]),
       "6104739": ("トパーズ", 0.5, True, False, [("2 つの縮小", True, 0.5)]), "6104736": ("ルビー", 0.5, False, False, [("2 つの縮小", True, 0.5)]), "6071612": ("パール", 1.0, False, False, [("2 つの縮小", True, 0.5)])}
def sim_mc(T, cols, mdd, smin, trail, pad, n_paths, weeks, seed=187):
    """残す金額 BUF の全水準を同じ乱数で同時に計算。戻り値: {週: (存続率[B], 累計出金の平均[B], 中央[B])}"""
    pnl, fired = T[0][:, cols], T[1][:, cols]; n = pnl.shape[1]; nb = len(BUF); rng = np.random.default_rng(seed); B = np.array(BUF)[:, None]
    c = np.zeros((nb, n_paths)); hwm = np.zeros((nb, n_paths)); alive = np.ones((nb, n_paths), bool); fires = np.zeros((nb, n_paths), int); paid = np.zeros((nb, n_paths)); out = {}
    for w in range(weeks):
        if w % 4 == 0:
            fires[:] = 0
            if w > 0:
                pay = np.where(alive, np.maximum(c - B, 0.0), 0.0); paid += pay; c = c - pay; hwm = np.where(pay > 0, c, hwm)
        idx = np.broadcast_to(rng.integers(0, n, n_paths), (nb, n_paths)); floor = (np.minimum(hwm, 0.10) - mdd) if trail else -mdd
        if smin is None: gi = np.full((nb, n_paths), len(GRID) - 1)
        else: gi = np.abs(GRID[None, None, :] - np.clip((c - floor) / mdd, smin, 1.0)[:, :, None]).argmin(axis=2)
        act = alive & (fires < 2); c = c + np.where(act, pnl[gi, idx], 0.0); fires += np.where(act, fired[gi, idx], 0)
        alive &= ~(c <= floor + pad); hwm = np.maximum(hwm, c)
        if w + 1 in (52, 260, 520):
            tot = paid + np.where(alive, np.maximum(c - (B if w + 1 == 52 else 0.0), 0.0), 0.0); out[w + 1] = (alive.mean(axis=1) * 100, tot.mean(axis=1) * 100, np.median(tot, axis=1) * 100)
    return out
def sim_seq(T, dates, mdd, smin, trail, pad, B, start):
    pnl, fired = T[0], T[1]; c = 0.0; hwm = 0.0; paid = 0.0; fm = {}; last = None; fail = None
    for i, d in enumerate(dates):
        if d < start: continue
        ym = (d.year, d.month)
        if last is not None and ym != last:
            pay = max(c - B, 0.0); paid += pay; c -= pay
            if pay > 0: hwm = c
        last = ym; floor = (min(hwm, 0.10) - mdd) if trail else -mdd
        if fm.get(ym, 0) >= 2: continue
        gi = len(GRID) - 1 if smin is None else int(np.abs(GRID - np.clip((c - floor) / mdd, smin, 1.0)).argmin())
        c += float(pnl[gi, i]); fm[ym] = fm.get(ym, 0) + int(fired[gi, i])
        if c <= floor + pad: fail = d; break
        hwm = max(hwm, c)
    return round((paid + (max(c, 0.0) if fail is None else 0.0)) * 100, 1), ("存続" if fail is None else f"失格 {fail.date()}")
rows = []
for a in cfg["accounts"]:
    aid, items, cap, g = account_items(a)
    if aid not in ACC: continue
    nm, splan, skew, trail, variants = ACC[aid]; mdd = float(a["mdd"]); pad = 0.01 if trail else 0.0; fx = [(s, w) for s, idxf, w in items if not idxf]; fxm = sum(w for _, w in fx); flags = {}; skf = {}
    for s, w in fx:
        dts = [pd.Timestamp(d) for d in table(s, False)[0].date.unique()]; hit, valid = weak_flags(s, states_h1, dts, WFN); flags[s] = {d: bool(h and v) for d, h, v in zip(dts, hit, valid)}
        if skew:
            pr = PRK.reindex(pd.DatetimeIndex(dts) - pd.Timedelta(days=3), method="ffill").values; skf[s] = {d: 0.0 for d, p in zip(dts, pr) if p == p and p > 0.8}
    scs = sorted(set(SC) | {splan})
    for tilt in sorted({v[1] for v in variants}):
        fac = {(s, False): {d: skf.get(s, {}).get(d, 1.0) * (1.0 if (wk or not tilt) else 0.5) for d, wk in flags[s].items()} for s, w in fx}
        P1_ = None if cap else paths_fac(items, cap, fac, P0, P1)
        for s_ in scs:
            out = {"lo": [], "cl": []}; dates = None
            for lv in GRID:
                P = scaled(P1_, lv * s_) if P1_ is not None else paths_fac([(sy, ix, w * lv * s_) for sy, ix, w in items], cap, fac, P0, P1); R = run_guard(P, g); dates = [pd.Timestamp(p["d"]) for p in P]
                for tag in ("lo", "cl"): out[tag].append(R[tag][:2])
            T = {tag: tuple(np.array([x[i] for x in out[tag]]) for i in range(2)) for tag in out}; dts_ = np.array(dates); call = np.arange(len(dates)); c1 = call[dts_ >= PM]; c2 = call[dts_ < PM]
            for vn, vt, smin in variants:
                if vt != tilt: continue
                R_ = {tag: dict(all=sim_mc(T[tag], call, mdd, smin, trail, pad, 20000, 520), w1=sim_mc(T[tag], c1, mdd, smin, trail, pad, 10000, 260), w2=sim_mc(T[tag], c2, mdd, smin, trail, pad, 10000, 260)) for tag in ("lo", "cl")}
                for bi, B in enumerate(BUF):
                    r = dict(acct=nm, variant=vn, s=s_, fx_mult=round(fxm * s_, 2), buf_pct=B * 100, plan=bool(abs(s_ - splan) < 1e-6 and B == 0.0 and vn == variants[0][0]))
                    for tag in ("lo", "cl"):
                        m = R_[tag]["all"]; r.update({f"y1_{tag}": round(float(m[52][1][bi]), 1), f"surv5_{tag}": round(float(m[260][0][bi]), 1), f"surv10_{tag}": round(float(m[520][0][bi]), 1), f"mean5_{tag}": round(float(m[260][1][bi]), 1), f"mean10_{tag}": round(float(m[520][1][bi]), 1), f"med10_{tag}": round(float(m[520][2][bi]), 1)})
                        for wn in ("w1", "w2"): r.update({f"{wn}_surv5_{tag}": round(float(R_[tag][wn][260][0][bi]), 1), f"{wn}_mean5_{tag}": round(float(R_[tag][wn][260][1][bi]), 1)})
                        for lab, st in (("seq2016", P0), ("seq2021", PM)):
                            tot, stt = sim_seq(T[tag], dates, mdd, smin, trail, pad, B, st); r[f"{lab}_{tag}"] = f"{tot:+.1f}% {stt}"
                    rows.append(r)
    print(nm, "done", flush=True)
D = pd.DataFrame(rows); D["surv10"] = D[["surv10_lo", "surv10_cl"]].min(axis=1); D["w2_surv5"] = D[["w2_surv5_lo", "w2_surv5_cl"]].min(axis=1); D["mean10"] = D[["mean10_lo", "mean10_cl"]].min(axis=1); D["ok"] = (D.surv10 >= 75.0) & (D.w2_surv5 >= 65.0)
D.to_csv("results/q203_funded_multiplier_and_retained_buffer.csv", index=False); picks = []
def best_of(x):
    if x.empty: return None
    top = x.mean10.max(); return x[x.mean10 >= top - 3.0].sort_values(["surv10", "mean10"], ascending=[False, False]).iloc[0]
for acct, g_ in D.groupby("acct", sort=False):
    plan = g_[g_.plan].iloc[0]; ok = g_[g_.ok]; best = best_of(ok)
    if best is None: verdict = "条件を満たす組み合わせなし"
    elif bool(plan.ok) and best.mean10 - plan.mean10 < 5.0: verdict = "予定どおり"
    else: verdict = f"変更候補: {best.variant}・月曜 {best.fx_mult} 倍(s {best.s})・残す {best.buf_pct:.0f}%"
    picks.append(dict(acct=acct, kind="総合", variant=plan.variant, plan_fx=plan.fx_mult, plan_surv10=plan.surv10, plan_w2_surv5=plan.w2_surv5, plan_mean10=plan.mean10, plan_ok=bool(plan.ok), best_variant=(best.variant if best is not None else ""), best_fx=(best.fx_mult if best is not None else None), best_buf=(best.buf_pct if best is not None else None), best_surv10=(best.surv10 if best is not None else None), best_w2_surv5=(best.w2_surv5 if best is not None else None), best_mean10=(best.mean10 if best is not None else None), verdict=verdict))
    for B, gb in g_.groupby("buf_pct"):
        b = best_of(gb[gb.ok])
        picks.append(dict(acct=acct, kind=f"残す {B:.0f}%", best_variant=(b.variant if b is not None else ""), best_fx=(b.fx_mult if b is not None else None), best_buf=B, best_surv10=(b.surv10 if b is not None else None), best_w2_surv5=(b.w2_surv5 if b is not None else None), best_mean10=(b.mean10 if b is not None else None), verdict=("" if b is not None else "候補なし")))
Pk = pd.DataFrame(picks); Pk.to_csv("results/q203_funded_multiplier_and_retained_buffer_pick.csv", index=False)
pd.set_option("display.width", 360); pd.set_option("display.max_columns", 60); pd.set_option("display.max_rows", 900)
print("\n== 推奨 ==\n" + Pk.to_string(index=False))
print("\n== 全行 ==\n" + D[["acct", "variant", "fx_mult", "buf_pct", "plan", "ok", "y1_lo", "surv5_lo", "surv10_lo", "surv10_cl", "mean5_lo", "mean10_lo", "mean10_cl", "med10_lo", "w1_surv5_lo", "w2_surv5_lo", "w2_surv5_cl", "w1_mean5_lo", "w2_mean5_lo", "seq2016_lo", "seq2021_lo"]].to_string(index=False))
