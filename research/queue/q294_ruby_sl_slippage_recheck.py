# -*- coding: utf-8 -*-
"""[Q294 は下の説明を参照。以下は Q286 と同じ前半]
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
# ---------------- Q294 ----------------
# docs/244 Q294(2026-11-27 登録「登録実行」・毎日の作案 I-4・セル 18): ルビー — 損切りの約定にすべりを入れて比べ直す。
# 型: 基準(損切り 3.0・上限なし・ガード 2.4%)/ V3(1 日の損切り合計 ≤ 2.6% + ガード 2.8% + 損切り 2.0)/ V5(損切り 2.5・上限なし・ガード 2.4%)/ G20(損切り 3.0・上限なし・ガード 2.0%)。
# すべり σ = 0・0.6%・9%・13%: 損切りにかかった建玉の損失を「損切り幅 ×(1 + σ)」にする(すべての損切りに同じ σ)。上限の計算に使う損切りリスクは名目のまま。
# 選び方: σ = 9% で「2 場面とも悪化でない かつ 1 場面以上で改善」の型の中で score 合計が最大。無ければいまのまま。
# 使い方: cd research && PYTHONPATH=queue python3 -W ignore queue/q294_ruby_sl_slippage_recheck.py <累積セル数>   出力: results/q294_ruby_sl_slippage.csv
import multiprocessing as mp
KX = {"k": 3.0}; SIG = {"s": 0.0}; _SC = {}; _tx = paths_fac.__globals__["table"]
def tbl(sym, idx):
    M, res = _tx(sym, idx); kk = 3.0 if (idx or sym[-2:] in ("@L", "@H")) else KX["k"]; R = res[kk]
    if SIG["s"] > 0:
        key = (sym, idx, kk, MODE["k"], SIG["s"])
        if key not in _SC:
            st = R["stop"]; hit = (st < 1e5) & np.isclose(R["r"], -R["risk"]); d = np.where(hit, -SIG["s"] * R["risk"], 0.0); mark = R["mark"].copy(); worst = R["worst"].copy()
            for i in np.flatnonzero(hit): j = int(st[i]); mark[i, j:] += d[i]; worst[i, j:] += d[i]
            _SC[key] = dict(R, r=R["r"] + d, mark=mark, worst=worst)
        R = _SC[key]
    return M, {KX["k"]: R}
paths_fac.__globals__["table"] = tbl
def set_k(k): KX["k"] = k; paths_fac.__globals__["K"] = k; n3["K"] = k; n3["_M3"].clear()
B = [("ルビー", "6104736", "いま", 8.35, 10046032 / 1e7 - 1, 0.08, 0.01, "E1"), ("ルビー", "6104736", "次(6.3 倍)", 6.3, 0.0, 0.06, 0.01, "E1")]
CAP = (0.026, "B"); V = [("基準(3.0・上限なし・ガード 2.4%)", 3.0, None, 0.024), ("V3 上限 2.6% + ガード 2.8%・損切り 2.0", 2.0, CAP, 0.028), ("V5 上限なし・ガード 2.4%・損切り 2.5", 2.5, None, 0.024), ("G20 上限なし・ガード 2.0%・損切り 3.0", 3.0, None, 0.020)]
SIGS = (0.0, 0.006, 0.09, 0.13)
def worse(b, v): return bool(any(v[f"reach_{w}"] < b[f"reach_{w}"] - 1.0 or v[f"fail_{w}"] > b[f"fail_{w}"] + 1.0 for w in ("W1", "W2")))
def run_task(t):
    bi, sg = t; nm, key, stage, mm, start, target, pad0, mode = B[bi]; SIG["s"] = sg; items, _, _ = norm_items(key); its = list(items); fac = make_fac(items, True, 0.5); out = []; b = None
    for lab, k, cap, g in V:
        set_k(k); MODE["k"] = mode; T, dates = build_full(its, cap, g, fac, mm); MODE["k"] = None; r = {"guard_rate": round(float(max((T[x][1][-1] > 0).mean() for x in ("lo", "cl"))) * 100, 1), "wk_mean_bps": round(float(min(T[x][0][-1].mean() for x in ("lo", "cl"))) * 1e4, 1)}
        for wn, sel in (("W1", np.array([d >= PM for d in dates])), ("W2", np.array([d < PM for d in dates]))):
            cols = np.arange(len(dates))[sel]; rr = [sim_eval(T[tag], cols, start, target, 0.10, pad0, 0.5, False) for tag in ("lo", "cl")]; r[f"reach_{wn}"] = round(min(x[0] for x in rr), 1); r[f"fail_{wn}"] = round(max(x[1] for x in rr), 1); r[f"weeks_{wn}"] = max((x[2] or 0) for x in rr)
        r["score"] = round(r["reach_W1"] - r["fail_W1"] + r["reach_W2"] - r["fail_W2"], 1)
        if b is None: b = r
        out.append(dict(stage=stage, sigma_pct=round(sg * 100, 1), form=lab, cells=0 if (r is b or sg == 0.0) else 1, verdict="基準" if r is b else ("改善" if ev_ok(b, r) else ("悪化" if worse(b, r) else "影響なし")), **r)); print("done", stage, sg, lab, r, flush=True)
    set_k(3.0); SIG["s"] = 0.0; return out
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 18; tasks = [(bi, sg) for bi in range(len(B)) for sg in SIGS]
    with mp.get_context("fork").Pool(min(4, os.cpu_count() or 1)) as pool: rows = [x for o in pool.map(run_task, tasks, chunksize=1) for x in o]
    D = pd.DataFrame(rows); D.to_csv("results/q294_ruby_sl_slippage.csv", index=False); assert int(D.cells.sum()) == N, D.cells.sum()
    pd.set_option("display.width", 330); pd.set_option("display.max_rows", 200)
    print(f"\n== Q294(累積セル {cum} + {N} = {cum + N}・到達 % / 失格 % / 中央の週数。W1 = 2021-08〜・W2 = 2016-11〜2021-07・sigma = 損切りのすべり(損切り幅に対する %)) =="); print(D[["stage", "sigma_pct", "form", "guard_rate", "wk_mean_bps", "reach_W1", "fail_W1", "weeks_W1", "reach_W2", "fail_W2", "weeks_W2", "score", "verdict"]].to_string(index=False))
    r290 = pd.read_csv("results/q290_sl_budget_cap.csv"); r290 = r290[r290.acct == "ルビー"]; r289 = pd.read_csv("results/q289_warning_policy_eval.csv"); r289 = r289[(r289.acct == "ルビー") & (r289.form == "安全側") & (r289.width_pct == 2.0)]
    print("\n照合(σ = 0):")
    for _, x in D[D.sigma_pct == 0.0].iterrows():
        if x.form.startswith("G20"): y = r289[r289.stage == x.stage].iloc[0]
        else: y = r290[(r290.stage == x.stage) & (r290.form.str[:2] == x.form[:2])].iloc[0]
        ok = all(abs(x[c] - y[c]) < 0.05 for c in ("reach_W1", "fail_W1", "reach_W2", "fail_W2")); print(f"  {x.stage} {x.form[:6]}: {'一致' if ok else '不一致'} ({x.reach_W1}/{x.fail_W1}・{x.reach_W2}/{x.fail_W2} vs {y.reach_W1}/{y.fail_W1}・{y.reach_W2}/{y.fail_W2})")
    for sg in SIGS[1:]:
        x = D[(D.sigma_pct == round(sg * 100, 1)) & (D.cells == 1)]; ok = []
        for lab, gdf in x.groupby("form", sort=False):
            if not (gdf.verdict == "悪化").any() and (gdf.verdict == "改善").any(): ok.append((round(float(gdf.score.sum()), 1), lab))
        base = round(float(D[(D.sigma_pct == round(sg * 100, 1)) & (D.verdict == "基準")].score.sum()), 1); print(f"\nσ = {sg * 100:.1f}%: 基準の score 合計 {base}。残る型 = {sorted(ok, reverse=True) if ok else 'なし'}" + ("  ← 選び方に使う水準" if sg == 0.09 else ""))
    print(f"\nセルの判定: 改善 {int(((D.verdict == '改善') & (D.cells == 1)).sum())}・影響なし {int(((D.verdict == '影響なし') & (D.cells == 1)).sum())}・悪化 {int(((D.verdict == '悪化') & (D.cells == 1)).sum())} / {N}")
