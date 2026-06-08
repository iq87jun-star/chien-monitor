# -*- coding: utf-8 -*-
"""
p2_portfolio_validate.py — 第2ポートフォリオ(P2)「ターン・オブ・ウィーク株価指数バスケット」本検証。

P1のv7基準と同一の9ゲートで P2 を採点する。P2の核 = 米独株価指数の【月曜ロング】
(US500 / NAS100 / GER40)を、v7の円月曜マルチショットと同型に【複数指数で分散サンプリング】。

p2_edge_search.py の発見:
  - 月曜ロングは US500(p.019)/NAS100(p.0035)/GER40(p.017) で独立に有意、他曜日は非有意(プラセボ識別成立)。
  - P1(v7/v4/E5合成)との相関は -0.05〜-0.14(低相関)＝真の別分散源。
  - JPYクロス月曜(AUDJPY等)はv7と相関0.33ゆえ除外。暗号月曜は有意だがDD大→衛星扱い(別途)。

ゲート(P1のv7基準・10年日足):
  G1 10年 / G2 ノールックアヘッド+実コスト(構造) / G3 プールperm_p<Bonferroni(N=274,α) /
  G4 プラセボ(月曜のみ有意・他非有意) / G5 年次ジャックナイフ max_p<=0.10 / G6 IS/OOS両+ /
  G7 ウォークフォワード >=4/5 / G8 コスト2×でnet>0 / G9 −10%枠適合(代表サイズでp95 maxDD>=−10%)
  + 相関(対P1/対v7)・脚間相関(分散効果)。

データ: research/data/{US500,NAS100,GER40,...}_d.csv (Yahoo 10年)。出力: results/p2_portfolio_validate.json。
注意: 指数=配当抜きprice index。CFD実コスト/スワップ/配当はデモで要確認。誇張しない。最終確認はDukascopy/Colab。
"""
import os, sys, json, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p2_edge_search as P   # データロード/コスト/統計を再利用(同一定義で一貫性担保)

HERE=os.path.dirname(os.path.abspath(__file__))
CORE=["US500","NAS100","GER40"]          # P2核: 月曜効果が月曜特異+独立に有意な3指数
N_SEARCH=274                              # p2_edge_search の全試行数(探索補正母数)
BONF=0.05/N_SEARCH                        # ≈0.000182

def mon_long(name, mult=1.0):
    """指数 name の 月曜LONG 週次リターン(往復コスト後), index=月曜trade_date。"""
    return P.dow_series(name, 0, +1, mult)

def weekday_pool(names, weekdays, mult=1.0):
    """names×weekdays の LONG トレードを等加重で週次にプール(同週の複数指数を平均)。"""
    parts=[]
    for nm in names:
        for w in weekdays:
            s=P.dow_series(nm,w,+1,mult); s.index=s.index.to_period("W")
            parts.append(s.rename(f"{nm}_{w}"))
    df=pd.concat(parts,axis=1)
    return df.mean(axis=1).dropna()        # 週次バスケット(その週に在る指数の平均)

def perm_p(x,n=5000,seed=11): return P.perm_p(np.asarray(x,float),n_iter=n,seed=seed)

def basket_weekly(names=CORE, mult=1.0):
    """核バスケット(月曜のみ)の週次リターン。"""
    return weekday_pool(names,[0],mult)

def stats_eq(x):
    x=pd.Series(x).dropna()
    eq=(1+x).cumprod(); dd=((eq-eq.cummax())/eq.cummax())
    ann= (1+x.mean())**52-1
    sh = x.mean()/x.std()*np.sqrt(52) if x.std()>0 else float("nan")
    return dict(net_pct=round((eq.iloc[-1]-1)*100,1), n=int(len(x)),
                maxDD_pct=round(dd.min()*100,1), ann_pct=round(ann*100,2),
                sharpe_ann=round(float(sh),2), win_pct=round(float((x>0).mean())*100,1))

