# 補完: 月次窓が offset 上限(2,000 件)で切り詰められた月を、日次の end_date 窓で取り直す(追補3)。
# 一覧だけを markets.jsonl に追記する。履歴は collect2.py を再実行すれば未取得分だけ取る。
# 使い方: python3 collect3.py <データディレクトリ> 2025-03 2026-12
import json, os, sys, time, urllib.request, datetime as dt
D=sys.argv[1]; a0=dt.date.fromisoformat(sys.argv[2]+'-01'); y,m=map(int,sys.argv[3].split('-'))
a1=dt.date(y+1,1,1) if m==12 else dt.date(y,m+1,1)
def get(url, tries=5):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'research-script'}),timeout=60) as r: return json.loads(r.read().decode())
        except Exception: time.sleep(2*(i+1))
    return None
mk=os.path.join(D,'markets.jsonl'); seen=set(json.loads(l)['id'] for l in open(mk)) if os.path.exists(mk) else set()
capped=[]
with open(mk,'a') as f:
    d=a0
    while d<a1:
        e=d+dt.timedelta(days=1); tot=0; got=0
        for page in range(0,20):
            m=get(f'https://gamma-api.polymarket.com/markets?closed=true&limit=100&offset={page*100}&order=closedTime&ascending=false&volume_num_min=10000&end_date_min={d}&end_date_max={e}')
            if not m: break
            got+=len(m)
            for r in m:
                if r['id'] in seen: continue
                ev=(r.get('events') or [{}])[0]
                keep={k:r.get(k) for k in ('id','question','outcomes','outcomePrices','clobTokenIds','endDate','closedTime','volumeNum','negRisk','startDate','createdAt','umaResolutionStatus','orderPriceMinTickSize','feesEnabled','takerBaseFee','makerBaseFee')}
                keep['event']={k:ev.get(k) for k in ('id','ticker','title','slug')}
                f.write(json.dumps(keep,ensure_ascii=False)+'\n'); seen.add(r['id']); tot+=1
            f.flush()
            if len(m)<100: break
            time.sleep(0.3)
        if got>=2000: capped.append(str(d))
        print('day',d,'listed',got,'new',tot,'total',len(seen),flush=True)
        d=e
print('CAPPED_DAYS',capped,flush=True); print('LISTDONE',flush=True)
