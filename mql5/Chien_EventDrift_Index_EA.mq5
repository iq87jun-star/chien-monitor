//+------------------------------------------------------------------+
//|                       Chien_EventDrift_Index_EA.mq5               |
//|   マクロ・イベント・ドリフト "E-FOMC" 候補EA(第3並走ポート核候補): |
//|   株価指数バスケット(US500/NAS100/GER40)を、FOMC公表の"前営業日"に  |
//|   等加重LONGし、公表当日に時間決済する 24h イベント・ドリフト戦略。  |
//|                                                                   |
//|   ■ なぜこのエッジか(docs/65): 既存の探索土俵=曜日/月末/月別/プレ   |
//|     祝日/年末年始/足内セッション は出尽くし(v7/E-Mon/S-Jul のみ生存)。|
//|     本EAの根拠=これまで未検定の『マクロ・イベント・ドリフト』を      |
//|     research/event_intermarket_edge_10y.py で一括事前登録検定する    |
//|     第3並走ポート(口座C)の"核候補"。古典的アノマリー:                |
//|       Lucca & Moench(2015) "pre-FOMC announcement drift"=米株は      |
//|       FOMC公表直前24hに超過リターンを稼ぐ。曜日(v7/E-Mon)とは        |
//|       機序が直交(イベント日条件)=A・B両方と低相関の第3系統候補。     |
//|                                                                   |
//|   ■ ★重要(数字を盛らない/docs/65): このエッジは本リポジトリでは     |
//|     まだ Drive10年で確定検証していない=LEAD未満の"候補"。           |
//|     先に notebooks/event_intermarket.ipynb を Drive 実行し、         |
//|       (1) 年次ブロックp / (2) 既存4成分(v7/v4/E5/E-Mon)すべてと       |
//|       |相関|<=0.3 / (3) IS-OOS均衡 / (4) コスト2xでもnet>0           |
//|     を満たし STRONG-LEAD と確認できてから、デモ前進検証(docs/29)。    |
//|     本資金投入は その後。InpAcknowledgeCANDIDATE で承認(=候補/極小)。|
//|                                                                   |
//|   ■ トレード定義(バックテストと同形):                              |
//|     FOMC公表の InpDaysBefore 営業日前(既定1=前日)の InpEntryHourUTC  |
//|     に指数バスケットを等加重LONG → 公表当日の InpExitHourUTC または   |
//|     InpHoldHours 経過で時間決済。各銘柄1ポジ・SL=2.5ATR(災害保険)。  |
//|   ■ ガードは全EA共通(docs/01規約準拠): equityフロア(既定−8%/最終     |
//|     backstop−10%)・日次−4%(規約−5%手前)・毎ティック equity 監視。    |
//|                                                                   |
//|   ★FOMC日表は定例会合のみ(下記 InpFomcDates)。Fed公式カレンダーで   |
//|     毎年要更新: federalreserve.gov/monetarypolicy/fomccalendars.htm |
//|   ★1チャートに本EAを1つだけドロップ(どの銘柄/足でも可)。残高は自動。 |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.00"
#property strict
#property description "Event-drift index basket (pre-FOMC drift, E-FOMC). LONG equity indices the trading day before FOMC announcements. CANDIDATE = validate on Drive + demo first. FundedNext guards built-in."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

input group "=== イベント設定（pre-FOMC drift）==="
input string InpSymbols       = "US500,NAS100,GER40"; // 指数バスケット(等加重LONG)
input int    InpDaysBefore    = 1;            // FOMC公表の何営業日前に建てるか(既定1=前日)
input int    InpEntryHourUTC  = 14;           // 建て時刻(UTC)。米セッション開始帯に合わせる
input int    InpExitHourUTC   = 14;           // 決済時刻(UTC)。公表当日のこの時刻に時間決済
input int    InpHoldHours     = 28;           // 最大保有時間(時間決済の保険。前日14時→翌日18時等)
// FOMC公表日(定例・概ね会合2日目)。★Fed公式で毎年更新すること。下記は2024-2026の公表日。
input string InpFomcDates     = "2024.01.31,2024.03.20,2024.05.01,2024.06.12,2024.07.31,2024.09.18,2024.11.07,2024.12.18,2025.01.29,2025.03.19,2025.05.07,2025.06.18,2025.07.30,2025.09.17,2025.10.29,2025.12.10,2026.01.28,2026.03.18,2026.04.29,2026.06.17,2026.07.29,2026.09.16,2026.10.28,2026.12.09";

