//+------------------------------------------------------------------+
//|                 Chien_FTMO_Compliant_AllInOne.mq5                |
//|   FTMO規約準拠 オールインワン: v4(FX9ペアk≥4合議 両建て) +        |
//|   E-Mon(株価指数 月曜LONG限定) を1チャート挿入で運用。            |
//|                                                                   |
//|   ■ 確定スペック(docs/61): 手法 v4 : E-Mon = 55 : 45。            |
//|     準拠でCalmar1.81・年率@−6%10.9%＝非準拠P★(1.66)を上回る。      |
//|     v4=FX / E-Mon=指数LONGのみ＝【同一銘柄の反対両建てを作らない】 |
//|     ＝FTMOヘッジ禁止に抵触しない(v7/E5は衝突ゆえ不採用, docs/59)。 |
//|                                                                   |
//|   ■ FTMO準拠ガード(docs/59-61):                                   |
//|     ・E-Monは LONG のみ(指数SHORTを一切作らない)。                |
//|     ・v4は1ペア1ポジ(同一ペアの反対同時なし)。FXのみ=指数非接触。 |
//|     ・ニュース2分制限: 高インパクト指標 前後で新規見送り          |
//|       (FTMO Swing口座を使うなら InpUseNewsFilter=false で可)。     |
//|     ・損失ガード(docs/60): 日次−3%(FTMO−5%の内側)/総合フロア−8%   |
//|       (−10%の手前で全停止)/各ポジ災害SL。失格率の決定的低減手段。 |
//|     ・最大割当 $400k/戦略・顧客 はFN/FTMO合算で管理(EA外)。        |
//|                                                                   |
//|   ■ サイズ・シナリオ(docs/62-63 ＝出発点・デモで実DD確認):        |
//|     保守−6% / 中庸−8%(推奨) / 攻め−10% / 速攻(中央4ヶ月 ×1.64) /  |
//|     超速攻(中央3ヶ月 ×2.0=要強ガード・口座喪失前提)。             |
//|     funded後は必ず中庸へ減サイズ(生存優先, docs/57)。            |
//|                                                                   |
//|   ★1チャートに本EA1つだけ。残高自動。銘柄名は業者仕様に。         |
//|   ⚠ v4=ADOPT/E-Mon=STRONG-LEAD(未確証)＝本資金前デモ前進検証必須。 |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.00"
#property strict
#property description "FTMO-compliant all-in-one: v4(FX k>=4 confluence, long/short) + E-Mon(equity-index Monday LONG only). News filter + hard guards. v4:E-Mon=55:45."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

enum ENUM_FTMO_SCENARIO
{
   FT_CONSERVATIVE = 0, // 保守 -6% (失格ほぼ無・確実な資金化)
   FT_BALANCED     = 1, // 中庸 -8% (推奨・収益と生存の最適点)
   FT_AGGRESSIVE   = 2, // 攻め -10%枠フル
   FT_FAST4        = 3, // 速攻 中央4ヶ月 (×1.64・失格~11%・要ガード)
   FT_FAST3        = 4, // 超速攻 中央3ヶ月 (×2.0・失格~15%・口座喪失前提)
   FT_MANUAL       = 5  // 手動(下のv4/E-Mon値)
};

input group "=== シナリオ（倍率/比率を自動設定・55:45）==="
input ENUM_FTMO_SCENARIO InpScenario = FT_BALANCED;  // ★推奨=中庸-8%
input bool   InpAcknowledgeLEAD = true;   // v4=ADOPT/E-Mon=STRONG-LEAD。デモ/極小で承認

input group "=== 銘柄（業者の実銘柄名に合わせる）==="
input string InpV4Symbols   = "EURUSD,GBPUSD,USDJPY,AUDUSD,USDCHF,USDCAD,NZDUSD,EURJPY,GBPJPY"; // v4: FX9
input string InpEMonSymbols = "US500,NAS100,GER40";   // E-Mon: 株価指数3(LONGのみ)

