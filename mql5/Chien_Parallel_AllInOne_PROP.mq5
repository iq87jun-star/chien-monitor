//+------------------------------------------------------------------+
//|                    Chien_Parallel_AllInOne_PROP.mq5              |
//|   並行ポートフォリオ・オールインワン(プロップ既定):               |
//|   E-Mon(株価指数 月曜LONG) + E5(多資産トレンド) を1チャート挿入。  |
//|                                                                   |
//|   ■ なぜ"並行"か(docs/50-51): ユーザー要望「既存(v7主軸)とは別に、 |
//|     同じレベルの検証を通った並行ポートフォリオ」。新エッジ一括探索  |
//|     (research/parallel_edge_hunt_10y.py, N=130/Bonferroni)で唯一   |
//|     生き残った無相関の新エッジ=【株価指数の月曜効果 E-Mon】。       |
//|     E-Mon は v7基準9ゲートを 7/9 通過(=v7と同じ STRONG-LEAD):       |
//|       G4プラセボ:月曜のみ有意(火-金 非有意) / G6 IS+OOS両方+ /      |
//|       G7 WF 5/5+ / G8 コスト2×でも+ / G9 −10%枠適合。落ちるのは     |
//|       G3(Bonferroni, v7も同じ)とG5(2020年のみ僅差0.125)。          |
//|     ★肝=E-Mon ⇄ v7(円月曜)の月次相関 +0.22(低)・E-Mon ⇄ E5 −0.06。 |
//|       ∴既存v7口座と"同時にDDしない"=別口座/別業者で並走する価値。  |
//|                                                                   |
//|   ■ 本ファイル=プロップ既定 ★最速攻め3.0x(FundedNext/FTMO等2-step): |
//|     E-Mon週次 3.00% / E5 legRisk 1.50%・静的−10%/+8%停止/日次−4%。   |
//|     全停止フロア=−9%(枠を使い切る攻め)。気長確実は PORT_MANUAL 1.5x  |
//|     (E-Mon1.50/E5 0.75)。資金化後の守りは 1.0x(1.00/0.50)。         |
//|     ⚠ 攻め倍率はmaxDDが−10%枠に接近→−9%フロアが頻繁作動の想定。     |
//|       業者破綻/規約変更リスク前提で速く突破・資金化後も早期出金。   |
//|     (インスタント運用は Chien_Parallel_AllInOne_INSTANT.mq5 を使う) |
//|                                                                   |
//|   ■ 内部2戦略(Magic分離で混線なし):                                |
//|     E-Mon: 指数3つ(NAS100/US500/GER40) 月曜 09/14UTC LONG・24h時間   |
//|            決済(SL=2.5ATR_H1保険)。v7と同じ多ショット・リスク予算化。 |
//|     E5: 金+指数 月初TSMOM両建て・逆ボラ加重(legRisk)/SL2.5ATR_MN1。  |
//|     口座ガード: 総合−10%枠の内側(既定−9%)で全停止。                |
//|                                                                   |
//|   ★1チャートに本EAを1つだけドロップ(どの銘柄/足でも可)。残高は自動。|
//|     銘柄名は業者仕様に合わせ InpEMonSymbols / InpE5Symbols を編集。  |
//|   ⚠ E-Mon=STRONG-LEAD / E5=STRONG-LEAD(共に未確証)。本資金前にデモ  |
//|     前進検証(docs/29)必須。サイズ既定は保守的な出発点。−10%が最終   |
//|     backstop。指数CFDの実スプレッド/スワップ/配当は要デモ実測。     |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.00"
#property strict
#property description "Parallel portfolio all-in-one (PROP default): E-Mon(equity-index Monday LONG)+E5(multi-asset trend). Per-strategy magics. Both STRONG-LEAD=demo first."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

enum ENUM_PARA_SCENARIO
{
   PARA_INSTANT            = 0, // インスタント(守り寄り: トレーリング / 無目標)
   PARA_PROP_BREAKTHROUGH  = 1, // プロップ突破(静的-10% / +8%目標 / 日次-4%)
   PARA_MANUAL             = 2  // 手動(下の EMon/E5 値・静的-10%)
};

