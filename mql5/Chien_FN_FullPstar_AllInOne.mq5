//+------------------------------------------------------------------+
//|                   Chien_FN_FullPstar_AllInOne.mq5               |
//|   FundedNext用 最強P★ オールインワン(4戦略・1チャート挿入):      |
//|   v7(円月曜) + v4(FX k≥4合議) + E-Mon(株価指数 月曜) + E5(多資産) |
//|                                                                   |
//|   ■ なぜFNでフル4戦略か(docs/64-65): FundedNextは【同一口座内の    |
//|     ヘッジOK】ゆえ、FTMO用に削った v7/E5 も含めた最強P★            |
//|     (v4:35/v7:25/E-Mon:25/E5:15・docs/55最適・Calmar1.66)を1口座で。|
//|     FN条件 P1+8%(FTMO+10%より低)＋4戦略の滑らかさで、速攻でも       |
//|     失格が低い: ★中央4ヶ月 ×1.22 で P1失格3.9%/2段通過92.9%       |
//|     /funded月¥264k($100k・分配95%)。(docs/65)                     |
//|                                                                   |
//|   ■ 既定=FN_FAST4(中央4ヶ月・攻め枠の約1.22倍)。気長確実は         |
//|     FN_BALANCED(-8%)、守りは FN_CONSERV(-6%)。funded(資金化)後は    |
//|     必ず中庸へ減サイズ(生存優先, docs/57)。                        |
//|                                                                   |
//|   ■ 内部4戦略(Magic分離):                                         |
//|     v7   : 円3クロス 月曜04/06/08/10UTC LONG・24h(SL2.5ATR_H1)     |
//|     v4   : FX9 日足k≥4合議 long/short・SL1.5ATR/RR1.2/8日          |
//|     E-Mon: 指数3 月曜09/14UTC LONG・24h(SL2.5ATR_H1)               |
//|     E5   : 金+指数 月初TSMOM 両建て・逆ボラ加重(SL2.5ATR_MN1)       |
//|     口座ガード: 総合フロア(-9%)で全停止・日次-4%・+8%で新規停止     |
//|                                                                   |
//|   ★1チャートに本EA1つだけ。残高自動。銘柄名は業者仕様に。         |
//|   ⚠ v4=ADOPT/v7・E-Mon・E5=未確証=本資金前デモ前進検証必須。      |
//|     サイズ既定は出発点=デモで実maxDD/日次-5%抵触を確認し調整。     |
//|     FN一貫性ルール: 審査と本番で同じEA/戦略を維持。               |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.00"
#property strict
#property description "FundedNext full P-star all-in-one (4 strategies): v7+v4+E-Mon+E5 on one chart. Hedging-within-account OK. Default=FAST4 (median ~4 months). Demo first."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

enum ENUM_FNP_SCENARIO
{
   FNP_CONSERV  = 0, // 守り -6% (失格ほぼ無)
   FNP_BALANCED = 1, // 中庸 -8% (funded後の本線)
   FNP_FAST4    = 2, // ★速攻 中央4ヶ月 (×1.22・P1失格~3.9%)
   FNP_FAST3    = 3, // 超速攻 中央3ヶ月 (×1.63・P1失格~6.7%・要強ガード)
   FNP_MANUAL   = 4  // 手動(下の各値)
};

input group "=== シナリオ（倍率/比率を自動設定・P★ 35:25:25:15）==="
input ENUM_FNP_SCENARIO InpScenario = FNP_FAST4;   // ★既定=速攻 中央4ヶ月
input bool   InpAcknowledgeLEAD = true;   // v4=ADOPT/他=未確証。デモ/極小で承認

input group "=== 銘柄（業者の実銘柄名に合わせる）==="
input string InpYenSymbols  = "EURJPY,GBPJPY,USDJPY";                          // v7: 円3
input string InpV4Symbols   = "EURUSD,GBPUSD,USDJPY,AUDUSD,USDCHF,USDCAD,NZDUSD,EURJPY,GBPJPY"; // v4: FX9
input string InpEMonSymbols = "US500,NAS100,GER40";                            // E-Mon: 指数3
input string InpE5Symbols   = "XAUUSD,US500,NAS100,GER40";                     // E5: 金+指数

