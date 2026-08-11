//+------------------------------------------------------------------+
//|                    Chien_PortfolioD_AllInOne_PROP.mq5            |
//|   分散案D オールインワン(プロップ既定・1チャート1EA):               |
//|   v4(日足k≥4合議) + v7(円月曜) + E-Mon[RG3](指数月曜+リスクオフ・   |
//|   ゲート) + E5(多資産トレンド) = 30:25:25:20 を単一口座で運用。     |
//|                                                                   |
//|   ■ なぜ分散案Dか(docs/75 §6・Drive実データ確定):                   |
//|     FundedNext P1(+8%/−10%) median-3(中央3ヶ月)で全構成中の最小失格。 |
//|       median-3 標準: 通過95.1% / 失格4.9% / p95年DD −14%             |
//|       median-4     : 通過97.3% / 失格2.7% / p95年DD −11%             |
//|     旧2成分(v4:E-Mon 55:45[RG3]=15.1%)から失格が1/3に。4スリーブの    |
//|     分散(v7⇄v4 −0.10ほか)で「攻めなのにDDが浅い」が源泉。            |
//|     E-Mon は RG3ゲート版(docs/68採用: SMA200割れ×高ボラ週のみ見送り)。 |
//|                                                                   |
//|   ■ シナリオ(InpScenario 1つで配分/ガード自動):                     |
//|     PD_MEDIAN3_STD  ★既定: 中央3ヶ月・標準(失格4.9%)                |
//|        v7 1.95%/wk・v4 0.58%/trade・E-Mon 1.95%/wk・E5 1.56% leg     |
//|        (= p3_median4_D.set の確定値 ×1.247 = Drive実測 ×2.73/×2.19) |
//|     PD_MEDIAN3_X150 : 高リスク×1.5(中央2ヶ月・失格18%級=非推奨寄り)  |
//|     PD_FUNDED_CONSERV: 資金化後の保守−6%(年失格0.2%・$100kで        |
//|        手取り≈¥86k/月)。資金化したら即これへ切替(docs/57/76)。        |
//|     PD_MANUAL       : 手動値                                       |
//|     共通ガード: 静的−10% / +8%利確停止(審査時) / 日次−4% / フロア−9% |
//|                                                                   |
//|   ■ 実装は検証済みEAから逐語流用(ロジック改変なし):                  |
//|     v7/v4/E5 = Chien_Portfolio3_AllInOne_PROP.mq5                   |
//|     E-Mon+RG3 = Chien_Parallel_AllInOne_PROP.mq5                    |
//|     Magic: base+1=v7 / +2=v4 / +3=E5 / +4=E-Mon (base既定760720)     |
//|                                                                   |
//|   ★1チャートに本EAを1つだけドロップ(どの銘柄/足でも可)。残高は自動。 |
//|     銘柄名は業者仕様に合わせ InpYen/V4/E5/EMon Symbols を編集。       |
//|   ⚠ v7/v4=ADOPT、E-Mon/E5=STRONG-LEAD(未確証)。本資金前にデモ必須。  |
//|     失格4.9%は月次解像度=楽観側。サイズは一次校正=デモ実DDで確定。   |
//|     median-3は口座喪失前提の攻め。資金化後は PD_FUNDED_CONSERV へ。  |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.00"
#property strict
#property description "Portfolio-D all-in-one (PROP): v4+v7+E-Mon[RG3]+E5 = 30:25:25:20 on one chart. median-3 default (Drive-confirmed fail 4.9%). Per-strategy magics."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

enum ENUM_PD_SCENARIO
{
   PD_MEDIAN3_STD     = 0, // ★中央3ヶ月・標準(失格4.9%/Drive確定)
   PD_MEDIAN3_X150    = 1, // 高リスク×1.5(中央2ヶ月・失格18%級)
   PD_FUNDED_CONSERV  = 2, // 資金化後・保守−6%(年失格0.2%)
   PD_MANUAL          = 3  // 手動(下の各risk値)
};

