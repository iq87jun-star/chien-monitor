//+------------------------------------------------------------------+
//|                              Chien_Portfolio_AllInOne.mq5          |
//|   オールインワン: 1チャートに乗せるだけで v7(円月曜)＋E5(多資産トレ |
//|   ンド)を全7銘柄まとめて運用。シナリオ選択で倍率/比率/ルール自動。  |
//|                                                                   |
//|   ■ シナリオ(InpScenario)                                          |
//|     PORT_INSTANT       : インスタント運用. v7 週次1.5% / E5 75:25  |
//|        (legRisk0.46) / −10%トレーリング / 無目標 / 日次なし。       |
//|     PORT_PROP_BREAKTHROUGH: プロップ突破. v7 週次2.5% / E5 65:35   |
//|        (legRisk1.23) / 静的−10% / +8%で新規停止 / 日次−4%。        |
//|     PORT_MANUAL        : 下の手動値(週次/legRisk)・静的−10%。       |
//|                                                                   |
//|   ■ 内部で2戦略を実行:                                              |
//|     v7: 円3クロス(InpYenSymbols)を月曜 04/06/08/10UTC にLONG、24h   |
//|         時間決済。リスク=週次予算/12ショット。SL=ATR(H1)×2.5。     |
//|     E5: 金+指数(InpE5Symbols)を月初(MN1)に時系列モメンタムで両建て、 |
//|         逆ボラ加重(legRisk)で建て1ヶ月保有。SL=ATR(MN1)×2.5。      |
//|     口座ガード: 総合−10%枠の内側(既定−8%)で全停止。               |
//|                                                                   |
//|   ★1チャートに1つだけ乗せる(どの銘柄/時間足でも可。内部で全銘柄を   |
//|     SymbolSelectして扱う)。残高は自動取得。銘柄名は業者仕様に合わせ |
//|     InpYenSymbols / InpE5Symbols を編集(US500=SPX500 等)。         |
//|   ⚠ E5はSTRONG-LEAD(未検証)。本資金前にデモ(docs/29)。docs/36参照。 |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.00"
#property strict
#property description "All-in-one: v7(JPY Monday) + E5(multi-asset trend) on one chart. Scenario presets. Auto-balance. E5=LEAD/demo."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

enum ENUM_PORT_SCENARIO
{
   PORT_INSTANT            = 0, // インスタント運用(v7 1.5% / E5 75:25 / トレーリング)
   PORT_PROP_BREAKTHROUGH  = 1, // プロップ突破(v7 2.5% / E5 65:35 / 静的+8%目標)
   PORT_MANUAL             = 2  // 手動(下のWeeklyRisk/E5LegRisk・静的)
};

input group "=== シナリオ（これ1つで倍率/比率/ルール自動）==="
input ENUM_PORT_SCENARIO InpScenario = PORT_INSTANT; // ★運用先
input bool   InpAcknowledgeLEAD = true;   // E5はLEAD(未検証)。デモ/極小のみ=trueで承認

input group "=== 銘柄（業者の実銘柄名に合わせる）==="
input string InpYenSymbols = "EURJPY,GBPJPY,USDJPY";        // v7: 円3クロス
input string InpE5Symbols  = "XAUUSD,US500,NAS100,GER40";   // E5: 金+株価指数

input group "=== 口座/ガード ==="
input double InpInitialBalance   = 0.0;   // 0=口座残高を自動取得 / 手動なら口座額
input double InpMaxLossLimitPct  = 10.0;  // 失格ライン%
input double InpAccountFloorDDPct= 8.0;   // 総合 -8% で全停止(−10%の内側)

input group "=== 手動値（PORT_MANUAL時のみ）==="
input double InpWeeklyRiskPct = 1.5;      // v7 週次リスク%
input double InpE5LegRiskPct  = 0.46;     // E5 legRisk%(各レッグ月次σ)

