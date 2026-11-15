# -*- coding: utf-8 -*-
"""docs/244 Q233(診断・セル 0・2026-11-15 登録「登録して実行」): 月曜の円クロスの決済の形を口座モデルで比べる。
現行(全通貨 24h)/ M3(200 日線より上の通貨だけ同日 20 UTC)/ E1(前金曜 VIX ≤ 25 の週は全通貨 20 UTC・25 超は 24h)/ E2(24h は 200 日線の下 かつ VIX > 25 の通貨だけ)。
モデル・場面・開始残高・乱数は Q230 と同じ(スクリプトは Q230 から決済の条件だけを一般化)。数量は変えない。
使い方: cd research && python3 -W ignore queue/q233_exit_switch_line_vs_vix_account_model.py   出力: results/q233_exit_switch_funded.csv・_eval.csv・_instant.csv・_pick.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
import q_common as q
_src = open(os.path.join(HERE, "q208_funded_non_monday_legs.py"), encoding="utf-8").read().split("\nrows = []\nfor a in cfg")[0]; n8 = {"__name__": "q208_head", "__file__": os.path.join(HERE, "q208_funded_non_monday_legs.py")}; exec(compile(_src, "q208_head", "exec"), n8)
cfg, table0, run_guard, account_items, paths_fac, scaled, weak_flags, states_h1, WFN, PRK, ROLL, build, P0, PM, P1 = (n8[k] for k in ("cfg", "table", "run_guard", "account_items", "paths_fac", "scaled", "weak_flags", "states_h1", "WFN", "PRK", "ROLL", "build", "P0", "PM", "P1"))
LV = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.625, 0.75, 0.875, 1.0]); n8["GRID"] = LV; NP = 20000; SMIN = 0.25; K = paths_fac.__globals__["K"]; X20 = 16          # 経路の添字 16 = 月曜 20:00 UTC(04:00 起点)
MODE = {"k": None}; _M3 = {}; _FL = {}
_V = pd.read_csv("data_ext/VIX_History.csv"); _V["d"] = pd.to_datetime(_V["DATE"]); VIX = _V.set_index("d")["CLOSE"].sort_index().astype(float)
def hot(d):
    """前金曜の VIX が 25 超か。"""
    v = VIX.reindex([pd.Timestamp(d) - pd.Timedelta(days=3)], method="ffill").values[0]; return bool(v == v and v > 25)
def hold24(kind, d, weak):
    """True = 24 時間持つ。M3: 線の下。E1: VIX 25 超の週。E2: 線の下 かつ VIX 25 超。"""
    wk = weak.get(d, False)
    return wk if kind == "M3" else (hot(d) if kind == "E1" else (wk and hot(d)))
def flags_of(s):
    if s not in _FL:
        dts = [pd.Timestamp(d) for d in table0(s, False)[0].date.unique()]; hit, valid = weak_flags(s, states_h1, dts, WFN); _FL[s] = {d: bool(h and v) for d, h, v in zip(dts, hit, valid)}
    return _FL[s]
def table_x(sym, idx):
    """MODE['k'] が M3 / E1 / E2 のとき、24 時間持たない(hold24 が False の)月曜のショットを 20:00 UTC の始値で決済する経路に差し替える。"""
    if idx or MODE["k"] is None: return table0(sym, idx)
    kind = MODE["k"]
    if (sym, kind) in _M3: return _M3[(sym, kind)]
    M, res = table0(sym, False); Rk = res[K]; weak = flags_of(sym); o = q.load(sym)["open"]; mark = Rk["mark"].copy(); worst = Rk["worst"].copy(); r = Rk["r"].copy(); stop = Rk["stop"].copy(); n_ch = 0
    for i, (d, t) in enumerate(zip(M.date.values, M.t.values)):
        d = pd.Timestamp(d); t = pd.Timestamp(t)
        if hold24(kind, d, weak) or stop[i] < X20: continue
        e = o.get(t, np.nan); o20 = o.get(d + pd.Timedelta(hours=20), np.nan)
        if e != e or o20 != o20: continue
        r20 = float(o20) / float(e) - 1 - float(q.cost(sym, [float(e)])[0]); mark[i, X20:] = r20; worst[i, X20:] = r20; r[i] = r20; stop[i] = X20; n_ch += 1
    res2 = dict(res); res2[K] = dict(Rk, mark=mark, worst=worst, r=r, stop=stop); _M3[(sym, kind)] = (M, res2); print(f"  [{kind} 経路] {sym}: {n_ch} / {len(M)} ショットを 20 UTC 決済に差し替え", flush=True); return _M3[(sym, kind)]
paths_fac.__globals__["table"] = table_x
def acct(k): return [x for x in cfg["accounts"] if k in x["name"]][0]
def norm_items(key):
    a = acct(key); aid, items, cap, g = account_items(a); fxs = sum(w for s, i, w in items if not i); return [(s, i, w / fxs) for s, i, w in items], cap, g
MON4, _, _ = norm_items("521100397"); RD = {pd.Timestamp(d): float(v) for d, v in ROLL.items() if v == v}
def make_fac(items, skew, lo):
    fx = [(s, w) for s, i, w in items if not i]; skf = {}
    for s, w in fx:
        if skew: dts = list(flags_of(s).keys()); pr = PRK.reindex(pd.DatetimeIndex(dts) - pd.Timedelta(days=3), method="ffill").values; skf[s] = {d: 0.0 for d, p in zip(dts, pr) if p == p and p > 0.8}
    return {(s, False): {d: skf.get(s, {}).get(d, 1.0) * (1.0 if (wk or lo is None) else lo) for d, wk in flags_of(s).items()} for s, w in fx}
def build_full(items, cap, g, fac, mult):
    PA = paths_fac(items, None, fac, P0, P1) if cap is None else None; out = {"lo": [], "cl": []}; dates = None
    for lv in LV:
        P = scaled(PA, lv * mult) if PA is not None else paths_fac([(sy, ix, w * lv * mult) for sy, ix, w in items], cap, fac, P0, P1); dates = np.array([pd.Timestamp(p["d"]) for p in P]); R = run_guard(P, g)
        for tag in ("lo", "cl"): out[tag].append(R[tag][:3])
    return {tag: tuple(np.array([x[i] for x in out[tag]]) for i in range(3)) for tag in out}, dates
def roll_week(dates, rw, g):
    add = []
    for d in dates:
        c = 0.0
        for j in range(1, 7):
            x = RD.get(pd.Timestamp(d) + pd.Timedelta(days=j), 0.0) * rw; c += (-g * 1.1 if x <= -g else x)
        add.append(c)
    return np.array(add)
def sim_funded(T, add, cols, mdd, pad, trail, weeks, n_paths, seed=187):          # Q223 の sim と同じ
    pnl, fired = T[0][:, cols], T[1][:, cols]; add = add[cols]; n = pnl.shape[1]; rng = np.random.default_rng(seed); c = np.zeros(n_paths); hwm = np.zeros(n_paths); alive = np.ones(n_paths, bool); fires = np.zeros(n_paths, int); paid = np.zeros(n_paths); out = {}
    for w in range(weeks):
        if w % 4 == 0:
            fires[:] = 0
            if w > 0: pay = np.where(alive, np.maximum(c, 0.0), 0.0); paid += pay; c = c - pay; hwm = np.where(pay > 0, c, hwm) if trail else hwm
        idx = rng.integers(0, n, n_paths); floor = (np.minimum(hwm, 0.10) - mdd) if trail else np.full(n_paths, -mdd); s = np.clip((c - floor) / mdd, SMIN, 1.0); gi = np.abs(LV[None, :] - s[:, None]).argmin(axis=1)
        act = alive & (fires < 2); c = c + np.where(act, pnl[gi, idx], 0.0) + np.where(alive, add[idx], 0.0); fires += np.where(act, fired[gi, idx], 0); alive &= ~(c <= floor + pad); hwm = np.maximum(hwm, c)
        if w + 1 in (52, 260, 520): out[w + 1] = (float(alive.mean()) * 100, float(paid.mean()) * 100)
    return out
def sim_eval(T, cols, start, target, mdd, pad, smin, trail, weeks=52, n_paths=NP, seed=187):          # Q221 の sim_eval と同じ
    pnl, fired, peak = T[0][:, cols], T[1][:, cols], T[2][:, cols]; n = pnl.shape[1]; rng = np.random.default_rng(seed); c = np.full(n_paths, float(start)); hwm = np.full(n_paths, max(float(start), 0.0)); alive = np.ones(n_paths, bool); res = np.zeros(n_paths, int); wk = np.zeros(n_paths, int); fires = np.zeros(n_paths, int)
    for w in range(weeks):
        if w % 4 == 0: fires[:] = 0
        idx = rng.integers(0, n, n_paths); floor = (np.minimum(hwm, 0.10) - mdd) if trail else np.full(n_paths, -mdd)
        s = np.ones(n_paths) if smin is None else np.clip((c - floor) / mdd, smin, 1.0); gi = np.abs(LV[None, :] - s[:, None]).argmin(axis=1); act = alive & (fires < 2)
        x = np.where(act, pnl[gi, idx], 0.0); pk = np.where(act, peak[gi, idx], -1.0); hit = alive & ((c + pk >= target) | (c + x >= target)); c = c + x; fires += np.where(act, fired[gi, idx], 0); res[hit] = 1; wk[hit] = w + 1; alive &= ~hit
        dead = alive & (c <= floor + pad); res[dead] = 2; alive &= ~dead; hwm = np.maximum(hwm, c)
    ok = res == 1; return float(ok.mean()) * 100, float((res == 2).mean()) * 100, (int(np.median(wk[ok])) if ok.any() else None)
pd.set_option("display.width", 340); pd.set_option("display.max_rows", 600); pd.set_option("display.max_columns", 50); pd.set_option("display.max_colwidth", 140); MODES = (("現行(全通貨 24h)", None), ("M3(線の上は 20 UTC)", "M3"), ("E1(VIX ≤ 25 は全通貨 20 UTC)", "E1"), ("E2(24h は線の下 × VIX > 25 だけ)", "E2"))
def one_week_stats(T, dates):
    """数量 1.0 倍の段階での月曜 1 回の平均 %・標準偏差 %・ガード発動率 %(終値判定 / 安値判定の順)。"""
    return {f"wk_mean_{tag}": round(float(T[tag][0][-1].mean()) * 100, 3) for tag in ("cl", "lo")} | {f"wk_sd_{tag}": round(float(T[tag][0][-1].std()) * 100, 3) for tag in ("cl", "lo")} | {f"guard_{tag}": round(float((T[tag][1][-1] > 0).mean()) * 100, 2) for tag in ("cl", "lo")}
# ---------------- (A) 本口座後 ----------------
# 表示名, 口座キー, 月曜の構成(None = 口座のもの), cap("acct" = 口座のもの), SKEW, 追随型, 線の上の倍率(None = 縮小なし), 停止線の手前幅, 円クロス倍率, ロール
A = [("FTMO 50k ×2", "521100397", None, None, False, False, 0.5, 0.01, 3.75, 0.0), ("宝くじ", "531343523", None, None, True, False, 0.5, 0.005, 4.0, 0.0), ("トパーズ", "6104739", None, None, True, False, 0.5, 0.01, 3.0, 4.5),
     ("ルビー / パール", "6104736", None, None, False, False, 0.5, 0.01, 2.78, 4.5), ("1-Step", "531466484", None, "acct", True, True, None, 0.01, 2.43, 0.0),
     ("FN 14074882", "14074882", None, (0.024, "A"), True, False, 0.5, 0.01, 4.0, 0.0), ("FN 14166201", "14166201", MON4, (0.024, "A"), False, False, 0.5, 0.01, 3.0, 4.5)]
rows = []
for nm, key, itov, capov, skew, trail, lo, pad, mm, rw in A:
    if itov is None: items, cap, g = norm_items(key)
    else: items, cap, g = itov, None, 0.04
    cap = cap if capov == "acct" else capov; fac = make_fac(items, skew, lo)
    for mn, md in MODES:
        MODE["k"] = md; T, dates = build_full(items, cap, g, fac, mm); MODE["k"] = None; call = np.arange(len(dates)); c2 = call[np.array([d < PM for d in dates])]; add = roll_week(dates, rw, g) if rw else np.zeros(len(dates))
        r = dict(acct=nm, mode=mn, mon=mm, roll=rw, **one_week_stats(T, dates))
        for tag in ("lo", "cl"):
            m = sim_funded(T[tag], add, call, 0.10, pad, trail, 520, NP); m2 = sim_funded(T[tag], add, c2, 0.10, pad, trail, 260, 10000)
            r.update({f"s1_{tag}": m[52][0], f"s5_{tag}": m[260][0], f"s10_{tag}": m[520][0], f"p5_{tag}": m[260][1], f"p10_{tag}": m[520][1], f"w2s5_{tag}": m2[260][0], f"w2p5_{tag}": m2[260][1]})
        rows.append(r)
    print("A done", nm, flush=True)
DA = pd.DataFrame(rows)
for k in ("s1", "s5", "s10", "p5", "p10", "w2s5", "w2p5"): DA[k] = DA[[f"{k}_lo", f"{k}_cl"]].min(axis=1).round(1)
DA.to_csv("results/q233_exit_switch_funded.csv", index=False); picks = []
def fund_ok(b, v): return bool((v.s10 >= b.s10 + 3.0 and v.p10 >= b.p10) or (v.p10 >= b.p10 + 3.0 and v.s10 >= b.s10 - 1.0 and v.w2s5 >= b.w2s5 - 1.0))
def fund_pick(b, cands):
    c = [v for v in cands if fund_ok(b, v)]
    if not c: return "現行どおり"
    top = max(v.s10 for v in c); c = [v for v in c if v.s10 >= top - 1.0]; return "変更候補: " + max(c, key=lambda v: v.p10)["mode"]
def fund_txt(v): return f"{v.s1:.0f} / {v.s5:.0f} / {v.s10:.0f}・{v.w2s5:.0f}・+{v.p5:.0f} / +{v.p10:.0f}・弱い時期 5 年 +{v.w2p5:.0f}"
for nm, x in DA.groupby("acct", sort=False):
    b = x.iloc[0]; vs = [x.iloc[i] for i in range(1, len(x))]
    picks.append(dict(part="A 本口座後", scene=nm, base=fund_txt(b), M3=fund_txt(vs[0]) + (" ○" if fund_ok(b, vs[0]) else ""), E1=fund_txt(vs[1]) + (" ○" if fund_ok(b, vs[1]) else ""), E2=fund_txt(vs[2]) + (" ○" if fund_ok(b, vs[2]) else ""), verdict=fund_pick(b, vs)))
print("\n== (A) 本口座後(1 年 / 5 年 / 10 年存続・2016〜21 年のみ 5 年存続・累計出金 5 年 / 10 年・2016〜21 年のみ 5 年出金) =="); print(DA[["acct", "mode", "mon", "roll", "wk_mean_cl", "wk_sd_cl", "guard_cl", "guard_lo", "s1", "s5", "s10", "w2s5", "p5", "p10", "w2p5"]].to_string(index=False))
# ---------------- (B) 評価中 ----------------
# 表示名, 口座キー, 段階, 円クロス倍率, SKEW, 200 日線, 縮小の下限, 追随型, 開始, 目標, 停止線の手前幅, cap("acct" = 口座のもの)
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
    fac = make_fac(items, skew, 0.5 if tilt else None)
    for mn, md in MODES:
        MODE["k"] = md; T, dates = build_full(items, cap, g, fac, mm); MODE["k"] = None; r = dict(acct=nm, stage=stage, mode=mn, mon=round(mm, 2), **one_week_stats(T, dates))
        for wn, sel in (("W1", np.array([d >= PM for d in dates])), ("W2", np.array([d < PM for d in dates]))):
            cols = np.arange(len(dates))[sel]; rr = [sim_eval(T[tag], cols, start, target, 0.10, pad0, smin, trail) for tag in ("lo", "cl")]
            r[f"reach_{wn}"] = round(min(x[0] for x in rr), 1); r[f"fail_{wn}"] = round(max(x[1] for x in rr), 1); r[f"weeks_{wn}"] = max((x[2] or 0) for x in rr)
        rowsB.append(r)
    print("B done", nm, stage, flush=True)
DB = pd.DataFrame(rowsB); DB.to_csv("results/q233_exit_switch_eval.csv", index=False)
def ev_ok(b, v): return bool(all(v[f"reach_{w}"] >= b[f"reach_{w}"] - 1.0 and v[f"fail_{w}"] <= b[f"fail_{w}"] + 1.0 for w in ("W1", "W2")) and any(v[f"reach_{w}"] >= b[f"reach_{w}"] + 2.0 or v[f"fail_{w}"] <= b[f"fail_{w}"] - 2.0 for w in ("W1", "W2")))
def ev_pick(b, cands):
    c = [v for v in cands if ev_ok(b, v)]
    if not c: return "現行どおり"
    low = min(v.fail_W1 + v.fail_W2 for v in c); c = [v for v in c if v.fail_W1 + v.fail_W2 <= low + 1.0]; return "変更候補: " + max(c, key=lambda v: v.reach_W1 + v.reach_W2)["mode"]
def ev_txt(v): return f"到達 {v.reach_W1:.0f} / {v.reach_W2:.0f}%・失格 {v.fail_W1:.0f} / {v.fail_W2:.0f}%・{v.weeks_W1} / {v.weeks_W2} 週"
for (nm, stage), x in DB.groupby(["acct", "stage"], sort=False):
    b = x.iloc[0]; vs = [x.iloc[i] for i in range(1, len(x))]
    picks.append(dict(part="B 評価中", scene=f"{nm}・{stage}", base=ev_txt(b), M3=ev_txt(vs[0]) + (" ○" if ev_ok(b, vs[0]) else ""), E1=ev_txt(vs[1]) + (" ○" if ev_ok(b, vs[1]) else ""), E2=ev_txt(vs[2]) + (" ○" if ev_ok(b, vs[2]) else ""), verdict=ev_pick(b, vs)))
print("\n== (B) 評価中(到達 % / 失格 % / 中央の週数。EA の停止線。W1 = 2021-08〜2026-07・W2 = 2016-11〜2021-07) =="); print(DB[["acct", "stage", "mode", "mon", "wk_mean_cl", "wk_sd_cl", "guard_cl", "guard_lo", "reach_W1", "fail_W1", "weeks_W1", "reach_W2", "fail_W2", "weeks_W2"]].to_string(index=False))
# ---------------- (C) 本番中の FN Instant ----------------
a = acct("11988011"); aid, itemsI, capI, gI = account_items(a); mddI = float(a["mdd"]); totI = sum(w for s, i, w in itemsI); START = 20338.37 / 2e4 - 1; ARM = 0.02; KEEP = 0.10; MMI = 1.875; itI = [(sy, ix, w / totI * MMI) for sy, ix, w in itemsI]
FACI = {(s, False): {d: (1.0 if wk else 0.5) for d, wk in flags_of(s).items()} for s, i, w in itemsI if not i}
def sim_inst(T, cols, smin, weeks, n_paths, seed=187):          # Q222 の sim と同じ
    pnl, fired = T[0][:, cols], T[1][:, cols]; n = pnl.shape[1]; rng = np.random.default_rng(seed); c = np.full(n_paths, START); hwm = np.full(n_paths, max(START, 0.0)); alive = np.ones(n_paths, bool); fires = np.zeros(n_paths, int); paid = np.zeros(n_paths); out = {}
    for w in range(weeks):
        if w % 4 == 0:
            fires[:] = 0
            if w > 0: pay = np.where(alive, np.maximum(c - KEEP, 0.0), 0.0); paid += pay; c = c - pay
        floor = np.minimum(hwm - mddI, 0.0); idx = rng.integers(0, n, n_paths); s = np.clip((c - floor) / mddI, smin, 1.0); gi = np.abs(LV[None, :] - s[:, None]).argmin(axis=1)
        act = alive & (fires < 2); c = c + np.where(act, pnl[gi, idx], 0.0); fires += np.where(act, fired[gi, idx], 0); alive &= ~(c <= floor + ARM); hwm = np.maximum(hwm, c)
        if w + 1 in (52, 260, 520): out[w + 1] = (float(alive.mean()) * 100, float(paid.mean()) * 100)
    return out
rowsC = []
for mn, md in MODES:
    MODE["k"] = md; T, dates = build(lambda lv: paths_fac([(sy, ix, w * lv) for sy, ix, w in itI], capI, FACI, P0, P1), gI, None); MODE["k"] = None; dates = pd.DatetimeIndex(dates); call = np.arange(len(dates)); c2 = call[dates < PM]; r = dict(acct="FN Instant(月曜 1.875 倍)", mode=mn)
    for tag in ("lo", "cl"):
        m = sim_inst(T[tag], call, 0.5, 520, NP); m2 = sim_inst(T[tag], c2, 0.5, 260, 10000); r.update({f"s1_{tag}": m[52][0], f"s5_{tag}": m[260][0], f"s10_{tag}": m[520][0], f"p5_{tag}": m[260][1], f"p10_{tag}": m[520][1], f"w2s5_{tag}": m2[260][0], f"w2p5_{tag}": m2[260][1]})
    rowsC.append(r)
DC = pd.DataFrame(rowsC)
for k in ("s1", "s5", "s10", "p5", "p10", "w2s5", "w2p5"): DC[k] = DC[[f"{k}_lo", f"{k}_cl"]].min(axis=1).round(1)
DC.to_csv("results/q233_exit_switch_instant.csv", index=False); b = DC.iloc[0]; vs = [DC.iloc[i] for i in range(1, len(DC))]
picks.append(dict(part="C 本番中", scene="FN Instant", base=fund_txt(b), M3=fund_txt(vs[0]) + (" ○" if fund_ok(b, vs[0]) else ""), E1=fund_txt(vs[1]) + (" ○" if fund_ok(b, vs[1]) else ""), E2=fund_txt(vs[2]) + (" ○" if fund_ok(b, vs[2]) else ""), verdict=fund_pick(b, vs)))
print("\n== (C) 本番中の FN Instant(1 年 / 5 年 / 10 年存続・2016〜21 年のみ 5 年存続・累計出金) =="); print(DC[["acct", "mode", "s1", "s5", "s10", "w2s5", "p5", "p10", "w2p5"]].to_string(index=False))
PK = pd.DataFrame(picks); PK.to_csv("results/q233_exit_switch_pick.csv", index=False); print("\n== 形式の規則による判定 =="); print(PK.to_string(index=False))
