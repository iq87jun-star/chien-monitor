# 追補3 の操作的定義による H1〜H3 の全期間検証(analyze.py の登録内容を保ち、ゲート判定・頑健性・執行面を追加)
# 使い方: python3 analyze2.py <データディレクトリ(markets.jsonl, ph/)> [books.jsonl] > report.md
import json, os, re, sys, math, statistics, datetime as dt
from collections import defaultdict, Counter
import numpy as np
D=sys.argv[1]; PH=os.path.join(D,'ph'); BOOKS=sys.argv[2] if len(sys.argv)>2 else None
C0=0.005; RNG=np.random.default_rng(20261104); NB=2000
BK=[(0.0,0.02),(0.02,0.05),(0.05,0.10),(0.10,0.20),(0.20,0.40),(0.40,0.60),(0.60,0.80),(0.80,0.90),(0.90,0.95),(0.95,0.98),(0.98,1.0)]
UNITS=[('NO',(0.02,0.05)),('NO',(0.05,0.10)),('YES',(0.90,0.95)),('YES',(0.95,0.98)),('YES',(0.98,1.0))]
TS=(1,3,7,30)
# (b) 語境界つきカテゴリ(語のリストは analyze.py と同一)
SP=re.compile(r'\b(nfl|nba|mlb|nhl|ufc|f1|premier league|la liga|serie a|bundesliga|champions league|epl|ncaa|tennis|open|cup|match|game|vs\.?|spread|o/u|over/under|win on|wins on|grand prix|boxing|golf|atp|wta|esports|cs2|lol|dota|valorant)\b')
CR=re.compile(r'\b(bitcoin|btc|ethereum|eth|solana|sol|crypto|token|coin|xrp|doge|price of)\b|(above|below|hit) \$')
PO=re.compile(r'\b(election|president|senate|house|governor|primary|nominee|minister|parliament|trump|biden|harris|congress|vote|poll|mayor|party|cabinet|secretary|attorney general|impeach|fed|rate cut|tariff|executive order|ceasefire|war|nato|ukraine|israel|iran)\b')
def cat(r):
    q=(r['question']+' '+(r['event'].get('title') or '')).lower()
    if SP.search(q): return 'sports'
    if CR.search(q): return 'crypto'
    if PO.search(q): return 'politics'
    return 'other'
def parse_t(s):
    if not s: return None
    s=s.replace(' ','T') if ' ' in s else s
    s=re.sub(r'\+00$','+00:00',s)
    try:
        t=dt.datetime.fromisoformat(s.replace('Z','+00:00'))
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    except Exception: return None
rows={}
for l in open(os.path.join(D,'markets.jsonl')):
    r=json.loads(l); rows[r['id']]=r
SID=os.path.join(D,'sample_ids.json')
if os.path.exists(SID):  # 追補4: 標本だけを使う(取り直し前の偏った取得分を混ぜない)
    keep=set(json.load(open(SID))); rows={i:r for i,r in rows.items() if i in keep}
cnt=Counter(); data=[]
for r in rows.values():
    cnt['listed']+=1
    f=os.path.join(PH,f"{r['id']}.json")
    if not os.path.exists(f): cnt['no_history_file']+=1; continue
    try:
        j=json.load(open(f)); h=j['history']
        if j.get('src')!='chunked14d': cnt['not_refetched']+=1; continue
    except Exception: cnt['bad_history']+=1; continue
    if len(h)<10: cnt['history_lt10']+=1; continue
    try: op=[float(x) for x in json.loads(r['outcomePrices'])]
    except Exception: cnt['bad_outcome']+=1; continue
    if len(op)!=2 or not (max(op)>=0.99 and min(op)<=0.01): cnt['excl_nonbinary_resolution']+=1; continue  # (a)
    if r.get('feesEnabled'): cnt['excl_fees_enabled']+=1; continue  # (c)
    y=1 if op[0]>0.5 else 0
    ct=parse_t(r.get('closedTime')); ed=parse_t(r.get('endDate'))
    hist=[(x['t'],float(x['p'])) for x in h]; hist.sort()
    live=[t for t,p in hist if 0.02<p<0.98]
    if not live: cnt['never_live']+=1; continue
    data.append(dict(id=r['id'],ev=(r['event'] or {}).get('id') or r['id'],y=y,cat=cat(r),closeA=live[-1],
        closed=ct.timestamp() if ct else hist[-1][0],end=ed.timestamp() if ed else None,
        ts=np.array([t for t,_ in hist]),ps=np.array([p for _,p in hist]),neg=bool(r.get('negRisk')),uma=r.get('umaResolutionStatus'),vol=r.get('volumeNum') or 0))
    cnt['used']+=1
