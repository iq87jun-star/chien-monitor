import yfinance as yf, pandas as pd, os, sys, time
OUT=sys.argv[1]
T=["AAPL","MSFT","AMZN","GOOGL","META","NVDA","TSLA","NFLX","JPM","BAC","WFC","GS","V","MA","WMT","COST","KO","PEP","PG","JNJ",
   "PFE","MRK","UNH","XOM","CVX","DIS","INTC","AMD","CSCO","ORCL","ADBE","CRM","NKE","MCD","BA","T","VZ","HD","QCOM","AVGO"]
px=yf.download(T+["SPY"],start="2015-12-01",progress=False,auto_adjust=True,group_by="ticker",threads=True)
px.to_pickle(f"{OUT}/px.pkl"); print("prices",px.shape,flush=True)
rows=[]
for t in T:
    for k in range(3):
        try:
            e=yf.Ticker(t).get_earnings_dates(limit=48); e=e.reset_index(); e["ticker"]=t; rows.append(e); break
        except Exception as ex: print("retry",t,ex,flush=True); time.sleep(3)
E=pd.concat(rows); E.to_pickle(f"{OUT}/earn.pkl"); print("earnings",len(E),E.ticker.nunique(),flush=True)
