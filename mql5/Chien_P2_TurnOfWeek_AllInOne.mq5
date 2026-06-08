//+------------------------------------------------------------------+
//|                          Chien_P2_TurnOfWeek_AllInOne.mq5          |
//|   第2ポートフォリオ(P2)オールインワン: 既存P1(v7+v4+E5)と【相関ほぼ |
//|   ゼロ(月次0.014)】な"別物の分散源"を1チャートで運用する。         |
//|                                                                   |
//|   ■ エッジ(商品ユニバース拡張で発見・10年Yahoo検証, docs/50):       |
//|     TOW-Equity(核): 米独株価指数(US500/NAS100/GER40)の【月曜LONG】 |
//|        =週初ドリフト。月曜のみ有意・他曜日は非有意(プラセボ識別)。  |
//|        プールperm_p=0.0098 / IS-OOS両+ / WF4/5 / コスト2×+ /       |
//|        判定 STRONG-LEAD(P1のv7/E5と同級。G3 Bonf・G5 2020依存で未達)|
//|     TOW-Crypto(衛星・任意): BTC/ETH 月曜LONG＋月末LONG。株コアと    |
//|        相関0.10。DD大ゆえ小サイズ＋暗号可の業者のみ(InpEnableCrypto)|
//|                                                                   |
//|   ■ シナリオ(InpScenario)                                          |
//|     P2_INSTANT  : インスタント. 週次0.50% / 暗号leg0.20% /          |
//|        −10%トレーリング / 無目標 / 日次なし。                       |
//|     P2_PROP     : プロップ突破. 週次1.00% / 暗号leg0.35% /          |
//|        静的−10% / +8%で新規停止 / 日次−4%。                        |
//|     P2_MANUAL   : 下の手動値・静的−10%。                            |
//|                                                                   |
//|   ★1チャートに1つだけ。残高自動。銘柄名は業者仕様に合わせ          |
//|     InpEqSymbols / InpCryptoSymbols を編集(US500=SPX500 等)。      |
//|   ⚠ P2は STRONG-LEAD(未確証)＝本資金前にデモ前進検証(docs/29同方針)。|
//|     指数=配当抜き検証ゆえCFD実スプレッド/スワップ/配当はデモで実測。 |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.00"
#property strict
#property description "P2 all-in-one: Turn-of-Week equity (US500/NAS100/GER40 Monday-long) + optional crypto satellite. Near-zero corr to P1. STRONG-LEAD/demo."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

enum ENUM_P2_SCENARIO
{
   P2_INSTANT = 0, // インスタント(週次0.50% / 暗号0.20% / トレーリング)
   P2_PROP    = 1, // プロップ突破(週次1.00% / 暗号0.35% / 静的+8%目標)
   P2_MANUAL  = 2  // 手動(下のWeeklyRisk/CryptoLeg・静的)
};

input group "=== シナリオ（これ1つで倍率/ルール自動）==="
input ENUM_P2_SCENARIO InpScenario = P2_INSTANT; // ★運用先
input bool   InpAcknowledgeLEAD = true;  // P2はSTRONG-LEAD(未確証)。デモ/小サイズ前提=trueで承認

input group "=== 銘柄（業者の実銘柄名に合わせる）==="
input string InpEqSymbols     = "US500,NAS100,GER40";   // TOW核: 株価指数3
input string InpCryptoSymbols = "BTCUSD,ETHUSD";        // TOW衛星: 暗号(任意)
input bool   InpEnableCrypto  = false;                  // 暗号衛星を使う(暗号可の業者のみ)

input group "=== 口座/ガード ==="
input double InpInitialBalance   = 0.0;   // 0=口座残高を自動取得
input double InpMaxLossLimitPct  = 10.0;  // 失格ライン%
input double InpAccountFloorDDPct= 8.0;   // 総合 -8% で全停止(−10%の内側)

input group "=== 手動値（P2_MANUAL時のみ）==="
input double InpWeeklyRiskPct = 0.50;     // 株コア 週次リスク%(3指数で分割)
input double InpCryptoLegPct  = 0.20;     // 暗号 1脚あたりリスク%

input group "=== TOW-Equity(核) 設定 ==="
input int    InpEntryHourUTC = 0;         // 月曜エントリー時刻UTC(週初・指数寄り付き目安)
input int    InpHoldHours    = 24;        // 24h時間決済(月曜→火曜)
input int    InpAtrPeriodH1  = 24;
input double InpCatastropheATR = 3.0;     // 保険SL=ATR(H1)×倍(時間決済が主・SLは保険)
input double InpMaxSpreadFrac = 0.0015;   // 指数の許容スプレッド(価格比, 0.15%)