input group "=== 口座/ガード（FundedNext）==="
input double InpInitialBalance   = 0.0;   // 0=口座残高を自動取得
input double InpMaxLossLimitPct  = 10.0;  // 失格ライン%
input double InpAccountFloorDDPct= 9.0;   // 総合フロア%で全停止(-10%手前)
input double InpProfitTargetPct  = 8.0;   // FN Phase1目標+8%で新規停止
input bool   InpUseProfitStop    = true;  // 審査中=true / funded(無目標)=false
input double InpDailyStopPct     = 4.0;   // 日次ストップ%(FN-5%の内側)
input bool   InpUseDailyStop     = true;

input group "=== 手動配分（FNP_MANUAL時・P★ 35:25:25:15目安）==="
input double InpWeeklyRiskPct    = 0.90;  // v7 週次リスク%
input double InpV4RiskPerTradePct= 0.50;  // v4 1トレードリスク%
input double InpEMonWeeklyPct    = 0.85;  // E-Mon 週次リスク%
input double InpE5LegRiskPct     = 0.55;  // E5 legRisk%

input group "=== v7 / E-Mon 共通(月曜・時間決済) ==="
input string InpEntryHoursUTC    = "4,6,8,10";   // v7 円の建て時刻
input string InpEMonHoursUTC     = "9,14";       // E-Mon 指数の建て時刻
input int    InpShotsPerWeekYen  = 12;           // v7 = 円3×4時刻
input int    InpShotsPerWeekEMon = 6;            // E-Mon = 指数3×2時刻
input int    InpHoldHours        = 24;
input int    InpAtrPeriodH1      = 24;
input double InpCatastropheATR   = 2.5;
input double InpMinStopPips      = 10.0;          // 円(pips)
input double InpMaxStopPips      = 400.0;
input double InpMaxSpreadPips    = 3.0;
input double InpIdxMinStopPts    = 50.0;          // 指数(ポイント)
input double InpIdxMaxStopPts    = 200000.0;
input double InpIdxMaxSpreadPts  = 1500.0;

input group "=== v4 設定（日足k≥4合議）==="
input int    InpV4_RSI=14;  input double InpV4_RSIlo=35.0, InpV4_RSIhi=65.0;
input int    InpV4_BBwin=20; input double InpV4_BBz=1.5;
input int    InpV4_streak=3; input double InpV4_dayMovePct=0.5;
input int    InpV4_ATR=14;   input double InpV4_SLatr=1.5, InpV4_RR=1.2;
input int    InpV4_MaxHoldDays=8; input bool InpV4_AllowShort=true;

input group "=== E5 設定（多資産月次TSMOM）==="
input int    InpLB1=1, InpLB2=3, InpLB3=6, InpLB4=12;
input bool   InpAllowShort=true;
input int    InpAtrPeriodMN1=6; input double InpCatATR_E5=2.5;

input group "=== 共通 ==="
input double InpMinLot=0.01, InpMaxLot=50.0;
input long   InpMagicBase=970800;        // v7=+1 / v4=+2 / E-Mon=+3 / E5=+4
input int    InpSlippagePoints=30;
input bool   InpVerboseLog=true;

//==================================================================
CTrade        trade;
CPositionInfo posinfo;

string   g_yen[]; string g_v4[]; string g_emon[]; string g_e5[];
int      g_hY[]; int g_hE[];
int      g_atrYen[]; int g_atrD1[]; int g_rsiD1[]; int g_atrEMon[]; int g_atrMN1[];
datetime g_lastY[]; datetime g_lastV4Bar[]; datetime g_lastE[]; datetime g_lastMonth[];
double   g_initBal=0.0, g_v7w=0.9, g_v4r=0.5, g_emw=0.85, g_e5l=0.55;
double   g_maxLossPct=10.0, g_floorPct=9.0, g_profitPct=8.0, g_dailyPct=4.0;
bool     g_useProfit=true, g_useDaily=true;
double   g_dayStartEq=0.0; datetime g_curDay=0; bool g_halted=false, g_dayBlocked=false;
string   g_scen=""; long g_mV7=0, g_mV4=0, g_mEMon=0, g_mE5=0;

