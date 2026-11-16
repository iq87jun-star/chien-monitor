# -*- coding: utf-8 -*-
"""docs/244 Q254(2026-11-17 登録「登録して実行」・セル +22): 金が横ばい / 下落だったと仮定したときの、金の保有あり・なしの比較(Q253 の続き)。
Q253(docs/493)は金が上がり続けた期間(2016-11〜2021-07 +41%・2021-08〜2026-07 +122%)の実績の値動きを当てはめたため、金を持つ型に有利だった。
ここでは金の日次の値動きから期間ごとの平均の上昇分だけを取り除き(日々の上下・月曜レグとの同時性はそのまま)、年率の傾きを与え直す。
  場面: 実績のまま(Q253 の再現・照合用)/ 横ばい(年率 0%: 期間の始めと終わりが同じ値)/ 下落(年率 −6%: 2012〜2015 年の実績の年率)。
  傾きの取り除きは 2 期間(2016-11-01〜2021-07-31・2021-08-01〜2026-07-31)それぞれの対数収益の平均を引く。安値は終値との比を保つ。
口座モデル・開始週・開始残高・型・判定は Q253 と同じ(開始週をずらした実際の並び・52 週。判定 = Q233 の ev_ok・基準 = その場面の「現状」)。金は日足。
候補(セル): 金なし・建て直しを半分に(5 口座段階)+ 宝くじ いま の「いまの大きさに」= 11 × 2 場面 = 22。金なしの数字は場面によらない。
使い方: cd research && python3 -W ignore queue/q254_gold_hold_flat_and_falling_scenarios.py   出力: results/q254_gold_scenarios.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(HERE, "q253_gold_hold_carry_vs_daily_guard.py"), encoding="utf-8").read().split("# ---------- 口座 ----------")[0]; n5 = {"__name__": "q253_head", "__file__": os.path.join(HERE, "q253_gold_hold_carry_vs_daily_guard.py")}; exec(compile(_src, "q253_head", "exec"), n5)
np, pd = n5["np"], n5["pd"]; norm_items, account_items, acct, make_fac, MODE, PM, LV, TOP, MONS, W, mon_levels, run, gold_arrays, GA = (n5[k] for k in ("norm_items", "account_items", "acct", "make_fac", "MODE", "PM", "LV", "TOP", "MONS", "W", "mon_levels", "run", "gold_arrays", "GA"))
DG0 = n5["DG"].copy(); P0, P1 = n5["P0"], n5["P1"]
def scenario(drift):
    """drift = None: 実績のまま。数値 = 年率の傾き(対数)。期間ごとの平均を引いてから傾きを足す。"""
    if drift is None: return DG0.copy()
    D = DG0.copy(); lr = np.log(D["close"]).diff().fillna(0.0); adj = lr.copy()
    for a, b in ((P0 - pd.Timedelta(days=30), PM - pd.Timedelta(days=1)), (PM, P1 + pd.Timedelta(days=7))):
        m = (D.index >= a) & (D.index <= b); adj[m] = lr[m] - lr[m].mean() + drift / 252.0
    c = float(D["close"].iloc[0]) * np.exp(adj.cumsum()); ratio = c / D["close"]; D["close"] = c; D["low"] = DG0["low"] * ratio; D["open"] = DG0["open"] * ratio; D["high"] = DG0["high"] * ratio
    return D
SC = [("実績のまま(照合)", None), ("横ばい(年率 0%)", 0.0), ("下落(年率 −6%)", float(np.log(1 - 0.06)))]
B = [("1-Step", "531466484", "いま", None, True, False, None, True, 100225.64 / 1e5 - 1, 0.10, 0.01, "acct", None, 0.36, 0.36, 0.0, -52.0),
     ("宝くじ", "531343523", "いま", 8.0, True, False, 0.5, False, 94106.87 / 1e5 - 1, 0.10, 0.005, None, "E1", 0.9, 0.29, -(2102.1 + 235.14) / 1e5, -52.0), ("宝くじ", "531343523", "次", 8.0, True, True, 0.5, False, 0.0, 0.05, 0.005, None, "E1", 0.9, 0.9, 0.0, -52.0),
     ("FN 14074882", "14074882", "いま", 4.0, True, False, None, False, 92322.27 / 1e5 - 1, 0.08, 0.003, None, None, 0.4, 0.39, -(474.1 + 150.06) / 1e5, -76.0), ("FN 14074882", "14074882", "次", 4.0, True, False, None, False, 0.0, 0.05, 0.003, None, None, 0.4, 0.4, 0.0, -76.0)]
okA = ~np.isnan(GA["A"][2]); idx = np.arange(W); STARTS = {"W1": [s for s in idx if MONS[s] >= PM and s + 52 <= W and okA[s]], "W2": [s for s in idx if MONS[s] < PM and s + 52 <= W and MONS[s + 51] < PM and okA[s]]}
MLS = {}
for nm, key, stage, mm, skew, tilt, smin, trail, start, target, pad0, capm, mode, wgd, wgn, cr0, swm in B:
    items, cap, g = norm_items(key); cap = cap if capm == "acct" else None
    if mm is None: _, it0, _, _ = account_items(acct(key)); mm = sum(w for s, i, w in it0 if not i)
    fac = make_fac(items, skew, 0.5 if tilt else None); levels = list(range(len(LV))) if smin is not None else [TOP]
    MODE["k"] = mode; ML = mon_levels(items, cap, fac, mm, levels); MODE["k"] = None; MLS[(nm, stage)] = ({li: ML[li if li in ML else TOP] for li in range(len(LV))}, g)
rows = []
for sn, dr in SC:
    n5["DG"] = scenario(dr); GA["A"] = gold_arrays("A"); c = n5["DG"]["close"]; print(f"[{sn}] 金: 2016-11 {c[:'2016-11-01'].iloc[-1]:.0f} → 2021-07 {c[:'2021-07-31'].iloc[-1]:.0f} → 2026-07 {c[:'2026-07-31'].iloc[-1]:.0f}", flush=True)
    for nm, key, stage, mm, skew, tilt, smin, trail, start, target, pad0, capm, mode, wgd, wgn, cr0, swm in B:
        ML, g = MLS[(nm, stage)]
        V = [("現状(建て直しは設計どおり)", wgn, cr0, wgd, 0), ("金なし", 0.0, 0.0, 0.0, 1), ("建て直しを半分に", wgn, cr0, wgd / 2, 1)] + ([("建て直しをいまの大きさに", wgn, cr0, wgn, 1)] if abs(wgn - wgd) > 0.02 else [])
        for vn, w0, c0, wr, cell in V:
            kw = dict(start=start, target=target, mdd=0.10, pad=pad0, smin=smin, trail=trail, g=g, swm=swm, wg0=w0, carry0=c0, wg_re=wr, integ=True); r = dict(scenario=sn, acct=nm, stage=stage, variant=vn, cells=cell if dr is not None else 0)
            for wn in ("W1", "W2"):
                o = run(ML, STARTS[wn], "A", **kw); r[f"reach_{wn}"] = round(min(o[t]["reach"] for t in o), 1); r[f"fail_{wn}"] = round(max(o[t]["fail"] for t in o), 1); r[f"weeks_{wn}"] = max(o[t]["weeks"] for t in o); r[f"fires_{wn}"] = round(max(o[t]["fires_per52"] for t in o), 2); r[f"gold_only_{wn}"] = round(max(o[t]["gold_only"] for t in o), 2)
            rows.append(r)
    print("done", sn, flush=True)
pd.set_option("display.width", 320); pd.set_option("display.max_rows", 400); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 60)
D = pd.DataFrame(rows); D.to_csv("results/q254_gold_scenarios.csv", index=False); print(D.to_string(index=False))
def ev_ok(b, v): return bool(all(v[f"reach_{w}"] >= b[f"reach_{w}"] - 1.0 and v[f"fail_{w}"] <= b[f"fail_{w}"] + 1.0 for w in ("W1", "W2")) and any(v[f"reach_{w}"] >= b[f"reach_{w}"] + 2.0 or v[f"fail_{w}"] <= b[f"fail_{w}"] - 2.0 for w in ("W1", "W2")))
print("\n== 判定(基準 = その場面の現状) ==")
for (sn, nm, stage), x in D.groupby(["scenario", "acct", "stage"], sort=False):
    b = x[x.variant.str.startswith("現状")].iloc[0]
    for _, v in x[x.variant != b.variant].iterrows(): print(f"  [{sn}] {nm} {stage}: {v.variant} → {'変更候補' if ev_ok(b, v) else '現行どおり'}(到達 {v.reach_W1:.0f} / {v.reach_W2:.0f}% vs {b.reach_W1:.0f} / {b.reach_W2:.0f}%・失格 {v.fail_W1:.0f} / {v.fail_W2:.0f}% vs {b.fail_W1:.0f} / {b.fail_W2:.0f}%)")
