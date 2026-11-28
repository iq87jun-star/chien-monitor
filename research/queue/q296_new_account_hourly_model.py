# -*- coding: utf-8 -*-
"""[Q296 は下の説明を参照。以下は Q286 と同じ前半]
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
# ---------------- Q296 ----------------
# docs/244 Q296(2026-11-27 登録「登録実行」・セル 22): 新しく買う口座(月曜の円クロス 4 本)を 1 時間足の口座模型で確かめ直す。
# 場面: A = 目標 +10% → +5%(The5ers High Stakes・FTMO の 2 段階の型)/ B = 目標 +8% → +5%(FN Stellar 2-Step の型)。決済 24 時間・EA の全決済ガード 4%・固定の失格線 −10%(全停止 −9%)・52 週。
# 型: ガード {G0 なし / G2 200 日線 + 縮小 / G3 G2 + SKEW} × 倍率 {3.3, 4.5, 6.0, 7.5}。基準 = G0 × 3.3。
# 通過 = P1 到達 × P2 到達、失格 = P1 失格 + P1 到達 × P2 失格(2 期間それぞれ・安値判定と終値判定の悪い方)。
# 使い方: cd research && PYTHONPATH=queue python3 -W ignore queue/q296_new_account_hourly_model.py <累積セル数>   出力: results/q296_new_account_hourly.csv
MON4 = n["MON4"]; G = 0.04; MULTS = (3.3, 4.5, 6.0, 7.5); SC = [("A 目標 10% → 5%", 0.10, 0.05), ("B 目標 8% → 5%", 0.08, 0.05)]
GU = [("G0", False, None, None), ("G2", False, 0.5, 0.5), ("G3", True, 0.5, 0.5)]
def stage(T, dates, target, smin):
    r = {}
    for wn, sel in (("W1", np.array([d >= PM for d in dates])), ("W2", np.array([d < PM for d in dates]))):
        cols = np.arange(len(dates))[sel]; rr = [sim_eval(T[tag], cols, 0.0, target, 0.10, 0.01, smin, False) for tag in ("lo", "cl")]; r[f"reach_{wn}"] = min(x[0] for x in rr); r[f"fail_{wn}"] = max(x[1] for x in rr); r[f"weeks_{wn}"] = max((x[2] or 0) for x in rr)
        r[f"reach104_{wn}"] = min(sim_eval(T[tag], cols, 0.0, target, 0.10, 0.01, smin, False, weeks=104)[0] for tag in ("lo", "cl"))
    return r
def better(b, v): return bool(all(v[f"pass_{w}"] >= b[f"pass_{w}"] - 1.0 and v[f"fail_{w}"] <= b[f"fail_{w}"] + 1.0 for w in ("W1", "W2")) and any(v[f"pass_{w}"] >= b[f"pass_{w}"] + 2.0 or v[f"fail_{w}"] <= b[f"fail_{w}"] - 2.0 for w in ("W1", "W2")))
def worse(b, v): return bool(any(v[f"pass_{w}"] < b[f"pass_{w}"] - 1.0 or v[f"fail_{w}"] > b[f"fail_{w}"] + 1.0 for w in ("W1", "W2")))
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 22; rows = []; print("月曜の円クロス:", [(s_, round(w, 4)) for s_, i, w in MON4], flush=True); TT = {}
    for gn, skew, lo, smin in GU:
        fac = make_fac(MON4, skew, lo)
        for m in MULTS: MODE["k"] = None; TT[(gn, m)] = build_full(list(MON4), None, G, fac, m)
        print("built", gn, flush=True)
    for sn, t1, t2 in SC:
        res = {}
        for gn, skew, lo, smin in GU:
            for m in MULTS:
                T, dates = TT[(gn, m)]; p1 = stage(T, dates, t1, smin); p2 = stage(T, dates, t2, smin); r = {"guard_rate": round(float(max((T[x][1][-1] > 0).mean() for x in ("lo", "cl"))) * 100, 1)}
                for w in ("W1", "W2"):
                    r[f"pass_{w}"] = round(p1[f"reach_{w}"] * p2[f"reach_{w}"] / 100, 1); r[f"fail_{w}"] = round(p1[f"fail_{w}"] + p1[f"reach_{w}"] * p2[f"fail_{w}"] / 100, 1); r[f"p1_{w}"] = f"{p1[f'reach_{w}']:.1f} / {p1[f'fail_{w}']:.1f} / {p1[f'weeks_{w}']}"; r[f"p2_{w}"] = f"{p2[f'reach_{w}']:.1f} / {p2[f'fail_{w}']:.1f} / {p2[f'weeks_{w}']}"; r[f"weeks_{w}"] = p1[f"weeks_{w}"] + p2[f"weeks_{w}"]; r[f"p1_reach104_{w}"] = round(p1[f"reach104_{w}"], 1)
                r["net"] = round(r["pass_W1"] - r["fail_W1"] + r["pass_W2"] - r["fail_W2"], 1); res[(gn, m)] = r
        b = res[("G0", 3.3)]
        for (gn, m), r in res.items():
            isb = (gn == "G0" and m == 3.3); rows.append(dict(scene=sn, guard=gn, mult=m, cells=0 if isb else 1, verdict="基準" if isb else ("改善" if better(b, r) else ("悪化" if worse(b, r) else "差なし")), **r))
        print("done", sn, flush=True)
    D = pd.DataFrame(rows); D.to_csv("results/q296_new_account_hourly.csv", index=False); assert int(D.cells.sum()) == N
    pd.set_option("display.width", 330); pd.set_option("display.max_rows", 200)
    print(f"\n== Q296(累積セル {cum} + {N} = {cum + N}・通過 % / 失格 %(2 段階の合成)・p1 / p2 = 各段階の 到達 / 失格 / 中央の週数・W1 = 2021-08〜・W2 = 2016-11〜2021-07) =="); print(D[["scene", "guard", "mult", "guard_rate", "pass_W1", "fail_W1", "weeks_W1", "pass_W2", "fail_W2", "weeks_W2", "p1_W1", "p2_W1", "p1_W2", "p2_W2", "p1_reach104_W1", "p1_reach104_W2", "net", "verdict"]].to_string(index=False))
    print("\n選び方(場面ごとに改善の型をすべて挙げ、net が最大のもの):")
    for sn, x in D.groupby("scene", sort=False):
        ok = x[(x.cells == 1) & (x.verdict == "改善")].sort_values("net", ascending=False); b = x[x.cells == 0].iloc[0]; g26 = x[(x.guard == "G2") & (x.mult == 6.0)].iloc[0]
        print(f"  {sn}: 基準 net {b.net}(通過 {b.pass_W1} / {b.pass_W2}・失格 {b.fail_W1} / {b.fail_W2})。改善 = {[(r.guard, r.mult, r.net) for r in ok.itertuples()]}。G2 × 6.0 = {g26.verdict}(通過 {g26.pass_W1} / {g26.pass_W2}・失格 {g26.fail_W1} / {g26.fail_W2}・週 {g26.weeks_W1} / {g26.weeks_W2})")
    print(f"\nセルの判定: 改善 {int((D.verdict == '改善').sum())}・差なし {int((D.verdict == '差なし').sum())}・悪化 {int((D.verdict == '悪化').sum())} / {N}")
