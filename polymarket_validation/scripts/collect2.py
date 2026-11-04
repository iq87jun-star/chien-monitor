# 月次の end_date 窓で解決済み市場を取り直す(offset 上限 2,000 の回避)。その後、価格履歴が無い市場の履歴を取得。
import json, os, time, urllib.request, datetime as dt
D=os.path.dirname(os.path.abspath(__file__)); PH=os.path.join(D,'ph'); os.makedirs(PH,exist_ok=True)
def get(url, tries=5):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'research-script'}),timeout=60) as r: return json.loads(r.read().decode())
        except Exception: time.sleep(2*(i+1))
    return None
mk=os.path.join(D,'markets.jsonl'); seen=set(json.loads(l)['id'] for l in open(mk)) if os.path.exists(mk) else set()
def month_windows(start=(2024,1), end=(2026,12)):
    y,m=start
    while (y,m)<=end:
        y2,m2=(y+1,1) if m==12 else (y,m+1)
        yield f'{y}-{m:02d}-01', f'{y2}-{m2:02d}-01'; y,m=y2,m2
with open(mk,'a') as f:
    for a,b in month_windows():
        tot=0
        for page in range(0,20):
            m=get(f'https://gamma-api.polymarket.com/markets?closed=true&limit=100&offset={page*100}&order=closedTime&ascending=false&volume_num_min=10000&end_date_min={a}&end_date_max={b}')
            if not m: break
            for r in m:
                if r['id'] in seen: continue
                ev=(r.get('events') or [{}])[0]
                keep={k:r.get(k) for k in ('id','question','outcomes','outcomePrices','clobTokenIds','endDate','closedTime','volumeNum','negRisk','startDate','createdAt','umaResolutionStatus','orderPriceMinTickSize','feesEnabled','takerBaseFee','makerBaseFee')}
                keep['event']={k:ev.get(k) for k in ('id','ticker','title','slug')}
                f.write(json.dumps(keep,ensure_ascii=False)+'\n'); seen.add(r['id']); tot+=1
            f.flush()
            if len(m)<100: break
            time.sleep(0.3)
        print('window',a,b,'new',tot,'total',len(seen),flush=True)
rows=[json.loads(l) for l in open(mk)]; print('markets',len(rows),flush=True)
done=0
for r in rows:
    out=os.path.join(PH,f"{r['id']}.json")
    if os.path.exists(out): continue
    try: tok=json.loads(r['clobTokenIds'])[0]
    except Exception: continue
    h=get(f'https://clob.polymarket.com/prices-history?market={tok}&interval=max&fidelity=60')
    if h is None: continue
    json.dump(h,open(out,'w')); done+=1
    if done%500==0: print('ph',done,flush=True)
    time.sleep(0.25)
print('ALLDONE',flush=True)
