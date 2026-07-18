# -*- coding: utf-8 -*-
"""
colab_crash_replay.py — クラッシュ・リプレイ(docs/168事前登録)【ユーザーColab用】。

2024-08-05(月)と2025-04-09(水)を、EAの実仕様(全レッグSL・日次-4%ガード)込みで
H1解像度で再現し、PD間引き3x(主判定)と季節1.5x(副・当時のSLなし仕様)の
「実効日次損失」を測る。スリッページ{0/0.1%/0.3%}の3シナリオ。

使い方(Colab): 「すべて実行」→ Driveマウント許可 → 最後の### 判定ブロックを貼り付け。
FX H1はDrive(dukascopy_data_h1)、指数/金はDrive優先→無ければYahoo 60分足で補完。
"""
import os, json, math
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
H1_DIR = f"{DRIVE_BASE}/dukascopy_data_h1"
OUT_JSON = f"{DRIVE_BASE}/crash_replay.json"

EVENTS = ["2016-07-06","2018-02-05","2018-11-12","2020-03-12","2020-03-19",
          "2024-08-05","2025-04-09"]
SLIPS = [0.0, 0.001, 0.003]          # SL/ガード約定の不利方向スリッページ(価格比)
GUARD_DAY = -0.04                    # EA日次ガード
FN_DAY = -0.05                       # FN日次違反ライン

# PD間引き3x(docs/135・EA実装値)
PD = dict(v7_pairs=["EURJPY","GBPJPY"], v7_hours=[4,6,8,10], v7_shot=0.00136,
          emon_syms=["US500","NAS100","GER40"], emon_hours=[9,14], emon_shot=0.00182,
          v4_pairs=["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD","EURJPY","GBPJPY"],
          v4_risk=0.0032, e5_assets=["XAUUSD","NAS100"], e5_leg=0.0175, cat_atr=2.5, v4_slatr=1.5)
# 季節1.5x(WR4焼き込み・当時仕様=月曜系/E5/SJulはSLなし)
SEAS_W = {"2024-08-05": dict(v4=.331, EMon=.206, E5=.328, SJul=.135),
          "2025-04-09": dict(EMon=.773, SJul=.227),
          "2016-07-06": dict(SJul=1.0),
          "2018-02-05": dict(v4=1.0),          # 2月=v4単騎(月間保有レッグなし=季節側は対象外)
          "2018-11-12": dict(EMonX=.181, SJul=.819),
          "2020-03-12": dict(v4=.377, EMon=.405, E5=.218),
          "2020-03-19": dict(v4=.377, EMon=.405, E5=.218)}
SEAS_MULT = 1.5
SEAS_E5 = ["XAUUSD","US500","NAS100","GER40"]
YH = {"US500":"^GSPC","NAS100":"^NDX","GER40":"^GDAXI","XAUUSD":"GC=F",
      "JP225":"^N225","UK100":"^FTSE","FR40":"^FCHI"}

try:
    if not os.path.exists("/content/drive/MyDrive"):
        from google.colab import drive; drive.mount("/content/drive", force_remount=False)
except Exception as e:
    print("Drive不可:", e)


def _read_h1(path):
    df = pd.read_csv(path); df.columns=[c.strip().lower() for c in df.columns]
    t = next((c for c in ["time","timestamp","date","datetime","gmt time"] if c in df.columns), df.columns[0])
    raw=df[t]
    if np.issubdtype(raw.dtype, np.number):          # エポック(秒/ミリ秒)形式のCSV対応
        unit="ms" if float(raw.max())>1e11 else "s"
        df["t"]=pd.to_datetime(raw,unit=unit,utc=True,errors="coerce")
    else:
        df["t"]=pd.to_datetime(raw,utc=True,errors="coerce")
    df=df.dropna(subset=["t"]).sort_values("t").set_index("t")
    def col(*n):
        for x in n:
            for c in df.columns:
                if c==x: return c
        return None
    o,h,l,c = col("open","bidopen"),col("high","bidhigh"),col("low","bidlow"),col("close","bidclose")
    return df[[o,h,l,c]].astype(float).rename(columns={o:"open",h:"high",l:"low",c:"close"})


