//+------------------------------------------------------------------+
//|                 Chien_Parallel3_Crypto_Sjul_PROP.mq5             |
//|   第3並行ポートフォリオ・オールインワン(プロップ既定):             |
//|   CRYPTO(BTC/ETH 月曜LONG) + S-Jul(株価指数 7月季節LONG) を         |
//|   1チャート挿入。既存2口座(口座1=v7+v4+E5 / 口座2=E-Mon+E5)とは     |
//|   別口座/別業者で並走させる"3つ目の器"(docs/65)。                   |
//|                                                                   |
//|   ■ なぜ"第3の並行"か(docs/65): 口座1のコア=円月曜(v7)/FX(v4)、     |
//|     口座2のコア=指数月曜(E-Mon)。これら両方と無相関の材料だけで      |
//|     3つ目を組む(=真の第3系統)。N=130(docs/50)/N=164(docs/64)の      |
//|     網羅探索で、口座1/2のコアと被らず残った材料は実質2つ:           |
//|       ・CRYPTO(BTC/ETH 月曜LONG): 全戦略と無相関                    |
//|         (v7=0.06/v4=−0.10/E-Mon=0.16/E5=0.04, docs/54)。            |
//|       ・S-Jul(指数7月LONG): ★E-Mon相関 −0.31(負=指数月曜の分散源)。  |
//|     ∴ 口座3 = CRYPTO(核) + S-Jul(7月サテライト)。発火窓(週次/7月)が  |
//|       口座1/2と時間的にもずれ、同時DDしにくい。                     |
//|                                                                   |
//|   ■ ★正直な級(数字を盛らない/docs/54,65): 口座3は2口座より          |
//|     "1口座あたりの質は低い"。CRYPTOは【有意・高DD】級——docs/50で      |
//|     はOOS減衰/年次JK不合格で"核"としては棄却され、docs/54で別ブランチ |
//|     P2との収束により"衛星候補"として復活した位置づけ。素のmaxDDは     |
//|     −55%(=v7の−5%, E-Monの−14%より遥かに深い)。S-Julは             |
//|     SEASONAL-LEAD(実標本=年数10のみ)。∴ 狙いは"高収益"ではなく       |
//|     【総量拡大＋業者分散(全損回避)】。本資金前デモ前進検証必須。      |
//|                                                                   |
//|   ■ 本ファイル=プロップ既定(FundedNext/FTMO等2-step):               |
//|     ★CRYPTOは高DDゆえ小サイズ既定。攻め=CRYPTO週次1.20%/S-Jul月次     |
//|     1.00%・静的−10%/+8%停止/日次−4%・全停止フロア−9%。               |
//|     守りは P3_MANUAL で週次0.60/月次0.50・フロア−8%(プリセット同梱)。 |
//|     (インスタント運用は Chien_Parallel3_Crypto_Sjul_INSTANT.mq5)    |
//|                                                                   |
//|   ■ 内部2戦略(Magic分離で混線なし・Magic帯=950740):                 |
//|     CRYPTO: BTC/ETH 月曜 09/14UTC LONG・24h時間決済・週次予算を       |
//|             ショット数で割って合算DDを器に収める(v7/E-Monと同型)。    |
//|             SL=2.5ATR_H1(災害保険・暗号は広めに置く)。Magic base+1。 |
//|     S-Jul:  指数(US500/NAS100)を7月だけ等加重LONG・月跨ぎ翌月初決済。 |
//|             SL=2.5ATR_D1。Magic base+2。                           |
//|     口座ガード: 総合−10%枠の内側(既定−9%)で全停止。                |
//|                                                                   |
//|   ★1チャートに本EAを1つだけドロップ(どの銘柄/足でも可)。残高は自動。 |
//|     ⚠ 暗号可の業者でのみ動く。InpCryptoSymbols を実銘柄名に。        |
//|     ⚠ CRYPTO=有意・高DD / S-Jul=SEASONAL-LEAD(共に未確証)。本資金前  |
//|       にデモ前進検証(docs/29)必須。−10%が最終backstop。             |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.00"
#property strict
#property description "3rd parallel portfolio all-in-one (PROP default): CRYPTO(BTC/ETH Monday LONG)+S-Jul(equity-index July seasonal LONG). Per-strategy magics. CRYPTO=significant/high-DD, S-Jul=SEASONAL-LEAD: demo first."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