input group "=== シナリオ（これ1つで配分/ガード自動）==="
input ENUM_PD_SCENARIO InpScenario = PD_MEDIAN3_STD; // ★既定=中央3ヶ月・標準
input bool   InpAcknowledgeLEAD = true;   // v7/v4=ADOPT, E-Mon/E5=LEAD。デモ/極小で承認=true

input group "=== 銘柄（業者の実銘柄名に合わせる）==="
input string InpYenSymbols  = "EURJPY,GBPJPY,USDJPY";                          // v7: 円3クロス
input string InpV4Symbols   = "EURUSD,GBPUSD,USDJPY,AUDUSD,USDCHF,USDCAD,NZDUSD,EURJPY,GBPJPY"; // v4: 9ペア
input string InpE5Symbols   = "XAUUSD,US500,NAS100,GER40";                     // E5: 金+株価指数
input string InpEMonSymbols = "NAS100,US500,GER40";                            // E-Mon: 指数3つ(月曜LONG)

input group "=== 口座/ガード ==="
input double InpInitialBalance   = 0.0;   // 0=口座残高を自動取得
input double InpMaxLossLimitPct  = 10.0;  // 失格ライン%
input double InpAccountFloorDDPct= 9.0;   // 全停止ライン%(攻め=9.0で-10%枠をほぼ使い切る)

input group "=== 手動値（PD_MANUAL時のみ・4スリーブの配分）==="
input double InpWeeklyRiskPct    = 1.95;  // v7 週次リスク%(median-3標準と同値)
input double InpV4RiskPerTradePct= 0.58;  // v4 1トレードあたりリスク%
input double InpEMonWeeklyPct    = 1.95;  // E-Mon 週次リスク%
input double InpE5LegRiskPct     = 1.56;  // E5 legRisk%(各レッグ月次σ)
input double InpManualProfitStopPct = 8.0; // PD_MANUAL: +この%で新規停止(0=無効)。FN P1=8.0
input double InpManualDailyStopPct  = 4.0; // PD_MANUAL: 日次−この%で当日全決済(0=無効)

input group "=== v7 設定（円クロス 月曜マルチショット）==="
input string InpV7HoursUTC    = "4,6,8,10";
input int    InpV7ShotsPerWeek= 12;
input int    InpV7HoldHours   = 24;
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

input group "=== E-Mon 設定（株価指数 月曜LONG）==="
input int    InpEMonWeekday   = 1;        // 1=月曜
input string InpEMonHoursUTC  = "9,14";   // 欧州/米セッション2点
input int    InpEMonShotsPerWeek = 6;     // 指数3×時刻2
input int    InpEMonHoldHours = 24;
input double InpMinStopPts    = 50.0;     // 指数の最小SL(ポイント)
input double InpMaxStopPts    = 200000.0;
input double InpMaxSpreadPts  = 1500.0;

input group "=== E-Mon RG3 レジームゲート（docs/68採用・DD保険）==="
input bool   InpEMonRegimeGate = true;    // ★分散案Dの確定仕様=RG3 ON
input int    InpRG_SMA        = 200;
input int    InpRG_VolWin     = 20;
input int    InpRG_VolLB      = 252;
input double InpRG_VolQ       = 0.80;

input group "=== E5 設定（多資産月次TSMOM）==="
input int    InpLB1=1, InpLB2=3, InpLB3=6, InpLB4=12;
input bool   InpAllowShort = true;
input int    InpAtrPeriodMN1= 6;
input double InpCatATR_E5  = 2.5;

input group "=== 共通 ==="
input double InpMinLot = 0.01;
input double InpMaxLot = 50.0;
input long   InpMagicBase = 760720;       // v7=+1 / v4=+2 / E5=+3 / E-Mon=+4
input int    InpSlippagePoints = 30;
input bool   InpVerboseLog = true;

//==================================================================
CTrade        trade;
CPositionInfo posinfo;

