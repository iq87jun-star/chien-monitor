# -*- coding: utf-8 -*-
"""
recency_vs_existing.py — 直近特化(docs/175採用)と既存構成の同一土俵比較。
ユーザー要望(2026-07-30)「既存との比較をお願いします」。

対象(全て同一窓 2017-01〜2026-07・docs/111機械で中央3ヶ月校正):
  A) 直近特化 sharpe_W12_k3 のWF系列(docs/175)
  B) 季節R4+G3(旧標準・docs/172で撤収済みだが参照として)
  C) PD_noV4基準 v7p/EMonRG3/E5p=35.7/35.7/28.6(FN100k現行, docs/171)
  D) PD_noV4 EMonキャップ 45/25/30(FTMO現行, docs/171)
  E) PD間引き v4込み 30/25/25/20(FN Instant現行, docs/135)
追加: 月次リターン相関行列・各構成の最悪5ヶ月と直近特化の同月重なり(分散価値の検証)。
⚠ 土俵はFN P1+8%のチャレンジ速度統一比較。docs/171の本番数字(2段階MC・balanceガード・
  RG3込み)とは機械が違うため直接は比べないこと。EMonのRG3ゲートは edge_regime_gate_10y を
  再利用してC/D/Eに適用(docs/171 §1-3でRG3込みが正)。
出力: results/recency_vs_existing.json → docs/175 追補
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("RG_ALLOW_YAHOO", "0")

import recency_track as rt
from recency_track import calib_and_mc, W0, W1, SEED
import portfolio_daily_compare as pdc
from policy_prune_symbols import e5_basket
import edge_regime_gate_10y as RG


def wk_key(idx):
    iso = pd.DatetimeIndex(idx).isocalendar()
    return list(zip(iso.year, iso.week))


def emon_rg3_daily():
    """mon_daily(EMON,3e-4)にRG3(riskoff)週次ゲートを適用(OFF週=不参加=0寄与)"""
    raw_d = pdc.mon_daily(pdc.EMON, 3e-4)
    raw_w = RG.emon_weekly_raw()
    gated_w = RG.emon_weekly_gated("riskoff")
    off = set(wk_key(raw_w.index)) - set(wk_key(gated_w.index))
    keep = [k not in off for k in wk_key(raw_d.index)]
    return raw_d[keep]


def blend_daily(parts):
    """{series: weight} を日付ユニオンで加重合成(欠損=その日その玉なし=0)"""
    idx = sorted(set().union(*[set(s.index) for s, w in parts]))
    out = pd.Series(0.0, index=pd.DatetimeIndex(idx))
    for s, w in parts:
        out = out.add(s.reindex(out.index).fillna(0.0) * w, fill_value=0.0)
    return out[(out.index >= W0) & (out.index <= W1)]


def monthly(s):
    mk = pd.PeriodIndex(s.index, freq="M")
    return pd.Series({k: float((1 + s[mk == k]).prod() - 1) for k in mk.unique()}).sort_index()


def main():
    print("[1/4] 系列構築")
    pdc.W0, pdc.W1 = pd.Timestamp("2015-06-01"), W1
    _, units = rt.build_units()
    df = pd.DataFrame(units); df = df[df.index <= W1]
    rec, _ = rt.walk_forward(df, "sharpe", 12, 3)

    from seasonal_optimize_loyo import build_sleeves, month_stats, weights_for, LOYO_YEARS
    pdc.FOMC = pdc.FOMC + ["2026-06-17", "2026-07-29"]
    sleeves = dict(v7=pdc.mon_daily(pdc.YEN), v7x=pdc.mon_daily(pdc.V7X),
                   EMon=pdc.mon_daily(pdc.EMON, 3e-4), EMonX=pdc.mon_daily(pdc.EMONX, 3e-4),
                   E5=pdc.e5_daily(), SJul=pdc.cc_daily(["US500", "NAS100"]), v4=pdc.v4_daily())
    dfm = build_sleeves(1.0)
    dfm = dfm[(dfm.index.year >= 2016) & (dfm.index.year <= 2025)]
    mu, sd = month_stats(dfm, LOYO_YEARS)
    R4 = {m: weights_for("R4", mu.loc[m], sd.loc[m]) for m in range(1, 13)}
    seasonal = pdc.composite_daily(sleeves, R4); seasonal = seasonal[seasonal.index >= W0]
    g3 = pdc.g3_daily(); g3 = g3[g3.index >= W0]

    v7p = pdc.mon_daily(["EURJPY", "GBPJPY"])
    emon_rg3 = emon_rg3_daily()
    e5p = e5_basket(["XAUUSD", "NAS100"])
    v4 = sleeves["v4"]
    pd_fn = blend_daily([(v7p, .357), (emon_rg3, .357), (e5p, .286)])
    pd_ftmo = blend_daily([(v7p, .45), (emon_rg3, .25), (e5p, .30)])
    pd_inst = blend_daily([(v4, .30), (v7p, .25), (emon_rg3, .25), (e5p, .20)])

    print("[2/4] 校正+MC(docs/111・2万パス)")
    rows = {}
    rows["直近特化(sharpe_W12_k3・WF)"] = calib_and_mc(rec, label="直近特化WF")
    rows["季節R4+G3(旧標準・撤収済)"] = calib_and_mc(seasonal, g3, label="季節R4+G3")
    rows["PD_noV4基準(FN100k現行)"] = calib_and_mc(pd_fn, label="PD_noV4基準")
    rows["PD_noV4 EMonキャップ(FTMO現行)"] = calib_and_mc(pd_ftmo, label="PD_noV4キャップ")
    rows["PD間引きv4込み(Instant現行)"] = calib_and_mc(pd_inst, label="PD間引き")

    print("[3/4] 相関・危機月の重なり")
    mo = pd.DataFrame({"直近特化": monthly(rec), "季節R4G3": monthly(seasonal),
                       "PD_noV4基準": monthly(pd_fn), "PD_noV4キャップ": monthly(pd_ftmo),
                       "PD間引き": monthly(pd_inst)}).dropna()
    corr = mo.corr().round(2)
    overlap = {}
    rec_bad = set(mo["直近特化"].nsmallest(10).index.astype(str))
    for c in mo.columns[1:]:
        bad = set(mo[c].nsmallest(10).index.astype(str))
        overlap[c] = dict(shared_worst10=sorted(rec_bad & bad),
                          n_shared=len(rec_bad & bad))
    joint = {c: round(float(mo[(mo["直近特化"] < -0.02) & (mo[c] < -0.02)].shape[0]
                            / max(1, mo[mo["直近特化"] < -0.02].shape[0])), 2)
             for c in mo.columns[1:]}

    print("[4/4] 保存")
    res = dict(meta=dict(window=f"{W0.date()}..{W1.date()}",
                         method="docs/111逐語・FN P1+8%チャレンジ速度統一(中央3ヶ月)・シード7・2万パス",
                         caveat="docs/171の本番数字(2段階MC・balanceガード)とは機械が別。"
                                "C/D/EのEMonはRG3(riskoff)ゲート込み。Yahoo日足近似。"),
               rows=rows, corr_monthly=corr.to_dict(),
               worst10_overlap_vs_recency=overlap,
               p_joint_bigloss_given_recency_bigloss=joint)
    with open(os.path.join(HERE, "results", "recency_vs_existing.json"), "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print(corr)
    print("保存: results/recency_vs_existing.json")


if __name__ == "__main__":
    main()
