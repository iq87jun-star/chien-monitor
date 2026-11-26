import json,collections,math,sys
M=sys.argv[1]; rows=json.load(open(f"{M}/night10c.json"))+json.load(open(f"{M}/nk10c.json"))
FY=lambda d:int(d[:4])+(d[5:7]=="12")
def rep(name,sel):
    R=[r for r in rows if sel(r[0]) and r[5] is not None]
    def wr(x): return (sum(r[2] for r in x),len(x))
    def diff(x):
        a=wr([r for r in x if r[5]]); b=wr([r for r in x if not r[5]]); 
        if not a[1] or not b[1]: return None
        return a[0]/a[1]-b[0]/b[1],a,b
    d,a,b=diff(R); p=(a[0]+b[0])/(a[1]+b[1]); z=d/math.sqrt(p*(1-p)*(1/a[1]+1/b[1]))
    h1=diff([r for r in R if r[1]<"2021-12"]); h2=diff([r for r in R if r[1]>="2021-12"])
    ys=[diff([r for r in R if FY(r[1])==y]) for y in range(2017,2027)]; pos=sum(1 for y in ys if y and y[0]>0)
    print(f"{name}: 条件あり {100*a[0]/a[1]:.1f}% (n={a[1]}) / なし {100*b[0]/b[1]:.1f}% (n={b[1]}) 差 {100*d:+.1f}pt z={z:.2f} | 前半 {100*h1[0]:+.1f} 後半 {100*h2[0]:+.1f} | 年度別プラス {pos}/10", [round(100*y[0],1) if y else None for y in ys])
rep("C AUDJPY02 当日下げ",lambda i:i=="AUDJPY_02")
rep("D EURGBP 当日上げ",lambda i:i=="EURGBP_N6L")
rep("R1 月曜3本 金曜下落",lambda i:i.endswith("_N6"))
for i in ["EURJPY_N6","AUDJPY_N6","NZDJPY_N6"]: rep("   "+i,lambda x,i=i:x==i)
rep("R2 仲値 run-up>0",lambda i:i.endswith("_NK"))
for i in ["USDJPY_NK","EURJPY_NK","GBPJPY_NK","CHFJPY_NK","CADJPY_NK"]: rep("   "+i,lambda x,i=i:x==i)
