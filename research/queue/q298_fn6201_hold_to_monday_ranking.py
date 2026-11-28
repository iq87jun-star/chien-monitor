# -*- coding: utf-8 -*-
"""docs/244 Q298(2026-11-28 登録・毎朝の改良検証・台帳 I-9・セル 3): FN 14166201(P1 評価中)— 長期保有(UK100・原油)を月曜の円クロス + ガードに載せ替える形の順位づけ。
枠組みは Q291(docs/533)と同じ(日次の帳簿・36 か月・6,000 本・2016-11〜2026-07)。型: 基準 = 保有 2.22 倍 + ロール / R = ロールのみ / M45 = 月曜 4.5 倍 + G2 + ロール / M60 = 月曜 6.0 倍 + G2 + ロール。
資金化後は 4 型とも 月曜 3.0 倍 + G2 + ロール。目標 +8% → +5%・失格線 −10%・日次ガード 4%・口座 10 万ドル。ロールは登録どおりグロス 2.7(参照: 4.5)。
判定は Q291 と同じ。選び方: 改善の型をすべて挙げ、純益が最大のものを載せ替えの候補とする。無ければいまの形のまま。
使い方: cd research && PYTHONPATH=queue python3 -W ignore queue/q298_fn6201_hold_to_monday_ranking.py <累積セル数>   出力: results/q298_fn6201_hold_to_monday.csv"""
import os, sys
_ARGV = list(sys.argv); HERE = os.path.dirname(os.path.abspath(__file__))
_s = open(os.path.join(HERE, "q291_purchase_mc_with_current_guards.py"), encoding="utf-8").read().split('\nif __name__ == "__main__":')[0]
q = {"__name__": "q291_head", "__file__": os.path.join(HERE, "q291_purchase_mc_with_current_guards.py")}; sys.argv = sys.argv[:1]; exec(compile(_s, "q291_head", "exec"), q)
np, pd, simulate3, FX, PC = (q[k] for k in ("np", "pd", "simulate3", "FX", "PC"))
def forms(R): return [("基準(保有 2.22 倍 + ロール)", {"hold_uw": 2.22, "roll": R}), ("R ロールのみ", {"roll": R}), ("M45 月曜 4.5 倍 + G2 + ロール", {"mon4": 4.5, "roll": R}), ("M60 月曜 6.0 倍 + G2 + ロール", {"mon4": 6.0, "roll": R})]
def verdict(b, r): return "改善" if (r["net36"] >= b["net36"] and r["fail"] <= b["fail"] + 1.0 and (r["net36"] >= 1.1 * b["net36"] or r["fail"] <= b["fail"] - 3.0)) else ("悪化" if (r["net36"] < 0.9 * b["net36"] or r["fail"] > b["fail"] + 3.0) else "差なし")
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 3; rows = []
    for R, part in ((2.7, "判定(ロール 2.7)"), (4.5, "参照(ロール 4.5)")):
        b = None
        for lab, ev in forms(R):
            c = dict(eval=ev, funded={"mon4": 3.0, "roll": R}, targets=[0.08, 0.05], mdd=0.10, dll=0.04, trail=False, k=0.0, keep=0.2, pay_frac=0.5, split=0.8, balance_jpy=100e3 * FX); r = simulate3(c, "G2", True, PC, None)
            r = {k: (round(v, 1) if isinstance(v, float) else v) for k, v in r.items()}; r["net36"] = r["pay36"]
            if b is None: b = r
            rows.append(dict(part=part, form=lab, cells=1 if (R == 2.7 and r is not b) else 0, verdict="基準" if r is b else verdict(b, r), **r)); print("done", part, lab, r, flush=True)
    D = pd.DataFrame(rows); D.to_csv("results/q298_fn6201_hold_to_monday.csv", index=False); assert int(D.cells.sum()) == N
    pd.set_option("display.width", 330); pd.set_option("display.max_colwidth", 40)
    print(f"\n== Q298(累積セル {cum} + {N} = {cum + N}・到達 % / 失格 %(評価中 / 資金化後)/ 中央到達日 / 36 か月の出金(万円・購入費は計上しない)) =="); print(D[["part", "form", "reach", "fail", "fail_eval", "fail_funded", "reach_med_days", "net36", "steady_m", "pay36_p0", "verdict"]].to_string(index=False))
    x = D[(D.cells == 1) & (D.verdict == "改善")].sort_values("net36", ascending=False); print("\n選び方(改善の型をすべて):", [(r.form, r.net36, r.fail) for r in x.itertuples()] if len(x) else "なし → いまの形のまま"); print(f"セルの判定: 改善 {int(((D.verdict == '改善') & (D.cells == 1)).sum())}・差なし {int(((D.verdict == '差なし') & (D.cells == 1)).sum())}・悪化 {int(((D.verdict == '悪化') & (D.cells == 1)).sum())} / {N}")
