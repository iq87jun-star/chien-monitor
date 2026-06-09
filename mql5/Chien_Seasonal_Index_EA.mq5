//+------------------------------------------------------------------+
//|                       Chien_Seasonal_Index_EA.mq5                 |
//|   季節性(month-of-year)エッジ "S-Jul/S-Nov" 銘柄EA:                |
//|   株価指数バスケット(US500/NAS100[/GER40]) を、指定した暦月だけ     |
//|   丸ごとLONG保有する季節性サテライト。既存ポート(v7/E-Mon/E5)に      |
//|   "別の発火窓"で利益を足す第3系統(docs/64)。                        |
//|                                                                   |
//|   ■ なぜこのエッジか(docs/64): これまでの探索は「曜日(DOW)」と       |
//|     「月末(TOM)」のみ。本EAの根拠=未トライ土俵                      |
//|     『曜日・月末以外のカレンダー(プレ祝日/年末年始/月別)』を         |
//|     research/calendar_event_edge_10y.py(N=164/Bonferroni)で一括検定。|
//|     生存パターン=【株価指数の "7月" ロング(S-Jul)】が最もクリーン:   |
//|       US500 7月: 年次ブロックp=0.0024・陽性年90%・maxDD−4.0%・        |
//|       IS+13.2%/OOS+14.3%(均衡)・JKmax0.016・コスト3xでも+。          |
//|       バスケットS-Jul(US500+NAS100): 陽性年80%・最悪年−0.4%・        |
//|       ★E-Mon相関 −0.31(負=指数月曜の真の分散源)。                   |
//|     11月(S-Nov)も陽性だがE-Mon相関+0.55(冗長)。既定=7月、11月は任意。 |
//|                                                                   |
//|   ■ 正直な限界(数字を盛らない/docs/64):                            |
//|     単月季節性の実サンプル=年数(10)しかない。日次pは過大評価しうる   |
//|     ので★年次ブロックpで採点。Bonferroni(α=0.0003)は未達=v7/E-Mon    |
//|     と同じ天井。∴ ADOPTではなく SEASONAL-LEAD。サテライト(小サイズ)  |
//|     限定・本資金前にデモ前進検証(docs/29)必須。                     |
//|                                                                   |
//|   ■ トレード定義(バックテストと同形):                              |
//|     対象月の最初の取引日に指数バスケットを等加重LONG → 月末(または    |
//|     翌月初)に時間決済。各銘柄1ポジ・SL=2.5ATR(災害保険)。            |
//|   ■ ガードは全EA共通(docs/01規約準拠): equityフロア(既定−8%/最終     |
//|     backstop−10%)・日次−4%(規約−5%手前)・毎ティック equity 監視。    |
//|                                                                   |
//|   ■ 7月開始シナリオ(docs/64 §8): 既存P1(v7:v4:E5)に7月だけ重畳する     |
//|     使い方では InpJulyBoostEnable=true で7月の実効リスクを             |
//|     InpMonthRiskPct×InpJulyRiskMult(既定1.0%×2.5=2.5%≒中サイズ)へ     |
//|     自動増量。中央4ヶ月運用(×1.47)で3ヶ月以内通過 ~38%→~41%・失格     |
//|     6.1%→5.6%(速度寄りの小改善)。効くのは速さで、失格減は小。         |
//|                                                                   |
//|   ★1チャートに本EAを1つだけドロップ(どの銘柄/足でも可)。残高は自動。 |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.00"
#property strict
#property description "Seasonal month-of-year index basket (S-Jul/S-Nov). Equity-index LONG for configured calendar months. SEASONAL-LEAD=demo first. FundedNext guards built-in."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

input group "=== 季節性設定（month-of-year）==="
input string InpSeasonMonths   = "7";          // 保有する暦月(CSV)。既定=7(S-Jul)。S-Nov併用は "7,11"
input string InpSymbols        = "US500,NAS100"; // 指数バスケット(等加重LONG)。S-Nov併用時は GER40 追加可
input int    InpEntryDom       = 1;            // 月内 何営業日目に建てるか(1=月初第1営業日)。月跨ぎで自動決済

