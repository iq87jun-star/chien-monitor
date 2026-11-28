# -*- coding: utf-8 -*-
"""docs/244 Q274(2026-11-24 登録「登録して実行」・セル 3): 季節 EA(季節 R4・RG3)の成績を作り直す。
ユーザー 2026-11-23「季節eaの成績は再現できましたっけ」→ 11/24「登録して実行」。
元の研究コード(research/seasonal_optimize_loyo.py・research/parallel_vs_existing_compare.py)は、ブランチ claude/prop-trading-ea-short-term-8ta3be から変更せずに移した。
データ: Yahoo 日足 2015-01-01〜2026-10-31・20 銘柄(recentfit_screen.fetch で research/data_seasonal に取得・git 管理外)。
照合: (A) 年を抜いた重みの R4(2016〜2025)を元の記録(+0.849%/月・Sharpe 1.282・最大 DD −8.1%・最悪月 −4.71%)と比べる(±0.10 ポイント・±0.15・±2.0 ポイント)。
      (B) 全期間(2016〜2025)で決めた重みを EA の表 WR4 と比べる(ゼロでない欄が一致・差の最大 0.05 以内)。(C) 参考: 全期間の重みを同じ期間に当てた成績。
判定(セル 3): R4 / R4 + RG3 / R3a を、月曜の円クロス 4 本(Mon4)に対して。① 2016〜2025(年を抜いた重み)② 2026-01〜10(重みは 2016〜2025 で固定)の両方で Sharpe が基準 + 0.10 以上、
      かつ全 130 か月の最悪月(月次の変動を基準にそろえた後)が基準より悪くない → 見直しの候補。
使い方: cd research && python3 -W ignore queue/q274_seasonal_r4_rebuild.py <累積セル数>   出力: results/q274_seasonal_r4_rebuild.csv・results/q274_seasonal_r4_weights.csv"""
import os, sys, calendar, datetime as dt
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); RES = os.path.dirname(HERE); os.chdir(RES); sys.path.insert(0, RES)
import recentfit_screen as base
import seasonal_optimize_loyo as so, parallel_vs_existing_compare as pv
DATA = os.path.join(RES, "data_seasonal"); so.DATA = pv.DATA = DATA; END = pd.Timestamp("2026-10-31")
SLV = ["v4", "v7", "v7x", "EMon", "EMonX", "E5", "SJul"]; YEARS = so.LOYO_YEARS
# EA(mql5/【FN100k_口座14074882】季節RG3_1.0倍.mq5)に焼き込まれた表。添字 = 月(1〜12)
WR4 = {"v4":    [0, 1.00, 0.38, 0, 0.092, 0.25, 0, 0.331, 0.483, 0, 0, 0.406],
       "E5":    [0, 0, 0.217, 0, 0, 0.332, 0, 0.328, 0, 0, 0, 0.594],
       "EMon":  [0.689, 0, 0.403, 0.773, 0.084, 0.173, 0, 0.206, 0.517, 0.379, 0, 0],
       "EMonX": [0, 0, 0, 0, 0.114, 0, 0, 0, 0, 0.437, 0.181, 0],
       "v7x":   [0, 0, 0, 0, 0.270, 0, 0, 0, 0, 0, 0, 0],
       "v7":    [0, 0, 0, 0, 0.279, 0, 0, 0, 0, 0, 0, 0],
       "SJul":  [0.311, 0, 0, 0.227, 0.162, 0.245, 1.00, 0.135, 0, 0.184, 0.819, 0]}
ORIG = dict(mean_month_pct=0.849, sharpe=1.282, maxDD=-8.1, worst_month_pct=-4.71)   # results/seasonal_optimize_loyo.json(元の記録)の R4

def fetch_all():
    os.makedirs(DATA, exist_ok=True); base.DATA = DATA; base.P1_EPOCH = 1420070400; base.P2_EPOCH = calendar.timegm(dt.datetime(2026, 11, 1).timetuple()) - 1; n = 0
    for nm in so.SYMBOLS:
        p = os.path.join(DATA, f"{nm}_d.csv")
        if not os.path.exists(p):
            src = base.fetch(nm); d = pd.read_csv(src); d = d[pd.to_datetime(d["timestamp"]) <= END + pd.Timedelta(hours=23, minutes=59)]; d.to_csv(p, index=False); os.remove(src); n += 1
    return n
