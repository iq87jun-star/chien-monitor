# 追補7: 指値(maker)執行の検証。追補5 で基準 B に残った 2 単位(T=30)の市場について、
# t0 = endDate − 30 日に 1c 有利な指値を 72 時間置いていたら約定したか・約定した市場の結果はどうだったかを、
# 公開の約定データ(Data API v2 /v2/trades、taker 側の行)で測る。口座不要・読み取りのみ。
# 使い方: python3 maker.py <データディレクトリ(markets.jsonl, ph/, sample_ids.json)>  → 結果を標準出力、約定は <データ>/trades/ に保存
import sys, os, io, json, math, time, runpy, contextlib, urllib.request, urllib.parse
from collections import Counter
D=sys.argv[1]; TR=os.path.join(D,'trades'); os.makedirs(TR,exist_ok=True)
HERE=os.path.dirname(os.path.abspath(__file__))
sys.argv=['analyze2.py',D]
with contextlib.redirect_stdout(io.StringIO()):
    g=runpy.run_path(os.path.join(HERE,'analyze2.py'))
data=g['data']; rows=g['rows']; price_at=g['price_at']; cp_bound=g['cp_bound']; DAY=86400; WIN=72*3600; MAXPAGES=200
def get(url, tries=5):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'research-script'}),timeout=60) as r: return json.loads(r.read().decode())
        except Exception: time.sleep(2*(i+1))
    return None
# 対象市場(追補5 と同じ基準 B・T=30 の条件)
units={'F1':[], 'F2':[]}
for d in data:
    if d['end'] is None: continue
    t0=d['end']-30*DAY
    if d['closed']<=t0: continue
    p=price_at(d,t0)
    if p is None: continue
    if 0.95<=p<0.98: units['F1'].append((d,t0,p))
    elif 0.05<=p<0.10: units['F2'].append((d,t0,p))
print('対象', {k:len(v) for k,v in units.items()}, flush=True)
def cond_id(mid):
    f=os.path.join(TR,f'{mid}.cid')
    if os.path.exists(f): return open(f).read().strip()
    r=get(f'https://gamma-api.polymarket.com/markets?id={mid}&closed=true')
    c=(r[0].get('conditionId') if r else '') or ''
    open(f,'w').write(c); return c
def trades_window(mid, cid, t0):
    # 新しい順にページを送り、t0 より古い取引に届いたら止める。[t0, t0+72h] の取引だけ保存。
    f=os.path.join(TR,f'{mid}.json')
    if os.path.exists(f): return json.load(open(f))
    out=[]; cur=None; reached=False
    for page in range(MAXPAGES):
        q={'condition':cid,'limit':1000}
        if cur: q['cursor']=cur
        r=get('https://data-api.polymarket.com/v2/trades?'+urllib.parse.urlencode(q)); time.sleep(0.25)
        if r is None: break
        rows_=r.get('data') or []
        for x in rows_:
            if t0<=x['timestamp']<=t0+WIN: out.append({k:x[k] for k in ('timestamp','side','outcome_index','price','size')})
        if rows_ and min(x['timestamp'] for x in rows_)<t0: reached=True; break
        cur=(r.get('pagination') or {}).get('next_cursor')
        if not cur: reached=True; break
    res={'reached':reached,'trades':out}
    json.dump(res,open(f,'w')); return res
def yes_view(x):
    # taker の約定を YES 換算: ('hit_bid', YES 価格) = YES の bid を叩く、('lift_ask', YES 価格) = YES の ask を取る
    p=float(x['price'])
    if x['outcome_index']==0: return ('hit_bid',p) if x['side']=='SELL' else ('lift_ask',p)
    if x['outcome_index']==1: return ('lift_ask',1-p) if x['side']=='SELL' else ('hit_bid',1-p)
    return (None,None)
res={}
for u,lst in units.items():
    recs=[]; cnt=Counter()
    for i,(d,t0,p0) in enumerate(lst):
        cid=cond_id(d['id'])
        if not cid: cnt['no_condition_id']+=1; continue
        w=trades_window(d['id'],cid,t0)
        if not w['reached']: cnt['not_reached_t0']+=1; continue
        tv=[yes_view(x) for x in w['trades']]
        if u=='F1':
            L=p0-0.01
            strict=any(k=='hit_bid' and v<L-1e-9 for k,v in tv); loose=any(k=='hit_bid' and v<=L+1e-9 for k,v in tv)
        else:
            L=p0+0.01  # YES 換算の売り値 = NO を 1−L で買う
            strict=any(k=='lift_ask' and v>L+1e-9 for k,v in tv); loose=any(k=='lift_ask' and v>=L-1e-9 for k,v in tv)
        recs.append(dict(id=d['id'],ev=d['ev'],y=d['y'],p0=p0,L=L,strict=strict,loose=loose,ntr=len(w['trades'])))
        if (i+1)%50==0: print(u,i+1,'/',len(lst),flush=True)
    res[u]=(recs,cnt)
def ret(u,y,L): return (y/L-1) if u=='F1' else ((1-y)/(1-L)-1)
TAKER={'F1':0.018,'F2':0.011}  # 追補5 参考判定: 基準 B・T=30・実測コスト時の taker 純益
print('\n## 追補7 結果: 指値(maker)執行、基準 B・T=30、指値は 1c 有利・72 時間有効\n')
print('| 単位 | 判定可能 n | 判定不能 | 約定の定義 | 約定 n | 約定率 | q(約定) | q(未約定) | 平均指値 | 約定分の純益 | CP 95% 下限 | taker 純益(追補5) | 資金 1 ドルあたり |')
print('|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
for u,(recs,cnt) in res.items():
    n=len(recs)
    for kind in ('strict','loose'):
        f=[r for r in recs if r[kind]]; nf=[r for r in recs if not r[kind]]; m=len(f)
        if m==0: print(f'| {u} | {n} | {dict(cnt)} | {kind} | 0 | | | | | | | | |'); continue
        qf=sum(r['y'] for r in f)/m; qn=sum(r['y'] for r in nf)/len(nf) if nf else float('nan'); Lm=sum(r['L'] for r in f)/m
        r_=ret(u,qf,Lm); k=sum(r['y'] for r in f)
        qb=cp_bound(k,m,'YES' if u=='F1' else 'NO'); lb=ret(u,qb,Lm)
        print(f'| {u} | {n} | {dict(cnt)} | {"厳しめ" if kind=="strict" else "甘め"} | {m} | {m/n:.0%} | {qf:.3f} | {qn:.3f} | {Lm:.3f} | {r_*100:+.1f}% | {lb*100:+.1f}% | {TAKER[u]*100:+.1f}% | {m/n*r_*100:+.2f}% |')
for u,(recs,cnt) in res.items():
    f=[r for r in recs if r['strict']]; m=len(f)
    if m<30: v='判定せず(厳しめ約定 n<30)'
    else:
        qf=sum(r['y'] for r in f)/m; Lm=sum(r['L'] for r in f)/m; r_=ret(u,qf,Lm)
        lb=ret(u,cp_bound(sum(r['y'] for r in f),m,'YES' if u=='F1' else 'NO'),Lm)
        v='指値で改善' if (r_>TAKER[u] and lb>0) else '改善を確認できず'
    print(f'\n{u} 判定(追補7): {v}')
