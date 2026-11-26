# -*- coding: utf-8 -*-
"""[Q289 は下の説明を参照。以下は Q286 と同じ前半]
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
# ---------------- Q289 ----------------
# docs/244 Q289(2026-11-26 登録「登録実行」・毎日の作案 I-1・セル 44): Fintokei の警告 3 回後(最大リスク 1%)の口座の価値と、2 回目の警告後に幅を下げるべきかの分かれ目。
# 基準 = いまの配備(ガード幅 トパーズ 2.6%・ルビー / パール 2.4%・トパーズの月曜の指数 0.5 倍・SKEW + 200 日線 + 縮小)。開始残高は 2026-11-26 06:22 JST。
# (a) 1% の形: ガード 0.8% × 倍率の係数 {1.0, 0.5, 0.375, 0.25}(評価中 6 場面 + 本口座後 2 構成・32 セル)。(b) 安全側: 評価中 6 場面でガード 2.2%・2.0%(12 セル)。
# まとめ: S = score の 2 場面合計。F = 「いま」の場面の満額の発動率 × 50 週。p* = 1 − (1 − (S_now − S_safe)/(S_now − S_1))^(1/F)。p* ≤ 25% →「2 回目で 2.0% へ」、≥ 50% →「いまのまま」、その間 → 判断を仰ぐ。
# 使い方: cd research && PYTHONPATH=queue python3 -W ignore queue/q289_fintokei_warning_count_policy.py <累積セル数>   出力: results/q289_warning_policy_eval.csv・_funded.csv・_summary.csv
sim_funded, roll_week, fund_ok, NP = n["sim_funded"], n["roll_week"], n["fund_ok"], n["NP"]
B = [("トパーズ", "6104739", "いま", 8.0, 35338207 / 35e6 - 1, 0.08, 0.01, "E1", False, 0.026, 0.5), ("トパーズ", "6104739", "次(6 倍)", 6.0, 0.0, 0.06, 0.01, "E1", True, 0.026, 0.5),
     ("ルビー", "6104736", "いま", 8.35, 10046032 / 1e7 - 1, 0.08, 0.01, "E1", False, 0.024, 1.0), ("ルビー", "6104736", "次(6.3 倍)", 6.3, 0.0, 0.06, 0.01, "E1", False, 0.024, 1.0),
     ("パール", "6071612", "いま", 5.57, 5060687 / 5e6 - 1, 0.08, 0.01, "E1", True, 0.024, 1.0), ("パール", "6071612", "次", 5.57, 0.0, 0.06, 0.01, "E1", True, 0.024, 1.0)]
A = [("トパーズ", "6104739", 3.0, 4.5, 0.026, 0.5), ("ルビー / パール", "6104736", 2.78, 4.5, 0.024, 1.0)]
G1 = 0.008; FAC = (1.0, 0.5, 0.375, 0.25); SAFE = (0.022, 0.020)
def worse(b, v): return bool(any(v[f"reach_{w}"] < b[f"reach_{w}"] - 1.0 or v[f"fail_{w}"] > b[f"fail_{w}"] + 1.0 for w in ("W1", "W2")))
def ev(its, fac, mode, g, mult, start, target, pad0):
    MODE["k"] = mode; T, dates = build_full(its, None, g, fac, mult); MODE["k"] = None; r = {"guard_rate": round(float(max((T[t][1][-1] > 0).mean() for t in ("lo", "cl"))) * 100, 1)}
    for wn, sel in (("W1", np.array([d >= PM for d in dates])), ("W2", np.array([d < PM for d in dates]))):
        cols = np.arange(len(dates))[sel]; rr = [sim_eval(T[tag], cols, start, target, 0.10, pad0, 0.5, False) for tag in ("lo", "cl")]; r[f"reach_{wn}"] = round(min(x[0] for x in rr), 1); r[f"fail_{wn}"] = round(max(x[1] for x in rr), 1); r[f"weeks_{wn}"] = max((x[2] or 0) for x in rr)
        r3 = [sim_eval(T[tag], cols, start, target, 0.10, pad0, 0.5, False, weeks=156) for tag in ("lo", "cl")]; r[f"reach156_{wn}"] = round(min(x[0] for x in r3), 1); r[f"fail156_{wn}"] = round(max(x[1] for x in r3), 1)
    r["score"] = round(r["reach_W1"] - r["fail_W1"] + r["reach_W2"] - r["fail_W2"], 1); return r
def fu(items, fac, g, mm, rw):
    MODE["k"] = "E1"; T, dates = build_full(items, None, g, fac, mm); MODE["k"] = None; call = np.arange(len(dates)); c2 = call[np.array([d < PM for d in dates])]; add = roll_week(dates, rw, g) if rw else np.zeros(len(dates)); r = {"guard_rate": round(float(max((T[t][1][-1] > 0).mean() for t in ("lo", "cl"))) * 100, 1)}; x = {}
    for tag in ("lo", "cl"):
        m = sim_funded(T[tag], add, call, 0.10, 0.01, False, 520, NP); m2 = sim_funded(T[tag], add, c2, 0.10, 0.01, False, 260, 10000); x[tag] = dict(s10=m[520][0], p10=m[520][1], s5=m[260][0], p5=m[260][1], w2s5=m2[260][0])
    for k in ("s10", "p10", "s5", "p5", "w2s5"): r[k] = round(min(x["lo"][k], x["cl"][k]), 1)
    return r
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 44; rows = []; rowsF = []; RES = {}
    for nm, key, stage, mm, start, target, pad0, mode, night, gcur, fi in B:
        items, _, _ = norm_items(key); itx = [(s_, i, (w * fi if i else w)) for s_, i, w in items]; its = itx + (NIGHT if night else []); fac = make_fac(items, True, 0.5)
        b = ev(its, fac, mode, gcur, mm, start, target, pad0); RES[(nm, stage, "基準")] = b; rows.append(dict(acct=nm, stage=stage, form="基準(いまの配備)", width_pct=round(gcur * 100, 1), mult_factor=1.0, cells=0, verdict="基準", **b)); print("base", nm, stage, b, flush=True)
        for f in FAC:
            v = ev(its, fac, mode, G1, mm * f, start, target, pad0); RES[(nm, stage, ("1%", f))] = v; rows.append(dict(acct=nm, stage=stage, form="1% の形", width_pct=0.8, mult_factor=f, cells=1, verdict="改善" if ev_ok(b, v) else ("悪化" if worse(b, v) else "影響なし"), **v))
        for g in SAFE:
            v = ev(its, fac, mode, g, mm, start, target, pad0); RES[(nm, stage, ("safe", g))] = v; rows.append(dict(acct=nm, stage=stage, form="安全側", width_pct=round(g * 100, 1), mult_factor=1.0, cells=1, verdict="改善" if ev_ok(b, v) else ("悪化" if worse(b, v) else "影響なし"), **v))
        print("done", nm, stage, flush=True)
    for nm, key, mm, rw, gcur, fi in A:
        items, _, _ = norm_items(key); itx = [(s_, i, (w * fi if i else w)) for s_, i, w in items]; fac = make_fac(items, True, 0.5); b = fu(itx, fac, gcur, mm, rw); rowsF.append(dict(acct=nm, form="基準(いまの幅)", width_pct=round(gcur * 100, 1), mult_factor=1.0, cells=0, verdict="基準", **b)); print("funded base", nm, b, flush=True)
        for f in FAC:
            v = fu(itx, fac, G1, mm * f, rw * f); bs, vs = pd.Series(b), pd.Series(v); rowsF.append(dict(acct=nm, form="1% の形", width_pct=0.8, mult_factor=f, cells=1, verdict="改善" if fund_ok(bs, vs) else ("悪化" if (v["s10"] < b["s10"] - 1.0 or v["p10"] < b["p10"]) else "影響なし"), **v))
        print("funded done", nm, flush=True)
    D = pd.DataFrame(rows); DF = pd.DataFrame(rowsF); D.to_csv("results/q289_warning_policy_eval.csv", index=False); DF.to_csv("results/q289_warning_policy_funded.csv", index=False); assert int(D.cells.sum()) + int(DF.cells.sum()) == N
    pd.set_option("display.width", 330); pd.set_option("display.max_rows", 200)
    print(f"\n== Q289 評価中(累積セル {cum} + {N} = {cum + N}・到達 % / 失格 % / 中央の週数。W1 = 2021-08〜・W2 = 2016-11〜2021-07・reach156 = 156 週までの到達) =="); print(D[["acct", "stage", "form", "width_pct", "mult_factor", "guard_rate", "reach_W1", "fail_W1", "weeks_W1", "reach_W2", "fail_W2", "weeks_W2", "reach156_W1", "fail156_W1", "reach156_W2", "fail156_W2", "score", "verdict"]].to_string(index=False))
    print("\n== Q289 本口座後(s10 = 10 年の生存 %・p10 = 10 年の出金 = 額面比 %・s5 / p5 = 5 年・w2s5 = 前半だけで抽選した 5 年の生存) =="); print(DF[["acct", "form", "width_pct", "mult_factor", "guard_rate", "s10", "p10", "s5", "p5", "w2s5", "verdict"]].to_string(index=False))
    S = []
    for nm in ("トパーズ", "ルビー", "パール"):
        st = [s for (a, s, k) in RES if a == nm and k == "基準"]; s_now = sum(RES[(nm, s, "基準")]["score"] for s in st); s_1 = sum(max(RES[(nm, s, ("1%", f))]["score"] for f in FAC) for s in st); best = {s: max(FAC, key=lambda f: RES[(nm, s, ("1%", f))]["score"]) for s in st}
        F = RES[(nm, "いま", "基準")]["guard_rate"] / 100 * 50; r = dict(acct=nm, S_now=round(s_now, 1), S_1pct=round(s_1, 1), best_factor=str(best), fires_per_year=round(F, 2))
        for g in SAFE:
            s_s = sum(RES[(nm, s, ("safe", g))]["score"] for s in st); ratio = (s_now - s_s) / (s_now - s_1) if s_now - s_1 > 0 else float("nan"); ps = (1.0 if ratio >= 1 else (0.0 if ratio <= 0 else 1 - (1 - ratio) ** (1 / F))) if (ratio == ratio and F > 0) else float("nan")
            r[f"S_safe_{g * 100:.1f}"] = round(s_s, 1); r[f"pstar_{g * 100:.1f}"] = round(ps * 100, 1)
        ps = r["pstar_2.0"]; r["advice"] = "2 回目の警告を受けたら 2.0% に下げる" if ps <= 25 else ("下げずにいまの幅のまま" if ps >= 50 else "数字を示して判断を仰ぐ")
        for p in (5, 10, 25, 50): r[f"warn_per_year_p{p}"] = round(F * p / 100, 2)
        S.append(r)
    DS = pd.DataFrame(S); DS.to_csv("results/q289_warning_policy_summary.csv", index=False); print("\n== まとめ(S = score の 2 場面合計・pstar = 分かれ目の p %) =="); print(DS.to_string(index=False))
    print(f"\nセルの判定(評価中): 改善 {int((D.verdict == '改善').sum())}・影響なし {int((D.verdict == '影響なし').sum())}・悪化 {int((D.verdict == '悪化').sum())} / {int(D.cells.sum())}  本口座後: 改善 {int((DF.verdict == '改善').sum())}・影響なし {int((DF.verdict == '影響なし').sum())}・悪化 {int((DF.verdict == '悪化').sum())} / {int(DF.cells.sum())}")
