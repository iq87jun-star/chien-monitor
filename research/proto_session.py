# -*- coding: utf-8 -*-
"""
proto_session.py  —  事前登録(docs/06)に従い、1回だけ実行する日中セッション戦略の評価。
H1: London ORB / H2: Asian Range Fade。ノールックアヘッド・実コスト・ペア別/プール/レジーム分割。
データ: research/data/{pair}_h1.csv (UTC hourly, 約2年, Yahoo)。本番OOSはユーザーDukascopyで。
パラメータは docs/06 で固定。ここでは一切調整しない。
"""
import os, csv, math, json, datetime as dt
import numpy as np

DATA=os.path.join(os.path.dirname(__file__),"data")
PAIRS=["EURUSD","GBPUSD","USDJPY","EURJPY","GBPJPY"]
SPREAD_PIPS={"USDJPY":1.2,"EURJPY":1.6,"GBPJPY":2.0,"EURUSD":0.8,"GBPUSD":1.2}
SLIP=0.5
def pip(p): return 0.01 if p.endswith("JPY") else 0.0001

def load_h1(pair):
    ts=[];o=[];h=[];l=[];c=[]
    with open(os.path.join(DATA,f"{pair}_h1.csv")) as f:
        for r in csv.DictReader(f):
            d=dt.datetime.strptime(r["timestamp"][:19],"%Y-%m-%d %H:%M:%S")
            ts.append(d);o.append(float(r["open"]));h.append(float(r["high"]))
            l.append(float(r["low"]));c.append(float(r["close"]))
    return ts,np.array(o),np.array(h),np.array(l),np.array(c)

def atr_wilder(h,l,c,n=24):
    pc=np.roll(c,1);pc[0]=c[0]
    tr=np.maximum.reduce([h-l,np.abs(h-pc),np.abs(l-pc)])
    out=np.empty_like(c);out[0]=tr[0];a=1.0/n
    for i in range(1,len(c)): out[i]=a*tr[i]+(1-a)*out[i-1]
    return out

def day_index(ts):
    """UTC日付ごとにバーindexをまとめ、各日 hour->index の辞書を返す。"""
    days={}
    for i,d in enumerate(ts):
        key=d.date()
        days.setdefault(key,{})[d.hour]=i
    return days

def simulate_orb(pair):
    ts,o,h,l,c=load_h1(pair); P=pip(pair)
    atr=atr_wilder(h,l,c,24)
    half=(SPREAD_PIPS[pair]/2.0+SLIP)*P
    days=day_index(ts)
    R=[]; tdates=[]
    daykeys=sorted(days.keys())
    for dk in daykeys:
        hod=days[dk]
        if 7 not in hod: continue
        i07=hod[7]
        ORh=h[i07]; ORl=l[i07]; ORrange=ORh-ORl
        if ORrange<=0: continue
        A=atr[i07]
        if not (0.15*A<=ORrange<=3.0*A): continue   # 固定フィルタ
        # ブレイク窓 08:00-16:00 (hour 8..15) の確定足を順に
        entry=None;dirn=0
        for hh in range(8,16):
            if hh not in hod: continue
            k=hod[hh]
            if c[k]>ORh: dirn=1; bk=k; break
            if c[k]<ORl: dirn=-1; bk=k; break
        if dirn==0: continue
        # 次のH1足始値で約定(ノールックアヘッド)。同日内に次足が必要。
        nk=bk+1
        if nk>=len(ts) or ts[nk].date()!=dk: continue
        raw_entry=o[nk]
        SL = ORl if dirn>0 else ORh
        risk = abs(raw_entry-SL)
        if risk<=0: continue
        TP = raw_entry+1.5*risk*dirn
        # 21:00 まで前進
        exit_price=None
        kk=nk
        # 当日 hour<=21 のバーで判定
        while kk<len(ts) and ts[kk].date()==dk and ts[kk].hour<=21:
            hi=h[kk];lo=l[kk]
            if dirn>0:
                if lo<=SL: exit_price=SL; break
                if hi>=TP: exit_price=TP; break
            else:
                if hi>=SL: exit_price=SL; break
                if lo<=TP: exit_price=TP; break
            if ts[kk].hour==21:
                exit_price=c[kk]; break
            kk+=1
        if exit_price is None:
            # 21:00足が無ければ当日最終足で
            exit_price=c[kk-1] if kk>nk else raw_entry
        pnl=dirn*(exit_price-raw_entry)-2*half
        R.append(pnl/risk); tdates.append(ts[nk])
    return np.array(R), tdates