string   g_yen[]; string g_v4[]; string g_e5[]; string g_emon[];
int      g_v7hours[]; int g_emhours[];
int      g_atrH1[]; int g_atrD1[]; int g_rsiD1[]; int g_atrMN1[]; int g_atrH1em[];
datetime g_lastShotV7[];   // [yenIdx*nV7Hours + hourIdx]
datetime g_lastShotEM[];   // [emonIdx*nEMHours + hourIdx]
datetime g_lastV4Bar[];    // [v4Idx]
datetime g_lastMonth[];    // [e5Idx]
double   g_initBal=0.0, g_weeklyRisk=1.95, g_v4risk=0.58, g_emonWeekly=1.95, g_e5leg=1.56, g_maxLossPct=10.0;
bool     g_useProfitStop=false, g_useDailyStop=false;
double   g_profitPct=0.0, g_dailyStopPct=0.0, g_floorBufPct=1.0;
double   g_dayStartEq=0.0;
datetime g_curDay=0; bool g_halted=false, g_dayBlocked=false;
string   g_scenName="";
long     g_mV7=0, g_mV4=0, g_mE5=0, g_mEMon=0;

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
double PointOf(string s){ return SymbolInfoDouble(s,SYMBOL_POINT); }

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
   // 単位サイズの校正アンカー: p3_median4_D.set(分散案D 中央4ヶ月=Drive実測×2.19)を
   // ×1.247(=median-3 ×2.73 / median-4 ×2.19, docs/75 §6 Drive確定)した値が「中央3ヶ月・標準」。
   g_weeklyRisk=InpWeeklyRiskPct; g_v4risk=InpV4RiskPerTradePct;
   g_emonWeekly=InpEMonWeeklyPct; g_e5leg=InpE5LegRiskPct;
   g_useProfitStop=false; g_useDailyStop=false;
   g_profitPct=0; g_dailyStopPct=0; g_maxLossPct=InpMaxLossLimitPct;
   g_floorBufPct=MathMax(0.0, InpMaxLossLimitPct-InpAccountFloorDDPct);
   g_scenName="MANUAL";
   if(InpScenario==PD_MEDIAN3_STD){
      // ★中央3ヶ月・標準(Drive確定: 通過95.1%/失格4.9%/p95年DD−14%)。静的−10%/+8%/日次−4%。
      g_scenName="D_MEDIAN3_STD"; g_weeklyRisk=1.95; g_v4risk=0.58; g_emonWeekly=1.95; g_e5leg=1.56;
      g_useProfitStop=true; g_profitPct=8.0; g_useDailyStop=true; g_dailyStopPct=4.0;
   } else if(InpScenario==PD_MEDIAN3_X150){
      // 高リスク×1.5(中央2ヶ月・失格18%級=Yahoo近似)。⚠返金なし業者では非推奨寄り。
      g_scenName="D_MEDIAN3_X1.5"; g_weeklyRisk=2.92; g_v4risk=0.88; g_emonWeekly=2.92; g_e5leg=2.34;
      g_useProfitStop=true; g_profitPct=8.0; g_useDailyStop=true; g_dailyStopPct=4.0;
   } else if(InpScenario==PD_FUNDED_CONSERV){
      // 資金化後・保守−6%(年失格0.2%・$100kで手取り≈¥86k/月)。利確停止なし・日次−4%は維持。
      // 一次近似: 標準×0.43(p95年DD −14%→−6%の線形換算, docs/46流)。デモで微調整。
      g_scenName="D_FUNDED_CONSERV"; g_weeklyRisk=0.84; g_v4risk=0.25; g_emonWeekly=0.84; g_e5leg=0.67;
      g_useProfitStop=false; g_useDailyStop=true; g_dailyStopPct=4.0;
   } else {
      if(InpManualProfitStopPct>0.0){ g_useProfitStop=true; g_profitPct=InpManualProfitStopPct; }
      if(InpManualDailyStopPct>0.0){ g_useDailyStop=true;  g_dailyStopPct=InpManualDailyStopPct; }
   }
}

