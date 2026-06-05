//+------------------------------------------------------------------+
//|                    Chien_Portfolio4_Optimized.mq5                 |
//|   最適化済み3戦略ポートフォリオEA: v7(円月曜)+v4(日足k≥4合議)      |
//|   +E5(多資産トレンド)。比率を docs/49 のスイープ最適で確定。       |
//|                                                                   |
//|   ■ docs/49 の確定: 3戦略比率(v7:v4:E5)を Sharpeアンカー＋実形状で  |
//|     スイープ最適化。手置きの 40:40:20 は既にフロンティア上、       |
//|     最適点は【40:35:25(Calmar最大)】。3戦は無相関分散で v7単体比   |
//|     Calmar ほぼ倍(0.39→0.77)。差は誤差内ゆえ比率に頑健。           |
//|                                                                   |
//|   ■ 目的別プリセット(InpObjective・E5≤25%ガード内蔵):              |
//|     CALMAR  = 40:35:25 ★推奨(Calmar最大, docs/49)                  |
//|     CAGR    = 45:35:20 (CAGR最大・やや攻め)                        |
//|     DEFENSE = 45:40:15 (E5を絞りモデルリスク最小)                  |
//|     BASELINE= 40:40:20 (旧Chien_Portfolio3・参照/移行用)           |
//|     MANUAL  = 下の Weekly/V4/E5 手動値                             |
//|   ■ ルール別(InpRuleMode):                                         |
//|     INSTANT = −10%トレーリング/無目標 (Blueberry等)                |
//|     PROP    = 静的−10%/+8%目標/日次−4% (FN/FTMO 2-step)            |
//|                                                                   |
//|   ■ 内部3戦略(Magic分離で混線なし):                                 |
//|     v7: 円3クロス 月曜04/06/08/10UTC LONG・24h時間決済(SL=2.5ATR_H1)|
//|     v4: 9ペア 日足 4条件合議k≥4 で両建て・SL1.5ATR_D1/RR1.2/8日決済  |
//|     E5: 金+指数 月初TSMOM両建て・逆ボラ加重(legRisk)/SL2.5ATR_MN1   |
//|     口座ガード: 総合−10%枠の内側(既定−8%)で全停止。                |
//|                                                                   |
//|   ★1チャートに本EAを1つだけドロップ(どの銘柄/足でも可)。残高は自動。|
//|     銘柄名は業者仕様に合わせ InpYen/ InpV4/ InpE5 Symbols を編集。   |
//|   ⚠ v4=ADOPT/E5=STRONG-LEAD(未確証)。本資金前にデモ(docs/29)必須。  |
//|     比率は最適化済みだが**絶対サイズ(倍率)は Drive10年＋デモで確定**|
//|     (docs/49 §4)。−10%ガードが最終backstop。                       |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "4.00"
#property strict
#property description "Optimized 3-strategy portfolio (docs/49): v7+v4+E5 swept-optimal ratio. Default CALMAR 40:35:25. Objective x Rule presets, E5<=25% guard. E5=LEAD/demo."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

enum ENUM_PORT4_OBJECTIVE
{
   OBJ_CALMAR   = 0, // 40:35:25 Calmar最大(推奨, docs/49)
   OBJ_CAGR     = 1, // 45:35:20 CAGR最大(やや攻め)
   OBJ_DEFENSE  = 2, // 45:40:15 E5守り(モデルリスク最小)
   OBJ_BASELINE = 3, // 40:40:20 旧Portfolio3(参照/移行)
   OBJ_MANUAL   = 4  // 手動(下のWeekly/V4/E5値)
};
enum ENUM_PORT4_RULE
{
   RULE_INSTANT = 0, // インスタント: -10%トレーリング/無目標(Blueberry等)
   RULE_PROP    = 1  // プロップ突破: 静的-10%/+8%目標/日次-4%(FN/FTMO)
};

input group "=== 最適化プリセット（これ2つで比率/サイズ/ルール自動）==="
input ENUM_PORT4_OBJECTIVE InpObjective = OBJ_CALMAR;    // ★既定=Calmar最大 40:35:25(docs/49)
input ENUM_PORT4_RULE       InpRuleMode  = RULE_INSTANT; // 口座ルール(INSTANT/PROP)
input bool   InpAcknowledgeLEAD = true;   // v4=ADOPT/E5=LEAD。デモ/極小で承認=true