def simulate_asian(pair):
    ts,o,h,l,c=load_h1(pair); P=pip(pair)
    half=(SPREAD_PIPS[pair]/2.0+SLIP)*P
    days=day_index(ts)
    R=[]; tdates=[]
    for dk in sorted(days.keys()):
        hod=days[dk]
        hrs=[x for x in range(0,6) if x in hod]
        if len(hrs)<3: continue
        idxs=[hod[x] for x in hrs]
        ARh=max(h[i] for i in idxs); ARl=min(l[i] for i in idxs)
        mid=(ARh+ARl)/2.0; rng=ARh-ARl
        if rng<=0: continue
        entry=None;dirn=0
        for hh in range(6,12):
            if hh not in hod: continue
            k=hod[hh]
            if c[k]>ARh: dirn=-1; bk=k; break   # 上抜け→フェード売り
            if c[k]<ARl: dirn=1;  bk=k; break
        if dirn==0: continue
        nk=bk+1
        if nk>=len(ts) or ts[nk].date()!=dk: continue
        raw_entry=o[nk]
        SL=raw_entry-rng*dirn*(-1) if False else (raw_entry+rng*dirn*( -1))  # placeholder
        # SL: ブレイク方向へ rng*1.0 (売りなら上に, 買いなら下に)
        SL = raw_entry + rng*1.0 if dirn<0 else raw_entry - rng*1.0
        risk=abs(raw_entry-SL)
        if risk<=0: continue
        # TP: mid か リスク*1.0 の近い方
        tp_mid=mid
        tp_r = raw_entry + 1.0*risk*dirn
        TP = tp_mid if abs(tp_mid-raw_entry)<abs(tp_r-raw_entry) else tp_r
        exit_price=None;kk=nk
        while kk<len(ts) and ts[kk].date()==dk and ts[kk].hour<=16:
            hi=h[kk];lo=l[kk]
            if dirn>0:
                if lo<=SL: exit_price=SL;break
                if hi>=TP: exit_price=TP;break
            else:
                if hi>=SL: exit_price=SL;break
                if lo<=TP: exit_price=TP;break
            if ts[kk].hour==16: exit_price=c[kk];break
            kk+=1
        if exit_price is None:
            exit_price=c[kk-1] if kk>nk else raw_entry
        pnl=dirn*(exit_price-raw_entry)-2*half
        R.append(pnl/risk); tdates.append(ts[nk])
    return np.array(R), tdates

def boot_p(R,nb=5000,seed=42):
    if len(R)<10: return float("nan")
    rng=np.random.default_rng(seed);n=len(R);cnt=0
    for _ in range(nb):
        s=R[rng.integers(0,n,n)];gp=s[s>0].sum();gl=-s[s<0].sum()
        pf=gp/gl if gl>0 else 1e9
        if pf<=1.0:cnt+=1
    return cnt/nb

def stats(R):
    n=len(R)
    if n<5: return {"n":n,"PF":None,"exp":None,"WR":None,"P":None}
    gp=R[R>0].sum();gl=-R[R<0].sum();pf=gp/gl if gl>0 else float("inf")
    return {"n":n,"PF":round(pf,3),"exp":round(float(R.mean()),4),
            "WR":round(float((R>0).mean()),3),"P":round(boot_p(R),4)}

def regime(R,td):
    if len(R)==0: return {},{}
    mid=td[len(td)//2]
    a=np.array([r for r,t in zip(R,td) if t<mid])
    b=np.array([r for r,t in zip(R,td) if t>=mid])
    return stats(a),stats(b)

def run(simfn,label):
    print(f"\n========== {label} ==========")
    print(f"{'pair':<8}{'n':>5}{'PF':>7}{'exp':>8}{'WR':>7}{'P(PF<=1)':>10}{'前半PF':>8}{'後半PF':>8}")
    pooled=[];pooled_td=[]
    perpair_pf_gt1=0; npairs=0
    for p in PAIRS:
        R,td=simfn(p); s=stats(R); ra,rb=regime(R,td)
        pooled.append(R); pooled_td+=td
        if s["n"]>=5:
            npairs+=1
            if s["PF"] and s["PF"]>1: perpair_pf_gt1+=1
        print(f"{p:<8}{s['n']:>5}{str(s['PF']):>7}{str(s['exp']):>8}{str(s['WR']):>7}{str(s['P']):>10}"
              f"{str(ra.get('PF')):>8}{str(rb.get('PF')):>8}")
    POOL=np.concatenate(pooled) if pooled else np.array([])
    ps=stats(POOL); pa,pb=regime(POOL,pooled_td)
    print(f"{'POOL':<8}{ps['n']:>5}{str(ps['PF']):>7}{str(ps['exp']):>8}{str(ps['WR']):>7}{str(ps['P']):>10}"
          f"{str(pa.get('PF')):>8}{str(pb.get('PF')):>8}")
    # 事前登録基準の自動判定(プロトタイプ版; 本番はユーザーDukascopyで)
    crit1 = (ps["PF"] or 0)>1 and (ps["P"] is not None and ps["P"]<0.05)
    crit2 = perpair_pf_gt1>=4
    crit3 = (pa.get("PF") or 0)>1 and (pb.get("PF") or 0)>1
    crit4 = (ps["n"] or 0)>=200
    print(f"\n[事前登録基準(proto)] ①プールPF>1&P<0.05={crit1}  ②ペア≥4 で PF>1={perpair_pf_gt1}/{npairs}→{crit2}  "
          f"③前後半ともPF>1={crit3}  ④n≥200={crit4}")
    print(f"  → proto総合: {'PASS(本番Dukascopyで再検証へ)' if (crit1 and crit2 and crit3 and crit4) else 'FAIL'}")
    return {"label":label,"pool":ps,"regime":[pa,pb],"perpair_pf_gt1":perpair_pf_gt1,
            "crit":{"1":crit1,"2":crit2,"3":crit3,"4":crit4}}

if __name__=="__main__":
    out=[]
    out.append(run(simulate_orb,"H1: London Open Range Breakout"))
    out.append(run(simulate_asian,"H2: Asian Range Fade"))
    json.dump(out, open(os.path.join(os.path.dirname(__file__),"results","proto_session.json"),"w"),
              indent=2, default=str)
    print("\n(注: プロトタイプは約2年のYahoo H1。最終判定はユーザーのDukascopy H1 10年で。)")