input group "=== 口座/ガード（FTMO準拠・docs/60）==="
input double InpInitialBalance   = 0.0;   // 0=口座残高を自動取得
input double InpMaxLossLimitPct  = 10.0;  // 失格ライン%(FTMO)
input double InpAccountFloorDDPct= 8.0;   // 総合フロア%で全停止(-10%の手前)
input double InpDailyStopPct     = 3.0;   // 日次ストップ%(FTMO-5%の内側)
input bool   InpUseDailyStop     = true;

input group "=== 手動配分（FT_MANUAL時・55:45の目安）==="
input double InpV4RiskPerTradePct = 0.27; // v4 1トレードあたりリスク%
input double InpEMonWeeklyPct     = 0.65; // E-Mon 週次リスク%(ショット数で割る)

input group "=== v4 設定（日足k≥4合議）==="
input int    InpV4_RSI=14;  input double InpV4_RSIlo=35.0, InpV4_RSIhi=65.0;
input int    InpV4_BBwin=20; input double InpV4_BBz=1.5;
input int    InpV4_streak=3; input double InpV4_dayMovePct=0.5;
input int    InpV4_ATR=14;   input double InpV4_SLatr=1.5, InpV4_RR=1.2;
input int    InpV4_MaxHoldDays=8;
input bool   InpV4_AllowShort=true;       // FTMO: 同一ペアの反対同時は作らない(1ペア1ポジ)。SHORT自体は可

input group "=== E-Mon 設定（指数 月曜LONG・24h）==="
input int    InpEntryWeekday=1;           // 1=月曜
input string InpEntryHoursUTC="9,14";     // 月曜の建て時刻(欧州/米)
input int    InpShotsPerWeek=6;           // 指数3×時刻2
input int    InpHoldHours=24;
input int    InpAtrPeriodH1=24;
input double InpCatastropheATR=2.5;
input double InpMinStopPts=50.0, InpMaxStopPts=200000.0, InpMaxSpreadPts=1500.0;

input group "=== ニュースフィルタ（FTMO 2分制限・Swingならfalse）==="
input bool   InpUseNewsFilter=true;
input int    InpNewsBeforeMin=2;
input int    InpNewsAfterMin=2;

input group "=== 共通 ==="
input double InpMinLot=0.01, InpMaxLot=50.0;
input long   InpMagicBase=960800;         // v4=+1 / E-Mon=+2
input int    InpSlippagePoints=30;
input bool   InpVerboseLog=true;

//==================================================================
CTrade        trade;
CPositionInfo posinfo;

string   g_v4[]; string g_emon[]; int g_hours[];
int      g_atrD1[]; int g_rsiD1[]; int g_atrH1[];
datetime g_lastV4Bar[]; datetime g_lastShot[];
double   g_initBal=0.0, g_v4risk=0.27, g_emonWeekly=0.65;
double   g_maxLossPct=10.0, g_floorPct=8.0, g_dailyPct=3.0;
double   g_dayStartEq=0.0; datetime g_curDay=0; bool g_halted=false, g_dayBlocked=false;
string   g_scen=""; long g_mV4=0, g_mEMon=0;

//==================================================================
int SplitCSV(string csv, string &arr[])
{
   string p[]; int k=StringSplit(csv,',',p); int m=0; ArrayResize(arr,k);
   for(int i=0;i<k;i++){ string s=p[i]; StringTrimLeft(s); StringTrimRight(s); if(StringLen(s)>0){ arr[m]=s; m++; } }
   ArrayResize(arr,m); return m;
}
int SplitHours(string csv, int &arr[])
{
   string p[]; int k=StringSplit(csv,',',p); int m=0; ArrayResize(arr,k);
   for(int i=0;i<k;i++){ string s=p[i]; StringTrimLeft(s); StringTrimRight(s); if(StringLen(s)==0) continue;
      int h=(int)StringToInteger(s); if(h>=0&&h<=23){ arr[m]=h; m++; } }
   ArrayResize(arr,m); return m;
}
double PipOf(string s){ return (StringFind(s,"JPY")>=0)? 0.01 : 0.0001; }
double PointOf(string s){ return SymbolInfoDouble(s,SYMBOL_POINT); }

