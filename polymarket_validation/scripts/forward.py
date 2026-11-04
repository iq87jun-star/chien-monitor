# 紙上フォワードの記録(追補6・追補8)。読み取りのみ・口座不要・発注しない。標準ライブラリのみ。
#   scan   : 予定終了日まで 29〜31 日の open 市場(出来高の条件なし。過去検証の「最終出来高 ≥ $10k」は記録時点では分からないため、
#            入口の出来高を残し、評価時に最終出来高 ≥ $10k の部分集合でも集計する)から F1(YES 中値 0.95〜0.98)と F2(YES 中値 0.05〜0.10)を記録
#   settle : 解決した記録に結果を付け、指値(72 時間)が約定したかを約定データで判定
#   report : 単位ごとの集計(taker / maker、手数料控除、Clopper–Pearson 下限、打ち切り規則)
# 使い方: python3 forward.py <scan|settle|report> <記録ディレクトリ> [vol10k(report で最終出来高 ≥ $10k に限る)]   → <記録>/entries.jsonl
import sys, os, re, json, math, time, urllib.request, urllib.parse, datetime as dt
MODE=sys.argv[1]; OUT=sys.argv[2]; os.makedirs(OUT,exist_ok=True); EF=os.path.join(OUT,'entries.jsonl')
DAY=86400; WIN=72*3600; SIZE=50.0
def get(url, tries=5):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'research-script'}),timeout=60) as r: return json.loads(r.read().decode())
        except Exception: time.sleep(2*(i+1))
    return None
def ts(s):
    if not s: return None
    s=s.replace(' ','T'); s=re.sub(r'\+00$','+00:00',s)
    try:
        t=dt.datetime.fromisoformat(s.replace('Z','+00:00')); return (t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)).timestamp()
    except Exception: return None
def load():
    return [json.loads(l) for l in open(EF)] if os.path.exists(EF) else []
def save(E):
    tmp=EF+'.tmp'
    with open(tmp,'w') as f:
        for e in E: f.write(json.dumps(e,ensure_ascii=False)+'\n')
    os.replace(tmp,EF)
SP=re.compile(r'\b(nfl|nba|mlb|nhl|ufc|f1|premier league|la liga|serie a|bundesliga|champions league|epl|ncaa|tennis|open|cup|match|game|vs\.?|spread|o/u|over/under|win on|wins on|grand prix|boxing|golf|atp|wta|esports|cs2|lol|dota|valorant)\b')
CR=re.compile(r'\b(bitcoin|btc|ethereum|eth|solana|sol|crypto|token|coin|xrp|doge|price of)\b|(above|below|hit) \$')
PO=re.compile(r'\b(election|president|senate|house|governor|primary|nominee|minister|parliament|trump|biden|harris|congress|vote|poll|mayor|party|cabinet|secretary|attorney general|impeach|fed|rate cut|tariff|executive order|ceasefire|war|nato|ukraine|israel|iran)\b')
def cat(q):
    q=q.lower()
    return 'sports' if SP.search(q) else 'crypto' if CR.search(q) else 'politics' if PO.search(q) else 'other'
def fee_per_share(e, price):
    # 公式文書の taker 手数料: 1 株あたり feeRate × p × (1−p)。maker は 0。
    fs=e.get('feeSchedule') or {}
    if not e.get('feesEnabled'): return 0.0
    r=fs.get('rate')
    if r is None: return None  # 料率が取れない → 集計で別扱い
    return r*price*(1-price)
