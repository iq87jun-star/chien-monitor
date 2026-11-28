# -*- coding: utf-8 -*-
"""docs/244 Q282(2026-11-24 登録「登録して実行」・セル 14): 相場の外の情報 2 つ — 週末の暗号資産の動き / 記事の本数で作る不確実性の指数(EPU・GPR)。
信号(月曜の建ての前に分かる値・その週より前の値だけで基準を作る):
  BTC = 金曜の終値 → 日曜の終値の騰落(Yahoo 日足)÷ 直前 52 週の週末の騰落の標準偏差。
  EPU = 米国の経済政策の不確実性の指数(FRED USEPUINDXD)の土曜までの 7 日平均。直前 52 週の同じ値(対数)で z。GPR = 地政学リスクの指数(GPRD)を同じ作り方で z。
型(セル 14): BTC = z ≤ −1 / −2 を見送る・z ≥ +1 / +2 を見送る・z ≤ −1 / −2 を 1.5 倍(6)。EPU・GPR = z ≥ +1 / +2 を見送る・1.5 倍(各 4)。
口座の物差しと判定は Q278・Q279 と同じ(FTMO 50k の本口座後・①② の両方で現行を上回る)。
データ: data_live/BTCUSD_rf.csv(Yahoo)・data_ext/USEPUINDXD.csv(https://fred.stlouisfed.org/graph/fredgraph.csv?id=USEPUINDXD)・data_ext/gpr_daily.xls(https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls)。data_* は git 管理外。
使い方: cd research && PYTHONPATH=queue python3 -W ignore queue/q282_outside_info_btc_weekend_epu_gpr.py <累積セル数>   出力: results/q282_outside_info.csv・results/q282_outside_info_weeks.csv"""
import os, sys
_ARGV = list(sys.argv)
import q278_mon_detail_grid_funded_ranking as m
np, pd, n3 = m.np, m.pd, m.n3
def mondays(): return pd.date_range(m.P0 + pd.Timedelta(days=(7 - m.P0.dayofweek) % 7), m.P1, freq="7D")
def sig_btc():
    b = pd.read_csv("data_live/BTCUSD_rf.csv"); b["d"] = pd.to_datetime(b["timestamp"]).dt.normalize(); c = b.drop_duplicates("d", keep="last").set_index("d")["close"].astype(float)
    M = pd.date_range("2016-01-04", m.P1, freq="7D"); wr = pd.Series({d: (c.get(d - pd.Timedelta(days=1), np.nan) / c.get(d - pd.Timedelta(days=3), np.nan) - 1) for d in M}).dropna()
    return (wr / wr.rolling(52).std().shift(1)).dropna(), wr
def sig_level(daily):
    M = pd.date_range("2014-01-06", m.P1, freq="7D"); m7 = daily.rolling(7).mean(); v = pd.Series({d: m7.get(d - pd.Timedelta(days=2), np.nan) for d in M}).dropna(); lv = np.log(v)
    return ((lv - lv.rolling(52).mean().shift(1)) / lv.rolling(52).std().shift(1)).dropna(), v
def sig_epu():
    e = pd.read_csv("data_ext/USEPUINDXD.csv"); e["d"] = pd.to_datetime(e.iloc[:, 0]); s = pd.to_numeric(e.iloc[:, 1], errors="coerce"); s.index = e["d"]; return sig_level(s.dropna().asfreq("D").ffill())
def sig_gpr():
    g = pd.read_excel("data_ext/gpr_daily.xls"); s = pd.Series(pd.to_numeric(g["GPRD"], errors="coerce").values, index=pd.to_datetime(g["date"])).dropna(); return sig_level(s.asfreq("D").ffill())
