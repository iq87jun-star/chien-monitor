# -*- coding: utf-8 -*-
"""[Q297 は下の説明を参照。以下は Q286 と同じ前半]
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
# ---------------- Q297 ----------------
# docs/244 Q297(2026-11-28 登録・毎朝の改良検証・台帳 I-8・セル 18): Fintokei 3 口座 — ガードの幅を狭めた後の倍率を下げる側に見直す。
# 場面・開始残高・基準は Q289 と同じ。型: 月曜と夜の数量を一律に 0.9・0.8・0.7 倍(基準 1.0)。判定は Q287 と同じ。
# 選び方: 口座ごとに「2 場面とも悪化でない かつ 1 場面以上で改善」の型をすべて挙げ、score 合計が最大。無ければいまの倍率のまま。発動回数(満額の発動率 × 50 週)を併記。
# 使い方: cd research && PYTHONPATH=queue python3 -W ignore queue/q297_fintokei_multiplier_down.py <累積セル数>   出力: results/q297_fintokei_mult_down.csv
B = [("トパーズ", "6104739", "いま", 8.0, 35338207 / 35e6 - 1, 0.08, 0.01, "E1", False, 0.026, 0.5), ("トパーズ", "6104739", "次(6 倍)", 6.0, 0.0, 0.06, 0.01, "E1", True, 0.026, 0.5),
     ("ルビー", "6104736", "いま", 8.35, 10046032 / 1e7 - 1, 0.08, 0.01, "E1", False, 0.024, 1.0), ("ルビー", "6104736", "次(6.3 倍)", 6.3, 0.0, 0.06, 0.01, "E1", False, 0.024, 1.0),
     ("パール", "6071612", "いま", 5.57, 5060687 / 5e6 - 1, 0.08, 0.01, "E1", True, 0.024, 1.0), ("パール", "6071612", "次", 5.57, 0.0, 0.06, 0.01, "E1", True, 0.024, 1.0)]
FAC = (1.0, 0.9, 0.8, 0.7)
def worse(b, v): return bool(any(v[f"reach_{w}"] < b[f"reach_{w}"] - 1.0 or v[f"fail_{w}"] > b[f"fail_{w}"] + 1.0 for w in ("W1", "W2")))
def ev(its, fac, mode, g, mult, start, target, pad0):
    MODE["k"] = mode; T, dates = build_full(its, None, g, fac, mult); MODE["k"] = None; r = {"guard_rate": round(float(max((T[t][1][-1] > 0).mean() for t in ("lo", "cl"))) * 100, 1)}
    for wn, sel in (("W1", np.array([d >= PM for d in dates])), ("W2", np.array([d < PM for d in dates]))):
        cols = np.arange(len(dates))[sel]; rr = [sim_eval(T[tag], cols, start, target, 0.10, pad0, 0.5, False) for tag in ("lo", "cl")]; r[f"reach_{wn}"] = round(min(x[0] for x in rr), 1); r[f"fail_{wn}"] = round(max(x[1] for x in rr), 1); r[f"weeks_{wn}"] = max((x[2] or 0) for x in rr)
    r["score"] = round(r["reach_W1"] - r["fail_W1"] + r["reach_W2"] - r["fail_W2"], 1); r["fires_per_year"] = round(r["guard_rate"] / 100 * 50, 2); return r
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 18; rows = []; ref = pd.read_csv("results/q289_warning_policy_eval.csv"); ref = ref[ref.verdict == "基準"]
    for nm, key, stage, mm, start, target, pad0, mode, night, gcur, fi in B:
        items, _, _ = norm_items(key); itx = [(s_, i, (w * fi if i else w)) for s_, i, w in items]; its = itx + (NIGHT if night else []); fac = make_fac(items, True, 0.5); b = None
        for f in FAC:
            r = ev(its, fac, mode, gcur, mm * f, start, target, pad0)
            if f == 1.0:
                b = r; y = ref[(ref.acct == nm) & (ref.stage == stage)].iloc[0]; assert all(abs(r[c] - y[c]) < 0.05 for c in ("reach_W1", "fail_W1", "reach_W2", "fail_W2", "guard_rate")), (nm, stage, r, y.to_dict())
            rows.append(dict(acct=nm, stage=stage, mult_factor=f, mult=round(mm * f, 2), cells=0 if f == 1.0 else 1, verdict="基準" if f == 1.0 else ("改善" if ev_ok(b, r) else ("悪化" if worse(b, r) else "影響なし")), **r))
        print("done", nm, stage, flush=True)
    D = pd.DataFrame(rows); D.to_csv("results/q297_fintokei_mult_down.csv", index=False); assert int(D.cells.sum()) == N
    pd.set_option("display.width", 330); pd.set_option("display.max_rows", 200)
    print(f"\n== Q297(累積セル {cum} + {N} = {cum + N}・照合: 基準 6 行は Q289 と一致・到達 % / 失格 % / 中央の週数・fires_per_year = 満額の発動率 × 50 週) =="); print(D[["acct", "stage", "mult_factor", "mult", "guard_rate", "fires_per_year", "reach_W1", "fail_W1", "weeks_W1", "reach_W2", "fail_W2", "weeks_W2", "score", "verdict"]].to_string(index=False))
    print("\n選び方(口座ごと・2 場面とも悪化でない かつ 1 場面以上で改善の型・score 合計):")
    for nm in ("トパーズ", "ルビー", "パール"):
        x = D[D.acct == nm]; base = round(float(x[x.cells == 0].score.sum()), 1); bf = float(x[(x.cells == 0) & (x.stage == "いま")].fires_per_year.iloc[0]); ok = []; alt = []
        for f, g in x[x.cells == 1].groupby("mult_factor", sort=False):
            notworse = not (g.verdict == "悪化").any(); fy = float(g[g.stage == "いま"].fires_per_year.iloc[0])
            if notworse and (g.verdict == "改善").any(): ok.append((round(float(g.score.sum()), 1), f))
            if notworse and fy <= 0.8 * bf: alt.append((f, round(float(g.score.sum()), 1), fy))
        print(f"  {nm}: 基準 score 合計 {base}・発動 年 {bf} 回。勧める型 = {sorted(ok, reverse=True) if ok else 'なし → いまの倍率のまま'}。発動 2 割減で悪化なしの型(係数, score 合計, 発動回数)= {alt if alt else 'なし'}")
    print(f"\nセルの判定: 改善 {int((D.verdict == '改善').sum())}・影響なし {int((D.verdict == '影響なし').sum())}・悪化 {int((D.verdict == '悪化').sum())} / {N}")
