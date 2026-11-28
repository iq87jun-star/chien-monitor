# -*- coding: utf-8 -*-
"""docs/244 Q271(2026-11-20 登録「登録して実行」・セル 6): 1-Step の金の保有を、いまの状態から計算し直す。
ユーザー 2026-11-20「1ステップの金は外せますか」。1-Step は 11/16 と 11/20 に日次ガードが発動(今月 2 回・2 回目は金の含み損だけで到達)。
Q253・Q254 は 1 回目の直後(残高 +0.2%・発動 0 回から)の計算で「金を残す」だった。判定の型と基準は docs/244 に先に固定した。
開始: 残高 97,826.72(−2.17%)・金の建玉なし・EOD の最高 102,813.25(追随の床 = 最高 − 10%・全停止は床 + 1%)・11 月の発動 2 回。
型: 現状 = 週明けに金 0.36 倍を建て直す(判定の基準)/ 金なし / 建て直しを半分(0.18 倍)。
場面(Q254 と同じ作り方): 実績のまま・横ばい(年率 0%)・下落(年率 −6%)。参照(判定しない): 急落(年率 −20%)・月内の停止を旧い約束(2 回で停止)にした場合。
Q253 の episode からの変更(文字列の置き換えで作る・q253 のファイルは変更しない):
  (1) 開始時の最高値 HWM0 (2) 開始月の発動回数 MF0 (3) 月の区切り = これからの暦(2026-11-23 の週から)(4) 月内の停止 = EA の実装どおり 3 回目(g_balFires > InpBalGuardMaxMonth)。
照合: 旧設定(開始 100,225.64・HWM0 0・MF0 0・過去の暦・2 回で停止)で Q254 の 1-Step の行(100 / 0・36 / 30、金なし 81 / 0・35 / 35)を再現する。
判定 = Q233 の ev_ok(基準 = その場面の現状)。限界: 夜の指数(v1.10)・11/23 の祝日の見送りは入れない。NAS100 の 1 時間足の欠け。開始週は重なる。
使い方: cd research && python3 -W ignore queue/q271_one_step_gold_from_current_state.py <累積セル数>   出力: results/q271_one_step_gold.csv"""
import os, sys
_ARGV = list(sys.argv)
HERE = os.path.dirname(os.path.abspath(__file__))
_full = open(os.path.join(HERE, "q253_gold_hold_carry_vs_daily_guard.py"), encoding="utf-8").read(); _src = _full.split("# ---------- 口座 ----------")[0]
def _rep(s, old, new): assert s.count(old) == 1, old; return s.replace(old, new)
_src = _rep(_src, "hwm = max(c, 0.0); e = None", "hwm = max(c, 0.0, HWM0); e = None")
_src = _rep(_src, "mkey = None; mf = 0; fresh = True", "mkey = MKEY(s, s, 0); mf = MF0; fresh = True")
_src = _rep(_src, "if MK[w, i] != mkey: mkey = MK[w, i]; mf = 0", "if MKEY(w, s, i) != mkey: mkey = MKEY(w, s, i); mf = 0")
_src = _rep(_src, "halted = mf >= 2; a = 24 * i", "halted = mf >= HALT_AT; a = 24 * i")
n5 = {"__name__": "q253_head", "__file__": os.path.join(HERE, "q253_gold_hold_carry_vs_daily_guard.py"), "HWM0": 0.0, "MF0": 0, "HALT_AT": 2}
n5["MKEY"] = lambda w, s, i: n5["MK"][w, i]                                   # 既定 = 過去の暦(照合用)。exec の前に置く(episode は呼ばれる時に参照する)
exec(compile(_src, "q253_head", "exec"), n5)
np, pd = n5["np"], n5["pd"]; norm_items, account_items, acct, make_fac, MODE, PM, LV, TOP, MONS, W, mon_levels, run, gold_arrays, GA = (n5[k] for k in ("norm_items", "account_items", "acct", "make_fac", "MODE", "PM", "LV", "TOP", "MONS", "W", "mon_levels", "run", "gold_arrays", "GA"))
DG0 = n5["DG"].copy(); P0, P1 = n5["P0"], n5["P1"]
T0 = pd.Timestamp("2026-11-23"); MKF = np.array([[(T0 + pd.Timedelta(days=7 * j + i)).year * 100 + (T0 + pd.Timedelta(days=7 * j + i)).month for i in range(5)] for j in range(53)])
def setup(hwm0, mf0, halt_at, future):
    n5["HWM0"] = hwm0; n5["MF0"] = mf0; n5["HALT_AT"] = halt_at; n5["MKEY"] = (lambda w, s, i: MKF[w - s, i]) if future else (lambda w, s, i: n5["MK"][w, i])
def scenario(drift):
    if drift is None: return DG0.copy()
    D = DG0.copy(); lr = np.log(D["close"]).diff().fillna(0.0); adj = lr.copy()
    for a, b in ((P0 - pd.Timedelta(days=30), PM - pd.Timedelta(days=1)), (PM, P1 + pd.Timedelta(days=7))):
        m = (D.index >= a) & (D.index <= b); adj[m] = lr[m] - lr[m].mean() + drift / 252.0
    c = float(D["close"].iloc[0]) * np.exp(adj.cumsum()); ratio = c / D["close"]; D["close"] = c; D["low"] = DG0["low"] * ratio; D["open"] = DG0["open"] * ratio; D["high"] = DG0["high"] * ratio
    return D