def _yahoo(sym, interval, start, end):
    import urllib.request, json as js
    p1=int(pd.Timestamp(start,tz="UTC").timestamp()); p2=int(pd.Timestamp(end,tz="UTC").timestamp())
    u=(f"https://query2.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}"
       f"?interval={interval}&period1={p1}&period2={p2}")
    import urllib.parse
    req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"})
    d=js.loads(urllib.request.urlopen(req,timeout=30).read())
    r=d["chart"]["result"][0]; q=r["indicators"]["quote"][0]
    idx=pd.to_datetime(r["timestamp"],unit="s",utc=True)
    return pd.DataFrame({k:q[k] for k in ("open","high","low","close")},index=idx).dropna()

import urllib.parse  # noqa

def _synth_h1(name, until=None):
    """日足→擬似H1(00:00=寄り/12:00=高安フル/21:00=引け)。保守近似(docs/168 §4)"""
    d=daily(name)
    if until is not None: d=d[d.index<pd.Timestamp(until)]
    rows=[]
    for t,b in d.iterrows():
        base=pd.Timestamp(t).tz_localize("UTC")
        rows.append((base, b["open"],b["open"],b["open"],b["open"]))
        rows.append((base+pd.Timedelta(hours=12), b["open"],b["high"],b["low"],b["close"]))
        rows.append((base+pd.Timedelta(hours=21), b["close"],b["close"],b["close"],b["close"]))
    return pd.DataFrame(rows,columns=["t","open","high","low","close"]).set_index("t")

H1CACHE={}
def h1(name):
    if name in H1CACHE: return H1CACHE[name]
    p=f"{H1_DIR}/{name}_h1.csv"
    if os.path.exists(p):
        df=_read_h1(p); src="dukascopy"
        if df.index.min()>pd.Timestamp("2016-01-10",tz="UTC"):   # 例: XAUUSDは2021年〜
            pre=_synth_h1(name, until=df.index.min().tz_localize(None))
            df=pd.concat([pre,df]).sort_index(); src="dukascopy+synth"
    else:
        try:
            start=max(pd.Timestamp.utcnow().tz_localize(None)-pd.Timedelta(days=725),
                      pd.Timestamp("2024-07-20"))
            recent=_yahoo(YH.get(name,name+"=X"),"60m",str(start.date()),"2025-05-01")
        except Exception:
            recent=None
        pre=_synth_h1(name, until=None)
        df=pre if recent is None else pd.concat([pre[pre.index<recent.index.min()],recent]).sort_index()
        src="synth(+yahoo60m)" if recent is not None else "synth"
    H1CACHE[name]=(df,src); return H1CACHE[name]

DCACHE={}
def daily(name):
    if name in DCACHE: return DCACHE[name]
    p=f"{H1_DIR}/{name}_h1.csv"; df=None
    if os.path.exists(p):
        x=_read_h1(p); g=x.resample("1D")
        df=pd.DataFrame({"open":g["open"].first(),"high":g["high"].max(),
                         "low":g["low"].min(),"close":g["close"].last()}).dropna()
        df.index=pd.DatetimeIndex(pd.DatetimeIndex(df.index).date)
    if df is not None and (len(df)==0 or df.index.max()<pd.Timestamp("2020-01-01")):
        print(f"[data] {name}: Drive由来の日足が不正(〜{df.index.max() if len(df) else 'empty'})→Yahoo単独へ")
        df=None
    if df is None or len(df[df.index<pd.Timestamp("2016-01-01")])<50 \
       or len(df[df.index<pd.Timestamp("2024-08-01")])<400:
        try:
            y=_yahoo(YH.get(name,name+"=X"),"1d","2013-01-01","2025-05-01")
            y.index=pd.DatetimeIndex(pd.DatetimeIndex(y.index).date)
            df=y if df is None else pd.concat([y[y.index<df.index.min()],df]).sort_index()
            print(f"[data] {name}: 日足をYahooで延長({df.index.min().date()}〜{df.index.max().date()})")
        except Exception as e:
            print(f"[data] {name}: Yahoo日足補完失敗 {e}")
    DCACHE[name]=df; return df


def _utc(when):
    ts=pd.Timestamp(when)
    return ts.tz_localize("UTC") if ts.tz is None else ts.tz_convert("UTC")

