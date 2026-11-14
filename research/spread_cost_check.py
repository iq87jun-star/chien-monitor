# -*- coding: utf-8 -*-
"""docs/216: Dukascopy ティック要約(2026-08)の時間帯別スプレッド vs 選抜モデルの往復 2pip 定数。Mon レッグ 12m 平均のコスト感度。"""
import os, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
import recentfit_screen as base
HERE = os.path.dirname(os.path.abspath(__file__)); SYMS = ["GBPJPY", "USDJPY", "AUDJPY", "EURJPY", "GBPUSD"]; SHOTS = [4, 6, 8, 10]
MODEL_RT = 2.0


def main():
    out = {}
    for s in SYMS:
        d = pd.read_csv(os.path.join(HERE, "results", f"spread_profile_{s}.csv"))
        med = d.pivot(index="weekday", columns="hour_utc", values="med_pips"); p90 = d.pivot(index="weekday", columns="hour_utc", values="p90_pips")
        rt_med = {h: round(float(med.at[0, h] + med.at[1, h]), 2) for h in SHOTS}; rt_p90 = {h: round(float(p90.at[0, h] + p90.at[1, h]), 2) for h in SHOTS}
        allh = d.groupby("hour_utc")["med_pips"].median(); worst = allh.idxmax()
        rt00 = round(float(med.at[0, 0] + med.at[1, 0]), 2)
        out[s] = dict(rt_med_by_shot=rt_med, rt_p90_by_shot=rt_p90, rt_p90_mean=round(float(np.mean(list(rt_p90.values()))), 2),
                      ratio_p90_vs_model=round(float(np.mean(list(rt_p90.values()))) / MODEL_RT, 2), worst_hour_utc=int(worst), worst_med_pips=round(float(allh.max()), 2),
                      rt_med_00utc=rt00, hourly_med=allh.round(2).to_dict())
        print(f"{s}: 往復 中央値 {rt_med} / p90 {rt_p90}  p90平均={out[s]['rt_p90_mean']}pip = モデル×{out[s]['ratio_p90_vs_model']}  最悪帯 {worst}UTC {out[s]['worst_med_pips']}pip  00UTC往復={rt00}")
    # 感度: Mon レッグ 12m 平均(Yahoo 日足・mon_cell と同式)
    base.W_ALL0, base.W_ALL1 = pd.Timestamp("2016-01-01"), pd.Timestamp("2026-07-29"); w0 = pd.Timestamp("2025-08-01")
    print("\nMon レッグ 直近12ヶ月(2025-08〜2026-07)平均 bps / 累積 %:  コスト = モデル2pip | Duka往復p90 | Duka p90+2pip(ブローカー上乗せ)")
    sens = {}
    for s in SYMS:
        df = base.load_daily(s); pip = base.pip_size(s); mon = df[df["weekday"] == 0]; o2o = mon["o2o"]; op = mon["open"]
        res = {}
        for lab, c in (("model_2pip", MODEL_RT), ("duka_p90", out[s]["rt_p90_mean"]), ("duka_p90_plus2", out[s]["rt_p90_mean"] + 2.0)):
            r = (o2o - c * pip / op).dropna(); r = r[r.index >= w0]
            res[lab] = dict(mean_bps=round(float(r.mean()) * 1e4, 2), cum_pct=round(float((1 + r).prod() - 1) * 100, 2), n=len(r))
        sens[s] = res; print(f"  {s}: " + " | ".join(f"{v['mean_bps']:+.1f}bps/{v['cum_pct']:+.2f}%" for v in res.values()) + f"  (n={res['model_2pip']['n']})")
    out["sensitivity_12m"] = sens
    json.dump(out, open(os.path.join(HERE, "results", "spread_cost_check.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__": main()