//==================================================================
int SplitCSV(string csv, string &arr[]){
   string p[]; int k=StringSplit(csv,',',p); int m=0; ArrayResize(arr,k);
   for(int i=0;i<k;i++){ string s=p[i]; StringTrimLeft(s); StringTrimRight(s); if(StringLen(s)>0){ arr[m]=s; m++; } }
   ArrayResize(arr,m); return m; }
int SplitHours(string csv, int &arr[]){
   string p[]; int k=StringSplit(csv,',',p); int m=0; ArrayResize(arr,k);
   for(int i=0;i<k;i++){ string s=p[i]; StringTrimLeft(s); StringTrimRight(s); if(StringLen(s)==0) continue;
      int h=(int)StringToInteger(s); if(h>=0&&h<=23){ arr[m]=h; m++; } }
   ArrayResize(arr,m); return m; }
double PipOf(string s){ return (StringFind(s,"JPY")>=0)? 0.01 : 0.0001; }
double PointOf(string s){ return SymbolInfoDouble(s,SYMBOL_POINT); }

string ResolveSymbol(string want){
   string suf[]={"",".pi",".raw",".ecn",".stp",".pro",".cash",".r",".c",".m","m",".spot","-cash",".sd","+",".i","_SB","_raw",".a",".z"};
   string bases[]; ArrayResize(bases,40); int nb=0; bases[nb++]=want;
   string U=want; StringToUpper(U);
   if(StringFind(U,"XAU")>=0||StringFind(U,"GOLD")>=0){ bases[nb++]="XAUUSD"; bases[nb++]="GOLD"; bases[nb++]="GOLDUSD"; }
   else if(StringFind(U,"SPX")>=0||StringFind(U,"500")>=0){ bases[nb++]="US500"; bases[nb++]="SPX500"; bases[nb++]="SP500"; bases[nb++]="USA500"; bases[nb++]="US500.cash"; }
   else if(StringFind(U,"NAS")>=0||StringFind(U,"USTEC")>=0||StringFind(U,"NDX")>=0||StringFind(U,"US100")>=0){ bases[nb++]="NAS100"; bases[nb++]="USTEC"; bases[nb++]="US100"; bases[nb++]="NDX100"; bases[nb++]="NAS100.cash"; }
   else if(StringFind(U,"GER")>=0||StringFind(U,"DAX")>=0||StringFind(U,"DE40")>=0){ bases[nb++]="GER40"; bases[nb++]="DE40"; bases[nb++]="DAX40"; bases[nb++]="GER40.cash"; }
   ArrayResize(bases,nb);
   for(int b=0;b<nb;b++) for(int s=0;s<ArraySize(suf);s++){ string cand=bases[b]+suf[s]; if(SymbolSelect(cand,true)) return cand; }
   return ""; }

void ResolveScenario(){
   g_v7w=InpWeeklyRiskPct; g_v4r=InpV4RiskPerTradePct; g_emw=InpEMonWeeklyPct; g_e5l=InpE5LegRiskPct;
   g_maxLossPct=InpMaxLossLimitPct; g_floorPct=InpAccountFloorDDPct; g_profitPct=InpProfitTargetPct;
   g_dailyPct=InpDailyStopPct; g_useProfit=InpUseProfitStop; g_useDaily=InpUseDailyStop; g_scen="MANUAL";
   // P★ 35:25:25:15(v4:v7:E-Mon:E5)を各サイズで。出発点=デモで実DD確認。
   if(InpScenario==FNP_CONSERV){  g_scen="CONSERV_-6%";  g_v7w=0.45; g_v4r=0.22; g_emw=0.42; g_e5l=0.27; g_floorPct=8.0; }
   else if(InpScenario==FNP_BALANCED){ g_scen="BALANCED_-8%"; g_v7w=0.60; g_v4r=0.30; g_emw=0.55; g_e5l=0.35; g_floorPct=8.0; }
   else if(InpScenario==FNP_FAST4){ g_scen="FAST4_x1.22"; g_v7w=0.73; g_v4r=0.37; g_emw=0.67; g_e5l=0.43; g_floorPct=9.0; }
   else if(InpScenario==FNP_FAST3){ g_scen="FAST3_x1.63"; g_v7w=0.98; g_v4r=0.49; g_emw=0.90; g_e5l=0.57; g_floorPct=9.0; }
}

