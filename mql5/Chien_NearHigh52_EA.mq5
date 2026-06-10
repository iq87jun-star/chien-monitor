//+------------------------------------------------------------------+
//|                          Chien_NearHigh52_EA.mq5                  |
//|   52週高値近接(NH52)エッジ 銘柄EA:                                 |
//|   株価指数(US500/NAS100/GER40)のうち「前月末終値が52週高値の        |
//|   95%以上」の銘柄だけを、翌月の間 等加重LONG保有する月次リバランス   |
//|   スリーブ。George-Hwang(52-week high)系の未踏軸(docs/72)。         |
//|                                                                   |
//|   ■ なぜこのエッジか(docs/72): 自走探索バッチ第2弾(N=6事前登録・    |
//|     Bonferroni α=0.0083)で唯一の全ゲート通過=ADOPT:                |
//|       純益+137.9% / maxDD−12.8% / 頑健p=0.0017(★Bonferroni生存=    |
//|       本リポジトリ自走バッチ初) / JKmax0.013 / IS+59.1/OOS+49.6 /   |
//|       E-Mon相関0.16・v7相関−0.05 / コスト20bpsでも+110%。           |
//|     ★価値の正体=リスクタイミング: 純益はランダム同数ロングと同等     |
//|     だが、maxDDはランダム分布のp98.8で浅い(高値圏だけ乗ることで      |
//|     2020/3・2022弱気を構造的に回避)。プロップ(−10%枠)向きの性質。    |
//|                                                                   |
//|   ■ 正直な限界(数字を盛らない/docs/72):                            |
//|     Yahoo日足一次近似(配当除く指数・終値モデル)。系譜はトレンド系    |
//|     (MA2/E5と同族)だが別シグナルでJK/Bonferroniを初めて通過。        |
//|     1ヶ月保有=スワップ累積は業者差大→デモで実測必須。               |
//|     既存ポート(docs/61/68)への組込みは等ボラ比較(docs/67手順)を      |
//|     経てから。本EA単体での本資金投入は不可(デモ前進検証が先)。       |
//|                                                                   |
//|   ■ トレード定義(バックテストと同形):                              |
//|     月初第1営業日: 各銘柄の前月末終値 ≥ 直近252営業日最高終値×0.95   |
//|     → LONG(未保有なら建てる)。条件を満たさない銘柄は決済。           |
//|     各銘柄1ポジ・SL=2.5ATR(災害保険)。                              |
//|   ■ ガードは全EA共通(docs/01規約準拠): equityフロア(既定−8%/最終     |
//|     backstop−10%)・日次−4%(規約−5%手前)・タイマー equity 監視。      |
//|                                                                   |
//|   ★1チャートに本EAを1つだけドロップ(どの銘柄/足でも可)。残高は自動。 |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.00"
#property strict
#property description "52-week-high proximity index basket (NH52, docs/72). Monthly rebalance LONG only near 52w high. ADOPT on 10y harness; demo forward validation required. FundedNext guards built-in."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

input group "=== NH52 設定（52週高値近接）==="
input string InpSymbols        = "US500,NAS100,GER40"; // 指数バスケット(条件を満たす銘柄のみ等加重LONG)
input double InpNearHighRatio  = 0.95;         // 52週高値×この比率 以上で「近接」判定(検証値0.95)
input int    InpHighLookbackD  = 252;          // 高値参照期間(営業日)=52週
input int    InpEntryDom       = 1;            // 月内 何営業日目に判定/リバランスするか(1=月初第1営業日)

input group "=== サイズ（ADOPTだがデモ前進検証が先）==="
input bool   InpAcknowledgeDemo = true;        // 本資金前にデモ実測を承認=true(falseで起動拒否)
input double InpMonthRiskPct   = 1.50;         // 1ヶ月あたりの総リスク%(保有銘柄に等分)
input double InpCatastropheATR = 2.5;          // 災害SL=2.5×ATR(D1)
input double InpMinStopPts     = 50.0;         // 指数の最小SL(ポイント)
input double InpMaxSpreadPts   = 1500.0;       // 指数スプレッド上限(ポイント)
input int    InpAtrPeriodD1    = 14;           // 日次ATR期間

