# -*- coding: utf-8 -*-
"""docs/244 Q295(2026-11-27 登録「登録実行」・毎日の作案 I-5・セル 12): 新しく買う口座 — ガードを入れた上で倍率を上げる形。
枠組みは Q291(docs/533)と同じ。候補: The5ers High Stakes 100k + Mon4・FN Stellar 2-Step 25k ×3 + Mon4。型: {G2, G3} × 倍率 {3.3(再現), 4.5, 6.0, 7.5}。基準 = その候補の G0 × 3.3。
判定は Q291 と同じ。まとめ: 候補ごとに改善の型の中で純益最大を採り、Q291 の首位(A 案 ×1.5・純益 176.2 万・失格 16.2%)を上回るかを報告。
参照: 日次ガードの発動時の損失を幅 × 1.1 にした場合(*_s11 列)。
使い方: cd research && PYTHONPATH=queue python3 -W ignore queue/q295_purchase_guards_higher_multiplier.py <累積セル数>   出力: results/q295_purchase_guards_mult.csv"""
import os, sys
_ARGV = list(sys.argv); HERE = os.path.dirname(os.path.abspath(__file__))
_s = open(os.path.join(HERE, "q291_purchase_mc_with_current_guards.py"), encoding="utf-8").read().split('\nif __name__ == "__main__":')[0]
_old = "ret = np.clip(np.where(funded, (cfm[:, t] * sh + cfo[:, t]) * f, cem[:, t] * sh + ceo[:, t]), -dll, None)"; assert _s.count(_old) == 1
_s = _s.replace(_old, "raw = np.where(funded, (cfm[:, t] * sh + cfo[:, t]) * f, cem[:, t] * sh + ceo[:, t]); ret = np.where(raw < -dll, -dll * GS['x'], raw)")
q = {"__name__": "q291_head", "__file__": os.path.join(HERE, "q291_purchase_mc_with_current_guards.py"), "GS": {"x": 1.0}}; sys.argv = sys.argv[:1]; exec(compile(_s, "q291_head", "exec"), q)
np, pd, simulate3, CANDS, FX, PC, GS = (q[k] for k in ("np", "pd", "simulate3", "CANDS", "FX", "PC", "GS"))
MULTS = (3.3, 4.5, 6.0, 7.5); TOP_NET, TOP_FAIL = 176.2, 16.2
def sim(c, m, G, shrink, n_acc, fee):
    c2 = dict(c, eval={"mon4": m}, funded={"mon4": m}); out = {}
    for tag, x in (("", 1.0), ("_s11", 1.1)):
        GS["x"] = x; r = simulate3(c2, G, shrink, PC, None); out[f"reach{tag}"] = round(r["reach"], 1); out[f"fail{tag}"] = round(r["fail"], 1); out[f"net36{tag}"] = round(r["pay36"] * n_acc - fee, 1)
        if tag == "": out.update(fail_eval=round(r["fail_eval"], 1), fail_funded=round(r["fail_funded"], 1), reach_med_days=r["reach_med_days"], steady_m=round(r["steady_m"] * n_acc, 1))
    GS["x"] = 1.0; return out
def verdict(b, r): return "改善" if (r["net36"] >= b["net36"] and r["fail"] <= b["fail"] + 1.0 and (r["net36"] >= 1.1 * b["net36"] or r["fail"] <= b["fail"] - 3.0)) else ("悪化" if (r["net36"] < 0.9 * b["net36"] or r["fail"] > b["fail"] + 3.0) else "差なし")
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 12; rows = []; ref = pd.read_csv("results/q291_purchase_mc_guards.csv")
    for nm, c, fee_usd, n_acc, note in CANDS:
        if not (nm.startswith("The5ers High Stakes 100k + Mon4") or nm.startswith("FN Stellar")): continue
        assert set(c["eval"]) == {"mon4"} and abs(c["eval"]["mon4"] - 3.3) < 1e-9; fee = fee_usd * FX * n_acc / 1e4; b = sim(c, 3.3, "G0", False, n_acc, fee); y = ref[(ref.cand == nm) & (ref.form == "G0")].iloc[0]; assert abs(b["net36"] - y.net36) < 0.11 and abs(b["fail"] - y.fail) < 0.11, (b, y.net36, y.fail)
        rows.append(dict(cand=nm, form="G0", mult=3.3, cells=0, verdict="基準", **b))
        for G in ("G2", "G3"):
            for m in MULTS:
                r = sim(c, m, G, True, n_acc, fee)
                if m == 3.3: y = ref[(ref.cand == nm) & (ref.form == G)].iloc[0]; assert abs(r["net36"] - y.net36) < 0.11 and abs(r["fail"] - y.fail) < 0.11, (r, y.net36, y.fail)
                rows.append(dict(cand=nm, form=G, mult=m, cells=0 if m == 3.3 else 1, verdict=verdict(b, r) + ("(Q291 の行)" if m == 3.3 else ""), **r)); print("done", nm[:28], G, m, r, flush=True)
    D = pd.DataFrame(rows); D.to_csv("results/q295_purchase_guards_mult.csv", index=False); assert int(D.cells.sum()) == N
    pd.set_option("display.width", 330); pd.set_option("display.max_rows", 200); pd.set_option("display.max_colwidth", 40)
    print(f"\n== Q295(累積セル {cum} + {N} = {cum + N}・到達 % / 失格 % / 36 か月の純益(万円)。*_s11 = 日次ガードの発動時の損失を幅 × 1.1 にした参照) =="); print(D[["cand", "form", "mult", "reach", "fail", "fail_eval", "fail_funded", "reach_med_days", "net36", "steady_m", "reach_s11", "fail_s11", "net36_s11", "verdict"]].to_string(index=False))
    print("\n候補ごとのまとめ(改善の型の中で純益最大):")
    for nm in D.cand.unique():
        x = D[(D.cand == nm) & (D.cells == 1) & (D.verdict == "改善")].sort_values("net36", ascending=False); b = D[(D.cand == nm) & (D.form == "G0")].iloc[0]
        if len(x) == 0: print(f"  {nm[:40]}: 改善の型なし(基準 純益 {b.net36} 万・失格 {b.fail}%)"); continue
        t = x.iloc[0]; print(f"  {nm[:40]}: {t.form} × {t.mult} 倍・純益 {t.net36} 万・到達 {t.reach}% / 失格 {t.fail}%(基準 {b.net36} 万・{b.fail}%。参照 ×1.1: 純益 {t.net36_s11} 万・失格 {t.fail_s11}%)→ 首位(A 案 {TOP_NET} 万・失格 {TOP_FAIL}%)に対して {'替わる' if (t.net36 > TOP_NET and t.fail <= TOP_FAIL + 1.0) else '替わらない'}")
    print(f"\nセルの判定: 改善 {int(((D.verdict == '改善') & (D.cells == 1)).sum())}・差なし {int(((D.verdict == '差なし') & (D.cells == 1)).sum())}・悪化 {int(((D.verdict == '悪化') & (D.cells == 1)).sum())} / {N}")
