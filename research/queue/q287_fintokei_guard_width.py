# -*- coding: utf-8 -*-
"""[Q287 は下の説明を参照。以下は Q286 と同じ前半]
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
# ---------------- Q287 ----------------
# docs/244 Q287(2026-11-25 登録「登録実行」・セル 30): Fintokei 3 口座の全決済ガードの幅を下げる(最大許容リスク 3% の注意への対応・docs/241 §1bx)。
# 幅: 2.8%(基準)・2.6・2.5・2.4・2.2・2.0。場面 6(3 口座 × いま・次)。ガードの組み合わせは 11/25 に切り替えた形(SKEW + 200 日線 + 縮小)。ほかは Q286 と同じ。
# 判定: 2 期間とも 到達 ≥ 基準 − 1・失格 ≤ 基準 + 1 →「影響なし」、さらに ev_ok →「改善」、それ以外「悪化」。選び方: 2.4% 以下で、口座の 2 場面とも悪化でない最も広い幅。
# 使い方: cd research && PYTHONPATH=queue python3 -W ignore queue/q287_fintokei_guard_width.py <累積セル数>   出力: results/q287_fintokei_guard_width.csv
B = [("トパーズ", "6104739", "いま", 8.0, 35344369 / 35e6 - 1, 0.08, 0.01, "E1", False), ("トパーズ", "6104739", "次(6 倍)", 6.0, 0.0, 0.06, 0.01, "E1", True),
     ("ルビー", "6104736", "いま", 8.35, 10047790 / 1e7 - 1, 0.08, 0.01, "E1", False), ("ルビー", "6104736", "次(6.3 倍)", 6.3, 0.0, 0.06, 0.01, "E1", False),
     ("パール", "6071612", "いま", 5.57, 5061556 / 5e6 - 1, 0.08, 0.01, "E1", True), ("パール", "6071612", "次", 5.57, 0.0, 0.06, 0.01, "E1", True)]
WID = (0.028, 0.026, 0.025, 0.024, 0.022, 0.020)
def worse(b, v): return bool(any(v[f"reach_{w}"] < b[f"reach_{w}"] - 1.0 or v[f"fail_{w}"] > b[f"fail_{w}"] + 1.0 for w in ("W1", "W2")))
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 30; rows = []
    for nm, key, stage, mm, start, target, pad0, mode, night in B:
        items, _, g0 = norm_items(key); assert abs(g0 - 0.028) < 1e-9, (nm, g0); its = list(items) + (NIGHT if night else []); fac = make_fac(items, True, 0.5); res = {}
        for g in WID:
            MODE["k"] = mode; T, dates = build_full(its, None, g, fac, mm); MODE["k"] = None; r = {"guard_rate": round(float(max((T[t][1][-1] > 0).mean() for t in ("lo", "cl"))) * 100, 1)}
            for wn, sel in (("W1", np.array([d >= PM for d in dates])), ("W2", np.array([d < PM for d in dates]))):
                cols = np.arange(len(dates))[sel]; rr = [sim_eval(T[tag], cols, start, target, 0.10, pad0, 0.5, False) for tag in ("lo", "cl")]; r[f"reach_{wn}"] = round(min(x[0] for x in rr), 1); r[f"fail_{wn}"] = round(max(x[1] for x in rr), 1); r[f"weeks_{wn}"] = max((x[2] or 0) for x in rr)
            r["score"] = round(r["reach_W1"] - r["fail_W1"] + r["reach_W2"] - r["fail_W2"], 1); res[g] = r
        b = res[0.028]
        for g in WID:
            v = "基準" if g == 0.028 else ("改善" if ev_ok(b, res[g]) else ("悪化" if worse(b, res[g]) else "影響なし"))
            rows.append(dict(acct=nm, stage=stage, width_pct=round(g * 100, 1), loss_at_fire_pct=round(g * 110, 2), within3_slip20=bool(g * 1.2 < 0.03), cells=0 if g == 0.028 else 1, verdict=v, **res[g]))
        print("done", nm, stage, b, flush=True)
    D = pd.DataFrame(rows); D.to_csv("results/q287_fintokei_guard_width.csv", index=False); assert int(D.cells.sum()) == N
    pd.set_option("display.width", 330); pd.set_option("display.max_rows", 200)
    print(f"\n== Q287(累積セル {cum} + {N} = {cum + N}・到達 % / 失格 % / 中央の週数。W1 = 2021-08〜・W2 = 2016-11〜2021-07・guard_rate = 満額の数量でガードが発動する月曜の割合 %) =="); print(D[["acct", "stage", "width_pct", "guard_rate", "reach_W1", "fail_W1", "weeks_W1", "reach_W2", "fail_W2", "weeks_W2", "score", "within3_slip20", "verdict"]].to_string(index=False))
    print("\n口座ごとの選び方(2.4% 以下で、2 場面とも悪化でない最も広い幅):")
    for nm in ("トパーズ", "ルビー", "パール"):
        x = D[(D.acct == nm) & D.within3_slip20]; ok = [w for w in sorted(x.width_pct.unique(), reverse=True) if not (x[x.width_pct == w].verdict == "悪化").any()]; print(f"  {nm}: {'幅 ' + str(ok[0]) + '%' if ok else '該当なし(2.4% の悪化の幅を示して判断を仰ぐ)'}")
    print(f"\nセルの判定: 改善 {int((D.verdict == '改善').sum())}・影響なし {int((D.verdict == '影響なし').sum())}・悪化 {int((D.verdict == '悪化').sum())} / {N}")