def price_at(d,t):
    i=np.searchsorted(d['ts'],t,side='right')-1
    return float(d['ps'][i]) if i>=0 else None
DAY=86400
def obs(sub,T,anchor):
    out=[]
    for d in sub:
        if anchor=='A': t0=d['closeA']-T*DAY
        else:
            if d['end'] is None: continue
            t0=d['end']-T*DAY
            if d['closed']<=t0: continue  # その時点で既に解決済み → 執行不能
        p=price_at(d,t0)
        if p is not None: out.append((p,d['y'],d['ev']))
    return out
def net(side,p,q,c=C0): return (1-q)/(1-p+c)-1 if side=='NO' else q/(p+c)-1
def binom_cdf(k,n,q):
    if q<=0: return 1.0
    if q>=1: return 1.0 if k>=n else 0.0
    lq,l1=math.log(q),math.log1p(-q); s=0.0
    for i in range(0,k+1): s+=math.exp(math.lgamma(n+1)-math.lgamma(i+1)-math.lgamma(n-i+1)+i*lq+(n-i)*l1)
    return min(s,1.0)
def cp_bound(k,n,side):
    # NO 買い: q の片側 95% 上限 / YES 買い: q の片側 95% 下限
    lo,hi=0.0,1.0
    for _ in range(50):
        mid=(lo+hi)/2
        if side=='NO':
            if binom_cdf(k,n,mid)>0.05: lo=mid
            else: hi=mid
        else:
            if 1-binom_cdf(k-1,n,mid)<0.05 if k>0 else False: lo=mid
            else: hi=mid
    return hi if side=='NO' else lo
def boot_lower(side,o,c=C0):
    g=defaultdict(lambda:[0.0,0,0])
    for p,y,e in o: g[e][0]+=p; g[e][1]+=y; g[e][2]+=1
    A=np.array(list(g.values()),dtype=float); m=len(A)
    idx=RNG.integers(0,m,size=(NB,m)); S=A[idx].sum(axis=1)
    p=S[:,0]/S[:,2]; q=S[:,1]/S[:,2]
    r=(1-q)/(1-p+c)-1 if side=='NO' else q/(p+c)-1
    return float(np.quantile(r,0.05)), m
def stats(o):
    if not o: return None
    n=len(o); p=sum(x[0] for x in o)/n; q=sum(x[1] for x in o)/n; return n,p,q
def inb(o,lo,hi): return [x for x in o if lo<=x[0]<hi]
def table(title,sub,T,anchor):
    o=obs(sub,T,anchor)
    print(f'\n**{title}**(T={T} 日前、基準 {anchor})\n\n| 価格帯 | n | p | q | q−p | NO 買い純益 | YES 買い純益 |\n|---|---:|---:|---:|---:|---:|---:|')
    for lo,hi in BK:
        s=stats(inb(o,lo,hi))
        if not s or s[0]<30: continue
        n,p,q=s; print(f'| {lo:.2f}–{hi:.2f} | {n} | {p:.3f} | {q:.3f} | {q-p:+.3f} | {net("NO",p,q)*100:+.1f}% | {net("YES",p,q)*100:+.1f}% |')
