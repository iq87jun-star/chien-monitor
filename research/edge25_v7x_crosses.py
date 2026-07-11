# -*- coding: utf-8 -*-
"""
edge25_v7x_crosses.py — docs/131 P2 の実行: v7x(円月曜・新4クロス AUD/NZD/CAD/CHF-JPY)の
スリーブ採用検定。docs/86 H14c(機構確認)の宿題=配分・コスト・相関の正式検定。
ルール(v7逐語): 月曜open→火曜open LONG・4クロス等ウェイト。コスト基準往復3pip(感応2/3/4.5/6)。
ゲート: G1-G6+G9(docs/131固定・α=0.01)。出力: results/edge25_v7x_crosses.json → docs/132。
"""
import os, sys, json, glob, hashlib, datetime as dt
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
sys.path.insert(0, HERE)

from edge23_cot_positioning import load_daily, clip, perm_p, jackknife

ALPHA = 0.01
MAIN = ("2016-01-01", "2026-06-30")
IS_END, OOS_START = "2020-12-31", "2021-01-01"
V7X = ["AUDJPY", "NZDJPY", "CADJPY", "CHFJPY"]
YEN = ["EURJPY", "GBPJPY", "USDJPY"]
PIP = 0.01                                    # 円クロスのpip
COST_PIPS = 3.0                               # docs/131固定(基準)


def basket_daily(pairs, cost_pips, weekday=0, seed=None):
    """weekday曜日open→翌営業日open LONG・等ウェイト。seed指定時=同週ランダム非月曜(プラセボ)。"""
    rng = np.random.default_rng(seed) if seed is not None else None
    parts = []
    for p in pairs:
        df = load_daily(p)
        df = df.copy()
        df["o2o"] = df["open"].shift(-1) / df["open"] - 1.0
        if rng is None:
            sel = df[df.index.dayofweek == weekday]
        else:
            # 各週から非月曜の営業日を1つランダム抽出
            wk = df.index.to_period("W")
            picks = []
            for w, g in df.groupby(wk):
                cand = g[g.index.dayofweek != 0]
                if len(cand):
                    picks.append(cand.index[rng.integers(len(cand))])
            sel = df.loc[sorted(picks)]
        r = (sel["o2o"] - cost_pips * PIP / sel["open"]).dropna()
        parts.append(r.rename(p))
    return pd.concat(parts, axis=1).mean(axis=1, skipna=True).dropna()


def metrics_d(r):
    r = r.dropna()
    eq = (1 + r).cumprod()
    dd = float(((eq - eq.cummax()) / eq.cummax()).min()) if len(eq) else 0.0
    mu, sd = r.mean() * 52, r.std() * np.sqrt(52)
    return dict(net=round(float(eq.iloc[-1] - 1) * 100, 2), maxdd=round(dd * 100, 2),
                sharpe=round(float(mu / sd), 2) if sd > 0 else 0.0,
                n=int(len(r)), winrate=round(float((r > 0).mean()) * 100, 1))


def to_monthly(r):
    s = r.copy(); s.index = pd.to_datetime(s.index).to_period("M")
    return s.groupby(level=0).sum()


def calmar_monthly(m):
    eq = (1 + m).cumprod()
    dd = float(((eq - eq.cummax()) / eq.cummax()).min())
    ann = float(m.mean() * 12)
    return round(ann / abs(dd), 2) if dd < 0 else np.inf


def main():
    R = {"meta": dict(started=dt.datetime.now(dt.timezone.utc).isoformat(), spec="docs/131 P2",
                      alpha=ALPHA, cost_base_pips=COST_PIPS)}
    print("[1/4] 本窓検定(3pip)")
    r = clip(basket_daily(V7X, COST_PIPS), *MAIN)
    m = metrics_d(r)
    p = perm_p(r)
    jk, jk_pos, jk_n = jackknife(r)
    r_is = clip(r, MAIN[0], IS_END); r_oos = clip(r, OOS_START, MAIN[1])
    print("  ", m, "p=", p, "JK", f"{jk_pos}/{jk_n}")

    print("[2/4] コスト感応・プラセボ")
    cost_sens = {}
    for cp in (2.0, 3.0, 4.5, 6.0):
        cost_sens[f"{cp}pip"] = metrics_d(clip(basket_daily(V7X, cp), *MAIN))["net"]
    nets = []
    for i in range(500):
        nets.append(float(clip(basket_daily(V7X, COST_PIPS, seed=1000 + i), *MAIN).sum()))
    plc_p95 = round(float(np.quantile(nets, 0.95)) * 100, 2)
    plc_p = round(float((np.asarray(nets) >= float(r.sum())).mean()), 4)
    print("  cost:", cost_sens, "placebo p95:", plc_p95, "p:", plc_p)

    print("[3/4] G9 v7クラシックとのブレンド寄与")
    v7c = clip(basket_daily(YEN, 2.0), *MAIN)      # 既存v7=2pip(docs/14系)
    mv7 = to_monthly(v7c); mx = to_monthly(r)
    blend = (mv7.add(mx, fill_value=0.0)) / 2.0
    cal_v7, cal_blend = calmar_monthly(mv7), calmar_monthly(blend)
    j = pd.concat([mv7.rename("a"), mx.rename("b")], axis=1).dropna()
    rho = round(float(j["a"].corr(j["b"])), 3)
    print(f"  Calmar v7={cal_v7} blend={cal_blend} ρ={rho}")

    gates = dict(G1_econ=m["net"] > 0, G2_perm=p < ALPHA,
                 G3_jk=(jk_pos / jk_n) >= 0.9 if jk_n else False,
                 G4_placebo=m["net"] > plc_p95,
                 G5_cost2x=cost_sens["6.0pip"] > 0,
                 G6_isoos=(float(r_is.sum()) > 0 and float(r_oos.sum()) > 0),
                 G9_blend=cal_blend > cal_v7)
    R.update(main=m, perm_p=p, jk_pass=f"{jk_pos}/{jk_n}", jackknife=jk,
             is_net=round(float(r_is.sum()) * 100, 2), oos_net=round(float(r_oos.sum()) * 100, 2),
             cost_sens=cost_sens, placebo_p95=plc_p95, placebo_p=plc_p,
             corr_v7classic=rho, calmar=dict(v7=cal_v7, blend50=cal_blend),
             gates=gates, gates_passed=sum(gates.values()),
             verdict="v7xスリーブ採用可(配備形態はdocs/132)" if all(gates.values()) else "REJECT")
    print("[4/4] gates:", gates, "→", R["verdict"])

    hashes = {}
    for n in V7X + YEN:
        pth = os.path.join(DATA, f"{n}_d.csv")
        if os.path.exists(pth):
            hashes[f"{n}_d.csv"] = hashlib.sha256(open(pth, "rb").read()).hexdigest()[:16]
    R["input_sha256"] = hashes
    out = os.path.join(HERE, "results", "edge25_v7x_crosses.json")
    json.dump(R, open(out, "w"), indent=1, ensure_ascii=False, default=str)
    print("saved:", out)


if __name__ == "__main__":
    main()