int OnInit(){
   if(!InpAcknowledgeLEAD){ Print("[STOP] v4=ADOPT/他=未確証。InpAcknowledgeLEAD=trueで承認(デモ/極小)。"); return INIT_FAILED; }
   int ny=SplitCSV(InpYenSymbols,g_yen), nv=SplitCSV(InpV4Symbols,g_v4);
   int nm=SplitCSV(InpEMonSymbols,g_emon), ne=SplitCSV(InpE5Symbols,g_e5);
   int nhY=SplitHours(InpEntryHoursUTC,g_hY), nhE=SplitHours(InpEMonHoursUTC,g_hE);
   if(ny==0||nv==0||nm==0||ne==0||nhY==0||nhE==0){ Print("シンボル/時刻パース失敗"); return INIT_FAILED; }
   ResolveScenario();
   g_mV7=InpMagicBase+1; g_mV4=InpMagicBase+2; g_mEMon=InpMagicBase+3; g_mE5=InpMagicBase+4;
   g_initBal=(InpInitialBalance>0.0)?InpInitialBalance:AccountInfoDouble(ACCOUNT_BALANCE);
   if(g_initBal<=0.0) g_initBal=AccountInfoDouble(ACCOUNT_EQUITY);

   ArrayResize(g_atrYen,ny); ArrayResize(g_lastY,ny*nhY); ArrayInitialize(g_lastY,0);
   ArrayResize(g_atrD1,nv); ArrayResize(g_rsiD1,nv); ArrayResize(g_lastV4Bar,nv); ArrayInitialize(g_lastV4Bar,0);
   ArrayResize(g_atrEMon,nm); ArrayResize(g_lastE,nm*nhE); ArrayInitialize(g_lastE,0);
   ArrayResize(g_atrMN1,ne); ArrayResize(g_lastMonth,ne); ArrayInitialize(g_lastMonth,0);

   for(int i=0;i<ny;i++){ string r=ResolveSymbol(g_yen[i]); g_atrYen[i]=INVALID_HANDLE;
      if(r==""){ PrintFormat("⚠ v7銘柄 %s 無→skip",g_yen[i]); continue; }
      g_yen[i]=r; g_atrYen[i]=iATR(g_yen[i],PERIOD_H1,InpAtrPeriodH1); }
   for(int i=0;i<nv;i++){ string r=ResolveSymbol(g_v4[i]); g_atrD1[i]=INVALID_HANDLE; g_rsiD1[i]=INVALID_HANDLE;
      if(r==""){ PrintFormat("⚠ v4銘柄 %s 無→skip",g_v4[i]); continue; }
      g_v4[i]=r; g_atrD1[i]=iATR(g_v4[i],PERIOD_D1,InpV4_ATR); g_rsiD1[i]=iRSI(g_v4[i],PERIOD_D1,InpV4_RSI,PRICE_CLOSE); }
   for(int i=0;i<nm;i++){ string r=ResolveSymbol(g_emon[i]); g_atrEMon[i]=INVALID_HANDLE;
      if(r==""){ PrintFormat("⚠ E-Mon銘柄 %s 無→skip",g_emon[i]); continue; }
      g_emon[i]=r; g_atrEMon[i]=iATR(g_emon[i],PERIOD_H1,InpAtrPeriodH1); }
   for(int i=0;i<ne;i++){ string r=ResolveSymbol(g_e5[i]); g_atrMN1[i]=INVALID_HANDLE;
      if(r==""){ PrintFormat("⚠ E5銘柄 %s 無→skip",g_e5[i]); continue; }
      g_e5[i]=r; g_atrMN1[i]=iATR(g_e5[i],PERIOD_MN1,InpAtrPeriodMN1); }

   trade.SetDeviationInPoints(InpSlippagePoints);
   ResetDay(TimeCurrent());
   PrintFormat("[INIT FN-P★ %s] initBal=%.0f v7=%.2f%% v4=%.2f%% E-Mon=%.2f%% E5=%.2f%% floor=-%.0f%% profit=%s(+%.0f%%) daily=%s(-%.0f%%)",
      g_scen,g_initBal,g_v7w,g_v4r,g_emw,g_e5l,g_floorPct,(g_useProfit?"Y":"N"),g_profitPct,(g_useDaily?"Y":"N"),g_dailyPct);
   if(InpVerboseLog) Print("[NOTE] FN=同一口座ヘッジOK→4戦略同居可。Magic ",g_mV7,"/",g_mV4,"/",g_mEMon,"/",g_mE5,"。1口座1EA。funded後はProfitStop=false・中庸へ。");
   EventSetTimer(30);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){
   EventKillTimer();
   for(int i=0;i<ArraySize(g_atrYen);i++) if(g_atrYen[i]!=INVALID_HANDLE) IndicatorRelease(g_atrYen[i]);
   for(int i=0;i<ArraySize(g_atrD1);i++) if(g_atrD1[i]!=INVALID_HANDLE) IndicatorRelease(g_atrD1[i]);
   for(int i=0;i<ArraySize(g_rsiD1);i++) if(g_rsiD1[i]!=INVALID_HANDLE) IndicatorRelease(g_rsiD1[i]);
   for(int i=0;i<ArraySize(g_atrEMon);i++) if(g_atrEMon[i]!=INVALID_HANDLE) IndicatorRelease(g_atrEMon[i]);
   for(int i=0;i<ArraySize(g_atrMN1);i++) if(g_atrMN1[i]!=INVALID_HANDLE) IndicatorRelease(g_atrMN1[i]);
}