print('# analyze2 出力\n\n件数:',dict(cnt))
yrate=statistics.mean(d['y'] for d in data); medA=float(np.median([d['closeA'] for d in data]))
f=lambda t: dt.datetime.fromtimestamp(t,dt.timezone.utc).date()
print(f'\n使用 {len(data)} 市場、YES 解決率 {yrate:.3f}、期間 {f(min(d["closeA"] for d in data))}〜{f(max(d["closeA"] for d in data))}、中央 {f(medA)}')
print('カテゴリ:',dict(Counter(d['cat'] for d in data)),' negRisk:',sum(d['neg'] for d in data),' イベント数:',len(set(d['ev'] for d in data)))
print('umaResolutionStatus:',dict(Counter(str(d['uma']) for d in data)))
early=[d for d in data if d['closeA']<medA]; late=[d for d in data if d['closeA']>=medA]
CATS=('politics','sports','crypto','other')
# 実測スプレッド
cmeas={}
if BOOKS and os.path.exists(BOOKS):
    B=[json.loads(l) for l in open(BOOKS)]
    print(f'\n## 板の実測(open 市場 {len(B)} 件、解決まで 0〜31 日、YES 板)\n\n| 価格帯(mid) | n | スプレッド中央値 | 75% 点 | best から 1c 内で執行できる額 NO 買い / YES 買い(USD 中央値) | 同 25% 点 | negRisk 比率 |\n|---|---:|---:|---:|---:|---:|---:|')
    for lo,hi in BK:
        s=[b for b in B if lo<=b['mid']<hi]
        if len(s)<5: continue
        sp=sorted(b['spread'] for b in s); cmeas[(lo,hi)]=max(C0,statistics.median(sp)/2)
        print(f'| {lo:.2f}–{hi:.2f} | {len(s)} | {statistics.median(sp)*100:.1f}c | {sp[int(len(sp)*0.75)]*100:.1f}c | {statistics.median(b["no_buy_usd1"] for b in s):,.0f} / {statistics.median(b["yes_buy_usd1"] for b in s):,.0f} | {sorted(b["no_buy_usd1"] for b in s)[len(s)//4]:,.0f} / {sorted(b["yes_buy_usd1"] for b in s)[len(s)//4]:,.0f} | {sum(1 for b in s if b["neg"])/len(s):.0%} |')
print('\n## 全期間(基準 A = 登録版)')
for T in TS: table('全期間',data,T,'A')
print('\n## 全期間(基準 B = 予定終了日 endDate、執行可能)')
for T in TS: table('全期間 B',data,T,'B')
print('\n## 前半/後半(基準 A)')
for T in TS: table('前半',early,T,'A'); table('後半',late,T,'A')
print('\n## カテゴリ別(基準 A)')
for T in TS:
    for c in CATS: table(c,[d for d in data if d['cat']==c],T,'A')