def atr_h1(name, when, n=24):
    df,_=h1(name); w=df[df.index<_utc(when)].tail(n+1)
    tr=np.maximum(w["high"]-w["low"],
        np.maximum((w["high"]-w["close"].shift()).abs(),(w["low"]-w["close"].shift()).abs()))
    return float(tr.tail(n).mean())

def atr_d1(name, day, n=14):
    df=daily(name); w=df[df.index<pd.Timestamp(day)].tail(n+1)
    tr=np.maximum(w["high"]-w["low"],
        np.maximum((w["high"]-w["close"].shift()).abs(),(w["low"]-w["close"].shift()).abs()))
    return float(tr.tail(n).mean())

def atr_mn(name, month_end, n=6):
    df=daily(name); mc=df.resample("ME").agg({"open":"first","high":"max","low":"min","close":"last"})
    w=mc[mc.index<=pd.Timestamp(month_end)].tail(n+1)
    tr=np.maximum(w["high"]-w["low"],
        np.maximum((w["high"]-w["close"].shift()).abs(),(w["low"]-w["close"].shift()).abs()))
    return float(tr.tail(n).mean())

def e5_sign(name, before_month_end):
    df=daily(name); mc=df["close"].resample("ME").last()
    mc=mc[mc.index<=pd.Timestamp(before_month_end)]
    if len(mc)<14:
        print(f"⚠ {name}: 月次履歴{len(mc)}本<14 → E5シグナル判定不能(0扱い)")
        return 0
    comp=0
    for lb in (1,3,6,12):
        r=mc.iloc[-1]/mc.iloc[-1-lb]-1
        comp += 1 if r>0 else (-1 if r<0 else 0)
    return 1 if comp>0 else (-1 if comp<0 else 0)


class Leg:
    """1建玉: entry価格・方向・SL価格・「1価格%あたりequity%」感応度"""
    def __init__(self, name, direction, entry, slp, sens, tag):
        self.name,self.dir,self.entry,self.sl,self.sens,self.tag=name,direction,entry,slp,sens,tag
        self.alive=True; self.realized=0.0
    def pnl(self, px):
        return self.sens*self.dir*(px-self.entry)/self.entry
    def check_sl(self, bar, slip):
        if not self.alive: return None
        hit = (bar["low"]<=self.sl) if self.dir>0 else (bar["high"]>=self.sl)
        if hit:
            fill=self.sl*(1-slip) if self.dir>0 else self.sl*(1+slip)
            self.realized=self.sens*self.dir*(fill-self.entry)/self.entry
            self.alive=False
            return self.realized
        return None


