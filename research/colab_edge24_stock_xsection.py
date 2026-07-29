"""
colab_edge24_stock_xsection.py — edge24: 個別株クロスセクション(docs/192 事前登録に従う)。

位置づけ: docs/126 D6(実装先なしで閉鎖)を docs/191(自己口座)で再開した最初の検定バッチ。
  仮説3本(X1: 12-1モメンタム / X2: 低ボラ / X3: 結合)・S&P100現構成・ロングオンリー・月次。
  ⚠ パラメータ/ユニバース/ゲートは docs/192 で凍結済み。登録外の変更をした結果は無効(docs/165)。

評価: 同一ユニバース等ウェイトに対する【超過】のみ(生存者バイアスの相対相殺)。
  プラセボ: ランダム10銘柄×毎月×1,000本の【グロス超過】分布と比較(コスト非対称の影響を排除)。
ゲート: G1 超過>0(コスト込) / G2 プラセボp<0.0167 / G3 超過負け年≤3 / G4 コスト2倍で超過>0 /
  G5 自EA月次相関|ρ|<0.30(DriveにCSVがあれば)。

使い方(Colab): そのまま「すべて実行」(データはYahooから自動取得・約100銘柄×10年日足)。
"""
import json, math, os, time, urllib.request
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

RNG=np.random.default_rng(20260729)
TOP_N=10; COST_RT=0.002; LOOKBACK=12; SKIP=1; N_PLACEBO=1000
DRIVE_BASE="/content/drive/MyDrive/forex_ml"; OWN_MONTHLY=f"{DRIVE_BASE}/results/own_portfolio_monthly.csv"

UNIVERSE=("AAPL ABBV ABT ACN ADBE AIG AMD AMGN AMT AMZN AVGO AXP BA BAC BK BKNG BLK BMY BRK-B C "
"CAT CHTR CL CMCSA COF COP COST CRM CSCO CVS CVX DE DHR DIS DOW DUK EMR ETN F FDX GD GE GILD GM "
"GOOG GS HD HON IBM INTC INTU ISRG JNJ JPM KHC KO LIN LLY LMT LOW MA MCD MDLZ MDT MET META MMM "
"MO MRK MS MSFT NEE NFLX NKE NOW NVDA ORCL PEP PFE PG PM PYPL QCOM RTX SBUX SCHW SO SPG T TGT "
"TMO TMUS TSLA TXN UNH UNP UPS USB V VZ WFC WMT XOM").split()

def fetch_monthly(sym, retries=2):
    import datetime as dt
    p2=int(time.time()); p1=p2-int(11.2*365.25*86400)
    u=(f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}"
       f"?interval=1d&period1={p1}&period2={p2}&events=div%2Csplit")
    for a in range(retries+1):
        try:
            req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"})
            d=json.loads(urllib.request.urlopen(req,timeout=30).read())
            r=d["chart"]["result"][0]; ts=r["timestamp"]
            adj=r["indicators"].get("adjclose",[{}])[0].get("adjclose") \
                or r["indicators"]["quote"][0]["close"]
            s=pd.Series(adj, index=pd.to_datetime(ts,unit="s",utc=True)).dropna()
            m=s.resample("ME").last()
            return m if len(m)>=8*12 else None
        except Exception:
            if a==retries: return None
            time.sleep(1.5)

def build_panel():
    cols={}
    for i,sym in enumerate(UNIVERSE):
        s=fetch_monthly(sym)
        if s is not None: cols[sym]=s
        if (i+1)%20==0: print(f"  取得 {i+1}/{len(UNIVERSE)} (有効 {len(cols)})")
        time.sleep(0.25)
    px=pd.DataFrame(cols).sort_index()
    print(f"  パネル: {px.shape[1]}銘柄 × {px.shape[0]}ヶ月 ({px.index[0]:%Y-%m}〜{px.index[-1]:%Y-%m})")
    return px