datetime DayStart(datetime t){ MqlDateTime s; TimeToStruct(t,s); s.hour=0;s.min=0;s.sec=0; return StructToTime(s); }
void ResetDay(datetime t){ g_curDay=DayStart(t); g_dayStartEq=AccountInfoDouble(ACCOUNT_EQUITY); g_dayBlocked=false; }
double AtrAt(int h){ double a[1]; if(h==INVALID_HANDLE||CopyBuffer(h,0,1,1,a)<1) return 0.0; return a[0]; }
double LotsFor(string sym, double priceMove, double riskMoney){
   if(priceMove<=0||riskMoney<=0) return 0.0;
   double tv=SymbolInfoDouble(sym,SYMBOL_TRADE_TICK_VALUE), ts=SymbolInfoDouble(sym,SYMBOL_TRADE_TICK_SIZE);
   if(tv<=0||ts<=0) return 0.0;
   double lossPerLot=(priceMove/ts)*tv; if(lossPerLot<=0) return 0.0;
   double lots=riskMoney/lossPerLot;
   double step=SymbolInfoDouble(sym,SYMBOL_VOLUME_STEP), vmin=SymbolInfoDouble(sym,SYMBOL_VOLUME_MIN), vmax=SymbolInfoDouble(sym,SYMBOL_VOLUME_MAX);
   if(step>0) lots=MathFloor(lots/step)*step;
   lots=MathMin(lots,MathMin(InpMaxLot,vmax));
   if(lots<MathMax(InpMinLot,vmin)) return 0.0;
   return lots; }
int CountPos(string sym,long magic){ int n=0; for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
   if(!posinfo.SelectByTicket(tk)) continue; if(posinfo.Symbol()==sym&&posinfo.Magic()==magic) n++; } return n; }
int DirOf(string sym,long magic){ for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
   if(!posinfo.SelectByTicket(tk)) continue; if(posinfo.Symbol()==sym&&posinfo.Magic()==magic)
      return (posinfo.PositionType()==POSITION_TYPE_BUY?1:-1); } return 0; }
void CloseSymMagic(string sym,long magic,string why){ for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
   if(!posinfo.SelectByTicket(tk)) continue; if(posinfo.Symbol()==sym&&posinfo.Magic()==magic){ if(trade.PositionClose(tk)&&InpVerboseLog) PrintFormat("[CLOSE %s] %s",why,sym); } } }
bool IsMine(long m){ return (m==g_mV7||m==g_mV4||m==g_mEMon||m==g_mE5); }
void CloseAllMine(string why){ for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
   if(!posinfo.SelectByTicket(tk)) continue; if(IsMine(posinfo.Magic())) trade.PositionClose(tk); }
   if(InpVerboseLog) PrintFormat("[CLOSE ALL %s]",why); }