input group "=== シナリオ（これ1つで倍率/比率/ルール自動）==="
input ENUM_PARA_SCENARIO InpScenario = PARA_PROP_BREAKTHROUGH; // ★本ファイル既定=プロップ突破
input bool   InpAcknowledgeLEAD = true;   // E-Mon/E5=STRONG-LEAD。デモ/極小で承認=true

input group "=== 銘柄（業者の実銘柄名に合わせる）==="
input string InpEMonSymbols = "NAS100,US500,GER40";          // E-Mon: 株価指数3つ(月曜LONG)
input string InpE5Symbols   = "XAUUSD,US500,NAS100,GER40";   // E5: 金+株価指数

input group "=== 口座/ガード ==="
input double InpInitialBalance   = 0.0;   // 0=口座残高を自動取得
input double InpMaxLossLimitPct  = 10.0;  // 失格ライン%
input double InpAccountFloorDDPct= 9.0;   // 全停止ライン%(★攻め=9.0で-10%枠をほぼ使い切る/守りは8.0)

input group "=== 手動値（PORT_MANUAL時のみ・2戦略の配分）==="
input double InpEMonWeeklyPct   = 3.00;   // E-Mon 週次リスク%（PROP 3.0x攻め既定と同値）
input double InpE5LegRiskPct    = 1.50;   // E5 legRisk%(各レッグ月次σ)。P-A/D/C重畳時は0=E-Monのみ
input double InpManualProfitStopPct = 0.0; // PARA_MANUAL: +この%で新規停止(0=無効)。重畳脚は主EA側に任せ0が既定
input double InpManualDailyStopPct  = 4.0; // PARA_MANUAL: 日次−この%で当日全決済(0=無効)。規約−5%手前

input group "=== E-Mon 設定（株価指数 月曜LONG）==="
input int    InpEntryWeekday  = 1;        // 1=月曜(MQL: 0=日..6=土)
input string InpEntryHoursUTC = "9,14";   // 月曜の建て時刻(欧州/米セッションを2点サンプリング)
input int    InpShotsPerWeek  = 6;        // 指数3×時刻2=6ショット。週次予算をこれで割る
input int    InpHoldHours     = 24;       // 各ショット24h保有→時間決済
input int    InpAtrPeriodH1   = 24;       // H1×24≒日次ATR
input double InpCatastropheATR= 2.5;      // SL=2.5×ATR(災害用・広く置く)
input double InpMinStopPts    = 50.0;     // 指数の最小SL(ポイント)
input double InpMaxStopPts    = 200000.0; // 指数の最大SL(ポイント・大きめ許容)
input double InpMaxSpreadPts  = 1500.0;   // 指数スプレッド上限(ポイント)

input group "=== E5 設定（多資産月次TSMOM）==="
input int    InpLB1=1, InpLB2=3, InpLB3=6, InpLB4=12;
input bool   InpAllowShort = true;
input int    InpAtrPeriodMN1= 6;
input double InpCatATR_E5  = 2.5;

input group "=== 共通 ==="
input double InpMinLot = 0.01;
input double InpMaxLot = 50.0;
input long   InpMagicBase = 950720;       // E-Mon=+1 / E5=+2
input int    InpSlippagePoints = 30;
input bool   InpVerboseLog = true;

//==================================================================
CTrade        trade;
CPositionInfo posinfo;

string   g_emon[]; string g_e5[]; int g_hours[];
int      g_atrH1[]; int g_atrMN1[];
datetime g_lastShot[];     // [emonIdx*nHours + hourIdx]
datetime g_lastMonth[];    // [e5Idx]
double   g_initBal=0.0, g_emonWeekly=0.6, g_e5leg=0.30, g_maxLossPct=10.0;
bool     g_useTrailing=true, g_useProfitStop=false, g_useDailyStop=false;
double   g_profitPct=0.0, g_dailyStopPct=0.0, g_floorBufPct=1.0;
double   g_peakEquity=0.0, g_trailFloor=0.0, g_dayStartEq=0.0;
datetime g_curDay=0; bool g_halted=false, g_dayBlocked=false;
string   g_scenName="";
long     g_mEMon=0, g_mE5=0;

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

