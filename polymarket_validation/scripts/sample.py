# 価格履歴を取る標本を作る(追補4)。母集団 = markets.jsonl(解決済み・出来高 ≥ $10k・endDate 2024-01〜)。
# 寿命(endDate − startDate)が 1 日未満の市場は、T≥1 日前の価格を持ち得ず H1〜H3 のどのセルにも入らないので枠から外す。
# 残りを endDate の月で層に分け、各月から固定シードで一様に最大 2,000 件を抽出(登録版の「各月 2,000 件まで」の規模を保ち、
# 登録版の「各月で後に閉じた順に 2,000 件」という偏りを除く)。
# 使い方: python3 sample.py <データディレクトリ>  → <データディレクトリ>/sample_ids.json、sample_frame.json(層ごとの母数)
import json, os, sys, random, re, datetime as dt
from collections import defaultdict
D=sys.argv[1]; K=2000
def ts(s):
    if not s: return None
    s=s.replace(' ','T'); s=re.sub(r'\+00$','+00:00',s)
    try:
        t=dt.datetime.fromisoformat(s.replace('Z','+00:00')); return (t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)).timestamp()
    except Exception: return None
rows={}
for l in open(os.path.join(D,'markets.jsonl')):
    r=json.loads(l); rows[r['id']]=r
strata=defaultdict(list); short=defaultdict(int)
for i,r in rows.items():
    e=ts(r.get('endDate')); s=ts(r.get('startDate')) or ts(r.get('createdAt'))
    mo=(r.get('endDate') or '')[:7] or 'none'
    if e is not None and s is not None and e-s<86400: short[mo]+=1; continue
    strata[mo].append(i)
rng=random.Random(20261104); ids=[]; frame={}
for mo in sorted(strata):
    L=sorted(strata[mo]); pick=L if len(L)<=K else rng.sample(L,K); ids+=pick
    frame[mo]=dict(population=len(L),sampled=len(pick),short_lived_excluded=short[mo])
json.dump(sorted(ids),open(os.path.join(D,'sample_ids.json'),'w')); json.dump(frame,open(os.path.join(D,'sample_frame.json'),'w'),indent=1)
print('listed',len(rows),'sampled',len(ids)); [print(k,v) for k,v in frame.items()]
