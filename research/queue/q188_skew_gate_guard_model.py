# -*- coding: utf-8 -*-
"""docs/244 Q188(診断・セル 0・2026-11-13 登録「登録して実行」): SKEW の見送り(Q173 / Q174 で改良系を通過)を、日次ガード込みの口座モデル(Q187・docs/428)で再評価。
規則: 前金曜(月曜 − 3 日・無ければ直前)の CBOE SKEW の 252 営業日分位 > 0.8 の月曜は円クロス(mon:*)を見送る。指数の月曜レグは見送らない。参照: half(0.5 倍)。
対象 = 4 通貨型(1-Step・宝くじ・トパーズ・FTMO 50k×2)と 3 通貨型(14074882)。2 通貨型(ルビー・パール・Instant)は Q174 不成立のため参考表示。
共有関数(paths / run_guard / evaluate)は Q189 も使う。
使い方: cd research && python3 -W ignore queue/q188_skew_gate_guard_model.py   出力: results/q188_skew_gate_guard_model.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
src = open(os.path.join(HERE, "q187_guard_aware_multiplier.py"), encoding="utf-8").read().split("rows = []\nfor a in cfg")[0]
ns = {"__name__": "q187_head", "__file__": os.path.join(HERE, "q187_guard_aware_multiplier.py")}; exec(compile(src, "q187_head", "exec"), ns)
cfg, EA_LEGS, acc_id, table, us_dst, G, IDXMAP, P0, P1, K, N, INIT, BAL, guards, mc = (ns[k] for k in ("cfg", "EA_LEGS", "acc_id", "table", "us_dst", "G", "IDXMAP", "P0", "P1", "K", "N", "INIT", "BAL", "guards", "mc"))
VALIDATED = {"531466484": "4 通貨型", "531343523": "4 通貨型", "6104739": "4 通貨型", "521100397": "4 通貨型", "531407058": "4 通貨型", "14074882": "3 通貨型"}
def skew_gate_dates():
    V = pd.read_csv("data_ext/SKEW_History.csv"); V["d"] = pd.to_datetime(V["DATE"]); v = V.set_index("d")["SKEW"].sort_index().astype(float)
    return v.rolling(252).apply(lambda w: (w[:-1] < w[-1]).mean(), raw=True)
def paths(items, cap, fx_factor=None):
    """月曜ごとの経路。fx_factor: {date: 倍率}(円クロスのみに掛ける・指数は不変)。戻り値: [dict(d, gb, tot{lo,cl}, met{lo,cl}, fin)]"""
    parts = []
    for s, idx, w in items:
        M, res = table(s, idx); R = res[K]; p = M.copy(); p["w"] = w / p.nshots
        if fx_factor is not None and not idx: p["w"] = p.w * p.date.map(lambda d: fx_factor.get(d, 1.0)).values
        p["risk_w"] = p.w * R["risk"]; p["r"] = R["r"]; p["stop"] = R["stop"]; p["i"] = np.arange(len(p)); p["key"] = f"{s}|{idx}"; parts.append(p)
    S = pd.concat(parts); S = S[(S.date >= P0) & (S.date <= P1)].sort_values(["date", "t"]).reset_index(drop=True); f = np.ones(len(S))
    if cap:
        C, V = cap
        for d, g in S.groupby("date"):
            used = []
            for i in g.index:
                r = S.risk_w[i]
                if r <= 0: f[i] = 0.0; continue
                room = C - sum(x for st, x in used if V == "B" or st > S.off[i]); fi = 1.0 if r <= room else (room / r if room >= 0.1 * r else 0.0); f[i] = fi; used.append((S.stop[i], r * fi))
    S["wf"] = S.w * f; out = []
    for d, g in S.groupby("date"):
        gb = (21 if us_dst(d) else 22) - 4; tot = {"lo": np.zeros(G), "cl": np.zeros(G)}; met = {"lo": np.zeros(G), "cl": np.zeros(G)}
        for key, gg in g.groupby("key"):
            s, idx = key.split("|"); R = table(s, idx == "True")[1][K]
            for i, wf, off, st in zip(gg.i.values, gg.wf.values, gg.off.values, gg.stop.values):
                if wf == 0: continue
                close = int(min(st, off + 24))
                for tag, arr in (("lo", R["worst"][i]), ("cl", R["mark"][i])):
                    a = arr * wf; tot[tag] += a; b = a.copy()
                    if close < gb: b[gb:] = 0.0
                    met[tag] += b
        out.append(dict(d=d, gb=gb, tot=tot, met=met, fin=float(tot["cl"][-1])))
    return out
def run_guard(P, g, theta=None):
    """ガード g(と、任意で手前 −θg での半減)を適用。戻り値: {tag: (pnl, fired, peak, derisked)}"""
    res = {}
    for tag in ("lo", "cl"):
        pnl, fired, peak, der = [], [], [], []
        for p in P:
            M = p["met"][tag]; T = p["tot"][tag]; Tc = p["tot"]["cl"]; fin = p["fin"]; d1 = 0
            if theta is not None:
                h1 = np.where(M <= -theta * g)[0]
                if len(h1) and M[h1[0]] > -g:                                  # 半減(いきなり −g を割った場合は全決済へ)
                    j1 = int(h1[0]); gb = p["gb"]; idx = np.arange(G); after = idx > j1; d1 = 1
                    M2 = M.copy(); M2[after] = M[j1] + 0.5 * (M[after] - M[j1])
                    if j1 < gb: nxt = after & (idx >= gb); M2[nxt] = 0.5 * M[nxt]
                    T2 = T.copy(); T2[after] = T[j1] + 0.5 * (T[after] - T[j1]); Tc2 = Tc.copy(); Tc2[after] = T[j1] + 0.5 * (Tc[after] - Tc[j1]); fin = float(T[j1] + 0.5 * (fin - T[j1])); M, T, Tc = M2, T2, Tc2
            hit = np.where(M <= -g)[0]
            if len(hit): j = int(hit[0]); pnl.append(float(T[j] - M[j]) - g * 1.1); fired.append(1); peak.append(float(Tc[:j].max()) if j > 0 else 0.0)
            else: pnl.append(fin); fired.append(0); peak.append(float(Tc.max()))
            der.append(d1)
        res[tag] = (np.array(pnl), np.array(fired), np.array(peak), np.array(der))
    return res
def scenes(a, aid):
    tg = a.get("targets") or []; sc = []
    if tg and aid in BAL: sc.append(("(i) 現在地 → いまの段階", BAL[aid] / INIT[aid] - 1, tg[0]))
    if len(tg) > 1: sc.append(("(ii) ゼロ → 次の段階", 0.0, tg[1]))
    return sc
def evaluate(a, aid, R, label, extra=None):
    mdd = float(a["mdd"]); base = dict(acct=a["name"][:20], variant=label, **(extra or {}))
    for tag in ("lo", "cl"): base[f"mean_bps_{tag}"] = round(float(R[tag][0].mean()) * 1e4, 1); base[f"hits_{tag}"] = int(R[tag][1].sum()); base[f"derisk_{tag}"] = int(R[tag][3].sum())
    sc = scenes(a, aid)
    if not sc: return [dict(base, scen="—")]
    out = []
    for nm, start, target in sc:
        r = dict(base, scen=nm, start_pct=round(start * 100, 2), target_pct=round(target * 100, 1))
        for tag in ("lo", "cl"):
            rng = np.random.default_rng(187); reach, fail, med, r8 = mc(R[tag][0], R[tag][1], R[tag][2], start, target, -mdd, rng); r.update({f"reach_{tag}": reach, f"fail_{tag}": fail, f"weeks_{tag}": med, f"reach8w_{tag}": r8})
        out.append(r)
    return out
def account_items(a):
    aid = acc_id(a["name"]); legs = EA_LEGS[aid]["eval"]; rule = a.get("rule")
    sc = 0.8 if aid == "531343523" else 1.0                      # 宝くじは 2026-11-13 に 10 → 8 倍へ切替済み(EA10L v1.09)。EA_LEGS の表は 10 倍のままなので登録どおり 8 倍に直す
    items = [(k[4:], False, w * sc) for k, w in legs.items() if k.startswith("mon:")] + [(IDXMAP[k], True, w) for k, w in legs.items() if k in IDXMAP]
    cap = (0.024, "A") if rule == "fn_instant" else ((0.025, "B") if rule == "ftmo1step" else None)
    return aid, items, cap, guards(aid, rule)[1]
def verdict(g, cur_label):
    """Q187 と同じ規則: 両判定で到達率 +2pt 以上・中央週数が現行の 1.5 倍以内。"""
    cur = g[g.variant == cur_label].iloc[0]; c = g[(g.variant != cur_label) & (g.reach_lo >= cur.reach_lo + 2) & (g.reach_cl >= cur.reach_cl + 2) & (g.weeks_lo <= 1.5 * cur.weeks_lo)]
    return cur, (c.sort_values("reach_lo", ascending=False).iloc[0] if len(c) else None)
if __name__ == "__main__":
    PR = skew_gate_dates(); rows = []; info = []
    for a in cfg["accounts"]:
        aid, items, cap, g = account_items(a)
        if not items: continue
        P0_ = paths(items, cap); dates = [p["d"] for p in P0_]; pr = PR.reindex(pd.DatetimeIndex(dates) - pd.Timedelta(days=3), method="ffill").values; hi = pr > 0.8
        fx_sum = sum(w for s, idx, w in items if not idx); status = VALIDATED.get(aid, "2 通貨型(Q174 不成立・参考)")
        R0 = run_guard(P0_, g); ex = dict(structure=status, guard_pct=round(g * 100, 1), fx_mult=round(fx_sum, 2), mondays=len(dates), gated=int(hi.sum()))
        rows += evaluate(a, aid, R0, "現行", ex)
        for lab, fac in (("SKEW 見送り", 0.0), ("SKEW 半分(参照)", 0.5)):
            Pg = paths(items, cap, {d: fac for d, h in zip(dates, hi) if h}); rows += evaluate(a, aid, run_guard(Pg, g), lab, ex)
        info.append(dict(acct=a["name"][:20], structure=status, mondays=len(dates), gated=int(hi.sum()), hit_rate_gated_lo=round(float(R0["lo"][1][hi].mean()) * 100, 1), hit_rate_kept_lo=round(float(R0["lo"][1][~hi].mean()) * 100, 1),
                         mean_gated_bps_lo=round(float(R0["lo"][0][hi].mean()) * 1e4, 1), mean_kept_bps_lo=round(float(R0["lo"][0][~hi].mean()) * 1e4, 1), mean_gated_bps_cl=round(float(R0["cl"][0][hi].mean()) * 1e4, 1), mean_kept_bps_cl=round(float(R0["cl"][0][~hi].mean()) * 1e4, 1)))
    D = pd.DataFrame(rows); D.to_csv("results/q188_skew_gate_guard_model.csv", index=False); I = pd.DataFrame(info)
    pd.set_option("display.width", 300); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 300)
    print(I.to_string(index=False)); print()
    cols = ["acct", "structure", "scen", "variant", "mean_bps_lo", "hits_lo", "mean_bps_cl", "hits_cl", "reach_lo", "reach_cl", "fail_lo", "fail_cl", "weeks_lo", "reach8w_lo"]
    print(D[[c for c in cols if c in D.columns]].to_string(index=False)); print()
    for (acct, sc), g_ in D[(D.scen != "—") & (D.variant != "SKEW 半分(参照)")].groupby(["acct", "scen"], sort=False):
        cur, best = verdict(g_, "現行"); st = g_.structure.iloc[0]
        print(f"{acct} {sc}: {'変更候補' if best is not None else '現行維持'}{'(参考・規則の対象外)' if '参考' in st else ''}")
