#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
monthly_income_projection.py — 6月起点・攻めプランの月次累計 期待収益 投影。

目的(ユーザー): 2026-06 から、審査突破タイミングを織り込んで、月毎の期待収益額(累計)を出す(攻めプラン)。

モデル(モンテカルロ・月次):
  各プランを口座資産=1.0から月次リターン r~N(μ,σ) で進める。
  ・プロップ(FN $100k, 3.0x): 審査中は収益ゼロ。+8%到達で『資金化』→以後 毎月 純益(分配後)を出金(=収益計上)。
    審査中に−10%抵触で失格→掛け金(返金あり=実質0)で再挑戦。資金化後に−10%抵触で口座喪失→再挑戦。
  ・インスタント(Blueberry $50k, 2.0x): 審査なし=初月から毎月 純益を出金。−10%トレーリング抵触で口座喪失
    →掛け金F再契約して継続。利益は毎サイクル出金(攻めの前提)。
  期待収益(月) = 全パス平均の その月の出金額。累計=月次の累積和。

パラメータは docs/46/47 の実10年確定値から較正:
  μ_month = 年率gross/12, σ_month = (年率gross/Sharpe)/√12 (Sharpe=3種1.71)。
  純益(出金)月額 = payout年額/12 (分配後・確定値)。
⚠ 正規近似のMC。確定系列の裾やリセット空白を完全再現しない=月次の形は目安。額は確定年額にアンカー。
"""
import numpy as np
import datetime as dt

YEN=157.0; SHARPE=1.71; SEED=11; NPATH=20000; MONTHS=24
START=dt.date(2026,6,1)

# プラン定義(docs/46/47確定・攻め)
PLANS = {
 "PROP_FN_$100k_3.0x": dict(
    acct=100_000, payout_year=3_851_273, gross_year=0.3066, fail_year=0.092,
    challenge=True, target=0.08, dd=0.10, fee=0,            # FNは通過で掛け金返金=実質0
 ),
 "INSTANT_BB_$50k_2.0x": dict(
    acct=50_000, payout_year=1_253_219, gross_year=0.1996, fail_year=0.074,
    challenge=False, target=None, dd=0.10, fee=117_086,     # Blueberry掛け金(クーポン)・返金なし
 ),
}

def sim_plan(p, npath=NPATH, months=MONTHS, seed=SEED):
    rng=np.random.default_rng(seed)
    mu=p["gross_year"]/12.0
    sg=(p["gross_year"]/SHARPE)/np.sqrt(12.0)
    monthly_net=p["payout_year"]/12.0    # 資金化後の月次出金(分配後・円)
    target=p["target"]; dd=p["dd"]; challenge=p["challenge"]; fee=p["fee"]
    income=np.zeros((npath,months))      # 各月の出金額(円)
    for i in range(npath):
        eq=1.0; peak=1.0; funded=(not challenge)   # インスタントは初月から funded
        for m in range(months):
            r=rng.normal(mu,sg)
            eq*=(1+r); peak=max(peak,eq)
            if not funded:
                # 審査中: +8%で資金化 / −10%で失格→再挑戦(eqリセット, 費用は返金前提で0計上)
                if (eq-1.0)>=target:
                    funded=True; eq=1.0; peak=1.0     # 資金化口座を新規に1.0から
                elif (eq-1.0)<=-dd:
                    eq=1.0; peak=1.0                    # 再挑戦(FN返金ゆえ費用0)
                # 審査中は収益ゼロ
            else:
                # 資金化/インスタント: 毎月 純益を出金(=収益計上)。口座は出金後も継続(残高は業者資金)。
                income[i,m]+=monthly_net
                # 口座喪失判定(トレーリング/静的-10%)
                base = peak if not challenge else 1.0   # インスタント=トレーリング, プロップ資金化=静的
                if (eq-base)/base <= -dd:
                    income[i,m]-=fee                     # 再契約費用(インスタントのみ>0)
                    eq=1.0; peak=1.0
                    if challenge: funded=False           # プロップは再び審査から
    exp_month=income.mean(axis=0)
    return exp_month, np.cumsum(exp_month)

def cal(m):
    y=START.year+(START.month-1+m)//12; mo=(START.month-1+m)%12+1
    return f"{y}-{mo:02d}"

def main():
    print("="*72); print("攻めプラン 月次累計 期待収益 投影（2026-06起点・MC, 確定値較正）"); print("="*72)
    res={}
    for name,p in PLANS.items():
        em,cum=sim_plan(p); res[name]=(em,cum)
        print(f"\n■ {name}  (年額payout¥{p['payout_year']:,}・{'審査あり' if p['challenge'] else '審査なし'})")
        print(f"   {'月':>8} | {'当月期待':>10} | {'累計期待':>12}")
        for m in range(min(MONTHS,15)):
            print(f"   {cal(m):>8} | ¥{em[m]:>9,.0f} | ¥{cum[m]:>11,.0f}")
        print(f"   ... 12ヶ月累計 ¥{cum[11]:,.0f} / 24ヶ月累計 ¥{cum[-1]:,.0f}")
    # 合算(両プラン同時運用)
    em_sum=sum(res[n][0] for n in res); cum_sum=np.cumsum(em_sum)
    print("\n"+"="*72); print("★合算（PROP+INSTANT 同時運用）月次累計 期待収益"); print("="*72)
    print(f"   {'月':>8} | {'当月期待':>10} | {'累計期待':>12}")
    for m in range(MONTHS):
        mark=""
        # 資金化が立ち上がる目安(プロップ当月期待が monthly_net の50%超え=過半が資金化)
        print(f"   {cal(m):>8} | ¥{em_sum[m]:>9,.0f} | ¥{cum_sum[m]:>11,.0f}{mark}")
    print(f"\n   → 12ヶ月累計 ¥{cum_sum[11]:,.0f} / 24ヶ月累計 ¥{cum_sum[-1]:,.0f}")
    print("\n⚠ 正規近似MC・確定年額アンカー。プロップは突破まで収益0→資金化後に流入(立ち上がりが効く)。")
    print("  実額はエッジ持続(デモ要)・出金規律・スプレッド/スワップで変動。EV(期待)であり保証ではない。")

if __name__=="__main__":
    main()