string ResolveSymbol(string want)
{
   string suf[]={"",".pi",".raw",".ecn",".stp",".pro",".cash",".r",".c",".m","m",".spot","-cash",".sd","+",".i","_SB","_raw",".a",".z"};
   string bases[]; ArrayResize(bases,40); int nb=0;
   bases[nb++]=want;
   string U=want; StringToUpper(U);
   if(StringFind(U,"XAU")>=0 || StringFind(U,"GOLD")>=0){
      bases[nb++]="XAUUSD"; bases[nb++]="GOLD"; bases[nb++]="GOLDUSD"; }
   else if(StringFind(U,"SPX")>=0 || StringFind(U,"500")>=0){
      bases[nb++]="US500"; bases[nb++]="SPX500"; bases[nb++]="SP500"; bases[nb++]="USA500"; bases[nb++]="US500Cash"; bases[nb++]="US_500"; bases[nb++]="SPX"; bases[nb++]="S&P500"; bases[nb++]="US500.cash"; }
   else if(StringFind(U,"NAS")>=0 || StringFind(U,"USTEC")>=0 || StringFind(U,"NDX")>=0 || StringFind(U,"US100")>=0 || StringFind(U,"TECH")>=0){
      bases[nb++]="NAS100"; bases[nb++]="USTEC"; bases[nb++]="US100"; bases[nb++]="NDX100"; bases[nb++]="USTECH"; bases[nb++]="USTEC100"; bases[nb++]="NDX"; bases[nb++]="US_TECH100"; bases[nb++]="NAS100.cash"; }
   else if(StringFind(U,"GER")>=0 || StringFind(U,"DAX")>=0 || StringFind(U,"DE40")>=0 || StringFind(U,"DE30")>=0){
      bases[nb++]="GER40"; bases[nb++]="DE40"; bases[nb++]="DAX40"; bases[nb++]="GER30"; bases[nb++]="DE30"; bases[nb++]="GERMANY40"; bases[nb++]="DE_40"; bases[nb++]="DAX"; bases[nb++]="GER40.cash"; }
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
   g_emonWeekly=InpEMonWeeklyPct; g_e5leg=InpE5LegRiskPct;
   g_useTrailing=false; g_useProfitStop=false; g_useDailyStop=false;
   g_profitPct=0; g_dailyStopPct=0; g_maxLossPct=InpMaxLossLimitPct;
   g_floorBufPct=MathMax(0.0, InpMaxLossLimitPct-InpAccountFloorDDPct); // 全停止= -InpAccountFloorDDPct
   g_scenName="MANUAL";
   if(InpScenario==PARA_INSTANT){
      // ★インスタント攻め 2.0x。トレーリング枠(Blueberry等)。E-Mon:E5≈67:33。
      g_scenName="INSTANT_2.0x_AGGR"; g_emonWeekly=1.20; g_e5leg=0.60;
      g_useTrailing=true; g_useProfitStop=false; g_useDailyStop=false;
   } else if(InpScenario==PARA_PROP_BREAKTHROUGH){
      // ★プロップ最速攻め 3.0x。静的-10%/+8%/日次-4%(FTMOは日次-5%/+10%目標に変更可)。
      g_scenName="PROP_3.0x_AGGR"; g_emonWeekly=3.00; g_e5leg=1.50;
      g_useTrailing=false; g_useProfitStop=true; g_profitPct=8.0;
      g_useDailyStop=true; g_dailyStopPct=4.0;
   } else {
      // ★PARA_MANUAL: 手動ガードを入力から有効化（P-A/D/CでE-Mon脚を主EAと併走させる時も自前で日次/利確を持つ）。
      if(InpManualProfitStopPct>0.0){ g_useProfitStop=true; g_profitPct=InpManualProfitStopPct; }
      if(InpManualDailyStopPct>0.0){ g_useDailyStop=true;  g_dailyStopPct=InpManualDailyStopPct; }
   }
}