input group "=== 口座/ガード（docs/01規約準拠）==="
input double InpInitialBalance = 0.0;          // 0=口座残高を自動取得
input double InpMaxLossLimitPct= 10.0;         // 失格ライン%(最終backstop)
input double InpAccountFloorDDPct = 8.0;       // 全停止ライン%(規約−10%の手前。守り=8.0)
input double InpDailyStopPct   = 4.0;          // 日次全決済%(規約−5%の手前)。0で無効

input group "=== 共通 ==="
input double InpMinLot = 0.01;
input double InpMaxLot = 50.0;
input long   InpMagicBase = 950740;            // NH52=+1(他EAと衝突しないMagic帯)
input int    InpSlippagePoints = 30;
input bool   InpVerboseLog = true;

//==================================================================
CTrade        trade;
CPositionInfo posinfo;

string   g_syms[]; int g_atrD1[];
double   g_initBal=0.0;
long     g_mNH=0;
double   g_peakEquity=0.0, g_dayStartEq=0.0;
datetime g_curDay=0; bool g_halted=false, g_dayBlocked=false;
datetime g_lastRebalMonth=0;   // 当月リバランス済みか

//==================================================================
int SplitCSV(string csv, string &arr[])
{
   string p[]; int k=StringSplit(csv, ',', p); int m=0; ArrayResize(arr,k);
   for(int i=0;i<k;i++){ string s=p[i]; StringTrimLeft(s); StringTrimRight(s);
      if(StringLen(s)>0){ arr[m]=s; m++; } }
   ArrayResize(arr,m); return m;
}

string ResolveSymbol(string want)
{
   string suf[]={"",".pi",".raw",".ecn",".stp",".pro",".cash",".r",".c",".m","m",".spot","-cash",".sd","+",".i","_SB","_raw",".a",".z"};
   string bases[]; ArrayResize(bases,40); int nb=0;
   bases[nb++]=want;
   string U=want; StringToUpper(U);
   if(StringFind(U,"SPX")>=0 || StringFind(U,"500")>=0){
      bases[nb++]="US500"; bases[nb++]="SPX500"; bases[nb++]="SP500"; bases[nb++]="USA500"; bases[nb++]="US500Cash"; bases[nb++]="US_500"; bases[nb++]="SPX"; bases[nb++]="US500.cash"; }
   else if(StringFind(U,"NAS")>=0 || StringFind(U,"USTEC")>=0 || StringFind(U,"NDX")>=0 || StringFind(U,"US100")>=0 || StringFind(U,"TECH")>=0){
      bases[nb++]="NAS100"; bases[nb++]="USTEC"; bases[nb++]="US100"; bases[nb++]="NDX100"; bases[nb++]="USTECH"; bases[nb++]="NDX"; bases[nb++]="US_TECH100"; bases[nb++]="NAS100.cash"; }
   else if(StringFind(U,"GER")>=0 || StringFind(U,"DAX")>=0 || StringFind(U,"DE40")>=0 || StringFind(U,"DE30")>=0){
      bases[nb++]="GER40"; bases[nb++]="DE40"; bases[nb++]="DAX40"; bases[nb++]="GER30"; bases[nb++]="DE30"; bases[nb++]="GERMANY40"; bases[nb++]="DAX"; bases[nb++]="GER40.cash"; }
   ArrayResize(bases,nb);
   for(int b=0;b<nb;b++)
      for(int s=0;s<ArraySize(suf);s++){
         string cand=bases[b]+suf[s];
         if(SymbolSelect(cand,true)) return cand;
      }
   return "";
}