enum ENUM_P3_SCENARIO
{
   P3_INSTANT            = 0, // インスタント(守り寄り: トレーリング / 無目標)
   P3_PROP_BREAKTHROUGH  = 1, // プロップ突破(静的-10% / +8%目標 / 日次-4%)
   P3_MANUAL             = 2  // 手動(下の Crypto/Sjul 値・静的-10%)
};

input group "=== シナリオ（これ1つで倍率/比率/ルール自動）==="
input ENUM_P3_SCENARIO InpScenario = P3_PROP_BREAKTHROUGH; // ★本ファイル既定=プロップ突破
input bool   InpAcknowledgeLEAD = true;   // CRYPTO=有意・高DD / S-Jul=SEASONAL-LEAD。デモ/極小で承認=true

input group "=== 銘柄（業者の実銘柄名に合わせる・暗号可業者のみ）==="
input string InpCryptoSymbols = "BTCUSD,ETHUSD";   // CRYPTO: 暗号2つ(月曜LONG)
input string InpSjulSymbols   = "US500,NAS100";    // S-Jul: 指数バスケット(7月LONG)

input group "=== 口座/ガード ==="
input double InpInitialBalance   = 0.0;   // 0=口座残高を自動取得
input double InpMaxLossLimitPct  = 10.0;  // 失格ライン%(最終backstop)
input double InpAccountFloorDDPct= 9.0;   // 全停止ライン%(★攻め=9.0で-10%枠をほぼ使い切る/守りは8.0)

input group "=== 手動値（P3_MANUAL時のみ・2戦略の配分）==="
input double InpCryptoWeeklyPct = 1.20;   // CRYPTO 週次リスク%(★高DDゆえ小さめ。守り0.60)
input double InpSjulMonthPct    = 1.00;   // S-Jul 月次リスク%(サテライト。守り0.50)

input group "=== CRYPTO 設定（暗号 月曜LONG・リスク予算化）==="
input int    InpEntryWeekday  = 1;        // 1=月曜(MQL: 0=日..6=土)
input string InpEntryHoursUTC = "9,14";   // 月曜の建て時刻(2点サンプリング)。暗号は24h取引=セッション制約は緩い
input int    InpShotsPerWeek  = 4;        // 暗号2×時刻2=4ショット。週次予算をこれで割る
input int    InpHoldHours     = 24;       // 各ショット24h保有→時間決済
input int    InpAtrPeriodH1   = 24;       // H1×24≒日次ATR
input double InpCatastropheATR= 2.5;      // SL=2.5×ATR(災害用・暗号は広く置く)
input double InpMinStopPts    = 50.0;     // 暗号の最小SL(ポイント)
input double InpMaxStopPts    = 50000000.0;// 暗号の最大SL(ポイント・高価格=大きめ許容)
input double InpMaxSpreadPts  = 500000.0; // 暗号スプレッド上限(ポイント・広め許容)

input group "=== S-Jul 設定（株価指数 季節性 month-of-year）==="
input string InpSeasonMonths  = "7";      // 保有する暦月(CSV)。既定=7(S-Jul)。S-Nov併用は "7,11"(冗長承知)
input int    InpEntryDom      = 1;        // 月内 何営業日目に建てるか(1=月初第1営業日)。月跨ぎで自動決済
input int    InpAtrPeriodD1   = 14;       // S-Jul 日次ATR期間
input double InpSjulCatATR    = 2.5;      // S-Jul 災害SL=2.5×ATR(D1)
input double InpSjulMinStopPts= 50.0;     // 指数の最小SL(ポイント)
input double InpSjulMaxSpread = 1500.0;   // 指数スプレッド上限(ポイント)

