import sys,os,json,csv,gzip,lzma,struct,glob,datetime as dt,collections
sys.path.insert(0,sys.argv[1]); import to_live_ops as t
H=sys.argv[2]; DH=sys.argv[4]
def rd(f,c="open"): return {dt.datetime.strptime(r["timestamp"],"%Y-%m-%d %H:%M:%S"):float(r[c]) for r in csv.DictReader(gzip.open(f,"rt"))}
def load(p):
    b=rd(f"{H}/{p}.csv.gz"); a=rd(f"{H}/{p}_ask.csv.gz")
    px={k:(b[k]+a[k])/2 for k in b if k in a}
    bc=rd(f"{H}/{p}.csv.gz","close"); ac=rd(f"{H}/{p}_ask.csv.gz","close")
    for k in bc:
        k2=k+dt.timedelta(hours=1)
        if k in ac and k2 not in px: px[k2]=(bc[k]+ac[k])/2
    nf=0
    for f in glob.glob(f"{DH}/../fxcm/{p}_2026_*.csv.gz"):
        try:
            for r in csv.reader(gzip.open(f,"rt")):
                if r[0][14:16]=="00":
                    k=dt.datetime.strptime(r[0][:16],"%m/%d/%Y %H:%M")
                    if k not in px: px[k]=(float(r[1])+float(r[5]))/2; nf+=1
        except Exception: pass
    print(p,"fxcm added",nf,file=sys.stderr)
    div=1000 if p.endswith("JPY") else 100000; n=0; late={}
    for f in glob.glob(f"{DH}/{p}_*.bi5"):
        k=dt.datetime.strptime(os.path.basename(f)[len(p)+1:-4],"%Y%m%d_%H")
        try: raw=lzma.decompress(open(f,"rb").read())
        except Exception: continue
        if len(raw)<20: continue
        ms,ask,bid,_,_=struct.unpack(">IIIff",raw[:20])
        ms2,ask2,bid2,_,_=struct.unpack('>IIIff',raw[-20:])  # LASTTICK
        if ms2>3000000: late[k+dt.timedelta(hours=1)]=(ask2+bid2)/2/div
        if ms>600000: continue
        px[k]=(ask+bid)/2/div; n+=1
    for k,v in late.items(): px.setdefault(k,v)
    print(p,len(px),"ticks added",n,max(px),file=sys.stderr); return px
PX={p:load(p) for p in ["EURJPY","AUDJPY","NZDJPY","EURGBP"]}
legs=[l for l in t.MENU if not l.get("gotobi")]
out=[]; miss=collections.defaultdict(list)
d=dt.date(2016,12,1)
while d<=dt.date(2026,11,25):
    for l in legs:
        if not t.is_due_today(l,d): continue
        e=t.jst(d,l["entry"]).astimezone(t.UTC).replace(tzinfo=None); x=t.judge_utc(l,d).replace(tzinfo=None)
        px=PX[l["pair"]]
        if e not in px or x not in px: miss[l["id"]].append(str(d)); continue
        a,b=px[e],px[x]
        win=(a!=b) and ((b>a)==(l["sel"]=="HIGH"))
        ref=None
        if l["id"] in ("AUDJPY_02","EURGBP_N6L"):
            r0=dt.datetime(e.year,e.month,e.day,21)-dt.timedelta(days=1)
            for h in range(0,96):
                if r0-dt.timedelta(hours=h) in px: ref=px[r0-dt.timedelta(hours=h)]; break
        else:
            f1=dt.datetime(e.year,e.month,e.day,21)-dt.timedelta(days=2); f0=f1-dt.timedelta(days=1)   # 金曜 21Z と 木曜 21Z
            a1=next((px[f1-dt.timedelta(hours=h)] for h in range(0,6) if f1-dt.timedelta(hours=h) in px),None)
            a0=next((px[f0-dt.timedelta(hours=h)] for h in range(0,6) if f0-dt.timedelta(hours=h) in px),None)
            ref=(a1/a0-1) if a1 and a0 else None
        cond=None
        if ref is not None:
            cond = (a<ref) if l["id"]=="AUDJPY_02" else (a>ref) if l["id"]=="EURGBP_N6L" else (ref<0)
        out.append((l["id"],str(d),bool(win),l["stake"],1.95,cond))
    d+=dt.timedelta(days=1)
for k,v in miss.items(): print("missing",k,len(v),v[:3],v[-3:],file=sys.stderr)
need=set()
for l in legs:
    for ds in miss.get(l["id"],[]):
        d=dt.date.fromisoformat(ds)
        for x in (t.jst(d,l["entry"]).astimezone(t.UTC).replace(tzinfo=None), t.judge_utc(l,d).replace(tzinfo=None)):
            if x not in PX[l["pair"]]: need.add((l["pair"],x.strftime("%Y%m%d_%H")))
json.dump(sorted(need),open(sys.argv[3]+".need","w"))
json.dump(out,open(sys.argv[3],"w"))
c=collections.defaultdict(lambda:[0,0])
for i,_,w,_,_,_ in out: c[i][0]+=w; c[i][1]+=1
for k,(w,n) in c.items(): print(k,w,n,round(100*w/n,1),file=sys.stderr)