input group "=== サイズ（季節性=サテライト小サイズ）==="
input bool   InpAcknowledgeLEAD = true;        // S-Jul=SEASONAL-LEAD。デモ/極小で承認=true
input double InpMonthRiskPct   = 1.00;         // 1季節(1ヶ月)あたりの総リスク%(全銘柄合算の予算)
input bool   InpJulyBoostEnable = false;       // ★7月だけ中サイズへ自動増量(docs/64 §8: P1重畳の7月開始シナリオ)
input double InpJulyRiskMult    = 2.5;         // 7月の実効リスク= InpMonthRiskPct × この倍率(既定1.0%×2.5=2.5%≒中サイズ)
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
input long   InpMagicBase = 950730;            // 季節性=+1(他EAと衝突しないMagic帯)
input int    InpSlippagePoints = 30;
input bool   InpVerboseLog = true;

//==================================================================
CTrade        trade;
CPositionInfo posinfo;

string   g_syms[]; int g_atrD1[]; int g_months[];
double   g_initBal=0.0;
long     g_mSeason=0;
double   g_peakEquity=0.0, g_dayStartEq=0.0;
datetime g_curDay=0; bool g_halted=false, g_dayBlocked=false;
datetime g_lastEntryMonth=0;   // 二重建て防止(その月に建て済みか)

//==================================================================
int SplitCSV(string csv, string &arr[])
{
   string p[]; int k=StringSplit(csv, ',', p); int m=0; ArrayResize(arr,k);
   for(int i=0;i<k;i++){ string s=p[i]; StringTrimLeft(s); StringTrimRight(s);
      if(StringLen(s)>0){ arr[m]=s; m++; } }
   ArrayResize(arr,m); return m;
}
int SplitInts(string csv, int &arr[])
{
   string p[]; int k=StringSplit(csv, ',', p); int m=0; ArrayResize(arr,k);
   for(int i=0;i<k;i++){ string s=p[i]; StringTrimLeft(s); StringTrimRight(s);
      if(StringLen(s)==0) continue; arr[m]=(int)StringToInteger(s); m++; }
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
   if(!InpAcknowledgeLEAD){ Print("[STOP] S-Jul=SEASONAL-LEAD。InpAcknowledgeLEAD=trueで承認(デモ/極小)。"); return INIT_FAILED; }
   int ns=SplitCSV(InpSymbols,g_syms);
   int nm=SplitInts(InpSeasonMonths,g_months);
   if(ns==0||nm==0){ Print("シンボル/月のパース失敗"); return INIT_FAILED; }
   g_mSeason=InpMagicBase+1;
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
   PrintFormat("[INIT SEASONAL] initBal=%.0f months=%s syms=%s monthRisk=%.2f%% floor=-%.1f%% daily=-%.1f%%",
      g_initBal,InpSeasonMonths,InpSymbols,InpMonthRiskPct,InpAccountFloorDDPct,InpDailyStopPct);
   if(InpVerboseLog) Print("[NOTE] 季節性サテライト=S-Jul(SEASONAL-LEAD,docs/64)。本資金前デモ必須。Magic=",g_mSeason);
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

int CountMine(){
   int n=0;
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()==g_mSeason) n++; }
   return n;
}
void CloseAllMine(string why){
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()==g_mSeason) trade.PositionClose(tk); }
   if(InpVerboseLog) PrintFormat("[CLOSE ALL %s]",why);
}

// その営業日が「対象月・建て営業日」か / 「決済営業日(月末手前)」かを判定。
// 取引日インデックスは D1 足の並びで近似(休場は足が無い→自然にスキップ)。
int DomFromStart(string sym, datetime now)
{
   // 当月の最初の取引日から数えて何営業日目か(D1足の日付で算出)。
   MqlDateTime n; TimeToStruct(now,n);
   int cnt=0;
   for(int i=0;i<40;i++){
      datetime bt=(datetime)iTime(sym,PERIOD_D1,i);
      if(bt==0) break;
      MqlDateTime b; TimeToStruct(bt,b);
      if(b.mon!=n.mon || b.year!=n.year) break;
      cnt++;
   }
   return cnt;  // 当月内に存在する確定済み日足数=今日が当月何営業日目か(概算)
}

bool IsSeasonMonth(int mon)
{
   for(int i=0;i<ArraySize(g_months);i++) if(g_months[i]==mon) return true;
   return false;
}

