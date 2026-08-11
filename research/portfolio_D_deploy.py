# -*- coding: utf-8 -*-
"""
portfolio_D_deploy.py — 推奨ポートフォリオ「分散案D[RG3]」(v4:v7:E-Mon[RG3]:E5 = 30:25:25:20)の
   運用カード数値を一括算出: (1)審査 median-3(標準/高リスク) (2)資金化後 収益 (3)高リスク版。

出所/手法: median3_rg3_target.py(系列・中央値定義) + pstar_funded_income.py(資金化後収益) を流用。
データ: Drive優先(forex_ml/multiasset_daily の指数=docs/68 と同一入力, E-Mon net≈67%)、無ければ固定窓Yahoo。
規律: 数字は盛らない。月次解像度=失格は楽観(日次−5%/月内/ギャップで実際は上振れ)。為替/分配率/口座サイズは可変。
   絶対値は Drive+デモで確定。審査=median-3 は口座喪失前提の攻め、資金化後は生存優先で別サイズ(docs/36/57)。
出力: results/portfolio_D_deploy.json
"""
import os, sys, json, shutil, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
os.environ.setdefault("RG_ALLOW_YAHOO", "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parallel_vs_existing_compare import v7_monthly, v4_monthly, e5_monthly, z
from pstar_challenge_mc import find_scale, simulate, p95_annual_maxdd, block_paths
import edge_regime_gate_10y as RG

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
INDEXES = ["NAS100", "US500", "GER40"]

# --- 資金化後 収益の前提(可変) ---
ACCOUNT_USD = 100000.0      # FN Stellar funded $100k
SPLIT = 0.95                # 分配率(base80% + アドオン15%)
FX = 155.0                  # ¥/$
WEIGHTS = {"v4": .30, "v7": .25, "E-Mon": .25, "E5": .20}   # 分散案D


def resolve_drive_first():
    src = os.path.join(DRIVE_BASE, "multiasset_daily"); got = []
    if os.path.isdir(src):
        os.makedirs(DATA, exist_ok=True)
        for nm in INDEXES:
            s = os.path.join(src, f"{nm}_d.csv")
            if os.path.exists(s):
                shutil.copy(s, os.path.join(DATA, f"{nm}_d.csv")); got.append(nm)
    print(f"[データ] Drive取込={got or 'なし(固定窓Yahoo)'}")
    return got


def to_m(w):
    s = w.copy(); s.index = pd.to_datetime(s.index).to_period("M"); return s.groupby(level=0).sum()


def median_month(s, sc, t):
    return simulate(s, sc, t, n_paths=12000)["med_month"]


def scale_for_median(s, want, t, lo=0.05, hi=12.0):
    for _ in range(28):
        mid = (lo + hi) / 2
        if median_month(s, mid, t) <= want: hi = mid
        else: lo = mid
    return hi


def ann_return(s, sc):
    v = s.values * sc; return float(np.prod(1 + v) ** (12 / len(v)) - 1)


def annual_fail(s, sc, n=20000, ml=0.10, seed=5):
    P = block_paths(s.values * sc, n, 12, seed=seed); f = 0
    for i in range(n):
        eq = np.cumprod(1 + P[i]); ddv = (eq - np.maximum.accumulate(eq)) / np.maximum.accumulate(eq)
        if ddv.min() <= -ml: f += 1
    return f / n


def main():
    drive = resolve_drive_first()
    SRC = {"v7": v7_monthly(), "v4": v4_monthly(), "E5": e5_monthly(),
           "E-Mon": to_m(RG.emon_weekly_gated("riskoff"))}
    M = pd.DataFrame({k: SRC[k] for k in WEIGHTS}).dropna()
    D = sum(z(M[k]) * WEIGHTS[k] for k in WEIGHTS).dropna()
    src_tag = "Drive" if drive else "Yahoo(fixed-window)"
    print(f"分散案D[RG3] (30:25:25:20) n={len(D)}ヶ月 span={D.index.min()}..{D.index.max()} / 入力={src_tag}")

    out = {"data_source": src_tag, "weights": WEIGHTS, "challenge": {}, "funded": {},
           "params": dict(account_usd=ACCOUNT_USD, split=SPLIT, fx=FX)}

    # 【1】審査(Phase1 +8%/−10%): median-3 標準 と 高リスク
    S3 = scale_for_median(D, 3, 0.08)
    print("\n【1】審査 Phase1(+8%/−10%):")
    print(f"{'サイズ':24s}{'p95年DD':>9}{'通過%':>8}{'失格%':>8}{'中央月':>7}")
    for tag, S in [("median-3 標準", S3), ("median-3 ×1.25", S3 * 1.25), ("median-3 ×1.5 高リスク", S3 * 1.5)]:
        r = simulate(D, S, 0.08, n_paths=30000); dd = p95_annual_maxdd(D, S)
        out["challenge"][tag] = dict(mult_vs_std=round(S / S3, 2), p95DD=round(dd, 0),
                                     pass_pct=r["pass_pct"], fail_pct=r["fail_pct"], med=r["med_month"])
        print(f"{tag:24s}{dd:>9.0f}{r['pass_pct']:>8}{r['fail_pct']:>8}{r['med_month']:>7}")

    # 【2】資金化後 収益(持続サイズ + 高リスク)
    S10 = find_scale(D, -10.0)
    print(f"\n【2】資金化後 収益  口座=${ACCOUNT_USD:,.0f} / 分配{SPLIT*100:.0f}% / ¥{FX}/$:")
    print(f"{'サイズ':16s}{'年率%':>8}{'年失格%':>9}{'手取り/月':>13}{'手取り/年':>13}{'期待手取り/年':>15}")
    for tag, S in [("保守 −6%", find_scale(D, -6.0)), ("中庸 −8%", find_scale(D, -8.0)),
                   ("攻め −10%", S10), ("高リスク ×1.5", S10 * 1.5), ("超攻め ×2.0", S10 * 2.0)]:
        ar = ann_return(D, S); af = annual_fail(D, S)
        gy = ACCOUNT_USD * ar * SPLIT * FX; gm = gy / 12; ey = gy * (1 - af)
        out["funded"][tag] = dict(ann_return_pct=round(ar * 100, 1), annual_fail_pct=round(af * 100, 1),
                                  net_month_jpy=round(gm), net_year_jpy=round(gy), exp_year_jpy=round(ey))
        print(f"{tag:16s}{ar*100:>8.1f}{af*100:>9.1f}{('¥'+format(round(gm),',')):>13}{('¥'+format(round(gy),',')):>13}{('¥'+format(round(ey),',')):>15}")

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    json.dump(out, open(os.path.join(HERE, "results", "portfolio_D_deploy.json"), "w"),
              ensure_ascii=False, indent=2, default=str)
    print("\n保存: results/portfolio_D_deploy.json")
    print("注: 審査=median-3攻め(口座喪失前提)。資金化後は別サイズ(生存優先)。¥は近似(Drive+デモで確定)。")
    print("    $50k口座は概ね半額・base分配80%なら×0.842・為替変動・年失格は月次=楽観側。")
    return out


if __name__ == "__main__":
    main()
