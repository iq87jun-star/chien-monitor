# -*- coding: utf-8 -*-
"""[Q290 は下の説明を参照。以下は Q286 と同じ前半]
docs/244 Q286(2026-11-25 登録・ユーザー「各口座最適ガードを考案してください」・セル 63): 口座ごとのガードの最適な組み合わせ(Fintokei 3 口座・FTMO 50k 2 口座)。
組み合わせ(8): SKEW の見送り × 200 日線の上 0.5 倍 × 損失枠の縮小(下限 0.5)。場面(9): 5 口座のいまの段階と次の段階。「いま」の開始残高は 2026-11-25 06:22 JST。
倍率・決済の型・日次ガードは Q263b の場面のまま。夜の指数は配備・予定どおり(FTMO 7058 いま・パール いま・FTMO 50k 次・トパーズ 次・パール 次)。
判定: 各セル = Q233 の ev_ok(その場面のいまの組み合わせに対して)。その場面の最適 = ev_ok の中で(① 到達 − 失格)+(② 到達 − 失格)が最大。無ければ「いまの組み合わせが最適」。
使い方: cd research && PYTHONPATH=queue python3 -W ignore queue/q286_guard_combo_per_account_eval.py <累積セル数>   出力: results/q286_guard_combo_eval.csv"""
import os, sys, itertools
_ARGV = list(sys.argv)
HERE = os.path.dirname(os.path.abspath(__file__)); _s = open(os.path.join(HERE, "q263b_monday_night_index_account_model.py"), encoding="utf-8").read()
n = {"__name__": "q263b_head", "__file__": os.path.join(HERE, "q263b_monday_night_index_account_model.py")}; exec(compile(_s.split("\nrows = []\n")[0], "q263b_head", "exec"), n)
np, pd = n["np"], n["pd"]; n3 = n["n3"]; norm_items, make_fac, build_full, sim_eval, MODE, PM, table_x, paths_fac, ev_ok = (n[k] for k in ("norm_items", "make_fac", "build_full", "sim_eval", "MODE", "PM", "table_x", "paths_fac", "ev_ok")); VIX = n3["VIX"]; _hot0 = n["hot"]; _C = {}
def _v(d): x = VIX.reindex([pd.Timestamp(d) - pd.Timedelta(days=3)], method="ffill").values[0]; return x if x == x else 0.0
HOTF = {"L": lambda d: 25 < _v(d) <= 30, "H": lambda d: _v(d) > 30}
def band_table(sym, band):                                                  # Q269b と同じ
    k = (sym, band)
    if k not in _C: n["hot"] = HOTF[band]; n["_N"].pop(sym, None); _C[k] = n["night_table"](sym); n["_N"].pop(sym, None); n["hot"] = _hot0
    return _C[k]
paths_fac.__globals__["table"] = lambda sym, idx: band_table(sym[:-2], sym[-1]) if sym[-2:] in ("@L", "@H") else table_x(sym, idx)
IDX = ("NAS100", "US500", "US30", "JP225", "UK100"); NIGHT = [(s + "@L", True, 0.05) for s in IDX] + [(s + "@H", True, 0.10) for s in IDX]
# ---------------- Q290 ----------------
# docs/244 Q290(2026-11-26 登録「登録実行」・毎日の作案 I-3・セル 30): Fintokei 3 口座 — 1 日の損切り合計を 2.6% に収める形(V1〜V3)と、損切りを狭める形(V4・V5)。
# 基準 = いまの配備(損切り 3.0 × ATR・上限なし・口座ガード トパーズ 2.6% / ルビー・パール 2.4%)。場面・開始残高は Q289 と同じ。指数と夜の指数の損切りは 3.0 × ATR のまま。
# 選び方: 口座ごとに「2 場面とも悪化でない かつ 1 場面以上で改善」の型をすべて挙げ、score の 2 場面合計が最大のものを勧める。無ければいまの形のまま。
# 使い方: cd research && PYTHONPATH=queue python3 -W ignore queue/q290_fintokei_sl_budget_cap.py <累積セル数>   出力: results/q290_sl_budget_cap.csv
import multiprocessing as mp
KX = {"k": 3.0}; _tx = paths_fac.__globals__["table"]
def tbl(sym, idx):
    M, res = _tx(sym, idx)
    return (M, {KX["k"]: res[3.0]}) if (idx or sym[-2:] in ("@L", "@H")) else (M, res)
paths_fac.__globals__["table"] = tbl
def set_k(k): KX["k"] = k; paths_fac.__globals__["K"] = k; n3["K"] = k; n3["_M3"].clear()
B = [("トパーズ", "6104739", "いま", 8.0, 35338207 / 35e6 - 1, 0.08, 0.01, "E1", False, 0.026, 0.5), ("トパーズ", "6104739", "次(6 倍)", 6.0, 0.0, 0.06, 0.01, "E1", True, 0.026, 0.5),
     ("ルビー", "6104736", "いま", 8.35, 10046032 / 1e7 - 1, 0.08, 0.01, "E1", False, 0.024, 1.0), ("ルビー", "6104736", "次(6.3 倍)", 6.3, 0.0, 0.06, 0.01, "E1", False, 0.024, 1.0),
     ("パール", "6071612", "いま", 5.57, 5060687 / 5e6 - 1, 0.08, 0.01, "E1", True, 0.024, 1.0), ("パール", "6071612", "次", 5.57, 0.0, 0.06, 0.01, "E1", True, 0.024, 1.0)]