input group "=== サイズ（候補=サテライト小サイズ）==="
input bool   InpAcknowledgeCANDIDATE = true;  // E-FOMC=Drive未確定の候補。デモ/極小で承認=true
input double InpEventRiskPct  = 1.00;         // 1イベントあたりの総リスク%(全銘柄合算の予算)
input double InpCatastropheATR = 2.5;         // 災害SL=2.5×ATR(D1)
input double InpMinStopPts     = 50.0;        // 指数の最小SL(ポイント)
input double InpMaxSpreadPts   = 1500.0;      // 指数スプレッド上限(ポイント)
input int    InpAtrPeriodD1    = 14;          // 日次ATR期間

input group "=== 口座/ガード（docs/01規約準拠）==="
input double InpInitialBalance = 0.0;         // 0=口座残高を自動取得
input double InpMaxLossLimitPct= 10.0;        // 失格ライン%(最終backstop)
input double InpAccountFloorDDPct = 8.0;      // 全停止ライン%(規約−10%の手前。守り=8.0)
input double InpDailyStopPct   = 4.0;         // 日次全決済%(規約−5%の手前)。0で無効

input group "=== 共通 ==="
input double InpMinLot = 0.01;
input double InpMaxLot = 50.0;
input long   InpMagicBase = 950740;           // イベント・ドリフト=+1(他EAと衝突しないMagic帯)
input int    InpSlippagePoints = 30;
input bool   InpVerboseLog = true;

//==================================================================
CTrade        trade;
CPositionInfo posinfo;

string   g_syms[]; int g_atrD1[];
datetime g_fomc[];                 // 公表日(00:00 UTC)昇順
double   g_initBal=0.0;
long     g_mEvent=0;
double   g_peakEquity=0.0, g_dayStartEq=0.0;
datetime g_curDay=0; bool g_halted=false, g_dayBlocked=false;
datetime g_curEvent=0;             // 現在建て対象としているFOMC日(二重建て防止)
datetime g_entryTime=0;            // 建てた時刻(保有時間管理)

//==================================================================
int SplitCSV(string csv, string &arr[])
{
   string p[]; int k=StringSplit(csv, ',', p); int m=0; ArrayResize(arr,k);
   for(int i=0;i<k;i++){ string s=p[i]; StringTrimLeft(s); StringTrimRight(s);
      if(StringLen(s)>0){ arr[m]=s; m++; } }
   ArrayResize(arr,m); return m;
}

int ParseDates(string csv, datetime &arr[])
{
   string p[]; int k=StringSplit(csv, ',', p); int m=0; ArrayResize(arr,k);
   for(int i=0;i<k;i++){ string s=p[i]; StringTrimLeft(s); StringTrimRight(s);
      if(StringLen(s)==0) continue;
      datetime d=StringToTime(s);             // "YYYY.MM.DD" → 00:00
      if(d>0){ arr[m]=d; m++; } }
   ArrayResize(arr,m);
   ArraySort(arr);
   return m;
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
   if(!InpAcknowledgeCANDIDATE){ Print("[STOP] E-FOMC=Drive未確定の候補。InpAcknowledgeCANDIDATE=trueで承認(デモ/極小)。先にnotebooks/event_intermarket.ipynbで検証。"); return INIT_FAILED; }
   int ns=SplitCSV(InpSymbols,g_syms);
   int nf=ParseDates(InpFomcDates,g_fomc);
   if(ns==0||nf==0){ Print("シンボル/FOMC日のパース失敗"); return INIT_FAILED; }
   g_mEvent=InpMagicBase+1;
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
   PrintFormat("[INIT E-FOMC] initBal=%.0f FOMC件数=%d syms=%s eventRisk=%.2f%% floor=-%.1f%% daily=-%.1f%%",
      g_initBal,nf,InpSymbols,InpEventRiskPct,InpAccountFloorDDPct,InpDailyStopPct);
   if(InpVerboseLog) Print("[NOTE] E-FOMC=第3並走ポート核候補(docs/65)。Drive10年で要確定→デモ必須。Magic=",g_mEvent);
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
      if(posinfo.Magic()==g_mEvent) n++; }
   return n;
}
void CloseAllMine(string why){
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()==g_mEvent) trade.PositionClose(tk); }
   if(InpVerboseLog) PrintFormat("[CLOSE ALL %s]",why);
}

// 直近の未来FOMC公表日(=今日以降で最小)。無ければ0。
datetime NextFomc(datetime today0)
{
   for(int i=0;i<ArraySize(g_fomc);i++) if(g_fomc[i]>=today0) return g_fomc[i];
   return 0;
}

