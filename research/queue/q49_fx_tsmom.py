# -*- coding: utf-8 -*-
"""docs/295 Q49: FX の時系列モメンタム(採用レグ TSMOM=E5 の抽象化を FX へ)。月足 1/3/6/12 ヶ月リターンの符号和の符号を翌月保有(recentfit_screen.tsmom_cell と同一・月初 5 bps)。
使い方: python3 queue/q49_fx_tsmom.py <累積>"""
import sys, os
from q_common import *
base.DATA = os.path.join(ROOT, "data_202609")
PAIRS = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF", "USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "NZDJPY", "CADJPY", "CHFJPY", "EURGBP"]
cum = int(sys.argv[1]); R = Runner("Q49", cum, len(PAIRS), "results/q49_fx_tsmom.csv")
for p in PAIRS:
    try: s = base.tsmom_cell(p)
    except Exception as e: print(f"[{p}] 構築不可: {e}"); s = pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    R.add("FX TSMOM", p, "月足 1/3/6/12 符号和・翌月保有", s.dropna())
R.finish()