string ResolveSymbol(string want)
{
   string suf[]={"",".pi",".raw",".ecn",".stp",".pro",".cash",".r",".c",".m","m",".spot","-cash",".sd","+",".i","_SB","_raw",".a",".z"};
   string bases[]; ArrayResize(bases,40); int nb=0; bases[nb++]=want;
   string U=want; StringToUpper(U);
   if(StringFind(U,"SPX")>=0 || StringFind(U,"500")>=0){
      bases[nb++]="US500"; bases[nb++]="SPX500"; bases[nb++]="SP500"; bases[nb++]="USA500"; bases[nb++]="US500.cash"; bases[nb++]="US_500"; }
   else if(StringFind(U,"NAS")>=0 || StringFind(U,"USTEC")>=0 || StringFind(U,"NDX")>=0 || StringFind(U,"US100")>=0){
      bases[nb++]="NAS100"; bases[nb++]="USTEC"; bases[nb++]="US100"; bases[nb++]="NDX100"; bases[nb++]="USTECH"; bases[nb++]="NAS100.cash"; }
   else if(StringFind(U,"GER")>=0 || StringFind(U,"DAX")>=0 || StringFind(U,"DE40")>=0){
      bases[nb++]="GER40"; bases[nb++]="DE40"; bases[nb++]="DAX40"; bases[nb++]="GER30"; bases[nb++]="GERMANY40"; bases[nb++]="GER40.cash"; }
   ArrayResize(bases,nb);
   for(int b=0;b<nb;b++) for(int s=0;s<ArraySize(suf);s++){ string cand=bases[b]+suf[s]; if(SymbolSelect(cand,true)) return cand; }
   return "";
}

void ResolveScenario()
{
   g_v4risk=InpV4RiskPerTradePct; g_emonWeekly=InpEMonWeeklyPct;
   g_maxLossPct=InpMaxLossLimitPct; g_floorPct=InpAccountFloorDDPct; g_dailyPct=InpDailyStopPct;
   g_scen="MANUAL";
   // サイズはdocs/62-63の出発点(55:45・目標p95年DD)。デモで実DDを見て調整。
   if(InpScenario==FT_CONSERVATIVE){ g_scen="CONSERV_-6%"; g_v4risk=0.20; g_emonWeekly=0.50; g_floorPct=8.0; }
   else if(InpScenario==FT_BALANCED){ g_scen="BALANCED_-8%"; g_v4risk=0.27; g_emonWeekly=0.65; g_floorPct=8.0; }
   else if(InpScenario==FT_AGGRESSIVE){ g_scen="AGGR_-10%"; g_v4risk=0.33; g_emonWeekly=0.80; g_floorPct=9.0; }
   else if(InpScenario==FT_FAST4){ g_scen="FAST4_x1.64"; g_v4risk=0.44; g_emonWeekly=1.07; g_floorPct=9.0; }
   else if(InpScenario==FT_FAST3){ g_scen="FAST3_x2.0";  g_v4risk=0.54; g_emonWeekly=1.30; g_floorPct=9.0; }
}

