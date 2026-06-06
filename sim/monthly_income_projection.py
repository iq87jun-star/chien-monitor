#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
monthly_income_projection.py — 6月起点・月次累計 期待収益 投影（守り/標準/攻め 3ティア）。

目的(ユーザー): 2026-06 から、審査突破タイミングを織り込んだ月毎の期待収益(累計)を、
  攻め・標準・守り の3プランで出す。

モデル(MC・月次): 口座=1.0から月次 r~N(μ,σ)。
  ・プロップ(FN $100k): 審査中は収益0。+8%到達で資金化→以後 毎月 純益(分配後)を出金。
    審査中−10%抵触=失格→再挑戦(FN返金ゆえ費用0)。資金化後−10%抵触=口座喪失→再挑戦。
  ・インスタント(Blueberry $50k): 初月から毎月 純益を出金。−10%トレーリング抵触=口座喪失→掛け金F再契約。
  期待収益(月)=全パス平均の出金額。累計=累積和。倍率↑で μ,σ↑→審査突破も速くなる(自動)。

パラメータ=docs/46/47 実10年確定値:
  gross_year(年率)= payout年額/(口座×分配率×JPY)。μ=gross/12, σ=(gross/Sharpe1.71)/√12。
  純益月額= payout年額/12 (分配後・確定)。
⚠ 正規近似MC・確定年額アンカー。EV(期待)であり保証ではない。実額はエッジ持続(デモ要)・出金規律で変動。
"""
import numpy as np, datetime as dt
YEN=157.0; SHARPE=1.71; SEED=11; NPATH=20000; MONTHS=24; START=dt.date(2026,6,1)

# (口座, payout年額¥[分配後], 年失格f, 審査有無, 掛け金F[再契約・返金なし分])  ← docs/46/47確定
TIERS = {
 "守り": {
   "PROP":    dict(acct=100_000, payout_year=1_221_863, fail_year=0.0004, challenge=True,  fee=0),       # 1.0x
   "INSTANT": dict(acct=50_000,  payout_year=610_931,   fail_year=0.001,  challenge=False, fee=117_086), # 1.0x
 },
 "標準": {
   "PROP":    dict(acct=100_000, payout_year=1_856_446, fail_year=0.009,  challenge=True,  fee=0),       # 1.5x
   "INSTANT": dict(acct=50_000,  payout_year=928_223,   fail_year=0.018,  challenge=False, fee=117_086), # 1.5x
 },
 "攻め": {
   "PROP":    dict(acct=100_000, payout_year=3_851_273, fail_year=0.092,  challenge=True,  fee=0),       # 3.0x
   "INSTANT": dict(acct=50_000,  payout_year=1_253_219, fail_year=0.074,  challenge=False, fee=117_086), # 2.0x
 },
}

def sim_plan(p, npath=NPATH, months=MONTHS, seed=SEED):
    rng=np.random.default_rng(seed)
    gross=p["payout_year"]/(p["acct"]*0.8*YEN)
    mu=gross/12.0; sg=(gross/SHARPE)/np.sqrt(12.0)
    mnet=p["payout_year"]/12.0; ch=p["challenge"]; fee=p["fee"]; dd=0.10; tgt=0.08
    inc=np.zeros((npath,months))
    for i in range(npath):
        eq=1.0; peak=1.0; funded=(not ch)
        for m in range(months):
            eq*=(1+rng.normal(mu,sg)); peak=max(peak,eq)
            if not funded:
                if (eq-1.0)>=tgt: funded=True; eq=1.0; peak=1.0
                elif (eq-1.0)<=-dd: eq=1.0; peak=1.0
            else:
                inc[i,m]+=mnet
                base=1.0 if ch else peak
                if (eq-base)/base<=-dd:
                    inc[i,m]-=fee; eq=1.0; peak=1.0
                    if ch: funded=False
    em=inc.mean(axis=0); return em, np.cumsum(em)

def cal(m):
    y=START.year+(START.month-1+m)//12; mo=(START.month-1+m)%12+1; return f"{y}-{mo:02d}"

def main():
    print("="*78); print("月次累計 期待収益 投影（2026-06起点・守り/標準/攻め・PROP+INSTANT合算・EV）"); print("="*78)
    cum={}
    for tier,plans in TIERS.items():
        em_sum=np.zeros(MONTHS)
        for nm,p in plans.items():
            em,_=sim_plan(p); em_sum=em_sum+em
        cum[tier]=np.cumsum(em_sum)
    # 合算累計 比較表
    print(f"\n  {'月':>8} | {'守り 累計':>12} | {'標準 累計':>12} | {'攻め 累計':>12}")
    for m in range(MONTHS):
        print(f"  {cal(m):>8} | ¥{cum['守り'][m]:>11,.0f} | ¥{cum['標準'][m]:>11,.0f} | ¥{cum['攻め'][m]:>11,.0f}")
    print(f"\n  12ヶ月累計: 守り ¥{cum['守り'][11]:,.0f} / 標準 ¥{cum['標準'][11]:,.0f} / 攻め ¥{cum['攻め'][11]:,.0f}")
    print(f"  24ヶ月累計: 守り ¥{cum['守り'][-1]:,.0f} / 標準 ¥{cum['標準'][-1]:,.0f} / 攻め ¥{cum['攻め'][-1]:,.0f}")

    # 各ティアの内訳(PROP/INSTANT別 12/24ヶ月)
    print("\n  [内訳 12ヶ月 / 24ヶ月 累計]")
    for tier,plans in TIERS.items():
        line=[]
        for nm,p in plans.items():
            _,c=sim_plan(p); line.append(f"{nm} ¥{c[11]:,.0f}/¥{c[-1]:,.0f}")
        print(f"   {tier}: " + " | ".join(line))
    print("\n⚠ 攻めほど立ち上がり速く高EVだが実現は荒い(失格時は当月減・再構築)。守りは低EVだが安定。")
    print("  EV(期待)・確定年額アンカー・正規近似MC。本資金前デモ必須。出金は毎サイクル(口座残高を小さく)。")

if __name__=="__main__":
    main()