RULES = [("BTC", "週末の BTC が下げた週(z ≤ −1)を見送る", lambda z: z <= -1, 0.0), ("BTC", "週末の BTC が下げた週(z ≤ −2)を見送る", lambda z: z <= -2, 0.0), ("BTC", "週末の BTC が上げた週(z ≥ +1)を見送る", lambda z: z >= 1, 0.0), ("BTC", "週末の BTC が上げた週(z ≥ +2)を見送る", lambda z: z >= 2, 0.0),
         ("BTC", "週末の BTC が下げた週(z ≤ −1)を 1.5 倍", lambda z: z <= -1, 1.5), ("BTC", "週末の BTC が下げた週(z ≤ −2)を 1.5 倍", lambda z: z <= -2, 1.5),
         ("EPU", "政策の不確実性が高い週(z ≥ +1)を見送る", lambda z: z >= 1, 0.0), ("EPU", "政策の不確実性が高い週(z ≥ +2)を見送る", lambda z: z >= 2, 0.0), ("EPU", "政策の不確実性が高い週(z ≥ +1)を 1.5 倍", lambda z: z >= 1, 1.5), ("EPU", "政策の不確実性が高い週(z ≥ +2)を 1.5 倍", lambda z: z >= 2, 1.5),
         ("GPR", "地政学リスクが高い週(z ≥ +1)を見送る", lambda z: z >= 1, 0.0), ("GPR", "地政学リスクが高い週(z ≥ +2)を見送る", lambda z: z >= 2, 0.0), ("GPR", "地政学リスクが高い週(z ≥ +1)を 1.5 倍", lambda z: z >= 1, 1.5), ("GPR", "地政学リスクが高い週(z ≥ +2)を 1.5 倍", lambda z: z >= 2, 1.5)]
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 14; items, cap, g = m.norm_items("521100397"); fac = m.make_fac(items, False, 0.5); MULT, PAD = 3.75, 0.01
    n3["paths_fac"] = m.paths_v; m.VAR["v"] = m.BASE; b, _ = m.evaluate(items, g, fac, MULT, PAD); print("現行:", b, flush=True)
    Z = {"BTC": sig_btc()[0], "EPU": sig_epu()[0], "GPR": sig_gpr()[0]}
    P = m.paths_v(items, None, fac, m.P0, m.P1); wk = pd.Series({pd.Timestamp(p["d"]): p["fin"] * MULT * 100 for p in P}); WK = pd.DataFrame({"mon_pnl_pct": wk});
    for k, z in Z.items(): WK[k] = z.reindex(WK.index)
    V = pd.read_csv("data_ext/VIX_History.csv"); V["d"] = pd.to_datetime(V["DATE"]); vix = V.set_index("d")["CLOSE"].astype(float); WK["VIX_fri"] = vix.reindex(WK.index - pd.Timedelta(days=3), method="ffill").values; WK["w1"] = WK.index >= m.PM; WK.to_csv("results/q282_outside_info_weeks.csv")
    print(f"週の数 {len(WK)}・信号が付く週: " + " / ".join(f"{k} {int(WK[k].notna().sum())}" for k in Z)); print("信号どうしと VIX・月曜の損益の相関:"); print(WK[["BTC", "EPU", "GPR", "VIX_fri", "mon_pnl_pct"]].corr().round(2).to_string())
    for k in Z:
        x = WK.dropna(subset=[k]).copy(); x["band"] = pd.cut(x[k], [-99, -2, -1, 0, 1, 2, 99]); print(f"\n{k} の帯ごとの月曜の平均損益 %(本口座後の数量):"); print(x.groupby("band", observed=True).agg(n=("mon_pnl_pct", "size"), mean=("mon_pnl_pct", "mean"), neg_share=("mon_pnl_pct", lambda v: float((v < 0).mean())), n_w1=("w1", "sum")).round(3).to_string())
    rows = [dict(signal="—", rule="現行", n_flag=0, n_flag_w1=0, n_flag_w2=0, mean_flag=np.nan, mean_rest=round(float(WK.mon_pnl_pct.mean()), 3), cells=0, verdict="基準", **b)]
    for sg, nm, fn, mult in RULES:
        z = Z[sg]; flag = {d for d, v in z.items() if fn(v) and m.P0 <= d <= m.P1}; fc = {k: {d: (v * mult if d in flag else v) for d, v in dd.items()} for k, dd in fac.items()}
        for k in fc:
            for d in flag: fc[k].setdefault(d, mult)
        r, _ = m.evaluate(items, g, fc, MULT, PAD); fl = WK[WK.index.isin(flag)]; rs = WK[~WK.index.isin(flag)]; ok = m.win_ok(r, b, "a") and m.win_ok(r, b, "b")
        rows.append(dict(signal=sg, rule=nm, n_flag=len(fl), n_flag_w1=int(fl.w1.sum()), n_flag_w2=int((~fl.w1).sum()), mean_flag=round(float(fl.mon_pnl_pct.mean()), 3) if len(fl) else np.nan, mean_rest=round(float(rs.mon_pnl_pct.mean()), 3), cells=1, verdict="変更候補" if ok else "現行どおり", ok_w1=m.win_ok(r, b, "a"), ok_w2=m.win_ok(r, b, "b"), **r)); print("done", nm, flush=True)
    D = pd.DataFrame(rows); D.to_csv("results/q282_outside_info.csv", index=False); assert int(D.cells.sum()) == N
    pd.set_option("display.width", 330); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 46)
    print(f"\n== Q282(累積セル {cum} + {N} = {cum + N}・FTMO 50k 本口座後・mean_flag / mean_rest = 該当する週 / それ以外の週の月曜の平均損益 %) =="); print(D[["rule", "n_flag", "n_flag_w1", "n_flag_w2", "mean_flag", "mean_rest", "s10", "p10", "s5a", "p5a", "s5b", "p5b", "ok_w1", "ok_w2", "verdict"]].to_string(index=False))
    print(f"\n判定: 変更候補 {int((D.verdict == '変更候補').sum())} / {N} 件")