CAP = (0.026, "B"); V = [("基準(3.0・上限なし・いまの幅)", 3.0, None, None), ("V1 上限 2.6% + ガード 2.8%・損切り 3.0", 3.0, CAP, 0.028), ("V2 上限 2.6% + ガード 2.8%・損切り 2.5", 2.5, CAP, 0.028), ("V3 上限 2.6% + ガード 2.8%・損切り 2.0", 2.0, CAP, 0.028),
     ("V4 上限なし・いまの幅・損切り 2.0", 2.0, None, None), ("V5 上限なし・いまの幅・損切り 2.5", 2.5, None, None)]
def worse(b, v): return bool(any(v[f"reach_{w}"] < b[f"reach_{w}"] - 1.0 or v[f"fail_{w}"] > b[f"fail_{w}"] + 1.0 for w in ("W1", "W2")))
def risk_stats(its, fac, mode, mult, C):
    """満額の数量での 1 日の損切り合計(口座比 %)の中央・95% 点、上限を超える月曜の割合、上限で残る数量の平均(概算 = min(1, C / 合計))。"""
    MODE["k"] = mode; parts = []
    for s, idxf, w in its:
        Mt, res = tbl(s, idxf); p = Mt[["date"]].copy(); ww = mult * w / Mt.nshots.values
        if (s, idxf) in fac: ww = ww * p.date.map(lambda d: fac[(s, idxf)].get(d, 1.0)).values
        p["r"] = ww * res[KX["k"]]["risk"]; parts.append(p)
    MODE["k"] = None; R = pd.concat(parts); R = R[(R.date >= n3["P0"]) & (R.date <= n3["P1"])].groupby("date").r.sum(); R = R[R > 0]
    return dict(risk_med=round(float(R.median()) * 100, 2), risk_p95=round(float(R.quantile(0.95)) * 100, 2), capped_pct=round(float((R > C).mean()) * 100, 1), kept_avg=round(float(np.minimum(1.0, C / R).mean()), 3))
def run_scene(i):
    nm, key, stage, mm, start, target, pad0, mode, night, gcur, fi = B[i]; items, _, _ = norm_items(key); itx = [(s_, j, (w * fi if j else w)) for s_, j, w in items]; its = itx + (NIGHT if night else []); fac = make_fac(items, True, 0.5); out = []; b = None
    for lab, k, cap, g in V:
        set_k(k); g = gcur if g is None else g; MODE["k"] = mode; T, dates = build_full(its, cap, g, fac, mm); MODE["k"] = None; r = {"guard_rate": round(float(max((T[t][1][-1] > 0).mean() for t in ("lo", "cl"))) * 100, 1)}
        for wn, sel in (("W1", np.array([d >= PM for d in dates])), ("W2", np.array([d < PM for d in dates]))):
            cols = np.arange(len(dates))[sel]; rr = [sim_eval(T[tag], cols, start, target, 0.10, pad0, 0.5, False) for tag in ("lo", "cl")]; r[f"reach_{wn}"] = round(min(x[0] for x in rr), 1); r[f"fail_{wn}"] = round(max(x[1] for x in rr), 1); r[f"weeks_{wn}"] = max((x[2] or 0) for x in rr)
        r["score"] = round(r["reach_W1"] - r["fail_W1"] + r["reach_W2"] - r["fail_W2"], 1); r["wk_mean_bps"] = round(float(min(T[t][0][-1].mean() for t in ("lo", "cl"))) * 1e4, 1); r.update(risk_stats(its, fac, mode, mm, CAP[0]))
        if b is None: b = r
        out.append(dict(acct=nm, stage=stage, form=lab, sl_k=k, cap_pct=(CAP[0] * 100 if cap else None), guard_pct=round(g * 100, 1), cells=0 if r is b else 1, verdict="基準" if r is b else ("改善" if ev_ok(b, r) else ("悪化" if worse(b, r) else "影響なし")), **r)); print("done", nm, stage, lab, r, flush=True)
    set_k(3.0); return out
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 30
    with mp.get_context("fork").Pool(min(6, os.cpu_count() or 1)) as pool: rows = [x for o in pool.map(run_scene, range(len(B))) for x in o]
    D = pd.DataFrame(rows); D.to_csv("results/q290_sl_budget_cap.csv", index=False); assert int(D.cells.sum()) == N
    pd.set_option("display.width", 330); pd.set_option("display.max_rows", 200)
    print(f"\n== Q290(累積セル {cum} + {N} = {cum + N}・到達 % / 失格 % / 中央の週数。W1 = 2021-08〜・W2 = 2016-11〜2021-07・risk_* = 満額での 1 日の損切り合計 %・kept_avg = 上限 2.6% で残る数量の概算) =="); print(D[["acct", "stage", "form", "guard_rate", "wk_mean_bps", "reach_W1", "fail_W1", "weeks_W1", "reach_W2", "fail_W2", "weeks_W2", "score", "risk_med", "risk_p95", "capped_pct", "kept_avg", "verdict"]].to_string(index=False))
    print("\n口座ごとの選び方(2 場面とも悪化でない かつ 1 場面以上で改善の型をすべて挙げ、score 合計が最大のもの):")
    for nm in ("トパーズ", "ルビー", "パール"):
        x = D[(D.acct == nm) & (D.cells == 1)]; ok = []
        for lab, g in x.groupby("form"):
            if not (g.verdict == "悪化").any() and (g.verdict == "改善").any(): ok.append((round(float(g.score.sum()), 1), lab))
        base = round(float(D[(D.acct == nm) & (D.cells == 0)].score.sum()), 1); print(f"  {nm}: 基準の score 合計 {base}。該当 = {sorted(ok, reverse=True) if ok else 'なし → いまの形(口座ガードのみ)のまま'}")
    print(f"\nセルの判定: 改善 {int((D.verdict == '改善').sum())}・影響なし {int((D.verdict == '影響なし').sum())}・悪化 {int((D.verdict == '悪化').sum())} / {N}")