print('\n## negRisk 別(記述のみ、ゲート外。基準 A, T=7)')
table('negRisk',[d for d in data if d['neg']],7,'A'); table('非 negRisk',[d for d in data if not d['neg']],7,'A')
# ゲート判定。PA = 主の基準、OA = G5 で照合するもう一方の基準
def gate(PA,OA,title):
    print(f'\n## {title}\n\n| 戦略 | 価格帯 | T | n | p | q | 純益 {PA} | 純益 {OA} (n) | 前半 / 後半 | カテゴリ(n≥30) | 実測コスト時 | 95% 下限(boot / CP) | 判定 | 落ちたゲート |\n|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|---|')
    verdicts=[]
    for T in TS:
        oA=obs(data,T,PA); oB=obs(data,T,OA); oE=obs(early,T,PA); oL=obs(late,T,PA); oC={c:obs([d for d in data if d['cat']==c],T,PA) for c in CATS}
        for side,(lo,hi) in UNITS:
            a=inb(oA,lo,hi); s=stats(a)
            if not s or s[0]<30: print(f'| {side} | {lo:.2f}–{hi:.2f} | {T} | {len(a)} | | | | | | | | | 判定せず(n<30) | |'); continue
            n,p,q=s; rA=net(side,p,q); fails=[]
            if rA<=0: fails.append('G1')
            sb=stats(inb(oB,lo,hi)); rB=net(side,sb[1],sb[2]) if sb and sb[0]>=30 else None
            if rB is None: fails.append('G5(B n<30)')
            elif rB<=0: fails.append('G5')
            hs=[]
            for o in (oE,oL):
                t=stats(inb(o,lo,hi))
                if t and t[0]>=30:
                    r=net(side,t[1],t[2]); hs.append(f'{r*100:+.1f}%')
                    if r<=0 or r<0.5*rA: fails.append('G2')
                else: hs.append('n<30')
            cs=[]
            for c in CATS:
                t=stats(inb(oC[c],lo,hi))
                if t and t[0]>=30:
                    r=net(side,t[1],t[2]); cs.append(f'{c[:3]} {r*100:+.1f}%')
                    if r<=0: fails.append('G3')
            cm=cmeas.get((lo,hi),C0); rM=net(side,p,q,cm)
            if rM<=0: fails.append('G4')
            bl,m=boot_lower(side,a); k=sum(x[1] for x in a)
            qb=cp_bound(k,n,side); cl=net(side,p,qb); low=min(bl,cl)
            fails=sorted(set(fails))
            v='不合格' if fails else ('合格' if low>0 else '保留')
            miss=(n-k) if side=='YES' else k
            verdicts.append((side,lo,hi,T,v))
            print(f'| {side} | {lo:.2f}–{hi:.2f} | {T} | {n} | {p:.3f} | {q:.3f} | {rA*100:+.1f}% | {"" if rB is None else f"{rB*100:+.1f}%"} ({sb[0] if sb else 0}) | {" / ".join(hs)} | {", ".join(cs)} | {rM*100:+.1f}% (c={cm*100:.2f}c) | {bl*100:+.1f}% / {cl*100:+.1f}% (外れ {miss}, イベント {m}) | {v} | {",".join(fails)} |')
    print('\n判定集計:',dict(Counter(v[-1] for v in verdicts)))
gate('A','B','判定(追補3、正式: 主 = 基準 A、G5 で基準 B を照合)')
gate('B','A','参考(事後に追加、判定は変えない): 主 = 執行可能な基準 B で同じゲート、G5 で基準 A を照合')
print('\n## H3 時間減価: T=7 → T=1 の YES 価格変化(基準 A、解決側別)\n\n| p7 帯 | 解決 | n | 平均 Δp |\n|---|---|---:|---:|')
for lo,hi in [(0.02,0.10),(0.10,0.30),(0.30,0.70),(0.70,0.90),(0.90,0.98)]:
    for y in (1,0):
        ch=[]
        for d in data:
            if d['y']!=y: continue
            p7=price_at(d,d['closeA']-7*DAY); p1=price_at(d,d['closeA']-DAY)
            if p7 is not None and p1 is not None and lo<=p7<hi: ch.append(p1-p7)
        if len(ch)>=30: print(f'| {lo:.2f}–{hi:.2f} | {"YES" if y else "NO"} | {len(ch)} | {statistics.mean(ch):+.3f} |')
# 裾: T=1 で p≥0.95 だったのに NO 解決した市場(UMA の裁量・番狂わせの実例)
print('\n## 裾の実例: 基準 B・T=1 で YES ≥ 0.95 だったが NO 解決(出来高上位 15)\n')
tail=[]
for d in data:
    if d['end'] is None or d['closed']<=d['end']-DAY: continue
    p=price_at(d,d['end']-DAY)
    if p is not None and p>=0.95 and d['y']==0: tail.append((d['vol'],p,d['id'],rows[d['id']]['question']))
for v,p,i,q in sorted(tail,reverse=True)[:15]: print(f'- {q}(id {i}, p={p:.3f}, 出来高 ${v:,.0f})')
print(f'\n該当 {len(tail)} 件')
