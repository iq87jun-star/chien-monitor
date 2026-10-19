# -*- coding: utf-8 -*-
"""
portfolio_patterns.py — 全エッジを棚卸しし、複数のポートフォリオ・パターンを定量提案。

在庫(検証済み/候補):
  v7  円月曜(STRONG-LEAD)   v4 FX日足k≥4合議(ADOPT)   E5 多資産月次TSMOM(STRONG-LEAD)
  E-Mon 株価指数月曜(STRONG-LEAD・新/別ブランチP2と収束)   CRYPTO BTC/ETH月曜(有意・高DD=衛星)
  ※ v9(円月曜12h)はv7の低DD変種(日足から再現不可→v7で代表)。

各パターンを「リスク加重(各レッグ等ボラ標準化×比率)」で合成し、Sharpe/Calmar/maxDD/年率@-6% を実測。
規律: 数字は盛らない。Yahoo日足10年・近似。絶対値はDrive+デモで確定。"""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parallel_vs_existing_compare import (load_daily, v7_monthly, v4_monthly, e5_monthly,
                                          emon_monthly, to_monthly, metrics, z)

HERE = os.path.dirname(os.path.abspath(__file__))


def crypto_monthly():
    """BTC/ETH 月曜LONG 等加重(暗号は2倍コスト)。"""
    parts = []
    for nm in ["BTCUSD", "ETHUSD"]:
        df = pd.read_csv(os.path.join(HERE, "data", f"{nm}_d.csv"))
        df["t"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        df = df.dropna(subset=["t"]).sort_values("t")
        df["trade_date"] = (df["t"] + pd.Timedelta(hours=2)).dt.floor("D")
        df = df.groupby("trade_date").last(); df["weekday"] = df.index.dayofweek
        df["o2o"] = df["open"].shift(-1) / df["open"] - 1.0
        r = (df[df["weekday"] == 0]["o2o"] - 12e-4).dropna()   # 12bps往復
        parts.append(r.rename(nm))
    w = pd.concat(parts, axis=1).mean(axis=1, skipna=True).dropna()
    return to_monthly(w).rename("CRYPTO")


def build():
    comp = {"v7": v7_monthly(), "v4": v4_monthly(), "E5": e5_monthly(),
            "E-Mon": emon_monthly(), "CRYPTO": crypto_monthly()}
    return comp


def port(comp, weights):
    """weights: {name: risk_weight}。等ボラ標準化×比率で合成した月次系列。"""
    s = None
    for k, w in weights.items():
        if w == 0 or k not in comp:
            continue
        leg = z(comp[k]) * w
        s = leg if s is None else s.add(leg, fill_value=0.0)
    return s.dropna()


def main():
    comp = build()
    M = pd.DataFrame(comp)
    corr = M.corr().round(2)
    print("=" * 84)
    print("全エッジ 月次相関行列(10年・Yahoo日足近似):")
    print(corr.to_string())
    print("\n各エッジ 単体(素系列):")
    for k, v in comp.items():
        m = metrics(v, 12); print(f"   {k:7s} Sharpe{m['sharpe']:>5} maxDD{m['maxDD']:>6}% Calmar{m['calmar']:>5} n={m['n']}")

    # ---- 提案パターン(リスク加重) ----
    patterns = {
        "P0 既存主力 v7+v4+E5 (40:40:20)":
            {"v7": .40, "v4": .40, "E5": .20},
        "P-A 4戦略単一口座 +E-Mon (30:30:20:20)":
            {"v7": .30, "v4": .30, "E5": .20, "E-Mon": .20},
        "P-B 並行ポート核 E-Mon+E5 (65:35)":
            {"E-Mon": .65, "E5": .35},
        "P-C 守備・低DD v4厚め (v4 50/v7 30/E-Mon 20)":
            {"v4": .50, "v7": .30, "E-Mon": .20},
        "P-D 攻撃・暗号衛星 (v4 30/v7 25/E-Mon 25/E5 12/CRYPTO 8)":
            {"v4": .30, "v7": .25, "E-Mon": .25, "E5": .12, "CRYPTO": .08},
        "P-E フル分散5戦略 (v4 28/v7 24/E-Mon 24/E5 16/CRYPTO 8)":
            {"v4": .28, "v7": .24, "E-Mon": .24, "E5": .16, "CRYPTO": .08},
    }
    print("\n" + "=" * 84)
    print("提案パターン(リスク加重・等ボラ標準化→共通目標DD−6%で年率):")
    print(f"{'パターン':52s} {'Sharpe':>7}{'maxDD%':>8}{'Calmar':>8}{'年率@-6%':>9}")
    out_pat = {}
    for name, w in patterns.items():
        s = port(comp, w); m = metrics(s, 12)
        out_pat[name] = m
        print(f"{name:52s} {m['sharpe']:>7}{m['maxDD']:>8}{m['calmar']:>8}{m['ann6']:>8}%")

    # ---- 2口座並走(P1 ∥ P2) ----
    P1 = port(comp, {"v7": .40, "v4": .40, "E5": .20})
    P2 = port(comp, {"E-Mon": .80, "CRYPTO": .20})   # 並行核=株月曜+暗号衛星
    j = pd.concat([z(P1).rename("P1"), z(P2).rename("P2")], axis=1).dropna()
    AB = 0.5 * j["P1"] + 0.5 * j["P2"]
    mP1, mP2, mAB = metrics(P1, 12), metrics(P2, 12), metrics(AB, 12)
    cAB = round(float(j["P1"].corr(j["P2"])), 3)
    coneg = round(float(((j["P1"] < 0) & (j["P2"] < 0)).mean()) * 100, 0)
    print("\n" + "=" * 84)
    print("2口座並走(別口座/別業者): P1(v7+v4+E5) ∥ P2(E-Mon80+暗号20)")
    print(f"   P1単体 Sharpe{mP1['sharpe']} maxDD{mP1['maxDD']}% / P2単体 Sharpe{mP2['sharpe']} maxDD{mP2['maxDD']}%")
    print(f"   P1⇄P2 相関 = {cAB}  / 同時マイナス月 = {coneg}%(複製なら100%)")
    print(f"   ★並走(50:50) Sharpe{mAB['sharpe']} maxDD{mAB['maxDD']}% = 共倒れを避けつつ総量拡大")

    out = dict(corr=corr.to_dict(), components={k: metrics(v, 12) for k, v in comp.items()},
               patterns=out_pat, parallel=dict(P1=mP1, P2=mP2, AB=mAB, corr=cAB, co_neg=coneg))
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "portfolio_patterns.json"), "w") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2, default=str)
    print("\n保存: research/results/portfolio_patterns.json")


if __name__ == "__main__":
    main()
