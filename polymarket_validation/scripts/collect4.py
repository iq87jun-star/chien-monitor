# 旧市場の履歴は interval=max では空になるため、解決時刻基準の窓(≤15日)で取得。引数: shard nshards
# W1=[ref-14d, ref+1d] 60分足(T=1/3/7, H3)、W2=[ref-31d, ref-17d] 60分足(T=30)。ref=min(closedTime,endDate)
import json, os, sys, time, urllib.request, datetime as dt
D=os.path.dirname(os.path.abspath(__file__)); PH=os.path.join(D,'ph2'); os.makedirs(PH,exist_ok=True)
k,n=int(sys.argv[1]),int(sys.argv[2])
def get(url, tries=6):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'research-script'}),timeout=30) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code==400: return {'history':[]}
            time.sleep(3*(i+1))
        except Exception: time.sleep(3*(i+1))
    return None
def parse_t(s):
    if not s: return None
    s=s.replace(' ','T')
    if s.endswith('+00'): s+=':00'
    try: return dt.datetime.fromisoformat(s.replace('Z','+00:00'))
    except Exception: return None
rows=[json.loads(l) for l in open(os.path.join(D,'markets.jsonl'))]
done=0
for i,r in enumerate(rows):
    if i%n!=k: continue
    out=os.path.join(PH,f"{r['id']}.json")
    if os.path.exists(out): continue
    try: tok=json.loads(r['clobTokenIds'])[0]
    except Exception: continue
    ts=[t for t in (parse_t(r.get('closedTime')),parse_t(r.get('endDate'))) if t]
    if not ts: continue
    ref=int(min(ts).timestamp()); hist=[]
    ok=True
    for a,b in ((ref-31*86400,ref-17*86400),(ref-14*86400,ref+86400)):
        h=get(f'https://clob.polymarket.com/prices-history?market={tok}&startTs={a}&endTs={b}&fidelity=60')
        if h is None: ok=False; break
        hist+=h.get('history',[])
        time.sleep(0.15)
    if not ok: continue
    json.dump({'ref':ref,'history':hist},open(out+'.tmp','w')); os.replace(out+'.tmp',out); done+=1
    if done%500==0: print('ph2',k,done,time.strftime('%H:%M:%S'),flush=True)
print('ALLDONE',k,flush=True)
