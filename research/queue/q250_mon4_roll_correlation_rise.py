# -*- coding: utf-8 -*-
"""docs/244 Q250(診断・セル 0・2026-11-16 登録): 月曜の円クロス(Mon4・E1)と水曜のロール(Roll5・門 2.0pp)の週次の相関が 2025 年以降に上がった理由。
年ごと・窓ごとの相関(順位相関も)、寄与の大きい週を除いた相関、ロールの門が開いている通貨の数、通貨ごとのロールとの相関、週の円クロスの向きとの関係。
使い方: cd research && python3 -W ignore queue/q250_mon4_roll_correlation_rise.py   出力: results/q250_mon4_roll_corr_year.csv・_detail.csv"""
import sys, os
from q_common import *
from scipy import stats as sps
from q240_weekend_premium_predictions import frame as mframe, series as mseries, MON4
from q228_roll5_vix_x_sma200_score import frame as rframe, PAIRS as RPAIRS
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END), ("全期間", PRE0, END))
def wk(i): i = pd.DatetimeIndex(i); return i - pd.to_timedelta(i.dayofweek, unit="D")
if __name__ == "__main__":
    PM_ = mframe(); M = mseries(PM_, "E1"); M24 = mseries(PM_, "base"); PR, days = rframe(); PR = PR.assign(week=wk(PR.index), x=PR.r * PR.g.astype(float))
    R = (PR.groupby("week").x.sum() / len(RPAIRS)).reindex(M.index).fillna(0.0); RS = {s: PR[PR.sym == s].groupby("week").x.sum().reindex(M.index).fillna(0.0) for s in RPAIRS}; NG = PR.groupby("week").g.sum().reindex(M.index).fillna(0)
    o = {s: load(s)["open"] for s in MON4}; W = sum((o[s].reindex(M.index + pd.Timedelta(days=4, hours=20)).values / o[s].reindex(M.index).values - 1) for s in MON4) / 4; W = pd.Series(W, index=M.index)          # 週の円クロスの向き(月曜 00 → 金曜 20 UTC・4 本平均)
    X = pd.DataFrame({"M": M, "M24": M24, "R": R, "W": W, "ng": NG}); rows = []
    def c(a, b): z = pd.concat([a, b], axis=1).dropna(); return (round(float(np.corrcoef(z.iloc[:, 0], z.iloc[:, 1])[0, 1]), 2), round(float(sps.spearmanr(z.iloc[:, 0], z.iloc[:, 1])[0]), 2), len(z)) if len(z) > 5 and z.iloc[:, 0].std() > 0 and z.iloc[:, 1].std() > 0 else (None, None, len(z))
    for y in sorted(set(X.index.year)):
        x = X[X.index.year == y]; a = c(x.M, x.R); b = c(x.M24, x.R); rows.append(dict(period=str(y), weeks=len(x), roll_active_weeks=int((x.R != 0).sum()), gate_open_pairs=round(float(x.ng.mean()), 2), corr_M_R=a[0], rank_corr_M_R=a[1], corr_M24_R=b[0], roll_sd_bps=round(float(x.R.std()) * 1e4, 1), M_sd_bps=round(float(x.M.std()) * 1e4, 1), corr_M_week=c(x.M, x.W)[0], corr_R_week=c(x.R, x.W)[0]))
    for w, a_, b_ in WIN:
        x = X[(X.index >= a_) & (X.index <= b_)]; a = c(x.M, x.R); b = c(x.M24, x.R); rows.append(dict(period=w, weeks=len(x), roll_active_weeks=int((x.R != 0).sum()), gate_open_pairs=round(float(x.ng.mean()), 2), corr_M_R=a[0], rank_corr_M_R=a[1], corr_M24_R=b[0], roll_sd_bps=round(float(x.R.std()) * 1e4, 1), M_sd_bps=round(float(x.M.std()) * 1e4, 1), corr_M_week=c(x.M, x.W)[0], corr_R_week=c(x.R, x.W)[0]))
    Y = pd.DataFrame(rows); Y.to_csv("results/q250_mon4_roll_corr_year.csv", index=False)
    det = []; x = X[(X.index >= OOS0) & (X.index <= END)]; zm = (x.M - x.M.mean()) / x.M.std(); zr = (x.R - x.R.mean()) / x.R.std(); pr = (zm * zr).sort_values(ascending=False); n = len(x); r0 = float(np.corrcoef(x.M, x.R)[0, 1])
    det.append(dict(item="OOS 全週", n=n, corr=round(r0, 2), t=round(r0 * np.sqrt((n - 2) / (1 - r0 * r0)), 2)))
    for k in (1, 3, 5, 10):
        y = x.drop(pr.index[:k]); r = float(np.corrcoef(y.M, y.R)[0, 1]); det.append(dict(item=f"OOS 寄与の大きい {k} 週を除く", n=len(y), corr=round(r, 2), t=round(r * np.sqrt((len(y) - 2) / (1 - r * r)), 2)))
    for s in RPAIRS:
        for w, a_, b_ in WIN[1:3]: z = X[(X.index >= a_) & (X.index <= b_)]; r = c(z.M, RS[s].reindex(z.index)); det.append(dict(item=f"{w} Mon4 × ロール {s}", n=int((RS[s].reindex(z.index) != 0).sum()), corr=r[0], t=None))
    for w, a_, b_ in WIN[:3]:
        z = X[(X.index >= a_) & (X.index <= b_)]
        for gn, m in (("月曜がプラスの週", z.M > 0), ("月曜がマイナスの週", z.M < 0)): det.append(dict(item=f"{w} {gn}: ロールの平均 bps", n=int(m.sum()), corr=round(float(z.R[m].mean()) * 1e4, 2), t=None))
    DT = pd.DataFrame(det); DT.to_csv("results/q250_mon4_roll_corr_detail.csv", index=False); top = pd.DataFrame({"M_bps": (x.M.reindex(pr.index[:8]) * 1e4).round(1), "R_bps": (x.R.reindex(pr.index[:8]) * 1e4).round(1), "week_pct": (x.W.reindex(pr.index[:8]) * 100).round(2)})
    pd.set_option("display.width", 300); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 200); pd.set_option("display.max_colwidth", 60)
    print("Q250(診断・セル 0)"); print(Y.to_string(index=False)); print(); print(DT.to_string(index=False)); print("\nOOS で寄与の大きい 8 週(月曜の損益 bps・ロールの損益 bps・週の円クロスの向き %):"); print(top.to_string())
