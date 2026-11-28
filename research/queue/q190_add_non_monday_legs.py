# -*- coding: utf-8 -*-
"""docs/244 Q190(診断・セル 0・2026-11-13 登録「登録して実行」): 月曜以外の検証済みレグを足す — 日次ガード込みの週次モデル。
(a) ルビー・パール・トパーズ: + roll4 ×2.0 / ×4.5。(b) 1-Step: + hold:UK100 0.31 + hold:WTI 0.10 を Mon ×1.0 のまま / Mon ×0.7 で。(c) FTMO 50k 7058: + brk ×2.0。
月曜 = Q188 の H1 経路モデル(SL・全決済ガード・ロック)。月曜以外のレグ(既存の hold:XAUUSD・v4:*・brk を含む)= account_cards.S() の日次系列。
月曜の他レグ損益 oM は合計に加算、ガード指標には min(0, oM) を加算(保守側)。火〜日は日次損益 ≤ −g で −g×1.1・発動 1 回。
週の損益 = 月曜 + 火〜日、週の最高値 = max(月曜の経路最高値, 各日終値の累計)。現行 = 既存レグのみの同モデル(Q187〜Q189 の「現行」= 月曜レグのみ、とは数字が違う)。
使い方: cd research && python3 -W ignore queue/q190_add_non_monday_legs.py   出力: results/q190_add_non_monday_legs.csv・_pick.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
src = open(os.path.join(HERE, "q188_skew_gate_guard_model.py"), encoding="utf-8").read().split('if __name__ == "__main__":')[0]
ns = {"__name__": "q188_head", "__file__": os.path.join(HERE, "q188_skew_gate_guard_model.py")}; exec(compile(src, "q188_head", "exec"), ns)
cfg, EA_LEGS, acc_id, IDXMAP, paths, run_guard, guards, scenes, mc, verdict = (ns[k] for k in ("cfg", "EA_LEGS", "acc_id", "IDXMAP", "paths", "run_guard", "guards", "scenes", "mc", "verdict"))
S = ns["ns"]["ns"]["ns"]["S"]                                   # q187 → q186 → q162 の名前空間にある account_cards.S
VARIANTS = {"6104736": [("+ ロール ×2.0", {"roll4": 2.0}, 1.0), ("+ ロール ×4.5", {"roll4": 4.5}, 1.0)], "6071612": [("+ ロール ×2.0", {"roll4": 2.0}, 1.0), ("+ ロール ×4.5", {"roll4": 4.5}, 1.0)],
            "6104739": [("+ ロール ×2.0", {"roll4": 2.0}, 1.0), ("+ ロール ×4.5", {"roll4": 4.5}, 1.0)],
            "531466484": [("+ Hold UK100 0.31 / WTI 0.10(Mon ×1.0)", {"hold:UK100": 0.31, "hold:WTI": 0.10}, 1.0), ("+ Hold UK100 0.31 / WTI 0.10(Mon ×0.7)", {"hold:UK100": 0.31, "hold:WTI": 0.10}, 0.7)],
            "531407058": [("+ GER40 ブレイク ×2.0", {"brk": 2.0}, 1.0)]}
def is_mon(k): return k.startswith("mon:") or k in IDXMAP
def other_series(legs, sw):
    s = None
    for k, w in legs.items():
        if is_mon(k) or w == 0: continue
        x = S(k) * w; s = x if s is None else s.add(x, fill_value=0)
    xau = legs.get("hold:XAUUSD", 0.0)
    if s is not None and sw and xau: s = s + xau * sw / 1e4 / 21.0
    return s
def weekly(a, legs, mon_scale):
    aid = acc_id(a["name"]); rule = a.get("rule"); g = guards(aid, rule)[1]; sc = 0.8 if aid == "531343523" else 1.0
    items = [(k[4:], False, w * sc * mon_scale) for k, w in legs.items() if k.startswith("mon:")] + [(IDXMAP[k], True, w * mon_scale) for k, w in legs.items() if k in IDXMAP]
    cap = (0.024, "A") if rule == "fn_instant" else ((0.025, "B") if rule == "ftmo1step" else None)
    P = paths(items, cap); o = other_series(legs, a.get("swap_xau_bps_m", 0.0)); rest = []
    for p in P:
        d = p["d"]; days = [float(o.get(d + pd.Timedelta(days=j), 0.0)) if o is not None else 0.0 for j in range(7)]; days = [0.0 if np.isnan(x) else x for x in days]
        oM = days[0]
        for tag in ("lo", "cl"): p["tot"][tag] = p["tot"][tag] + oM; p["met"][tag] = p["met"][tag] + min(0.0, oM)
        p["fin"] += oM; rest.append(days[1:])
    R = run_guard(P, g); out = {}
    for tag in ("lo", "cl"):
        pnl, fired, peak, _ = R[tag]; wp, wf, wk = [], [], []
        for i, days in enumerate(rest):
            c = pnl[i]; f = int(fired[i]); pk = max(peak[i], c)
            for x in days:
                if x <= -g: x = -g * 1.1; f += 1
                c += x; pk = max(pk, c)
            wp.append(c); wf.append(f); wk.append(pk)
        out[tag] = (np.array(wp), np.array(wf), np.array(wk))
    return out, g, (float(o[(o.index >= ns["P0"]) & (o.index <= ns["P1"])].mean()) * 5 if o is not None else 0.0)
rows = []
for a in cfg["accounts"]:
    aid = acc_id(a["name"]); legs0 = dict(EA_LEGS[aid]["eval"])
    if aid not in VARIANTS: continue
    for lab, add, ms in [("現行", {}, 1.0)] + VARIANTS[aid]:
        legs = dict(legs0)
        for k, w in add.items(): legs[k] = legs.get(k, 0.0) + w
        R, g, other_week = weekly(a, legs, ms); mdd = float(a["mdd"])
        base = dict(acct=a["name"][:20], variant=lab, guard_pct=round(g * 100, 1), other_legs_bps_week=round(other_week * 1e4, 1))
        for tag in ("lo", "cl"): base[f"mean_bps_{tag}"] = round(float(R[tag][0].mean()) * 1e4, 1); base[f"hits_{tag}"] = int(R[tag][1].sum()); base[f"worst_week_pct_{tag}"] = round(float(R[tag][0].min()) * 100, 2)
        for nm, start, target in scenes(a, aid):
            r = dict(base, scen=nm, start_pct=round(start * 100, 2), target_pct=round(target * 100, 1))
            for tag in ("lo", "cl"):
                rng = np.random.default_rng(187); reach, fail, med, r8 = mc(R[tag][0], np.minimum(R[tag][1], 2), R[tag][2], start, target, -mdd, rng); r.update({f"reach_{tag}": reach, f"fail_{tag}": fail, f"weeks_{tag}": med, f"reach8w_{tag}": r8})
            rows.append(r)
D = pd.DataFrame(rows); D.to_csv("results/q190_add_non_monday_legs.csv", index=False); picks = []
for (acct, sc), g_ in D.groupby(["acct", "scen"], sort=False):
    cur, best = verdict(g_, "現行")
    picks.append(dict(acct=acct, scen=sc, cur_reach_lo=cur.reach_lo, cur_reach_cl=cur.reach_cl, cur_fail_lo=cur.fail_lo, cur_weeks=cur.weeks_lo, verdict=("変更候補" if best is not None else "現行維持"), variant=(best.variant if best is not None else "現行"),
                      reach_lo=(best.reach_lo if best is not None else None), reach_cl=(best.reach_cl if best is not None else None), fail_lo=(best.fail_lo if best is not None else None), weeks=(best.weeks_lo if best is not None else None)))
Pk = pd.DataFrame(picks); Pk.to_csv("results/q190_add_non_monday_legs_pick.csv", index=False)
pd.set_option("display.width", 320); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 300)
print(Pk.to_string(index=False)); print()
print(D[["acct", "scen", "variant", "other_legs_bps_week", "mean_bps_lo", "hits_lo", "worst_week_pct_lo", "mean_bps_cl", "hits_cl", "reach_lo", "reach_cl", "fail_lo", "fail_cl", "weeks_lo", "reach8w_lo"]].to_string(index=False))