def monthly_from_weekly(w):
    w=w.copy(); idx=w.index.to_timestamp() if hasattr(w.index,"to_timestamp") else w.index
    s=pd.Series(w.values,index=pd.to_datetime(idx))
    return s.groupby(s.index.to_period("M")).sum()

def main():
    out={}
    span=P.DF["US500"].index
    print("="*72); print(f"P2 検証: ターン・オブ・ウィーク株価指数バスケット {CORE}"); print("="*72)
    print(f"期間: {span.min().date()} .. {span.max().date()}  (US500 {len(P.DF['US500'])}本)\n")

    # --- 脚間相関(分散効果) ---
    legs={nm:mon_long(nm) for nm in CORE}
    wk={nm:legs[nm].copy() for nm in CORE}
    for nm in wk: wk[nm].index=wk[nm].index.to_period("W")
    L=pd.concat([wk[nm].rename(nm) for nm in CORE],axis=1)
    cc=L.corr()
    pair_corrs={f"{a}-{b}":round(float(cc.loc[a,b]),2) for i,a in enumerate(CORE) for b in CORE[i+1:]}
    print(f"[脚間相関] {pair_corrs}  平均={np.mean(list(pair_corrs.values())):.2f} (1.0でない=分散効く)")

    # --- 個別指数 月曜LONG ゲート ---
    print("\n[個別指数 月曜LONG]")
    per_index={}
    for nm in CORE:
        r=mon_long(nm); st=P.eq_stats(r.values); p=perm_p(r.values)
        per_index[nm]=dict(**st,perm_p=round(p,4))
        print(f"  {nm}: net{st['net_pct']:6.1f}% 勝率{st['win_pct']}% DD{st['maxDD_pct']}% n={st['n']} perm_p={p:.4f}")

    # --- プール(3指数 月曜) vs プラセボ(3指数 火-金) ---
    Bmon=basket_weekly(CORE)               # 月曜バスケット週次
    Bother=weekday_pool(CORE,[1,2,3,4])    # 火-金バスケット(プラセボ)
    p_mon=perm_p(Bmon.values); p_oth=perm_p(Bother.values)
    print(f"\n[G3/G4 プール&プラセボ]")
    print(f"  月曜バスケット : net{stats_eq(Bmon)['net_pct']}% n={len(Bmon)} perm_p={p_mon:.4f} (Bonf α={BONF:.5f})")
    print(f"  火-金プラセボ  : net{stats_eq(Bother)['net_pct']}% n={len(Bother)} perm_p={p_oth:.4f} (非有意なら識別OK)")
    g3=bool(p_mon<BONF); g4=bool(p_mon<0.05 and p_oth>0.05)

    # --- IS/OOS ---
    half=Bmon.index[len(Bmon)//2]; Ris=Bmon[Bmon.index<half]; Roos=Bmon[Bmon.index>=half]
    g6=bool(Ris.sum()>0 and Roos.sum()>0)
    print(f"\n[G6 IS/OOS] IS net{stats_eq(Ris)['net_pct']}%(p={perm_p(Ris.values):.4f}) / OOS net{stats_eq(Roos)['net_pct']}%(p={perm_p(Roos.values):.4f}) → {g6}")

    # --- 年次ジャックナイフ ---
    yrs=sorted(set(Bmon.index.year))
    jk={int(y):round(perm_p(Bmon[Bmon.index.year!=y].values),3) for y in yrs}
    jkmax=max(jk.values()); g5=bool(jkmax<=0.10)
    print(f"[G5 年次JK] max_p={jkmax:.3f} → {g5}   {jk}")

    # --- ウォークフォワード(5分割) ---
    wf=0; seg_net=[]
    for s in range(5):
        a=Bmon.index[int(len(Bmon)*s/5)]; b=Bmon.index[min(len(Bmon)-1,int(len(Bmon)*(s+1)/5))]
        seg=Bmon[(Bmon.index>=a)&(Bmon.index<b)] if s<4 else Bmon[Bmon.index>=a]
        net=stats_eq(seg)['net_pct']; seg_net.append(net)
        if net>0: wf+=1
    g7=bool(wf>=4)
    print(f"[G7 WF] {wf}/5 各期net={seg_net} → {g7}")

    # --- コスト2× ---
    B2=basket_weekly(CORE,2.0); g8=bool(stats_eq(B2)['net_pct']>0)
    print(f"[G8 コスト2×] net{stats_eq(B2)['net_pct']}% → {g8}")

    # --- 相関(対P1合成 / 対v7) ---
    P1,p1legs,_=P.build_p1()
    Bm=monthly_from_weekly(Bmon)
    def corr(a,b):
        j=pd.concat([a.rename('a'),b.rename('b')],axis=1).dropna();
        return (round(float(j['a'].corr(j['b'])),3),len(j)) if len(j)>=24 else (None,len(j))
    c_p1=corr(Bm,P1); c_v7=corr(Bm,p1legs['v7']); c_v4=corr(Bm,p1legs['v4']); c_e5=corr(Bm,p1legs['e5'])
    print(f"\n[相関] 対P1合成={c_p1[0]}(n{c_p1[1]}) 対v7={c_v7[0]} 対v4={c_v4[0]} 対E5={c_e5[0]}")

    # --- バスケット成績(等加重・週次) ---
    bs=stats_eq(Bmon)
    print(f"\n[バスケット成績(等加重,生リターン)] net{bs['net_pct']}% 年率{bs['ann_pct']}% "
          f"Sharpe(年){bs['sharpe_ann']} maxDD{bs['maxDD_pct']}% 勝率{bs['win_pct']}% n={bs['n']}")

    gates={"G3_perm_bonf":g3,"G4_placebo":g4,"G5_jackknife":g5,"G6_IS_OOS":g6,"G7_wf":g7,"G8_cost2x":g8}
    npass=sum(gates.values())
    core_adopt=all(gates.values())
    # 判定はP1と同一規約(docs/40 / colab_validate_all_v7standard.py):
    #   ADOPT=全コア通過 / STRONG-LEAD=G4・G6・G7・G8通過(G3 Bonf か G5 JK のみ未達) / LEAD=それ未満
    grade="ADOPT" if core_adopt else ("STRONG-LEAD" if (g4 and g6 and g7 and g8) else "LEAD")
    print(f"\n→ コアゲート {npass}/6 (G1/G2/G9は別途) / 判定: {grade}")
    if not g3: print(f"   ※プールperm_p={p_mon:.4f} は探索補正α={BONF:.5f}に未達＝STRONG-LEAD(P1のv7と同じ性質)")

    out=dict(span=[str(span.min().date()),str(span.max().date())],core=CORE,N_search=N_SEARCH,bonf=BONF,
             leg_pair_corr=pair_corrs, per_index=per_index,
             pool_mon=dict(**stats_eq(Bmon),perm_p=round(p_mon,4)),
             placebo_other=dict(**stats_eq(Bother),perm_p=round(p_oth,4)),
             is_oos=dict(is_net=stats_eq(Ris)['net_pct'],oos_net=stats_eq(Roos)['net_pct']),
             jackknife=jk, jk_max_p=jkmax, wf=f"{wf}/5", wf_seg_net=seg_net,
             cost2x_net=stats_eq(B2)['net_pct'],
             corr_P1=c_p1[0], corr_v7=c_v7[0], corr_v4=c_v4[0], corr_e5=c_e5[0],
             basket=bs, gates=gates, grade=grade)
    with open(os.path.join(HERE,"results","p2_portfolio_validate.json"),"w") as f:
        json.dump(out,f,ensure_ascii=False,indent=2,default=str)
    print("\n保存: research/results/p2_portfolio_validate.json")
    return out

if __name__=="__main__":
    main()