def replay(config, event, slip, seasonal=False):
    day=pd.Timestamp(event,tz="UTC"); d0=day; d1=day+pd.Timedelta(days=1)
    legs=[]; notes=[]
    month_start=day.replace(day=1)
    prev_month_end=(month_start-pd.Timedelta(days=1)).date()
    is_monday = day.dayofweek==0
    if not seasonal:
        # E5(月初建て・XAU+NAS)
        for a in config["e5_assets"]:
            sig=e5_sign(a, prev_month_end)
            if sig==0: continue
            df=daily(a); ent=float(df[df.index>=month_start.tz_localize(None)]["open"].iloc[0])
            amn=atr_mn(a, prev_month_end)
            sens=config["e5_leg"]*ent/amn          # 1×ATR逆行=legRisk
            slp=ent-sig*config["cat_atr"]*amn
            legs.append(Leg(a,sig,ent,slp,sens,f"E5:{a}"))
        # v4(イベント前10営業日の信号を日足で近似再現)
        for pair in config["v4_pairs"]:
            df=daily(pair); hist=df[df.index<day.tz_localize(None)].tail(60)
            c=hist["close"]
            for i in range(len(hist)-9,len(hist)):
                if i<20: continue
                seg=c.iloc[:i+1]
                rsi_d = seg.diff(); up=rsi_d.clip(lower=0).ewm(alpha=1/14).mean(); dn=(-rsi_d).clip(lower=0).ewm(alpha=1/14).mean()
                rsi=float((100-100/(1+up/dn)).iloc[-1])
                z=float((seg.iloc[-1]-seg.rolling(20).mean().iloc[-1])/seg.rolling(20).std().iloc[-1])
                down=0
                for k in range(1,6):
                    if seg.iloc[-k]<seg.iloc[-k-1]: down+=1
                    else: break
                upn=0
                for k in range(1,6):
                    if seg.iloc[-k]>seg.iloc[-k-1]: upn+=1
                    else: break
                ret=float(seg.iloc[-1]/seg.iloc[-2]-1)
                buy=(rsi<35)+(z<-1.5)+(down>=3)+(ret<-0.005)
                sell=(rsi>65)+(z>1.5)+(upn>=3)+(ret>0.005)
                sig=1 if (buy>=4 and buy>sell) else (-1 if (sell>=4 and sell>buy) else 0)
                if sig==0: continue
                ent=float(hist["close"].iloc[i]); ad=atr_d1(pair,hist.index[i]); sd=config["v4_slatr"]*ad
                slp=ent-sig*sd; tp=ent+sig*1.2*sd
                # イベント前にSL/TP到達済みなら除外(日足高安で判定)
                path=df[(df.index>hist.index[i])&(df.index<day.tz_localize(None))]
                closed=False
                for _,b in path.iterrows():
                    if (sig>0 and (b["low"]<=slp or b["high"]>=tp)) or (sig<0 and (b["high"]>=slp or b["low"]<=tp)):
                        closed=True; break
                if closed or len(path)>=8: continue
                sens=config["v4_risk"]*ent/sd
                legs.append(Leg(pair,sig,ent,slp,sens,f"v4:{pair}"))
                break   # 1ペア1建玉
        if is_monday:
            for pair in config["v7_pairs"]:
                for hr in config["v7_hours"]:
                    t=day+pd.Timedelta(hours=hr); df,_=h1(pair)
                    bar=df[df.index>=t]
                    if len(bar)==0: continue
                    ent=float(bar["open"].iloc[0]); a=atr_h1(pair,t); sd=config["cat_atr"]*a
                    legs.append(Leg(pair,1,ent,ent-sd,config["v7_shot"]*ent/sd,f"v7:{pair}@{hr}"))
            for symn in config["emon_syms"]:
                for hr in config["emon_hours"]:
                    t=day+pd.Timedelta(hours=hr); df,_=h1(symn)
                    bar=df[df.index>=t]
                    if len(bar)==0: continue
                    ent=float(bar["open"].iloc[0]); a=atr_h1(symn,t); sd=config["cat_atr"]*a
                    legs.append(Leg(symn,1,ent,ent-sd,config["emon_shot"]*ent/sd,f"EMon:{symn}@{hr}"))
    else:
        W=SEAS_W[event]
        if "SJul" in W:
            for a in ["US500","NAS100"]:
                df=daily(a); ent=float(df[df.index>=month_start.tz_localize(None)]["open"].iloc[0])
                legs.append(Leg(a,1,ent,-1e18,SEAS_MULT*W["SJul"]/2,f"SJul:{a}"))  # SLなし
        if "E5" in W:
            invv={}; sgn={}
            for a in SEAS_E5:
                s=e5_sign(a,prev_month_end)
                if s==0: continue
                amn=atr_mn(a,prev_month_end); df=daily(a)
                ent=float(df[df.index>=month_start.tz_localize(None)]["open"].iloc[0])
                sgn[a]=(s,ent); invv[a]=1.0/(amn/ent)
            tot=sum(invv.values())
            for a,(s,ent) in sgn.items():
                legs.append(Leg(a,s,ent,-1e18 if s>0 else 1e18,SEAS_MULT*W["E5"]*invv[a]/tot,f"E5:{a}"))
        if "EMonX" in W and is_monday:
            for a in ["JP225","UK100","FR40"]:
                df,_=h1(a); t=day+pd.Timedelta(hours=9)
                bar=df[df.index>=t]
                if len(bar)==0: continue
                ent=float(bar["open"].iloc[0])
                legs.append(Leg(a,1,ent,-1e18,SEAS_MULT*W["EMonX"]/3,f"EMonX:{a}"))
        if "EMon" in W and is_monday:
            for a in ["US500","NAS100","GER40"]:
                df,_=h1(a); t=day+pd.Timedelta(hours=9)
                bar=df[df.index>=t]
                if len(bar)==0: continue
                ent=float(bar["open"].iloc[0])
                legs.append(Leg(a,1,ent,-1e18,SEAS_MULT*W["EMon"]/3,f"EMon:{a}"))
        if "v4" in W:
            notes.append("季節v4はSL付き・寄与は小=PD側のv4近似を参照(ここでは省略・保守側)")

    # H1経路でequityを追う
    hours=pd.date_range(d0,d1,freq="1h",tz="UTC")[:-1]
    eq_path=[]; guard_done=False; guard_at=None
    for t in hours:
        eq=0.0; any_alive=False
        for leg in legs:
            df,_=h1(leg.name)
            bar=df[(df.index>=t)&(df.index<t+pd.Timedelta(hours=1))]
            if len(bar)==0:
                px=None
                prev=df[df.index<t]
                if len(prev): px=float(prev["close"].iloc[-1])
                eq += leg.realized if not leg.alive else (leg.pnl(px) if px else 0.0)
                continue
            b=bar.iloc[0]
            if leg.alive:
                leg.check_sl(b, slip)
            if leg.alive:
                # バー内最悪(low基準/ショートはhigh)で評価=保守側
                worst=float(b["low"] if leg.dir>0 else b["high"])
                eq += leg.pnl(worst)
                any_alive=True
            else:
                eq += leg.realized
        eq_path.append((str(t), eq))
        if not guard_done and eq<=GUARD_DAY:
            guard_done=True; guard_at=str(t)
            # 全決済: 次バー寄り+スリッページ
            for leg in legs:
                if leg.alive:
                    df,_=h1(leg.name)
                    nxt=df[df.index>t]
                    if len(nxt):
                        fill=float(nxt["open"].iloc[0])
                        fill*=(1-slip) if leg.dir>0 else (1+slip)
                        leg.realized=leg.sens*leg.dir*(fill-leg.entry)/leg.entry
                    else:
                        leg.realized=leg.pnl(float(df["close"].iloc[-1]))
                    leg.alive=False
    mins=min(v for _,v in eq_path)
    end=0.0
    for l in legs:
        if l.alive:
            df,_=h1(l.name); w=df[df.index<d1]
            end+=l.pnl(float(w["close"].iloc[-1])) if len(w) else 0.0
        else:
            end+=l.realized
    breakdown={l.tag: round((l.realized if not l.alive else l.pnl(
        float(h1(l.name)[0][h1(l.name)[0].index<d1]["close"].iloc[-1])))*100,3) for l in legs}
    return dict(min_intraday_pct=round(mins*100,2), end_day_pct=round(end*100,2),
                guard_at=guard_at, fn_daily_breach=bool(mins<=FN_DAY), n_legs=len(legs),
                pnl_breakdown_pct=breakdown, notes=notes)


