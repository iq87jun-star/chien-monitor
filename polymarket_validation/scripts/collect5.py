# 補完(追補4): 日次窓でも offset 上限 2,000 に達した日を、窓を半分ずつに割って取り直す(上限に達しなくなるまで)。
# 使い方: python3 collect5.py <データディレクトリ> <collect3.log>
import json, os, sys, time, re, urllib.request, datetime as dt
D=sys.argv[1]; LOG=sys.argv[2]
def get(url, tries=5):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'research-script'}),timeout=60) as r: return json.loads(r.read().decode())
        except Exception: time.sleep(2*(i+1))
    return None
mk=os.path.join(D,'markets.jsonl'); seen=set(json.loads(l)['id'] for l in open(mk))
days=[l.split()[1] for l in open(LOG) if l.startswith('day ') and int(l.split()[3])>=2000]
print('capped days',len(days),flush=True)
F=lambda t: t.strftime('%Y-%m-%dT%H:%M:%SZ')
f=open(mk,'a'); still=[]
def window(a,b):
    got=0; new=0
    for page in range(0,20):
        m=get(f'https://gamma-api.polymarket.com/markets?closed=true&limit=100&offset={page*100}&order=closedTime&ascending=false&volume_num_min=10000&end_date_min={F(a)}&end_date_max={F(b)}')
        if not m: break
        got+=len(m)
        for r in m:
            if r['id'] in seen: continue
            ev=(r.get('events') or [{}])[0]
            keep={k:r.get(k) for k in ('id','question','outcomes','outcomePrices','clobTokenIds','endDate','closedTime','volumeNum','negRisk','startDate','createdAt','umaResolutionStatus','orderPriceMinTickSize','feesEnabled','takerBaseFee','makerBaseFee')}
            keep['event']={k:ev.get(k) for k in ('id','ticker','title','slug')}
            f.write(json.dumps(keep,ensure_ascii=False)+'\n'); seen.add(r['id']); new+=1
        f.flush()
        if len(m)<100: break
        time.sleep(0.3)
    if got>=2000:
        if (b-a)<=dt.timedelta(minutes=15): still.append(F(a)); return new
        mid=a+(b-a)/2; return new+window(a,mid)+window(mid,b)
    return new
for d in days:
    a=dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc)
    n=window(a,a+dt.timedelta(days=1)); print('day',d,'new',n,'total',len(seen),flush=True)
print('STILL_CAPPED',still,flush=True); print('LISTDONE',flush=True)