def rg3_off(names):
    """EA の RiskOffWeek と同じ定義: 前営業日の終値が 200 日平均を上回る銘柄が半数未満、かつ束の 20 日実現ボラ(前日まで)が直近 252 日の 80% 分位を超える週 = 月曜を見送る。"""
    C = pd.DataFrame({nm: pv.load_daily(nm)["close"] for nm in names}).sort_index().ffill()
    above = (C.shift(1) > C.shift(1).rolling(200).mean()); valid = C.shift(1).rolling(200).mean().notna()
    up_maj = (above & valid).sum(axis=1) * 2 >= valid.sum(axis=1)
    vol = (C.pct_change().rolling(20).std(ddof=0) * np.sqrt(252)).shift(1).mean(axis=1, skipna=True)
    thr = vol.rolling(252, min_periods=30).quantile(0.80)
    return ((~up_maj) & (vol > thr) & (valid.sum(axis=1) > 0)).reindex(C.index).fillna(False)
def mon_basket_gated(names, cost):
    off = rg3_off(names); parts = []
    for nm in names:
        d = pv.load_daily(nm); m = (d[d["weekday"] == 0]["o2o"] - cost); m = m[~off.reindex(m.index).fillna(False).values]; parts.append(m.rename(nm))
    w = pd.concat(parts, axis=1).mean(axis=1, skipna=True).dropna(); skipped = int(off[off.index.dayofweek == 0].sum()); total = int((off.index.dayofweek == 0).sum())
    return pv.to_monthly(w), skipped, total
def mon4():
    acc = None
    for p in ("GBPJPY", "EURJPY", "AUDJPY", "USDJPY"):
        d = pv.load_daily(p); m = pv.to_monthly((d[d["weekday"] == 0]["o2o"] - 2 * pv.pip_size(p) / d[d["weekday"] == 0]["open"]).dropna()); acc = m if acc is None else acc.add(m, fill_value=0.0)
    return acc / 4.0
def wmap(df_train, rule, years):
    mu, sd = so.month_stats(df_train, years); return {m: so.weights_for(rule, mu.loc[m], sd.loc[m]) for m in range(1, 13)}
def apply(df, W):
    return pd.Series({i: sum(r.get(k, 0.0) * v for k, v in W[i.month].items()) for i, r in df.iterrows()}).sort_index()
def loyo(df_train, df_apply, rule):
    out = []
    for y in YEARS:
        W = wmap(df_train, rule, [t for t in YEARS if t != y]); out.append(apply(df_apply[df_apply.index.year == y], W))
    return pd.concat(out).sort_index()
def st(s):
    m = so.metrics(s); eq = (1 + s).cumprod(); m["ann_pct"] = round(float(eq.iloc[-1] ** (12 / len(s)) - 1) * 100, 2); m["vol_month_pct"] = round(float(s.std() * 100), 3); return m

