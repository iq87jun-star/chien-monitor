# 執行面の実測: open 市場(出来高 ≥ $10k、解決まで 0〜30 日)の YES 板をサンプリングし、
# 価格帯別のスプレッドと best から 1c/2c 以内の厚み(USD)を記録する(標準ライブラリのみ、口座不要)。
# 使い方: python3 books.py <出力ディレクトリ>   → <出力>/books.jsonl に追記
import json, os, sys, time, urllib.request, datetime as dt
OUT=sys.argv[1] if len(sys.argv)>1 else os.path.dirname(os.path.abspath(__file__)); os.makedirs(OUT,exist_ok=True)
def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'research-script'}),timeout=60) as r: return json.loads(r.read().decode())
        except Exception: time.sleep(2*(i+1))
    return None
now=dt.datetime.now(dt.timezone.utc); a=now.strftime('%Y-%m-%d'); b=(now+dt.timedelta(days=31)).strftime('%Y-%m-%d')
mk=[]
for page in range(0,20):
    m=get(f'https://gamma-api.polymarket.com/markets?closed=false&active=true&limit=100&offset={page*100}&volume_num_min=10000&end_date_min={a}&end_date_max={b}&order=volumeNum&ascending=false')
    if not m: break
    mk+=m
    if len(m)<100: break
    time.sleep(0.3)
print('open markets',len(mk),flush=True)
def depth(levels, best, side, w):
    # side='bid': price >= best-w ; 'ask': price <= best+w。USD = price*size
    s=0.0
    for l in levels:
        p=float(l['price']); z=float(l['size'])
        if (side=='bid' and p>=best-w-1e-9) or (side=='ask' and p<=best+w+1e-9): s+=p*z
    return s
with open(os.path.join(OUT,'books.jsonl'),'a') as f:
    for r in mk:
        try: tok=json.loads(r['clobTokenIds'])[0]
        except Exception: continue
        bk=get(f'https://clob.polymarket.com/book?token_id={tok}')
        time.sleep(0.25)
        if not bk or not bk.get('bids') or not bk.get('asks'): continue
        bb=max(float(x['price']) for x in bk['bids']); ba=min(float(x['price']) for x in bk['asks'])
        rec=dict(ts=now.isoformat(),id=r['id'],q=r['question'],end=r.get('endDate'),neg=r.get('negRisk'),tick=r.get('orderPriceMinTickSize'),
                 fees=r.get('feesEnabled'),vol=r.get('volumeNum'),bid=bb,ask=ba,mid=(bb+ba)/2,spread=ba-bb,
                 bid1=depth(bk['bids'],bb,'bid',0.01),ask1=depth(bk['asks'],ba,'ask',0.01),
                 bid2=depth(bk['bids'],bb,'bid',0.02),ask2=depth(bk['asks'],ba,'ask',0.02))
        f.write(json.dumps(rec,ensure_ascii=False)+'\n')
print('DONE',flush=True)