def main():
    print("[診断] データ源と期間:")
    for nm in ["EURJPY","GBPJPY","US500","NAS100","GER40","XAUUSD"]:
        try:
            df,src=h1(nm)
            print(f"  H1 {nm}: {src} {df.index.min()}〜{df.index.max()} ({len(df)}本)")
        except Exception as e:
            print(f"  H1 {nm}: 取得失敗 {e}")
    out={}
    for ev in EVENTS:
        out[ev]={}
        for slip in SLIPS:
            r=replay(PD, ev, slip, seasonal=False)
            out[ev][f"PD3x_slip{slip}"]=r
            print(f"[{ev}] PD3x slip={slip}: 日中最小 {r['min_intraday_pct']}% "
                  f"(FN日次違反={r['fn_daily_breach']} ガード={r['guard_at']}) legs={r['n_legs']}")
        rs=replay(PD, ev, 0.0, seasonal=True)
        out[ev]["Seasonal15"]=rs
        print(f"[{ev}] 季節1.5x: 日中最小 {rs['min_intraday_pct']}% (FN日次違反={rs['fn_daily_breach']})")
    with open(OUT_JSON,"w") as f:
        json.dump(out,f,ensure_ascii=False,indent=1,default=str)
    print("保存:",OUT_JSON)
    print("\n### 判定(この行以下をそのまま貼り付け) ###")
    print(json.dumps(out,ensure_ascii=False,indent=1,default=str))


if __name__=="__main__":
    main()
