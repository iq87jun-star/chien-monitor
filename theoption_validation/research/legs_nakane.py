import sys,os,json,csv,gzip,lzma,struct,glob,datetime as dt,collections
sys.path.insert(0,sys.argv[1]); import to_live_ops as t
M=sys.argv[2]
legs=[l for l in t.MENU if l.get("gotobi")]
days=[]; d=dt.date(2016,12,1)
while d<=dt.date(2026,11,25):
    if t.is_gotobi(d): days.append(d)
    d+=dt.timedelta(days=1)
want={(dt.datetime(d.year,d.month,d.day,0,55)):d for d in days}
fx=collections.defaultdict(dict)
for p in ["USDJPY","EURJPY","GBPJPY","USDCHF","USDCAD"]:
    for f in glob.glob(f"{M}/fxcm/{p}_*.csv.gz"):
        try:
            for r in csv.reader(gzip.open(f,"rt")):
                if r[0][11:16] in ("00:30","00:55","01:05"):
                    k=dt.datetime.strptime(r[0][:16],"%m/%d/%Y %H:%M"); fx[p][k]=(float(r[1])+float(r[5]))/2
        except Exception as e: pass
for k,v in fx["USDJPY"].items():
    if k in fx["USDCHF"]: fx["CHFJPY"][k]=v/fx["USDCHF"][k]
    if k in fx["USDCAD"]: fx["CADJPY"][k]=v/fx["USDCAD"][k]
def tick(p,d,h,ms0):
    f=f"{M}/duka/{p}_{d}_{h}.bi5"
    try: raw=lzma.decompress(open(f,"rb").read())
    except Exception: return None
    for i in range(0,len(raw),20):
        ms,ask,bid,_,_=struct.unpack(">IIIff",raw[i:i+20])
        if ms>=ms0: return (ask+bid)/2/1000 if ms<ms0+120000 else None
    return None
out=[]; miss=collections.defaultdict(list); src=collections.Counter()
for l in legs:
    p=l["pair"]
    for d in days:
        a=fx[p].get(dt.datetime(d.year,d.month,d.day,0,55)); b=fx[p].get(dt.datetime(d.year,d.month,d.day,1,5)); s="fxcm"
        if a is None or b is None:
            a=tick(p,d,0,55*60000); b=tick(p,d,1,5*60000); s="duka"
        if a is None or b is None: miss[l["id"]].append(str(d)); continue
        r0=fx[p].get(dt.datetime(d.year,d.month,d.day,0,30)) if s=="fxcm" else tick(p,d,0,30*60000)
        cond=(a>r0) if r0 else None
        src[s]+=1
        stake=round(l["stake"]*t.gotobi_mult(l,d)/100)*100
        out.append((l["id"],str(d),bool(b<a),stake,1.85,cond))
for k,v in miss.items(): print("missing",k,len(v),v[:4],v[-3:],file=sys.stderr)
json.dump(sorted({(l["pair"],ds) for l in legs for ds in miss.get(l["id"],[])}),open(sys.argv[3]+".need","w"))
print(dict(src),file=sys.stderr)
json.dump(out,open(sys.argv[3],"w"))
c=collections.defaultdict(lambda:[0,0])
for i,_,w,_,_,_ in out: c[i][0]+=w; c[i][1]+=1
for k,(w,n) in c.items(): print(k,w,n,round(100*w/n,1),file=sys.stderr)