//==================================================================
void OnTimer(){
   datetime now=TimeCurrent(); datetime utc=TimeGMT();
   if(DayStart(now)!=g_curDay) ResetDay(now);
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);

   double floorEq=g_initBal*(1.0-g_floorPct/100.0);
   if(equity<=floorEq && !g_halted){ g_halted=true; CloseAllMine("EQUITY_FLOOR");
      PrintFormat("[HALT] equity %.2f <= floor %.2f",equity,floorEq); }
   if(g_halted){ CloseAllMine("HALTED"); return; }

   if(g_useDaily){ double dpnl=equity-g_dayStartEq;
      if(dpnl<=-g_initBal*g_dailyPct/100.0 && !g_dayBlocked){ g_dayBlocked=true; CloseAllMine("DAILY_STOP");
         PrintFormat("[DAILY STOP] %.2f",dpnl); } }

   ManageV7Exit(); ManageEMonExit(); ManageV4Exit(); ManageE5();

   bool blockNew=(g_useProfit && equity>=g_initBal*(1.0+g_profitPct/100.0)) || g_dayBlocked;
   if(blockNew) return;

   EntriesV7(utc); EntriesEMon(utc); EntriesV4(utc); EntriesE5();
}

//===== v7 (円月曜 多ショット) =====
void ManageV7Exit(){ for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
   if(!posinfo.SelectByTicket(tk)) continue; if(posinfo.Magic()!=g_mV7) continue;
   int held=(int)(TimeCurrent()-(datetime)posinfo.Time());
   if(held>=InpHoldHours*3600){ if(trade.PositionClose(tk)&&InpVerboseLog) PrintFormat("[v7 TIME EXIT] %s",posinfo.Symbol()); } } }
void EntriesV7(datetime utc){
   MqlDateTime u; TimeToStruct(utc,u); if(u.day_of_week!=1) return;
   int slot=-1; for(int h=0;h<ArraySize(g_hY);h++) if(u.hour==g_hY[h]){ slot=h; break; }
   if(slot<0) return; datetime hourBar=utc-(utc%3600); int nh=ArraySize(g_hY);
   double perShot=g_v7w/(InpShotsPerWeekYen>0?InpShotsPerWeekYen:1);
   trade.SetExpertMagicNumber(g_mV7);
   for(int s=0;s<ArraySize(g_yen);s++){ if(g_atrYen[s]==INVALID_HANDLE) continue;
      int key=s*nh+slot; if(g_lastY[key]==hourBar) continue;
      string sym=g_yen[s]; double pip=PipOf(sym); double atr=AtrAt(g_atrYen[s]); if(atr<=0) continue;
      double sd=InpCatastropheATR*atr; double sp=sd/pip; if(sp<InpMinStopPips){ sp=InpMinStopPips; sd=sp*pip; }
      if(sp>InpMaxStopPips) continue;
      double ask=SymbolInfoDouble(sym,SYMBOL_ASK), bid=SymbolInfoDouble(sym,SYMBOL_BID); if(ask<=0||bid<=0) continue;
      if((ask-bid)/pip>InpMaxSpreadPips){ g_lastY[key]=hourBar; continue; }
      double lots=LotsFor(sym,sd,g_initBal*(perShot/100.0)); if(lots<InpMinLot){ g_lastY[key]=hourBar; continue; }
      int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS); double sl=NormalizeDouble(ask-sd,dg);
      g_lastY[key]=hourBar;
      if(trade.Buy(lots,sym,0.0,sl,0.0,StringFormat("v7_%s_h%d",sym,g_hY[slot]))&&InpVerboseLog) PrintFormat("[v7 LONG] %s h%d lots=%.2f",sym,g_hY[slot],lots); } }

//===== E-Mon (指数月曜 多ショット・LONG) =====
void ManageEMonExit(){ for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
   if(!posinfo.SelectByTicket(tk)) continue; if(posinfo.Magic()!=g_mEMon) continue;
   int held=(int)(TimeCurrent()-(datetime)posinfo.Time());
   if(held>=InpHoldHours*3600){ if(trade.PositionClose(tk)&&InpVerboseLog) PrintFormat("[E-Mon TIME EXIT] %s",posinfo.Symbol()); } } }