input group "=== v7 設定 ==="
input string InpEntryHoursUTC = "4,6,8,10";
input int    InpShotsPerWeek  = 12;
input int    InpHoldHours     = 24;
input int    InpAtrPeriodH1   = 24;
input double InpCatastropheATR= 2.5;
input double InpMinStopPips   = 10.0;
input double InpMaxStopPips   = 400.0;
input double InpMaxSpreadPips = 3.0;

input group "=== E5 設定 ==="
input int    InpLB1=1, InpLB2=3, InpLB3=6, InpLB4=12;
input bool   InpAllowShort = true;
input int    InpAtrPeriodMN1= 6;
input double InpCatATR_E5  = 2.5;

input group "=== 共通 ==="
input double InpMinLot = 0.01;
input double InpMaxLot = 50.0;
input long   InpMagic  = 940700;
input int    InpSlippagePoints = 30;
input bool   InpVerboseLog = true;

//==================================================================
CTrade        trade;
CPositionInfo posinfo;

string   g_yen[]; string g_e5[]; int g_hours[];
int      g_atrH1[]; int g_atrMN1[];
datetime g_lastShot[];     // [yenIdx*nHours + hourIdx]
datetime g_lastMonth[];    // [e5Idx]
double   g_initBal=0.0, g_weeklyRisk=1.5, g_e5leg=0.46, g_maxLossPct=10.0;
bool     g_useTrailing=true, g_useProfitStop=false, g_useDailyStop=false;
double   g_profitPct=0.0, g_dailyStopPct=0.0, g_floorBufPct=2.0;
double   g_peakEquity=0.0, g_trailFloor=0.0, g_dayStartEq=0.0;
datetime g_curDay=0; bool g_halted=false, g_dayBlocked=false;
string   g_scenName="";

//==================================================================
int SplitCSV(string csv, string &arr[])
{
   string p[]; int k=StringSplit(csv, ',', p); int m=0; ArrayResize(arr,k);
   for(int i=0;i<k;i++){ string s=p[i]; StringTrimLeft(s); StringTrimRight(s);
      if(StringLen(s)>0){ arr[m]=s; m++; } }
   ArrayResize(arr,m); return m;
}
int SplitHours(string csv, int &arr[])
{
   string p[]; int k=StringSplit(csv, ',', p); int m=0; ArrayResize(arr,k);
   for(int i=0;i<k;i++){ string s=p[i]; StringTrimLeft(s); StringTrimRight(s);
      if(StringLen(s)==0) continue; int h=(int)StringToInteger(s);
      if(h>=0&&h<=23){ arr[m]=h; m++; } }
   ArrayResize(arr,m); return m;
}
double PipOf(string s){ return (StringFind(s,"JPY")>=0)? 0.01 : 0.0001; }

// 業者で銘柄名が違う問題に対応: 指定名＋主要別名＋サフィックスを総当りで実在銘柄を解決。
string ResolveSymbol(string want)
{
   string suf[]={"",".pi",".raw",".ecn",".stp",".pro",".cash",".r",".c",".m","m",".spot","-cash",".sd","+",".i","_SB","_raw",".a",".z"};
   string bases[]; ArrayResize(bases,20); int nb=0;
   bases[nb++]=want;
   string U=want; StringToUpper(U);
   if(StringFind(U,"XAU")>=0 || StringFind(U,"GOLD")>=0){
      bases[nb++]="XAUUSD"; bases[nb++]="GOLD"; bases[nb++]="GOLDUSD"; }
   else if(StringFind(U,"SPX")>=0 || StringFind(U,"500")>=0){
      bases[nb++]="US500"; bases[nb++]="SPX500"; bases[nb++]="SP500"; bases[nb++]="USA500"; bases[nb++]="US500Cash"; }
   else if(StringFind(U,"NAS")>=0 || StringFind(U,"USTEC")>=0 || StringFind(U,"NDX")>=0 || StringFind(U,"US100")>=0 || StringFind(U,"TECH")>=0){
      bases[nb++]="NAS100"; bases[nb++]="USTEC"; bases[nb++]="US100"; bases[nb++]="NDX100"; bases[nb++]="USTECH"; }
   else if(StringFind(U,"GER")>=0 || StringFind(U,"DAX")>=0 || StringFind(U,"DE40")>=0 || StringFind(U,"DE30")>=0 || StringFind(U,"40")>=0){
      bases[nb++]="GER40"; bases[nb++]="DE40"; bases[nb++]="DAX40"; bases[nb++]="GER30"; bases[nb++]="DE30"; }
   ArrayResize(bases,nb);
   for(int b=0;b<nb;b++)
      for(int s=0;s<ArraySize(suf);s++){
         string cand=bases[b]+suf[s];
         if(SymbolSelect(cand,true)) return cand;
      }
   return "";
}

