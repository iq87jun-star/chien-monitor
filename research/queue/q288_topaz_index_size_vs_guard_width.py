# -*- coding: utf-8 -*-
"""[Q288 は下の説明を参照。以下は Q286 と同じ前半]
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
# ---------------- Q288 ----------------
# docs/244 Q288(2026-11-25 登録「登録実行」・セル 28): トパーズ — 月曜の指数の数量 {1.0, 0.75, 0.5, 0.25, 0} × 全決済ガードの幅 {2.8, 2.6, 2.4%}。
# 円クロス・夜の指数・3 つのガード・決済の型は 11/25 の形。場面 = トパーズ いま(8 倍)・次(6 倍)。基準 = 指数 1.0・幅 2.8%。
# すべりの見込み(仮定): 発動時の損失 = 幅 + 0.4% × 指数の倍率 + 0.1%。3.0% 未満を「収まる」。選び方: 収まる中で 2 場面の score 合計が最大 → Q287 の提案(1.0・2.4%)に対して ev_ok かつ悪化なしなら勧める。
# 使い方: cd research && PYTHONPATH=queue python3 -W ignore queue/q288_topaz_index_size_vs_guard_width.py <累積セル数>   出力: results/q288_topaz_index_vs_guard.csv
B = [("トパーズ", "6104739", "いま", 8.0, 35344369 / 35e6 - 1, 0.08, 0.01, "E1", False), ("トパーズ", "6104739", "次(6 倍)", 6.0, 0.0, 0.06, 0.01, "E1", True)]
FI = (1.0, 0.75, 0.5, 0.25, 0.0); WID = (0.028, 0.026, 0.024)
def worse(b, v): return bool(any(v[f"reach_{w}"] < b[f"reach_{w}"] - 1.0 or v[f"fail_{w}"] > b[f"fail_{w}"] + 1.0 for w in ("W1", "W2")))
def fits(f, g): return bool(g * 100 + 0.4 * f + 0.1 < 3.0 - 1e-9)
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 28; rows = []; RES = {}
    for nm, key, stage, mm, start, target, pad0, mode, night in B:
        items, _, g0 = norm_items(key); assert abs(g0 - 0.028) < 1e-9; fac = make_fac(items, True, 0.5); print(stage, "指数のレグ:", [(s_, round(w, 4)) for s_, i, w in items if i], flush=True)
        for f in FI:
            its = [(s_, i, (w * f if i else w)) for s_, i, w in items if not (i and f == 0.0)] + (NIGHT if night else [])
            for g in WID:
                MODE["k"] = mode; T, dates = build_full(its, None, g, fac, mm); MODE["k"] = None; r = {"guard_rate": round(float(max((T[t][1][-1] > 0).mean() for t in ("lo", "cl"))) * 100, 1)}
                for wn, sel in (("W1", np.array([d >= PM for d in dates])), ("W2", np.array([d < PM for d in dates]))):
                    cols = np.arange(len(dates))[sel]; rr = [sim_eval(T[tag], cols, start, target, 0.10, pad0, 0.5, False) for tag in ("lo", "cl")]; r[f"reach_{wn}"] = round(min(x[0] for x in rr), 1); r[f"fail_{wn}"] = round(max(x[1] for x in rr), 1); r[f"weeks_{wn}"] = max((x[2] or 0) for x in rr)
                r["score"] = round(r["reach_W1"] - r["fail_W1"] + r["reach_W2"] - r["fail_W2"], 1); RES[(stage, f, g)] = r
            print("done", stage, f, flush=True)
    for (stage, f, g), r in RES.items():
        b = RES[(stage, 1.0, 0.028)]; ref = RES[(stage, 1.0, 0.024)]; isb = (f == 1.0 and g == 0.028)
        rows.append(dict(stage=stage, idx_factor=f, width_pct=round(g * 100, 1), loss_at_fire_assumed=round(g * 100 + 0.4 * f + 0.1, 2), fits=fits(f, g), cells=0 if isb else 1, verdict="基準" if isb else ("改善" if ev_ok(b, r) else ("悪化" if worse(b, r) else "影響なし")), vs_ref=("—" if (f == 1.0 and g == 0.024) else ("ev_ok" if ev_ok(ref, r) else ("悪化" if worse(ref, r) else "差なし"))), **r))
    D = pd.DataFrame(rows); D.to_csv("results/q288_topaz_index_vs_guard.csv", index=False); assert int(D.cells.sum()) == N
    pd.set_option("display.width", 330); pd.set_option("display.max_rows", 200)
    print(f"\n== Q288(累積セル {cum} + {N} = {cum + N}・vs_ref = Q287 の提案(指数 1.0・幅 2.4%)に対する判定) =="); print(D[["stage", "idx_factor", "width_pct", "loss_at_fire_assumed", "fits", "guard_rate", "reach_W1", "fail_W1", "weeks_W1", "reach_W2", "fail_W2", "weeks_W2", "score", "verdict", "vs_ref"]].to_string(index=False))
    S = D[D.fits].groupby(["idx_factor", "width_pct"]).score.sum().sort_values(ascending=False); print("\n「収まる」組み合わせの 2 場面の score 合計:"); print(S.round(1).to_string())
    (bf, bw) = S.index[0]; x = D[(D.idx_factor == bf) & (D.width_pct == bw)]; print(f"\n候補 = 指数 {bf} 倍・幅 {bw}%: Q287 の提案に対して {list(x.vs_ref.values)}")
    print("結論:", "Q287 の提案(指数 1.0 倍・幅 2.4%)のまま" if (bf == 1.0 and bw == 2.4) or not ((x.vs_ref == "ev_ok").any() and not (x.vs_ref == "悪化").any()) else f"指数 {bf} 倍・幅 {bw}% を勧める")