input group "=== 共通 ==="
input double InpMinLot = 0.01;
input double InpMaxLot = 50.0;
input long   InpMagicBase = 950740;       // CRYPTO=+1 / S-Jul=+2 (既存950710/720/730と非衝突)
input int    InpSlippagePoints = 30;
input bool   InpVerboseLog = true;

//==================================================================
CTrade        trade;
CPositionInfo posinfo;

string   g_crypto[]; string g_sjul[]; int g_hours[]; int g_months[];
int      g_atrH1[]; int g_atrD1[];
datetime g_lastShot[];     // [cryptoIdx*nHours + hourIdx]
datetime g_lastEntryMonth=0;
double   g_initBal=0.0, g_cryptoWeekly=1.20, g_sjulMonth=1.00, g_maxLossPct=10.0;
bool     g_useTrailing=true, g_useProfitStop=false, g_useDailyStop=false;
double   g_profitPct=0.0, g_dailyStopPct=0.0, g_floorBufPct=1.0;
double   g_peakEquity=0.0, g_trailFloor=0.0, g_dayStartEq=0.0;
datetime g_curDay=0; bool g_halted=false, g_dayBlocked=false;
string   g_scenName="";
long     g_mCrypto=0, g_mSjul=0;

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
   if(StringFind(U,"BTC")>=0 || StringFind(U,"XBT")>=0 || StringFind(U,"BITCOIN")>=0){
      bases[nb++]="BTCUSD"; bases[nb++]="BTCUSDT"; bases[nb++]="XBTUSD"; bases[nb++]="BTC/USD"; bases[nb++]="BITCOIN"; bases[nb++]="BTCUSD.cash"; }
   else if(StringFind(U,"ETH")>=0 || StringFind(U,"ETHER")>=0){
      bases[nb++]="ETHUSD"; bases[nb++]="ETHUSDT"; bases[nb++]="ETH/USD"; bases[nb++]="ETHEREUM"; bases[nb++]="ETHUSD.cash"; }
   else if(StringFind(U,"SPX")>=0 || StringFind(U,"500")>=0){
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

void ResolveScenario()
{
   g_cryptoWeekly=InpCryptoWeeklyPct; g_sjulMonth=InpSjulMonthPct;
   g_useTrailing=false; g_useProfitStop=false; g_useDailyStop=false;
   g_profitPct=0; g_dailyStopPct=0; g_maxLossPct=InpMaxLossLimitPct;
   g_floorBufPct=MathMax(0.0, InpMaxLossLimitPct-InpAccountFloorDDPct); // 全停止= -InpAccountFloorDDPct
   g_scenName="MANUAL";
   if(InpScenario==P3_INSTANT){
      // ★インスタント攻め。トレーリング枠。CRYPTO高DDゆえ控えめ週次0.80/月次0.60。
      g_scenName="INSTANT_AGGR"; g_cryptoWeekly=0.80; g_sjulMonth=0.60;
      g_useTrailing=true; g_useProfitStop=false; g_useDailyStop=false;
   } else if(InpScenario==P3_PROP_BREAKTHROUGH){
      // ★プロップ攻め。静的-10%/+8%/日次-4%。CRYPTO高DDゆえ週次1.20/月次1.00。
      g_scenName="PROP_AGGR"; g_cryptoWeekly=1.20; g_sjulMonth=1.00;
      g_useTrailing=false; g_useProfitStop=true; g_profitPct=8.0;
      g_useDailyStop=true; g_dailyStopPct=4.0;
   }
}

int OnInit()
{
   if(!InpAcknowledgeLEAD){ Print("[STOP] CRYPTO=有意・高DD / S-Jul=SEASONAL-LEAD。InpAcknowledgeLEAD=trueで承認(デモ/極小)。"); return INIT_FAILED; }
   int nc=SplitCSV(InpCryptoSymbols,g_crypto);
   int nj=SplitCSV(InpSjulSymbols,g_sjul);
   int nh=SplitHours(InpEntryHoursUTC,g_hours);
   int nm=SplitInts(InpSeasonMonths,g_months);
   if(nc==0||nj==0||nh==0||nm==0){ Print("シンボル/時刻/月のパース失敗"); return INIT_FAILED; }
   ResolveScenario();
   g_mCrypto=InpMagicBase+1; g_mSjul=InpMagicBase+2;
   g_initBal=(InpInitialBalance>0.0)?InpInitialBalance:AccountInfoDouble(ACCOUNT_BALANCE);
   if(g_initBal<=0.0) g_initBal=AccountInfoDouble(ACCOUNT_EQUITY);

   ArrayResize(g_atrH1,nc); ArrayResize(g_atrD1,nj);
   ArrayResize(g_lastShot,nc*nh); ArrayInitialize(g_lastShot,0);

   for(int i=0;i<nc;i++){
      string r=ResolveSymbol(g_crypto[i]); g_atrH1[i]=INVALID_HANDLE;
      if(r==""){ PrintFormat("⚠ CRYPTO銘柄 %s 見つからず→スキップ(暗号不可業者か銘柄名違い)",g_crypto[i]); continue; }
      if(r!=g_crypto[i]) PrintFormat("[銘柄解決] CRYPTO %s → %s",g_crypto[i],r);
      g_crypto[i]=r; g_atrH1[i]=iATR(g_crypto[i],PERIOD_H1,InpAtrPeriodH1);
   }
   for(int i=0;i<nj;i++){
      string r=ResolveSymbol(g_sjul[i]); g_atrD1[i]=INVALID_HANDLE;
      if(r==""){ PrintFormat("⚠ S-Jul銘柄 %s 見つからず→スキップ",g_sjul[i]); continue; }
      if(r!=g_sjul[i]) PrintFormat("[銘柄解決] S-Jul %s → %s",g_sjul[i],r);
      g_sjul[i]=r; g_atrD1[i]=iATR(g_sjul[i],PERIOD_D1,InpAtrPeriodD1);
   }
   trade.SetDeviationInPoints(InpSlippagePoints);
   g_peakEquity=g_initBal; g_trailFloor=g_initBal*(1.0-g_maxLossPct/100.0);
   ResetDay(TimeCurrent());
   PrintFormat("[INIT P3 %s] initBal=%.0f CRYPTO週次=%.2f%% S-Jul月次=%.2f%% trailing=%s profit=%s(%.0f) daily=%s",
      g_scenName,g_initBal,g_cryptoWeekly,g_sjulMonth,(g_useTrailing?"Y":"N"),
      (g_useProfitStop?"Y":"N"),g_profitPct,(g_useDailyStop?"Y":"N"));
   if(InpVerboseLog) Print("[NOTE] 第3並行ポート=CRYPTO(核,高DD)+S-Jul(7月)。1チャートに本EA1つだけ。Magic分離(",g_mCrypto,"/",g_mSjul,")。共に未確証=デモ前提。");
   EventSetTimer(30);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){
   EventKillTimer();
   for(int i=0;i<ArraySize(g_atrH1);i++) if(g_atrH1[i]!=INVALID_HANDLE) IndicatorRelease(g_atrH1[i]);
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

double BreachFloor(double equity)
{
   if(!g_useTrailing) return g_initBal*(1.0-g_maxLossPct/100.0);
   if(equity>g_peakEquity) g_peakEquity=equity;
   double raw=g_peakEquity-g_initBal*g_maxLossPct/100.0;
   double capped=MathMin(raw,g_initBal);
   if(capped>g_trailFloor) g_trailFloor=capped;
   return g_trailFloor;
}

int CountPosMagic(long magic){
   int n=0;
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()==magic) n++; }
   return n;
}
void CloseMagic(long magic, string why){
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()==magic){
         if(trade.PositionClose(tk) && InpVerboseLog) PrintFormat("[CLOSE %s] %s",why,posinfo.Symbol()); } }
}
bool IsMine(long m){ return (m==g_mCrypto||m==g_mSjul); }
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

   ManageCryptoExit();
   ManageSjulExit(now);

   bool blockNew = (g_useProfitStop && equity>=g_initBal*(1.0+g_profitPct/100.0)) || g_dayBlocked;
   if(blockNew) return;

   EntriesCrypto(utc);
   EntriesSjul(now);
}