int OnInit()
{
   if(!InpAcknowledgeLEAD){ Print("[STOP] E-Mon/E5=STRONG-LEAD。InpAcknowledgeLEAD=trueで承認(デモ/極小)。"); return INIT_FAILED; }
   int nm=SplitCSV(InpEMonSymbols,g_emon);
   int ne=SplitCSV(InpE5Symbols,g_e5);
   int nh=SplitHours(InpEntryHoursUTC,g_hours);
   if(nm==0||ne==0||nh==0){ Print("シンボル/時刻のパース失敗"); return INIT_FAILED; }
   ResolveScenario();
   g_mEMon=InpMagicBase+1; g_mE5=InpMagicBase+2;
   g_initBal=(InpInitialBalance>0.0)?InpInitialBalance:AccountInfoDouble(ACCOUNT_BALANCE);
   if(g_initBal<=0.0) g_initBal=AccountInfoDouble(ACCOUNT_EQUITY);

   ArrayResize(g_atrH1,nm); ArrayResize(g_atrMN1,ne);
   ArrayResize(g_lastShot,nm*nh); ArrayInitialize(g_lastShot,0);
   ArrayResize(g_lastMonth,ne); ArrayInitialize(g_lastMonth,0);

   for(int i=0;i<nm;i++){
      string r=ResolveSymbol(g_emon[i]); g_atrH1[i]=INVALID_HANDLE;
      if(r==""){ PrintFormat("⚠ E-Mon銘柄 %s 見つからず→スキップ",g_emon[i]); continue; }
      if(r!=g_emon[i]) PrintFormat("[銘柄解決] E-Mon %s → %s",g_emon[i],r);
      g_emon[i]=r; g_atrH1[i]=iATR(g_emon[i],PERIOD_H1,InpAtrPeriodH1);
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
   PrintFormat("[INIT PARA %s] initBal=%.0f E-Mon週次=%.2f%% E5leg=%.2f%% trailing=%s profit=%s(%.0f) daily=%s",
      g_scenName,g_initBal,g_emonWeekly,g_e5leg,(g_useTrailing?"Y":"N"),
      (g_useProfitStop?"Y":"N"),g_profitPct,(g_useDailyStop?"Y":"N"));
   if(InpVerboseLog) Print("[NOTE] 1チャートに本EA1つだけ。E-Mon+E5を内部運用。Magic分離(",g_mEMon,"/",g_mE5,")。共にSTRONG-LEAD=デモ前提。");
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

double BreachFloor(double equity)
{
   if(!g_useTrailing) return g_initBal*(1.0-g_maxLossPct/100.0);
   if(equity>g_peakEquity) g_peakEquity=equity;
   double raw=g_peakEquity-g_initBal*g_maxLossPct/100.0;
   double capped=MathMin(raw,g_initBal);
   if(capped>g_trailFloor) g_trailFloor=capped;
   return g_trailFloor;
}

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
bool IsMine(long m){ return (m==g_mEMon||m==g_mE5); }
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

   ManageEMonExit();
   ManageE5();

   bool blockNew = (g_useProfitStop && equity>=g_initBal*(1.0+g_profitPct/100.0)) || g_dayBlocked;
   if(blockNew) return;

   EntriesEMon(utc);
   EntriesE5();
}

//===== E-Mon (株価指数 月曜LONG 多ショット・リスク予算化, v7と同型) =====
void ManageEMonExit()
{
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()!=g_mEMon) continue;
      int held=(int)(TimeCurrent()-(datetime)posinfo.Time());
      if(held>=InpHoldHours*3600){ if(trade.PositionClose(tk)&&InpVerboseLog)
         PrintFormat("[E-Mon TIME EXIT] %s",posinfo.Symbol()); }
   }
}
void EntriesEMon(datetime utc)
{
   MqlDateTime u; TimeToStruct(utc,u);
   if(u.day_of_week!=InpEntryWeekday) return;
   int slot=-1; for(int h=0;h<ArraySize(g_hours);h++) if(u.hour==g_hours[h]){ slot=h; break; }
   if(slot<0) return;
   datetime hourBar=utc-(utc%3600); int nh=ArraySize(g_hours);
   double perShot=g_emonWeekly/(InpShotsPerWeek>0?InpShotsPerWeek:1);
   trade.SetExpertMagicNumber(g_mEMon);
   for(int s=0;s<ArraySize(g_emon);s++){
      if(g_atrH1[s]==INVALID_HANDLE) continue;
      int key=s*nh+slot;
      if(g_lastShot[key]==hourBar) continue;
      string sym=g_emon[s]; double pt=PointOf(sym); if(pt<=0) continue;
      double atr=AtrAt(g_atrH1[s]); if(atr<=0) continue;
      double sd=InpCatastropheATR*atr; double sp=sd/pt;     // SL距離(ポイント)
      if(sp<InpMinStopPts){ sp=InpMinStopPts; sd=sp*pt; }
      if(sp>InpMaxStopPts) continue;
      double ask=SymbolInfoDouble(sym,SYMBOL_ASK), bid=SymbolInfoDouble(sym,SYMBOL_BID);
      if(ask<=0||bid<=0) continue;
      if((ask-bid)/pt>InpMaxSpreadPts){ g_lastShot[key]=hourBar; continue; }
      double riskMoney=g_initBal*(perShot/100.0);
      double lots=LotsFor(sym,sd,riskMoney); if(lots<InpMinLot){ g_lastShot[key]=hourBar; continue; }
      int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      double sl=NormalizeDouble(ask-sd,dg);
      g_lastShot[key]=hourBar;
      if(trade.Buy(lots,sym,0.0,sl,0.0,StringFormat("EMon_%s_h%d",sym,g_hours[slot])))
         { if(InpVerboseLog) PrintFormat("[E-Mon ENTRY] LONG %s h%dUTC lots=%.2f SL=%.2f perShot=%.3f%%",sym,g_hours[slot],lots,sl,perShot); }
   }
}