int OnInit()
{
   if(!InpAcknowledgeDemo){ Print("[STOP] NH52はADOPTだが本資金前デモ実測が先。InpAcknowledgeDemo=trueで承認。"); return INIT_FAILED; }
   int ns=SplitCSV(InpSymbols,g_syms);
   if(ns==0){ Print("シンボルのパース失敗"); return INIT_FAILED; }
   g_mNH=InpMagicBase+1;
   g_initBal=(InpInitialBalance>0.0)?InpInitialBalance:AccountInfoDouble(ACCOUNT_BALANCE);
   if(g_initBal<=0.0) g_initBal=AccountInfoDouble(ACCOUNT_EQUITY);

   ArrayResize(g_atrD1,ns);
   for(int i=0;i<ns;i++){
      string r=ResolveSymbol(g_syms[i]); g_atrD1[i]=INVALID_HANDLE;
      if(r==""){ PrintFormat("⚠ 銘柄 %s 見つからず→スキップ",g_syms[i]); continue; }
      if(r!=g_syms[i]) PrintFormat("[銘柄解決] %s → %s",g_syms[i],r);
      g_syms[i]=r; g_atrD1[i]=iATR(g_syms[i],PERIOD_D1,InpAtrPeriodD1);
   }
   trade.SetDeviationInPoints(InpSlippagePoints);
   g_peakEquity=g_initBal;
   ResetDay(TimeCurrent());
   PrintFormat("[INIT NH52] initBal=%.0f syms=%s ratio=%.2f lookback=%dD monthRisk=%.2f%% floor=-%.1f%% daily=-%.1f%%",
      g_initBal,InpSymbols,InpNearHighRatio,InpHighLookbackD,InpMonthRiskPct,InpAccountFloorDDPct,InpDailyStopPct);
   if(InpVerboseLog) Print("[NOTE] NH52=52週高値近接スリーブ(ADOPT,docs/72)。本資金前デモ必須。Magic=",g_mNH);
   EventSetTimer(30);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){
   EventKillTimer();
   for(int i=0;i<ArraySize(g_atrD1);i++) if(g_atrD1[i]!=INVALID_HANDLE) IndicatorRelease(g_atrD1[i]);
}

datetime DayStart(datetime t){ MqlDateTime s; TimeToStruct(t,s); s.hour=0;s.min=0;s.sec=0; return StructToTime(s); }
void ResetDay(datetime t){ g_curDay=DayStart(t); g_dayStartEq=AccountInfoDouble(ACCOUNT_EQUITY); g_dayBlocked=false; }
double AtrAt(int handle){ double a[1]; if(handle==INVALID_HANDLE||CopyBuffer(handle,0,1,1,a)<1) return 0.0; return a[0]; }
double PointOf(string s){ return SymbolInfoDouble(s,SYMBOL_POINT); }

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

bool HaveSym(string sym){
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()==g_mNH && posinfo.Symbol()==sym) return true; }
   return false;
}
void CloseSym(string sym, string why){
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()==g_mNH && posinfo.Symbol()==sym){ trade.PositionClose(tk);
         if(InpVerboseLog) PrintFormat("[CLOSE %s] %s",why,sym); } }
}
void CloseAllMine(string why){
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()==g_mNH) trade.PositionClose(tk); }
   if(InpVerboseLog) PrintFormat("[CLOSE ALL %s]",why);
}

// 当月の確定済みD1足数=今日が当月何営業日目か(概算)
int DomFromStart(string sym, datetime now)
{
   MqlDateTime n; TimeToStruct(now,n);
   int cnt=0;
   for(int i=0;i<40;i++){
      datetime bt=(datetime)iTime(sym,PERIOD_D1,i);
      if(bt==0) break;
      MqlDateTime b; TimeToStruct(bt,b);
      if(b.mon!=n.mon || b.year!=n.year) break;
      cnt++;
   }
   return cnt;
}

// NH52判定: 直近確定足(前営業日=月初判定なら前月末)の終値 >= 過去 InpHighLookbackD 本の最高終値×ratio
bool NearHigh(string sym)
{
   double cl[];
   int need=InpHighLookbackD+1;
   if(CopyClose(sym,PERIOD_D1,1,need,cl)<need) return false;  // 履歴不足は建てない(保守)
   double last=cl[need-1];                                    // 直近確定終値
   double hi=0.0;
   for(int i=0;i<need;i++) if(cl[i]>hi) hi=cl[i];
   if(hi<=0.0) return false;
   return (last >= hi*InpNearHighRatio);
}