int OnInit()
{
   if(!InpAcknowledgeLEAD){ Print("[STOP] v4=ADOPT/E-Mon=STRONG-LEAD。InpAcknowledgeLEAD=trueで承認(デモ/極小)。"); return INIT_FAILED; }
   int nv=SplitCSV(InpV4Symbols,g_v4);
   int nm=SplitCSV(InpEMonSymbols,g_emon);
   int nh=SplitHours(InpEntryHoursUTC,g_hours);
   if(nv==0||nm==0||nh==0){ Print("シンボル/時刻パース失敗"); return INIT_FAILED; }
   ResolveScenario();
   g_mV4=InpMagicBase+1; g_mEMon=InpMagicBase+2;
   g_initBal=(InpInitialBalance>0.0)?InpInitialBalance:AccountInfoDouble(ACCOUNT_BALANCE);
   if(g_initBal<=0.0) g_initBal=AccountInfoDouble(ACCOUNT_EQUITY);

   ArrayResize(g_atrD1,nv); ArrayResize(g_rsiD1,nv); ArrayResize(g_lastV4Bar,nv); ArrayInitialize(g_lastV4Bar,0);
   ArrayResize(g_atrH1,nm); ArrayResize(g_lastShot,nm*nh); ArrayInitialize(g_lastShot,0);

   for(int i=0;i<nv;i++){
      string r=ResolveSymbol(g_v4[i]); g_atrD1[i]=INVALID_HANDLE; g_rsiD1[i]=INVALID_HANDLE;
      if(r==""){ PrintFormat("⚠ v4銘柄 %s 見つからず→スキップ",g_v4[i]); continue; }
      if(r!=g_v4[i]) PrintFormat("[銘柄解決] v4 %s → %s",g_v4[i],r);
      g_v4[i]=r; g_atrD1[i]=iATR(g_v4[i],PERIOD_D1,InpV4_ATR); g_rsiD1[i]=iRSI(g_v4[i],PERIOD_D1,InpV4_RSI,PRICE_CLOSE);
   }
   for(int i=0;i<nm;i++){
      string r=ResolveSymbol(g_emon[i]); g_atrH1[i]=INVALID_HANDLE;
      if(r==""){ PrintFormat("⚠ E-Mon銘柄 %s 見つからず→スキップ",g_emon[i]); continue; }
      if(r!=g_emon[i]) PrintFormat("[銘柄解決] E-Mon %s → %s",g_emon[i],r);
      g_emon[i]=r; g_atrH1[i]=iATR(g_emon[i],PERIOD_H1,InpAtrPeriodH1);
   }
   trade.SetDeviationInPoints(InpSlippagePoints);
   ResetDay(TimeCurrent());
   PrintFormat("[INIT FTMO %s] initBal=%.0f v4/trade=%.2f%% E-Mon週次=%.2f%% floor=-%.0f%% daily=%s(-%.0f%%) news=%s",
      g_scen,g_initBal,g_v4risk,g_emonWeekly,g_floorPct,(InpUseDailyStop?"Y":"N"),g_dailyPct,(InpUseNewsFilter?"Y":"N"));
   if(InpVerboseLog) Print("[NOTE] FTMO準拠: E-Mon=LONGのみ(指数SHORT無)・v4=1ペア1ポジ。Magic ",g_mV4,"/",g_mEMon,"。1口座1EA。");
   EventSetTimer(30);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){
   EventKillTimer();
   for(int i=0;i<ArraySize(g_atrD1);i++) if(g_atrD1[i]!=INVALID_HANDLE) IndicatorRelease(g_atrD1[i]);
   for(int i=0;i<ArraySize(g_rsiD1);i++) if(g_rsiD1[i]!=INVALID_HANDLE) IndicatorRelease(g_rsiD1[i]);
   for(int i=0;i<ArraySize(g_atrH1);i++) if(g_atrH1[i]!=INVALID_HANDLE) IndicatorRelease(g_atrH1[i]);
}

datetime DayStart(datetime t){ MqlDateTime s; TimeToStruct(t,s); s.hour=0;s.min=0;s.sec=0; return StructToTime(s); }
void ResetDay(datetime t){ g_curDay=DayStart(t); g_dayStartEq=AccountInfoDouble(ACCOUNT_EQUITY); g_dayBlocked=false; }
double AtrAt(int h){ double a[1]; if(h==INVALID_HANDLE||CopyBuffer(h,0,1,1,a)<1) return 0.0; return a[0]; }

double LotsFor(string sym, double priceMove, double riskMoney)
{
   if(priceMove<=0||riskMoney<=0) return 0.0;
   double tv=SymbolInfoDouble(sym,SYMBOL_TRADE_TICK_VALUE), ts=SymbolInfoDouble(sym,SYMBOL_TRADE_TICK_SIZE);
   if(tv<=0||ts<=0) return 0.0;
   double lossPerLot=(priceMove/ts)*tv; if(lossPerLot<=0) return 0.0;
   double lots=riskMoney/lossPerLot;
   double step=SymbolInfoDouble(sym,SYMBOL_VOLUME_STEP), vmin=SymbolInfoDouble(sym,SYMBOL_VOLUME_MIN), vmax=SymbolInfoDouble(sym,SYMBOL_VOLUME_MAX);
   if(step>0) lots=MathFloor(lots/step)*step;
   lots=MathMin(lots,MathMin(InpMaxLot,vmax));
   if(lots<MathMax(InpMinLot,vmin)) return 0.0;
   return lots;
}
int CountPos(string sym,long magic){ int n=0; for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
   if(!posinfo.SelectByTicket(tk)) continue; if(posinfo.Symbol()==sym&&posinfo.Magic()==magic) n++; } return n; }
