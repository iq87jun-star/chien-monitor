# -*- coding: utf-8 -*-
"""docs/262 Q18: 旧 19 銘柄の bid/ask(2024-01〜2026-08)で往復コストを実測し、docs/249 で無効になった Sess 8 セル + A 案 S3 を実測コストで再検定する診断。
A) 実測往復コスト表: 銘柄 × 建て時刻(9 窓)。LONG = ask.open で建て bid.open で出る、SHORT = bid.open で建て ask.open で出る。中値 open→open との差 = 往復コスト。
B) 9 セル(Sess 8: EA4 の InpSessLegs・月〜木・4h SHORT / A 案 S3: 木曜 16 UTC +6h USDCHF SHORT)を {仮定 3pip, 実測 bid/ask} の 2 通りで 2024-01〜2026-08(32 ヶ月)評価。自己検証: 実測 LONG+SHORT = −実測往復。
使い方: python3 queue/q18_measured_cost_sess_retest.py <累積セル数>"""
import sys, numpy as np, pandas as pd
from q_common import *
cum = int(sys.argv[1]); N = 11   # Sess 8 + S3 + S3 の出口変種 2(20/21 UTC・21〜23 UTC のスプレッド拡大を避ける診断)
OLD = ["EURGBP", "USDCHF", "NZDUSD", "AUDUSD", "CHFJPY", "GBPJPY", "EURJPY", "AUDJPY", "USDJPY", "CADJPY", "NZDJPY", "EURUSD", "GBPUSD", "EURAUD", "GBPAUD", "XAUUSD", "GER40", "NAS100", "US500"]
WINS = [(h, 4) for h in (0, 4, 8, 12, 16, 20)] + [(h, 8) for h in (0, 8, 16)]
A0 = pd.Timestamp("2024-01-01")
def load_ba(sym):
    b = load(sym); a = pd.read_csv(f"data_dukascopy/{sym}_hour_ask.csv.gz"); a["t"] = pd.to_datetime(a["timestamp"]); a = a.set_index("t").sort_index(); a = a[~a.index.duplicated(keep="last")]
    j = b[["open"]].rename(columns={"open": "bid"}).join(a[["open"]].rename(columns={"open": "ask"}), how="inner"); j = j[j.index >= A0]; j["mid"] = (j.bid + j.ask) / 2
    return j
# A) 実測往復コスト表
rows = []
for sym in OLD:
    j = load_ba(sym); pipv = base.pip_size(sym)
    for h0, span in WINS:
        t = j.index[(j.index.hour == h0) & (j.index.dayofweek <= 4)]; te = t + pd.Timedelta(hours=span)
        e_ask = j.ask.reindex(t).values; e_bid = j.bid.reindex(t).values; x_ask = j.ask.reindex(te).values; x_bid = j.bid.reindex(te).values; m0 = j.mid.reindex(t).values; m1 = j.mid.reindex(te).values
        ok = ~np.isnan(x_bid) & ~np.isnan(x_ask)
        rt_long = (m1[ok] / m0[ok] - 1) - (x_bid[ok] / e_ask[ok] - 1)      # 中値リターン − 実測 LONG リターン = 往復コスト(比率)
        rows.append(dict(symbol=sym, window=f"{h0:02d}-{(h0+span)%24:02d}", n=int(ok.sum()), rt_bps_median=round(float(np.median(rt_long)) * 1e4, 2), rt_bps_mean=round(float(np.mean(rt_long)) * 1e4, 2), rt_pip_median=(round(float(np.median(rt_long * m0[ok])) / pipv, 2) if (sym not in NONFX_COST and base.IDX_COST.get(sym) is None) else np.nan), assumed_bps=round(float(np.median(cost(sym, m0[ok]))) * 1e4, 2)))
T = pd.DataFrame(rows); T.to_csv("results/q18_measured_roundtrip_cost.csv", index=False)
print("== A) 実測往復コスト(bps・中央値)= 銘柄 × 窓 =="); print(T.pivot(index="symbol", columns="window", values="rt_bps_median").loc[OLD].to_string()); print("\n仮定コスト(bps・中央値):"); print(T.groupby("symbol").assumed_bps.median().loc[OLD].round(2).to_string())
# B) 9 セル再検定
CELLS = [("EURGBP", 20, 4, "MonThu"), ("NZDUSD", 20, 4, "MonThu"), ("AUDUSD", 20, 4, "MonThu"), ("EURGBP", 16, 4, "MonThu"), ("USDCHF", 0, 4, "MonThu"), ("USDCHF", 16, 4, "MonThu"), ("NZDUSD", 16, 4, "MonThu"), ("CHFJPY", 20, 4, "MonThu"), ("USDCHF", 16, 6, "Thu"), ("USDCHF", 16, 4, "Thu"), ("USDCHF", 16, 5, "Thu")]
out = []
for sym, h0, span, dows in CELLS:
    j = load_ba(sym); dset = [0, 1, 2, 3] if dows == "MonThu" else [3]
    t = j.index[(j.index.hour == h0) & (j.index.dayofweek.isin(dset))]; te = t + pd.Timedelta(hours=span)
    m0 = j.mid.reindex(t).values; m1 = j.mid.reindex(te).values; ok = ~np.isnan(m1); t = t[ok]; te = te[ok]; m0 = m0[ok]; m1 = m1[ok]
    gross = -(m1 / m0 - 1)                                              # SHORT 粗利(中値)
    assumed = gross - cost(sym, m0)                                     # 仮定 3pip
    e_bid = j.bid.reindex(t).values; x_ask = j.ask.reindex(te).values; e_ask = j.ask.reindex(t).values; x_bid = j.bid.reindex(te).values
    meas_s = e_bid / x_ask - 1                                          # 実測 SHORT: bid で売り ask で買い戻し
    meas_l = x_bid / e_ask - 1                                          # 実測 LONG(自己検証用)
    z = np.log1p(meas_s) + np.log1p(meas_l); assert float(z.max()) <= 1e-12 and float(z.min()) < 0, f"[MEASURED SIGN] {sym}"   # 対数では LONG+SHORT = log(bid/ask)×2 側 ≤ 0
    def summ(r):
        s = pd.Series(r, index=t); mm = s.groupby(pd.PeriodIndex(s.index, freq="M")).apply(lambda q: (1 + q).prod() - 1); k, n, p = pb(mm); return k, n, p, round(float(s.mean()) * 1e4, 2)
    kg, ng, pg, mg = summ(gross); ka, na, pa, ma = summ(assumed); km, nm, pm, mmn = summ(meas_s)
    out.append(dict(cell=f"{dows} {sym} {h0:02d}+{span}h S", trades=len(t), gross_bps=mg, assumed3pip_bps=ma, measured_bps=mmn, measured_cost_bps=round(mg - mmn, 2), plus_gross=f"{kg}/{ng}", plus_assumed=f"{ka}/{na}", plus_measured=f"{km}/{nm}", p_measured=pm))
O = pd.DataFrame(out); O.to_csv("results/q18_measured_cost_sess_retest.csv", index=False); pd.set_option("display.width", 250)
print(f"\n== B) Sess 8 + A 案 S3(2024-01〜2026-08・{N} セル・累積 {cum} → {cum+N}) =="); print(O.to_string(index=False))