void ResolveScenario()
{
   g_weeklyRisk=InpWeeklyRiskPct; g_e5leg=InpE5LegRiskPct;
   g_useTrailing=false; g_useProfitStop=false; g_useDailyStop=false;
   g_profitPct=0; g_dailyStopPct=0; g_maxLossPct=InpMaxLossLimitPct; g_floorBufPct=2.0;
   g_scenName="MANUAL";
   if(InpScenario==PORT_INSTANT){
      g_scenName="INSTANT"; g_weeklyRisk=1.5; g_e5leg=0.46;
      g_useTrailing=true; g_useProfitStop=false; g_useDailyStop=false;
   } else if(InpScenario==PORT_PROP_BREAKTHROUGH){
      g_scenName="PROP_BREAKTHROUGH"; g_weeklyRisk=2.5; g_e5leg=1.23;
      g_useTrailing=false; g_useProfitStop=true; g_profitPct=8.0;
      g_useDailyStop=true; g_dailyStopPct=4.0;
   }
}

int OnInit()
{
   if(!InpAcknowledgeLEAD){ Print("[STOP] E5はLEAD。InpAcknowledgeLEAD=trueで承認(デモ/極小)。"); return INIT_FAILED; }
   int ny=SplitCSV(InpYenSymbols,g_yen);
   int ne=SplitCSV(InpE5Symbols,g_e5);
   int nh=SplitHours(InpEntryHoursUTC,g_hours);
   if(ny==0||ne==0||nh==0){ Print("シンボル/時刻のパース失敗"); return INIT_FAILED; }
   ResolveScenario();
   g_initBal=(InpInitialBalance>0.0)?InpInitialBalance:AccountInfoDouble(ACCOUNT_BALANCE);
   if(g_initBal<=0.0) g_initBal=AccountInfoDouble(ACCOUNT_EQUITY);

   ArrayResize(g_atrH1,ny); ArrayResize(g_atrMN1,ne);
   ArrayResize(g_lastShot,ny*nh); ArrayInitialize(g_lastShot,0);
   ArrayResize(g_lastMonth,ne); ArrayInitialize(g_lastMonth,0);
   for(int i=0;i<ny;i++){
      string r=ResolveSymbol(g_yen[i]); g_atrH1[i]=INVALID_HANDLE;
      if(r==""){ PrintFormat("⚠ v7銘柄 %s が見つからず(別名総当り不可)→スキップ",g_yen[i]); continue; }
      if(r!=g_yen[i]) PrintFormat("[銘柄解決] v7 %s → %s",g_yen[i],r);
      g_yen[i]=r;
      g_atrH1[i]=iATR(g_yen[i],PERIOD_H1,InpAtrPeriodH1);
      if(g_atrH1[i]==INVALID_HANDLE) PrintFormat("⚠ ATR(H1) handle失敗 %s",g_yen[i]);
   }
   for(int i=0;i<ne;i++){
      string r=ResolveSymbol(g_e5[i]); g_atrMN1[i]=INVALID_HANDLE;
      if(r==""){ PrintFormat("⚠ E5銘柄 %s が見つからず(別名総当り不可)→スキップ",g_e5[i]); continue; }
      if(r!=g_e5[i]) PrintFormat("[銘柄解決] E5 %s → %s",g_e5[i],r);
      g_e5[i]=r;
      g_atrMN1[i]=iATR(g_e5[i],PERIOD_MN1,InpAtrPeriodMN1);
      if(g_atrMN1[i]==INVALID_HANDLE) PrintFormat("⚠ ATR(MN1) handle失敗 %s",g_e5[i]);
   }
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   g_peakEquity=g_initBal; g_trailFloor=g_initBal*(1.0-g_maxLossPct/100.0);
   ResetDay(TimeCurrent());
   PrintFormat("[INIT ALLINONE] scen=%s initBal=%.0f v7週次=%.2f%%/shots%d E5leg=%.2f%% trailing=%s profitStop=%s(%.0f) dailyStop=%s",
      g_scenName,g_initBal,g_weeklyRisk,InpShotsPerWeek,g_e5leg,(g_useTrailing?"Y":"N"),
      (g_useProfitStop?"Y":"N"),g_profitPct,(g_useDailyStop?"Y":"N"));
   if(InpVerboseLog) Print("[NOTE] 1チャートに本EAを1つだけ。v7=円3クロス, E5=金+指数を内部で全銘柄運用。E5はLEAD=デモ前提。");
   EventSetTimer(30);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){
   EventKillTimer();
   for(int i=0;i<ArraySize(g_atrH1);i++) if(g_atrH1[i]!=INVALID_HANDLE) IndicatorRelease(g_atrH1[i]);
   for(int i=0;i<ArraySize(g_atrMN1);i++) if(g_atrMN1[i]!=INVALID_HANDLE) IndicatorRelease(g_atrMN1[i]);
}

