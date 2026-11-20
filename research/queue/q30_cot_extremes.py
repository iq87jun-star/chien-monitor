# -*- coding: utf-8 -*-
"""docs/277 Q30: CFTC COT(TFF)のレバレッジド・ファンド純ポジションの極端値。通貨 {JPY EUR GBP AUD CAD CHF NZD(あれば)} × z 閾値 {1.5, 2.0} × {反転, 追随}。
z = (net/OI − 156 週平均)/156 週 σ(最低 52 週)。火曜基準・金曜公表 → 翌月曜の最初の H1 始値で建て、次の月曜の最初の H1 始値で出る(1 週)。通貨の対 USD リターン(USDJPY 等は符号反転)。コスト 3pip。
使い方: python3 queue/q30_cot_extremes.py <累積セル数>"""
import sys, glob, zipfile, io, numpy as np, pandas as pd
from q_common import *
MK = {"JPY": "JAPANESE YEN", "EUR": "EURO FX -", "GBP": "BRITISH POUND", "AUD": "AUSTRALIAN DOLLAR", "CAD": "CANADIAN DOLLAR", "CHF": "SWISS FRANC", "NZD": "NZ DOLLAR|NEW ZEALAND"}
PAIR = {"JPY": ("USDJPY", -1), "EUR": ("EURUSD", 1), "GBP": ("GBPUSD", 1), "AUD": ("AUDUSD", 1), "CAD": ("USDCAD", -1), "CHF": ("USDCHF", -1), "NZD": ("NZDUSD", 1)}
frames = []
for f in sorted(glob.glob("data_ext/cot_*.zip")):
    z = zipfile.ZipFile(f); name = [n for n in z.namelist() if n.lower().endswith((".txt", ".csv"))][0]
    frames.append(pd.read_csv(io.BytesIO(z.read(name)), low_memory=False))
C = pd.concat(frames, ignore_index=True); C["date"] = pd.to_datetime(C["Report_Date_as_YYYY-MM-DD"])
cur = {}
for ccy, pat in MK.items():
    m = C[C["Market_and_Exchange_Names"].str.contains(pat, regex=True, case=False)].sort_values("date")
    if len(m) < 100: print(f"[{ccy}] COT 行が不足({len(m)})→ 除外"); continue
    net = (m["Lev_Money_Positions_Long_All"] - m["Lev_Money_Positions_Short_All"]) / m["Open_Interest_All"]; s = pd.Series(net.values, index=m["date"].values); s = s[~s.index.duplicated(keep="last")]
    mu = s.rolling(156, min_periods=52).mean(); sd = s.rolling(156, min_periods=52).std(); cur[ccy] = ((s - mu) / sd).dropna()
N = len(cur) * 4; cum = int(sys.argv[1]); R = Runner("Q30", cum, N, "results/q30_cot_extremes.csv"); print("通貨:", list(cur), "セル", N)
for ccy, z in cur.items():
    pair, sgn = PAIR[ccy]; df = load(pair); o = df["open"]
    mondays = o.index[(o.index.dayofweek == 0)]; first = pd.Series(mondays, index=mondays).groupby(mondays.normalize()).min()   # 月曜の最初のバー
    days = first.index; entries = []
    for d, zval in z.items():
        rel = d + pd.Timedelta(days=3)                                  # 火曜基準 → 金曜公表
        nxt = days[days > rel.normalize()]
        if len(nxt) < 2: continue
        t_in = first[nxt[0]]; t_out = first[nxt[1]]; entries.append((t_in, t_out, zval))
    E = pd.DataFrame(entries, columns=["t_in", "t_out", "z"]).drop_duplicates("t_in")
    px_in = o.reindex(E.t_in).values; px_out = o.reindex(E.t_out).values
    for thr in (1.5, 2.0):
        for lab, k in (("反転", -1), ("追随", 1)):
            sig = np.where(E.z.values >= thr, 1.0, np.where(E.z.values <= -thr, -1.0, 0.0))   # +1 = 混雑ロング
            d_ccy = k * sig                                                                 # 反転: 混雑ロング → 通貨 SHORT
            d_pair = d_ccy * sgn                                                            # 通貨方向 → ペア方向
            R.add("COT 極端値", ccy, f"z>={thr} {lab} 1w ({pair})", trades(pair, pd.DatetimeIndex(E.t_in), px_in, d_pair, px_out))
R.finish()
