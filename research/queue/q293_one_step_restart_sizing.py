# -*- coding: utf-8 -*-
"""docs/244 Q293(2026-11-27 登録「登録実行」・毎日の作案 I-6・セル 14): 1-Step の 12 月の再開をどの数量で始めるか。
枠組みは Q271(docs/511)と同じ(過去の各週から 52 週の再現・追随型の失格線・EA の全停止 = 失格線 + 1%・1 日リスク上限 2.5%・SKEW・金の保有込み)。
開始: 残高 95,432(−4.57%)・最高 102,813.25・建玉なし・11 月は発動 3 回(11/30 の月曜は建てない・金は 12/1 に建て直す)。
型: 月曜の数量 {満額 / 余裕比例・下限 0.75 / 0.5 / 0.25} × 金 {そのまま 0.36 倍 / 金なし}。基準 = 満額・金そのまま。金の場面 = 実績のまま・横ばい。
判定: ev_ok →「変更候補」/ 2 期間のどこかで 到達 −1 超 or 失格 +1 超 →「悪化」/ それ以外「差なし」。選び方: 2 場面とも変更候補の型の中で(到達 − 失格)の合計が最大。無ければいまの設定のまま再開。
使い方: cd research && python3 -W ignore queue/q293_one_step_restart_sizing.py <累積セル数>   出力: results/q293_one_step_restart.csv"""
import os, sys
_ARGV = list(sys.argv); HERE = os.path.dirname(os.path.abspath(__file__))
_s = open(os.path.join(HERE, "q271_one_step_gold_from_current_state.py"), encoding="utf-8").read().split('if __name__ == "__main__":')[0]
q = {"__name__": "q271_head", "__file__": os.path.join(HERE, "q271_one_step_gold_from_current_state.py")}; sys.argv = sys.argv[:1]; exec(compile(_s, "q271_head", "exec"), q)
np, pd, n5, setup, scenario, STARTS, items, cap, g, mm, fac, LV, MODE, mon_levels, GA, gold_arrays, ev_ok, WG, SWM = (q[k] for k in ("np", "pd", "n5", "setup", "scenario", "STARTS", "items", "cap", "g", "mm", "fac", "LV", "MODE", "mon_levels", "GA", "gold_arrays", "ev_ok", "WG", "SWM")); episode = n5["episode"]
def mkf(t0): t0 = pd.Timestamp(t0); return np.array([[(t0 + pd.Timedelta(days=7 * j + i)).year * 100 + (t0 + pd.Timedelta(days=7 * j + i)).month for i in range(5)] for j in range(53)])
START = 95432.0 / 1e5 - 1; HWM = 102813.25 / 1e5 - 1
def one(ML, start, smin, w0, wr):
    kw = dict(start=start, target=0.10, mdd=0.10, pad=0.01, smin=smin, trail=True, g=g, swm=SWM, wg0=w0, carry0=0.0, wg_re=wr, integ=True); r = {}
    for wn in ("W1", "W2"):
        o = {}
        for tag in ("lo", "cl"):
            st = dict(room=[], fires=[], weeks=0, sl=0); res = [episode(ML, tag, s, kind="A", st=st, **kw) for s in STARTS[wn]]; rr = np.array([x[0] for x in res]); wk = np.array([x[1] for x in res])
            o[tag] = dict(reach=float((rr == 1).mean()) * 100, fail=float((rr == 2).mean()) * 100, weeks=(int(np.median(wk[rr == 1])) if (rr == 1).any() else 0), fail8=float(((rr == 2) & (wk <= 8)).mean()) * 100, fires=len(st["fires"]) / max(st["weeks"], 1) * 52)
        r[f"reach_{wn}"] = round(min(o[t]["reach"] for t in o), 1); r[f"fail_{wn}"] = round(max(o[t]["fail"] for t in o), 1); r[f"weeks_{wn}"] = max(o[t]["weeks"] for t in o); r[f"fail8_{wn}"] = round(max(o[t]["fail8"] for t in o), 1); r[f"fires_{wn}"] = round(max(o[t]["fires"] for t in o), 2)
    r["n_W1"] = len(STARTS["W1"]); r["n_W2"] = len(STARTS["W2"]); return r
