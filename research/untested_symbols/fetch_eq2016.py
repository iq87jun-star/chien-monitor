import yfinance as yf, pandas as pd, json, sys, time, logging
from concurrent.futures import ThreadPoolExecutor
logging.disable(logging.CRITICAL)
D=sys.argv[1]; T=json.load(open(f"{D}/sp500_2016.json"))
px=yf.download(T+["SPY"],start="2015-12-01",progress=False,auto_adjust=True,group_by="ticker",threads=True)
px.to_pickle(f"{D}/px2016.pkl"); print("prices",px.shape,flush=True)
def one(t):
    for k in range(3):
        try:
            e=yf.Ticker(t).get_earnings_dates(limit=48)
            if e is None or len(e)==0: return None
            e=e.reset_index(); e["ticker"]=t; return e
        except Exception as ex:
            time.sleep(2+3*k)
    return None
with ThreadPoolExecutor(4) as ex: res=list(ex.map(one,T))
E=pd.concat([r for r in res if r is not None]); E.to_pickle(f"{D}/earn2016.pkl")
print("earnings",len(E),E.ticker.nunique(),"/",len(T),flush=True)
