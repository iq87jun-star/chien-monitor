# -*- coding: utf-8 -*-
"""
screen_strategies.py
====================
複数の戦略タイプを実データ(日足10年, 全ペア)で正直に検定する。
各戦略は IS(前70%) でだけ「方向/採用」を決め、OOS(後30%) で素の成績を見る。
ここでパラメータ最適化はせず、定番値1セットのみ(カーブフィット回避)。

検定する戦略タイプ(経済的根拠つき):
  S1 ドンチャン・ブレイクアウト(順張り): N日高値更新で買い/安値更新で売り。
     根拠: トレンドフォロー/タイムシリーズ・モメンタムは長期に薄いが持続的なプレミアム。
  S2 移動平均クロス(順張り): 速いSMA>遅いSMAで買い。根拠: 同上。
  S3 RSI平均回帰(逆張り): RSI<30買い/>70売り。根拠: 短期反転(リバーサル)効果。
  S4 ボラ・ブレイクアウト: 前日レンジのk倍を当日始値からブレイクで建つ。
  S5 クロスセクショナル・モメンタム代理(各ペア12ヶ月モメンタムの符号で順張り保有)。

評価: OOSで PF, 期待値, ブートストラップP(PF<=1)。
正直さ: 全ペア集計(プール)でOOSのエッジが有意か。出なければ「出ない」と表示。
"""
import os, json
import numpy as np
import research_backtester as rb

PAIRS = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD","EURJPY","GBPJPY"]
RESULTS = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS, exist_ok=True)


def don_breakout(o,h,l,c, n=20):
    hh=rb.rolling_max(h,n); ll=rb.rolling_min(l,n)
    sig=np.zeros(len(c))
    for i in range(len(c)):
        if np.isnan(hh[i]) or np.isnan(ll[i]): continue
        if c[i]>=hh[i]: sig[i]=1
        elif c[i]<=ll[i]: sig[i]=-1
    return sig

def ma_cross(o,h,l,c, fast=20, slow=50):
    sf=rb.sma(c,fast); ss=rb.sma(c,slow)
    sig=np.zeros(len(c))
    up=(sf>ss);
    for i in range(1,len(c)):
        if np.isnan(sf[i]) or np.isnan(ss[i]): continue
        sig[i]=1 if up[i] else -1
    return sig

def rsi_meanrev(o,h,l,c, n=14, lo=30, hi=70):
    rsi=rb.rsi_wilder(c,n); sig=np.zeros(len(c))
    for i in range(len(c)):
        if rsi[i]<lo: sig[i]=1
        elif rsi[i]>hi: sig[i]=-1
    return sig

def vol_breakout(o,h,l,c, k=0.5):
    sig=np.zeros(len(c))
    for i in range(1,len(c)):
        rng=h[i-1]-l[i-1]
        if rng<=0: continue
        # 当日終値が前日終値+k*rangeを超えていれば翌日順張り(終値ベース近似)
        if c[i]>=c[i-1]+k*rng: sig[i]=1
        elif c[i]<=c[i-1]-k*rng: sig[i]=-1
    return sig

def ts_momentum(o,h,l,c, lookback=252):
    sig=np.zeros(len(c))
    for i in range(lookback,len(c)):
        sig[i]=1 if c[i]>c[i-lookback] else -1
    return sig


STRATS = {
    "S1_Donchian20":  (don_breakout, dict(n=20),            dict(sl_atr=2.0, rr=2.0, max_hold=20)),
    "S2_MAcross20_50":(ma_cross,     dict(fast=20,slow=50), dict(sl_atr=2.5, rr=2.0, max_hold=30)),
    "S3_RSI_meanrev": (rsi_meanrev,  dict(n=14),            dict(sl_atr=1.5, rr=1.5, max_hold=10)),
    "S4_VolBreakout": (vol_breakout, dict(k=0.5),           dict(sl_atr=2.0, rr=2.0, max_hold=15)),
    "S5_TSmom252":    (ts_momentum,  dict(lookback=252),    dict(sl_atr=3.0, rr=2.5, max_hold=60)),
}


def run():
    report={}
    for sname,(fn,kw,simkw) in STRATS.items():
        pooled_oos=[]; pooled_is=[]; per_pair={}
        for pair in PAIRS:
            ts,o,h,l,c=rb.load_daily(pair)
            sig=fn(o,h,l,c,**kw)
            cut=int(len(c)*0.7)
            # IS
            R_is=rb.simulate(pair,o[:cut],h[:cut],l[:cut],c[:cut],sig[:cut],**simkw)
            # OOS (連続性のためにOOS区間だけ渡す; ウォームアップずれは許容)
            R_oos=rb.simulate(pair,o[cut:],h[cut:],l[cut:],c[cut:],sig[cut:],**simkw)
            pooled_is.append(R_is); pooled_oos.append(R_oos)
            per_pair[pair]={"IS":rb.stats(R_is,"IS"),"OOS":rb.stats(R_oos,"OOS")}
        IS=np.concatenate(pooled_is) if pooled_is else np.array([])
        OOS=np.concatenate(pooled_oos) if pooled_oos else np.array([])
        report[sname]={
            "pooled_IS": rb.stats(IS, f"{sname} pooled IS"),
            "pooled_OOS":rb.stats(OOS,f"{sname} pooled OOS"),
            "per_pair": per_pair,
        }
    with open(os.path.join(RESULTS,"screen_results.json"),"w") as f:
        json.dump(report,f,indent=2,default=str)

    # 表示
    print(f"\n{'Strategy':<18}{'IS_PF':>7}{'IS_exp':>8}{'OOS_n':>7}{'OOS_PF':>8}{'OOS_exp':>9}{'OOS_WR':>8}{'P(PF<=1)':>10}")
    print("-"*76)
    for s,r in report.items():
        i=r["pooled_IS"]; oo=r["pooled_OOS"]
        print(f"{s:<18}{i.get('PF',float('nan')):>7}{i.get('expectancy_R',float('nan')):>8}"
              f"{oo.get('n',0):>7}{oo.get('PF',float('nan')):>8}{oo.get('expectancy_R',float('nan')):>9}"
              f"{oo.get('win_rate',float('nan')):>8}{oo.get('boot_P_PF<=1',float('nan')):>10}")
    print("\n判定: OOS_PF>1 かつ P(PF<=1)<0.05 を満たす戦略のみ『エッジの兆候あり』。")
    print("(日足10年・定番値1セット・プール集計。ペア毎の詳細はscreen_results.json)")


if __name__=="__main__":
    run()
