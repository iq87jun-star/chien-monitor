import sys,os,csv,gzip,glob,json,math,datetime as dt,collections,urllib.request,calendar
M=sys.argv[1]
PAIRS=["EURUSD","GBPUSD","AUDUSD"]
def load(p):
    px={}
    for f in glob.glob(f"{M}/fxcm/{p}_*.csv.gz"):
        try:
            for r in csv.reader(gzip.open(f,"rt")):
                if r[0][0]=="D": continue
                px[dt.datetime.strptime(r[0][:16],"%m/%d/%Y %H:%M")]=(float(r[1])+float(r[5]))/2
        except Exception as e: pass
    return px
PX={p:load(p) for p in PAIRS}
for p in PAIRS: print(p,len(PX[p]),min(PX[p]),max(PX[p]),file=sys.stderr)
def at(px,t,back=0,fwd=5):
    for m in range(0,fwd+1):
        if t+dt.timedelta(minutes=m) in px: return px[t+dt.timedelta(minutes=m)]
    for m in range(1,back+1):
        if t-dt.timedelta(minutes=m) in px: return px[t-dt.timedelta(minutes=m)]
    return None
# --- G: weekend gap fade
G=[];Gall=[];G1h=[]
d=dt.date(2016,12,5)
while d<=dt.date(2026,11,23):
    e=dt.datetime(d.year,d.month,d.day)-dt.timedelta(hours=2)   # Sun 22:00 UTC = Mon 07:00 JST
    x=e+dt.timedelta(hours=23); fr=e-dt.timedelta(hours=48)       # 金曜 22:00 UTC から遡って最後のミッド
    for p in PAIRS:
        px=PX[p]; a=at(px,e,0,5); b=at(px,x,0,5) or at(px,x,60,0); c=at(px,fr,180,0)
        if None in (a,b,c): continue
        gap=a/c-1
        if gap==0 or a==b: continue
        win=(b<a) if gap>0 else (b>a)
        Gall.append((p,str(d),win,gap))
        if abs(gap)>=0.001: G.append((p,str(d),win,gap))
        e1=e+dt.timedelta(hours=1); a1=at(px,e1,0,5); b1=at(px,e1+dt.timedelta(hours=1),0,5)
        if a1 and b1 and a1!=b1 and abs(a1/c-1)>=0.001: G1h.append((p,str(d),(b1<a1) if a1>c else (b1>a1),a1/c-1))
    d+=dt.timedelta(days=7)
# --- M: month-end fix
u="https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?period1=1470000000&period2=1800000000&interval=1d"
j=json.load(urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"}),timeout=60))["chart"]["result"][0]
spx={dt.datetime.utcfromtimestamp(t).date():c for t,c in zip(j["timestamp"],j["indicators"]["quote"][0]["close"]) if c}
sd=sorted(spx)
def london_dst(d):  # BST: last Sun Mar .. last Sun Oct
    y=d.year; ls=lambda m: max(dt.date(y,m,x) for x in range(25,32) if dt.date(y,m,x).weekday()==6)
    return ls(3)<=d<ls(10)
Mr=[]
y,m=2016,12
while (y,m)<=(2026,10):
    last=dt.date(y,m,calendar.monthrange(y,m)[1])
    while last.weekday()>=5: last-=dt.timedelta(days=1)
    prev=[x for x in sd if x<last and (x.year,x.month)==(y,m)]; pm=[x for x in sd if x<dt.date(y,m,1)]
    if prev and pm:
        mtd=spx[prev[-1]]/spx[pm[-1]]-1
        fix=dt.datetime(last.year,last.month,last.day,15 if london_dst(last) else 16); e=fix-dt.timedelta(hours=1)
        for p in PAIRS:
            a=at(PX[p],e,0,3); b=at(PX[p],fix,0,3)
            if a and b and a!=b and mtd!=0: Mr.append((p,str(last),(b>a) if mtd>0 else (b<a),mtd))
    m+=1
    if m==13: y,m=y+1,1
FY=lambda d:int(d[:4])+(d[5:7]=="12")
def rep(name,R,be,gate):
    n=len(R); w=sum(r[2] for r in R); p=w/n; z=(p-be)/math.sqrt(be*(1-be)/n)
    h1=[r for r in R if r[1]<"2021-12"]; h2=[r for r in R if r[1]>="2021-12"]; l12=[r for r in R if r[1]>="2025-11-26"]
    ys={y:[r for r in R if FY(r[1])==y] for y in range(2017,2027)}
    yr=[round(100*sum(r[2] for r in v)/len(v),1) if v else None for v in ys.values()]
    print(f"{name}: n={n} 勝率 {100*p:.1f}% z={z:.2f} 前半 {100*sum(r[2] for r in h1)/max(1,len(h1)):.1f}({len(h1)}) 後半 {100*sum(r[2] for r in h2)/max(1,len(h2)):.1f}({len(h2)}) 直近12か月 {100*sum(r[2] for r in l12)/max(1,len(l12)):.1f}({len(l12)}) 年度別 {yr} 分岐割れ {sum(1 for v in yr if v is not None and v<100*be)}")
    for pr in PAIRS:
        v=[r for r in R if r[0]==pr]; print("    ",pr,len(v),round(100*sum(r[2] for r in v)/max(1,len(v)),1))
    days=collections.defaultdict(list)
    for r in R: days[r[1]].append(r[2])
    print("     日数(独立な回数)",len(days),"日ごと多数決の勝率",round(100*sum(1 for v in days.values() if sum(v)*2>len(v))/len(days),1))
rep("G 窓埋め 23H(|窓|>=0.10%)",G,1/1.95,0.5428)
rep("  参考 G 全週",Gall,1/1.95,0.5428)
rep("  参考 G 1H版(08:00→09:00)",G1h,1/1.90,0.5563)
rep("M 月末の値決め 1H",Mr,1/1.90,0.5563)
json.dump({"G":G,"M":Mr},open(f"{M}/newlegs.json","w"))
