# Polymarket 解決済み市場(出来高 ≥ $10k)の一覧と YES トークンの時間別価格履歴を収集(標準ライブラリのみ)
import json, os, sys, time, urllib.request, urllib.parse
D=os.path.dirname(os.path.abspath(__file__)); PH=os.path.join(D,'ph'); os.makedirs(PH,exist_ok=True)
def get(url, tries=5):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'research-script'}),timeout=60) as r: return json.loads(r.read().decode())
        except Exception as e:
            time.sleep(2*(i+1))
    return None
mk=os.path.join(D,'markets.jsonl'); seen=set()
if os.path.exists(mk):
    for l in open(mk): seen.add(json.loads(l)['id'])
if len(seen)<14000:
    with open(mk,'a') as f:
        for page in range(0,200):
            m=get(f'https://gamma-api.polymarket.com/markets?closed=true&limit=100&offset={page*100}&order=closedTime&ascending=false&volume_num_min=10000')
            if not m: print('page',page,'empty/fail'); break
            n=0
            for r in m:
                if r['id'] in seen: continue
                ev=(r.get('events') or [{}])[0]
                keep={k:r.get(k) for k in ('id','question','outcomes','outcomePrices','clobTokenIds','endDate','closedTime','volumeNum','negRisk','startDate','createdAt','umaResolutionStatus','orderPriceMinTickSize','feesEnabled','takerBaseFee','makerBaseFee')}
                keep['event']={k:ev.get(k) for k in ('id','ticker','title','slug')}
                f.write(json.dumps(keep,ensure_ascii=False)+'\n'); seen.add(r['id']); n+=1
            f.flush(); print('page',page,'new',n,m[-1]['closedTime'],flush=True)
            if len(m)<100: break
            time.sleep(0.3)
rows=[json.loads(l) for l in open(mk)]
print('markets',len(rows),flush=True)
done=0
for r in rows:
    out=os.path.join(PH,f"{r['id']}.json")
    if os.path.exists(out): continue
    try: tok=json.loads(r['clobTokenIds'])[0]
    except Exception: continue
    h=get(f'https://clob.polymarket.com/prices-history?market={tok}&interval=max&fidelity=60')
    if h is None: print('fail',r['id'],flush=True); continue
    json.dump(h,open(out,'w')); done+=1
    if done%200==0: print('ph',done,flush=True)
    time.sleep(0.25)
print('ALLDONE',flush=True)
