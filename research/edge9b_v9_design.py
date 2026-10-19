# -*- coding: utf-8 -*-
"""
edge9b_v9_design.py
===================
v9 設計の実証根拠。新しい独立シグナルは探索で出なかった(TOM=棄却 docs/20/edge8、
金曜SHORT鏡像=棄却 edge9)。確実に残るのは v7「月曜04-10 LONG(JPYクロス)」のみ。
そこで v9 は **新シグ15ではなく、確認済み機構から"より高いリスク調整後エッジ"を引き出す**
ことを目的に、検証済みの改良だけを実データで比較し、DD効率(Calmar)最良の構成を選ぶ。

比較する改良（すべて事前に動機づけ済み・恣意的チューニング回避）:
  BASE  : v7既定 = 全月曜・4-10UTC・24h保有・3ペア等加重
  +SKW  : 月初第1週の月曜を除外（docs/12 ゲート11: 月初除外で +31.6%/p=0.002 と改善）
  +H12  : 保有を12hへ（午前のフローを取り、夜間/スワップ/逆行を削減 → DD/効率改善仮説）
  +EW   : ペアをエッジ寄与で加重（各ペアの実現平均bpsで加重、合計1）。等加重との比較。
  +SKW+H12+EW : 上記の合成

評価: net% / maxDD% / 週次Sharpe / Calmar(=net/|maxDD|) / IS:OOS。
DD効率(Calmar)を主指標にする（プロップは-10%枠が制約＝同じ枠で多く積める形が最善）。
※ H1=2.76年 → LEAD級。最終はユーザー10年で。誇張しない。
"""
import os, json
import numpy as np
from edge9_weekendflow_h1 import (load_h1, fwd_returns, entry_mask, maxdd,
                                  boot_p_mean_le0, JPY_CROSS, BAND_HOURS, RESULTS)

HOLD=24

def week_of_month(t):
    return (t.day-1)//7 + 1

def mon_mask(T, hours, skip_first_week=False):
    hs=set(hours)
    return np.array([ (t.weekday()==0 and t.hour in hs and
                       (not skip_first_week or week_of_month(t)!=1)) for t in T ])

def pair_trades(O, mask, hold, pair, direction=1):
    ret=fwd_returns(O, hold, direction, pair)
    return ret[mask[:len(ret)]]

def weekly_pnl(T, O, mask, hold, pair, w, direction=1):
    """週キー -> 加重済みPnL を辞書加算。"""
    ret=fwd_returns(O, hold, direction, pair); m=mask[:len(ret)]
    out={}
    idx=np.flatnonzero(m)
    for i in idx:
        wk=T[i].isocalendar()[:2]
        out[wk]=out.get(wk,0.0)+w*ret[i]
    return out

def metrics_from_weekly(wk_dict):
    keys=sorted(wk_dict);
    series=np.array([wk_dict[k] for k in keys])
    if len(series)<10: return None
    eq=np.cumsum(series); peak=np.maximum.accumulate(eq); dd=(eq-peak).min()
    sh=series.mean()/series.std(ddof=1)*np.sqrt(52) if series.std(ddof=1)>0 else float("nan")
    net=series.sum()
    k=int(len(series)*0.7)
    return dict(n_weeks=len(series), net_pct=round(net*100,2),
                maxDD_pct=round(dd*100,2),
                calmar=round(net/abs(dd),2) if dd<0 else float("inf"),
                weekly_sharpe=round(sh,2),
                IS_net=round(series[:k].sum()*100,2),
                OOS_net=round(series[k:].sum()*100,2))

def build_config(data, hours, hold, skip_first_week, weight_mode):
    # ペア重み
    if weight_mode=="equal":
        w={p:1.0/len(JPY_CROSS) for p in JPY_CROSS}
    else:  # edge: 実現平均bpsで加重（負は0クリップ）
        raw={}
        for p in JPY_CROSS:
            T,O=data[p]; R=pair_trades(O, mon_mask(T,hours,skip_first_week), hold, p)
            raw[p]=max(R.mean(),0.0)
        s=sum(raw.values()) or 1.0
        w={p:raw[p]/s for p in JPY_CROSS}
    # 週次合算
    total={}
    for p in JPY_CROSS:
        T,O=data[p]
        wp=weekly_pnl(T,O, mon_mask(T,hours,skip_first_week), hold, p, w[p])
        for k,v in wp.items(): total[k]=total.get(k,0.0)+v
    return metrics_from_weekly(total), w

def main():
    data={p:load_h1(p) for p in JPY_CROSS}
    print("=== v9 設計比較 (JPYクロス・月曜LONG・H1 2.76年) ===")
    print("主指標=Calmar(=net/|maxDD|)。プロップ-10%枠での積み上げ効率。\n")
    configs=[
        ("BASE v7 (全月曜/24h/等加重)",        BAND_HOURS, 24, False, "equal"),
        ("+SKW (月初週除外)",                  BAND_HOURS, 24, True,  "equal"),
        ("+H12 (保有12h)",                     BAND_HOURS, 12, False, "equal"),
        ("+EW (エッジ加重)",                   BAND_HOURS, 24, False, "edge"),
        ("+SKW+H12 (合成A)",                   BAND_HOURS, 12, True,  "equal"),
        ("+SKW+H12+EW (合成B=v9候補)",         BAND_HOURS, 12, True,  "edge"),
    ]
    rows=[]
    for name,hours,hold,skw,wm in configs:
        m,w=build_config(data, hours, hold, skw, wm)
        if not m: print(f"{name}: too few"); continue
        rows.append((name,m,w))
        wtxt=" ".join(f"{p}:{w[p]:.2f}" for p in JPY_CROSS)
        print(f"{name:30s} net={m['net_pct']:+7.2f}% DD={m['maxDD_pct']:7.2f}% "
              f"Calmar={m['calmar']:5.2f} wSharpe={m['weekly_sharpe']:5.2f} "
              f"IS={m['IS_net']:+6.2f}/OOS={m['OOS_net']:+6.2f}  w[{wtxt}]")
    # 最良Calmar
    best=max(rows, key=lambda r:(r[1]['calmar'] if r[1]['OOS_net']>0 else -1))
    print(f"\n>>> OOS陽性かつCalmar最良: {best[0]}  (Calmar={best[1]['calmar']}, DD={best[1]['maxDD_pct']}%)")
    print("    ※ DDを縮めつつ純益を保てる構成ほどプロップ向き。v9はこの形を既定にする。")
    out={"note":"H1 2.76y LEAD-grade; 10年追認必須",
         "configs":[{"name":n, **m, "weights":{p:round(w[p],3) for p in JPY_CROSS}} for (n,m,w) in rows]}
    with open(os.path.join(RESULTS,"edge9b_v9_design.json"),"w") as f:
        json.dump(out, f, indent=1, default=str)
    print(f"saved -> results/edge9b_v9_design.json")

if __name__=="__main__":
    main()
