# -*- coding: utf-8 -*-
"""docs/244 Q187(診断・セル 0・2026-11-13 登録「登録して実行してください」): 日次ガード込みの倍率の見直し(口座別)。
月曜レグの倍率を現行の m 倍にしたとき、EA の全決済ガード込みで月曜 1 回の平均・ガード発動回数・段階の到達率がどう変わるか。
経路は Q186(H1・SL 3.0×ATR・2021-08〜2026-07)。ガード = 当日の確定損益 + 含み損益 ≤ −g(サーバー日付の変わり目 夏 21・冬 22 UTC で確定分をリセット)、
発動時は全決済(当日損益 −g×1.1)・当日の新規見送り。判定は安値(保守)と終値(楽観)。月内 2 回発動で月末まで新規停止(4 週ブロックで近似)。
実行後の追加(登録外): 目標到達時の自動決済(利益ロック)を経路上で判定する。週の途中で「それまでの累計 + 経路の最高値(終値ベース・ガード発動より前)」が目標に届けば到達とする。
登録どおりの週末判定だけの値は *_nolock 列に残す。理由: 目標が近い口座では高倍率ほど週の途中で届きやすく、週末判定だけでは高倍率に不利な偏りが出る(docs/428 §2)。
使い方: cd research && python3 -W ignore queue/q187_guard_aware_multiplier.py   出力: results/q187_guard_aware_multiplier.csv・_pick.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
src = open(os.path.join(HERE, "q186_mon_sl_width.py"), encoding="utf-8").read().split("# ---------- (A)")[0]
ns = {"__name__": "q186_head", "__file__": os.path.join(HERE, "q186_mon_sl_width.py")}; sys.argv = sys.argv[:1]; exec(compile(src, "q186_head", "exec"), ns)
cfg, EA_LEGS, acc_id, table, us_dst, G, IDXMAP, P0, P1 = (ns[k] for k in ("cfg", "EA_LEGS", "acc_id", "table", "us_dst", "G", "IDXMAP", "P0", "P1"))
K = 3.0; MS = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.25, 1.5]; N = 20000; WEEKS = 52
INIT = {"521100397": 50000, "531407058": 50000, "531343523": 1e5, "531466484": 1e5, "14074882": 1e5, "6071612": 5e6, "6104736": 1e7, "6104739": 35e6}
BAL = {"521100397": 54834.85, "531407058": 53683.04, "531343523": 97353.71, "531466484": 102722.34, "14074882": 93966.16, "6071612": 5291106, "6104736": 10348782, "6104739": 37535714}
def guards(aid, rule):
    if aid in ("6071612", "6104736", "6104739"): return [0.028], 0.028
    if rule == "ftmo1step": return [0.020, 0.024], 0.024
    if rule == "fn_instant": return [0.04], 0.04
    return [0.03, 0.035, 0.04, 0.045], 0.04
def monday_paths(items, m, cap):
    """月曜ごとに: 合計経路 tot[G](確定は r で固定)・ガード指標 met[G](日付が変わると前日の確定分を除く)を安値版 / 終値版で返す。"""
    parts = []
    for s, idx, w in items:
        M, res = table(s, idx); R = res[K]; p = M.copy(); p["w"] = m * w / p.nshots; p["risk_w"] = p.w * R["risk"]; p["r"] = R["r"]; p["stop"] = R["stop"]; p["i"] = np.arange(len(p)); p["key"] = f"{s}|{idx}"; parts.append(p)
    S = pd.concat(parts); S = S[(S.date >= P0) & (S.date <= P1)].sort_values(["date", "t"]).reset_index(drop=True); f = np.ones(len(S))
    if cap:
        C, V = cap
        for d, g in S.groupby("date"):
            used = []
            for i in g.index:
                room = C - sum(r for st, r in used if V == "B" or st > S.off[i]); r = S.risk_w[i]
                fi = 1.0 if r <= room else (room / r if room >= 0.1 * r else 0.0); f[i] = fi; used.append((S.stop[i], r * fi))
    S["wf"] = S.w * f; out = []
    for d, g in S.groupby("date"):
        gb = (21 if us_dst(d) else 22) - 4; tot = {"lo": np.zeros(G), "cl": np.zeros(G)}; met = {"lo": np.zeros(G), "cl": np.zeros(G)}; ent = []
        for key, gg in g.groupby("key"):
            s, idx = key.split("|"); R = table(s, idx == "True")[1][K]
            for i, wf, off, st in zip(gg.i.values, gg.wf.values, gg.off.values, gg.stop.values):
                if wf == 0: continue
                close = int(min(st, off + 24))
                for tag, arr in (("lo", R["worst"][i]), ("cl", R["mark"][i])):
                    a = arr * wf; tot[tag] += a
                    b = a.copy()
                    if close < gb: b[gb:] = 0.0                      # 月曜のうちに確定 → 火曜のガード指標からは外れる
                    met[tag] += b
                ent.append((int(off), wf))
        out.append((d, tot, met, float(tot["cl"][-1])))
    return out, float((S.wf.sum()) / (S.w.sum()))
def apply_guard(paths, g):
    """ガード g を適用。戻り値: {tag: (pnl[n], fired[n], peak[n])}。peak = ガード発動より前(発動なしなら全経路)の終値ベース最高値。発動時の損益 = それまでに前日確定した分 + (−g×1.1)。発動後の新規は経路に入らない(発動時刻の値で確定)。"""
    res = {}
    for tag in ("lo", "cl"):
        pnl = []; fired = []; peak = []
        for d, tot, met, fin in paths:
            hit = np.where(met[tag] <= -g)[0]
            if len(hit): j = hit[0]; pnl.append(float(tot[tag][j] - met[tag][j]) - g * 1.1); fired.append(1); peak.append(float(tot["cl"][:j].max()) if j > 0 else 0.0)
            else: pnl.append(fin); fired.append(0); peak.append(float(tot["cl"].max()))
        res[tag] = (np.array(pnl), np.array(fired), np.array(peak))
    return res
def mc(pnl, fired, peak, start, target, floor, rng, lock=True):
    idx = rng.integers(0, len(pnl), (N, WEEKS)); x = pnl[idx]; f = fired[idx].reshape(N, WEEKS // 4, 4); cf = np.cumsum(f, axis=2) - f; act = (cf < 2).reshape(N, WEEKS); x = x * act   # 月内 2 回で月末まで停止
    c = start + np.cumsum(x, axis=1); top = c if not lock else np.maximum(c, (c - x) + np.where(act, peak[idx], -1.0)); up = np.where((top >= target).any(axis=1), (top >= target).argmax(axis=1), 10**6); dn = np.where((c <= floor).any(axis=1), (c <= floor).argmax(axis=1), 10**6)
    ok = up < dn; return round(float(ok.mean()) * 100, 1), round(float((dn < up).mean()) * 100, 1), (int(np.median(up[ok]) + 1) if ok.any() else None), round(float((ok & (up < 8)).mean()) * 100, 1)
rows = []
for a in cfg["accounts"]:
    aid = acc_id(a["name"]); legs = EA_LEGS[aid]["eval"]; rule = a.get("rule"); mdd = float(a["mdd"]); tg = a.get("targets") or []
    items = [(k[4:], False, w) for k, w in legs.items() if k.startswith("mon:")] + [(IDXMAP[k], True, w) for k, w in legs.items() if k in IDXMAP]
    if not items: continue
    cap = (0.024, "A") if rule == "fn_instant" else ((0.025, "B") if rule == "ftmo1step" else None); GS, g_now = guards(aid, rule)
    scen = []
    if tg and aid in BAL: scen.append(("(i) 現在地 → いまの段階", BAL[aid] / INIT[aid] - 1, tg[0]))
    if len(tg) > 1: scen.append(("(ii) ゼロ → 次の段階", 0.0, tg[1]))
    for m in MS:
        paths, kept = monday_paths(items, m, cap)
        for g in GS:
            R = apply_guard(paths, g); base = dict(acct=a["name"][:20], m=m, guard_pct=round(g * 100, 1), current=bool(m == 1.0 and abs(g - g_now) < 1e-9), notional_kept=round(kept, 3), mondays=len(paths),
                                                   mean_noguard_bps=round(float(np.mean([p[3] for p in paths])) * 1e4, 1))
            for tag in ("lo", "cl"): base[f"mean_bps_{tag}"] = round(float(R[tag][0].mean()) * 1e4, 1); base[f"hits_{tag}"] = int(R[tag][1].sum()); base[f"worst_pct_{tag}"] = round(float(R[tag][0].min()) * 100, 2)
            if not scen: rows.append(dict(base, scen="—")); continue
            for nm, start, target in scen:
                r = dict(base, scen=nm, start_pct=round(start * 100, 2), target_pct=round(target * 100, 1))
                for tag in ("lo", "cl"):
                    rng = np.random.default_rng(187); reach, fail, med, r8 = mc(R[tag][0], R[tag][1], R[tag][2], start, target, -mdd, rng); r.update({f"reach_{tag}": reach, f"fail_{tag}": fail, f"weeks_{tag}": med, f"reach8w_{tag}": r8})
                    rng = np.random.default_rng(187); a1, a2, a3, a4 = mc(R[tag][0], R[tag][1], R[tag][2], start, target, -mdd, rng, lock=False); r.update({f"reach_{tag}_nolock": a1, f"fail_{tag}_nolock": a2, f"weeks_{tag}_nolock": a3})
                    rng = np.random.default_rng(187); idx1 = rng.integers(0, len(R[tag][0]), N); r[f"reach1w_{tag}"] = round(float(((start + np.maximum(R[tag][0][idx1], R[tag][2][idx1])) >= target).mean()) * 100, 1)
                rows.append(r)
D = pd.DataFrame(rows); D.to_csv("results/q187_guard_aware_multiplier.csv", index=False)
# 事前に決めた推奨の規則
picks = []
for (acct, sc), g in D[D.scen != "—"].groupby(["acct", "scen"], sort=False):
    cur = g[g.current].iloc[0]; c = g[(g.reach_lo >= cur.reach_lo + 2) & (g.reach_cl >= cur.reach_cl + 2) & (g.weeks_lo <= 1.5 * cur.weeks_lo)]
    best = c.sort_values("reach_lo", ascending=False).iloc[0] if len(c) else None
    picks.append(dict(acct=acct, scen=sc, cur_reach_lo=cur.reach_lo, cur_reach_cl=cur.reach_cl, cur_fail_lo=cur.fail_lo, cur_weeks=cur.weeks_lo, cur_hits_lo=cur.hits_lo, cur_mean_lo=cur.mean_bps_lo,
                      verdict=("変更候補" if best is not None else "現行維持"), m=(best.m if best is not None else 1.0), guard_pct=(best.guard_pct if best is not None else cur.guard_pct),
                      reach_lo=(best.reach_lo if best is not None else None), reach_cl=(best.reach_cl if best is not None else None), fail_lo=(best.fail_lo if best is not None else None),
                      weeks=(best.weeks_lo if best is not None else None), hits_lo=(best.hits_lo if best is not None else None), mean_lo=(best.mean_bps_lo if best is not None else None), n_candidates=len(c)))
Pk = pd.DataFrame(picks); Pk.to_csv("results/q187_guard_aware_multiplier_pick.csv", index=False)
pd.set_option("display.width", 300); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 400)
print(Pk.to_string(index=False)); print()
cols = ["acct", "scen", "m", "guard_pct", "notional_kept", "mean_noguard_bps", "mean_bps_lo", "hits_lo", "mean_bps_cl", "hits_cl", "reach_lo", "reach_cl", "fail_lo", "fail_cl", "weeks_lo", "reach8w_lo"]
print(D[[c for c in cols if c in D.columns]].to_string(index=False))
