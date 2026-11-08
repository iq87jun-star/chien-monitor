# -*- coding: utf-8 -*-
"""docs/411 Q176(修正・セル 0・2026-11-09 ユーザー「実行」): 帳簿の Mon 系列を EA 実時刻(Dukascopy H1・月曜 4/6/8/10 UTC 建て → 24h 後決済・4 ショット平均・往復 3pip)に置換し、
旧系列(Yahoo 日足 o2o = 月曜 00 → 火曜 00 UTC・docs/409 §8a)との差を 系列統計 と 帳簿 MC(forward/portfolio_sim.run_portfolio)で並べる。
口座カード(forward/account_cards.py)・docs/402 §7 格子(q162b)・docs/409 §5 門 MC(q173b)は deployed_book 置換後に各スクリプトを再実行して比較する。
使い方: cd research && python3 -W ignore queue/q176_mon_h1_timing_fix.py   出力: results/q176_series_compare.csv・results/q176_portfolio_compare.csv"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "forward"))
import numpy as np, pandas as pd
import portfolio_sim as ps
import deployed_book as db
base = ps.base
mon_daily = base.mon_cell            # 旧(日足 o2o・往復 2pip)
mon_h1 = db.mon_cell_h1             # 新(H1 実時刻・往復 3pip・NZDJPY/CADJPY/CHFJPY の H1 欠損期間 2026-01〜 は日足で補完)
P5a, P5b = pd.Timestamp("2021-08-01"), pd.Timestamp("2026-07-29")
def msum(s, a, b):
    x = s[(s.index >= a) & (s.index <= b)]; m = (1 + x).resample("ME").prod() - 1; eq = (1 + m).cumprod()
    return dict(sharpe=float(m.mean() / m.std() * np.sqrt(12)) if m.std() > 0 else np.nan, mean_bps_m=float(m.mean() * 1e4), worst_m=float(m.min()), mdd=float((eq / eq.cummax() - 1).min()), n_m=len(m))
def sh(s, a, b):
    x = s[(s.index >= a) & (s.index <= b)]; m = (1 + x).resample("ME").prod() - 1; return float(m.mean() / m.std() * np.sqrt(12)) if len(m) > 1 and m.std() > 0 else np.nan
COMBOS = {"Mon4(4 通貨等分)": {"AUDJPY": .25, "EURJPY": .25, "GBPJPY": .25, "USDJPY": .25},
          "Mon3(14074882)": {"EURJPY": .333, "USDJPY": .333, "NZDJPY": .334},
          "Mon2 instG(11988011)": {"GBPJPY": .537, "AUDJPY": .463},
          "B 案 Mon 部(6071612/6104736)": {"GBPJPY": .374, "AUDJPY": .322},
          "Mon GBPJPY 単独(531466484 主レグ)": {"GBPJPY": 1.0}}
rows = []
for nm, w in COMBOS.items():
    for form, fn in (("日足(旧)", mon_daily), ("H1 実時刻(新)", mon_h1)):
        s = sum(ps.on_cal(fn(k)) * v for k, v in w.items())
        d = msum(s, P5a, P5b); rows.append(dict(combo=nm, form=form, **d, sharpe_pre=sh(s, ps.PRE0, ps.IS0), sharpe_is=sh(s, ps.IS0, ps.IS1), sharpe_oos=sh(s, ps.OOS0, ps.END), sharpe_all=sh(s, ps.P0, ps.P1)))
    a = sum(ps.on_cal(mon_daily(k)) * v for k, v in w.items()); b = sum(ps.on_cal(mon_h1(k)) * v for k, v in w.items())
    wk = pd.concat([a, b], axis=1).resample("W-FRI").sum(); rows[-1]["weekly_corr_old_new"] = float(wk.corr().iloc[0, 1])
S = pd.DataFrame(rows); S.to_csv("results/q176_series_compare.csv", index=False)
pd.set_option("display.width", 250); print("== 系列(5 年 2021-08〜2026-07・月次) =="); print(S.round(3).to_string(index=False))
# ---- 帳簿 MC(portfolio_sim・N=6000・種 44・docs/349 §9a〜c)を 旧/新 で ----
cfg = json.load(open("config/portfolio_current.json", encoding="utf-8")); prow = []
for form, fn in (("日足(旧)", mon_daily), ("H1 実時刻(新)", mon_h1)):
    db.CELL_FN["Mon"] = fn; ps._LEGS = None; res = ps.run_portfolio(cfg); sm = ps.summarize(res, form)
    prow.append(dict(account="合計(万円/月)", form=form, mean=sm["mean"], p023=sm["p023"], p50=sm["p50"], p977=sm["p977"], p0=sm["p0"]))
    for nm, (jpy, pct) in res["per"].items():
        st = res["stats"][nm]; prow.append(dict(account=nm, form=form, mean=float(pct.mean() * 100), p023=float(np.quantile(pct, .023) * 100), p50=float(np.quantile(pct, .5) * 100), p977=float(np.quantile(pct, .977) * 100), p0=float((pct <= 0).mean()), reach=st["reach"], fail=st["fail"], fail_eval=st["fail_eval"], fail_funded=st["fail_funded"]))
db.CELL_FN["Mon"] = mon_h1; ps._LEGS = None
P = pd.DataFrame(prow); P.to_csv("results/q176_portfolio_compare.csv", index=False)
print("\n== 帳簿 MC(portfolio_sim・合計は 万円/月、口座は %/月) =="); print(P.round(3).to_string(index=False))