SC = [("実績のまま", None, True), ("横ばい(年率 0%)", 0.0, True), ("下落(年率 −6%)", float(np.log(1 - 0.06)), True), ("参照: 急落(年率 −20%)", float(np.log(1 - 0.20)), False)]
KEY = "531466484"; START = 97826.72 / 1e5 - 1; HWM = 102813.25 / 1e5 - 1; WG = 0.36; SWM = -52.0
okA = ~np.isnan(GA["A"][2]); idx = np.arange(W); STARTS = {"W1": [s for s in idx if MONS[s] >= PM and s + 52 <= W and okA[s]], "W2": [s for s in idx if MONS[s] < PM and s + 52 <= W and MONS[s + 51] < PM and okA[s]]}
items, cap, g = norm_items(KEY); _, it0, _, _ = account_items(acct(KEY)); mm = sum(w for s, i, w in it0 if not i); fac = make_fac(items, True, None)
MODE["k"] = None; ML0 = mon_levels(items, cap, fac, mm, [TOP]); ML = {li: ML0[TOP] for li in range(len(LV))}
def one(start, w0, wr):
    kw = dict(start=start, target=0.10, mdd=0.10, pad=0.01, smin=None, trail=True, g=g, swm=SWM, wg0=w0, carry0=0.0, wg_re=wr, integ=True); r = {}
    for wn in ("W1", "W2"):
        o = run(ML, STARTS[wn], "A", **kw); r[f"reach_{wn}"] = round(min(o[t]["reach"] for t in o), 1); r[f"fail_{wn}"] = round(max(o[t]["fail"] for t in o), 1); r[f"weeks_{wn}"] = max(o[t]["weeks"] for t in o); r[f"fires_{wn}"] = round(max(o[t]["fires_per52"] for t in o), 2); r[f"gold_only_{wn}"] = round(max(o[t]["gold_only"] for t in o), 2)
    return r
def ev_ok(b, v): return bool(all(v[f"reach_{w}"] >= b[f"reach_{w}"] - 1.0 and v[f"fail_{w}"] <= b[f"fail_{w}"] + 1.0 for w in ("W1", "W2")) and any(v[f"reach_{w}"] >= b[f"reach_{w}"] + 2.0 or v[f"fail_{w}"] <= b[f"fail_{w}"] - 2.0 for w in ("W1", "W2")))
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 6; rows = []; V = [("現状(金 0.36 倍で建て直す)", WG, WG), ("金なし", 0.0, 0.0), ("建て直しを半分(0.18 倍)", WG / 2, WG / 2)]
    # 照合: Q254 の 1-Step の行(旧設定)
    setup(0.0, 0, 2, False); n5["DG"] = scenario(None); GA["A"] = gold_arrays("A")
    for vn, w0, wr in (("照合: 現状(Q254 と同じ設定)", WG, WG), ("照合: 金なし(Q254 と同じ設定)", 0.0, 0.0)): rows.append(dict(part="照合", scenario="実績のまま", variant=vn, cells=0, **one(100225.64 / 1e5 - 1, w0, wr)))
    print("照合:", [(r["variant"], r["reach_W1"], r["fail_W1"], r["reach_W2"], r["fail_W2"]) for r in rows], "(期待: 100 / 0・36 / 30、金なし 81 / 0・35 / 35)", flush=True)
    for sn, dr, judged in SC:
        n5["DG"] = scenario(dr); GA["A"] = gold_arrays("A"); c = n5["DG"]["close"]; print(f"[{sn}] 金: 2016-11 {c[:'2016-11-01'].iloc[-1]:.0f} → 2021-07 {c[:'2021-07-31'].iloc[-1]:.0f} → 2026-07 {c[:'2026-07-31'].iloc[-1]:.0f}", flush=True)
        setup(HWM, 2, 3, True)
        for vn, w0, wr in V: rows.append(dict(part="判定" if judged else "参照", scenario=sn, variant=vn, cells=(1 if (judged and w0 != WG) else 0), **one(START, w0, wr)))
        setup(HWM, 2, 2, True)
        for vn, w0, wr in V: rows.append(dict(part="参照(2 回で停止)", scenario=sn, variant=vn, cells=0, **one(START, w0, wr)))
        setup(0.0, 0, 3, True)                                                # 参照: 発動 0 回・最高値なし(状態の変化の寄与を分ける)
        for vn, w0, wr in V[:2]: rows.append(dict(part="参照(発動 0 回・最高値なし)", scenario=sn, variant=vn, cells=0, **one(START, w0, wr)))
    D = pd.DataFrame(rows); D.to_csv("results/q271_one_step_gold.csv", index=False)
    pd.set_option("display.width", 320); pd.set_option("display.max_rows", 400); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 60)
    print(f"\n== Q271(累積セル {cum} + {N} = {cum + N}・開始 {START * 100:+.2f}%・最高 {HWM * 100:+.2f}%・床 {(HWM - 0.10) * 100:+.2f}%・全停止 {(HWM - 0.09) * 100:+.2f}%・g {g * 100:.1f}%) =="); print(D.to_string(index=False))
    assert int(D.cells.sum()) == N, D.cells.sum()
    print("\n== 判定(基準 = その場面の現状) ==")
    for part in ("判定", "参照", "参照(2 回で停止)"):
        for sn, x in D[D.part == part].groupby("scenario", sort=False):
            b = x[x.variant.str.startswith("現状")].iloc[0]
            for _, v in x[x.variant != b.variant].iterrows(): print(f"  [{part}・{sn}] {v.variant} → {'変更候補' if ev_ok(b, v) else '現行どおり'}(到達 {v.reach_W1:.0f} / {v.reach_W2:.0f}% vs {b.reach_W1:.0f} / {b.reach_W2:.0f}%・失格 {v.fail_W1:.0f} / {v.fail_W2:.0f}% vs {b.fail_W1:.0f} / {b.fail_W2:.0f}%・到達までの週 {v.weeks_W1} / {v.weeks_W2} vs {b.weeks_W1} / {b.weeks_W2})")