//===== CRYPTO (暗号 月曜LONG 多ショット・リスク予算化, v7/E-Monと同型) =====
void ManageCryptoExit()
{
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()!=g_mCrypto) continue;
      int held=(int)(TimeCurrent()-(datetime)posinfo.Time());
      if(held>=InpHoldHours*3600){ if(trade.PositionClose(tk)&&InpVerboseLog)
         PrintFormat("[CRYPTO TIME EXIT] %s",posinfo.Symbol()); }
   }
}
void EntriesCrypto(datetime utc)
{
   MqlDateTime u; TimeToStruct(utc,u);
   if(u.day_of_week!=InpEntryWeekday) return;
   int slot=-1; for(int h=0;h<ArraySize(g_hours);h++) if(u.hour==g_hours[h]){ slot=h; break; }
   if(slot<0) return;
   datetime hourBar=utc-(utc%3600); int nh=ArraySize(g_hours);
   double perShot=g_cryptoWeekly/(InpShotsPerWeek>0?InpShotsPerWeek:1);
   trade.SetExpertMagicNumber(g_mCrypto);
   for(int s=0;s<ArraySize(g_crypto);s++){
      if(g_atrH1[s]==INVALID_HANDLE) continue;
      int key=s*nh+slot;
      if(g_lastShot[key]==hourBar) continue;
      string sym=g_crypto[s]; double pt=PointOf(sym); if(pt<=0) continue;
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
      if(trade.Buy(lots,sym,0.0,sl,0.0,StringFormat("Crypto_%s_h%d",sym,g_hours[slot])))
         { if(InpVerboseLog) PrintFormat("[CRYPTO ENTRY] LONG %s h%dUTC lots=%.2f SL=%.2f perShot=%.3f%%",sym,g_hours[slot],lots,sl,perShot); }
   }
}

