# -*- coding: utf-8 -*-
"""docs/263 Q19(別トラック): 旧 19 銘柄に第 3 段の時間帯格子(5 曜日 × 9 窓 × L/S = 90 セル/銘柄 = 1,710)を、コスト = docs/262 §A の実測往復(銘柄 × 窓の中央値・2024-01〜2026-08 の Dukascopy bid/ask)× 1.5 で再走する。
判定は docs/244 §1 のまま(前窓 ≥ 50%・IS 二項 p < 0.05/累積・IS 月数 ≥ 24・OOS 平均 > 0。XAUUSD は前窓なし→免除)。通過セルは候補入りの前に実口座スプレッドの実測を要する(docs/262 §C)。
使い方: python3 queue/q19_measured_cost_h1_grid.py <累積セル数>"""
import sys, numpy as np, pandas as pd
from q_common import *
OLD = ["EURGBP", "USDCHF", "NZDUSD", "AUDUSD", "CHFJPY", "GBPJPY", "EURJPY", "AUDJPY", "USDJPY", "CADJPY", "NZDJPY", "EURUSD", "GBPUSD", "EURAUD", "GBPAUD", "XAUUSD", "GER40", "NAS100", "US500"]
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri"]; WINS = [(h, 4) for h in (0, 4, 8, 12, 16, 20)] + [(h, 8) for h in (0, 8, 16)]
MULT = 1.5
T = pd.read_csv("results/q18_measured_roundtrip_cost.csv"); C = {(r.symbol, r.window): r.rt_bps_median * MULT / 1e4 for r in T.itertuples()}
cum = int(sys.argv[1]); R = Runner("Q19", cum, len(OLD) * 90, "results/q19_measured_cost_h1_grid.csv")
for sym in OLD:
    df = load(sym); o = df["open"]
    # 自己検証(実測コスト版): 同一建てで LONG+SHORT = −2c
    t0 = o.index[(o.index.hour == 8) & (o.index.dayofweek == 1)][:300]; c0 = C[(sym, "08-12")]; p0 = o.reindex(t0).values; p1 = o.reindex(t0 + pd.Timedelta(hours=4)).values
    z = ((p1 / p0 - 1) - c0) + (-(p1 / p0 - 1) - c0); z = z[~np.isnan(z)]; assert len(z) > 0 and abs(float(z.max()) + 2 * c0) < 1e-12, f"[COST SIGN] {sym}"
    for dow in range(5):
        for h0, span in WINS:
            c = C[(sym, f"{h0:02d}-{(h0+span)%24:02d}")]
            t = o.index[(o.index.dayofweek == dow) & (o.index.hour == h0)]; px = o.reindex(t).values; pe = o.reindex(t + pd.Timedelta(hours=span)).values
            ok = ~np.isnan(pe); t = t[ok]; px = px[ok]; pe = pe[ok]
            for sh in (False, True):
                r = pd.Series((-(pe / px - 1) if sh else (pe / px - 1)) - c, index=t)
                R.add("実測コスト格子", sym, f"{DOW[dow]}{'S' if sh else ''} {h0:02d}-{(h0+span)%24:02d}UTC cost={c*1e4:.2f}bps", r)
R.finish()
