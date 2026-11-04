# Polymarket 事前登録仮説(H1 ロングショット / H2 本命 / H3 時間減価)の検証
import json, os, re, statistics, datetime as dt, sys
from collections import defaultdict
D=os.path.dirname(os.path.abspath(__file__)); PH=os.path.join(D,'ph')
rows=[json.loads(l) for l in open(os.path.join(D,'markets.jsonl'))]
def cat(r):
    q=(r['question']+' '+(r['event'].get('title') or '')).lower()
    if re.search(r'\b(nfl|nba|mlb|nhl|ufc|f1|premier league|la liga|serie a|bundesliga|champions league|epl|ncaa|tennis|open|cup|match|game|vs\.?|spread|o/u|over/under|win on|wins on|grand prix|boxing|golf|atp|wta|esports|cs2|lol|dota|valorant)\b',q): return 'sports'
    if re.search(r'(bitcoin|btc|ethereum|eth|solana|sol|crypto|token|coin|xrp|doge|price of|above \$|below \$|hit \$)',q): return 'crypto'
    if re.search(r'(election|president|senate|house|governor|primary|nominee|minister|parliament|trump|biden|harris|congress|vote|poll|mayor|party|cabinet|secretary|attorney general|impeach|fed |rate cut|tariff|executive order|ceasefire|war|nato|ukraine|israel|iran)',q): return 'politics'
    return 'other'
def parse_t(s):
    s=s.replace('+00','+00:00').replace(' ','T') if ' ' in s else s
    try: return dt.datetime.fromisoformat(s.replace('Z','+00:00'))
    except Exception: return None
data=[]
for r in rows:
    f=os.path.join(PH,f"{r['id']}.json")
    if not os.path.exists(f): continue
    try: h=json.load(open(f))['history']
    except Exception: continue
    if len(h)<10: continue
    try: op=json.loads(r['outcomePrices']); y=1 if float(op[0])>0.5 else 0
    except Exception: continue
    ct=parse_t(r['closedTime'] or '') or parse_t(r['endDate'] or '')
    if ct is None: continue
    hist=[(dt.datetime.fromtimestamp(x['t'],dt.timezone.utc),float(x['p'])) for x in h]
    # 実質的な最終取引(価格が 0/1 に張り付く前)を解決時刻の代理にする: 最後の 0.02<p<0.98 の時刻
    last_live=max([t for t,p in hist if 0.02<p<0.98], default=None)
    if last_live is None: continue
    data.append(dict(id=r['id'],y=y,cat=cat(r),close=last_live,hist=hist,vol=r['volumeNum'],neg=r['negRisk'],q=r['question']))
print('市場数',len(data),'解決 YES 率',f"{statistics.mean(d['y'] for d in data):.3f}",'カテゴリ',dict(sorted(((c,sum(1 for d in data if d['cat']==c)) for c in set(d['cat'] for d in data)),key=lambda x:-x[1])))
med_close=sorted(d['close'] for d in data)[len(data)//2]; print('期間', min(d['close'] for d in data).date(), '〜', max(d['close'] for d in data).date(), '中央', med_close.date())
def price_at(d,T):
    cutoff=d['close']-dt.timedelta(days=T); pts=[p for t,p in d['hist'] if t<=cutoff]
    return pts[-1] if pts else None
BK=[(0.0,0.02),(0.02,0.05),(0.05,0.10),(0.10,0.20),(0.20,0.40),(0.40,0.60),(0.60,0.80),(0.80,0.90),(0.90,0.95),(0.95,0.98),(0.98,1.0)]
def table(T, sub=None, label=''):
    print(f'\n--- T={T}日前の YES 価格帯別: 件数 / 平均価格 p / 実現 YES 率 q / q−p / NO買いの純損益(1$あたり、スプレッド片道0.5c控除) / YES買いの純損益 {label} ---')
    for lo,hi in BK:
        ps=[];ys=[]
        for d in (sub or data):
            p=price_at(d,T)
            if p is None or not (lo<=p<hi): continue
            ps.append(p); ys.append(d['y'])
        if len(ps)<30: continue
        p=statistics.mean(ps); q=statistics.mean(ys); n=len(ps)
        # NO 買い: 1 ドルで NO を (1-p+0.005) で買う → NO が当たれば 1/(1-p+0.005) ドル
        no_ret=(1-q)*(1/(1-p+0.005))-1; yes_ret=q*(1/(p+0.005))-1
        se=(q*(1-q)/n)**0.5
        print(f'  {lo:.2f}-{hi:.2f}: n={n:5} p={p:.3f} q={q:.3f} (±{2*se:.3f}) q−p={q-p:+.3f} | NO {no_ret*100:+6.1f}% | YES {yes_ret*100:+6.1f}%')
for T in (1,3,7,30): table(T)
# 前半/後半
early=[d for d in data if d['close']<med_close]; late=[d for d in data if d['close']>=med_close]
table(7,early,'[前半]'); table(7,late,'[後半]')
for c in ('politics','sports','crypto','other'):
    sub=[d for d in data if d['cat']==c]
    if len(sub)>=200: table(7,sub,f'[{c}]')
# H3: 時間減価 — T=7→T=1 の価格変化を、解決側別・価格帯別に
print('\n--- H3 T=7 → T=1 の YES 価格変化(平均)、解決側別 ---')
for lo,hi in [(0.02,0.10),(0.10,0.30),(0.30,0.70),(0.70,0.90),(0.90,0.98)]:
    for y in (1,0):
        ch=[price_at(d,1)-price_at(d,7) for d in data if d['y']==y and price_at(d,7) is not None and price_at(d,1) is not None and lo<=price_at(d,7)<hi]
        if len(ch)>=30: print(f'  p7 {lo:.2f}-{hi:.2f} 解決={"YES" if y else "NO "}: n={len(ch):5} Δp={statistics.mean(ch):+.3f}')
