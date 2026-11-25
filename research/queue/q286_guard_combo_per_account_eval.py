# -*- coding: utf-8 -*-
"""docs/244 Q286(2026-11-25 登録・ユーザー「各口座最適ガードを考案してください」・セル 63): 口座ごとのガードの最適な組み合わせ(Fintokei 3 口座・FTMO 50k 2 口座)。
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
# 場面: (口座, key, 段階, 倍率, いまの組み合わせ(skew, tilt, shrink), 開始, 目標, pad, 決済の型, 夜の指数)
B = [("FTMO 0397", "521100397", "いま", 6.0, (False, False, False), 53854 / 5e4 - 1, 0.10, 0.01, None, False), ("FTMO 7058", "531407058", "いま", 6.0, (False, False, False), 51513 / 5e4 - 1, 0.10, 0.01, None, True),
     ("FTMO 50k", "521100397", "次", 6.0, (False, True, True), 0.0, 0.05, 0.01, None, True),
     ("トパーズ", "6104739", "いま", 8.0, (False, False, False), 35344369 / 35e6 - 1, 0.08, 0.01, "E1", False), ("トパーズ", "6104739", "次(6 倍)", 6.0, (True, True, True), 0.0, 0.06, 0.01, "E1", True),
     ("ルビー", "6104736", "いま", 8.35, (False, True, True), 10047790 / 1e7 - 1, 0.08, 0.01, "E1", False), ("ルビー", "6104736", "次(6.3 倍)", 6.3, (False, True, True), 0.0, 0.06, 0.01, "E1", False),
     ("パール", "6071612", "いま", 5.57, (False, False, False), 5061556 / 5e6 - 1, 0.08, 0.01, "E1", True), ("パール", "6071612", "次", 5.57, (False, True, True), 0.0, 0.06, 0.01, "E1", True)]
def name(c): return " + ".join(x for x, f in zip(("SKEW", "200 日線", "縮小"), c) if f) or "なし"
def worse(b, v): return bool(any(v[f"reach_{w}"] < b[f"reach_{w}"] - 1.0 or v[f"fail_{w}"] > b[f"fail_{w}"] + 1.0 for w in ("W1", "W2")))
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 63; rows = []; COMBOS = list(itertools.product((False, True), repeat=3))
    for nm, key, stage, mm, cur, start, target, pad0, mode, night in B:
        items, _, g = norm_items(key); its = list(items) + (NIGHT if night else []); res = {}
        for c in COMBOS:
            skew, tilt, shr = c; fac = make_fac(items, skew, 0.5 if tilt else None); MODE["k"] = mode; T, dates = build_full(its, None, g, fac, mm); MODE["k"] = None; r = {}
            for wn, sel in (("W1", np.array([d >= PM for d in dates])), ("W2", np.array([d < PM for d in dates]))):
                cols = np.arange(len(dates))[sel]; rr = [sim_eval(T[tag], cols, start, target, 0.10, pad0, 0.5 if shr else None, False) for tag in ("lo", "cl")]; r[f"reach_{wn}"] = round(min(x[0] for x in rr), 1); r[f"fail_{wn}"] = round(max(x[1] for x in rr), 1); r[f"weeks_{wn}"] = max((x[2] or 0) for x in rr)
            r["score"] = round(r["reach_W1"] - r["fail_W1"] + r["reach_W2"] - r["fail_W2"], 1); res[c] = r
        b = res[cur]; oks = [c for c in COMBOS if c != cur and ev_ok(b, res[c])]; best = max(oks, key=lambda c: res[c]["score"]) if oks else cur
        for c in COMBOS:
            v = "基準(いま)" if c == cur else ("変更候補" if c in oks else ("悪化" if worse(b, res[c]) else "現行どおり"))
            rows.append(dict(acct=nm, stage=stage, combo=name(c), skew=c[0], tilt=c[1], shrink=c[2], night=night, mode=mode or "24h", mult=mm, cells=0 if c == cur else 1, verdict=v, best=(c == best), **res[c]))
        print("done", nm, stage, "いま =", name(cur), b, "→ 最適 =", name(best), res[best], flush=True)
    D = pd.DataFrame(rows); D.to_csv("results/q286_guard_combo_eval.csv", index=False); assert int(D.cells.sum()) == N
    pd.set_option("display.width", 330); pd.set_option("display.max_rows", 200)
    print(f"\n== Q286(累積セル {cum} + {N} = {cum + N}・到達 % / 失格 % / 中央の週数。W1 = 2021-08〜・W2 = 2016-11〜2021-07・score = 2 つの期間の(到達 − 失格)の合計) =="); print(D[["acct", "stage", "combo", "reach_W1", "fail_W1", "weeks_W1", "reach_W2", "fail_W2", "weeks_W2", "score", "verdict", "best"]].to_string(index=False))
    print(f"\nセルの判定: 変更候補 {int((D.verdict == '変更候補').sum())} / {N}・悪化 {int((D.verdict == '悪化').sum())} / {N}"); print("場面ごとの最適:"); print(D[D.best][["acct", "stage", "combo", "verdict", "reach_W1", "fail_W1", "reach_W2", "fail_W2", "score"]].to_string(index=False))
