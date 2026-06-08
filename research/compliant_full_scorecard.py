# -*- coding: utf-8 -*-
"""
compliant_full_scorecard.py — 確定スペック(v4:E-Mon 55:45・docs/61)のプロップ総合成績表。

条件: FTMO 2-step（Phase1 +10% / Phase2 +5% / 静的−10% / 時間無制限）。口座 $200,000・分配80%(FTMO基本)。
サイズ(保守-6/中庸-8/攻め-10)別に一括表示:
  バックテスト質: 年率 / p95年maxDD / Sharpe / Calmar / 月勝率
  審査: P1通過% / P1失格% / P1中央月 / 2段(P1→P2)通過% / 2段中央月
  funded後: 年失格% / 手取り(月/年, 生存時) / 期待手取り(失格考慮)
規律: 数字は盛らない。月次解像度=失格は楽観。Yahoo近似=Drive+デモで確定。FTMO分配は90%(スケール)も可。"""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parallel_vs_existing_compare import v4_monthly, emon_monthly, z, metrics
from pstar_challenge_mc import find_scale, simulate, p95_annual_maxdd, block_paths

HERE = os.path.dirname(os.path.abspath(__file__))
ACCOUNT = 200000.0     # FTMO $200k
SPLIT = 0.80           # FTMO基本80%(スケールで90%)
FX = 160.0             # USD/JPY(現値~160)


def compliant_monthly():
    M = pd.DataFrame({"v4full": v4_monthly(), "E-Mon": emon_monthly()}).dropna()
    return (0.55 * z(M["v4full"]) + 0.45 * z(M["E-Mon"])).dropna()


def ann_return(s, scale):
    x = s.values * scale
    return float(np.prod(1 + x) ** (12 / len(x)) - 1)


def annual_fail(s, scale, n=20000, seed=5):
    P = block_paths(s.values * scale, n, 12, seed=seed); f = 0
    for i in range(n):
        eq = np.cumprod(1 + P[i]); dd = (eq - np.maximum.accumulate(eq)) / np.maximum.accumulate(eq)
        if dd.min() <= -0.10: f += 1
    return f / n


def main():
    s = compliant_monthly()
    winrate = round(float((s > 0).mean() * 100), 0)
    print("=" * 100)
    print(f"確定スペック v4:E-Mon=55:45 ─ プロップ総合成績  [FTMO 2-step / $200k / 分配80% / ¥{FX}/$]")
    print(f"  月勝率(素){winrate:.0f}%  ※FTMO Phase1目標+10% / Phase2 +5% / 静的-10% / 時間無制限")
    print("=" * 100)
    hdr = ["サイズ", "年率", "p95DD", "Sharpe", "Calmar", "P1通過", "P1失格", "P1中央", "2段通過", "2段中央", "年失格", "手取/月", "期待手取/年"]
    print("".join(f"{h:>9}" if i else f"{h:<12}" for i, h in enumerate(hdr)))
    out = {}
    for tag, tdd in [("保守 -6%", -6.0), ("中庸 -8%", -8.0), ("攻め -10%", -10.0)]:
        S = find_scale(s, tdd)
        ar = ann_return(s, S); dd = p95_annual_maxdd(s, S)
        mfull = metrics(s * S, 12)
        p1 = simulate(s, S, 0.10); p2 = simulate(s, S, 0.05, seed=23)
        both = round(p1["pass_pct"] / 100 * p2["pass_pct"] / 100 * 100, 1)
        bothm = p1["med_month"] + p2["med_month"]
        af = annual_fail(s, S)
        gross_m = ACCOUNT * ar * SPLIT * FX / 12
        exp_y = ACCOUNT * ar * SPLIT * FX * (1 - af)
        out[tag] = dict(ann=round(ar * 100, 1), p95DD=round(dd, 1), sharpe=mfull["sharpe"], calmar=mfull["calmar"],
                        P1pass=p1["pass_pct"], P1fail=p1["fail_pct"], P1med=p1["med_month"],
                        twopass=both, twomed=bothm, annual_fail=round(af * 100, 1),
                        net_m=round(gross_m), exp_y=round(exp_y))
        row = [tag, f"{ar*100:.1f}%", f"{dd:.1f}", f"{mfull['sharpe']}", f"{mfull['calmar']}",
               f"{p1['pass_pct']}%", f"{p1['fail_pct']}%", f"{p1['med_month']}ヶ月", f"{both}%", f"{bothm}ヶ月",
               f"{af*100:.1f}%", f"¥{round(gross_m):,}", f"¥{round(exp_y):,}"]
        print("".join(f"{c:>9}" if i else f"{c:<12}" for i, c in enumerate(row)))

    print("\n[読み方] 年率/DD/Sharpe/Calmar=バックテスト質。P1=Challenge(+10%)/2段=P1+Verification(+5%)。")
    print("  手取/月=funded生存時($200k×年率×80%×¥160÷12)。期待手取/年=失格(口座喪失)考慮。")
    print("  ※$100k口座は半額・分配90%(FTMOスケール)なら×1.125。超攻めは別途docs/56/60(ガード必須)。")
    print("  ⚠ 月次解像度=失格は楽観。実値はDrive+デモで確定。FTMOニュース2分/指数SHORT禁止は準拠前提(docs/61)。")

    with open(os.path.join(HERE, "results", "compliant_full_scorecard.json"), "w") as fp:
        json.dump(dict(account=ACCOUNT, split=SPLIT, fx=FX, winrate=winrate, rows=out), fp, ensure_ascii=False, indent=2, default=str)
    print("\n保存: research/results/compliant_full_scorecard.json")


if __name__ == "__main__":
    main()
