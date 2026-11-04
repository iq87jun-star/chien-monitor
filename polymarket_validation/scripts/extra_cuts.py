# 追補3 用の追加断面: H2 を非スポーツに限定、H1 を negRisk 以外に限定、手数料有効市場の割合
import sys; sys.argv=['analyze2.py','ph2']
src=open('analyze2.py').read().split("for T in (1,3,7,30): table(T)")[0]
exec(src)
import statistics
print('feesEnabled 割合', f"{statistics.mean(1 if r.get('feesEnabled') else 0 for r in rows):.3f}", '件数', len(rows))
ns=[d for d in data if d['cat']!='sports']
print('\n[H2 非スポーツ] 95-98c YES 買い')
def cell(sub,T,lo,hi):
    ps=[];ys=[]
    for d in sub:
        p=price_at(d,T)
        if p is None or not (lo<=p<hi): continue
        ps.append(p); ys.append(d['y'])
    if len(ps)<30: return None
    p=statistics.mean(ps); q=statistics.mean(ys); n=len(ps); miss=n-sum(ys)
    return n,p,q,miss,q*(1/(p+0.005))-1,(1-q)*(1/(1-p+0.005))-1
for label,sub in [('全期間',ns),('前半',[d for d in ns if d['close']<med_close]),('後半',[d for d in ns if d['close']>=med_close]),('2024',[d for d in ns if d['close'].year==2024]),('2025',[d for d in ns if d['close'].year==2025]),('2026',[d for d in ns if d['close'].year==2026]),('politics',[d for d in ns if d['cat']=='politics']),('crypto',[d for d in ns if d['cat']=='crypto']),('other',[d for d in ns if d['cat']=='other'])]:
    for T in (1,3,7,30):
        c=cell(sub,T,0.95,0.98)
        if c: print(f"  {label:8s} T={T:2d}: n={c[0]:4d} p={c[1]:.3f} q={c[2]:.3f} 外れ={c[3]:2d} YES {c[4]*100:+.1f}%  (外れゼロなら3/n上限 {300/c[0]:.1f}% → 最悪 {((1-3/c[0])/(c[1]+0.005)-1)*100:+.1f}%)")
print('\n[H2 スポーツ] 95-98c / 90-95c')
sp=[d for d in data if d['cat']=='sports']
for T in (1,3,7):
    for lo,hi in ((0.90,0.95),(0.95,0.98),(0.98,1.0)):
        c=cell(sp,T,lo,hi)
        if c: print(f"  T={T} {lo:.2f}-{hi:.2f}: n={c[0]} q={c[2]:.3f} 外れ={c[3]} YES {c[4]*100:+.1f}%")
print('\n[H1 negRisk 以外] 2-5c / 5-10c NO 買い')
nn=[d for d in data if not d['neg']]
for label,sub in [('全期間',nn),('前半',[d for d in nn if d['close']<med_close]),('後半',[d for d in nn if d['close']>=med_close]),('politics',[d for d in nn if d['cat']=='politics']),('sports',[d for d in nn if d['cat']=='sports']),('crypto',[d for d in nn if d['cat']=='crypto']),('other',[d for d in nn if d['cat']=='other'])]:
    for T in (1,7):
        for lo,hi in ((0.02,0.05),(0.05,0.10)):
            c=cell(sub,T,lo,hi)
            if c: print(f"  {label:8s} T={T} {lo:.2f}-{hi:.2f}: n={c[0]:4d} p={c[1]:.3f} q={c[2]:.3f} NO {c[5]*100:+.1f}%")
# 95-98c 外れの内訳(T=7、全体)
print('\n[95-98c T=7 の外れ]')
for d in data:
    p=price_at(d,7)
    if p is not None and 0.95<=p<0.98 and d['y']==0: print('  ',d['close'].date(),d['cat'],d['q'][:70],f"p7={p:.3f}",'neg' if d['neg'] else '')
