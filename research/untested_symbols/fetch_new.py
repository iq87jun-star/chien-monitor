import dukascopy_python as dk, datetime as dt, os, logging, sys
from dukascopy_python import instruments as I
from concurrent.futures import ThreadPoolExecutor
logging.disable(logging.CRITICAL)
OUT=sys.argv[1]
P={"XPTUSD":"CMD_METALS_XPT_CMD_USD","XPDUSD":"CMD_METALS_XPD_CMD_USD","COPPER":"CMD_METALS_COPPER_CMD_USD",
   "XRPUSD":"VCCY_XRP_USD","LTCUSD":"VCCY_LTC_USD","ADAUSD":"VCCY_ADA_USD",
   "USDNOK":"FX_CROSSES_USD_NOK","USDSEK":"FX_CROSSES_USD_SEK","EURNOK":"FX_CROSSES_EUR_NOK","EURSEK":"FX_CROSSES_EUR_SEK",
   "USDCNH":"FX_CROSSES_USD_CNH","USDSGD":"FX_CROSSES_USD_SGD","USDPLN":"FX_CROSSES_USD_PLN","EURPLN":"FX_CROSSES_EUR_PLN",
   "USDHUF":"FX_CROSSES_USD_HUF","USDCZK":"FX_CROSSES_USD_CZK","SGDJPY":"FX_CROSSES_SGD_JPY",
   "SUI20":"IDX_EUROPE_E_SWMI","ESP35":"IDX_EUROPE_E_IBC_MAC","NLD25":"IDX_EUROPE_NLD_IDX_EUR","ITA40":"IDX_EUROPE_ITA_IDX_EUR",
   "FRA40":"IDX_EUROPE_E_CAAC_40","CHI50":"IDX_ASIA_CHI_IDX_USD","IND50":"IDX_ASIA_IND_IDX_USD","US2000":"IDX_AMERICA_USSC2000_IDX_USD"}
def run(j):
    p,suf,side=j; f=f"{OUT}/{p}_h1{suf}.csv"
    if os.path.exists(f): return
    try:
        dk.fetch(getattr(I,"INSTRUMENT_"+P[p]),dk.INTERVAL_HOUR_1,side,dt.datetime(2016,1,1),dt.datetime(2026,10,13)).to_csv(f); print(f,flush=True)
    except Exception as e: print("ERR",f,e,flush=True)
jobs=[(p,s,side) for p in P for s,side in (("",dk.OFFER_SIDE_BID),("_ask",dk.OFFER_SIDE_ASK))]
with ThreadPoolExecutor(10) as ex: list(ex.map(run,jobs))
print("done",flush=True)