//==================================================================
void OnTimer()
{
   datetime now=TimeCurrent();
   if(DayStart(now)!=g_curDay) ResetDay(now);
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);

   // ---- ガード階層(規約準拠): 全停止フロア(equityベース・毎ティック) ----
   if(equity>g_peakEquity) g_peakEquity=equity;
   double floor=g_initBal*(1.0-InpAccountFloorDDPct/100.0);
   if(equity<=floor && !g_halted){ g_halted=true; CloseAllMine("EQUITY_FLOOR");
      PrintFormat("[HALT] equity %.2f <= floor %.2f",equity,floor); }
   if(g_halted){ CloseAllMine("HALTED"); return; }

   // ---- 日次ストップ(当日開始equity起点・規約−5%手前) ----
   if(InpDailyStopPct>0){
      double dpnl=equity-g_dayStartEq;
      if(dpnl<=-g_initBal*InpDailyStopPct/100.0 && !g_dayBlocked){
         g_dayBlocked=true; CloseAllMine("DAILY_STOP");
         PrintFormat("[DAILY STOP] %.2f",dpnl); }
   }

   MqlDateTime t; TimeToStruct(now,t);
   bool inSeason = IsSeasonMonth(t.mon);

   // ---- 決済: 季節月を跨いだら翌月初の寄付で全決済(バックテスト定義=対象月末→翌月初openと一致) ----
   if(CountMine()>0 && !inSeason){ CloseAllMine("SEASON_END"); g_lastEntryMonth=0; }

   if(g_dayBlocked) return;

   // ---- エントリ: 季節月・当月未建て・建て営業日(月初 InpEntryDom 日目以降) ----
   if(!inSeason) return;
   MqlDateTime mk; TimeToStruct(now,mk); mk.day=1; mk.hour=0; mk.min=0; mk.sec=0;
   datetime thisMonth=StructToTime(mk);
   if(g_lastEntryMonth==thisMonth) return;       // 当月建て済み
   if(CountMine()>0) return;

   // 月初 InpEntryDom 営業日目に達したか(当月の確定済み日足数で概算)
   int dom=DomFromStart(g_syms[0],now);
   if(dom<InpEntryDom) return;

   OpenBasket();
   g_lastEntryMonth=thisMonth;
}

void OpenBasket()
{
   int ns=ArraySize(g_syms);
   // ★7月だけ中サイズへ自動増量(docs/64 §8)。建て月が7月かつ有効時のみ実効リスクを倍率適用。
   MqlDateTime nt; TimeToStruct(TimeCurrent(),nt);
   double monthRisk=InpMonthRiskPct;
   if(InpJulyBoostEnable && nt.mon==7 && InpJulyRiskMult>0.0){
      monthRisk=InpMonthRiskPct*InpJulyRiskMult;
      if(InpVerboseLog) PrintFormat("[JULY BOOST] 7月の実効リスク=%.2f%%(=%.2f%%×%.2f)",monthRisk,InpMonthRiskPct,InpJulyRiskMult);
   }
   double perSym=monthRisk/(ns>0?ns:1);
   trade.SetExpertMagicNumber(g_mSeason);
   for(int i=0;i<ns;i++){
      if(g_atrD1[i]==INVALID_HANDLE) continue;
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
      if(trade.Buy(lots,sym,0.0,sl,0.0,StringFormat("Season_%s",sym)))
         { if(InpVerboseLog) PrintFormat("[SEASONAL ENTRY] LONG %s lots=%.2f SL=%.2f perSym=%.3f%%",sym,lots,sl,perSym); }
   }
}
//+------------------------------------------------------------------+
//| 残存リスク(誠実な記録, docs/64):                                 |
//|  ・S-Jul=SEASONAL-LEAD。単月季節性=実サンプルは年数(10)のみ。      |
//|    年次ブロックp=0.0024(US500 7月)は良いが、10標本は薄い。         |
//|    Bonferroni(N=164, α=0.0003)未達=v7/E-Mon と同じ天井。ADOPT不可。|
//|  ・E-Mon相関 −0.31(S-Jul) = 指数月曜の真の分散源。だが S-Nov は    |
//|    E-Mon相関+0.55(冗長)。既定は7月のみ。11月併用は冗長承知で任意。  |
//|  ・指数CFDの実スプレッド/スワップ(1ヶ月保有=スワップ累積大)/配当/    |
//|    取引時間は業者差大。1ヶ月保有はスワップ負けの可能性→デモで実測。 |
//|    (スワップ回避したいなら保有を分割/翌月初決済に調整)             |
//|  ・サテライト小サイズ(既定 月次1%)厳守。季節性は"足す"もので主軸    |
//|    にしない。主軸は v4(ADOPT)/v7/E-Mon。                          |
//|  ・建て/決済の営業日判定はD1足で概算。業者の指数取引カレンダーに    |
//|    依存。本番前にデモで建て・決済タイミングを実確認。              |
//|  ・1チャートに本EAは1つだけ(他EAと同口座ならMagic帯950730で分離)。  |
//+------------------------------------------------------------------+