datetime DayStart(datetime t){ MqlDateTime s; TimeToStruct(t,s); s.hour=0;s.min=0;s.sec=0; return StructToTime(s); }
void ResetDay(datetime t){ g_curDay=DayStart(t); g_dayStartEq=AccountInfoDouble(ACCOUNT_EQUITY); g_dayBlocked=false; }

bool IsYen(string s){ for(int i=0;i<ArraySize(g_yen);i++) if(g_yen[i]==s) return true; return false; }

double AtrAt(int handle){ double a[1]; if(CopyBuffer(handle,0,1,1,a)<1) return 0.0; return a[0]; }

// 汎用ロット: priceMove 動いた時に riskMoney を失う/得るサイズ
double LotsFor(string sym, double priceMove, double riskMoney)
{
   if(priceMove<=0||riskMoney<=0) return 0.0;
   double tv=SymbolInfoDouble(sym,SYMBOL_TRADE_TICK_VALUE);
   double ts=SymbolInfoDouble(sym,SYMBOL_TRADE_TICK_SIZE);
   if(tv<=0||ts<=0) return 0.0;
   double lossPerLot=(priceMove/ts)*tv; if(lossPerLot<=0) return 0.0;
   double lots=riskMoney/lossPerLot;
   double step=SymbolInfoDouble(sym,SYMBOL_VOLUME_STEP);
   double vmin=SymbolInfoDouble(sym,SYMBOL_VOLUME_MIN);
   double vmax=SymbolInfoDouble(sym,SYMBOL_VOLUME_MAX);
   if(step>0) lots=MathFloor(lots/step)*step;
   lots=MathMin(lots,MathMin(InpMaxLot,vmax));
   if(lots<MathMax(InpMinLot,vmin)) return 0.0;
   return lots;
}

double BreachFloor(double equity)
{
   if(!g_useTrailing) return g_initBal*(1.0-g_maxLossPct/100.0);
   if(equity>g_peakEquity) g_peakEquity=equity;
   double raw=g_peakEquity-g_initBal*g_maxLossPct/100.0;
   double capped=MathMin(raw,g_initBal);
   if(capped>g_trailFloor) g_trailFloor=capped;
   return g_trailFloor;
}