bool IsMine(long m){ return (m==g_mV4||m==g_mEMon); }
void CloseAllMine(string why){ for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
   if(!posinfo.SelectByTicket(tk)) continue; if(IsMine(posinfo.Magic())) trade.PositionClose(tk); }
   if(InpVerboseLog) PrintFormat("[CLOSE ALL %s]",why); }

//===== ニュースフィルタ(FTMO 2分) =====
bool CalendarHit(string ccy, datetime utc){
   if(StringLen(ccy)==0) return false;
   MqlCalendarValue vals[]; datetime from=utc-InpNewsAfterMin*60, to=utc+InpNewsBeforeMin*60;
   int n=CalendarValueHistory(vals,from,to,NULL,ccy); if(n<=0) return false;
   for(int i=0;i<n;i++){ MqlCalendarEvent ev; if(!CalendarEventById(vals[i].event_id,ev)) continue;
      if(ev.importance==CALENDAR_IMPORTANCE_HIGH) return true; }
   return false;
}
bool NewsBlackout(string sym, datetime utc){
   if(!InpUseNewsFilter) return false;
   string b=SymbolInfoString(sym,SYMBOL_CURRENCY_BASE), q=SymbolInfoString(sym,SYMBOL_CURRENCY_PROFIT);
   if(CalendarHit(b,utc)||CalendarHit(q,utc)) return true;
   // 指数はbase/profitが空/USDのことが多い→主要通貨を保険でチェック
   string U=sym; StringToUpper(U);
   if(StringFind(U,"US")>=0||StringFind(U,"NAS")>=0||StringFind(U,"SPX")>=0||StringFind(U,"500")>=0) return CalendarHit("USD",utc);
   if(StringFind(U,"GER")>=0||StringFind(U,"DAX")>=0||StringFind(U,"DE")>=0) return CalendarHit("EUR",utc);
   return false;
}

//==================================================================
void OnTimer()
{
   datetime now=TimeCurrent(); datetime utc=TimeGMT();
   if(DayStart(now)!=g_curDay) ResetDay(now);
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);

   // 総合フロア(全停止)
   double floorEq=g_initBal*(1.0-g_floorPct/100.0);
   if(equity<=floorEq && !g_halted){ g_halted=true; CloseAllMine("EQUITY_FLOOR");
      PrintFormat("[HALT] equity %.2f <= floor %.2f (-%.0f%%)",equity,floorEq,g_floorPct); }
   if(g_halted){ CloseAllMine("HALTED"); return; }

   // 日次ストップ
   if(InpUseDailyStop){
      double dpnl=equity-g_dayStartEq;
      if(dpnl<=-g_initBal*g_dailyPct/100.0 && !g_dayBlocked){ g_dayBlocked=true;
         CloseAllMine("DAILY_STOP"); PrintFormat("[DAILY STOP] %.2f (-%.0f%%)",dpnl,g_dailyPct); }
   }

   ManageV4Exit();
   ManageEMonExit();
   if(g_dayBlocked) return;       // 当日は新規停止

   EntriesV4(utc);
   EntriesEMon(utc);
}

