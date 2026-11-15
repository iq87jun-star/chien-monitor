# -*- coding: utf-8 -*-
"""docs/244 Q245(診断・セル 0・2026-11-16 登録): 月曜の円クロス(4 本・E1)に月曜の指数と水曜のロールを足したときの分散。
M = Mon4 + E1(index = 月曜)。I = NAS100・US500 等分の月曜 13 UTC 24h(参考 IF = US30・JP225 の形 F)。片方の足が無い週はある銘柄だけで代用。R = Roll5(門 2.0pp・水曜 20 UTC → 木曜 00 UTC の売り)を週の月曜にそろえる。
使い方: cd research && python3 -W ignore queue/q245_diversification_mon_idx_roll.py   出力: results/q245_diversification_mon_idx_roll.csv・_corr.csv・_tail.csv"""
import sys, os
_ARGV = list(sys.argv)
from q_common import *
from q147_roll_rate_diff_gate import stats
from q240_weekend_premium_predictions import frame, series, idx_shot
from q231_near_miss_rotation_and_state_exit import f_series
from q228_roll5_vix_x_sma200_score import roll5_score
PRE1 = IS0 - pd.Timedelta(hours=1); T0 = pd.Timestamp("2018-01-08"); WIN = (("前窓(2018-01〜)", T0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END), ("全期間(2018-01〜)", T0, END))
def legs():
    P = frame(); M = series(P, "E1"); M24 = series(P, "base"); hot = P.groupby(level=0).hot.first()
    I = pd.concat([idx_shot(s, 0) for s in ("NAS100", "US500")], axis=1).mean(axis=1); IF = pd.concat([f_series(s, "F") for s in ("US30", "JP225")], axis=1).mean(axis=1)   # 片方の足が無い週は、ある銘柄だけの値で代用(NAS100 の H1 は月曜 13 UTC の足が無い週が 2〜3 割ある)
    R = roll5_score("base"); R.index = R.index - pd.to_timedelta(R.index.dayofweek, unit="D"); R = R.groupby(level=0).sum()
    X = pd.DataFrame({"M": M, "M24": M24, "I": I, "IF": IF, "R": R}).reindex(M.index); X["hot"] = hot.reindex(X.index); return X[X.index >= T0].fillna({"I": 0.0, "IF": 0.0, "R": 0.0})
def perf(x):
    m = x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1); eq = (1 + x).cumprod(); dd = float((eq / eq.cummax() - 1).min())
    return dict(sharpe=round(float(x.mean() / x.std() * np.sqrt(52)), 2) if x.std() > 0 else 0.0, worst_month=round(float(m.min()) * 100, 2), maxdd=round(dd * 100, 2), cum=round(float(eq.iloc[-1] - 1) * 100, 1), plus_months=f"{int((m > 0).sum())}/{len(m)}", week_sd_bps=round(float(x.std()) * 1e4, 1), active_weeks=int((x != 0).sum()))