if MODE=='scan':
    E=load(); seen={e['id'] for e in E}; now=time.time()
    a=dt.datetime.fromtimestamp(now+29*DAY,dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'); b=dt.datetime.fromtimestamp(now+31*DAY,dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    mk=[]
    for page in range(20):
        m=get(f'https://gamma-api.polymarket.com/markets?closed=false&active=true&limit=100&offset={page*100}&end_date_min={a}&end_date_max={b}')
        if not m: break
        mk+=m
        if len(m)<100: break
        time.sleep(0.3)
    new=0
    for r in mk:
        if r['id'] in seen: continue
        try:
            outs=json.loads(r.get('outcomes') or '[]'); tok=json.loads(r['clobTokenIds'])
        except Exception: continue
        if len(outs)!=2 or len(tok)!=2: continue
        bk=get(f'https://clob.polymarket.com/book?token_id={tok[0]}'); time.sleep(0.25)
        if not bk or not bk.get('bids') or not bk.get('asks'): continue
        bid=max(float(x['price']) for x in bk['bids']); ask=min(float(x['price']) for x in bk['asks']); mid=(bid+ask)/2
        unit='F1' if 0.95<=mid<0.98 else 'F2' if 0.05<=mid<0.10 else None
        if unit is None: continue
        bid1=sum(float(x['size']) for x in bk['bids'] if float(x['price'])>=bid-0.01-1e-9)
        ask1=sum(float(x['size']) for x in bk['asks'] if float(x['price'])<=ask+0.01+1e-9)
        e=dict(id=r['id'],unit=unit,question=r['question'],category=cat(r['question']+' '+((r.get('events') or [{}])[0].get('title') or '')),
               conditionId=r.get('conditionId'),endDate=r.get('endDate'),entry_ts=int(now),bid=bid,ask=ask,mid=mid,
               feesEnabled=bool(r.get('feesEnabled')),feeSchedule=r.get('feeSchedule'),negRisk=bool(r.get('negRisk')),
               # taker: F1 は ask で YES、F2 は 1−bid で NO。maker: 中値から 1c 有利な指値(追補7 と同じ)
               taker_price=ask if unit=='F1' else 1-bid, maker_limit=round(mid-0.01,4) if unit=='F1' else round(1-mid-0.01,4),
               depth_usd_1c=(ask*ask1) if unit=='F1' else ((1-bid)*bid1), volume_at_entry=r.get('volumeNum'))
        E.append(e); seen.add(r['id']); new+=1
    save(E); print(f'scan {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M}Z 候補 {len(mk)} 件、新規記録 {new} 件、累計 {len(E)} 件')
elif MODE=='settle':
    E=load(); now=time.time(); done=0
    for e in E:
        if e.get('outcome') is None:
            r=get(f"https://gamma-api.polymarket.com/markets?id={e['id']}&closed=true"); time.sleep(0.25)
            if r:
                try:
                    op=[float(x) for x in json.loads(r[0]['outcomePrices'])]
                    if max(op)>=0.99 and min(op)<=0.01:
                        e['outcome']=1 if op[0]>0.5 else 0; e['uma']=r[0].get('umaResolutionStatus'); e['closedTime']=r[0].get('closedTime'); e['volume_final']=r[0].get('volumeNum'); done+=1
                    elif r[0].get('closed'): e['outcome']='void'
                except Exception: pass
        if e.get('maker_filled') is None and now>e['entry_ts']+WIN and e.get('conditionId'):
            fill=False; cur=None; reached=False
            for page in range(200):
                q={'condition':e['conditionId'],'limit':1000}
                if cur: q['cursor']=cur
                r=get('https://data-api.polymarket.com/v2/trades?'+urllib.parse.urlencode(q)); time.sleep(0.25)
                if r is None: break
                for x in r.get('data') or []:
                    if not (e['entry_ts']<=x['timestamp']<=e['entry_ts']+WIN): continue
                    p=float(x['price']); yes_bid_hit=(x['outcome_index']==0 and x['side']=='SELL') or (x['outcome_index']==1 and x['side']=='BUY')
                    yp=p if x['outcome_index']==0 else 1-p
                    if e['unit']=='F1' and yes_bid_hit and yp<e['maker_limit']-1e-9: fill=True
                    if e['unit']=='F2' and (not yes_bid_hit) and yp>1-e['maker_limit']+1e-9: fill=True
                rows_=r.get('data') or []
                if fill or (rows_ and min(x['timestamp'] for x in rows_)<e['entry_ts']): reached=True; break
                cur=(r.get('pagination') or {}).get('next_cursor')
                if not cur: reached=True; break
            if reached: e['maker_filled']=fill
    save(E); print(f'settle 新たに解決 {done} 件')
elif MODE=='report':
    E=load()
    def binom_cdf(k,n,q):
        if q<=0: return 1.0
        if q>=1: return 1.0 if k>=n else 0.0
        return min(1.0,sum(math.exp(math.lgamma(n+1)-math.lgamma(i+1)-math.lgamma(n-i+1)+i*math.log(q)+(n-i)*math.log1p(-q)) for i in range(k+1)))
    def lower_win_rate(w,n):  # 勝率の片側 95% 下限
        lo,hi=0.0,1.0
        for _ in range(50):
            mid=(lo+hi)/2
            if w>0 and 1-binom_cdf(w-1,n,mid)<0.05: lo=mid
            else: hi=mid
        return lo
    print(f'記録 {len(E)} 件')
    for u in ('F1','F2'):
        R=[e for e in E if e['unit']==u and e.get('outcome') in (0,1)]
        if len(sys.argv)>3 and sys.argv[3]=='vol10k': R=[e for e in R if (e.get('volume_final') or 0)>=10000]
        win=lambda e: e['outcome']==1 if u=='F1' else e['outcome']==0
        print(f"\n{u}: 記録 {sum(1 for e in E if e['unit']==u)}、解決 {len(R)}、外れ {sum(1 for e in R if not win(e))}")
        for kind in ('taker','maker'):
            S=[e for e in R if kind=='taker' or e.get('maker_filled')]
            if not S: continue
            rets=[]
            for e in S:
                p=e['taker_price'] if kind=='taker' else e['maker_limit']
                yes_price=p if u=='F1' else 1-p
                f=fee_per_share(e,yes_price) if kind=='taker' else 0.0
                if f is None: continue
                rets.append((1.0/(p+f) if win(e) else 0.0)-1)
            if not rets: continue
            n=len(rets); w=sum(1 for e in S if win(e)); m=sum(rets)/n
            pm=sum((e['taker_price'] if kind=='taker' else e['maker_limit']) for e in S)/len(S)
            lb=lower_win_rate(w,len(S))/pm-1
            print(f'  {kind}: n={n} 平均純益 {m*100:+.2f}%  勝率下限で見た純益 {lb*100:+.2f}%  紙上損益(各 ${SIZE:.0f}) ${m*SIZE*n:+.1f}')
        if u=='F1' and sum(1 for e in R if not win(e))>=3: print('  打ち切り規則: F1 の外れが 3 件に到達 → 不合格')
        if len(R)>=100: print('  評価時点(解決 100 件)に到達')