//===== v4 (日足k≥4合議・long/short・1ペア1ポジ) =====
int V4Signal(string sym, int rsiHandle)
{
   double c[]; ArraySetAsSeries(c,true);
   int need=MathMax(InpV4_BBwin+2,InpV4_streak+3);
   if(CopyClose(sym,PERIOD_D1,1,need+2,c)<need+1) return 0;
   double rb[1]; if(rsiHandle==INVALID_HANDLE||CopyBuffer(rsiHandle,0,1,1,rb)<1) return 0;
   double rsi=rb[0];
   double mean=0; for(int k=1;k<=InpV4_BBwin;k++) mean+=c[k]; mean/=InpV4_BBwin;
   double var=0; for(int k=1;k<=InpV4_BBwin;k++) var+=(c[k]-mean)*(c[k]-mean); var/=(InpV4_BBwin-1);
   double sd=MathSqrt(var); double z=(sd>0)?(c[0]-mean)/sd:0.0;
   int down=0; for(int k=0;k<12;k++){ if(c[k]<c[k+1]) down++; else break; }
   int up=0;   for(int k=0;k<12;k++){ if(c[k]>c[k+1]) up++;   else break; }
   double ret=(c[1]!=0)?(c[0]-c[1])/c[1]:0.0; double mv=InpV4_dayMovePct/100.0;
   int buy =(rsi<InpV4_RSIlo?1:0)+(z<-InpV4_BBz?1:0)+(down>=InpV4_streak?1:0)+(ret<-mv?1:0);
   int sell=(rsi>InpV4_RSIhi?1:0)+(z> InpV4_BBz?1:0)+(up  >=InpV4_streak?1:0)+(ret> mv?1:0);
   if(buy>=4 && buy>sell) return 1;
   if(sell>=4 && sell>buy && InpV4_AllowShort) return -1;
   return 0;
}
void ManageV4Exit(){
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue; if(posinfo.Magic()!=g_mV4) continue;
      int heldDays=(int)((TimeCurrent()-(datetime)posinfo.Time())/86400);
      if(heldDays>=InpV4_MaxHoldDays){ if(trade.PositionClose(tk)&&InpVerboseLog) PrintFormat("[v4 TIME EXIT %dd] %s",heldDays,posinfo.Symbol()); } }
}
void EntriesV4(datetime utc){
   trade.SetExpertMagicNumber(g_mV4);
   for(int i=0;i<ArraySize(g_v4);i++){
      if(g_atrD1[i]==INVALID_HANDLE) continue;
      string sym=g_v4[i];
      datetime db=(datetime)iTime(sym,PERIOD_D1,0);
      if(db==0||db==g_lastV4Bar[i]) continue;       // 1日1回評価
      g_lastV4Bar[i]=db;
      if(CountPos(sym,g_mV4)>0) continue;            // 既存v4建玉あれば積まない(=1ペア1ポジ・準拠)
      int sig=V4Signal(sym,g_rsiD1[i]); if(sig==0) continue;
      if(NewsBlackout(sym,utc)){ if(InpVerboseLog) Print("[v4 SKIP news] ",sym); continue; }
      double atr=AtrAt(g_atrD1[i]); if(atr<=0) continue;
      double sd=InpV4_SLatr*atr, tpd=InpV4_RR*sd;
      double riskMoney=g_initBal*(g_v4risk/100.0);
      double lots=LotsFor(sym,sd,riskMoney); if(lots<InpMinLot) continue;
      int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      if(sig>0){ double e=SymbolInfoDouble(sym,SYMBOL_ASK); double sl=NormalizeDouble(e-sd,dg), tp=NormalizeDouble(e+tpd,dg);
         if(trade.Buy(lots,sym,0.0,sl,tp,"v4_"+sym)&&InpVerboseLog) PrintFormat("[v4 LONG] %s lots=%.2f",sym,lots); }
      else     { double e=SymbolInfoDouble(sym,SYMBOL_BID); double sl=NormalizeDouble(e+sd,dg), tp=NormalizeDouble(e-tpd,dg);
         if(trade.Sell(lots,sym,0.0,sl,tp,"v4_"+sym)&&InpVerboseLog) PrintFormat("[v4 SHORT] %s lots=%.2f",sym,lots); }
   }
}

