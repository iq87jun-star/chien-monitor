# -*- coding: utf-8 -*-
"""docs/244 Q269 口座モデル(診断・セル 0・2026-11-17 登録): 夜の指数の大きさを VIX の帯で変える形を、Q233・Q263b と同じ場面(本口座後 7 構成・評価中 15 場面)で確かめる。
並べる形: 現行(夜なし)・一律(VIX 25 超・各 0.05)・A(25〜30 各 0.05・30 超 各 0.10)・B(25〜30 各 0.025・30 超 各 0.10)。大きさは円クロスの合計 1.0 に対する比。
夜のレグの作り(月曜 20 UTC 買い・指数の月曜レグと同じ時刻に決済・損切り 3.0 × ATR24)・場面・乱数・判定の式(fund_ok / ev_ok)は Q263b のまま。A・B は「一律」に対しても数える。
使い方: cd research && python3 -W ignore queue/q269b_night_size_by_band_account_model.py   出力: results/q269b_night_size_funded.csv・_eval.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); _s = open(os.path.join(HERE, "q263b_monday_night_index_account_model.py"), encoding="utf-8").read()
n = {"__name__": "q263b_head", "__file__": os.path.join(HERE, "q263b_monday_night_index_account_model.py")}; exec(compile(_s.split("\nrows = []\n")[0], "q263b_head", "exec"), n)          # 定義と本口座後の場面 A
exec(compile("B = [" + _s.split("# ---------------- (B) 評価中")[1].split("\nB = [", 1)[1].split("\nrowsB = []")[0], "q263b_B", "exec"), n)                                   # 評価中の場面 B
np, pd = n["np"], n["pd"]; norm_items, account_items, acct, make_fac, build_full, roll_week, sim_funded, sim_eval, MODE, PM, NP, table_x, paths_fac, fund_ok, ev_ok = (n[k] for k in ("norm_items", "account_items", "acct", "make_fac", "build_full", "roll_week", "sim_funded", "sim_eval", "MODE", "PM", "NP", "table_x", "paths_fac", "fund_ok", "ev_ok"))
VIX = n["n3"]["VIX"]; _hot0 = n["hot"]; _C = {}
def _v(d): x = VIX.reindex([pd.Timestamp(d) - pd.Timedelta(days=3)], method="ffill").values[0]; return x if x == x else 0.0
HOTF = {"N": lambda d: _v(d) > 25, "L": lambda d: 25 < _v(d) <= 30, "H": lambda d: _v(d) > 30}
def band_table(sym, band):
    k = (sym, band)
    if k not in _C: n["hot"] = HOTF[band]; n["_N"].pop(sym, None); _C[k] = n["night_table"](sym); n["_N"].pop(sym, None); n["hot"] = _hot0
    return _C[k]
paths_fac.__globals__["table"] = lambda sym, idx: band_table(sym[:-2], sym[-1]) if sym[-2:] in ("@N", "@L", "@H") else table_x(sym, idx)
IDX = ("NAS100", "US500", "US30", "JP225", "UK100")
def night(wl, wh): return ([(s + "@L", True, wl) for s in IDX] if wl > 0 else []) + [(s + "@H", True, wh) for s in IDX]
VARS = (("現行", []), ("一律", [(s + "@N", True, 0.05) for s in IDX]), ("A", night(0.05, 0.10)), ("B", night(0.025, 0.10)))
rows = []
for nm, key, itov, capov, skew, trail, lo, pad, mm, rw, mode in n["A"]:
    if itov is None: items, cap, g = norm_items(key)
    else: items, cap, g = itov, None, 0.04
    cap = cap if capov == "acct" else capov; fac = make_fac(items, skew, lo)
    for vn, add_ in VARS:
        MODE["k"] = mode; T, dates = build_full(list(items) + add_, cap, g, fac, mm); MODE["k"] = None; call = np.arange(len(dates)); c2 = call[np.array([d < PM for d in dates])]; add = roll_week(dates, rw, g) if rw else np.zeros(len(dates)); r = dict(acct=nm, variant=vn, mode=mode or "24h", mon=mm, guard_lo=round(float((T["lo"][1][-1] > 0).mean()) * 100, 2), wk_mean=round(float(T["cl"][0][-1].mean()) * 100, 3))
        for tag in ("lo", "cl"):
            m = sim_funded(T[tag], add, call, 0.10, pad, trail, 520, NP); m2 = sim_funded(T[tag], add, c2, 0.10, pad, trail, 260, 10000); r.update({f"s10_{tag}": m[520][0], f"p10_{tag}": m[520][1], f"s5_{tag}": m[260][0], f"w2s5_{tag}": m2[260][0]})
        for k in ("s10", "p10", "s5", "w2s5"): r[k] = round(min(r[f"{k}_lo"], r[f"{k}_cl"]), 1)
        rows.append(r)
    print("A done", nm, flush=True)
DA = pd.DataFrame(rows); DA.to_csv("results/q269b_night_size_funded.csv", index=False)
rowsB = []
for nm, key, stage, mm, skew, tilt, smin, trail, start, target, pad0, capm, mode in n["B"]:
    items, cap, g = norm_items(key); cap = cap if capm == "acct" else None
    if mm is None: _, it0, _, _ = account_items(acct(key)); mm = sum(w for s, i, w in it0 if not i)
    fac = make_fac(items, skew, 0.5 if tilt else None)
    for vn, add_ in VARS:
        MODE["k"] = mode; T, dates = build_full(list(items) + add_, cap, g, fac, mm); MODE["k"] = None; r = dict(acct=nm, stage=stage, variant=vn, mode=mode or "24h", mon=round(mm, 2), guard_lo=round(float((T["lo"][1][-1] > 0).mean()) * 100, 2))
        for wn, sel in (("W1", np.array([d >= PM for d in dates])), ("W2", np.array([d < PM for d in dates]))):
            cols = np.arange(len(dates))[sel]; rr = [sim_eval(T[tag], cols, start, target, 0.10, pad0, smin, trail) for tag in ("lo", "cl")]; r[f"reach_{wn}"] = round(min(x[0] for x in rr), 1); r[f"fail_{wn}"] = round(max(x[1] for x in rr), 1); r[f"weeks_{wn}"] = max((x[2] or 0) for x in rr)
        rowsB.append(r)
    print("B done", nm, stage, flush=True)
DB = pd.DataFrame(rowsB); DB.to_csv("results/q269b_night_size_eval.csv", index=False)
pd.set_option("display.width", 320); pd.set_option("display.max_rows", 300); pd.set_option("display.max_colwidth", 40)
print("\n== (A) 本口座後(10 年存続 % / 10 年の累計出金 % / 5 年存続 / 2016〜21 年の 5 年存続。安値・終値の悪い方) =="); print(DA[["acct", "variant", "mode", "mon", "guard_lo", "wk_mean", "s10", "p10", "s5", "w2s5"]].to_string(index=False))
cnt = {}
for nm, x in DA.groupby("acct", sort=False):
    b0, u, a, b = (x[x.variant == k].iloc[0] for k in ("現行", "一律", "A", "B")); res = {"一律 対 現行": fund_ok(b0, u), "A 対 現行": fund_ok(b0, a), "B 対 現行": fund_ok(b0, b), "A 対 一律": fund_ok(u, a), "B 対 一律": fund_ok(u, b), "A が一律より悪い": (a.s10 < u.s10 - 1.0 or a.p10 < u.p10 - 1.0 or a.w2s5 < u.w2s5 - 1.0), "B が一律より悪い": (b.s10 < u.s10 - 1.0 or b.p10 < u.p10 - 1.0 or b.w2s5 < u.w2s5 - 1.0)}
    for k, v in res.items(): cnt[("本口座後", k)] = cnt.get(("本口座後", k), 0) + int(bool(v))
    print(f"  {nm}: 存続 {b0.s10} / {u.s10} / {a.s10} / {b.s10}・出金 {b0.p10} / {u.p10} / {a.p10} / {b.p10}・2016〜21 年の存続 {b0.w2s5} / {u.w2s5} / {a.w2s5} / {b.w2s5}(現行 / 一律 / A / B) {res}")
print("\n== (B) 評価中(到達 % / 失格 %。W1 = 2021-08〜・W2 = 2016-11〜2021-07) =="); print(DB[["acct", "stage", "variant", "mode", "mon", "guard_lo", "reach_W1", "fail_W1", "weeks_W1", "reach_W2", "fail_W2", "weeks_W2"]].to_string(index=False))
def worse(u, v): return any(v[f"reach_{w}"] < u[f"reach_{w}"] - 1.0 or v[f"fail_{w}"] > u[f"fail_{w}"] + 1.0 for w in ("W1", "W2"))
for (nm, stage), x in DB.groupby(["acct", "stage"], sort=False):
    b0, u, a, b = (x[x.variant == k].iloc[0] for k in ("現行", "一律", "A", "B")); res = {"一律 対 現行": ev_ok(b0, u), "A 対 現行": ev_ok(b0, a), "B 対 現行": ev_ok(b0, b), "A 対 一律": ev_ok(u, a), "B 対 一律": ev_ok(u, b), "A が一律より悪い": worse(u, a), "B が一律より悪い": worse(u, b)}
    for k, v in res.items(): cnt[("評価中", k)] = cnt.get(("評価中", k), 0) + int(bool(v))
    print(f"  {nm} {stage}: {res}")
print("\n== 場面の数(本口座後 7・評価中 15) =="); print(pd.Series(cnt).unstack(0).to_string())