def run_strategy(px, mode, cost_rt=COST_RT):
    """月次リターン列(net, gross)とベンチ超過を返す。mode: MOM/LOWVOL/COMBO"""
    ret=px.pct_change()
    vol=ret.rolling(12).std()
    mom=px.shift(SKIP)/px.shift(LOOKBACK)-1.0
    net=[]; gross=[]; bench=[]; idx=[]; prev=set()
    for t in range(LOOKBACK+1, len(px)-1):
        row_r=ret.iloc[t+1]                      # 翌月リターン
        avail=px.iloc[t].dropna().index
        avail=[s for s in avail if not math.isnan(mom.iloc[t].get(s,np.nan))
               and not math.isnan(vol.iloc[t].get(s,np.nan)) and not math.isnan(row_r.get(s,np.nan))]
        if len(avail)<40: continue
        if mode=="MOM":   rank=mom.iloc[t][avail].rank(ascending=False)
        elif mode=="LOWVOL": rank=vol.iloc[t][avail].rank(ascending=True)
        else:
            rank=(mom.iloc[t][avail].rank(ascending=False)+vol.iloc[t][avail].rank(ascending=True))/2
        pick=set(rank.nsmallest(TOP_N).index)
        turn=len(pick-prev)/TOP_N if prev else 1.0
        g=float(row_r[list(pick)].mean()); c=cost_rt*turn
        gross.append(g); net.append(g-c); bench.append(float(row_r[avail].mean())); idx.append(px.index[t+1])
        prev=pick
    return (pd.Series(net,index=idx), pd.Series(gross,index=idx), pd.Series(bench,index=idx))

def placebo_dist(px, n_iter=N_PLACEBO):
    """ランダムTOP_N銘柄・毎月入替のグロス超過(累積)分布。"""
    ret=px.pct_change(); out=[]
    months=range(LOOKBACK+1,len(px)-1)
    avail_cache={t: list(ret.iloc[t+1].dropna().index) for t in months}
    for _ in range(n_iter):
        ex=0.0
        for t in months:
            av=avail_cache[t]
            if len(av)<40: continue
            pick=RNG.choice(av,TOP_N,replace=False)
            ex+=float(ret.iloc[t+1][pick].mean())-float(ret.iloc[t+1][av].mean())
        out.append(ex)
    return np.array(out)

def gates(name, net, gross, bench, net2, plac):
    ex_net=float((net-bench).sum()); ex_gross=float((gross-bench).sum())
    ex2=float((net2-bench).sum())
    p=float((plac>=ex_gross).mean())
    yearly=(net-bench).groupby(lambda i:i.year).sum()
    losing=int((yearly<0).sum())
    g=dict(G1_excess_net=(round(ex_net,4), bool(ex_net>0)),
           G2_placebo_p=(round(p,4), bool(p<0.0167)),
           G3_losing_years=(losing, bool(losing<=3)),
           G4_cost2x_excess=(round(ex2,4), bool(ex2>0)))
    ok=all(v[1] for v in g.values())
    return dict(name=name, months=int(len(net)),
                ann_excess_net=float(round(ex_net/len(net)*12,4)),
                yearly_excess={int(k):float(round(v,4)) for k,v in yearly.items()},
                gates=g, verdict="→ペーパー前進検証候補(G6相関は別途)" if ok else "REJECT")

def main():
    print("="*88); print("edge24: 個別株クロスセクション検定(docs/192 登録ゲート)"); print("="*88)
    px=build_panel()
    print("  プラセボ分布を生成中(1,000本)…")
    plac=placebo_dist(px)
    out={"prereg":"docs/192","universe_n":int(px.shape[1]),"results":[]}
    for mode in ("MOM","LOWVOL","COMBO"):
        net,gross,bench=run_strategy(px,mode)
        net2,_,_=run_strategy(px,mode,cost_rt=COST_RT*2)
        r=gates(f"X_{mode}",net,gross,bench,net2,plac)
        out["results"].append(r); print(json.dumps(r,ensure_ascii=False,indent=1))
    print("\nG5 相関判定:", "own_portfolio_monthly.csv 検出→手動確認" if os.path.exists(OWN_MONTHLY)
          else "自EA月次CSVなし → G5保留(合格候補も採用禁止のまま)")
    os.makedirs("research/results",exist_ok=True)
    with open("research/results/edge24_stock_xsection.json","w",encoding="utf-8") as f:
        json.dump(out,f,ensure_ascii=False,indent=2)
    print("\n保存: research/results/edge24_stock_xsection.json → docs/193(結果)に転記のこと")

main()