input group "=== TOW-Crypto(衛星) 設定 ==="
input int    InpCryptoHoldHours = 24;     // 月曜LONG保有
input bool   InpCryptoTOM     = true;     // 月末(最終1+月初3営業日)LONGも行う
input int    InpAtrPeriodD1   = 14;
input double InpCatATR_Crypto = 3.0;

input group "=== 共通 ==="
input double InpMinLot = 0.01;
input double InpMaxLot = 50.0;
input long   InpMagic  = 940800;          // P1(940700系)と分離
input int    InpSlippagePoints = 50;
input bool   InpVerboseLog = true;

//==================================================================
CTrade        trade;
CPositionInfo posinfo;

string   g_eq[]; string g_cry[];
int      g_atrEqH1[]; int g_atrCryD1[];
datetime g_lastMonShotEq[];   // [eqIdx] 月曜発注済みバー
datetime g_lastMonShotCry[];  // [cryIdx]
datetime g_lastTomCry[];      // [cryIdx] TOM発注済み日
double   g_initBal=0.0, g_weeklyRisk=0.50, g_cryLeg=0.20, g_maxLossPct=10.0;
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

// 業者で銘柄名が違う問題に対応: 指定名＋主要別名＋サフィックスを総当りで実在銘柄を解決。
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
   else if(StringFind(U,"GER")>=0 || StringFind(U,"DAX")>=0 || StringFind(U,"DE40")>=0 || StringFind(U,"DE30")>=0 || StringFind(U,"40")>=0){
      bases[nb++]="GER40"; bases[nb++]="DE40"; bases[nb++]="DAX40"; bases[nb++]="GER30"; bases[nb++]="DE30"; bases[nb++]="GERMANY40"; bases[nb++]="DE_40"; bases[nb++]="DAX"; bases[nb++]="GER40.cash"; }
   else if(StringFind(U,"BTC")>=0){
      bases[nb++]="BTCUSD"; bases[nb++]="BTCUSD.std"; bases[nb++]="BTC/USD"; bases[nb++]="Bitcoin"; bases[nb++]="BTCUSDT"; }
   else if(StringFind(U,"ETH")>=0){
      bases[nb++]="ETHUSD"; bases[nb++]="ETHUSD.std"; bases[nb++]="ETH/USD"; bases[nb++]="Ethereum"; bases[nb++]="ETHUSDT"; }
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
   g_weeklyRisk=InpWeeklyRiskPct; g_cryLeg=InpCryptoLegPct;
   g_useTrailing=false; g_useProfitStop=false; g_useDailyStop=false;
   g_profitPct=0; g_dailyStopPct=0; g_maxLossPct=InpMaxLossLimitPct; g_floorBufPct=2.0;
   g_scenName="MANUAL";
   if(InpScenario==P2_INSTANT){
      g_scenName="INSTANT"; g_weeklyRisk=0.50; g_cryLeg=0.20;
      g_useTrailing=true;
   } else if(InpScenario==P2_PROP){
      g_scenName="PROP"; g_weeklyRisk=1.00; g_cryLeg=0.35;
      g_useProfitStop=true; g_profitPct=8.0; g_useDailyStop=true; g_dailyStopPct=4.0;
   }
}

