# -*- coding: utf-8 -*-
"""docs/244 Q191(診断・セル 0・2026-11-13 登録「登録して実行」): 含み損の日は追加で建てない。
月曜の各ショットの建て時刻に、当日のガード指標(確定 + 含み・直前の H1 終値・それまでに建てた分のみ)が −θ×g 以下なら、そのショットを見送る。
θ ∈ {0.25, 0.5, 0.75}。既存の建玉は触らない・ショットごとに再判定。口座モデルは Q187〜Q189 と同じ(月曜レグのみ)。
使い方: cd research && python3 -W ignore queue/q191_skip_shots_when_losing.py   出力: results/q191_skip_shots_when_losing.csv・_pick.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
src = open(os.path.join(HERE, "q188_skew_gate_guard_model.py"), encoding="utf-8").read().split('if __name__ == "__main__":')[0]
ns = {"__name__": "q188_head", "__file__": os.path.join(HERE, "q188_skew_gate_guard_model.py")}; exec(compile(src, "q188_head", "exec"), ns)
cfg, table, us_dst, G, K, P0, P1, run_guard, evaluate, account_items, verdict = (ns[k] for k in ("cfg", "table", "us_dst", "G", "K", "P0", "P1", "run_guard", "evaluate", "account_items", "verdict"))
def paths_skip(items, cap, thr):
    """Q188 の paths と同じ経路を、ショットを時刻順に積みながら作る。thr(> 0)を渡すと、建て時刻の直前の終値ベース指標が −thr 以下のショットを見送る。"""
    parts = []
    for s, idx, w in items:
        M, res = table(s, idx); R = res[K]; p = M.copy(); p["w"] = w / p.nshots; p["risk_w"] = p.w * R["risk"]; p["stop"] = R["stop"]; p["i"] = np.arange(len(p)); p["sym"] = s; p["idx"] = idx; parts.append(p)
    S = pd.concat(parts); S = S[(S.date >= P0) & (S.date <= P1)].sort_values(["date", "t"]).reset_index(drop=True); f = np.ones(len(S))
    if cap:
        C, V = cap
        for d, g in S.groupby("date"):
            used = []
            for i in g.index:
                r = S.risk_w[i]; room = C - sum(x for st, x in used if V == "B" or st > S.off[i]); fi = 1.0 if r <= room else (room / r if room >= 0.1 * r else 0.0); f[i] = fi; used.append((S.stop[i], r * fi))
    S["wf"] = S.w * f; out = []; n_skip = 0; n_all = 0
    for d, g in S.groupby("date"):
        gb = (21 if us_dst(d) else 22) - 4; tot = {"lo": np.zeros(G), "cl": np.zeros(G)}; met = {"lo": np.zeros(G), "cl": np.zeros(G)}
        for sym, idx, i, wf, off, st in zip(g.sym.values, g.idx.values, g.i.values, g.wf.values, g.off.values, g.stop.values):
            if wf == 0: continue
            n_all += 1; off = int(off)
            if thr is not None and off > 0 and met["cl"][off - 1] <= -thr: n_skip += 1; continue
            R = table(sym, bool(idx))[1][K]; close = int(min(st, off + 24))
            for tag, arr in (("lo", R["worst"][i]), ("cl", R["mark"][i])):
                a = arr * wf; tot[tag] += a; b = a.copy()
                if close < gb: b[gb:] = 0.0
                met[tag] += b
        out.append(dict(d=d, gb=gb, tot=tot, met=met, fin=float(tot["cl"][-1])))
    return out, n_skip, n_all
if __name__ == "__main__":
    rows = []
    for a in cfg["accounts"]:
        aid, items, cap, g = account_items(a)
        if not items: continue
        P, _, n_all = paths_skip(items, cap, None); rows += evaluate(a, aid, run_guard(P, g), "現行", dict(guard_pct=round(g * 100, 1), skipped_share=0.0))
        for th in (0.25, 0.5, 0.75):
            Pt, ns_, na = paths_skip(items, cap, th * g); rows += evaluate(a, aid, run_guard(Pt, g), f"θ={th}", dict(guard_pct=round(g * 100, 1), skip_at_pct=round(th * g * 100, 2), skipped_share=round(ns_ / na, 3)))
    D = pd.DataFrame(rows); D.to_csv("results/q191_skip_shots_when_losing.csv", index=False); picks = []
    for (acct, sc), g_ in D[D.scen != "—"].groupby(["acct", "scen"], sort=False):
        cur, best = verdict(g_, "現行")
        picks.append(dict(acct=acct, scen=sc, cur_reach_lo=cur.reach_lo, cur_reach_cl=cur.reach_cl, cur_fail_lo=cur.fail_lo, cur_weeks=cur.weeks_lo, verdict=("変更候補" if best is not None else "現行維持"), variant=(best.variant if best is not None else "現行"),
                          reach_lo=(best.reach_lo if best is not None else None), reach_cl=(best.reach_cl if best is not None else None), fail_lo=(best.fail_lo if best is not None else None), weeks=(best.weeks_lo if best is not None else None)))
    Pk = pd.DataFrame(picks); Pk.to_csv("results/q191_skip_shots_when_losing_pick.csv", index=False)
    pd.set_option("display.width", 300); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 300)
    print(Pk.to_string(index=False)); print()
    cols = ["acct", "scen", "variant", "skipped_share", "mean_bps_lo", "hits_lo", "mean_bps_cl", "hits_cl", "reach_lo", "reach_cl", "fail_lo", "fail_cl", "weeks_lo"]
    print(D[[c for c in cols if c in D.columns]].to_string(index=False))
