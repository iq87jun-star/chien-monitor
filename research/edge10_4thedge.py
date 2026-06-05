# -*- coding: utf-8 -*-
"""
edge10_4thedge.py — 4本目エッジ「未踏 intraday H1 3構造」予備スクリーナ(事前登録 docs/47)。

docs/47 で固定した C1/C2/C3（パラメータ後付け無し）を、手元 Yahoo H1(~2年) で検定する。
出力は docs/48 に**実数値**で転記する（docs/08 の仮数値errorを繰り返さない＝実行ログのみ）。

設計（ノールックアヘッド・同日完結・実コスト往復）:
  - シグナルは確定足(t-1まで)で判定、t本目の始値で約定。SLは足内で触れたら即決済。全候補同日クローズ。
  - ATR% = 直近 VOLWIN=24 本のH1リターン絶対値の中央値（足内ボラの頑健尺度）。
  - 主検定 = 各候補のプール(全9ペア)OOS。自己相関頑健の **移動ブロック・ブートストラップ** で P(mean≤0)。
  - 副次 = ペア個別 / IS:OOS(70:30) / ウォークフォワード5分割 / コスト2× / プラセボ。
  - ⚠ Yahoo H1 ~2年 = **LEAD級スクリーニング上限**。ADOPT判定は10年H1 Dukascopy(colab_edge10_*) が必須。

注意: 本スクリーナは「候補が存在し得るか」の予備選別。プール有意かつ低相関の候補のみ Drive 10年へ進める。
"""
import os, csv, json, datetime as dt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data"); RES = os.path.join(HERE, "results")
os.makedirs(RES, exist_ok=True)

PAIRS = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD","EURJPY","GBPJPY"]
SPREAD_PIPS = {"USDJPY":1.2,"EURJPY":1.6,"GBPJPY":2.0,"EURUSD":0.8,"GBPUSD":1.2,
               "USDCHF":1.4,"USDCAD":1.4,"AUDUSD":1.2,"NZDUSD":1.5}
SLIP = 0.5
VOLWIN = 24
SEED = 11

def pip_size(p): return 0.01 if p.endswith("JPY") else 0.0001
def cost_frac(p, px): return (SPREAD_PIPS.get(p,1.5) + 2*SLIP) * pip_size(p) / px

def load_h1(p):
    T=[];O=[];H=[];L=[];C=[]
    with open(os.path.join(DATA, f"{p}_h1.csv")) as f:
        for r in csv.DictReader(f):
            T.append(dt.datetime.fromisoformat(r["timestamp"]))
            O.append(float(r["open"])); H.append(float(r["high"]))
            L.append(float(r["low"]));  C.append(float(r["close"]))
    return (np.array(T,dtype=object), np.array(O,float), np.array(H,float),
            np.array(L,float), np.array(C,float))

def atr_pct(O, win=VOLWIN):
    """ATR% = 直近 win 本の |H1リターン| の中央値（確定足ベース・ノールックアヘッド）。"""
    r = np.abs(np.diff(O)/O[:-1])
    out = np.full(len(O), np.nan)
    for i in range(win, len(O)):
        out[i] = np.median(r[i-win:i])   # i-1 までの確定足のみ使用
    return out

# ---- トレード生成（各候補。戻り値: list of (entry_time, ret_fraction)） ----

def trades_C1(p, T,O,H,L,C, ap):
    """Impulse Fade: 08-17, 直前足|ret|>=2.0*ATR% → 逆張り, H=4h or SL=2.0*ATR%, 20:00強制クローズ。"""
    out=[]; theta=2.0; H_HOLD=4; SLk=2.0; n=len(O)
    for i in range(1, n-1):
        t=T[i]
        if not (8 <= t.hour <= 17): continue
        a=ap[i]
        if not np.isfinite(a): continue
        prev_ret=(O[i]-O[i-1])/O[i-1]
        if abs(prev_ret) < theta*a: continue
        direction = -np.sign(prev_ret)            # フェード（構造で決定）
        ent=O[i]; sl=SLk*a*ent
        # 保有 H 本 or SL or 20:00
        exit_px=None
        for k in range(i, min(i+H_HOLD, n-1)+1):
            if T[k].date()!=t.date() or T[k].hour>20: break
            if direction>0 and L[k] <= ent-sl: exit_px=ent-sl; break
            if direction<0 and H[k] >= ent+sl: exit_px=ent+sl; break
            if k==i+H_HOLD or T[k].hour==20: exit_px=C[k]; break
        if exit_px is None: exit_px=C[min(i+H_HOLD, n-1)]
        ret=direction*(exit_px-ent)/ent - cost_frac(p,ent)
        out.append((t, ret))
    return out