//===== S-Jul (株価指数 7月季節LONG・月跨ぎ翌月初決済) =====
bool IsSeasonMonth(int mon){
   for(int i=0;i<ArraySize(g_months);i++) if(g_months[i]==mon) return true;
   return false;
}
// 当月の最初の取引日から数えて今日が何営業日目か(D1足の日付で概算・休場は足が無く自然にスキップ)
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
void ManageSjulExit(datetime now)
{
   // 季節月を跨いだら(=対象月でなくなったら)翌月初の寄付で全決済。バックテスト定義(対象月末→翌月初open)と一致。
   MqlDateTime t; TimeToStruct(now,t);
   if(CountPosMagic(g_mSjul)>0 && !IsSeasonMonth(t.mon)){
      CloseMagic(g_mSjul,"SJUL_SEASON_END"); g_lastEntryMonth=0;
   }
}
void EntriesSjul(datetime now)
{
   MqlDateTime t; TimeToStruct(now,t);
   if(!IsSeasonMonth(t.mon)) return;
   MqlDateTime mk; TimeToStruct(now,mk); mk.day=1; mk.hour=0; mk.min=0; mk.sec=0;
   datetime thisMonth=StructToTime(mk);
   if(g_lastEntryMonth==thisMonth) return;       // 当月建て済み
   if(CountPosMagic(g_mSjul)>0) return;
   if(ArraySize(g_sjul)==0) return;
   int dom=DomFromStart(g_sjul[0],now);
   if(dom<InpEntryDom) return;

   int ns=ArraySize(g_sjul);
   double perSym=g_sjulMonth/(ns>0?ns:1);
   trade.SetExpertMagicNumber(g_mSjul);
   for(int i=0;i<ns;i++){
      if(g_atrD1[i]==INVALID_HANDLE) continue;
      string sym=g_sjul[i]; double pt=PointOf(sym); if(pt<=0) continue;
      double atr=AtrAt(g_atrD1[i]); if(atr<=0) continue;
      double sd=InpSjulCatATR*atr; double sp=sd/pt;
      if(sp<InpSjulMinStopPts){ sp=InpSjulMinStopPts; sd=sp*pt; }
      double ask=SymbolInfoDouble(sym,SYMBOL_ASK), bid=SymbolInfoDouble(sym,SYMBOL_BID);
      if(ask<=0||bid<=0) continue;
      if((ask-bid)/pt>InpSjulMaxSpread) continue;
      double riskMoney=g_initBal*(perSym/100.0);
      double lots=LotsFor(sym,sd,riskMoney); if(lots<InpMinLot) continue;
      int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      double sl=NormalizeDouble(ask-sd,dg);
      if(trade.Buy(lots,sym,0.0,sl,0.0,StringFormat("Sjul_%s",sym)))
         { if(InpVerboseLog) PrintFormat("[S-Jul ENTRY] LONG %s lots=%.2f SL=%.2f perSym=%.3f%%",sym,lots,sl,perSym); }
   }
   g_lastEntryMonth=thisMonth;
}
//+------------------------------------------------------------------+
//| 残存リスク(誠実な記録, docs/65):                                 |
//|  ・CRYPTO=【有意・高DD】(STRONG-LEAD未満)。docs/50ではOOS減衰/年次  |
//|    JK不合格で"核"棄却→docs/54で別ブランチP2収束により"衛星候補"。   |
//|    素のmaxDD≈−55%(=v7−5%/E-Mon−14%より遥かに深い)。∴小サイズ厳守。 |
//|    週次予算をショット数で割り合算DDを器に収める前提。              |
//|  ・S-Jul=SEASONAL-LEAD。単月季節性=実サンプルは年数(10)のみ。       |
//|    Bonferroni未達=v7/E-Mon と同じ天井。ADOPT不可。サテライト限定。  |
//|  ・無相関の根拠(docs/54/65): CRYPTO⇄全戦略≈低(v7=.06/v4=−.10/      |
//|    E-Mon=.16)・S-Jul⇄E-Mon=−0.31。∴口座1/2と同時DDしにくい第3の器。 |
//|    狙いは高収益でなく【総量拡大＋業者分散(全損回避)】。            |
//|  ・暗号の実スプレッド/スワップ/取引時間/プロップ規約(暗号可否・週末  |
//|    建て可否)は業者差が極端に大きい→デモで実測必須。多くのプロップは |
//|    暗号不可/別ルール。本EAは暗号可業者専用。                       |
//|  ・S-Jul 1ヶ月保有=指数CFDのスワップ累積/配当調整あり→デモで実測。  |
//|  ・CRYPTO と S-Jul は資産クラスが別(暗号/指数)→銘柄共有なし=        |
//|    Magic分離で混線しないが、ネッティング口座は同銘柄の相殺に注意。  |
//|  ・1チャートに本EAは1つだけ(複数/他EAと同口座でMagic衝突回避)。     |
//|    既存ポート(940710/720)・並行ポート(950710/720)・季節EA(950730)  |
//|    とは別Magic帯(950740)で衝突しない。                             |
//|  ・FTMO等2-stepは日次-5%/+10%目標→ InpScenario=P3_MANUAL +         |
//|    InpAccountFloorDDPct/日次は規約に合わせる(docs/51と同方針)。     |
//|  ・★必ず別口座/別業者で口座1・口座2と並走。同口座に複数ポートを     |
//|    乗せると証拠金/ガードが干渉する(docs/51 §4)。                   |
//+------------------------------------------------------------------+