//===== E5 (多資産月次TSMOM) =====
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
//|  ・E-Mon=STRONG-LEAD(7/9, docs/50)。落ちるのはG3(Bonferroni N=130, |
//|    v7も同じ)とG5(2020年のみ僅差0.125)。本資金前デモ前進検証必須。   |
//|    E5=STRONG-LEAD(未検証, docs/31)。                              |
//|  ・E-Monの3指数(NAS100/US500/GER40)は相互に正相関(同じ"月曜効果")。 |
//|    独立ではない=v7の円3クロスと同じ"1現象の多ショット"。分散は     |
//|    相関<1で実効。サイズは週次予算で建て、合算DDを器に収める。      |
//|  ・E-MonとE5は指数(US500/NAS100/GER40)を共有するがMagic分離で別管理 |
//|    (ヘッジ口座=両建て併存 / ネッティング口座=相殺に注意)。         |
//|  ・指数CFDの実スプレッド/スワップ/配当/取引時間は業者差大=要デモ。  |
//|    月曜のセッション開始時刻(InpEntryHoursUTC)は業者の指数取引時間に  |
//|    合わせて調整(休場だと建たない)。                                |
//|  ・サイズ既定はv7:E5の比率を踏襲した近似。正確な65:35〜70:30は      |
//|    notebooks/parallel_emon_validate(Drive)とデモ実DDで確定。        |
//|  ・1チャートに本EAは1つだけ(複数/他EAと同口座でMagic衝突回避)。     |
//|  ・FTMO等2-stepは日次-5%/+10%目標→ InpScenario=PARA_MANUAL +        |
//|    InpAccountFloorDDPct/日次は規約に合わせる(docs/51)。            |
//+------------------------------------------------------------------+