void EntriesEMon(datetime utc){
   MqlDateTime u; TimeToStruct(utc,u); if(u.day_of_week!=1) return;
   int slot=-1; for(int h=0;h<ArraySize(g_hE);h++) if(u.hour==g_hE[h]){ slot=h; break; }
   if(slot<0) return; datetime hourBar=utc-(utc%3600); int nh=ArraySize(g_hE);
   double perShot=g_emw/(InpShotsPerWeekEMon>0?InpShotsPerWeekEMon:1);
   trade.SetExpertMagicNumber(g_mEMon);
   for(int s=0;s<ArraySize(g_emon);s++){ if(g_atrEMon[s]==INVALID_HANDLE) continue;
      int key=s*nh+slot; if(g_lastE[key]==hourBar) continue;
      string sym=g_emon[s]; double pt=PointOf(sym); if(pt<=0) continue; double atr=AtrAt(g_atrEMon[s]); if(atr<=0) continue;
      double sd=InpCatastropheATR*atr; double sp=sd/pt; if(sp<InpIdxMinStopPts){ sp=InpIdxMinStopPts; sd=sp*pt; }
      if(sp>InpIdxMaxStopPts) continue;
      double ask=SymbolInfoDouble(sym,SYMBOL_ASK), bid=SymbolInfoDouble(sym,SYMBOL_BID); if(ask<=0||bid<=0) continue;
      if((ask-bid)/pt>InpIdxMaxSpreadPts){ g_lastE[key]=hourBar; continue; }
      double lots=LotsFor(sym,sd,g_initBal*(perShot/100.0)); if(lots<InpMinLot){ g_lastE[key]=hourBar; continue; }
      int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS); double sl=NormalizeDouble(ask-sd,dg);
      g_lastE[key]=hourBar;
      if(trade.Buy(lots,sym,0.0,sl,0.0,StringFormat("EMon_%s_h%d",sym,g_hE[slot]))&&InpVerboseLog) PrintFormat("[E-Mon LONG] %s h%d lots=%.2f",sym,g_hE[slot],lots); } }

//===== v4 (日足k≥4合議・long/short) =====
int V4Signal(string sym,int rsiHandle){
   double c[]; ArraySetAsSeries(c,true); int need=MathMax(InpV4_BBwin+2,InpV4_streak+3);
   if(CopyClose(sym,PERIOD_D1,1,need+2,c)<need+1) return 0;
   double rb[1]; if(rsiHandle==INVALID_HANDLE||CopyBuffer(rsiHandle,0,1,1,rb)<1) return 0; double rsi=rb[0];
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
   return 0; }
void ManageV4Exit(){ for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
   if(!posinfo.SelectByTicket(tk)) continue; if(posinfo.Magic()!=g_mV4) continue;
   int hd=(int)((TimeCurrent()-(datetime)posinfo.Time())/86400);
   if(hd>=InpV4_MaxHoldDays){ if(trade.PositionClose(tk)&&InpVerboseLog) PrintFormat("[v4 TIME EXIT %dd] %s",hd,posinfo.Symbol()); } } }
void EntriesV4(datetime utc){
   trade.SetExpertMagicNumber(g_mV4);
   for(int i=0;i<ArraySize(g_v4);i++){ if(g_atrD1[i]==INVALID_HANDLE) continue; string sym=g_v4[i];
      datetime db=(datetime)iTime(sym,PERIOD_D1,0); if(db==0||db==g_lastV4Bar[i]) continue; g_lastV4Bar[i]=db;
      if(CountPos(sym,g_mV4)>0) continue;
      int sig=V4Signal(sym,g_rsiD1[i]); if(sig==0) continue;
      double atr=AtrAt(g_atrD1[i]); if(atr<=0) continue; double sd=InpV4_SLatr*atr, tpd=InpV4_RR*sd;
      double lots=LotsFor(sym,sd,g_initBal*(g_v4r/100.0)); if(lots<InpMinLot) continue;
      int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      if(sig>0){ double e=SymbolInfoDouble(sym,SYMBOL_ASK); double sl=NormalizeDouble(e-sd,dg), tp=NormalizeDouble(e+tpd,dg);
         if(trade.Buy(lots,sym,0.0,sl,tp,"v4_"+sym)&&InpVerboseLog) PrintFormat("[v4 LONG] %s lots=%.2f",sym,lots); }
      else { double e=SymbolInfoDouble(sym,SYMBOL_BID); double sl=NormalizeDouble(e+sd,dg), tp=NormalizeDouble(e-tpd,dg);
         if(trade.Sell(lots,sym,0.0,sl,tp,"v4_"+sym)&&InpVerboseLog) PrintFormat("[v4 SHORT] %s lots=%.2f",sym,lots); } } }

