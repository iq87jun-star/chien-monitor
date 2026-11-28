# -*- coding: utf-8 -*-
"""docs/322 Q105(診断・セル 0): P2 のロック値(InpLockArmPct = 新規停止 / InpLockClosePct = 全決済ロック)の格子。
EA の実装(RecentFit 系共通): gain ≥ Close で全決済・恒久ロック(通過)。gain ≥ Arm で新規停止(Arm は毎 tick 再評価 = gain が Arm を割れば再開)。
→ 建玉が無い状態で gain が [Arm, Close) に着地すると、新規が建たず equity も動かないので**通過も再開もしない(手動介入待ち = 「滞留」)**。
MC は Q85 と同じ(研究系列 2021-10〜2026-08・5 日ブロック・5,000 本 × 250 営業日・日次ガードは下限クリップ・床は EA の全停止線)。
帳簿はレグを「イベント型(Mon/Roll/ブレイク/v4: 建てて閉じる → 閉じた後は建玉なし)」と「連続型(Hold: 常に建玉あり)」に分け、
Armed の日はイベント型の新規を 0 にし連続型だけ動かす。滞留 = 250 日後に通過も失格もせず Armed のまま(連続型が無い帳簿)。
格子: ロック幅 c = Close − 目標 ∈ {0.02,0.05,0.10,0.20,0.30}pp × アーム幅 g = Close − Arm ∈ {0,0.05,0.15,0.30,0.50}pp(現行 c 0.05 / g 0.15)。
出力: results/q105_p2_lock_grid.csv。配備・EA・manifest は変更しない。"""
import os, sys, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT); sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
src = open("logic_5y_scorecard.py", encoding="utf-8").read().split("rows = []")[0]
ns = {"__name__": "l5", "__file__": os.path.join(ROOT, "logic_5y_scorecard.py")}; exec(compile(src, "l5", "exec"), ns)
on_bd = ns["on_bd"]; wsum = ns["wsum"]; base = ns["base"]; db = ns["db"]; roll = ns["roll"]; mon4 = ns["mon4"]; L = ns["L"]
try:
    q = open("queue/q52_donchian_vs_hold.py", encoding="utf-8").read().split("cum = int(sys.argv[1])")[0]
    qn = {"__name__": "q52"}; exec(compile(q, "q52", "exec"), qn); brk = on_bd(qn["donchian"]("GER40", 120, "trail"))