int OnInit()
{
   if(!InpAcknowledgeLEAD){ Print("[STOP] P2はSTRONG-LEAD。InpAcknowledgeLEAD=trueで承認(デモ/小サイズ)。"); return INIT_FAILED; }
   int ne=SplitCSV(InpEqSymbols,g_eq);
   if(ne==0){ Print("株価指数シンボルのパース失敗"); return INIT_FAILED; }
   int nc=InpEnableCrypto?SplitCSV(InpCryptoSymbols,g_cry):0;

   ResolveScenario();
   g_initBal=(InpInitialBalance>0.0)?InpInitialBalance:AccountInfoDouble(ACCOUNT_BALANCE);
   if(g_initBal<=0.0) g_initBal=AccountInfoDouble(ACCOUNT_EQUITY);

   ArrayResize(g_atrEqH1,ne); ArrayResize(g_lastMonShotEq,ne); ArrayInitialize(g_lastMonShotEq,0);
   for(int i=0;i<ne;i++){
      string r=ResolveSymbol(g_eq[i]); g_atrEqH1[i]=INVALID_HANDLE;
      if(r==""){ PrintFormat("⚠ 株指数 %s が見つからず→スキップ",g_eq[i]); continue; }
      if(r!=g_eq[i]) PrintFormat("[銘柄解決] EQ %s → %s",g_eq[i],r);
      g_eq[i]=r;
      g_atrEqH1[i]=iATR(g_eq[i],PERIOD_H1,InpAtrPeriodH1);
   }
   if(nc>0){
      ArrayResize(g_atrCryD1,nc); ArrayResize(g_lastMonShotCry,nc); ArrayInitialize(g_lastMonShotCry,0);
      ArrayResize(g_lastTomCry,nc); ArrayInitialize(g_lastTomCry,0);
      for(int i=0;i<nc;i++){
         string r=ResolveSymbol(g_cry[i]); g_atrCryD1[i]=INVALID_HANDLE;
         if(r==""){ PrintFormat("⚠ 暗号 %s が見つからず→スキップ",g_cry[i]); continue; }
         if(r!=g_cry[i]) PrintFormat("[銘柄解決] CRY %s → %s",g_cry[i],r);
         g_cry[i]=r;
         g_atrCryD1[i]=iATR(g_cry[i],PERIOD_D1,InpAtrPeriodD1);
      }
   }
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   g_peakEquity=g_initBal; g_trailFloor=g_initBal*(1.0-g_maxLossPct/100.0);
   ResetDay(TimeCurrent());
   PrintFormat("[INIT P2] scen=%s initBal=%.0f 週次=%.2f%%(株%d) 暗号=%s(leg%.2f%%) trailing=%s profitStop=%s(%.0f) dailyStop=%s",
      g_scenName,g_initBal,g_weeklyRisk,ne,(InpEnableCrypto?"ON":"OFF"),g_cryLeg,
      (g_useTrailing?"Y":"N"),(g_useProfitStop?"Y":"N"),g_profitPct,(g_useDailyStop?"Y":"N"));
   if(InpVerboseLog) Print("[NOTE] 1チャートに本EAを1つだけ。P1のEA(Magic940700系)とは別口座 or 別Magicで併用可(相関≈0)。");
   EventSetTimer(30);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){
   EventKillTimer();
   for(int i=0;i<ArraySize(g_atrEqH1);i++) if(g_atrEqH1[i]!=INVALID_HANDLE) IndicatorRelease(g_atrEqH1[i]);
   for(int i=0;i<ArraySize(g_atrCryD1);i++) if(g_atrCryD1[i]!=INVALID_HANDLE) IndicatorRelease(g_atrCryD1[i]);
}

datetime DayStart(datetime t){ MqlDateTime s; TimeToStruct(t,s); s.hour=0;s.min=0;s.sec=0; return StructToTime(s); }
void ResetDay(datetime t){ g_curDay=DayStart(t); g_dayStartEq=AccountInfoDouble(ACCOUNT_EQUITY); g_dayBlocked=false; }

bool IsEq(string s){ for(int i=0;i<ArraySize(g_eq);i++) if(g_eq[i]==s) return true; return false; }
bool IsCry(string s){ for(int i=0;i<ArraySize(g_cry);i++) if(g_cry[i]==s) return true; return false; }
double AtrAt(int handle){ double a[1]; if(handle==INVALID_HANDLE) return 0.0; if(CopyBuffer(handle,0,1,1,a)<1) return 0.0; return a[0]; }

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

   // ===== 口座ガード(P1と同一思想) =====
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

   ManageTimeExits();   // 時間決済は常時

   if(g_useProfitStop && equity>=g_initBal*(1.0+g_profitPct/100.0)) return;  // 目標到達=新規停止
   if(g_dayBlocked) return;

   EntriesEquity(utc);
   if(InpEnableCrypto){ EntriesCryptoMon(utc); if(InpCryptoTOM) EntriesCryptoTOM(utc); }
}

void ManageTimeExits()
{
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()!=InpMagic) continue;
      string sym=posinfo.Symbol();
      int held=(int)(TimeCurrent()-(datetime)posinfo.Time());
      int holdLim = IsCry(sym) ? InpCryptoHoldHours : InpHoldHours;
      if(held>=holdLim*3600){ if(trade.PositionClose(tk)&&InpVerboseLog)
         PrintFormat("[TIME EXIT] %s",sym); }
   }
}

//===== TOW-Equity: 月曜 LONG =====
void EntriesEquity(datetime utc)
{
   MqlDateTime u; TimeToStruct(utc,u);
   if(u.day_of_week!=1) return;                  // 月曜のみ
   if(u.hour!=InpEntryHourUTC) return;           // 指定時刻
   datetime hourBar=utc-(utc%3600);
   int ne=ArraySize(g_eq);
   double perShot=g_weeklyRisk/(ne>0?ne:1);      // 週次予算を3指数で分割(合算建玉一定)
   for(int s=0;s<ne;s++){
      if(g_lastMonShotEq[s]==hourBar) continue;
      string sym=g_eq[s];
      double atr=AtrAt(g_atrEqH1[s]); if(atr<=0){ continue; }
      double bid=SymbolInfoDouble(sym,SYMBOL_BID), ask=SymbolInfoDouble(sym,SYMBOL_ASK);
      if(ask<=0||bid<=0) continue;
      if((ask-bid)/MathMax(ask,1.0) > InpMaxSpreadFrac){ if(InpVerboseLog) PrintFormat("[EQ SKIP spread] %s",sym); g_lastMonShotEq[s]=hourBar; continue; }
      double sd=InpCatastropheATR*atr;            // 保険SL(時間決済が主)
      double riskMoney=g_initBal*(perShot/100.0);
      double lots=LotsFor(sym,sd,riskMoney); if(lots<InpMinLot){ g_lastMonShotEq[s]=hourBar; continue; }
      int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      double sl=NormalizeDouble(ask-sd,dg);
      g_lastMonShotEq[s]=hourBar;
      if(trade.Buy(lots,sym,0.0,sl,0.0,StringFormat("P2eq_%s",sym)))
         { if(InpVerboseLog) PrintFormat("[EQ ENTRY] LONG %s lots=%.2f SL=%.2f",sym,lots,sl); }
   }
}