//===== E5 (多資産月次TSMOM・両建て) =====
int E5Signal(string sym){
   int need=InpLB4+2; double c[]; if(CopyClose(sym,PERIOD_MN1,0,need+1,c)<need+1) return 0;
   int n=ArraySize(c); int i1=n-2; if(i1<=InpLB4) return 0;
   int lbs[4]; lbs[0]=InpLB1; lbs[1]=InpLB2; lbs[2]=InpLB3; lbs[3]=InpLB4; double comp=0;
   for(int k=0;k<4;k++){ int j=i1-lbs[k]; if(j<0) continue; double r=c[i1]/c[j]-1.0; comp+=(r>0?1.0:(r<0?-1.0:0.0)); }
   int s=(comp>0?1:(comp<0?-1:0)); if(s<0 && !InpAllowShort) return 0; return s; }
void ManageE5(){ }
void EntriesE5(){
   trade.SetExpertMagicNumber(g_mE5);
   for(int i=0;i<ArraySize(g_e5);i++){ if(g_atrMN1[i]==INVALID_HANDLE) continue; string sym=g_e5[i];
      datetime mb=(datetime)iTime(sym,PERIOD_MN1,0); if(mb==0||mb==g_lastMonth[i]) continue; g_lastMonth[i]=mb;
      int sig=E5Signal(sym); int cur=DirOf(sym,g_mE5);
      if(sig==0){ if(cur!=0) CloseSymMagic(sym,g_mE5,"E5_FLAT"); continue; }
      if(cur==sig) continue; if(cur!=0) CloseSymMagic(sym,g_mE5,"E5_FLIP");
      double atr=AtrAt(g_atrMN1[i]); if(atr<=0) continue; double equity=AccountInfoDouble(ACCOUNT_EQUITY);
      double lots=LotsFor(sym,atr,equity*(g_e5l/100.0)); if(lots<InpMinLot) continue;
      double sd=InpCatATR_E5*atr; int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      if(sig>0){ double e=SymbolInfoDouble(sym,SYMBOL_ASK); double sl=NormalizeDouble(e-sd,dg);
         if(trade.Buy(lots,sym,0.0,sl,0.0,"E5_"+sym)&&InpVerboseLog) PrintFormat("[E5 LONG] %s lots=%.2f",sym,lots); }
      else { double e=SymbolInfoDouble(sym,SYMBOL_BID); double sl=NormalizeDouble(e+sd,dg);
         if(trade.Sell(lots,sym,0.0,sl,0.0,"E5_"+sym)&&InpVerboseLog) PrintFormat("[E5 SHORT] %s lots=%.2f",sym,lots); } } }
//+------------------------------------------------------------------+
//| 残存リスク(誠実な記録):                                          |
//|  ・FN=同一口座内ヘッジOKゆえ4戦略同居可(v7円LONG×v4円SHORT,       |
//|    E-Mon指数LONG×E5指数SHORT が同時発生してもFNでは可)。FTMO/     |
//|    Blueberryでは不可=Chien_FTMO_Compliant版(v4+E-Mon)を使う。     |
//|  ・サイズ既定はP★35:25:25:15の各サイズ近似(docs/65)=出発点。      |
//|    FAST4は中央~4ヶ月狙い(p95年DD~-12%)。必ずデモで実maxDD/日次-5% |
//|    抵触を確認し調整。審査突破後はProfitStop=false+中庸へ減サイズ。 |
//|  ・v4=ADOPT/v7・E-Mon・E5=未確証=本資金前デモ前進検証必須(docs/29)|
//|  ・FN一貫性ルール:審査と本番で同じEA/戦略を維持。最大割当$400kは別途|
//|  ・1チャートに本EA1つだけ(Magic衝突回避)。ネッティング口座は両建て |
//|    不可ゆえv4/E5/v7/E-Monの逆方向が相殺される点に注意(ヘッジ口座推奨)|
//+------------------------------------------------------------------+