int OnInit()
{
   if(!InpAcknowledgeLEAD){ Print("[STOP] E-Mon/E5=STRONG-LEAD。InpAcknowledgeLEAD=trueで承認(デモ/極小)。"); return INIT_FAILED; }
   int ny=SplitCSV(InpYenSymbols,g_yen);
   int nv=SplitCSV(InpV4Symbols,g_v4);
   int ne=SplitCSV(InpE5Symbols,g_e5);
   int nm=SplitCSV(InpEMonSymbols,g_emon);
   int nh7=SplitHours(InpV7HoursUTC,g_v7hours);
   int nhm=SplitHours(InpEMonHoursUTC,g_emhours);
   if(ny==0||nv==0||ne==0||nm==0||nh7==0||nhm==0){ Print("シンボル/時刻のパース失敗"); return INIT_FAILED; }
   ResolveScenario();
   g_mV7=InpMagicBase+1; g_mV4=InpMagicBase+2; g_mE5=InpMagicBase+3; g_mEMon=InpMagicBase+4;
   g_initBal=(InpInitialBalance>0.0)?InpInitialBalance:AccountInfoDouble(ACCOUNT_BALANCE);
   if(g_initBal<=0.0) g_initBal=AccountInfoDouble(ACCOUNT_EQUITY);

   ArrayResize(g_atrH1,ny); ArrayResize(g_atrD1,nv); ArrayResize(g_rsiD1,nv);
   ArrayResize(g_atrMN1,ne); ArrayResize(g_atrH1em,nm);
   ArrayResize(g_lastShotV7,ny*nh7); ArrayInitialize(g_lastShotV7,0);
   ArrayResize(g_lastShotEM,nm*nhm); ArrayInitialize(g_lastShotEM,0);
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
   for(int i=0;i<nm;i++){
      string r=ResolveSymbol(g_emon[i]); g_atrH1em[i]=INVALID_HANDLE;
      if(r==""){ PrintFormat("⚠ E-Mon銘柄 %s 見つからず→スキップ",g_emon[i]); continue; }
      if(r!=g_emon[i]) PrintFormat("[銘柄解決] E-Mon %s → %s",g_emon[i],r);
      g_emon[i]=r; g_atrH1em[i]=iATR(g_emon[i],PERIOD_H1,InpAtrPeriodH1);
   }
   trade.SetDeviationInPoints(InpSlippagePoints);
   ResetDay(TimeCurrent());
   PrintFormat("[INIT PD %s] initBal=%.0f v7=%.2f%%/wk v4=%.2f%%/tr E-Mon=%.2f%%/wk(RG3=%s) E5=%.2f%%leg profit=%s(%.0f) daily=%s(%.1f)",
      g_scenName,g_initBal,g_weeklyRisk,g_v4risk,g_emonWeekly,(InpEMonRegimeGate?"ON":"OFF"),g_e5leg,
      (g_useProfitStop?"Y":"N"),g_profitPct,(g_useDailyStop?"Y":"N"),g_dailyStopPct);
   if(InpVerboseLog) Print("[NOTE] 分散案D=30:25:25:20。1チャートに本EA1つだけ。Magic(",g_mV7,"/",g_mV4,"/",g_mE5,"/",g_mEMon,")。資金化後は PD_FUNDED_CONSERV へ。");
   EventSetTimer(30);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){
   EventKillTimer();
   for(int i=0;i<ArraySize(g_atrH1);i++)  if(g_atrH1[i]!=INVALID_HANDLE)  IndicatorRelease(g_atrH1[i]);
   for(int i=0;i<ArraySize(g_atrD1);i++)  if(g_atrD1[i]!=INVALID_HANDLE)  IndicatorRelease(g_atrD1[i]);
   for(int i=0;i<ArraySize(g_rsiD1);i++)  if(g_rsiD1[i]!=INVALID_HANDLE)  IndicatorRelease(g_rsiD1[i]);
   for(int i=0;i<ArraySize(g_atrMN1);i++) if(g_atrMN1[i]!=INVALID_HANDLE) IndicatorRelease(g_atrMN1[i]);
   for(int i=0;i<ArraySize(g_atrH1em);i++)if(g_atrH1em[i]!=INVALID_HANDLE)IndicatorRelease(g_atrH1em[i]);
}