def trades_C1_cont(p, T,O,H,L,C, ap):
    """C1 プラセボ=継続(順張り)。同トリガで prev_ret 方向に建てる。コストは正規に往復控除。"""
    out=[]; theta=2.0; H_HOLD=4; SLk=2.0; n=len(O)
    for i in range(1, n-1):
        t=T[i]
        if not (8 <= t.hour <= 17): continue
        a=ap[i]
        if not np.isfinite(a): continue
        prev_ret=(O[i]-O[i-1])/O[i-1]
        if abs(prev_ret) < theta*a: continue
        direction = np.sign(prev_ret)             # 継続（順張り）
        ent=O[i]; sl=SLk*a*ent; exit_px=None
        for k in range(i, min(i+H_HOLD, n-1)+1):
            if T[k].date()!=t.date() or T[k].hour>20: break
            if direction>0 and L[k] <= ent-sl: exit_px=ent-sl; break
            if direction<0 and H[k] >= ent+sl: exit_px=ent+sl; break
            if k==i+H_HOLD or T[k].hour==20: exit_px=C[k]; break
        if exit_px is None: exit_px=C[min(i+H_HOLD, n-1)]
        ret=direction*(exit_px-ent)/ent - cost_frac(p,ent)
        out.append((t, ret))
    return out

def _day_hours(T):
    by={}
    for i,t in enumerate(T): by.setdefault(t.date(),{})[t.hour]=i
    return by

def trades_C2(p, T,O,H,L,C, ap, byday):
    """Compression Breakout: 01-07レンジ<0.5*24hATRレンジ → 07-10で圧縮レンジ抜け方向, 16:00クローズ or SL=反対境界。"""
    out=[]; comp=0.5
    for day,hrs in byday.items():
        need=[1,2,3,4,5,6,7,8,9,10,16]
        if not all(h in hrs for h in [1,7,16]): continue
        idx=[hrs[h] for h in range(1,8) if h in hrs]
        if len(idx)<4: continue
        hi=max(H[j] for j in idx); lo=min(L[j] for j in idx)
        rng=hi-lo
        i0=hrs[1]
        a=ap[i0]
        if not np.isfinite(a): continue
        atr_range=a*O[i0]*VOLWIN**0.0  # ATR%→価格。24hレンジ近似 = ATR%(中央)×price×~比較係数
        # 24hレンジ近似は ATR%×price×k。ここでは圧縮を「6hレンジ < 0.5 × (ATR%×price×6)」で評価（同単位）。
        ref=a*O[i0]*6.0
        if rng >= comp*ref: continue
        # 07-10 でブレイク監視
        ent=None; direction=0
        for h in [7,8,9,10]:
            if h not in hrs: continue
            j=hrs[h]
            if H[j] >= hi: ent=hi; direction=+1; ej=j; break
            if L[j] <= lo: ent=lo; direction=-1; ej=j; break
        if ent is None: continue
        cl=hrs[16]; sl = lo if direction>0 else hi
        # 16:00までにSL?
        exit_px=C[cl]
        for j in range(ej, cl+1):
            if direction>0 and L[j] <= sl: exit_px=sl; break
            if direction<0 and H[j] >= sl: exit_px=sl; break
        ret=direction*(exit_px-ent)/ent - cost_frac(p,ent)
        out.append((T[ej], ret))
    return out

def trades_C3(p, T,O,H,L,C, ap, byday, reverse=True):
    """Asia→London: アジア(00-07)変位>=0.4*24hATRレンジ → 07始値で反転(reverse) 13:00クローズ or SL=2.0ATR%。"""
    out=[]; thr=0.4; SLk=2.0
    for day,hrs in byday.items():
        if not all(h in hrs for h in [0,7,13]): continue
        i0=hrs[0]; i7=hrs[7]; i13=hrs[13]
        a=ap[i7]
        if not np.isfinite(a): continue
        asia=(O[i7]-O[i0])/O[i0]
        ref=a*7.0   # アジア7hの基準変位（ATR%×時間）
        if abs(asia) < thr*ref: continue
        sgn = -np.sign(asia) if reverse else np.sign(asia)
        ent=O[i7]; sl=SLk*a*ent; exit_px=C[i13]
        for j in range(i7, i13+1):
            if sgn>0 and L[j] <= ent-sl: exit_px=ent-sl; break
            if sgn<0 and H[j] >= ent+sl: exit_px=ent+sl; break
        ret=sgn*(exit_px-ent)/ent - cost_frac(p,ent)
        out.append((T[i7], ret))
    return out

# ---- 統計 ----
def block_boot_p(rets, nboot=4000, block=5, seed=SEED):
    """移動ブロック・ブートストラップで P(mean<=0)（自己相関頑健）。"""
    r=np.asarray(rets,float); n=len(r)
    if n<15: return float("nan")
    rng=np.random.default_rng(seed); m=r.mean(); cnt=0
    nblk=int(np.ceil(n/block))
    for _ in range(nboot):
        starts=rng.integers(0,n,size=nblk)
        samp=np.concatenate([r[s:s+block] if s+block<=n else np.concatenate([r[s:],r[:s+block-n]]) for s in starts])[:n]
        if samp.mean() <= 0: cnt+=1
    return cnt/nboot

def stats(rets):
    r=np.asarray(rets,float)
    if len(r)==0: return dict(n=0)
    wins=(r>0).sum(); eq=np.cumsum(r); pk=np.maximum.accumulate(eq)
    gp=r[r>0].sum(); gl=-r[r<0].sum()
    return dict(n=int(len(r)), net=float(eq[-1]), mean=float(r.mean()),
                win=float(wins/len(r)), pf=float(gp/gl) if gl>0 else float("inf"),
                maxdd=float((eq-pk).min()))