if __name__ == "__main__":
    X = legs(); rows = []; cor = []; tail = []
    W_T = {"M": 8.0, "I": 2.0, "R": 4.5}                                        # トパーズの配備の比率(円クロスの束 8.0・指数 各 1.0 = 等分の束 2.0・ロール 4.5)
    sd = {k: float(X[k].std()) for k in ("M", "I", "R")}; W_E = {k: 1.0 / sd[k] for k in sd}; s = sum(W_E.values()); W_E = {k: v / s * 3 for k, v in W_E.items()}   # 等リスク(全期間の週次のばらつきの逆数)
    C = {"M 円クロス 4 本・E1(×1)": X.M, "I 指数 NAS100・US500(×1)": X.I, "IF 指数 US30・JP225 形 F(×1・参考)": X.IF, "R ロール 5 本(×1)": X.R,
         "トパーズの比率: M のみ(×8.0)": 8.0 * X.M, "トパーズの比率: M + I": 8.0 * X.M + 2.0 * X.I, "トパーズの比率: M + R": 8.0 * X.M + 4.5 * X.R, "トパーズの比率: M + I + R": 8.0 * X.M + 2.0 * X.I + 4.5 * X.R,
         "等リスク: M のみ": W_E["M"] * X.M, "等リスク: M + I + R": sum(W_E[k] * X[k] for k in W_E), "参考 トパーズの比率・円クロスが常に 24h: M24 + I + R": 8.0 * X.M24 + 2.0 * X.I + 4.5 * X.R}
    for nm, x in C.items():
        for w, a, e in WIN: rows.append(dict(series=nm, window=w, **perf(x[(x.index >= a) & (x.index <= e)])))
    D = pd.DataFrame(rows); D.to_csv("results/q245_diversification_mon_idx_roll.csv", index=False)
    for w, a, e in WIN:
        y = X[(X.index >= a) & (X.index <= e)]
        for g, z in (("全部", y), ("VIX > 25", y[y.hot == True]), ("VIX ≤ 25", y[y.hot != True])):
            c = z[["M", "M24", "I", "IF", "R"]].corr(); cor.append(dict(window=w, group=g, weeks=len(z), M_I=round(c.loc["M", "I"], 2), M_IF=round(c.loc["M", "IF"], 2), M_R=round(c.loc["M", "R"], 2), I_R=round(c.loc["I", "R"], 2), M24_I=round(c.loc["M24", "I"], 2), M24_R=round(c.loc["M24", "R"], 2)))
    CR = pd.DataFrame(cor); CR.to_csv("results/q245_diversification_mon_idx_roll_corr.csv", index=False)
    for nm, key in (("M 円クロスが悪い週(下位 10%)", "M"), ("I 指数が悪い週(下位 10%)", "I"), ("R ロールが悪い週(下位 10%)", "R")):
        thr = X[key].quantile(0.1); z = X[X[key] <= thr]; tail.append(dict(condition=nm, weeks=len(z), M_bps=round(float(z.M.mean()) * 1e4, 1), I_bps=round(float(z.I.mean()) * 1e4, 1), R_bps=round(float(z.R.mean()) * 1e4, 1), I_minus_share=round(float((z.I < 0).mean()) * 100, 0), R_minus_share=round(float((z.R < 0).mean()) * 100, 0), M_minus_share=round(float((z.M < 0).mean()) * 100, 0)))
    tail.append(dict(condition="全週の平均", weeks=len(X), M_bps=round(float(X.M.mean()) * 1e4, 1), I_bps=round(float(X.I.mean()) * 1e4, 1), R_bps=round(float(X.R.mean()) * 1e4, 1), I_minus_share=round(float((X.I < 0).mean()) * 100, 0), R_minus_share=round(float((X.R < 0).mean()) * 100, 0), M_minus_share=round(float((X.M < 0).mean()) * 100, 0)))
    TL = pd.DataFrame(tail); TL.to_csv("results/q245_diversification_mon_idx_roll_tail.csv", index=False)
    full = X; sdT = {k: float((W_T[k] * full[k]).std()) for k in W_T}; comb = float(sum(W_T[k] * full[k] for k in W_T).std())
    pd.set_option("display.width", 340); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 300); pd.set_option("display.max_colwidth", 70)
    print("Q245(診断・セル 0) 週数", len(X), X.index.min().date(), "〜", X.index.max().date(), " 等リスクの比率", {k: round(v, 2) for k, v in W_E.items()}); print(D.to_string(index=False)); print("\n== 週次の相関 =="); print(CR.to_string(index=False)); print("\n== 悪い週の重なり(全期間・×1 の平均 bps) =="); print(TL.to_string(index=False))
    print("\nトパーズの比率での週次のばらつき(bps): 単独", {k: round(v * 1e4, 1) for k, v in sdT.items()}, " 単純合計", round(sum(sdT.values()) * 1e4, 1), " 合成", round(comb * 1e4, 1), " 合成 / 単純合計", round(comb / sum(sdT.values()), 2), " 無相関なら", round(np.sqrt(sum(v * v for v in sdT.values())) * 1e4, 1))
