# -*- coding: utf-8 -*-
"""
instant20k_stepup_mc.py — FN Stellar Instant($20k・トレーリング−6%建値ロック)での
季節R4+G3の【ステップアップ初到達】を倍率別に計測。
ユーザー質問(2026-07-15)「リスク倍率を高めた場合のステップアップ中央月は?」への回答用。

ルール(公式Help 2026-07-15確認, docs/154 §5):
  - 失格: equity(日次close) <= フロア。フロア = HWM − 6%×初期。建値(初期残高)でロック。
  - ステップアップ: 現tierで累計出金10%+出金1回 → 初期額を加算して次tierへ。
    → 本MCでは「equityが+10%に初到達したら出金してtier昇格」を代理指標にする
      (1回の出金で両条件を同時充足=中間出金なし。中間出金は建値ロック下で
       equityをフロアに近づけるため合理戦略でもある)。
  - 同月内に+10%到達と失格が両方成立する場合は日次で先着判定・同日はfail優先(保守)。
方法: docs/111系の日次ブロックMC(月単位BS・シード7・2万パス・36ヶ月上限)。
構成: 季節R4+G3(instant50k_seasonal_trailing_mc.pyと同一構築)。
出力: results/instant20k_stepup.json → docs/155
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("RG_ALLOW_YAHOO", "0")

from portfolio_daily_compare import (mon_daily, cc_daily, e5_daily, v4_daily, g3_daily,
                                     composite_daily, YEN, V7X, EMON, EMONX)
from seasonal_optimize_loyo import build_sleeves, month_stats, weights_for, LOYO_YEARS, sha256s
from instant50k_seasonal_trailing_mc import month_paths

SEED, N_PATHS, HORIZON = 7, 20000, 36
MULTS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0]
X, TARGET = 0.06, 0.10


def simulate_stepup(months, n_paths, horizon, rng):
    nm = len(months)
    e = np.ones(n_paths); hwm = np.ones(n_paths)
    outcome = np.zeros(n_paths, dtype=int)          # 0=未決着 1=昇格 2=失格
    ev_month = np.full(n_paths, -1)
    for t in range(1, horizon + 1):
        open_ = outcome == 0
        if not open_.any():
            break
        idx = rng.integers(0, nm, size=n_paths)
        for m in np.unique(idx[open_]):
            sel = open_ & (idx == m)
            if not sel.any():
                continue
            cp, cmx = months[m]
            eq = e[sel, None] * cp[None, :]
            hw = np.maximum(hwm[sel, None], e[sel, None] * cmx[None, :])
            floor = np.minimum(hw - X, 1.0)
            br = eq <= floor
            up = eq >= 1.0 + TARGET
            has_br, has_up = br.any(axis=1), up.any(axis=1)
            bidx = np.where(has_br, br.argmax(axis=1), 10 ** 6)
            uidx = np.where(has_up, up.argmax(axis=1), 10 ** 6)
            ii = np.where(sel)[0]
            fail = has_br & (bidx <= uidx)          # 同日はfail優先(保守)
            win = has_up & (uidx < bidx)
            outcome[ii[fail]] = 2; ev_month[ii[fail]] = t
            outcome[ii[win]] = 1; ev_month[ii[win]] = t
            cont = ii[~fail & ~win]
            e[cont] = e[cont] * cp[-1]
            hwm[cont] = hw[~fail & ~win, -1]
    upm = ev_month[outcome == 1]
    return dict(
        stepup_pct=round(100 * float((outcome == 1).mean()), 1),
        breach_first_pct=round(100 * float((outcome == 2).mean()), 1),
        undone_36m_pct=round(100 * float((outcome == 0).mean()), 1),
        median_stepup_month=(float(np.median(upm)) if upm.size else None),
        p25_stepup_month=(float(np.percentile(upm, 25)) if upm.size else None),
        p75_stepup_month=(float(np.percentile(upm, 75)) if upm.size else None),
        stepup_within_6m_pct=round(100 * float(((outcome == 1) & (ev_month <= 6)).mean()), 1),
        stepup_within_12m_pct=round(100 * float(((outcome == 1) & (ev_month <= 12)).mean()), 1),
    )


def main():
    print("[1/2] スリーブ構築(docs/154と同一)")
    sleeves = dict(v7=mon_daily(YEN), v7x=mon_daily(V7X),
                   EMon=mon_daily(EMON, 3e-4), EMonX=mon_daily(EMONX, 3e-4),
                   E5=e5_daily(), SJul=cc_daily(["US500", "NAS100"]), v4=v4_daily())
    g3 = g3_daily()
    dfm = build_sleeves(1.0)
    dfm = dfm[(dfm.index.year >= 2016) & (dfm.index.year <= 2025)]
    mu, sd = month_stats(dfm, LOYO_YEARS)
    R4 = {m: weights_for("R4", mu.loc[m], sd.loc[m]) for m in range(1, 13)}
    base = composite_daily(sleeves, R4)
    g3s = g3.reindex(base.index).fillna(0.0)

    print("[2/2] 倍率別ステップアップMC(FN−6%建値ロック・+10%初到達 vs 失格・各2万パス)")
    out = {}
    for mult in MULTS:
        months = month_paths(base * mult + g3s)
        rec = simulate_stepup(months, N_PATHS, HORIZON, np.random.default_rng(SEED))
        out[f"x{mult}"] = rec
        print(f"  mult={mult}: {rec}")

    res = dict(meta=dict(
        method="日次ブロックMC(月単位BS)。昇格=+10%初到達(日次close)、失格=フロア(HWM−6%・建値"
               "ロック)以下。同月内両成立は日次先着・同日fail優先。中間出金なし想定。",
        rule="FN Stellar Instant(docs/154 §5・公式Help 2026-07-15確認)",
        window="2016-01..2026-06", n_paths=N_PATHS, horizon_months=HORIZON,
        composition="季節R4+G3(WR4月別表・G3は倍率非適用)", inputs=sha256s(),
        caveat="Yahoo日足=保守側(docs/138)。日次close解像度=失格はやや高い側。"),
        variants=out)
    path = os.path.join(HERE, "results", "instant20k_stepup.json")
    with open(path, "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", path)


if __name__ == "__main__":
    main()