input group "=== 銘柄（業者の実銘柄名に合わせる）==="
input string InpYenSymbols = "EURJPY,GBPJPY,USDJPY";                          // v7: 円3クロス
input string InpV4Symbols  = "EURUSD,GBPUSD,USDJPY,AUDUSD,USDCHF,USDCAD,NZDUSD,EURJPY,GBPJPY"; // v4: 9ペア
input string InpE5Symbols  = "XAUUSD,US500,NAS100,GER40";                     // E5: 金+株価指数

input group "=== 口座/ガード ==="
input double InpInitialBalance   = 0.0;   // 0=口座残高を自動取得
input double InpMaxLossLimitPct  = 10.0;  // 失格ライン%
input double InpAccountFloorDDPct= 8.0;   // 総合 -8% で全停止(-10%の内側)

input group "=== 手動値（OBJ_MANUAL時のみ・3戦略の配分）==="
input double InpWeeklyRiskPct   = 0.60;   // v7 週次リスク%
input double InpV4RiskPerTradePct= 0.13;  // v4 1トレードあたりリスク%(40:35:25近似)
input double InpE5LegRiskPct    = 0.375;  // E5 legRisk%(40:35:25近似)

input group "=== v7 設定 ==="
input string InpEntryHoursUTC = "4,6,8,10";
input int    InpShotsPerWeek  = 12;
input int    InpHoldHours     = 24;
input int    InpAtrPeriodH1   = 24;
input double InpCatastropheATR= 2.5;
input double InpMinStopPips   = 10.0;
input double InpMaxStopPips   = 400.0;
input double InpMaxSpreadPips = 3.0;

input group "=== v4 設定（日足k≥4合議）==="
input int    InpV4_RSI       = 14;
input double InpV4_RSIlo     = 35.0;
input double InpV4_RSIhi     = 65.0;
input int    InpV4_BBwin     = 20;
input double InpV4_BBz       = 1.5;
input int    InpV4_streak    = 3;
input double InpV4_dayMovePct= 0.5;       // 当日±0.5%
input int    InpV4_ATR       = 14;        // ATR(D1)
input double InpV4_SLatr     = 1.5;       // SL=1.5*ATR(D1)
input double InpV4_RR        = 1.2;       // TP=RR*SL
input int    InpV4_MaxHoldDays= 8;

input group "=== E5 設定 ==="
input int    InpLB1=1, InpLB2=3, InpLB3=6, InpLB4=12;
input bool   InpAllowShort = true;
input int    InpAtrPeriodMN1= 6;
input double InpCatATR_E5  = 2.5;

input group "=== 共通 ==="
input double InpMinLot = 0.01;
input double InpMaxLot = 50.0;
input long   InpMagicBase = 940710;       // v7=+1 / v4=+2 / E5=+3
input int    InpSlippagePoints = 30;
input bool   InpVerboseLog = true;

//==================================================================
CTrade        trade;
CPositionInfo posinfo;

string   g_yen[]; string g_v4[]; string g_e5[]; int g_hours[];
int      g_atrH1[]; int g_atrD1[]; int g_rsiD1[]; int g_atrMN1[];
datetime g_lastShot[];     // [yenIdx*nHours + hourIdx]
datetime g_lastV4Bar[];    // [v4Idx]
datetime g_lastMonth[];    // [e5Idx]
double   g_initBal=0.0, g_weeklyRisk=0.6, g_v4risk=0.15, g_e5leg=0.30, g_maxLossPct=10.0;
bool     g_useTrailing=true, g_useProfitStop=false, g_useDailyStop=false;
double   g_profitPct=0.0, g_dailyStopPct=0.0, g_floorBufPct=2.0;
double   g_peakEquity=0.0, g_trailFloor=0.0, g_dayStartEq=0.0;
datetime g_curDay=0; bool g_halted=false, g_dayBlocked=false;
string   g_scenName="";
string   g_objName="";
long     g_mV7=0, g_mV4=0, g_mE5=0;

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