if __name__ == "__main__":
    cum = int(sys.argv[1]); N = 3; nf = fetch_all()
    rng = {nm: (str(pv.load_daily(nm).index[0].date()), str(pv.load_daily(nm).index[-1].date()), len(pv.load_daily(nm))) for nm in ("GBPJPY", "US500", "FR40", "XAUUSD", "CHFJPY")}
    print(f"データ: 新規取得 {nf} 銘柄・{len(so.SYMBOLS)} 銘柄・例 {rng}", flush=True)
    df = so.build_sleeves(1.0); df = df[df.index <= pd.Period("2026-10", "M")]; dfL = df[(df.index.year >= 2016) & (df.index.year <= 2025)]; df26 = df[df.index.year == 2026]
    print(f"枠の月次: {df.index[0]}〜{df.index[-1]}({len(df)} か月)。枠ごとの平均月利 %(2016〜2025): {(dfL.mean() * 100).round(3).to_dict()}", flush=True)
    # ---- 照合 A: 年を抜いた重みの R4(元の関数そのまま)
    sA = so.loyo_series(dfL, "R4"); mA = so.metrics(sA)
    okA = abs(mA["mean_month_pct"] - ORIG["mean_month_pct"]) <= 0.10 and abs(mA["sharpe"] - ORIG["sharpe"]) <= 0.15 and abs(mA["maxDD"] - ORIG["maxDD"]) <= 2.0
    print(f"\n照合 A(年を抜いた重みの R4・2016〜2025): 今回 {mA} / 元 {ORIG} → {'再現' if okA else '再現せず'}")
    print("  参考(元の記録): R0 0.38/1.027/−5.56、R1 0.901/1.16/−13.46、R3a 0.51/1.326/−4.52。今回:", {r: (so.metrics(so.loyo_series(dfL, r))["mean_month_pct"], so.metrics(so.loyo_series(dfL, r))["sharpe"], so.metrics(so.loyo_series(dfL, r))["maxDD"]) for r in ("R0", "R1", "R3a")})
    # ---- 照合 B: 全期間で決めた重み vs EA の表
    Wall = wmap(dfL, "R4", YEARS); rowsW = []; maxdiff = 0.0; same_nz = True
    for k in SLV:
        for m in range(1, 13):
            a = float(Wall[m].get(k, 0.0)); b = WR4[k][m - 1]; rowsW.append(dict(sleeve=k, month=m, rebuilt=round(a, 3), ea_table=b, diff=round(a - b, 3))); maxdiff = max(maxdiff, abs(a - b)); same_nz &= ((a > 0) == (b > 0))
    WD = pd.DataFrame(rowsW); WD.to_csv("results/q274_seasonal_r4_weights.csv", index=False); okB = same_nz and maxdiff <= 0.05
    print(f"\n照合 B(全期間の重み vs EA の表): ゼロでない欄の一致 {same_nz}・差の最大 {maxdiff:.3f} → {'表を再現' if okB else '表は再現せず'}")
    print(WD.pivot(index="sleeve", columns="month", values="rebuilt").reindex(SLV).to_string()); bad = WD[WD["diff"].abs() > 0.05]; print("  差が 0.05 を超える欄:", bad.to_dict("records") if len(bad) else "なし")
    # ---- 参考 C: 後知恵込み(全期間の重みを同じ期間に)
    WEA = {m: {k: WR4[k][m - 1] for k in SLV if WR4[k][m - 1] > 0} for m in range(1, 13)}
    isR = st(apply(dfL, Wall)); isE = st(apply(dfL, WEA)); print(f"\n参考 C(後知恵込み・2016〜2025・倍率 1・ガードと G3 なし): 作り直した重み {isR} / EA の表 {isE}。当時の値: 年率 +18.6%・最大 DD −10.9%(G3・RG3・日次ガード込みの日次の再構築)")
    # ---- RG3 の系列
    dfG = df.copy(); gE, skE, totE = mon_basket_gated(["NAS100", "US500", "GER40"], 3e-4); gX, skX, totX = mon_basket_gated(so.EMONX, 3e-4)
    dfG["EMon"] = gE.reindex(dfG.index).fillna(0.0); dfG["EMonX"] = gX.reindex(dfG.index).fillna(0.0); dfGL = dfG[(dfG.index.year >= 2016) & (dfG.index.year <= 2025)]; dfG26 = dfG[dfG.index.year == 2026]
    print(f"\nRG3: 見送った月曜 EMon {skE} / {totE} 回・EMonX {skX} / {totX} 回(2015〜2026-10)")
    # ---- 判定
    M4 = mon4(); M4 = M4[(M4.index >= pd.Period("2016-01", "M")) & (M4.index <= pd.Period("2026-10", "M"))]; b1 = M4[M4.index.year <= 2025]; b2 = M4[M4.index.year == 2026]
    S1 = {"基準: 月曜の円クロス 4 本": b1, "R4(年を抜いた重み)": loyo(dfL, dfL, "R4"), "R4 + RG3": loyo(dfL, dfGL, "R4"), "R3a(固定に月別 25%)": loyo(dfL, dfL, "R3a"), "参照: R0 固定配分": loyo(dfL, dfL, "R0"), "参照: R1 月別の比例": loyo(dfL, dfL, "R1")}
    W3 = wmap(dfL, "R3a", YEARS); W0 = wmap(dfL, "R0", YEARS); W1 = wmap(dfL, "R1", YEARS)
    S2 = {"基準: 月曜の円クロス 4 本": b2, "R4(年を抜いた重み)": apply(df26, WEA), "R4 + RG3": apply(dfG26, WEA), "R3a(固定に月別 25%)": apply(df26, W3), "参照: R0 固定配分": apply(df26, W0), "参照: R1 月別の比例": apply(df26, W1)}
    assert np.allclose(S1["R4(年を抜いた重み)"].values, sA.values)
    rows = []; ball = pd.concat([b1, b2]); bst1, bst2 = st(b1), st(b2); bw = round(float(ball.min() * 100), 2)
    for nm in S1:
        a1, a2 = st(S1[nm]), st(S2[nm]); allm = pd.concat([S1[nm], S2[nm]]); k = ball.std() / allm.std(); wm = round(float((allm * k).min() * 100), 2); sa = st(allm); judged = not nm.startswith(("基準", "参照"))
        ok = (a1["sharpe"] >= bst1["sharpe"] + 0.10) and (a2["sharpe"] >= bst2["sharpe"] + 0.10) and (wm >= bw)
        rows.append(dict(arm=nm, mean_month_1=a1["mean_month_pct"], ann_1=a1["ann_pct"], sharpe_1=a1["sharpe"], maxDD_1=a1["maxDD"], worst_1=a1["worst_month_pct"],
                         sum_2026=round(float(S2[nm].sum() * 100), 2), mean_month_2=a2["mean_month_pct"], sharpe_2=a2["sharpe"], maxDD_2=a2["maxDD"], worst_2=a2["worst_month_pct"],
                         sharpe_all=sa["sharpe"], ann_all=sa["ann_pct"], maxDD_all=sa["maxDD"], ann_all_volmatched=st(allm * k)["ann_pct"], maxDD_all_volmatched=st(allm * k)["maxDD"], worst_all_volmatched=wm,
                         cells=1 if judged else 0, verdict=("見直しの候補" if ok else "現行どおり") if judged else ("基準" if nm.startswith("基準") else "—")))
    D = pd.DataFrame(rows); D.to_csv("results/q274_seasonal_r4_rebuild.csv", index=False); assert int(D.cells.sum()) == N
    pd.set_option("display.width", 320); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 40)
    print(f"\n== Q274(累積セル {cum} + {N} = {cum + N}・倍率 1・_1 = 2016〜2025(年を抜いた重み)・_2 = 2026-01〜10(重みは 2016〜2025 で固定)) =="); print(D.to_string(index=False))
    Y = pd.DataFrame({nm: pd.concat([S1[nm], S2[nm]]).groupby(lambda p: p.year).sum() * 100 for nm in S1}).round(1); print("\n年別の合計 %:"); print(Y.T.to_string())
    M26 = pd.DataFrame({nm: S2[nm] * 100 for nm in S1}).round(2); print("\n2026 年の月別 %:"); print(M26.T.to_string())
    print("\n実口座(FN 14074882・季節 RG3 1.0 倍): 2026-08 は +2.45%(docs/205)。紙上の同じ月: R4(EA の表)", round(float(S2["R4(年を抜いた重み)"].get(pd.Period("2026-08", "M"), np.nan) * 100), 2), "% / R4 + RG3", round(float(S2["R4 + RG3"].get(pd.Period("2026-08", "M"), np.nan) * 100), 2), "%")
    j = D[D.cells == 1]; print(f"\n判定: 見直しの候補 {int((j.verdict == '見直しの候補').sum())} / {len(j)} 件・照合 A {'再現' if okA else '再現せず'}・照合 B {'表を再現' if okB else '表は再現せず'}")
