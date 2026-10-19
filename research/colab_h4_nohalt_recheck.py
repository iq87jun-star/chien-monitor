# =====================================================================
# Cell 12: halt無し連続バックテスト — 真のequity曲線/MaxDD/連敗を観測
# ---------------------------------------------------------------------
# 目的: ベースラインは+8%で停止し2.6〜4ヶ月で終わる(=2016年限定)。
#   利益目標停止を外して10年連続で回し、止めなかった場合の
#   真のMaxDD・連敗・CAGR・equity曲線を見る。エッジ耐久性の最終確認。
#   ※ run_backtest はそのまま使い、target/floor停止だけ無効化した複製。
# =====================================================================
import numpy as np, pandas as pd, copy

def run_backtest_nohalt(pair, h4, h1, P, usdjpy_h4=None,
                        disable_target=True, disable_floor=True):
    """run_backtest の忠実複製。違いは利益目標(+8%)と任意でequity floor停止を
       無効化し、10年を最後まで回す点のみ。日次リスク制御は維持。"""
    sg=compute_signals(h4,P); pip=pip_size(pair); slip=P["SlippagePoints"]*(pip/10.0)
    T,O,H,L,C,S=_ohlc_arrays(h1)
    idx=list(sg.index); sigv=sg["signal"].to_numpy(); atrv=sg["atr"].to_numpy()
    equity=P["InitialBalance"]; trades=[]; eq_curve=[]
    cur_day=None; day_start_eq=equity; trades_today=0; risk_used=0.0
    day_blocked=False; halted=False
    floor_eq=P["InitialBalance"]*(1-P["EquityFloorDDPct"]/100.0)
    target_eq=P["InitialBalance"]*(1+P["ProfitTargetPct"]/100.0)
    hold_hours=P["MaxHoldBars"]*SIGNAL_TF_HOURS
    for i in range(len(idx)-1):
        t=idx[i]; sig=sigv[i]; atr=atrv[i]; tnext_day=idx[i+1].date()
        if cur_day!=tnext_day:
            cur_day=tnext_day; day_start_eq=equity; trades_today=0
            risk_used=0.0; day_blocked=False
        if (not disable_floor) and equity<=floor_eq: halted=True
        if halted: break
        if (not disable_target) and equity>=target_eq: break
        if sig==0 or not (atr==atr) or atr<=0: continue
        if day_blocked: continue
        if trades_today>=P["MaxTradesPerDay"]: continue
        if risk_used+P["RiskPerTradePct"]>P["MaxDailyRiskPct"]+1e-9: continue
        a=int(np.searchsorted(T, idx[i+1].to_datetime64(), side="right"))
        if a>=len(T): break
        spread0=S[a] if S[a]==S[a] else pip
        if spread0/pip>P["MaxSpreadPips"]: continue
        sd=P["AtrSLMult"]*atr
        if sd/pip<P["MinStopPips"] or sd/pip>P["MaxStopPips"]: continue
        until=T[a]+np.timedelta64(hold_hours,"h")
        b=max(int(np.searchsorted(T,until,side="right")),a+1)
        ujpy=usdjpy_at(idx[i+1],pair,usdjpy_h4); mid=O[a]
        R,off,why,entry=resolve_exit(int(sig),mid,sd,spread0,slip,O,H,L,C,S,a,b,P)
        lots=calc_lots(equity,sd,pair,mid,ujpy,P)
        if lots<P["MinLot"]: continue
        pnl=R*sd*lots*CONTRACT*quote_to_usd(pair,mid,ujpy)
        equity+=pnl; trades_today+=1; risk_used+=P["RiskPerTradePct"]
        ent_time=pd.Timestamp(T[a]); exit_time=pd.Timestamp(T[a+off])
        eq_curve.append((exit_time,equity))
        trades.append(dict(pair=pair,sig=int(sig),ent_time=ent_time,entry=entry,
            exit_time=exit_time,reason=why,lots=lots,stop_pips=sd/pip,
            pnl=pnl,equity=equity,rmultiple=R))
        if equity-day_start_eq <= -P["InitialBalance"]*P["DailyStopPct"]/100.0:
            day_blocked=True
    tdf=pd.DataFrame(trades)
    eqdf=pd.DataFrame(eq_curve,columns=["time","equity"]).set_index("time")
    return tdf, eqdf

# --- 10年連続(利益目標OFF, equity floorもOFF=「止めなかったら」を見る) ---
usdjpy_h4=None
try: _u,_=load_pair("USDJPY"); usdjpy_h4=_u
except Exception as e: print("USDJPY未取得→JPYクロス150固定(警告):",e)

import matplotlib.pyplot as plt
fig,ax=plt.subplots(figsize=(11,5)); rows=[]
for pair in PAIRS:
    try:
        h4,h1=load_pair(pair); Pm=copy.deepcopy(P); Pm["Momentum"]=True
        tdf,eqdf=run_backtest_nohalt(pair,h4,h1,Pm,usdjpy_h4=usdjpy_h4,
                                     disable_target=True,disable_floor=True)
        if len(tdf)==0: print(f"[{pair}] 0件"); continue
        r=tdf["rmultiple"].to_numpy(); eq=eqdf["equity"]
        peak=eq.cummax(); dd=((eq-peak)/peak*100.0)
        yrs=(tdf["exit_time"].max()-tdf["ent_time"].min()).days/365.25
        total_pct=(eq.iloc[-1]/P["InitialBalance"]-1)*100
        cagr=((eq.iloc[-1]/P["InitialBalance"])**(1/yrs)-1)*100 if yrs>0 else float("nan")
        # 連敗
        mx=run=0
        for v in tdf["pnl"]:
            run=run+1 if v<0 else 0; mx=max(mx,run)
        rows.append(dict(pair=pair,n=len(tdf),years=round(yrs,1),
            total_pct=round(total_pct,1),CAGR_pct=round(cagr,1),
            trueMaxDD_pct=round(float(dd.min()),2),max_consec_loss=mx,
            avg_R=round(float(r.mean()),3),
            breach_5pctDD=bool(dd.min()<=-5.0),   # FundedNext総合10%/日次5%相当の目安
            wr=round(float((r>0).mean())*100,1)))
        ax.plot(eqdf.index, eq.values, label=pair, lw=1)
    except Exception as e:
        print(f"[{pair}] スキップ:", e)
ax.axhline(P["InitialBalance"],color="k",lw=0.6,ls="--")
ax.set_title("v4 H4 momentum — 10yr CONTINUOUS equity (no profit-target halt)")
ax.set_ylabel("equity (USD)"); ax.legend(fontsize=8); ax.grid(alpha=0.3)
plt.tight_layout(); plt.savefig(f"{OUT}/v4_nohalt_equity.png",dpi=110); plt.show()

res=pd.DataFrame(rows); display(res)
print("\n読み: 真のMaxDDが-8%以内かつCAGR>0かつ連敗が許容内なら、+8%到達後も")
print("      エッジは持続=チャレンジ後の運用も成立。trueMaxDDが深ければ、")
print("      『+8%で即やめる』運用に限定すべき(=ベースラインが実態)。")
