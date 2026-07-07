# -*- coding: utf-8 -*-
"""
policy_dynmult_pd.py — docs/121(事前登録)の実行: 到達率連動の動的倍率ポリシー比較。
  P0固定 / P1クッション比例 / P1d防御のみ / P1u増しのみ / P2段階
判定: PD日次1x合成(2016-2025) × FN Stellar P1(+8%/−10%/日次2バウンド・時間無制限[36M上限])。
経路: 歴史120本(各月開始) + ブロックブートストラップ(3ヶ月×2000, seed=7)。
⚠ 事前登録の後に実行。結果はdocs/122へ転記。出力: results/policy_dynmult_pd.json
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
M0_GRID = [2.0, 3.0, 4.0, 5.0, 6.0]
TARGET, FLOOR, DSTOP, GCAP = 8.0, -10.0, -5.0, -4.0   # %(対初期残高)
CAPM = 36 * 21                                          # 36ヶ月上限(時間無制限の近似)
BOOT_N, BLOCK = 2000, 3


def policy_m(pid, m0, g):
    lo, hi = 0.3 * m0, 1.5 * m0
    if pid == "P0":
        return m0
    if pid == "P1":
        return min(hi, max(lo, m0 * (10.0 + g) / 10.0))
    if pid == "P1d":
        return max(lo, m0 * min(1.0, (10.0 + g) / 10.0))
    if pid == "P1u":
        return min(hi, m0 * max(1.0, (10.0 + g) / 10.0))
    if pid == "P2":
        return 0.5 * m0 if g <= -4.0 else (1.5 * m0 if g >= 4.0 else m0)
    raise ValueError(pid)


def run_path(r, pid, m0, guard):
    """r: 1x日次リターン配列(小数)。加算(対初期残高%)。returns (outcome, months)."""
    g = 0.0
    for i in range(min(len(r), CAPM)):
        m = policy_m(pid, m0, g)
        d = r[i] * m * 100.0
        if guard:
            d = max(d, GCAP)
        elif d <= DSTOP:
            return "fail", (i + 1) / 21.0
        g += d
        if g <= FLOOR:
            return "fail", (i + 1) / 21.0
        if g >= TARGET:
            return "pass", (i + 1) / 21.0
    return "open", CAPM / 21.0


def stats(outs):
    n = len(outs)
    pm = sorted(m for o, m in outs if o == "pass")
    return dict(n=n, pass_pct=round(100 * sum(1 for o, _ in outs if o == "pass") / n, 1),
                fail_pct=round(100 * sum(1 for o, _ in outs if o == "fail") / n, 1),
                open_pct=round(100 * sum(1 for o, _ in outs if o == "open") / n, 1),
                med_m=round(float(np.median(pm)), 1) if pm else None,
                p75_m=round(float(np.percentile(pm, 75)), 1) if pm else None)


def main():
    rng = np.random.default_rng(SEED)
    sl = build_daily_sleeves(1.0)
    comp = composite_daily(sl, PD)
    comp = comp[(comp.index.year >= 2016) & (comp.index.year <= 2025)]
    mk = pd.PeriodIndex(comp.index, freq="M")
    months = mk.unique()
    permo = [comp[mk == m].values for m in months]
    r_all = comp.values
    starts = [int(np.searchsorted(comp.index.values, comp[mk == m].index[0].to_datetime64()))
              for m in months]

    # ブートストラップ経路を先に生成(全政策で同一経路=対応比較)
    boot = []
    nm = len(permo)
    for _ in range(BOOT_N):
        seq = []
        while len(seq) < CAPM:
            b = int(rng.integers(0, nm))
            for j in range(BLOCK):
                seq.extend(permo[(b + j) % nm])
        boot.append(np.array(seq[:CAPM]))

    PIDS = ["P0", "P1", "P1d", "P1u", "P2"]
    res = {}
    for pid in PIDS:
        res[pid] = {}
        for m0 in M0_GRID:
            hist_o = [run_path(r_all[s:], pid, m0, guard=True) for s in starts]
            hist_p = [run_path(r_all[s:], pid, m0, guard=False) for s in starts]
            boot_o = [run_path(b, pid, m0, guard=True) for b in boot]
            res[pid][m0] = dict(hist_opt=stats(hist_o), hist_pes=stats(hist_p),
                                boot_opt=stats(boot_o))
        print(pid, {m0: (res[pid][m0]["hist_opt"]["fail_pct"], res[pid][m0]["hist_opt"]["med_m"])
                    for m0 in M0_GRID})

    # 決定規則(docs/121 §3)の機械適用
    verdicts = {}
    for pid in PIDS[1:]:
        dom = imp = 0
        pes_ok = True
        dom_b = 0
        for m0 in M0_GRID:
            a, b = res["P0"][m0]["hist_opt"], res[pid][m0]["hist_opt"]
            if (b["fail_pct"] <= a["fail_pct"] and b["med_m"] is not None and a["med_m"] is not None
                    and b["med_m"] <= a["med_m"]):
                dom += 1
                if (a["fail_pct"] > 0 and b["fail_pct"] <= 0.9 * a["fail_pct"]) or \
                   (b["med_m"] <= a["med_m"] - 0.5):
                    imp += 1
            ap, bp = res["P0"][m0]["hist_pes"], res[pid][m0]["hist_pes"]
            if bp["fail_pct"] > ap["fail_pct"] + 1.0:
                pes_ok = False
            ab, bb = res["P0"][m0]["boot_opt"], res[pid][m0]["boot_opt"]
            if (bb["fail_pct"] <= ab["fail_pct"] and bb["med_m"] is not None and ab["med_m"] is not None
                    and bb["med_m"] <= ab["med_m"]):
                dom_b += 1
        verdicts[pid] = dict(dominate_hist=f"{dom}/5", strict_improve=imp > 0,
                             pes_not_worse=pes_ok, dominate_boot=f"{dom_b}/5",
                             adopted=bool(dom >= 4 and imp > 0 and pes_ok and dom_b >= 4))
        print(pid, verdicts[pid])
    winners = [p for p in verdicts if verdicts[p]["adopted"]]
    if winners:
        best = max(winners, key=lambda p: res["P0"][4.0]["hist_opt"]["fail_pct"]
                   - res[p][4.0]["hist_opt"]["fail_pct"])
        decision = f"{best}採用"
    else:
        decision = "P0維持(固定倍率・現行)"
    print("決定:", decision)

    out = dict(prereg="docs/121", m0_grid=M0_GRID, rules=dict(target=TARGET, floor=FLOOR,
               dstop=DSTOP, gcap=GCAP, cap_months=36),
               results={p: {str(m0): res[p][m0] for m0 in M0_GRID} for p in PIDS},
               verdicts=verdicts, decision=decision)
    path = os.path.join(HERE, "results", "policy_dynmult_pd.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", path)


if __name__ == "__main__":
    main()