int DirOf(string sym){
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Symbol()==sym && posinfo.Magic()==InpMagic)
         return (posinfo.PositionType()==POSITION_TYPE_BUY?1:-1); }
   return 0;
}
void CloseSym(string sym, string why){
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Symbol()==sym && posinfo.Magic()==InpMagic){
         if(trade.PositionClose(tk) && InpVerboseLog) PrintFormat("[CLOSE %s] %s",why,sym); } }
}
void CloseAllMine(string why){
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()==InpMagic) trade.PositionClose(tk); }
   if(InpVerboseLog) PrintFormat("[CLOSE ALL %s]",why);
}

//==================================================================
void OnTimer()
{
   datetime now=TimeCurrent(); datetime utc=TimeGMT();
   if(DayStart(now)!=g_curDay) ResetDay(now);
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);

   // ===== 口座ガード =====
   double floor=BreachFloor(equity);
   double guard=floor+g_initBal*g_floorBufPct/100.0;
   if(equity<=guard && !g_halted){ g_halted=true; CloseAllMine("EQUITY_FLOOR");
      PrintFormat("[HALT] equity %.2f <= guard %.2f",equity,guard); }
   if(g_halted){ CloseAllMine("HALTED"); return; }

   // 日次ストップ(プロップ)
   if(g_useDailyStop){
      double dpnl=equity-g_dayStartEq;
      if(dpnl<=-g_initBal*g_dailyStopPct/100.0 && !g_dayBlocked){ g_dayBlocked=true;
         PrintFormat("[DAILY STOP] %.2f",dpnl); }
   }

   ManageV7Exit();         // 時間決済は常時
   ManageE5();             // 月初リバランス(新規はガードで抑制)

   // 利益目標(プロップ)で新規停止
   if(g_useProfitStop && equity>=g_initBal*(1.0+g_profitPct/100.0)) return;
   if(g_dayBlocked) return;

   EntriesV7(utc);         // 月曜エントリー
}

//===== v7 =====
void ManageV7Exit()
{
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()!=InpMagic) continue;
      if(!IsYen(posinfo.Symbol())) continue;
      int held=(int)(TimeCurrent()-(datetime)posinfo.Time());
      if(held>=InpHoldHours*3600){ if(trade.PositionClose(tk)&&InpVerboseLog)
         PrintFormat("[v7 TIME EXIT] %s",posinfo.Symbol()); }
   }
}
void EntriesV7(datetime utc)
{
   MqlDateTime u; TimeToStruct(utc,u);
   if(u.day_of_week!=1) return;                 // 月曜のみ
   int slot=-1; for(int h=0;h<ArraySize(g_hours);h++) if(u.hour==g_hours[h]){ slot=h; break; }
   if(slot<0) return;
   datetime hourBar=utc-(utc%3600);
   int nh=ArraySize(g_hours);
   double perShot=g_weeklyRisk/(InpShotsPerWeek>0?InpShotsPerWeek:1);
   for(int s=0;s<ArraySize(g_yen);s++){
      int key=s*nh+slot;
      if(g_lastShot[key]==hourBar) continue;     // この銘柄×時刻は発注済み
      string sym=g_yen[s]; double pip=PipOf(sym);
      double atr=AtrAt(g_atrH1[s]); if(atr<=0) continue;
      double sd=InpCatastropheATR*atr; double sp=sd/pip;
      if(sp<InpMinStopPips){ sp=InpMinStopPips; sd=sp*pip; }
      if(sp>InpMaxStopPips) continue;
      double ask=SymbolInfoDouble(sym,SYMBOL_ASK), bid=SymbolInfoDouble(sym,SYMBOL_BID);
      if(ask<=0||bid<=0) continue;
      if((ask-bid)/pip>InpMaxSpreadPips){ if(InpVerboseLog) PrintFormat("[v7 SKIP spread] %s",sym); g_lastShot[key]=hourBar; continue; }
      double riskMoney=g_initBal*(perShot/100.0);
      double lots=LotsFor(sym,sd,riskMoney); if(lots<InpMinLot){ g_lastShot[key]=hourBar; continue; }
      int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      double sl=NormalizeDouble(ask-sd,dg);
      g_lastShot[key]=hourBar;
      if(trade.Buy(lots,sym,0.0,sl,0.0,StringFormat("v7_%s_h%d",sym,g_hours[slot])))
         { if(InpVerboseLog) PrintFormat("[v7 ENTRY] LONG %s h%dUTC lots=%.2f SL=%.5f",sym,g_hours[slot],lots,sl); }
   }
}

