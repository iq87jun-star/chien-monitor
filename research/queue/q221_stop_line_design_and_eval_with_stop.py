# -*- coding: utf-8 -*-
"""docs/244 Q221(診断・セル 0・2026-11-15 登録「登録して実行」): (A) 本口座後の EA の全停止線の置き方 × 損失枠比例の縮小の下限。(B) 評価中の到達率・失格率を EA の実際の停止線で出し直す。
モデルは Q208 / Q210 / docs/241 §1bb と同じ。数量の段階は LV(0.1〜1.0)に細かくした。
(A) S0 現行の停止線 / S1 −9.5% / S2 −9.8% / S3 止めずに残りの枠に合わせて絞る / S4・S5 縮小の下限 0.25・0.75 / S6 = S3 + 下限 0.25。4 週ごとに全額出金。全期間 20,000 × 520 週・2016〜21 年のみ 10,000 × 260 週。
(B) いまの段階・次の段階 × {失格線そのもの, EA の停止線}。2 窓・20,000 × 52 週・月曜レグのみ。
使い方: cd research && python3 -W ignore queue/q221_stop_line_design_and_eval_with_stop.py   出力: results/q221_stop_line_design_funded.csv・_eval.csv・_pick.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
_src = open(os.path.join(HERE, "q208_funded_non_monday_legs.py"), encoding="utf-8").read().split("\nrows = []\nfor a in cfg")[0]; n8 = {"__name__": "q208_head", "__file__": os.path.join(HERE, "q208_funded_non_monday_legs.py")}; exec(compile(_src, "q208_head", "exec"), n8)
cfg, table, run_guard, account_items, paths_fac, scaled, weak_flags, states_h1, WFN, PRK, ROLL, P0, PM, P1 = (n8[k] for k in ("cfg", "table", "run_guard", "account_items", "paths_fac", "scaled", "weak_flags", "states_h1", "WFN", "PRK", "ROLL", "P0", "PM", "P1"))
LV = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.625, 0.75, 0.875, 1.0]); NP = 20000; MARGIN = 0.002
def acct(k): return [x for x in cfg["accounts"] if k in x["name"]][0]
def norm_items(key):
    a = acct(key); aid, items, cap, g = account_items(a); fxs = sum(w for s, i, w in items if not i); return [(s, i, w / fxs) for s, i, w in items], cap, g
MON4, _, _ = norm_items("521100397"); RD = {pd.Timestamp(d): float(v) for d, v in ROLL.items() if v == v}
def make_fac(items, skew, tilt):
    fx = [(s, w) for s, i, w in items if not i]; flags = {}; skf = {}
    for s, w in fx:
        dts = [pd.Timestamp(d) for d in table(s, False)[0].date.unique()]; hit, valid = weak_flags(s, states_h1, dts, WFN); flags[s] = {d: bool(h and v) for d, h, v in zip(dts, hit, valid)}
        if skew: pr = PRK.reindex(pd.DatetimeIndex(dts) - pd.Timedelta(days=3), method="ffill").values; skf[s] = {d: 0.0 for d, p in zip(dts, pr) if p == p and p > 0.8}
    return {(s, False): {d: skf.get(s, {}).get(d, 1.0) * (1.0 if (wk or not tilt) else 0.5) for d, wk in flags[s].items()} for s, w in fx}
_T = {}
def build_full(key, items, cap, g, skew, tilt, mult):
    """T[tag] = (pnl[L,n], fired[L,n], peak[L,n])・dates。数量の段階 = LV × mult。"""
    k = (key, skew, tilt, round(mult, 4))
    if k in _T: return _T[k]
    fac = make_fac(items, skew, tilt); PA = paths_fac(items, None, fac, P0, P1) if cap is None else None; out = {"lo": [], "cl": []}; dates = None
    for lv in LV:
        P = scaled(PA, lv * mult) if PA is not None else paths_fac([(sy, ix, w * lv * mult) for sy, ix, w in items], cap, fac, P0, P1); dates = np.array([pd.Timestamp(p["d"]) for p in P]); R = run_guard(P, g)
        for tag in ("lo", "cl"): out[tag].append(R[tag][:3])
    _T[k] = ({tag: tuple(np.array([x[i] for x in out[tag]]) for i in range(3)) for tag in out}, dates); return _T[k]
def roll_week(dates, rw, g):
    add = []
    for d in dates:
        c = 0.0
        for j in range(1, 7):
            x = RD.get(pd.Timestamp(d) + pd.Timedelta(days=j), 0.0) * rw; c += (-g * 1.1 if x <= -g else x)
        add.append(c)
    return np.array(add)
def level_idx(s, floor_mode):
    if floor_mode: gi = np.searchsorted(LV, s + 1e-12, side="right") - 1; return np.clip(gi, 0, len(LV) - 1), gi >= 0
    return np.abs(LV[None, :] - s[:, None]).argmin(axis=1), np.ones(len(s), bool)
def sim_funded(T, add, cols, mdd, pad, smin, trail, roomcap, g, weeks, n_paths, seed=187):
    pnl, fired = T[0][:, cols], T[1][:, cols]; add = add[cols]; n = pnl.shape[1]; rng = np.random.default_rng(seed); c = np.zeros(n_paths); hwm = np.zeros(n_paths); alive = np.ones(n_paths, bool); fires = np.zeros(n_paths, int); paid = np.zeros(n_paths); out = {}
    for w in range(weeks):
        if w % 4 == 0:
            fires[:] = 0
            if w > 0: pay = np.where(alive, np.maximum(c, 0.0), 0.0); paid += pay; c = c - pay; hwm = np.where(pay > 0, c, hwm) if trail else hwm
        idx = rng.integers(0, n, n_paths); floor = (np.minimum(hwm, 0.10) - mdd) if trail else np.full(n_paths, -mdd)
        s = np.ones(n_paths) if smin is None else np.clip((c - floor) / mdd, smin, 1.0); fr = np.ones(n_paths)
        if roomcap: fr = np.clip((c - floor - MARGIN) / (g * 1.1), 0.0, 1.0); s = s * fr
        gi, tr = level_idx(s, roomcap); act = alive & (fires < 2) & tr
        c = c + np.where(act, pnl[gi, idx], 0.0) + np.where(alive, add[idx] * fr, 0.0); fires += np.where(act, fired[gi, idx], 0); alive &= ~(c <= floor + pad); hwm = np.maximum(hwm, c)
        if w + 1 in (52, 260, 520): out[w + 1] = (float(alive.mean()) * 100, float(paid.mean()) * 100, float((alive & (c - floor < 0.02)).sum() / max(alive.sum(), 1)) * 100)
    return out
def sim_eval(T, cols, start, target, mdd, pad, smin, trail, weeks=52, n_paths=NP, seed=187):
    pnl, fired, peak = T[0][:, cols], T[1][:, cols], T[2][:, cols]; n = pnl.shape[1]; rng = np.random.default_rng(seed); c = np.full(n_paths, float(start)); hwm = np.full(n_paths, max(float(start), 0.0)); alive = np.ones(n_paths, bool); res = np.zeros(n_paths, int); wk = np.zeros(n_paths, int); fires = np.zeros(n_paths, int)
    for w in range(weeks):
        if w % 4 == 0: fires[:] = 0
        idx = rng.integers(0, n, n_paths); floor = (np.minimum(hwm, 0.10) - mdd) if trail else np.full(n_paths, -mdd)
        s = np.ones(n_paths) if smin is None else np.clip((c - floor) / mdd, smin, 1.0); gi, _ = level_idx(s, False); act = alive & (fires < 2)
        x = np.where(act, pnl[gi, idx], 0.0); pk = np.where(act, peak[gi, idx], -1.0); hit = alive & ((c + pk >= target) | (c + x >= target)); c = c + x; fires += np.where(act, fired[gi, idx], 0); res[hit] = 1; wk[hit] = w + 1; alive &= ~hit
        dead = alive & (c <= floor + pad); res[dead] = 2; alive &= ~dead; hwm = np.maximum(hwm, c)
    ok = res == 1; return float(ok.mean()) * 100, float((res == 2).mean()) * 100, (int(np.median(wk[ok])) if ok.any() else None)
pd.set_option("display.width", 320); pd.set_option("display.max_rows", 600); pd.set_option("display.max_columns", 40)
# ---------------- (A) 本口座後 ----------------
# 表示名, 口座キー, 月曜の構成(None = 口座のもの), cap の上書き, SKEW, 追随型, 200 日線, 現行の停止線の手前幅, 円クロス倍率(決定 / 参考), ロール
A = [("FTMO 50k ×2", "521100397", None, None, False, False, True, 0.01, (3.75, 4.5), 0.0), ("宝くじ", "531343523", None, None, True, False, True, 0.005, (4.0, 5.0), 0.0),
     ("1-Step", "531466484", None, "acct", True, True, False, 0.01, (2.43,), 0.0), ("トパーズ", "6104739", None, None, True, False, True, 0.01, (3.0, 4.0), 4.5),
     ("ルビー / パール", "6104736", None, None, False, False, True, 0.01, (2.78, 3.13), 4.5), ("FN 14074882", "14074882", None, (0.024, "A"), True, False, True, 0.01, (4.0,), 0.0),
     ("FN 14166201", "14166201", MON4, (0.024, "A"), False, False, True, 0.01, (3.0,), 4.5)]
rows = []
for nm, key, itov, capov, skew, trail, tilt, pad0, mults, rw in A:
    if itov is None: items, cap, g = norm_items(key)
    else: items, cap, g = itov, None, 0.04
    cap = cap if capov == "acct" else capov
    for mi, mm in enumerate(mults):
        T, dates = build_full(key, items, cap, g, skew, tilt, mm); call = np.arange(len(dates)); c2 = call[np.array([d < PM for d in dates])]; add = roll_week(dates, rw, g) if rw else np.zeros(len(dates))
        V = [("S0 現行の停止線", pad0, 0.5, False), ("S1 −9.5% で停止", 0.005, 0.5, False), ("S2 −9.8% で停止", 0.002, 0.5, False), ("S3 止めずに残りの枠に合わせて絞る", 0.0, 0.5, True), ("S4 現行の停止線・縮小の下限 0.25", pad0, 0.25, False), ("S5 現行の停止線・縮小の下限 0.75", pad0, 0.75, False), ("S6 絞って続ける + 下限 0.25", 0.0, 0.25, True)]
        for vn, pad, smin, rc in V:
            r = dict(acct=nm, mon=mm, decided=(mi == 0), roll=rw, variant=vn)
            for tag in ("lo", "cl"):
                m = sim_funded(T[tag], add, call, 0.10, pad, smin, trail, rc, g, 520, NP); m2 = sim_funded(T[tag], add, c2, 0.10, pad, smin, trail, rc, g, 260, 10000)
                r.update({f"s1_{tag}": m[52][0], f"s5_{tag}": m[260][0], f"s10_{tag}": m[520][0], f"p5_{tag}": m[260][1], f"p10_{tag}": m[520][1], f"stuck10_{tag}": m[520][2], f"w2s5_{tag}": m2[260][0], f"w2p5_{tag}": m2[260][1]})
            rows.append(r)
        print("A done", nm, mm, flush=True)
DA = pd.DataFrame(rows)
for k in ("s1", "s5", "s10", "p5", "p10", "w2s5", "w2p5"): DA[k] = DA[[f"{k}_lo", f"{k}_cl"]].min(axis=1).round(1)
DA["stuck10"] = DA[["stuck10_lo", "stuck10_cl"]].max(axis=1).round(1); DA.to_csv("results/q221_stop_line_design_funded.csv", index=False); picks = []
for (nm, mm), x in DA[DA.decided].groupby(["acct", "mon"], sort=False):
    b = x[x.variant.str.startswith("S0")].iloc[0]; pick = None
    for pre in ("S1", "S2", "S3"):
        v = x[x.variant.str.startswith(pre)].iloc[0]
        if v.s10 >= b.s10 + 5.0 and v.p10 >= b.p10 and v.w2s5 >= b.w2s5: pick = v; break
    picks.append(dict(acct=nm, mon=mm, base=f"{b.s1:.0f} / {b.s5:.0f} / {b.s10:.0f}・{b.w2s5:.0f}・+{b.p5:.0f} / +{b.p10:.0f}", verdict=("変更候補: " + pick.variant if pick is not None else "現行どおり"), pick=(f"{pick.s1:.0f} / {pick.s5:.0f} / {pick.s10:.0f}・{pick.w2s5:.0f}・+{pick.p5:.0f} / +{pick.p10:.0f}" if pick is not None else "—")))
PK = pd.DataFrame(picks); PK.to_csv("results/q221_stop_line_design_pick.csv", index=False)
print("\n== (A) 本口座後(1 年 / 5 年 / 10 年存続・2016〜21 年のみ 5 年存続・累計出金 5 年 / 10 年・S3 / S6 は動けない口座の割合) =="); print(DA[["acct", "mon", "decided", "roll", "variant", "s1", "s5", "s10", "w2s5", "p5", "p10", "stuck10"]].to_string(index=False)); print(); print(PK.to_string(index=False))
# ---------------- (B) 評価中 ----------------
# 表示名, 口座キー, 段階, 円クロス倍率, SKEW, 200 日線, 縮小の下限, 追随型, 開始, 目標, 現行の停止線の手前幅, cap("acct" = 口座のもの)
B = [("FTMO 0397", "521100397", "いま", 6.0, False, False, None, False, 54835 / 5e4 - 1, 0.10, 0.01, None), ("FTMO 7058", "531407058", "いま", 6.0, False, False, None, False, 53683 / 5e4 - 1, 0.10, 0.01, None),
     ("FTMO 50k", "521100397", "次", 6.0, False, True, 0.5, False, 0.0, 0.05, 0.01, None),
     ("宝くじ", "531343523", "いま", 8.0, True, False, 0.5, False, 97354 / 1e5 - 1, 0.10, 0.005, None), ("宝くじ", "531343523", "次", 8.0, True, True, 0.5, False, 0.0, 0.05, 0.005, None),
     ("1-Step", "531466484", "いま", None, True, False, None, True, 102722 / 1e5 - 1, 0.10, 0.01, "acct"),
     ("トパーズ", "6104739", "いま", 8.0, False, False, None, False, 37535714 / 35e6 - 1, 0.08, 0.01, None), ("トパーズ", "6104739", "次(6 倍)", 6.0, True, True, 0.5, False, 0.0, 0.06, 0.01, None),
     ("ルビー", "6104736", "いま", 8.35, False, True, 0.5, False, 10348782 / 1e7 - 1, 0.08, 0.01, None), ("ルビー", "6104736", "次(8.35 倍)", 8.35, False, True, 0.5, False, 0.0, 0.06, 0.01, None), ("ルビー", "6104736", "次(6.3 倍)", 6.3, False, True, 0.5, False, 0.0, 0.06, 0.01, None),
     ("パール", "6071612", "いま", 5.57, False, False, None, False, 5291106 / 5e6 - 1, 0.08, 0.01, None), ("パール", "6071612", "次", 5.57, False, True, 0.5, False, 0.0, 0.06, 0.01, None),
     ("FN 14074882", "14074882", "いま", 4.0, True, False, None, False, 93966 / 1e5 - 1, 0.08, 0.003, None), ("FN 14074882", "14074882", "次", 4.0, True, False, None, False, 0.0, 0.05, 0.003, None)]
rowsB = []
for nm, key, stage, mm, skew, tilt, smin, trail, start, target, pad0, capm in B:
    items, cap, g = norm_items(key); cap = cap if capm == "acct" else None
    if mm is None: _, it0, _, _ = account_items(acct(key)); mm = sum(w for s, i, w in it0 if not i)
    T, dates = build_full(key, items, cap, g, skew, tilt, mm); r = dict(acct=nm, stage=stage, mon=round(mm, 2), start_pct=round(start * 100, 2), target_pct=target * 100, stop_pct=-(0.10 - pad0) * 100)
    for wn, sel in (("W1", np.array([d >= PM for d in dates])), ("W2", np.array([d < PM for d in dates]))):
        cols = np.arange(len(dates))[sel]
        for pl, pad in (("line", 0.0), ("stop", pad0)):
            rr = [sim_eval(T[tag], cols, start, target, 0.10, pad, smin, trail) for tag in ("lo", "cl")]
            r[f"reach_{wn}_{pl}"] = round(min(x[0] for x in rr), 1); r[f"fail_{wn}_{pl}"] = round(max(x[1] for x in rr), 1); r[f"weeks_{wn}_{pl}"] = max((x[2] or 0) for x in rr)
    rowsB.append(r); print("B done", nm, stage, flush=True)
DB = pd.DataFrame(rowsB); DB.to_csv("results/q221_stop_line_design_eval.csv", index=False)
print("\n== (B) 評価中(到達 % / 失格 % / 中央の週数。line = 失格線そのもの・stop = EA の停止線。W1 = 2021-08〜2026-07・W2 = 2016-11〜2021-07) =="); print(DB.to_string(index=False))