datetime DayStart(datetime t){ MqlDateTime s; TimeToStruct(t,s); s.hour=0;s.min=0;s.sec=0; return StructToTime(s); }
void ResetDay(datetime t){ g_curDay=DayStart(t); g_dayStartEq=AccountInfoDouble(ACCOUNT_EQUITY); g_dayBlocked=false; }
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
bool IsMine(long m){ return (m==g_mV7||m==g_mV4||m==g_mE5||m==g_mEMon); }
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

   // 静的フロア(初期残高基準・FN Stellar)。guard=フロアの内側バッファで早期撤退。
   double floor=g_initBal*(1.0-g_maxLossPct/100.0);
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
   ManageEMonExit();
   ManageE5();

   bool blockNew = (g_useProfitStop && equity>=g_initBal*(1.0+g_profitPct/100.0)) || g_dayBlocked;
   if(blockNew) return;

   EntriesV7(utc);
   EntriesV4();
   EntriesEMon(utc);
   EntriesE5();
}

//===== v7 (円クロス 月曜マルチショット; Portfolio3 から逐語) =====
void ManageV7Exit()
{
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()!=g_mV7) continue;
      int held=(int)(TimeCurrent()-(datetime)posinfo.Time());
      if(held>=InpV7HoldHours*3600){ if(trade.PositionClose(tk)&&InpVerboseLog)
         PrintFormat("[v7 TIME EXIT] %s",posinfo.Symbol()); }
   }
}
void EntriesV7(datetime utc)
{
   MqlDateTime u; TimeToStruct(utc,u);
   if(u.day_of_week!=1) return;
   int slot=-1; for(int h=0;h<ArraySize(g_v7hours);h++) if(u.hour==g_v7hours[h]){ slot=h; break; }
   if(slot<0) return;
   datetime hourBar=utc-(utc%3600); int nh=ArraySize(g_v7hours);
   double perShot=g_weeklyRisk/(InpV7ShotsPerWeek>0?InpV7ShotsPerWeek:1);
   trade.SetExpertMagicNumber(g_mV7);
   for(int s=0;s<ArraySize(g_yen);s++){
      if(g_atrH1[s]==INVALID_HANDLE) continue;
      int key=s*nh+slot;
      if(g_lastShotV7[key]==hourBar) continue;
      string sym=g_yen[s]; double pip=PipOf(sym);
      double atr=AtrAt(g_atrH1[s]); if(atr<=0) continue;
      double sd=InpCatastropheATR*atr; double sp=sd/pip;
      if(sp<InpMinStopPips){ sp=InpMinStopPips; sd=sp*pip; }
      if(sp>InpMaxStopPips) continue;
      double ask=SymbolInfoDouble(sym,SYMBOL_ASK), bid=SymbolInfoDouble(sym,SYMBOL_BID);
      if(ask<=0||bid<=0) continue;
      if((ask-bid)/pip>InpMaxSpreadPips){ g_lastShotV7[key]=hourBar; continue; }
      double riskMoney=g_initBal*(perShot/100.0);
      double lots=LotsFor(sym,sd,riskMoney); if(lots<InpMinLot){ g_lastShotV7[key]=hourBar; continue; }
      int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      double sl=NormalizeDouble(ask-sd,dg);
      g_lastShotV7[key]=hourBar;
      if(trade.Buy(lots,sym,0.0,sl,0.0,StringFormat("v7_%s_h%d",sym,g_v7hours[slot])))
         { if(InpVerboseLog) PrintFormat("[v7 ENTRY] LONG %s h%dUTC lots=%.2f SL=%.5f",sym,g_v7hours[slot],lots,sl); }
   }
}