except Exception as e: print("GER40 ブレイク無し:", e); brk = mon4 * 0
hold_xau = on_bd(db.leg_series("Hold", "XAUUSD")); idx = on_bd(base.mon_cell("NAS100")) + on_bd(base.mon_cell("US500")); ger = on_bd(base.mon_cell("GER40"))
pearl = L["B案 RecentFit ×4.0(Fintokei パール)"] / 4.0
mon2 = on_bd(wsum([(db.leg_series("Mon", "CADJPY"), .5), (db.leg_series("Mon", "CHFJPY"), .5)]))
W0, W1 = pd.Timestamp("2021-10-01"), pd.Timestamp("2026-08-31")
def win(s): return s[(s.index >= W0) & (s.index <= W1)]
BOOKS = {  # name: (event series, continuous series, target, EA daily guard, EA floor)
 "トパーズ P2(Mon4 ×8 + 指数 Mon 1.0・目標 6%)": (win(mon4 * 8 + idx * 1.0), None, 0.06, 0.04, 0.09),
 "ルビー P2(B案 ×12・目標 6%)": (win(pearl * 12), None, 0.06, 0.04, 0.09),
 "FN 14166201 P2(C6 ×3.0・目標 5%)": (win((mon2 + ger * 0.5 + roll * 1.0) * 3.0), None, 0.05, 0.03, 0.09),
 "FTMO 531343523 P2(EA10L: Mon4 ×10 + ブレイク ×6 + Hold XAU 0.9・目標 5%)": (win(mon4 * 10 + brk * 6), win(hold_xau * 0.9), 0.05, 0.04, 0.095),
 "参考: トパーズ P1(目標 8%・現行 7.9/8.05)": (win(mon4 * 8 + idx * 1.0), None, 0.08, 0.04, 0.09),
 "参考: ルビー P1(目標 8%・現行 7.9/8.05)": (win(pearl * 12), None, 0.08, 0.04, 0.09),
}
C_OFF = [0.0002, 0.0005, 0.0010, 0.0020, 0.0030]; G_OFF = [0.0, 0.0005, 0.0015, 0.0030, 0.0050]
N = 5000; BLOCK = 5; DAYS = 250
def paths(s, rng):
    r = np.asarray(s.values, float); nb = len(r) - BLOCK + 1
    st = rng.integers(0, nb, size=(N, DAYS // BLOCK + 1)); return st
def run(ev, co, target, guard, floor, c, g):
    rng = np.random.default_rng(105)   # 同じ乱数で格子を比べる
    re_ = np.asarray(ev.values, float); rc = np.asarray(co.reindex(ev.index).fillna(0.0).values, float) if co is not None else np.zeros_like(re_)
    st = paths(ev, rng); ix = (st[:, :, None] + np.arange(BLOCK)[None, None, :]).reshape(N, -1)[:, :DAYS]
    E, Cn = re_[ix], rc[ix]
    e = np.ones(N); armed = np.zeros(N, bool); passed = np.zeros(N, bool); failed = np.zeros(N, bool); tpass = np.full(N, 10**6)
    close_lv, arm_lv = 1 + target + c, 1 + target + c - g
    for t in range(DAYS):
        live = ~passed & ~failed
        r = np.where(armed, Cn[:, t], E[:, t] + Cn[:, t]); r = np.clip(r, -guard, None)
        e = np.where(live, e * (1 + r), e)
        nf = live & (e <= 1 - floor); failed |= nf
        npass = live & ~nf & (e >= close_lv); passed |= npass; tpass[npass] = t + 1
        armed = live & ~passed & ~failed & (e >= arm_lv)
    has_cont = co is not None and float(np.abs(rc).sum()) > 0
    stuck = (~passed & ~failed & armed) if not has_cont else np.zeros(N, bool)
    med = int(np.median(tpass[passed])) if passed.any() else None
    return passed.mean(), failed.mean(), stuck.mean(), med
rows = []
for name, (ev, co, target, guard, floor) in BOOKS.items():
    for c in C_OFF:
        for g in G_OFF:
            p, f, s_, med = run(ev, co, target, guard, floor, c, g)
            rows.append(dict(book=name, target=target * 100, close=round((target + c) * 100, 2), arm=round((target + c - g) * 100, 2), c_pp=round(c * 100, 2), g_pp=round(g * 100, 2),
                             reach=round(p * 100, 1), fail=round(f * 100, 1), stuck=round(s_ * 100, 1), median_days=med, current=(abs(c - 0.0005) < 1e-9 and abs(g - 0.0015) < 1e-9)))
    d = pd.DataFrame([r for r in rows if r["book"] == name])
    cur = d[d.current].iloc[0]; best = d.sort_values(["reach", "stuck"], ascending=[False, True]).iloc[0]; g0 = d[(d.g_pp == 0) & (d.c_pp == 0.05)].iloc[0]
    print(f"\n== {name}")
    print(f"  現行 Close {cur.close} / Arm {cur.arm}: 到達 {cur.reach} 失格 {cur.fail} 滞留 {cur.stuck} 中央 {cur.median_days} 日")
    print(f"  Arm=Close(g=0, c=0.05): 到達 {g0.reach} 失格 {g0.fail} 滞留 {g0.stuck} 中央 {g0.median_days} 日")
    print(f"  最良 Close {best.close} / Arm {best.arm}: 到達 {best.reach} 失格 {best.fail} 滞留 {best.stuck}")
    print("  アーム幅 g 別(c=0.05): " + " | ".join(f"g {r.g_pp}: 到達 {r.reach} 滞留 {r.stuck}" for r in d[d.c_pp == 0.05].itertuples()))
    print("  ロック幅 c 別(g=0): " + " | ".join(f"c {r.c_pp}: 到達 {r.reach} 失格 {r.fail}" for r in d[d.g_pp == 0].itertuples()))
pd.DataFrame(rows).to_csv("results/q105_p2_lock_grid.csv", index=False); print("\nsaved results/q105_p2_lock_grid.csv", len(rows))
