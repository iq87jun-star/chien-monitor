# -*- coding: utf-8 -*-
"""docs/224: docs/216 §4.2 の感度を FNmarkets RAW 実コストで再計算(docs/223 §5.6 の未実施項目)。
コスト列: モデル 2pip | Duka 往復 p90 | Duka p90 + RAW 手数料(USD 7/lot を pip 換算) | 同 − 1 日分スワップ(LONG・実測 #511030)。
Mon レッグ(週1・24h)= 月→火でロール 1 回(3 倍日=水 は跨がない)。"""
import os, json, csv, pandas as pd, warnings; warnings.filterwarnings("ignore")
import recentfit_screen as base
HERE = os.path.dirname(os.path.abspath(__file__)); SYMS = ["GBPJPY", "USDJPY", "AUDJPY", "EURJPY", "GBPUSD"]; MODEL_RT = 2.0
duka = json.load(open(os.path.join(HERE, "results", "spread_cost_check.json")))
fn = {r["symbol"]: r for r in csv.DictReader(open(os.path.join(HERE, "results", "fn511030_costs.csv")))}


def main():
    base.W_ALL0, base.W_ALL1 = pd.Timestamp("2016-01-01"), pd.Timestamp("2026-07-29"); w0 = pd.Timestamp("2025-08-01")
    out = {}
    print("Mon レッグ 直近12ヶ月平均 bps / 累積%:  2pip | Duka p90 | +RAW手数料 | +手数料−1日スワップ(LONG)")
    for s in SYMS:
        df = base.load_daily(s); pip = base.pip_size(s); mon = df[df["weekday"] == 0]; o2o = mon["o2o"]; op = mon["open"]
        f = fn[s]; mid = float(f["mid"]); pip_bps = pip / mid * 1e4
        comm_pip = float(f["comm_rt_bps"]) / pip_bps                       # USD7/lot → pip
        swap_pip = float(f["swap_long_bps_d"]) / pip_bps                   # 1 日分(LONG)。正=受取
        p90 = duka[s]["rt_p90_mean"]
        costs = {"model_2pip": MODEL_RT, "duka_p90": p90, "duka_p90_comm": p90 + comm_pip, "duka_p90_comm_swap": p90 + comm_pip - swap_pip}
        res = {}
        for lab, c in costs.items():
            r = (o2o - c * pip / op).dropna(); r = r[r.index >= w0]
            res[lab] = dict(cost_pip=round(c, 2), mean_bps=round(float(r.mean()) * 1e4, 2), cum_pct=round(float((1 + r).prod() - 1) * 100, 2), n=len(r))
        out[s] = dict(comm_pip=round(comm_pip, 2), swap_1d_long_pip=round(swap_pip, 2), fn_snapshot_spread_pip=round(float(f["spread_bps"]) / pip_bps, 2), **res)
        print(f"  {s}: comm={comm_pip:.2f}pip swap1d={swap_pip:+.2f}pip  " + " | ".join(f"{v['cost_pip']:.2f}pip→{v['mean_bps']:+.1f}bps/{v['cum_pct']:+.2f}%" for v in res.values()) + f"  (n={res['model_2pip']['n']})")
    json.dump(out, open(os.path.join(HERE, "results", "fn_cost_sensitivity.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__": main()