//===== TOW-Crypto衛星: 月曜 LONG =====
void EntriesCryptoMon(datetime utc)
{
   MqlDateTime u; TimeToStruct(utc,u);
   if(u.day_of_week!=1) return;
   if(u.hour!=InpEntryHourUTC) return;
   datetime hourBar=utc-(utc%3600);
   for(int s=0;s<ArraySize(g_cry);s++){
      if(g_lastMonShotCry[s]==hourBar) continue;
      OpenCryptoLong(s, riskMoneyCrypto(), "P2cryMon"); g_lastMonShotCry[s]=hourBar;
   }
}

//===== TOW-Crypto衛星: 月末(最終1+月初3営業日) LONG =====
void EntriesCryptoTOM(datetime utc)
{
   MqlDateTime u; TimeToStruct(utc,u);
   if(u.hour!=InpEntryHourUTC) return;            // 1日1回(指定時刻)だけ判定
   datetime today=DayStart(utc);
   // TOM判定(簡易): 月初3日(day<=3) または 月末最終日(day==月内日数)。暗号は土日も取引ゆえ暦日で近似。
   int dim=DaysInMonth(u.year,u.mon);
   bool isTom = (u.day<=3) || (u.day==dim);
   if(!isTom) return;
   for(int s=0;s<ArraySize(g_cry);s++){
      if(g_lastTomCry[s]==today) continue;
      OpenCryptoLong(s, riskMoneyCrypto(), "P2cryTOM"); g_lastTomCry[s]=today;
   }
}

int DaysInMonth(int y,int m){
   int d[]={31,28,31,30,31,30,31,31,30,31,30,31};
   int dd=d[m-1]; if(m==2 && (y%4==0 && (y%100!=0||y%400==0))) dd=29; return dd;
}
double riskMoneyCrypto(){ return g_initBal*(g_cryLeg/100.0); }

void OpenCryptoLong(int s, double riskMoney, string tag)
{
   string sym=g_cry[s];
   double atr=AtrAt(g_atrCryD1[s]); if(atr<=0) return;
   double ask=SymbolInfoDouble(sym,SYMBOL_ASK); if(ask<=0) return;
   double sd=InpCatATR_Crypto*atr;
   double lots=LotsFor(sym,sd,riskMoney); if(lots<InpMinLot) return;
   int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
   double sl=NormalizeDouble(ask-sd,dg);
   if(trade.Buy(lots,sym,0.0,sl,0.0,tag+"_"+sym) && InpVerboseLog)
      PrintFormat("[CRY ENTRY] LONG %s lots=%.2f (%s)",sym,lots,tag);
}
//+------------------------------------------------------------------+
//| 残存リスク(誠実な記録):                                          |
//|  ・P2は STRONG-LEAD(未確証, docs/50)。G3 Bonferroni と G5 年次JK   |
//|    (2020依存)が未達＝P1のv7/E5と同級。本資金前にデモ前進検証必須。 |
//|  ・株価指数=配当抜きprice indexで検証。CFD実スプレッド/オーバーナイ|
//|    トスワップ/配当調整は未計上→デモで実測(特にPROPの保有コスト)。  |
//|  ・暗号衛星はDD大(BTC単体10年−43%)＝小サイズ＋暗号可の業者のみ。   |
//|    多くのプロップは暗号不可/別ルール→既定OFF。                     |
//|  ・銘柄名は業者依存(US500/SPX500, NAS100/USTEC, GER40/DE40)。      |
//|  ・1チャートに本EAは1つだけ。P1のEA(Magic940700系)とは別Magic      |
//|    (940800)ゆえ同口座併用も可だが、−10%枠は口座単位＝合算DDに注意。 |
//|    相関≈0で合算DDは縮むが、両方を同口座に乗せると枠を共有する点に留意|
//|  ・週次%→実現DDは業者条件で変動。10年バスケットmaxDD−13.8%(フルサ |
//|    イズ)を踏まえ既定は保守。デモで実maxDDが−10%内か必ず確認。      |
//+------------------------------------------------------------------+
