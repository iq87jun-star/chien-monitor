import dukascopy_python as dk, datetime as dt, os, sys, logging
from dukascopy_python import instruments as I
from concurrent.futures import ThreadPoolExecutor
logging.disable(logging.CRITICAL)
OUT=sys.argv[1]
P={"USDJPY":I.INSTRUMENT_FX_MAJORS_USD_JPY,"EURJPY":I.INSTRUMENT_FX_CROSSES_EUR_JPY,"GBPJPY":I.INSTRUMENT_FX_CROSSES_GBP_JPY,"AUDJPY":I.INSTRUMENT_FX_CROSSES_AUD_JPY,
   "NZDJPY":I.INSTRUMENT_FX_CROSSES_NZD_JPY,"EURUSD":I.INSTRUMENT_FX_MAJORS_EUR_USD,"GBPUSD":I.INSTRUMENT_FX_MAJORS_GBP_USD,"AUDUSD":I.INSTRUMENT_FX_MAJORS_AUD_USD}
d=dt.datetime(2016,1,3)   # Sunday
jobs=[]
while d<dt.datetime(2026,10,12):
    for p in P:
        for side in ("BID","ASK"): jobs.append((p,side,d))
    d+=dt.timedelta(days=7)
def run(j):
    p,side,d=j; f=f"{OUT}/{p}_{side}_{d:%Y%m%d}.csv"
    if os.path.exists(f): return
    try:
        df=dk.fetch(P[p],dk.INTERVAL_MIN_1,getattr(dk,f"OFFER_SIDE_{side}"),d.replace(hour=20),d+dt.timedelta(hours=31))
        df[["open"]].to_csv(f)
    except Exception as e:
        open(f+".err","w").write(str(e))
with ThreadPoolExecutor(24) as ex: list(ex.map(run,jobs))
print("done",len(jobs))