string ResolveSymbol(string want)
{
   string suf[]={"",".cash",".r",".c",".pro","m",".spot","-cash",".sd","+",".i","_SB"};
   string bases[]; ArrayResize(bases,20); int nb=0;
   bases[nb++]=want;
   string U=want; StringToUpper(U);
   if(StringFind(U,"XAU")>=0 || StringFind(U,"GOLD")>=0){
      bases[nb++]="XAUUSD"; bases[nb++]="GOLD"; bases[nb++]="GOLDUSD"; }
   else if(StringFind(U,"SPX")>=0 || StringFind(U,"500")>=0){
      bases[nb++]="US500"; bases[nb++]="SPX500"; bases[nb++]="SP500"; bases[nb++]="USA500"; bases[nb++]="US500Cash"; }
   else if(StringFind(U,"NAS")>=0 || StringFind(U,"USTEC")>=0 || StringFind(U,"NDX")>=0 || StringFind(U,"US100")>=0 || StringFind(U,"TECH")>=0){
      bases[nb++]="NAS100"; bases[nb++]="USTEC"; bases[nb++]="US100"; bases[nb++]="NDX100"; bases[nb++]="USTECH"; }
   else if(StringFind(U,"GER")>=0 || StringFind(U,"DAX")>=0 || StringFind(U,"DE40")>=0 || StringFind(U,"DE30")>=0){
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
   // (1) 目的別リスク配分(share v7:v4:E5・docs/49 スイープ最適。E5≤25%ガード内)
   double sh7=40, sh4=35, sh5=25;
   switch(InpObjective){
      case OBJ_CAGR:     sh7=45; sh4=35; sh5=20; g_objName="CAGR 45:35:20";     break;
      case OBJ_DEFENSE:  sh7=45; sh4=40; sh5=15; g_objName="DEFENSE 45:40:15";  break;
      case OBJ_BASELINE: sh7=40; sh4=40; sh5=20; g_objName="BASELINE 40:40:20"; break;
      case OBJ_MANUAL:   sh7=0;  sh4=0;  sh5=0;  g_objName="MANUAL";            break;
      default:           sh7=40; sh4=35; sh5=25; g_objName="CALMAR 40:35:25";   break; // ★推奨
   }
   // (2) ルール別 1シェアあたり予算(=サイズ基準)。docs/45 の実値にアンカー:
   //   INSTANT 40:40:20 ↔ v7 0.60 / v4 0.15 / E5 0.30  → perShare .01500 / .003750 / .01500
   //   PROP    40:40:20 ↔ v7 1.00 / v4 0.25 / E5 0.50  → perShare .02500 / .006250 / .02500
   double pv7, pv4, pv5;
   if(InpRuleMode==RULE_PROP){ pv7=0.025000; pv4=0.0062500; pv5=0.025000; }
   else                      { pv7=0.015000; pv4=0.0037500; pv5=0.015000; }
   if(InpObjective==OBJ_MANUAL){
      g_weeklyRisk=InpWeeklyRiskPct; g_v4risk=InpV4RiskPerTradePct; g_e5leg=InpE5LegRiskPct;
      // 手動でも E5≤25%ガード: E5シェアが v7+v4+E5 の25%超なら警告
      double tot=InpWeeklyRiskPct+InpV4RiskPerTradePct+InpE5LegRiskPct;
      if(tot>0 && InpE5LegRiskPct/tot>0.25) Print("[WARN] E5予算がガード(25%)超過。E5=未検証ゆえ縮小推奨(docs/49)。");
   } else {
      g_weeklyRisk=sh7*pv7; g_v4risk=sh4*pv4; g_e5leg=sh5*pv5;
   }
   // (3) ルール: INSTANT=トレーリング/無目標, PROP=静的-10%/+8%目標/日次-4%
   g_maxLossPct=InpMaxLossLimitPct; g_floorBufPct=2.0;
   if(InpRuleMode==RULE_PROP){
      g_scenName="PROP"; g_useTrailing=false;
      g_useProfitStop=true;  g_profitPct=8.0;
      g_useDailyStop=true;   g_dailyStopPct=4.0;
   } else {
      g_scenName="INSTANT"; g_useTrailing=true;
      g_useProfitStop=false; g_profitPct=0;
      g_useDailyStop=false;  g_dailyStopPct=0;
   }
}

int OnInit()
{
   if(!InpAcknowledgeLEAD){ Print("[STOP] v4=ADOPT/E5=LEAD。InpAcknowledgeLEAD=trueで承認(デモ/極小)。"); return INIT_FAILED; }
   int ny=SplitCSV(InpYenSymbols,g_yen);
   int nv=SplitCSV(InpV4Symbols,g_v4);
   int ne=SplitCSV(InpE5Symbols,g_e5);
   int nh=SplitHours(InpEntryHoursUTC,g_hours);
   if(ny==0||nv==0||ne==0||nh==0){ Print("シンボル/時刻のパース失敗"); return INIT_FAILED; }
   ResolveScenario();
   g_mV7=InpMagicBase+1; g_mV4=InpMagicBase+2; g_mE5=InpMagicBase+3;
   g_initBal=(InpInitialBalance>0.0)?InpInitialBalance:AccountInfoDouble(ACCOUNT_BALANCE);
   if(g_initBal<=0.0) g_initBal=AccountInfoDouble(ACCOUNT_EQUITY);

   ArrayResize(g_atrH1,ny); ArrayResize(g_atrD1,nv); ArrayResize(g_rsiD1,nv); ArrayResize(g_atrMN1,ne);
   ArrayResize(g_lastShot,ny*nh); ArrayInitialize(g_lastShot,0);
   ArrayResize(g_lastV4Bar,nv); ArrayInitialize(g_lastV4Bar,0);
   ArrayResize(g_lastMonth,ne); ArrayInitialize(g_lastMonth,0);

   for(int i=0;i<ny;i++){
      string r=ResolveSymbol(g_yen[i]); g_atrH1[i]=INVALID_HANDLE;
      if(r==""){ PrintFormat("⚠ v7銘柄 %s 見つからず→スキップ",g_yen[i]); continue; }
      if(r!=g_yen[i]) PrintFormat("[銘柄解決] v7 %s → %s",g_yen[i],r);
      g_yen[i]=r; g_atrH1[i]=iATR(g_yen[i],PERIOD_H1,InpAtrPeriodH1);
   }
   for(int i=0;i<nv;i++){
      string r=ResolveSymbol(g_v4[i]); g_atrD1[i]=INVALID_HANDLE; g_rsiD1[i]=INVALID_HANDLE;
      if(r==""){ PrintFormat("⚠ v4銘柄 %s 見つからず→スキップ",g_v4[i]); continue; }
      if(r!=g_v4[i]) PrintFormat("[銘柄解決] v4 %s → %s",g_v4[i],r);
      g_v4[i]=r;
      g_atrD1[i]=iATR(g_v4[i],PERIOD_D1,InpV4_ATR);
      g_rsiD1[i]=iRSI(g_v4[i],PERIOD_D1,InpV4_RSI,PRICE_CLOSE);
   }
   for(int i=0;i<ne;i++){
      string r=ResolveSymbol(g_e5[i]); g_atrMN1[i]=INVALID_HANDLE;
      if(r==""){ PrintFormat("⚠ E5銘柄 %s 見つからず→スキップ",g_e5[i]); continue; }
      if(r!=g_e5[i]) PrintFormat("[銘柄解決] E5 %s → %s",g_e5[i],r);
      g_e5[i]=r; g_atrMN1[i]=iATR(g_e5[i],PERIOD_MN1,InpAtrPeriodMN1);
   }
   trade.SetDeviationInPoints(InpSlippagePoints);
   g_peakEquity=g_initBal; g_trailFloor=g_initBal*(1.0-g_maxLossPct/100.0);
   ResetDay(TimeCurrent());
   PrintFormat("[INIT P4 obj=%s rule=%s] initBal=%.0f v7週次=%.3f%% v4/trade=%.3f%% E5leg=%.3f%% trailing=%s profit=%s(%.0f) daily=%s",
      g_objName,g_scenName,g_initBal,g_weeklyRisk,g_v4risk,g_e5leg,(g_useTrailing?"Y":"N"),
      (g_useProfitStop?"Y":"N"),g_profitPct,(g_useDailyStop?"Y":"N"));
   if(InpVerboseLog) Print("[NOTE] 最適化比率=",g_objName,"(docs/49)。1チャートに本EA1つだけ。Magic分離(",g_mV7,"/",g_mV4,"/",g_mE5,")。v4=ADOPT/E5=LEAD=デモ前提。");
   EventSetTimer(30);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){
   EventKillTimer();
   for(int i=0;i<ArraySize(g_atrH1);i++) if(g_atrH1[i]!=INVALID_HANDLE) IndicatorRelease(g_atrH1[i]);
   for(int i=0;i<ArraySize(g_atrD1);i++) if(g_atrD1[i]!=INVALID_HANDLE) IndicatorRelease(g_atrD1[i]);
   for(int i=0;i<ArraySize(g_rsiD1);i++) if(g_rsiD1[i]!=INVALID_HANDLE) IndicatorRelease(g_rsiD1[i]);
   for(int i=0;i<ArraySize(g_atrMN1);i++) if(g_atrMN1[i]!=INVALID_HANDLE) IndicatorRelease(g_atrMN1[i]);
}

datetime DayStart(datetime t){ MqlDateTime s; TimeToStruct(t,s); s.hour=0;s.min=0;s.sec=0; return StructToTime(s); }
void ResetDay(datetime t){ g_curDay=DayStart(t); g_dayStartEq=AccountInfoDouble(ACCOUNT_EQUITY); g_dayBlocked=false; }
bool IsYen(string s){ for(int i=0;i<ArraySize(g_yen);i++) if(g_yen[i]==s) return true; return false; }
double AtrAt(int handle){ double a[1]; if(handle==INVALID_HANDLE||CopyBuffer(handle,0,1,1,a)<1) return 0.0; return a[0]; }

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

// 指定magic×symbolの建玉数
int CountPos(string sym, long magic){
   int n=0;
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Symbol()==sym && posinfo.Magic()==magic) n++; }
   return n;
}
int DirOf(string sym, long magic){
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Symbol()==sym && posinfo.Magic()==magic)
         return (posinfo.PositionType()==POSITION_TYPE_BUY?1:-1); }
   return 0;
}
void CloseSymMagic(string sym, long magic, string why){
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Symbol()==sym && posinfo.Magic()==magic){
         if(trade.PositionClose(tk) && InpVerboseLog) PrintFormat("[CLOSE %s] %s",why,sym); } }
}
bool IsMine(long m){ return (m==g_mV7||m==g_mV4||m==g_mE5); }
void CloseAllMine(string why){
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(IsMine(posinfo.Magic())) trade.PositionClose(tk); }
   if(InpVerboseLog) PrintFormat("[CLOSE ALL %s]",why);
}

