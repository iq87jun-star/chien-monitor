import dukascopy_python as dk, datetime as dt, os, logging
from dukascopy_python import instruments as I
from concurrent.futures import ThreadPoolExecutor
logging.disable(logging.CRITICAL)
P={"AUDCAD":"INSTRUMENT_FX_CROSSES_AUD_CAD","EURCHF":"INSTRUMENT_FX_CROSSES_EUR_CHF","GBPCHF":"INSTRUMENT_FX_CROSSES_GBP_CHF",
   "NZDCAD":"INSTRUMENT_FX_CROSSES_NZD_CAD","CADCHF":"INSTRUMENT_FX_CROSSES_CAD_CHF","AUDNZD":"INSTRUMENT_FX_CROSSES_AUD_NZD"}
def run(j):
    p,suf,side=j; f=f"{p}_h1{suf}.csv"
    if os.path.exists(f): return
    dk.fetch(getattr(I,P[p]),dk.INTERVAL_HOUR_1,side,dt.datetime(2016,1,1),dt.datetime(2026,10,13)).to_csv(f); print(f,flush=True)
jobs=[(p,s,side) for p in P for s,side in (("",dk.OFFER_SIDE_BID),("_ask",dk.OFFER_SIDE_ASK))]
with ThreadPoolExecutor(6) as ex: list(ex.map(run,jobs))
print("done")
