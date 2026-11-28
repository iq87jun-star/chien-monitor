# -*- coding: utf-8 -*-
"""docs/244 Q192(診断・セル 0・2026-11-13 登録「登録して実行」): 事前の情報で建てる数量を変える。
(A) 損失枠の残りに比例: 週の頭に s = clamp((c − floor)/mdd, smin, 1) を月曜レグ全体に掛ける(smin 0.25 / 0.5)。
    s は 0.25〜1.0 の 0.125 刻み 7 段階に丸め、段階ごとに Q188 の H1 経路モデルで月曜の損益・ガード発動・経路の最高値を事前計算する。
(B・参考) SKEW 分位 p で円クロスの数量を段階的に: p ≤ 0.6 → 1.0、0.6 < p ≤ 0.8 → 0.5、p > 0.8 → 0。判定なし(段階は分位別平均を見た後に決めた)。
現行 = 2026-11-13 の配備(宝くじ 8 倍、宝くじ・1-Step・14074882 は SKEW 見送り込み)。
使い方: cd research && python3 -W ignore queue/q192_prior_info_sizing.py   出力: results/q192_prior_info_sizing.csv・_skew.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
src = open(os.path.join(HERE, "q188_skew_gate_guard_model.py"), encoding="utf-8").read().split('if __name__ == "__main__":')[0]
ns = {"__name__": "q188_head", "__file__": os.path.join(HERE, "q188_skew_gate_guard_model.py")}; exec(compile(src, "q188_head", "exec"), ns)
cfg, paths, run_guard, account_items, scenes, acc_id, skew_gate_dates, VALIDATED = (ns[k] for k in ("cfg", "paths", "run_guard", "account_items", "scenes", "acc_id", "skew_gate_dates", "VALIDATED"))
N, WEEKS = 20000, 52; GRID = np.array([0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0]); SKEW_ON = {"531343523", "531466484", "14074882"}
PR = skew_gate_dates()
def tables(items, cap, g, fx_fn):
    """数量段階ごとの (pnl, fired, peak)。fx_fn(dates) → {date: 円クロスの倍率}(None なら無し)。戻り値 {tag: (pnl[G,n], fired[G,n], peak[G,n])}"""
    out = {"lo": [], "cl": []}
    for s in GRID:
        it = [(sym, idx, w * s) for sym, idx, w in items]; P = paths(it, cap)
        if fx_fn is not None: P = paths(it, cap, fx_fn([p["d"] for p in P]))
        R = run_guard(P, g)
        for tag in ("lo", "cl"): out[tag].append(R[tag][:3])
    return {tag: tuple(np.array([x[i] for x in out[tag]]) for i in range(3)) for tag in out}
def skew_factor(dates, sched):
    pr = PR.reindex(pd.DatetimeIndex(dates) - pd.Timedelta(days=3), method="ffill").values; return {d: sched(p) for d, p in zip(dates, pr) if not np.isnan(p) and sched(p) != 1.0}
SK_SKIP = lambda p: 0.0 if p > 0.8 else 1.0
SK_GRADE = lambda p: 0.0 if p > 0.8 else (0.5 if p > 0.6 else 1.0)
def mc_state(T, start, target, floor, mdd, smin, seed=187):
    """状態に応じて数量段階を選ぶ MC。smin=None なら固定 1.0。"""
    pnl, fired, peak = T; n = pnl.shape[1]; rng = np.random.default_rng(seed)
    c = np.full(N, start); alive = np.ones(N, bool); res = np.zeros(N, int); wk = np.zeros(N, int); fires = np.zeros(N, int); ssum = np.zeros(N); scnt = np.zeros(N)
    for w in range(WEEKS):
        if w % 4 == 0: fires[:] = 0
        idx = rng.integers(0, n, N)
        if smin is None: gi = np.full(N, len(GRID) - 1)
        else: s = np.clip((c - floor) / mdd, smin, 1.0); gi = np.abs(GRID[None, :] - s[:, None]).argmin(axis=1)
        act = alive & (fires < 2); x = np.where(act, pnl[gi, idx], 0.0); pk = np.where(act, peak[gi, idx], -1.0); f = np.where(act, fired[gi, idx], 0)
        ssum += np.where(act, GRID[gi], 0.0); scnt += act
        hit = alive & ((c + pk >= target) | (c + x >= target)); c = c + x; fires += f
        res[hit] = 1; wk[hit] = w + 1; alive &= ~hit
        dead = alive & (c <= floor); res[dead] = 2; alive &= ~dead
    ok = res == 1
    return dict(reach=round(float(ok.mean()) * 100, 1), fail=round(float((res == 2).mean()) * 100, 1), weeks=(int(np.median(wk[ok])) if ok.any() else None), reach8w=round(float((ok & (wk <= 8)).mean()) * 100, 1), mean_size=round(float((ssum / np.maximum(scnt, 1)).mean()), 2))
rowsA, rowsB = [], []
for a in cfg["accounts"]:
    aid, items, cap, g = account_items(a)
    if not items or not (a.get("targets") or []): continue
    mdd = float(a["mdd"]); cur_fx = (lambda ds: skew_factor(ds, SK_SKIP)) if aid in SKEW_ON else None
    T = tables(items, cap, g, cur_fx)
    for nm, start, target in scenes(a, aid):
        for lab, smin in (("現行(固定 1.0)", None), ("残りに比例(下限 0.5)", 0.5), ("残りに比例(下限 0.25)", 0.25)):
            row = dict(acct=a["name"][:20], scen=nm, variant=lab, start_pct=round(start * 100, 2), target_pct=round(target * 100, 1), skew_skip=(aid in SKEW_ON))
            for tag in ("lo", "cl"):
                r = mc_state(T[tag], start, target, -mdd, mdd, smin); row.update({f"reach_{tag}": r["reach"], f"fail_{tag}": r["fail"], f"weeks_{tag}": r["weeks"], f"reach8w_{tag}": r["reach8w"], f"size_{tag}": r["mean_size"]})
            rowsA.append(row)
    if aid in VALIDATED:                                         # (B) 参考: SKEW の段階的な数量
        for lab, fn in (("見送りなし", None), ("0.8 超のみ見送り", lambda ds: skew_factor(ds, SK_SKIP)), ("段階(0.6〜0.8 は半分・0.8 超は見送り)", lambda ds: skew_factor(ds, SK_GRADE))):
            it = [(sym, idx, w) for sym, idx, w in items]; P = paths(it, cap) if fn is None else paths(it, cap, fn([p["d"] for p in paths(it, cap)])); R = run_guard(P, g)
            for nm, start, target in scenes(a, aid):
                row = dict(acct=a["name"][:20], scen=nm, variant=lab, deployed=bool((lab == "0.8 超のみ見送り") == (aid in SKEW_ON) and lab != "段階(0.6〜0.8 は半分・0.8 超は見送り)"))
                for tag in ("lo", "cl"):
                    T1 = tuple(x[None, :] for x in R[tag][:3]); G0 = GRID; GRID = np.array([1.0]); r = mc_state(T1, start, target, -mdd, mdd, None); GRID = G0
                    row.update({f"mean_bps_{tag}": round(float(R[tag][0].mean()) * 1e4, 1), f"hits_{tag}": int(R[tag][1].sum()), f"reach_{tag}": r["reach"], f"fail_{tag}": r["fail"], f"weeks_{tag}": r["weeks"]})
                rowsB.append(row)
A = pd.DataFrame(rowsA); A.to_csv("results/q192_prior_info_sizing.csv", index=False); B = pd.DataFrame(rowsB); B.to_csv("results/q192_prior_info_sizing_skew.csv", index=False)
picks = []
for (acct, sc), g_ in A.groupby(["acct", "scen"], sort=False):
    cur = g_[g_.variant.str.startswith("現行")].iloc[0]; c = g_[(~g_.variant.str.startswith("現行")) & (g_.reach_lo >= cur.reach_lo + 2) & (g_.reach_cl >= cur.reach_cl + 2) & (g_.weeks_lo <= 1.5 * cur.weeks_lo)]
    best = c.sort_values("reach_lo", ascending=False).iloc[0] if len(c) else None
    picks.append(dict(acct=acct, scen=sc, verdict=("変更候補" if best is not None else "現行維持"), variant=(best.variant if best is not None else "—")))
pd.set_option("display.width", 320); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 300)
print(pd.DataFrame(picks).to_string(index=False)); print()
print(A[["acct", "scen", "variant", "reach_lo", "reach_cl", "fail_lo", "fail_cl", "weeks_lo", "reach8w_lo", "size_lo"]].to_string(index=False)); print()
print(B[["acct", "scen", "variant", "deployed", "mean_bps_lo", "hits_lo", "mean_bps_cl", "reach_lo", "reach_cl", "fail_lo", "fail_cl", "weeks_lo"]].to_string(index=False))
