# -*- coding: utf-8 -*-
"""
portfolio3_p1_insurance.py — docs/131 P1 の実行: 第3ポートフォリオ候補
「Portfolio-I(レジーム保険)」= E5 60 / G3 20 / v4 20 の構成検定。
手法: docs/110 と同一(日次再合成→安全倍率=min(単日-4%,月中-8%)逆算×0.8)。
比較: PortfolioD(30/25/25/20)・R4+G3・E5単体。ゲート I-1〜I-4(docs/131固定)。
出力: results/portfolio3_p1_insurance.json → docs/132 へ転記。
"""
import os, sys, json, datetime as dt
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from portfolio_daily_compare import (mon_daily, e5_daily, v4_daily, g3_daily, cc_daily,
                                     composite_daily, calibrate, worst_stats, monthly_stats,
                                     YEN, EMON, W0, W1, M3)

WI = {m: {"E5": .60, "v4": .20} for m in range(1, 13)}          # G3は別レイヤ(校正はcalibrate(g3=)で)
WD = {m: {"v4": .30, "v7": .25, "EMon": .25, "E5": .20} for m in range(1, 13)}
WE5 = {m: {"E5": 1.0} for m in range(1, 13)}


def to_monthly_ret(daily):
    mk = pd.PeriodIndex(daily.index, freq="M")
    return pd.Series({m: float((1 + daily[mk == m]).prod() - 1) for m in mk.unique()}).sort_index()


def stress_expect(sleeve_ann, weights):
    """レジーム・ストレス: v4/G3/v7/EMonの期待値を0に置換、E5のみ実績年率を残す。"""
    return weights.get("E5", 0.0) * sleeve_ann["E5"]


def main():
    R = {"meta": dict(started=dt.datetime.now(dt.timezone.utc).isoformat(), spec="docs/131 P1",
                      window=f"{W0.date()}..{W1.date()}")}
    print("[1/4] スリーブ構築")
    sleeves = dict(v7=mon_daily(YEN), EMon=mon_daily(EMON, 3e-4),
                   E5=e5_daily(), v4=v4_daily())
    g3 = g3_daily()
    print("  ", {k: len(v) for k, v in sleeves.items()}, "G3 events:", len(g3))

    # R4+G3(現行季節・比較用)を docs/110 と同じ手順で再構築
    print("[2/4] R4+G3再構築(比較用)")
    from seasonal_optimize_loyo import build_sleeves, month_stats, weights_for, LOYO_YEARS
    dfm = build_sleeves(1.0)
    dfm = dfm[(dfm.index.year >= 2016) & (dfm.index.year <= 2025)]
    mu, sd = month_stats(dfm, LOYO_YEARS)
    R4 = {m: weights_for("R4", mu.loc[m], sd.loc[m]) for m in range(1, 13)}
    sleeves_full = dict(sleeves, v7x=mon_daily(["AUDJPY", "NZDJPY", "CADJPY", "CHFJPY"]),
                        EMonX=mon_daily(["JP225", "UK100", "FR40"], 3e-4),
                        SJul=cc_daily(["US500", "NAS100"]))

    print("[3/4] 校正と比較(全て docs/87 倍率規律)")
    # Portfolio-I: base(E5+v4)にG3レイヤを足して校正(G3はイベントリスク一定=倍率非適用, docs/110方式)
    # → 重み20%相当は g3_daily(event_risk=0.01)の素をそのまま(=口座リスク1%/イベント)使い、
    #   E5:v4=60:20 の相対比を保った base 側を校正する。
    variants = {}
    defs = {
        "Portfolio-I": (WI, sleeves, True),
        "PortfolioD": (WD, sleeves, False),
        "R4+G3": (R4, sleeves_full, True),
        "E5単体": (WE5, sleeves, False),
    }
    daily_final = {}
    for name, (wmap, slv, useG3) in defs.items():
        base = composite_daily(slv, wmap)
        rec = calibrate(base, g3 if useG3 else None)
        s = base * rec
        if useG3:
            s = s.add(g3, fill_value=0.0)
        st = monthly_stats(s)
        wd, wdd = worst_stats(s)
        st["mult"] = rec
        st["worst_intramonth_DD"] = round(wdd * 100, 1)
        variants[name] = st
        daily_final[name] = s
        print(f"  {name:12s} mult={rec:.2f} {st}")

    # ---- ゲート判定 ----
    print("[4/4] ゲート判定")
    mI = to_monthly_ret(daily_final["Portfolio-I"])
    corr = {}
    for other in ("PortfolioD", "R4+G3"):
        mo = to_monthly_ret(daily_final[other])
        j = pd.concat([mI.rename("i"), mo.rename("o")], axis=1).dropna()
        corr[other] = round(float(j["i"].corr(j["o"])), 3)
    # ストレス: 各スリーブの安全倍率適用後の年率寄与を素材に(E5のみ生存)
    # E5単体年率(安全倍率後)をE5の実績年率として使用
    e5_ann = variants["E5単体"]["cagr"]
    # Portfolio-Iの校正倍率でのE5実効ウェイト = 0.6*multI / 1.0*multE5 を年率換算で近似
    multI, multE5 = variants["Portfolio-I"]["mult"], variants["E5単体"]["mult"]
    stress_I = round(0.60 * multI / multE5 * e5_ann, 2)
    stress_D = round(0.20 * variants["PortfolioD"]["mult"] / multE5 * e5_ann, 2)
    gates = {
        "I1_independence": all(abs(v) < 0.5 for v in corr.values()),
        "I2_diversification": variants["Portfolio-I"]["sharpe"] > variants["E5単体"]["sharpe"],
        "I3_practicality": variants["Portfolio-I"]["cagr"] >= 4.0,
        "I4_insurance": stress_I > stress_D,
    }
    R.update(variants=variants, monthly_corr_vs=corr,
             stress=dict(e5_alone_ann=e5_ann, portfolio_I_stress_ann=stress_I,
                         portfolioD_stress_ann=stress_D,
                         note="v4/G3/v7/EMon期待値0置換・E5実績のみ(安全倍率換算)"),
             gates=gates, gates_passed=sum(gates.values()),
             verdict="採用提起(デモ前提)" if all(gates.values()) else "不採用(代替=案3複製)")
    print("  corr:", corr, "| stress I vs D:", stress_I, stress_D)
    print("  gates:", gates, "→", R["verdict"])

    out = os.path.join(HERE, "results", "portfolio3_p1_insurance.json")
    json.dump(R, open(out, "w"), indent=1, ensure_ascii=False, default=str)
    print("saved:", out)


if __name__ == "__main__":
    main()