def worse(b, v): return bool(any(v[f"reach_{w}"] < b[f"reach_{w}"] - 1.0 or v[f"fail_{w}"] > b[f"fail_{w}"] + 1.0 for w in ("W1", "W2")))
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 14; rows = []
    MODE["k"] = None; MLA = mon_levels(items, cap, fac, mm, list(range(len(LV)))); TOP = len(LV) - 1; MLF = {li: MLA[TOP] for li in range(len(LV))}; print("levels built", flush=True)
    # 照合: Q271 の設定(開始 97,826.72・発動 2 回・11/23 の週から・満額・金 0.36)
    n5["DG"] = scenario(None); GA["A"] = gold_arrays("A"); q["MKF"] = mkf("2026-11-23"); setup(HWM, 2, 3, True); chk = one(MLF, 97826.72 / 1e5 - 1, None, WG, WG)
    ref = pd.read_csv("results/q271_one_step_gold.csv"); ref = ref[(ref.part == "判定") & (ref.scenario == "実績のまま") & ref.variant.str.startswith("現状")].iloc[0]
    print("照合:", (chk["reach_W1"], chk["fail_W1"], chk["reach_W2"], chk["fail_W2"]), "docs/511:", (ref.reach_W1, ref.fail_W1, ref.reach_W2, ref.fail_W2), flush=True)
    assert abs(chk["reach_W1"] - ref.reach_W1) < 0.11 and abs(chk["fail_W1"] - ref.fail_W1) < 0.11 and abs(chk["reach_W2"] - ref.reach_W2) < 0.11 and abs(chk["fail_W2"] - ref.fail_W2) < 0.11
    q["MKF"] = mkf("2026-11-30"); SIZES = [("満額", None), ("余裕比例・下限 0.75", 0.75), ("余裕比例・下限 0.5", 0.5), ("余裕比例・下限 0.25", 0.25)]; GOLD = [("金そのまま(0.36 倍)", WG), ("金なし", 0.0)]
    for sn, dr in (("実績のまま", None), ("横ばい(年率 0%)", 0.0)):
        n5["DG"] = scenario(dr); GA["A"] = gold_arrays("A"); setup(HWM, 3, 3, True); b = None
        for gn, w in GOLD:
            for zn, smin in SIZES:
                r = one(MLF if smin is None else MLA, START, smin, w, w); isb = (smin is None and w == WG)
                if isb: b = r
                rows.append(dict(scenario=sn, gold=gn, size=zn, cells=0 if isb else 1, verdict="基準" if isb else ("変更候補" if ev_ok(b, r) else ("悪化" if worse(b, r) else "差なし")), net=round(r["reach_W1"] - r["fail_W1"] + r["reach_W2"] - r["fail_W2"], 1), **r)); print("done", sn, gn, zn, r, flush=True)
    D = pd.DataFrame(rows); D.to_csv("results/q293_one_step_restart.csv", index=False); assert int(D.cells.sum()) == N
    pd.set_option("display.width", 320); pd.set_option("display.max_rows", 200); pd.set_option("display.max_columns", 40)
    print(f"\n== Q293(累積セル {cum} + {N} = {cum + N}・開始 {START * 100:+.2f}%・最高 {HWM * 100:+.2f}%・全停止 {(HWM - 0.09) * 100:+.2f}%・g {g * 100:.1f}%・到達 % / 失格 % / 中央の週数 / 8 週以内の全停止 % / 年の発動回数) =="); print(D[["scenario", "gold", "size", "reach_W1", "fail_W1", "weeks_W1", "fail8_W1", "fires_W1", "reach_W2", "fail_W2", "weeks_W2", "fail8_W2", "fires_W2", "net", "verdict"]].to_string(index=False))
    print("\n選び方(2 つの金の場面の両方で変更候補の型・net の 2 場面合計):"); ok = []
    for (gn, zn), x in D[D.cells == 1].groupby(["gold", "size"], sort=False):
        if (x.verdict == "変更候補").all(): ok.append((round(float(x.net.sum()), 1), gn, zn))
    print("  基準の net 合計:", round(float(D[D.cells == 0].net.sum()), 1), "| 該当:", sorted(ok, reverse=True) if ok else "なし → いまの設定のまま再開")
    print(f"\nセルの判定: 変更候補 {int((D.verdict == '変更候補').sum())}・差なし {int((D.verdict == '差なし').sum())}・悪化 {int((D.verdict == '悪化').sum())} / {N}")