//===== v4 (日足k≥4合議; Portfolio3 から逐語) =====
int V4Signal(string sym, int rsiHandle, double &atrOut)
{
   atrOut=0.0;
   double c[]; ArraySetAsSeries(c,true);
   int need=MathMax(InpV4_BBwin+2, InpV4_streak+3);
   if(CopyClose(sym,PERIOD_D1,1,need+2,c)<need+1) return 0;   // c[0]=直近確定足
   double rb[1];
   if(rsiHandle==INVALID_HANDLE || CopyBuffer(rsiHandle,0,1,1,rb)<1) return 0;
   double rsi=rb[0];
   double mean=0; for(int k=1;k<=InpV4_BBwin;k++) mean+=c[k]; mean/=InpV4_BBwin;
   double var=0; for(int k=1;k<=InpV4_BBwin;k++) var+=(c[k]-mean)*(c[k]-mean); var/=(InpV4_BBwin-1);
   double sd=MathSqrt(var); double z=(sd>0)?(c[0]-mean)/sd:0.0;
   int down=0; for(int k=0;k<12;k++){ if(c[k]<c[k+1]) down++; else break; }
   int up=0;   for(int k=0;k<12;k++){ if(c[k]>c[k+1]) up++;   else break; }
   double ret=(c[1]!=0)?(c[0]-c[1])/c[1]:0.0; double mv=InpV4_dayMovePct/100.0;
   int buy = (rsi<InpV4_RSIlo?1:0)+(z<-InpV4_BBz?1:0)+(down>=InpV4_streak?1:0)+(ret<-mv?1:0);
   int sell= (rsi>InpV4_RSIhi?1:0)+(z> InpV4_BBz?1:0)+(up  >=InpV4_streak?1:0)+(ret> mv?1:0);
   if(buy>=4 && buy>sell) return 1;
   if(sell>=4 && sell>buy && InpAllowShort) return -1;
   return 0;
}
void ManageV4Exit()
{
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
      if(db==0 || db==g_lastV4Bar[i]) continue;
      g_lastV4Bar[i]=db;
      if(CountPos(sym,g_mV4)>0) continue;
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

//===== E-Mon + RG3 (株価指数 月曜LONG; Parallel から逐語) =====
void ManageEMonExit()
{
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()!=g_mEMon) continue;
      int held=(int)(TimeCurrent()-(datetime)posinfo.Time());
      if(held>=InpEMonHoldHours*3600){ if(trade.PositionClose(tk)&&InpVerboseLog)
         PrintFormat("[E-Mon TIME EXIT] %s",posinfo.Symbol()); }
   }
}
double PercentileSorted(double &v[], int n, double q)
{
   double a[]; ArrayResize(a,n); for(int i=0;i<n;i++) a[i]=v[i]; ArraySort(a);
   if(n<=1) return (n==1?a[0]:0.0);
   double idx=q*(n-1); int lo=(int)MathFloor(idx); double fr=idx-lo;
   if(lo>=n-1) return a[n-1];
   return a[lo]+(a[lo+1]-a[lo])*fr;
}
bool EMonRiskOffWeek()
{
   int n=ArraySize(g_emon);
   int need=InpRG_SMA+InpRG_VolLB+InpRG_VolWin+5;
   int upCount=0, valid=0;
   double bvsum[]; int bvcnt[]; ArrayResize(bvsum,InpRG_VolLB); ArrayResize(bvcnt,InpRG_VolLB);
   ArrayInitialize(bvsum,0.0); ArrayInitialize(bvcnt,0);
   for(int s=0;s<n;s++){
      if(g_atrH1em[s]==INVALID_HANDLE) continue;
      double c[]; int got=CopyClose(g_emon[s],PERIOD_D1,0,need,c);
      if(got<InpRG_SMA+2) continue;
      ArraySetAsSeries(c,true);                          // c[1]=前営業日の確定終値
      double sma=0; for(int k=1;k<=InpRG_SMA;k++) sma+=c[k]; sma/=InpRG_SMA;
      valid++; if(c[1]>sma) upCount++;
      for(int d=0;d<InpRG_VolLB;d++){
         int base=1+d; if(base+InpRG_VolWin+1>=got) break;
         double m=0; for(int j=0;j<InpRG_VolWin;j++) m+=(c[base+j]/c[base+j+1]-1.0); m/=InpRG_VolWin;
         double vv=0; for(int j=0;j<InpRG_VolWin;j++){ double r=c[base+j]/c[base+j+1]-1.0; vv+=(r-m)*(r-m); }
         double sd=MathSqrt(vv/InpRG_VolWin)*MathSqrt(252.0);
         bvsum[d]+=sd; bvcnt[d]++;
      }
   }
   if(valid==0) return false;                             // 判定不能→fail-open(通常建て)
   bool up_maj=(upCount*2>=valid);
   double bv[]; int m=0; ArrayResize(bv,InpRG_VolLB);
   for(int d=0;d<InpRG_VolLB;d++) if(bvcnt[d]>0) bv[m++]=bvsum[d]/bvcnt[d];
   if(m<30) return false;
   double cur=bv[0]; double thr=PercentileSorted(bv,m,InpRG_VolQ);
   bool hv_high=(cur>thr);
   return ((!up_maj) && hv_high);                         // 真リスクオフ週=見送り
}
void EntriesEMon(datetime utc)
{
   MqlDateTime u; TimeToStruct(utc,u);
   if(u.day_of_week!=InpEMonWeekday) return;
   int slot=-1; for(int h=0;h<ArraySize(g_emhours);h++) if(u.hour==g_emhours[h]){ slot=h; break; }
   if(slot<0) return;
   if(InpEMonRegimeGate && EMonRiskOffWeek()){
      if(InpVerboseLog) Print("[E-Mon RG3] リスクオフ週(SMA200割れ×高ボラ)→月曜建て見送り");
      return;
   }
   datetime hourBar=utc-(utc%3600); int nh=ArraySize(g_emhours);
   double perShot=g_emonWeekly/(InpEMonShotsPerWeek>0?InpEMonShotsPerWeek:1);
   trade.SetExpertMagicNumber(g_mEMon);
   for(int s=0;s<ArraySize(g_emon);s++){
      if(g_atrH1em[s]==INVALID_HANDLE) continue;
      int key=s*nh+slot;
      if(g_lastShotEM[key]==hourBar) continue;
      string sym=g_emon[s]; double pt=PointOf(sym); if(pt<=0) continue;
      double atr=AtrAt(g_atrH1em[s]); if(atr<=0) continue;
      double sd=InpCatastropheATR*atr; double sp=sd/pt;
      if(sp<InpMinStopPts){ sp=InpMinStopPts; sd=sp*pt; }
      if(sp>InpMaxStopPts) continue;
      double ask=SymbolInfoDouble(sym,SYMBOL_ASK), bid=SymbolInfoDouble(sym,SYMBOL_BID);
      if(ask<=0||bid<=0) continue;
      if((ask-bid)/pt>InpMaxSpreadPts){ g_lastShotEM[key]=hourBar; continue; }
      double riskMoney=g_initBal*(perShot/100.0);
      double lots=LotsFor(sym,sd,riskMoney); if(lots<InpMinLot){ g_lastShotEM[key]=hourBar; continue; }
      int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      double sl=NormalizeDouble(ask-sd,dg);
      g_lastShotEM[key]=hourBar;
      if(trade.Buy(lots,sym,0.0,sl,0.0,StringFormat("EMon_%s_h%d",sym,g_emhours[slot])))
         { if(InpVerboseLog) PrintFormat("[E-Mon ENTRY] LONG %s h%dUTC lots=%.2f SL=%.2f perShot=%.3f%%",sym,g_emhours[slot],lots,sl,perShot); }
   }
}

