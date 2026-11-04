# 2026-02〜09 の欠落窓を 10 日窓で取り直す(Gamma が月窓で 500 を返したため)。markets.jsonl に追記。
import json, os, time, urllib.request, datetime as dt
D=os.path.dirname(os.path.abspath(__file__)); mk=os.path.join(D,'markets.jsonl')
def get(url, tries=6):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'research-script'}),timeout=60) as r: return json.load(r)
        except Exception as e: print('retry',i,str(e)[:60],flush=True); time.sleep(3*(i+1))
    return None
seen=set(json.loads(l)['id'] for l in open(mk))
d=dt.date(2026,6,21); end=dt.date(2026,10,1)
with open(mk,'a') as f:
    while d<end:
        d2=min(d+dt.timedelta(days=5),end); a=d.isoformat()+'T00:00:00Z'; b=d2.isoformat()+'T00:00:00Z'; tot=0; fail=False
        for page in range(0,20):
            m=get(f'https://gamma-api.polymarket.com/markets?closed=true&limit=100&offset={page*100}&order=id&ascending=false&volume_num_min=10000&end_date_min={a}&end_date_max={b}')
            if m is None: fail=True; break
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
        print('window',a[:10],b[:10],'new',tot,'total',len(seen),'FAIL' if fail else '',flush=True); d=d2
print('LISTDONE',flush=True)
