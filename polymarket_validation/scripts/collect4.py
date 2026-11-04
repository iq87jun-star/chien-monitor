# 価格履歴の取り直し(追補4)。CLOB の prices-history は解決済みの古い市場で interval=max が空を返し、
# startTs/endTs の幅は約 15 日が上限。そこで closedTime から 14 日窓で遡り、
# min(最後に 0.02<p<0.98 だった時刻, endDate) の 31 日前まで(最大 10 窓)を集める。
# 既に十分な履歴がある ph/<id>.json は飛ばす。並列 4(引数で変更可)、各リクエスト後 0.25 秒待ち。順番は固定シードで混ぜる
# (途中で止まっても期間の偏らない標本になる)。再実行すれば続きから。
# <データディレクトリ>/sample_ids.json があれば、その市場だけを取る。
# 使い方: python3 collect4.py <データディレクトリ> [並列数=4]
import json, os, sys, time, random, re, urllib.request, urllib.error, datetime as dt, threading
from concurrent.futures import ThreadPoolExecutor
NW=int(sys.argv[2]) if len(sys.argv)>2 else 4
D=sys.argv[1]; PH=os.path.join(D,'ph'); os.makedirs(PH,exist_ok=True)
DAY=86400; W=14*DAY
def get(url, tries=6):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'research-script'}),timeout=60) as r: return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code==400: return {'history':[],'error':400}
            time.sleep(3*(i+1))
        except Exception: time.sleep(3*(i+1))
    return None
def ts(s):
    if not s: return None
    s=s.replace(' ','T'); s=re.sub(r'\+00$','+00:00',s)
    try:
        t=dt.datetime.fromisoformat(s.replace('Z','+00:00')); t=t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc); return t.timestamp()
    except Exception: return None
def enough(h, need_from):
    return len(h)>=10 and h[0]['t']<=need_from
def work(r):
    out=os.path.join(PH,f"{r['id']}.json")
    try: tok=json.loads(r['clobTokenIds'])[0]
    except Exception: return 'notoken'
    end_ref=(ts(r.get('closedTime')) or ts(r.get('endDate')) or time.time())+DAY
    start_ref=ts(r.get('startDate')) or ts(r.get('createdAt')) or 0
    ed=ts(r.get('endDate'))
    pts={}; hi=end_ref
    for k in range(10):
        lo=hi-W
        h=get(f'https://clob.polymarket.com/prices-history?market={tok}&startTs={int(lo)}&endTs={int(hi)}&fidelity=60'); time.sleep(0.25)
        if h is None: return 'fail'
        for x in h.get('history',[]): pts[x['t']]=x['p']
        live=[t for t,p in pts.items() if 0.02<p<0.98]
        anchor=min([a for a in (max(live) if live else None, ed) if a is not None], default=end_ref)
        if lo<=anchor-31*DAY or lo<=start_ref: break
        hi=lo
    hist=[{'t':t,'p':pts[t]} for t in sorted(pts)]
    json.dump({'history':hist,'src':'chunked14d'},open(out,'w'))
    return 'ok'
done=set()
while True:
    rows={}
    for l in open(os.path.join(D,'markets.jsonl')):
        r=json.loads(l); rows[r['id']]=r
    SID=os.path.join(D,'sample_ids.json')
    if os.path.exists(SID):  # 追補4: 標本(sample.py)だけを取る
        keep=set(json.load(open(SID))); rows={i:r for i,r in rows.items() if i in keep}
    todo=[]
    for i,r in rows.items():
        if i in done: continue
        f=os.path.join(PH,f'{i}.json')
        if os.path.exists(f):
            try:
                j=json.load(open(f))
                if j.get('src')=='chunked14d': done.add(i); continue
            except Exception: pass
        todo.append(r)
    if not todo: break
    random.Random(20261104).shuffle(todo)
    print('pass todo',len(todo),flush=True); n=0; lock=threading.Lock()
    with ThreadPoolExecutor(NW) as ex:
        for res in ex.map(work,todo):
            n+=1
            if n%1000==0: print('ph',n,res,flush=True)
    for r in todo: done.add(r['id'])
print('ALLDONE',flush=True)