//==================================================================
void OnTimer()
{
   datetime now=TimeCurrent(); datetime utc=TimeGMT();
   if(DayStart(now)!=g_curDay) ResetDay(now);
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);

   double floor=BreachFloor(equity);
   double guard=floor+g_initBal*g_floorBufPct/100.0;
   if(equity<=guard && !g_halted){ g_halted=true; CloseAllMine("EQUITY_FLOOR");
      PrintFormat("[HALT] equity %.2f <= guard %.2f",equity,guard); }
   if(g_halted){ CloseAllMine("HALTED"); return; }

   if(g_useDailyStop){
      double dpnl=equity-g_dayStartEq;
      if(dpnl<=-g_initBal*g_dailyStopPct/100.0 && !g_dayBlocked){ g_dayBlocked=true;
         PrintFormat("[DAILY STOP] %.2f",dpnl); }
   }

   ManageV7Exit();
   ManageV4Exit();
   ManageE5();

   bool blockNew = (g_useProfitStop && equity>=g_initBal*(1.0+g_profitPct/100.0)) || g_dayBlocked;
   if(blockNew) return;

   EntriesV7(utc);
   EntriesV4();
   EntriesE5();
}

//===== v7 =====
void ManageV7Exit()
{
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()!=g_mV7) continue;
      int held=(int)(TimeCurrent()-(datetime)posinfo.Time());
      if(held>=InpHoldHours*3600){ if(trade.PositionClose(tk)&&InpVerboseLog)
         PrintFormat("[v7 TIME EXIT] %s",posinfo.Symbol()); }
   }
}
void EntriesV7(datetime utc)
{
   MqlDateTime u; TimeToStruct(utc,u);
   if(u.day_of_week!=1) return;
   int slot=-1; for(int h=0;h<ArraySize(g_hours);h++) if(u.hour==g_hours[h]){ slot=h; break; }
   if(slot<0) return;
   datetime hourBar=utc-(utc%3600); int nh=ArraySize(g_hours);
   double perShot=g_weeklyRisk/(InpShotsPerWeek>0?InpShotsPerWeek:1);
   trade.SetExpertMagicNumber(g_mV7);
   for(int s=0;s<ArraySize(g_yen);s++){
      if(g_atrH1[s]==INVALID_HANDLE) continue;
      int key=s*nh+slot;
      if(g_lastShot[key]==hourBar) continue;
      string sym=g_yen[s]; double pip=PipOf(sym);
      double atr=AtrAt(g_atrH1[s]); if(atr<=0) continue;
      double sd=InpCatastropheATR*atr; double sp=sd/pip;
      if(sp<InpMinStopPips){ sp=InpMinStopPips; sd=sp*pip; }
      if(sp>InpMaxStopPips) continue;
      double ask=SymbolInfoDouble(sym,SYMBOL_ASK), bid=SymbolInfoDouble(sym,SYMBOL_BID);
      if(ask<=0||bid<=0) continue;
      if((ask-bid)/pip>InpMaxSpreadPips){ g_lastShot[key]=hourBar; continue; }
      double riskMoney=g_initBal*(perShot/100.0);
      double lots=LotsFor(sym,sd,riskMoney); if(lots<InpMinLot){ g_lastShot[key]=hourBar; continue; }
      int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      double sl=NormalizeDouble(ask-sd,dg);
      g_lastShot[key]=hourBar;
      if(trade.Buy(lots,sym,0.0,sl,0.0,StringFormat("v7_%s_h%d",sym,g_hours[slot])))
         { if(InpVerboseLog) PrintFormat("[v7 ENTRY] LONG %s h%dUTC lots=%.2f SL=%.5f",sym,g_hours[slot],lots,sl); }
   }
}