//===== E-Mon (株価指数 月曜LONG限定・24h・リスク予算化) =====
void ManageEMonExit(){
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue; if(posinfo.Magic()!=g_mEMon) continue;
      int held=(int)(TimeCurrent()-(datetime)posinfo.Time());
      if(held>=InpHoldHours*3600){ if(trade.PositionClose(tk)&&InpVerboseLog) PrintFormat("[E-Mon TIME EXIT] %s",posinfo.Symbol()); } }
}
void EntriesEMon(datetime utc){
   MqlDateTime u; TimeToStruct(utc,u);
   if(u.day_of_week!=InpEntryWeekday) return;
   int slot=-1; for(int h=0;h<ArraySize(g_hours);h++) if(u.hour==g_hours[h]){ slot=h; break; }
   if(slot<0) return;
   datetime hourBar=utc-(utc%3600); int nh=ArraySize(g_hours);
   double perShot=g_emonWeekly/(InpShotsPerWeek>0?InpShotsPerWeek:1);
   trade.SetExpertMagicNumber(g_mEMon);
   for(int s=0;s<ArraySize(g_emon);s++){
      if(g_atrH1[s]==INVALID_HANDLE) continue;
      int key=s*nh+slot; if(g_lastShot[key]==hourBar) continue;
      string sym=g_emon[s]; double pt=PointOf(sym); if(pt<=0) continue;
      double atr=AtrAt(g_atrH1[s]); if(atr<=0) continue;
      double sd=InpCatastropheATR*atr; double sp=sd/pt;
      if(sp<InpMinStopPts){ sp=InpMinStopPts; sd=sp*pt; }
      if(sp>InpMaxStopPts) continue;
      double ask=SymbolInfoDouble(sym,SYMBOL_ASK), bid=SymbolInfoDouble(sym,SYMBOL_BID);
      if(ask<=0||bid<=0) continue;
      if((ask-bid)/pt>InpMaxSpreadPts){ g_lastShot[key]=hourBar; continue; }
      if(NewsBlackout(sym,utc)){ if(InpVerboseLog) Print("[E-Mon SKIP news] ",sym); g_lastShot[key]=hourBar; continue; }
      double riskMoney=g_initBal*(perShot/100.0);
      double lots=LotsFor(sym,sd,riskMoney); if(lots<InpMinLot){ g_lastShot[key]=hourBar; continue; }
      int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      double sl=NormalizeDouble(ask-sd,dg);
      g_lastShot[key]=hourBar;
      // ★FTMO準拠: E-Mon は LONG のみ(指数SHORTを作らない)
      if(trade.Buy(lots,sym,0.0,sl,0.0,StringFormat("EMon_%s_h%d",sym,g_hours[slot])))
         { if(InpVerboseLog) PrintFormat("[E-Mon LONG] %s h%dUTC lots=%.2f perShot=%.3f%%",sym,g_hours[slot],lots,perShot); }
   }
}
//+------------------------------------------------------------------+
//| 残存リスク(誠実な記録):                                          |
//|  ・v4=ADOPT(実10年Dukascopy)/E-Mon=STRONG-LEAD(未確証)＝本資金前  |
//|    デモ前進検証必須(docs/29)。                                    |
//|  ・FTMO準拠: E-Mon=LONGのみ・v4=1ペア1ポジ(同一銘柄反対なし)・     |
//|    v4(FX)とE-Mon(指数)は銘柄非接触。指数SHORTは構造的に発生しない。 |
//|    ⚠ v4が高相関ペア(EURJPY long+GBPJPY short等)を同時に持つのは    |
//|    グレー(意図的ヘッジでなければ通常許容)。気になればv4銘柄を絞るか |
//|    抑制ガードを追加。最終判断はFTMO公式Forbidden Practices。       |
//|  ・サイズ既定はdocs/62-63の出発点(55:45)。必ずデモで実併用maxDDが  |
//|    目標(-8%等)・-10%内かを確認してから本番。funded後は中庸へ。     |
//|  ・ニュースフィルタは高インパクトのみ。FTMO Swing口座なら不要      |
//|    (InpUseNewsFilter=false)。指数のnews通貨判定は保険的。          |
//|  ・1チャートに本EA1つだけ(複数/他EAと同口座でMagic衝突回避)。      |
//|  ・最大割当$400k/戦略はFN/FTMO合算で管理(EA外, docs/58)。          |
//+------------------------------------------------------------------+
