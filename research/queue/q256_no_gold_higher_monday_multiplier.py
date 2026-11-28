# -*- coding: utf-8 -*-
"""docs/244 Q256(2026-11-17 登録「登録して実行」・セル +15): 金を外して月曜の倍率を上げた形を、金ありの現状と比べる。
対象 = 金の保有がある評価中の 3 口座(1-Step いま・宝くじ いま / 次・FN 14074882 いま / 次)。口座モデル・開始週・開始残高は Q253(docs/493)と同じ。
型: 現状(金あり・いまの建玉から始め、建て直しは設計どおり)を 2 つの金の場面で(実績のまま / 横ばい = Q254 と同じ作り方)。
    金なし × 月曜の倍率 s 倍(s = 1.0・1.125・1.25・1.5。1.0 は Q253 で計測済み・セル外)。1-Step は SL リスク合計上限(2.5%)込み。宝くじは決済 E1。
判定 = Q233 の ev_ok(両期間で到達 −1pt 以内・失格 +1pt 以内、かつどちらかで到達 +2pt 以上か失格 −2pt 以下)。基準 = 現状(金あり)を金の場面ごとに。
参考として「金なし・1.0 倍」に対する同じ判定も出す(倍率を上げること自体の是非)。
使い方: cd research && python3 -W ignore queue/q256_no_gold_higher_monday_multiplier.py   出力: results/q256_no_gold_higher_mult.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(HERE, "q253_gold_hold_carry_vs_daily_guard.py"), encoding="utf-8").read().split("# ---------- 口座 ----------")[0]; n5 = {"__name__": "q253_head", "__file__": os.path.join(HERE, "q253_gold_hold_carry_vs_daily_guard.py")}; exec(compile(_src, "q253_head", "exec"), n5)
np, pd = n5["np"], n5["pd"]; norm_items, account_items, acct, make_fac, MODE, PM, LV, TOP, MONS, W, mon_levels, run, gold_arrays, GA = (n5[k] for k in ("norm_items", "account_items", "acct", "make_fac", "MODE", "PM", "LV", "TOP", "MONS", "W", "mon_levels", "run", "gold_arrays", "GA"))
DG0 = n5["DG"].copy(); P0, P1 = n5["P0"], n5["P1"]
def scenario(drift):                                                            # Q254 と同じ
    if drift is None: return DG0.copy()
    D = DG0.copy(); lr = np.log(D["close"]).diff().fillna(0.0); adj = lr.copy()
    for a, b in ((P0 - pd.Timedelta(days=30), PM - pd.Timedelta(days=1)), (PM, P1 + pd.Timedelta(days=7))):
        m = (D.index >= a) & (D.index <= b); adj[m] = lr[m] - lr[m].mean() + drift / 252.0
    c = float(D["close"].iloc[0]) * np.exp(adj.cumsum()); ratio = c / D["close"]; D["close"] = c; D["low"] = DG0["low"] * ratio; D["open"] = DG0["open"] * ratio; D["high"] = DG0["high"] * ratio
    return D
B = [("1-Step", "531466484", "いま", None, True, False, None, True, 100225.64 / 1e5 - 1, 0.10, 0.01, "acct", None, 0.36, 0.36, 0.0, -52.0),
     ("宝くじ", "531343523", "いま", 8.0, True, False, 0.5, False, 94106.87 / 1e5 - 1, 0.10, 0.005, None, "E1", 0.9, 0.29, -(2102.1 + 235.14) / 1e5, -52.0), ("宝くじ", "531343523", "次", 8.0, True, True, 0.5, False, 0.0, 0.05, 0.005, None, "E1", 0.9, 0.9, 0.0, -52.0),
     ("FN 14074882", "14074882", "いま", 4.0, True, False, None, False, 92322.27 / 1e5 - 1, 0.08, 0.003, None, None, 0.4, 0.39, -(474.1 + 150.06) / 1e5, -76.0), ("FN 14074882", "14074882", "次", 4.0, True, False, None, False, 0.0, 0.05, 0.003, None, None, 0.4, 0.4, 0.0, -76.0)]
SS = (1.0, 1.125, 1.25, 1.5); okA = ~np.isnan(GA["A"][2]); idx = np.arange(W); STARTS = {"W1": [s for s in idx if MONS[s] >= PM and s + 52 <= W and okA[s]], "W2": [s for s in idx if MONS[s] < PM and s + 52 <= W and MONS[s + 51] < PM and okA[s]]}
def pack(o):
    return dict(reach=round(min(o[t]["reach"] for t in o), 1), fail=round(max(o[t]["fail"] for t in o), 1), weeks=max(o[t]["weeks"] for t in o), fires=round(max(o[t]["fires_per52"] for t in o), 2))
rows = []
for nm, key, stage, mm, skew, tilt, smin, trail, start, target, pad0, capm, mode, wgd, wgn, cr0, swm in B:
    items, cap, g = norm_items(key); cap = cap if capm == "acct" else None
    if mm is None: _, it0, _, _ = account_items(acct(key)); mm = sum(w for s, i, w in it0 if not i)
    fac = make_fac(items, skew, 0.5 if tilt else None); levels = list(range(len(LV))) if smin is not None else [TOP]; MLs = {}
    for s in SS:
        MODE["k"] = mode; ML = mon_levels(items, cap, fac, mm * s, levels); MODE["k"] = None; MLs[s] = {li: ML[li if li in ML else TOP] for li in range(len(LV))}
    kw0 = dict(start=start, target=target, mdd=0.10, pad=pad0, smin=smin, trail=trail, g=g, swm=swm, integ=True)
    for sn, dr in (("金あり・実績のまま", None), ("金あり・横ばい", 0.0)):
        n5["DG"] = scenario(dr); GA["A"] = gold_arrays("A"); r = dict(acct=nm, stage=stage, variant=f"現状({sn})", mon_mult=round(mm, 2), cells=0)
        for wn in ("W1", "W2"): r.update({f"{k}_{wn}": v for k, v in pack(run(MLs[1.0], STARTS[wn], "A", wg0=wgn, carry0=cr0, wg_re=wgd, **kw0)).items()})
        rows.append(r)
    n5["DG"] = scenario(None); GA["A"] = gold_arrays("A")
    for s in SS:
        r = dict(acct=nm, stage=stage, variant=f"金なし・月曜 {s:g} 倍", mon_mult=round(mm * s, 2), cells=int(s > 1.0))
        for wn in ("W1", "W2"): r.update({f"{k}_{wn}": v for k, v in pack(run(MLs[s], STARTS[wn], "A", wg0=0.0, carry0=0.0, wg_re=0.0, **kw0)).items()})
        rows.append(r)
    print("done", nm, stage, flush=True)
pd.set_option("display.width", 320); pd.set_option("display.max_rows", 400); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 60)
D = pd.DataFrame(rows); D.to_csv("results/q256_no_gold_higher_mult.csv", index=False); print(D.to_string(index=False))
def ev_ok(b, v): return bool(all(v[f"reach_{w}"] >= b[f"reach_{w}"] - 1.0 and v[f"fail_{w}"] <= b[f"fail_{w}"] + 1.0 for w in ("W1", "W2")) and any(v[f"reach_{w}"] >= b[f"reach_{w}"] + 2.0 or v[f"fail_{w}"] <= b[f"fail_{w}"] - 2.0 for w in ("W1", "W2")))
print("\n== 判定(○ = 変更候補)。基準: 現状(金あり・実績のまま)/ 現状(金あり・横ばい)/ 金なし・1 倍 ==")
for (nm, stage), x in D.groupby(["acct", "stage"], sort=False):
    b1 = x[x.variant == "現状(金あり・実績のまま)"].iloc[0]; b2 = x[x.variant == "現状(金あり・横ばい)"].iloc[0]; b3 = x[x.variant == "金なし・月曜 1 倍"].iloc[0]
    for _, v in x[x.variant.str.startswith("金なし")].iterrows(): print(f"  {nm} {stage}: {v.variant}({v.mon_mult} 倍)到達 {v.reach_W1:.0f} / {v.reach_W2:.0f}%・失格 {v.fail_W1:.0f} / {v.fail_W2:.0f}%・{v.weeks_W1} / {v.weeks_W2} 週 → 対 実績 {'○' if ev_ok(b1, v) else '×'}・対 横ばい {'○' if ev_ok(b2, v) else '×'}・対 金なし 1 倍 {'—' if v.cells == 0 else ('○' if ev_ok(b3, v) else '×')}")
