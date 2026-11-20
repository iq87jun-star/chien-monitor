# -*- coding: utf-8 -*-
"""docs/293 Q40(F5): 地域間セッション波及(日次)。前セッションの符号に追随。使い方: python3 queue/q40_session_spillover.py <累積>"""
import sys, numpy as np, pandas as pd
from q_common import *
# (追随側 sym, 建て UTC 時, 決済 UTC 時, 先行 sym, 先行の開始 UTC 時, 先行の終了 UTC 時, 先行が前日か)
CELLS = [("JP225", 0, 6, "US500", 14, 20, True), ("AUS200", 0, 6, "US500", 14, 20, True), ("HK50", 1, 8, "US500", 14, 20, True),
         ("GER40", 7, 15, "JP225", 0, 6, False), ("EUSTX50", 7, 15, "JP225", 0, 6, False),
         ("US500", 14, 20, "GER40", 7, 13, False), ("NAS100", 14, 20, "GER40", 7, 13, False)]
cum = int(sys.argv[1]); R = Runner("Q40", cum, len(CELLS) * 2, "results/q40_session_spillover.csv")
for sym, h0, h1, lead, l0, l1, prev in CELLS:
    df = load(sym); selfcheck(sym, df); o = df["open"]; ol = load(lead)["open"]
    t_in = o.index[(o.index.hour == h0) & (o.index.dayofweek < 5)]
    d0 = t_in.normalize() - (pd.Timedelta(days=1) if prev else pd.Timedelta(0))
    # 先行セッションが前日のとき、月曜は金曜を参照
    if prev: d0 = pd.DatetimeIndex([d - pd.Timedelta(days=2) if d.dayofweek == 6 else d for d in d0])
    a = ol.reindex(d0 + pd.Timedelta(hours=l0)).values; b = ol.reindex(d0 + pd.Timedelta(hours=l1)).values
    lead_r = b / a - 1.0; px_out = o.reindex(t_in + pd.Timedelta(hours=h1 - h0)).values
    for thr, lab in ((0.0, "追随(符号)"), (0.005, "追随(|先行|≥0.5%)")):
        dir_ = np.where(np.isnan(lead_r), 0.0, np.where(np.abs(lead_r) >= thr, np.sign(lead_r), 0.0)) if thr > 0 else np.where(np.isnan(lead_r), 0.0, np.sign(lead_r))
        r = trades(sym, t_in, o.reindex(t_in).values, dir_, px_out)
        R.add("セッション波及", sym, f"{lab} {lead}{'前日' if prev else '同日'}{l0}-{l1}→{sym} {h0}-{h1}UTC", r)
R.finish()