//===== E5 (多資産月次TSMOM; 両EA共通実装から逐語) =====
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
//|  ・失格4.9%(median-3標準)は月次解像度のMC=楽観側(日次−5%/月内DD/   |
//|    ギャップ未反映)。実際はこれより高い前提で。                     |
//|  ・サイズ既定は p3_median4_D.set(確定)×1.247 の一次校正。           |
//|    正確な配分は notebooks/portfolio_D_deploy(Drive)+デモ実DDで確定。|
//|  ・高リスク×1.5(中央2ヶ月/失格18%級)は返金なし業者では非推奨寄り。  |
//|  ・E-MonとE5は指数を共有、v4とv7は円クロスを共有。Magic分離で別管理 |
//|    (ヘッジ口座=両建て併存 / ネッティング口座=相殺に注意)。          |
//|  ・指数CFDの実スプレッド/スワップ/配当/取引時間は業者差大=要デモ。  |
//|  ・1チャートに本EAは1つだけ(他EAとの同口座はMagic衝突に注意)。      |
//|  ・資金化後は PD_FUNDED_CONSERV(0.43x一次近似)へ即切替=生存優先。   |
//|  ・RG3はデータ不足時fail-open(ゲートせず通常建て=raw挙動)。         |
//+------------------------------------------------------------------+
