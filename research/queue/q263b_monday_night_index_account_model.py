# -*- coding: utf-8 -*-
"""docs/244 Q263 (D)(診断・セル 0・2026-11-17 登録「未採用のものを登録して実行」): 荒れた週(前金曜 VIX > 25)の月曜の夜の株価指数(NAS100・US500)を足す形を口座モデルで確かめる。
レグ単体は Q237 の A2(配備形 Mon4 1.0 に対して指数 2 本の夜を合計 0.25)で、Sharpe と累積は 3 窓とも上がるが前窓の最悪月が 0.02 ポイント深くなり不成立だった(セルは Q237 で加算済み)。
夜のレグ = VIX > 25 の週だけ、月曜 20 UTC の始値で NAS100・US500 を買い、指数の月曜レグと同じ時刻(火曜 14 UTC 夏 / 15 UTC 冬)に決済。損切り 3.0 × ATR24。大きさ = 円クロスの合計 1.0 に対して各 0.125。
口座モデル・場面・開始残高・乱数・判定は Q233 と同じ(本口座後 7 構成・評価中 15 場面)。決済の型は口座ごとの採用形(Fintokei 3 口座と宝くじの評価中は E1・それ以外は 24h)。
使い方: cd research && python3 -W ignore queue/q263b_monday_night_index_account_model.py   出力: results/q263b_night_index_funded.csv・_eval.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(HERE, "q233_exit_switch_line_vs_vix_account_model.py"), encoding="utf-8").read().split("\n# ---------------- (A) 本口座後")[0]; n3 = {"__name__": "q233_head", "__file__": os.path.join(HERE, "q233_exit_switch_line_vs_vix_account_model.py")}; exec(compile(_src, "q233_head", "exec"), n3)
np, pd, q = n3["np"], n3["pd"], n3["q"]; norm_items, account_items, acct, make_fac, build_full, roll_week, sim_funded, sim_eval, MODE, PM, NP, table_x, hot, paths_fac, K, MON4 = (n3[k] for k in ("norm_items", "account_items", "acct", "make_fac", "build_full", "roll_week", "sim_funded", "sim_eval", "MODE", "PM", "NP", "table_x", "hot", "paths_fac", "K", "MON4"))
us_dst = paths_fac.__globals__["us_dst"]; G = 37; _N = {}
def night_table(sym):
    if sym in _N: return _N[sym]
    df = q.load(sym); atr = q.atr24(df); mondays = pd.DatetimeIndex(sorted(set(df.index[df.index.dayofweek == 0].normalize()))); meta = []; R = dict(risk=[], r=[], stop=[], mark=[], worst=[])
    for d in mondays:
        if not hot(d): continue
        g0 = d + pd.Timedelta(hours=4); grid = pd.date_range(g0, periods=G + 25, freq="h"); sub = df.loc[g0:grid[-1]]
        if len(sub) == 0: continue
        o_ = sub["open"].reindex(grid).values; lo_ = sub["low"].reindex(grid).values; c_ = sub["close"].reindex(grid).values; a = 16; b = (14 if us_dst(d) else 15) - 4 + 24; t = grid[a]
        if np.isnan(o_[a]) or np.isnan(o_[b]) or np.isnan(atr.get(t, np.nan)): continue
        e = float(o_[a]); c = float(q.cost(sym, [e])[0]); lo = lo_[a:b]; cl = pd.Series(c_[a:b]).ffill().fillna(e).values; lw = np.where(np.isnan(lo), cl, lo); sd = K * float(atr[t]); hit = np.where(lw <= e - sd)[0]; j = int(hit[0]) if len(hit) else -1
        r = (-sd / e - c) if j >= 0 else float(o_[b]) / e - 1 - c; m = cl / e - 1 - c; w = lw / e - 1 - c
        if j >= 0: m[j:] = r; w[j:] = r
        mark = np.zeros(G); worst = np.zeros(G); n_in = min(b, G) - a; mark[a:a + n_in] = m[:n_in]; worst[a:a + n_in] = w[:n_in]
        if b < G: mark[b:] = r; worst[b:] = r
        meta.append((d, t, a, 1)); R["risk"].append(sd / e + c); R["r"].append(r); R["stop"].append(a + j if j >= 0 else 10**6); R["mark"].append(mark); R["worst"].append(worst)
    M = pd.DataFrame(meta, columns=["date", "t", "off", "nshots"]); res = {K: dict(risk=np.array(R["risk"]), r=np.array(R["r"]), stop=np.array(R["stop"], dtype=float), mark=np.array(R["mark"]), worst=np.array(R["worst"]))}
    print(f"  [夜のレグ] {sym}: {len(M)} 週・平均 {res[K]['r'].mean() * 1e4:+.1f} bps・勝率 {100 * (res[K]['r'] > 0).mean():.0f}%・損切り {100 * (res[K]['stop'] < 10**5).mean():.0f}%", flush=True); _N[sym] = (M, res); return _N[sym]
paths_fac.__globals__["table"] = lambda sym, idx: night_table(sym[:-2]) if sym.endswith("@N") else table_x(sym, idx)
NIGHT = [("NAS100@N", True, 0.125), ("US500@N", True, 0.125)]
def fund_ok(b, v): return bool((v.s10 >= b.s10 + 3.0 and v.p10 >= b.p10) or (v.p10 >= b.p10 + 3.0 and v.s10 >= b.s10 - 1.0 and v.w2s5 >= b.w2s5 - 1.0))
def ev_ok(b, v): return bool(all(v[f"reach_{w}"] >= b[f"reach_{w}"] - 1.0 and v[f"fail_{w}"] <= b[f"fail_{w}"] + 1.0 for w in ("W1", "W2")) and any(v[f"reach_{w}"] >= b[f"reach_{w}"] + 2.0 or v[f"fail_{w}"] <= b[f"fail_{w}"] - 2.0 for w in ("W1", "W2")))
# ---------------- (A) 本口座後(Q233 と同じ 7 構成・最後の列 = 採用の決済の型) ----------------
A = [("FTMO 50k ×2", "521100397", None, None, False, False, 0.5, 0.01, 3.75, 0.0, None), ("宝くじ", "531343523", None, None, True, False, 0.5, 0.005, 4.0, 0.0, None), ("トパーズ", "6104739", None, None, True, False, 0.5, 0.01, 3.0, 4.5, "E1"),
     ("ルビー / パール", "6104736", None, None, False, False, 0.5, 0.01, 2.78, 4.5, "E1"), ("1-Step", "531466484", None, "acct", True, True, None, 0.01, 2.43, 0.0, None),
     ("FN 14074882", "14074882", None, (0.024, "A"), True, False, 0.5, 0.01, 4.0, 0.0, None), ("FN 14166201", "14166201", MON4, (0.024, "A"), False, False, 0.5, 0.01, 3.0, 4.5, None)]
rows = []
for nm, key, itov, capov, skew, trail, lo, pad, mm, rw, mode in A:
    if itov is None: items, cap, g = norm_items(key)
    else: items, cap, g = itov, None, 0.04
    cap = cap if capov == "acct" else capov; fac = make_fac(items, skew, lo)
    for vn, its in (("現行", items), ("+ 荒れた週の月曜の夜の指数", list(items) + NIGHT)):
        MODE["k"] = mode; T, dates = build_full(its, cap, g, fac, mm); MODE["k"] = None; call = np.arange(len(dates)); c2 = call[np.array([d < PM for d in dates])]; add = roll_week(dates, rw, g) if rw else np.zeros(len(dates)); r = dict(acct=nm, variant=vn, mode=mode or "24h", mon=mm, guard_lo=round(float((T["lo"][1][-1] > 0).mean()) * 100, 2), wk_mean=round(float(T["cl"][0][-1].mean()) * 100, 3))
        for tag in ("lo", "cl"):
            m = sim_funded(T[tag], add, call, 0.10, pad, trail, 520, NP); m2 = sim_funded(T[tag], add, c2, 0.10, pad, trail, 260, 10000); r.update({f"s10_{tag}": m[520][0], f"p10_{tag}": m[520][1], f"s5_{tag}": m[260][0], f"w2s5_{tag}": m2[260][0]})
        for k in ("s10", "p10", "s5", "w2s5"): r[k] = round(min(r[f"{k}_lo"], r[f"{k}_cl"]), 1)
        rows.append(r)
    print("A done", nm, flush=True)
DA = pd.DataFrame(rows); DA.to_csv("results/q263b_night_index_funded.csv", index=False)
# ---------------- (B) 評価中(Q233 と同じ 15 場面) ----------------
B = [("FTMO 0397", "521100397", "いま", 6.0, False, False, None, False, 54835 / 5e4 - 1, 0.10, 0.01, None, None), ("FTMO 7058", "531407058", "いま", 6.0, False, False, None, False, 53683 / 5e4 - 1, 0.10, 0.01, None, None),
     ("FTMO 50k", "521100397", "次", 6.0, False, True, 0.5, False, 0.0, 0.05, 0.01, None, None),
     ("宝くじ", "531343523", "いま", 8.0, True, False, 0.5, False, 97354 / 1e5 - 1, 0.10, 0.005, None, "E1"), ("宝くじ", "531343523", "次", 8.0, True, True, 0.5, False, 0.0, 0.05, 0.005, None, "E1"),
     ("1-Step", "531466484", "いま", None, True, False, None, True, 102722 / 1e5 - 1, 0.10, 0.01, "acct", None),
     ("トパーズ", "6104739", "いま", 8.0, False, False, None, False, 37535714 / 35e6 - 1, 0.08, 0.01, None, "E1"), ("トパーズ", "6104739", "次(6 倍)", 6.0, True, True, 0.5, False, 0.0, 0.06, 0.01, None, "E1"),
     ("ルビー", "6104736", "いま", 8.35, False, True, 0.5, False, 10348782 / 1e7 - 1, 0.08, 0.01, None, "E1"), ("ルビー", "6104736", "次(8.35 倍)", 8.35, False, True, 0.5, False, 0.0, 0.06, 0.01, None, "E1"), ("ルビー", "6104736", "次(6.3 倍)", 6.3, False, True, 0.5, False, 0.0, 0.06, 0.01, None, "E1"),
     ("パール", "6071612", "いま", 5.57, False, False, None, False, 5291106 / 5e6 - 1, 0.08, 0.01, None, "E1"), ("パール", "6071612", "次", 5.57, False, True, 0.5, False, 0.0, 0.06, 0.01, None, "E1"),
     ("FN 14074882", "14074882", "いま", 4.0, True, False, None, False, 93966 / 1e5 - 1, 0.08, 0.003, None, None), ("FN 14074882", "14074882", "次", 4.0, True, False, None, False, 0.0, 0.05, 0.003, None, None)]
rowsB = []
for nm, key, stage, mm, skew, tilt, smin, trail, start, target, pad0, capm, mode in B:
    items, cap, g = norm_items(key); cap = cap if capm == "acct" else None
    if mm is None: _, it0, _, _ = account_items(acct(key)); mm = sum(w for s, i, w in it0 if not i)
    fac = make_fac(items, skew, 0.5 if tilt else None)
    for vn, its in (("現行", items), ("+ 荒れた週の月曜の夜の指数", list(items) + NIGHT)):
        MODE["k"] = mode; T, dates = build_full(its, cap, g, fac, mm); MODE["k"] = None; r = dict(acct=nm, stage=stage, variant=vn, mode=mode or "24h", mon=round(mm, 2), guard_lo=round(float((T["lo"][1][-1] > 0).mean()) * 100, 2))
        for wn, sel in (("W1", np.array([d >= PM for d in dates])), ("W2", np.array([d < PM for d in dates]))):
            cols = np.arange(len(dates))[sel]; rr = [sim_eval(T[tag], cols, start, target, 0.10, pad0, smin, trail) for tag in ("lo", "cl")]; r[f"reach_{wn}"] = round(min(x[0] for x in rr), 1); r[f"fail_{wn}"] = round(max(x[1] for x in rr), 1); r[f"weeks_{wn}"] = max((x[2] or 0) for x in rr)
        rowsB.append(r)
    print("B done", nm, stage, flush=True)
DB = pd.DataFrame(rowsB); DB.to_csv("results/q263b_night_index_eval.csv", index=False)
pd.set_option("display.width", 320); pd.set_option("display.max_rows", 200); pd.set_option("display.max_colwidth", 40)
print("\n== (A) 本口座後(10 年存続 % / 10 年の累計出金 % / 5 年存続 / 2016〜21 年の 5 年存続。安値・終値の悪い方) =="); print(DA[["acct", "variant", "mode", "mon", "guard_lo", "wk_mean", "s10", "p10", "s5", "w2s5"]].to_string(index=False))
for nm, x in DA.groupby("acct", sort=False): b, v = x.iloc[0], x.iloc[1]; print(f"  {nm}: {'変更候補' if fund_ok(b, v) else '現行どおり'}(存続 {b.s10} → {v.s10}・出金 {b.p10} → {v.p10})")
print("\n== (B) 評価中(到達 % / 失格 % / 中央の週数。W1 = 2021-08〜・W2 = 2016-11〜2021-07) =="); print(DB[["acct", "stage", "variant", "mode", "mon", "guard_lo", "reach_W1", "fail_W1", "weeks_W1", "reach_W2", "fail_W2", "weeks_W2"]].to_string(index=False))
for (nm, stage), x in DB.groupby(["acct", "stage"], sort=False): b, v = x.iloc[0], x.iloc[1]; print(f"  {nm} {stage}: {'変更候補' if ev_ok(b, v) else '現行どおり'}(到達 {b.reach_W1} / {b.reach_W2} → {v.reach_W1} / {v.reach_W2}・失格 {b.fail_W1} / {b.fail_W2} → {v.fail_W1} / {v.fail_W2})")
