# -*- coding: utf-8 -*-
"""
policy_ratchet_confirm.py — docs/123(事前登録)の確証ラン:
  A=ベース / B=MCAP(月内-4%停止) / C=RATCHET(+5%ARM後+2%で0.4倍恒久降格) / D=B+C
主判定: 開始点g0=0(全生涯)・m0∈{3,4,5,6}・FN P1(+8%/−10%/日次2バウンド)・歴史120+ブート2000。
参考: g0=+5.04(現在地・採点外)。出力: results/policy_ratchet_confirm.json
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("RG_ALLOW_YAHOO", "0")

from early_profittake_loyo import build_daily_sleeves, PD
from portfolio_daily_compare import composite_daily

SEED = 7
TARGET, FLOOR, DSTOP, GCAP = 8.0, -10.0, -5.0, -4.0
CAPMO, BOOT_N, BLOCK = 36, 2000, 3
M0S = [3.0, 4.0, 5.0, 6.0]
ARM, GIVE, DEESC, MCAP = 5.0, 3.0, 0.4, -4.0


def run(mlist, guard, m0, use_mcap, use_ratchet, g0=0.0):
    g = g0; scale = 1.0; peak = g0; days = 0
    for mo in mlist[:CAPMO]:
        mpnl = 0.0; blocked = False
        for r in mo:
            days += 1
            if blocked:
                continue
            d = r * m0 * scale * 100.0
            if guard:
                d = max(d, GCAP)
            elif d <= DSTOP:
                return "fail", days / 21.0
            g += d; mpnl += d; peak = max(peak, g)
            if g <= FLOOR:
                return "fail", days / 21.0
            if g >= TARGET:
                return "pass", days / 21.0
            if use_mcap and mpnl <= MCAP:
                blocked = True
            if use_ratchet and scale == 1.0 and peak >= ARM and g <= ARM - GIVE:
                scale = DEESC
    return "open", days / 21.0


def st(outs):
    n = len(outs); pm = sorted(x for o, x in outs if o == "pass")
    q = lambda p: round(float(np.percentile(pm, p)), 2) if pm else None
    return dict(pass_pct=round(100 * sum(1 for o, _ in outs if o == "pass") / n, 1),
                fail_pct=round(100 * sum(1 for o, _ in outs if o == "fail") / n, 1),
                open_pct=round(100 * sum(1 for o, _ in outs if o == "open") / n, 1),
                med=q(50), p75=q(75))


def main():
    rng = np.random.default_rng(SEED)
    sl = build_daily_sleeves(1.0)
    comp = composite_daily(sl, PD)
    comp = comp[(comp.index.year >= 2016) & (comp.index.year <= 2025)]
    mk = pd.PeriodIndex(comp.index, freq="M"); months = mk.unique()
    permo = [comp[mk == m].values for m in months]
    hist = [permo[i:] for i in range(len(permo))]
    hist_years = [m.year for m in months]
    boot = []
    for _ in range(BOOT_N):
        seq = []
        while len(seq) < CAPMO:
            b = int(rng.integers(0, len(permo)))
            seq.extend(permo[(b + j) % len(permo)] for j in range(BLOCK))
        boot.append(seq[:CAPMO])

    VAR = {"A": (False, False), "B": (True, False), "C": (False, True), "D": (True, True)}
    res = {}
    fails_by_year = {}
    for v, (um, ur) in VAR.items():
        res[v] = {}
        for m0 in M0S:
            ho = [run(m, True, m0, um, ur) for m in hist]
            hp = [run(m, False, m0, um, ur) for m in hist]
            bo = [run(m, True, m0, um, ur) for m in boot]
            res[v][m0] = dict(hist_opt=st(ho), hist_pes=st(hp), boot_opt=st(bo))
            if v in ("A", "D"):
                fy = {}
                for (o, _), y in zip(ho, hist_years):
                    if o == "fail":
                        fy[y] = fy.get(y, 0) + 1
                fails_by_year.setdefault(v, {})[m0] = fy
        print(v, {m0: (res[v][m0]["hist_opt"]["fail_pct"], res[v][m0]["hist_opt"]["med"]) for m0 in M0S})

    # 参考: 現在地+5.04(採点外)
    ref = {}
    for v, (um, ur) in VAR.items():
        ho = [run(m, True, 5.0, um, ur, g0=5.04) for m in hist]
        ref[v] = st(ho)
    print("参考(g0=+5.04, m0=5):", {v: (ref[v]["fail_pct"], ref[v]["med"]) for v in VAR})

    # 決定規則(docs/123 §3)
    c1 = all(res["D"][m0][b]["fail_pct"] <= res["A"][m0][b]["fail_pct"]
             for m0 in M0S for b in ("hist_opt", "hist_pes"))
    c2 = sum(1 for m0 in M0S
             if res["D"][m0]["hist_opt"]["fail_pct"] <= 0.75 * res["A"][m0]["hist_opt"]["fail_pct"]) >= 3
    c3 = all(res["D"][m0]["hist_opt"]["med"] is not None and res["A"][m0]["hist_opt"]["med"] is not None
             and res["D"][m0]["hist_opt"]["med"] <= 1.4 * res["A"][m0]["hist_opt"]["med"] for m0 in M0S)
    c4 = sum(1 for m0 in M0S
             if res["D"][m0]["boot_opt"]["fail_pct"] <= 0.75 * res["A"][m0]["boot_opt"]["fail_pct"]) >= 3
    # 開始年頑健性: 各m0で D≤A の年数を数え、最小のm0でも8/10 か
    yr_ok_min = 99
    yr_detail = {}
    for m0 in M0S:
        fa = fails_by_year["A"][m0]; fd = fails_by_year["D"][m0]
        ok = sum(1 for y in range(2016, 2026) if fd.get(y, 0) <= fa.get(y, 0))
        yr_detail[m0] = ok
        yr_ok_min = min(yr_ok_min, ok)
    c5 = yr_ok_min >= 8
    checks = dict(c1_no_worse=bool(c1), c2_rel25_hist=bool(c2), c3_speed=bool(c3),
                  c4_rel25_boot=bool(c4), c5_startyear=bool(c5), startyear_ok=yr_detail)
    decision = "D採用(RATCHET+MCAP)" if all([c1, c2, c3, c4, c5]) else \
        f"見送り(不合格: {[k for k, v in checks.items() if isinstance(v, bool) and not v]})"
    print("checks:", checks)
    print("決定:", decision)

    out = dict(prereg="docs/123", spec=dict(ARM=ARM, GIVE=GIVE, DEESC=DEESC, MCAP=MCAP),
               m0_grid=M0S, results={v: {str(m0): res[v][m0] for m0 in M0S} for v in VAR},
               ref_from_current=ref, checks=checks, decision=decision)
    path = os.path.join(HERE, "results", "policy_ratchet_confirm.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", path)


if __name__ == "__main__":
    main()