//===== v4 (日足k≥4合議) =====
// 直近確定日足(shift1)で4条件を集計。買い/売り票がそれぞれ4(=全条件)で建て。
int V4Signal(string sym, int rsiHandle, double &atrOut)
{
   atrOut=0.0;
   double c[]; ArraySetAsSeries(c,true);
   int need=MathMax(InpV4_BBwin+2, InpV4_streak+3);
   if(CopyClose(sym,PERIOD_D1,1,need+2,c)<need+1) return 0;   // c[0]=直近確定足
   double rb[1];
   if(rsiHandle==INVALID_HANDLE || CopyBuffer(rsiHandle,0,1,1,rb)<1) return 0;
   double rsi=rb[0];
   // BB z: 直近足c[0]を、その前BBwin本(c[1..BBwin])で標準化
   double mean=0; for(int k=1;k<=InpV4_BBwin;k++) mean+=c[k]; mean/=InpV4_BBwin;
   double var=0; for(int k=1;k<=InpV4_BBwin;k++) var+=(c[k]-mean)*(c[k]-mean); var/=(InpV4_BBwin-1);
   double sd=MathSqrt(var); double z=(sd>0)?(c[0]-mean)/sd:0.0;
   // 連続日数
   int down=0; for(int k=0;k<12;k++){ if(c[k]<c[k+1]) down++; else break; }
   int up=0;   for(int k=0;k<12;k++){ if(c[k]>c[k+1]) up++;   else break; }
   // 当日リターン
   double ret=(c[1]!=0)?(c[0]-c[1])/c[1]:0.0; double mv=InpV4_dayMovePct/100.0;
   int buy = (rsi<InpV4_RSIlo?1:0)+(z<-InpV4_BBz?1:0)+(down>=InpV4_streak?1:0)+(ret<-mv?1:0);
   int sell= (rsi>InpV4_RSIhi?1:0)+(z> InpV4_BBz?1:0)+(up  >=InpV4_streak?1:0)+(ret> mv?1:0);
   if(buy>=4 && buy>sell) return 1;
   if(sell>=4 && sell>buy && InpAllowShort) return -1;
   return 0;
}
void ManageV4Exit()
{
   // SL/TPは建玉に付帯。ここは時間切れ(8日)の保険のみ。
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()!=g_mV4) continue;
      int heldDays=(int)((TimeCurrent()-(datetime)posinfo.Time())/86400);
      if(heldDays>=InpV4_MaxHoldDays){ if(trade.PositionClose(tk)&&InpVerboseLog)
         PrintFormat("[v4 TIME EXIT %dd] %s",heldDays,posinfo.Symbol()); }
   }
}
void EntriesV4()
{
   trade.SetExpertMagicNumber(g_mV4);
   for(int i=0;i<ArraySize(g_v4);i++){
      if(g_atrD1[i]==INVALID_HANDLE) continue;
      string sym=g_v4[i];
      datetime db=(datetime)iTime(sym,PERIOD_D1,0);
      if(db==0 || db==g_lastV4Bar[i]) continue;   // 当日足は評価済み(1日1回)
      g_lastV4Bar[i]=db;
      if(CountPos(sym,g_mV4)>0) continue;          // 既存v4建玉があれば積まない
      double dummy; int sig=V4Signal(sym,g_rsiD1[i],dummy);
      if(sig==0) continue;
      double atr=AtrAt(g_atrD1[i]); if(atr<=0) continue;
      double sd=InpV4_SLatr*atr; double tpd=InpV4_RR*sd;
      double riskMoney=g_initBal*(g_v4risk/100.0);
      double lots=LotsFor(sym,sd,riskMoney); if(lots<InpMinLot) continue;
      int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      if(sig>0){ double e=SymbolInfoDouble(sym,SYMBOL_ASK);
         double sl=NormalizeDouble(e-sd,dg), tp=NormalizeDouble(e+tpd,dg);
         if(trade.Buy(lots,sym,0.0,sl,tp,"v4_"+sym) && InpVerboseLog) PrintFormat("[v4 ENTRY] LONG %s lots=%.2f SL=%.5f TP=%.5f",sym,lots,sl,tp); }
      else     { double e=SymbolInfoDouble(sym,SYMBOL_BID);
         double sl=NormalizeDouble(e+sd,dg), tp=NormalizeDouble(e-tpd,dg);
         if(trade.Sell(lots,sym,0.0,sl,tp,"v4_"+sym) && InpVerboseLog) PrintFormat("[v4 ENTRY] SHORT %s lots=%.2f SL=%.5f TP=%.5f",sym,lots,sl,tp); }
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
void ManageE5(){ /* E5の新規/反転は EntriesE5 で処理(月初)。SLは建玉付帯 */ }
void EntriesE5()
{
   trade.SetExpertMagicNumber(g_mE5);
   for(int i=0;i<ArraySize(g_e5);i++){
      if(g_atrMN1[i]==INVALID_HANDLE) continue;
      string sym=g_e5[i];
      datetime mb=(datetime)iTime(sym,PERIOD_MN1,0);
      if(mb==0 || mb==g_lastMonth[i]) continue;
      g_lastMonth[i]=mb;
      int sig=E5Signal(sym); int cur=DirOf(sym,g_mE5);
      if(sig==0){ if(cur!=0) CloseSymMagic(sym,g_mE5,"E5_FLAT"); continue; }
      if(cur==sig) continue;
      if(cur!=0) CloseSymMagic(sym,g_mE5,"E5_FLIP");
      double atr=AtrAt(g_atrMN1[i]); if(atr<=0) continue;
      double equity=AccountInfoDouble(ACCOUNT_EQUITY);
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
//|  ・v4=ADOPT(実10年Dukascopy 6/6, docs/42)だが本資金前デモ必須。   |
//|    E5=STRONG-LEAD(未検証, docs/31)。E5≤25%ガードを維持(docs/49)。 |
//|  ・比率は docs/49 のスイープ最適(既定CALMAR 40:35:25)。ただし     |
//|    **絶対サイズ(倍率)は近似値**=docs/45のINSTANT/PROP実値に        |
//|    シェア按分でアンカーした出発点。正確な倍率は                    |
//|    colab_optimize_portfolio3_10y(Drive10年)＋デモ実DDで確定。     |
//|  ・3戦略はMagic分離(base+1/+2/+3)。v4とv7は円クロスを共有するが   |
//|    Magicで別管理(ヘッジ口座では両建て併存・ネッティング口座では相殺)|
//|  ・指数/金CFDの実スプレッド/スワップ/配当は未計上=デモで確認。   |
//|  ・1チャートに本EAは1つだけ(複数/他EAと同口座でMagic衝突回避)。   |
//|  ・ニュースフィルタは本オールイン版では省略。                    |
//+------------------------------------------------------------------+