//==================================================================
void OnTimer()
{
   datetime now=TimeCurrent();
   if(DayStart(now)!=g_curDay) ResetDay(now);
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);

   // ---- ガード階層(規約準拠): 全停止フロア(equityベース) ----
   if(equity>g_peakEquity) g_peakEquity=equity;
   double floor_=g_initBal*(1.0-InpAccountFloorDDPct/100.0);
   if(equity<=floor_ && !g_halted){ g_halted=true; CloseAllMine("EQUITY_FLOOR");
      PrintFormat("[HALT] equity %.2f <= floor %.2f",equity,floor_); }
   if(g_halted){ CloseAllMine("HALTED"); return; }

   // ---- 日次ストップ(当日開始equity起点・規約−5%手前) ----
   if(InpDailyStopPct>0){
      double dpnl=equity-g_dayStartEq;
      if(dpnl<=-g_initBal*InpDailyStopPct/100.0 && !g_dayBlocked){
         g_dayBlocked=true; CloseAllMine("DAILY_STOP");
         PrintFormat("[DAILY STOP] %.2f",dpnl); }
   }
   if(g_dayBlocked) return;

   // ---- 月次リバランス: 月初 InpEntryDom 営業日目に1回 ----
   MqlDateTime mk; TimeToStruct(now,mk); mk.day=1; mk.hour=0; mk.min=0; mk.sec=0;
   datetime thisMonth=StructToTime(mk);
   if(g_lastRebalMonth==thisMonth) return;       // 当月実施済み
   int dom=DomFromStart(g_syms[0],now);
   if(dom<InpEntryDom) return;

   Rebalance();
   g_lastRebalMonth=thisMonth;
}

void Rebalance()
{
   int ns=ArraySize(g_syms);
   // 1パス目: NH52判定 → 保有すべき銘柄リスト
   bool want[]; ArrayResize(want,ns); int nWant=0;
   for(int i=0;i<ns;i++){
      want[i]=(g_atrD1[i]!=INVALID_HANDLE && NearHigh(g_syms[i]));
      if(want[i]) nWant++;
   }
   if(InpVerboseLog){
      string s="";
      for(int i=0;i<ns;i++) s+=StringFormat("%s=%s ",g_syms[i],want[i]?"ON":"off");
      PrintFormat("[REBAL NH52] %s(保有%d/%d)",s,nWant,ns);
   }
   // 2パス目: 条件外は決済
   for(int i=0;i<ns;i++)
      if(!want[i] && HaveSym(g_syms[i])) CloseSym(g_syms[i],"NH52_OFF");
   if(nWant==0) return;
   // 3パス目: 条件内で未保有なら建てる(等加重=今月のリスク予算をnWantで等分)
   double perSym=InpMonthRiskPct/nWant;
   trade.SetExpertMagicNumber(g_mNH);
   for(int i=0;i<ns;i++){
      if(!want[i] || HaveSym(g_syms[i])) continue;
      string sym=g_syms[i]; double pt=PointOf(sym); if(pt<=0) continue;
      double atr=AtrAt(g_atrD1[i]); if(atr<=0) continue;
      double sd=InpCatastropheATR*atr; double sp=sd/pt;
      if(sp<InpMinStopPts){ sp=InpMinStopPts; sd=sp*pt; }
      double ask=SymbolInfoDouble(sym,SYMBOL_ASK), bid=SymbolInfoDouble(sym,SYMBOL_BID);
      if(ask<=0||bid<=0) continue;
      if((ask-bid)/pt>InpMaxSpreadPts) continue;
      double riskMoney=g_initBal*(perSym/100.0);
      double lots=LotsFor(sym,sd,riskMoney); if(lots<InpMinLot) continue;
      int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      double sl=NormalizeDouble(ask-sd,dg);
      if(trade.Buy(lots,sym,0.0,sl,0.0,StringFormat("NH52_%s",sym)))
         { if(InpVerboseLog) PrintFormat("[NH52 ENTRY] LONG %s lots=%.2f SL=%.2f perSym=%.3f%%",sym,lots,sl,perSym); }
   }
}
//+------------------------------------------------------------------+
//| 残存リスク(誠実な記録, docs/72):                                 |
//|  ・ADOPTは「Yahoo日足10年・本ハーネス内」の等級。配当除く指数・     |
//|    終値モデル・スワップ未精緻=実CFDでの再測(Drive)とデモ前進検証    |
//|    が本資金の前提。                                               |
//|  ・価値の正体はリスクタイミング(DD回避)でありリターン超過ではない。  |
//|    強気相場ではバイ&ホールドに純益で劣後しうる(それで正常)。        |
//|  ・1ヶ月保有=スワップ/配当調整の累積は業者差大→デモで実測。         |
//|  ・トレンド系(MA2/E5と同族)。E5系スリーブと併用するとトレンド       |
//|    リスクが重複する→ポート組込みは等ボラ比較(docs/67手順)後。       |
//|  ・建て/決済の営業日判定はD1足で概算。業者カレンダーに依存。        |
//|  ・1チャートに本EAは1つだけ(Magic帯950740で他EAと分離)。            |
//+------------------------------------------------------------------+
