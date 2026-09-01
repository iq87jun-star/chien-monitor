# -*- coding: utf-8 -*-
"""
selection_value_horizon_check.py — 【実験①の補正】アーム間の取引カレンダー差を正規化する。

自己レビューで判明した問題(docs/187 §6に記録):
BROAD系は暗号セル(BTC/ETH・週末も値がつく)とHold/TSMOM(毎日)を含むため、
OOS系列の「1日」の本数がSEL系より多い(例 BROAD_IV 2717本 vs SEL12 2137本・同一暦期間)。
このため
  (a) 日次シャープ・年率ボラの√252換算がアーム間で不整合
  (b) MCの地平 max_days=250「営業日」が、暦では BROAD_IV≈255日 / SEL12≈324日と
      **SEL系に有利**な非対称になっていた
本スクリプトは各アームの暦換算係数を出し、**同一の暦地平**でMCを再実行して比較を揃える。
出力: results/selection_value_horizon_check.json → docs/187 §6
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recentfit_screen as base
import selection_value_walkforward as wf

SEED = 7
CAL_HORIZON_P1 = 365          # P1の暦地平(日)
ARMS = list(wf.SEL_RULES) + wf.BROAD_ARMS


def main():
    print("[1/3] セル構築")
    for nm in base.YAHOO:
        try:
            base.fetch(nm)
        except Exception:
            pass
    cells = {}
    for nm in base.MON_FX + base.MON_IDX:
        cells[f"Mon_{nm}"] = dict(family="Mon", symbol=nm, s=base.mon_cell(nm))
    for nm in base.HOLD_SYMS:
        cells[f"Hold_{nm}"] = dict(family="Hold", symbol=nm, s=base.hold_cell(nm))
    for nm in base.TSMOM_SYMS:
        cells[f"TSMOM_{nm}"] = dict(family="TSMOM", symbol=nm, s=base.tsmom_cell(nm))
    for p in base.V4_PAIRS:
        cells[f"v4_{p}"] = dict(family="v4", symbol=p, s=base.v4_cell(p))

    base.verify_window([v["s"] for v in cells.values()])   # docs/192の再発防止
    print("[2/3] ウォークフォワード(月次入替のみ)")
    rebal = pd.date_range(wf.WF_START, wf.WF_LAST, freq="ME")
    daily = {}
    for arm in ARMS:
        s, _ = wf.run_arm(cells, arm, rebal, 1)
        daily[arm] = s
        span = (s.index[-1] - s.index[0]).days
        print(f"  {arm:11s} n={len(s)} 暦span={span}日 係数={span/len(s):.3f}")

    print("[3/3] 暦正規化MC(P1地平=365暦日・P2は倍)")
    out = {"meta": {"purpose": "実験①のカレンダー差補正 docs/187 §6", "seed": SEED,
                    "cal_horizon_p1_days": CAL_HORIZON_P1,
                    "note": "max_daysをアームごとに暦365日相当の本数へ換算して同一地平で比較"},
           "arms": {}}
    for arm in ARMS:
        s = daily[arm]
        span = (s.index[-1] - s.index[0]).days
        factor = span / len(s)                      # 1本あたりの暦日数
        md = int(round(CAL_HORIZON_P1 / factor))    # 暦365日に相当する本数
        rec = dict(n_index_days=int(len(s)), span_days=int(span),
                   calendar_days_per_index_day=round(factor, 3),
                   max_days_used=md,
                   sharpe_calendar=round(float(s.mean() / s.std() * np.sqrt(365 / factor)), 2),
                   vol_ann_calendar=round(float(s.std() * np.sqrt(365 / factor)) * 100, 2))
        for venue, p1 in (("FTMO_10_5", 0.10), ("FN_8_5", 0.08)):
            base.P1_TARGET = p1
            r = base.mc_challenge(s, 1.0, np.random.default_rng(SEED), max_days=md)
            # 日数を暦へ換算
            for k in ("p1_days_med", "p1_days_p90", "funded_days_med", "funded_days_p90"):
                if r.get(k) is not None:
                    r[k + "_cal"] = int(round(r[k] * factor))
            rec.setdefault("mc", {})[venue] = r
        out["arms"][arm] = rec
        m = rec["mc"]["FTMO_10_5"]
        print(f"  {arm:11s} SR暦={rec['sharpe_calendar']:.2f} 地平={md}本 "
              f"funded={m['funded']}% fail={m['fail']}% 中央={m.get('funded_days_med_cal')}暦日")

    fp = os.path.join(HERE, "results", "selection_value_horizon_check.json")
    with open(fp, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("saved:", fp)


if __name__ == "__main__":
    main()