//===== E5 =====
int E5Signal(string sym)
{
   int need=InpLB4+2; double c[];
   if(CopyClose(sym,PERIOD_MN1,0,need+1,c)<need+1) return 0;
   int n=ArraySize(c); int i1=n-2; if(i1<=InpLB4) return 0;
   int lbs[4]; lbs[0]=InpLB1; lbs[1]=InpLB2; lbs[2]=InpLB3; lbs[3]=InpLB4;
   double comp=0;
   for(int k=0;k<4;k++){ int j=i1-lbs[k]; if(j<0) continue; double r=c[i1]/c[j]-1.0;
      comp+=(r>0?1.0:(r<0?-1.0:0.0)); }
   int s=(comp>0?1:(comp<0?-1:0));
   if(s<0 && !InpAllowShort) return 0;
   return s;
}
void ManageE5()
{
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   bool blockNew = (g_useProfitStop && equity>=g_initBal*(1.0+g_profitPct/100.0)) || g_dayBlocked;
   for(int i=0;i<ArraySize(g_e5);i++){
      string sym=g_e5[i];
      datetime mb=(datetime)iTime(sym,PERIOD_MN1,0);
      if(mb==0) continue;
      if(mb==g_lastMonth[i]) continue;          // 当月は評価済み
      g_lastMonth[i]=mb;
      int sig=E5Signal(sym); int cur=DirOf(sym);
      if(sig==0){ if(cur!=0) CloseSym(sym,"E5_FLAT"); continue; }
      if(cur==sig) continue;                     // 継続
      if(cur!=0) CloseSym(sym,"E5_FLIP");
      if(blockNew) continue;                      // 目標到達/日次停止中は新規building停止
      double atr=AtrAt(g_atrMN1[i]); if(atr<=0) continue;
      double riskMoney=equity*(g_e5leg/100.0);
      double lots=LotsFor(sym,atr,riskMoney); if(lots<InpMinLot) continue;
      double sd=InpCatATR_E5*atr; int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      if(sig>0){ double e=SymbolInfoDouble(sym,SYMBOL_ASK); double sl=NormalizeDouble(e-sd,dg);
         if(trade.Buy(lots,sym,0.0,sl,0.0,"E5_"+sym) && InpVerboseLog) PrintFormat("[E5 ENTRY] LONG %s lots=%.2f",sym,lots); }
      else     { double e=SymbolInfoDouble(sym,SYMBOL_BID); double sl=NormalizeDouble(e+sd,dg);
         if(trade.Sell(lots,sym,0.0,sl,0.0,"E5_"+sym) && InpVerboseLog) PrintFormat("[E5 ENTRY] SHORT %s lots=%.2f",sym,lots); }
   }
}
//+------------------------------------------------------------------+
//| 残存リスク(誠実な記録):                                          |
//|  ・E5はSTRONG-LEAD(未検証, docs/31)。本資金前にデモ(docs/29)必須。 |
//|  ・銘柄名は業者依存(US500/SPX500, NAS100/USTEC, GER40/DE40,       |
//|    XAUUSD/GOLD)。InpE5Symbols/InpYenSymbolsを実銘柄に合わせる。    |
//|  ・指数/金CFDの実スプレッド/スワップ/配当はバックテスト未計上=デモ |
//|    で確認。ガードは総合equity基準(トレーリング/静的をシナリオ選択)。|
//|  ・1チャートに本EAは1つだけ(複数乗せると二重発注)。Magic単一で全   |
//|    レッグ管理。手動EA(v8/E5単体)と同口座併用しない(Magic衝突回避)。|
//|  ・ニュースフィルタは本オールイン版では省略(単体EA版にはあり)。    |
//+------------------------------------------------------------------+