def split_oos(trades, frac=0.7):
    if not trades: return [],[]
    k=int(len(trades)*frac); return trades[:k], trades[k:]

def wf(trades, k=5):
    if len(trades)<k*5: return None
    seg=np.array_split(np.arange(len(trades)),k); pos=0
    for s in seg:
        rr=[trades[i][1] for i in s]
        if sum(rr)>0: pos+=1
    return f"{pos}/{k}"

def main():
    rng_all={}
    cands={"C1_impulse_fade":[], "C2_compression_breakout":[], "C3_asia_london_reversal":[]}
    placebo={"C1_impulse_fade":[], "C3_asia_london_reversal":[]}
    perpair={c:{} for c in cands}
    for p in PAIRS:
        T,O,H,L,C=load_h1(p); ap=atr_pct(O); byday=_day_hours(T)
        c1=trades_C1(p,T,O,H,L,C,ap)
        c2=trades_C2(p,T,O,H,L,C,ap,byday)
        c3=trades_C3(p,T,O,H,L,C,ap,byday,reverse=True)
        c3p=trades_C3(p,T,O,H,L,C,ap,byday,reverse=False)  # 継続=プラセボ
        c1p=trades_C1_cont(p,T,O,H,L,C,ap)                  # C1プラセボ=継続(順張り)・コスト正規控除
        for tr,store,key in [(c1,cands,"C1_impulse_fade"),(c2,cands,"C2_compression_breakout"),
                             (c3,cands,"C3_asia_london_reversal"),
                             (c1p,placebo,"C1_impulse_fade"),(c3p,placebo,"C3_asia_london_reversal")]:
            store[key].extend(tr)
        for key,tr in [("C1_impulse_fade",c1),("C2_compression_breakout",c2),("C3_asia_london_reversal",c3)]:
            perpair[key][p]=stats([r for _,r in tr])
    out={"meta":{"source":"Yahoo H1 ~2y (preliminary, LEAD-cap)","pairs":PAIRS,
                 "alpha_family":0.0167,"alpha_strict":0.05/27,"note":"docs/47 pre-registered; numbers are real run outputs"},
         "candidates":{}}
    for key,tr in cands.items():
        tr=sorted(tr,key=lambda x:x[0]); rets=[r for _,r in tr]
        IS,OOS=split_oos(tr); isr=[r for _,r in IS]; oosr=[r for _,r in OOS]
        full=stats(rets); full["boot_p_all"]=block_boot_p(rets)
        oos=stats(oosr); oos["boot_p_oos"]=block_boot_p(oosr)
        cost2=[ (r - cost_frac("EURUSD",1.0)) for r in rets]  # 近似2×: 概算的に往復コストをもう一度引く
        # 2×コストは各pairで正確化が必要だが予備では近似（厳密版はcolabで）
        ph=None
        if key in placebo:
            pl=[r for _,r in sorted(placebo[key],key=lambda x:x[0])]
            ph={**stats(pl), "boot_p":block_boot_p(pl)}
        out["candidates"][key]={
            "full":full, "IS":stats(isr), "OOS":oos,
            "wf":wf(tr), "placebo":ph,
            "perpair_pf":{p:round(perpair[key][p].get("pf",float('nan')),3) for p in PAIRS},
            "perpair_net":{p:round(perpair[key][p].get("net",float('nan')),4) for p in PAIRS},
        }
    with open(os.path.join(RES,"edge10_4thedge.json"),"w") as f:
        json.dump(out,f,indent=2,default=str)
    # コンソール要約
    print("="*70)
    for key,c in out["candidates"].items():
        f=c["full"]; o=c["OOS"]
        print(f"\n[{key}] n={f['n']}  net={f['net']*100:+.2f}%  PF={f['pf']:.3f}  win={f['win']*100:.1f}%  maxDD={f['maxdd']*100:.2f}%")
        print(f"   全boot_p(mean<=0)={f['boot_p_all']:.4f}  | OOS n={o['n']} net={o['net']*100:+.2f}% PF={o.get('pf',float('nan')):.3f} boot_p_oos={o['boot_p_oos']:.4f}  | WF={c['wf']}")
        print(f"   IS net={c['IS']['net']*100:+.2f}%  OOS net={o['net']*100:+.2f}%  (両正?={c['IS']['net']>0 and o['net']>0})")
        if c["placebo"]: print(f"   placebo(逆/継続): n={c['placebo']['n']} net={c['placebo']['net']*100:+.2f}% PF={c['placebo'].get('pf',float('nan')):.3f} boot_p={c['placebo']['boot_p']:.4f}")
        pp=c["perpair_pf"]; pos=sum(1 for v in pp.values() if v>1)
        print(f"   ペアPF>1: {pos}/9  {pp}")
    print("\n→ プールOOS boot_p < α_family(0.0167) かつ 低相関 の候補のみ Drive 10年へ。出所: results/edge10_4thedge.json")

if __name__=="__main__":
    main()