// today0(当日00:00) が ev の InpDaysBefore 営業日前か(土日を除いた営業日数で判定)。
bool IsEntryDay(datetime today0, datetime ev)
{
   if(ev<=today0) return false;
   int bdays=0; datetime d=today0;
   for(int i=0;i<10;i++){
      d+=86400; MqlDateTime s; TimeToStruct(d,s);
      if(s.day_of_week>=1 && s.day_of_week<=5) bdays++;   // 月-金のみ営業日カウント
      if(DayStart(d)==DayStart(ev)) return (bdays==InpDaysBefore);
      if(d>ev) break;
   }
   return false;
}

//==================================================================
void OnTimer()
{
   datetime now=TimeCurrent();
   if(DayStart(now)!=g_curDay) ResetDay(now);
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);

   // ---- ガード階層(規約準拠): 全停止フロア(equityベース) ----
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
   datetime today0=DayStart(now);

   // ---- 決済: 公表当日の決済時刻 到達 or 最大保有時間 超過 ----
   if(CountMine()>0){
      bool exitByHour = (g_curEvent>0 && today0==DayStart(g_curEvent) && t.hour>=InpExitHourUTC);
      bool exitByHold = (g_entryTime>0 && (now-g_entryTime) >= (long)InpHoldHours*3600);
      if(exitByHour || exitByHold){
         CloseAllMine(exitByHour?"FOMC_DAY_EXIT":"HOLD_TIMEOUT");
         g_curEvent=0; g_entryTime=0;
      }
   }

   if(g_dayBlocked) return;
   if(CountMine()>0) return;            // 既に建て中

   // ---- エントリ: 直近FOMCの InpDaysBefore 営業日前・建て時刻到達・当該イベント未建て ----
   datetime ev=NextFomc(today0);
   if(ev<=0) return;
   if(g_curEvent==ev) return;           // この公表向けは建て済み(決済後リセット済みのはず)
   if(!IsEntryDay(today0,ev)) return;
   if(t.hour<InpEntryHourUTC) return;

   OpenBasket(ev);
}

void OpenBasket(datetime ev)
{
   int ns=ArraySize(g_syms);
   double perSym=InpEventRiskPct/(ns>0?ns:1);
   trade.SetExpertMagicNumber(g_mEvent);
   int opened=0;
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
      if(trade.Buy(lots,sym,0.0,sl,0.0,StringFormat("EFOMC_%s",sym)))
         { opened++; if(InpVerboseLog) PrintFormat("[E-FOMC ENTRY] LONG %s lots=%.2f SL=%.2f perSym=%.3f%% ev=%s",sym,lots,sl,perSym,TimeToString(ev,TIME_DATE)); }
   }
   if(opened>0){ g_curEvent=ev; g_entryTime=TimeCurrent(); }
}
//+------------------------------------------------------------------+
//| 残存リスク(誠実な記録, docs/65):                                 |
//|  ・E-FOMC=本リポジトリでは Drive10年 未確定の"候補"。LEAD未満。     |
//|    まず notebooks/event_intermarket.ipynb で 年次ブロックp /        |
//|    既存4成分すべてと|相関|<=0.3 / IS-OOS均衡 / コスト頑健 を確認し、 |
//|    STRONG-LEAD なら デモ前進検証(docs/29)。本資金はその後・小サイズ。|
//|  ・pre-FOMC drift は学術的に有名(Lucca&Moench 2015)だが、2010年代   |
//|    後半に減衰したとの報告もある=レジーム依存の疑い。年次ブロックp/   |
//|    OOSで必ず確認(派手な過去純益に釣られない/docs/07,08の轍)。        |
//|  ・FOMC日表(InpFomcDates)は定例会合のみ・手入力。緊急会合は含まない。 |
//|    毎年 Fed 公式カレンダーで更新必須(古いと建たない/誤建て)。        |
//|  ・建て営業日判定は土日のみ除外の近似(指数の休場日は考慮しない)。   |
//|    祝日が前日に当たる場合のズレは デモで実建てタイミングを実確認。    |
//|  ・指数CFDの実スプレッド/スワップ/取引時間は業者差大→デモで実測。   |
//|  ・サテライト/候補=小サイズ(既定 1イベント1%)厳守。主軸にしない。   |
//|    主軸は v4(ADOPT)/v7/E-Mon。本EAは"足す"第3系統の検証台。          |
//|  ・1チャートに本EAは1つだけ(他EAと同口座ならMagic帯950740で分離)。   |
//+------------------------------------------------------------------+
