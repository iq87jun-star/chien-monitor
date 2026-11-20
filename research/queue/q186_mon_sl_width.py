# -*- coding: utf-8 -*-
"""docs/244 Q186(2026-11-12 登録「登録して実行してください」): 月曜レグの損切り幅 — 3.0×ATR より広い側と「なし」。利益最大の幅はどこか。
(A) 改良系 20 セル: 構成 {Mon4, Mon2, Mon3, 指数月曜} × k {3.5, 4.0, 5.0, 6.0, なし}、基準 = 3.0×ATR24(H1)。判定は q_cal.improved。
(B) 診断・セル 0: 口座ごとに EA の月曜レグの重みで 1 時間ごとの経路を作り、日次ガード(config の dll)込みの月曜 1 回の損益・ガード発動・到達率を k ごとに出す。
再現: 為替 4/6/8/10 UTC 建て・指数は米国現物寄り後の最初の正時(夏 14・冬 15 UTC)・24h 保有・SL は H1 安値で判定し SL 価格で約定・コスト q_common.cost。
実行後の追加(登録外・参考・判定なし): (B) に狭い側 k = 2.0・2.5 と、ガード判定を各時間の終値で行った場合の感度(*_close 列)を足した。理由は docs/427 §3。
使い方: cd research && python3 -W ignore queue/q186_mon_sl_width.py <累積セル数>   出力: results/q186_mon_sl_width.csv・_acct.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
import q_common as q
from q_cal import improved
src = open(os.path.join(HERE, "q162_weekday_diversification.py"), encoding="utf-8").read().split('scen = {"B 現状"')[0]
ns = {"__name__": "q162_head", "__file__": os.path.join(HERE, "q162_weekday_diversification.py")}; exec(compile(src, "q162_head", "exec"), ns)
cfg, EA_LEGS = ns["cfg"], ns["EA_LEGS"]; acc_id = ns["ns"]["acc_id"]
CUM = int(sys.argv[1]) if len(sys.argv) > 1 else 0
KS = [2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, None]; KA = [3.5, 4.0, 5.0, 6.0, None]; KN = lambda k: "なし" if k is None else f"{k:.1f}"
P0, P1 = pd.Timestamp("2021-08-01"), pd.Timestamp("2026-07-31")
LIMIT = {"ftmo1step": 0.03, "fn_instant": 0.03}; IDXMAP = {"nas": "NAS100", "spx": "US500"}
G = 37                                                     # 月曜 04:00 UTC から 1 時間刻み 37 点(〜火曜 16:00)
def us_dst(d):
    y = d.year; mar = pd.Timestamp(y, 3, 8); mar += pd.Timedelta(days=(6 - mar.dayofweek) % 7); nov = pd.Timestamp(y, 11, 1); nov += pd.Timedelta(days=(6 - nov.dayofweek) % 7)
    return mar <= d < nov
_T = {}
def table(sym, idx):
    """全 k のショット表と経路。戻り値: meta(date, t, off, nshots) と k ごとの dict(risk, r, stop_off, mark[n,G], worst[n,G])"""
    if (sym, idx) in _T: return _T[(sym, idx)]
    df = q.load(sym); atr = q.atr24(df); pip = q.base.pip_size(sym) if not idx else 0.0
    mondays = pd.DatetimeIndex(sorted(set(df.index[df.index.dayofweek == 0].normalize()))); meta = []; res = {k: dict(risk=[], r=[], stop=[], mark=[], worst=[]) for k in KS}
    for d in mondays:
        g0 = d + pd.Timedelta(hours=4); grid = pd.date_range(g0, periods=G + 25, freq="h"); sub = df.loc[g0:grid[-1]]
        if len(sub) == 0: continue
        o_ = sub["open"].reindex(grid).values; lo_ = sub["low"].reindex(grid).values; c_ = sub["close"].reindex(grid).values
        hours = [(14 if us_dst(d) else 15)] if idx else [4, 6, 8, 10]
        for h in hours:
            a = h - 4; b = a + 24; t = grid[a]
            if np.isnan(o_[a]) or np.isnan(o_[b]) or np.isnan(atr.get(t, np.nan)): continue
            e = float(o_[a]); c = float(q.cost(sym, [e])[0]); lo = lo_[a:b]; cl = pd.Series(c_[a:b]).ffill().fillna(e).values; lw = np.where(np.isnan(lo), cl, lo)
            r_no = float(o_[b]) / e - 1 - c; meta.append((d, t, a, len(hours)))
            for k in KS:
                mark = np.zeros(G); worst = np.zeros(G); n_in = min(b, G) - a
                if k is None: sd = np.nan; j = -1
                else:
                    sd = max(k * float(atr[t]), 10 * pip); hit = np.where(lw <= e - sd)[0]; j = int(hit[0]) if len(hit) else -1
                r = (-sd / e - c) if j >= 0 else r_no
                m = cl / e - 1 - c; w = lw / e - 1 - c
                if j >= 0: m[j:] = r; w[j:] = r
                mark[a:a + n_in] = m[:n_in]; worst[a:a + n_in] = w[:n_in]
                if b < G: mark[b:] = r; worst[b:] = r
                R = res[k]; R["risk"].append(np.nan if k is None else sd / e + c); R["r"].append(r); R["stop"].append(a + j if j >= 0 else 10**6); R["mark"].append(mark); R["worst"].append(worst)
    M = pd.DataFrame(meta, columns=["date", "t", "off", "nshots"])
    for k in KS:
        for x in ("risk", "r", "stop"): res[k][x] = np.array(res[k][x], dtype=float)
        res[k]["mark"] = np.array(res[k]["mark"]); res[k]["worst"] = np.array(res[k]["worst"])
    _T[(sym, idx)] = (M, res); return _T[(sym, idx)]
# ---------- (A) 改良系 20 セル ----------
COMP = {"Mon4": ({"GBPJPY": .260, "EURJPY": .266, "AUDJPY": .215, "USDJPY": .258}, False), "Mon2": ({"GBPJPY": .537, "AUDJPY": .463}, False),
        "Mon3": ({"EURJPY": 1 / 3, "USDJPY": 1 / 3, "NZDJPY": 1 / 3}, False), "指数月曜": ({"NAS100": .5, "US500": .5}, True)}
def comp_series(w, idx, k):
    out = None; hits = 0; n = 0
    for s, wt in w.items():
        M, res = table(s, idx); r = pd.Series(res[k]["r"] * wt / M.nshots.values, index=M.date.values).groupby(level=0).sum()
        out = r if out is None else out.add(r, fill_value=0); hits += int((res[k]["stop"] < 10**6).sum()); n += len(M)
    return out, hits, n
x5 = lambda s: round(float(((1 + s[(s.index >= q.IS0) & (s.index <= q.END)]).prod() - 1) * 100), 1)
rowsA = []
for nm, (w, idx) in COMP.items():
    b, hb, nb = comp_series(w, idx, 3.0)
    for k in KA:
        v, H, N = comp_series(w, idx, k); im = improved(b, v)
        rowsA.append(dict(comp=nm, k=KN(k), hit_rate_base=round(hb / nb * 100, 1), hit_rate=round(H / N * 100, 1), cum5y_base=x5(b), cum5y=x5(v),
                          mean_bps_base=round(float(b[b.index >= q.IS0].mean()) * 1e4, 2), mean_bps=round(float(v[v.index >= q.IS0].mean()) * 1e4, 2),
                          IS_sharpe_base=round(im["base_IS"][0], 2), IS_sharpe=round(im["var_IS"][0], 2), IS_wm_base=round(im["base_IS"][1], 2), IS_wm=round(im["var_IS"][1], 2),
                          OOS_sharpe_base=round(im["base_OOS"][0], 2), OOS_sharpe=round(im["var_OOS"][0], 2), OOS_wm_base=round(im["base_OOS"][1], 2), OOS_wm=round(im["var_OOS"][1], 2), passed=im["ok"]))
A = pd.DataFrame(rowsA); assert len(A) == 20; A.to_csv("results/q186_mon_sl_width.csv", index=False)
pd.set_option("display.width", 320); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)
print(f"Q186-A: cells=20 cum_before={CUM} cum_after={CUM + 20} passed={int(A.passed.sum())}"); print(A.to_string(index=False)); print()
# ---------- (B) 口座別の診断 ----------
rng = np.random.default_rng(186); rowsB = []
ACCS = [(a, float(a["dll"]), "") for a in cfg["accounts"]] + [(a, 0.04, "(EA実設定4.0%)") for a in cfg["accounts"] if acc_id(a["name"]) == "6071612"]   # 追加: パールは config 2.8% と EA の InpBalGuardPct 4.0 が違う
for a, dll, tag in ACCS:
    aid = acc_id(a["name"]); legs = EA_LEGS[aid]["eval"]; L = LIMIT.get(a.get("rule"), 0.05); tg = (a.get("targets") or [None])[0]; mdd = float(a["mdd"])
    items = [(k[4:], False, w) for k, w in legs.items() if k.startswith("mon:")] + [(IDXMAP[k], True, w) for k, w in legs.items() if k in IDXMAP]
    if not items: continue
    cap = (0.024, "A") if a.get("rule") == "fn_instant" else ((0.025, "B") if a.get("rule") == "ftmo1step" else None)
    for k in KS:
        if cap and k is None:
            rowsB.append(dict(acct=a["name"][:20] + tag, k="なし", note="対象外(SL リスクの上限が計算できない)")); continue
        parts = []
        for s, idx, w in items:
            M, res = table(s, idx); p = M.copy(); p["w"] = w / p.nshots; p["risk_w"] = p.w * res[k]["risk"]; p["r"] = res[k]["r"]; p["stop"] = res[k]["stop"]; p["i"] = np.arange(len(p)); p["key"] = f"{s}|{idx}"; parts.append(p)
        S = pd.concat(parts); S = S[(S.date >= P0) & (S.date <= P1)].sort_values(["date", "t"]).reset_index(drop=True); f = np.ones(len(S))
        if cap:
            C, V = cap
            for d, g in S.groupby("date"):
                used = []
                for i in g.index:
                    room = C - sum(r for st, r in used if V == "B" or st > S.off[i]); r = S.risk_w[i]
                    fi = 1.0 if r <= room else (room / r if room >= 0.1 * r else 0.0); f[i] = fi; used.append((S.stop[i], r * fi))
        S["f"] = f; dates = sorted(S.date.unique()); pnl_ng = []; pnl_g = []; pnl_c = []; trig = 0; trig_c = 0
        MK = {key: (_T[(key.split("|")[0], key.split("|")[1] == "True")][1][k]) for key in S.key.unique()}
        for d, g in S.groupby("date"):
            worst = np.zeros(G); mark = np.zeros(G); fin = 0.0
            for key, gg in g.groupby("key"):
                ww = (gg.w * gg.f).values; worst += (MK[key]["worst"][gg.i.values] * ww[:, None]).sum(axis=0); mark += (MK[key]["mark"][gg.i.values] * ww[:, None]).sum(axis=0); fin += float((MK[key]["r"][gg.i.values] * ww).sum())
            pnl_ng.append(fin)
            if (worst <= -dll).any(): trig += 1; pnl_g.append(-dll * 1.1)
            else: pnl_g.append(fin)
            if (mark <= -dll).any(): trig_c += 1; pnl_c.append(-dll * 1.1)
            else: pnl_c.append(fin)
        ng = pd.Series(pnl_ng, index=pd.DatetimeIndex(dates)); gd = pd.Series(pnl_g, index=pd.DatetimeIndex(dates)); m = gd.groupby(gd.index.to_period("M")).sum()
        row = dict(acct=a["name"][:20] + tag, k=KN(k), registered=bool((k is None or k >= 3.0) and not tag), mondays=len(gd), dll=dll, firm_limit=L, mean_bps=round(gd.mean() * 1e4, 1), median_bps=round(gd.median() * 1e4, 1), worst_pct=round(gd.min() * 100, 2),
                   guard_hits=trig, mean_close_bps=round(float(np.mean(pnl_c)) * 1e4, 1), guard_hits_close=trig_c, mean_noguard_bps=round(ng.mean() * 1e4, 1), worst_noguard_pct=round(ng.min() * 100, 2), over_limit_noguard=int((ng < -L).sum()),
                   sharpe_m=round(float(m.mean() / m.std() * np.sqrt(12)), 2), notional_kept=round(float((S.w * S.f).sum() / S.w.sum()), 3))
        if tg:
            x = gd.values[rng.integers(0, len(gd), (20000, 52))].cumsum(axis=1); up = np.where((x >= tg).any(axis=1), (x >= tg).argmax(axis=1), 10**6); dn = np.where((x <= -mdd).any(axis=1), (x <= -mdd).argmax(axis=1), 10**6)
            ok = up < dn; row.update(target=tg, reach_52w=round(float(ok.mean()) * 100, 1), fail_52w=round(float((dn < up).mean()) * 100, 1), median_weeks=(int(np.median(up[ok]) + 1) if ok.any() else None))
        rowsB.append(row)
B = pd.DataFrame(rowsB); B.to_csv("results/q186_mon_sl_width_acct.csv", index=False); print("Q186-B(口座別・日次ガード込み)"); print(B.to_string(index=False))
