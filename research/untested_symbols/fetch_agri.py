import dukascopy_python as dk, datetime as dt, os, logging, sys
from dukascopy_python import instruments as I
from concurrent.futures import ThreadPoolExecutor
logging.disable(logging.CRITICAL)
OUT=sys.argv[1]
P={"COCOA":"CMD_AGRICULTURAL_COCOA_CMD_USD","COFFEE":"CMD_AGRICULTURAL_COFFEE_CMD_USX","COTTON":"CMD_AGRICULTURAL_COTTON_CMD_USX",
   "OJUICE":"CMD_AGRICULTURAL_OJUICE_CMD_USX","SOYBEAN":"CMD_AGRICULTURAL_SOYBEAN_CMD_USX","SUGAR":"CMD_AGRICULTURAL_SUGAR_CMD_USD",
   "DIESEL":"CMD_ENERGY_DIESEL_CMD_USD","NATGAS":"CMD_ENERGY_GAS_CMD_USD","UKGILT":"BND_CFD_UKGILT_TR_GBP",
   "ZARJPY":"FX_CROSSES_ZAR_JPY","MXNJPY":"FX_CROSSES_MXN_JPY","TRYJPY":"FX_CROSSES_TRY_JPY","HKDJPY":"FX_CROSSES_HKD_JPY"}
def run(j):
    p,suf,side=j; f=f"{OUT}/{p}_h1{suf}.csv"
    if os.path.exists(f): return
    try: dk.fetch(getattr(I,"INSTRUMENT_"+P[p]),dk.INTERVAL_HOUR_1,side,dt.datetime(2016,1,1),dt.datetime(2026,10,13)).to_csv(f); print(f,flush=True)
    except Exception as e: print("ERR",f,e,flush=True)
jobs=[(p,s,side) for p in P for s,side in (("",dk.OFFER_SIDE_BID),("_ask",dk.OFFER_SIDE_ASK))]
with ThreadPoolExecutor(10) as ex: list(ex.map(run,jobs))
import yfinance as yf
yf.download(["ZW=F","ZC=F","HO=F","CC=F","KC=F","CT=F","ZS=F","SB=F","OJ=F","NG=F"],start="2015-01-01",progress=False,auto_adjust=False,group_by="ticker").to_pickle(f"{OUT}/yf_futures.pkl")
print("done",flush=True)
