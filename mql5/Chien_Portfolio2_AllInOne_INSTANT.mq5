//+------------------------------------------------------------------+
//|                    Chien_Portfolio2_AllInOne_INSTANT.mq5          |
//|   第2(並走)ポートフォリオ オールインワン(インスタント既定)。       |
//|   検証済み【機構】を、現行が触らない【別ユニバース】へ展開:         |
//|     MR = v4機構(日足k≥4合議・平均回帰)を【別クロス9本】へ           |
//|     RP = E5機構(月次リスクパリティTSMOM)を【別バスケット】へ        |
//|   v7(円月曜)は意図的に複製しない=2口座が同じ取引を一切共有せず、    |
//|   真に並走できる第2口座になる(docs/50)。                           |
//|                                                                   |
//|   ■ なぜ別ユニバースか(docs/50): 同じv7/v4/E5を2口座で重ねると相関し |
//|     『並走』にならない(プロップは相関/コピー口座を嫌う・破綻時に共倒れ)。|
//|     検証済みの"機構"を非重複ユニバースへ移すことで、同じ9ゲート基準で |
//|     合格を狙いつつ、現行と低相関の独立した第2の収益源を作る。       |
//|                                                                   |
//|   ■ 本ファイル=インスタント既定 ★攻め(Blueberry等):                 |
//|     MR 0.30%/トレード / RP 0.60% legRisk・−10%トレーリング/無目標。  |
//|     全停止フロア=−9%(枠を使い切る攻め)。守りは PORT_MANUAL 0.15/0.30。|
//|     ⚠攻め=業者破綻/規約変更リスク前提『速く出金・口座に大金を置かない』|
//|       運用。出金は毎サイクル必ず実行。                              |
//|     (プロップ審査は Chien_Portfolio2_AllInOne_PROP.mq5 を使う)       |
//|                                                                   |
//|   ■ 内部2戦略(Magic分離で混線なし):                                 |
//|     MR: 別クロス9本 日足 4条件合議k≥4 で両建て・SL1.5ATR_D1/RR1.2/8日 |
//|     RP: 別バスケット 月初TSMOM両建て・逆ボラ加重/SL2.5ATR_MN1        |
//|     口座ガード: 総合−10%枠の内側(既定−9%)で全停止。                |
//|                                                                   |
//|   ★1チャートに本EAを1つだけドロップ(どの銘柄/足でも可)。残高は自動。|
//|     銘柄名は業者仕様に合わせ InpMR/ InpRP Symbols を編集。           |
//|   ⚠ MR=v4機構(現行ADOPT)/RP=E5機構(現行STRONG-LEAD)だが、別ユニバース|
//|     での級・相関はユーザーの10年Colab(notebooks/portfolio2_validate)|
//|     で確定し、本資金前にデモ前進検証(docs/29)必須。−10%が最終backstop。|
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "2.00"
#property strict
#property description "Parallel(2nd) portfolio all-in-one (INSTANT default): MR(v4 mechanism on disjoint crosses)+RP(E5 mechanism on disjoint basket). No v7. Per-strategy magics. Validate/correlation via notebooks/portfolio2_validate."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

enum ENUM_PORT2_SCENARIO
{
   PORT_INSTANT            = 0, // インスタント(攻め: トレーリング / 無目標)
   PORT_PROP_BREAKTHROUGH  = 1, // プロップ突破(静的-10% / +8%目標 / 日次-4%)
   PORT_MANUAL             = 2  // 手動(下の MR/RP 値・静的-10%)
};

input group "=== シナリオ（これ1つで倍率/比率/ルール自動）==="
input ENUM_PORT2_SCENARIO InpScenario = PORT_INSTANT; // ★本ファイル既定=インスタント
input bool   InpAcknowledgeLEAD = true;   // MR=v4機構/RP=E5機構。別ユニバースは要デモ。承認=true

input group "=== 銘柄（業者の実銘柄名に合わせる・現行と非重複）==="
input string InpMRSymbols  = "EURGBP,EURAUD,EURCHF,EURCAD,GBPAUD,AUDCAD,AUDNZD,GBPCHF,CADJPY"; // MR: 別クロス9本
input string InpRPSymbols  = "XAGUSD,USOIL,UK100,JP225";   // RP: 銀/原油/英FTSE/日経225

input group "=== 口座/ガード ==="
input double InpInitialBalance   = 0.0;   // 0=口座残高を自動取得
input double InpMaxLossLimitPct  = 10.0;  // 失格ライン%
input double InpAccountFloorDDPct= 9.0;   // 全停止ライン%(★攻め=9.0/守りは8.0)

input group "=== 手動値（PORT_MANUAL時のみ・2戦略の配分）==="
input double InpMRRiskPerTradePct= 0.15;  // MR 1トレードあたりリスク%
input double InpRPLegRiskPct     = 0.30;  // RP legRisk%(各レッグ月次σ)

input group "=== MR 設定（日足k≥4合議・v4機構と同一）==="
input int    InpMR_RSI       = 14;
input double InpMR_RSIlo     = 35.0;
input double InpMR_RSIhi     = 65.0;
input int    InpMR_BBwin     = 20;
input double InpMR_BBz       = 1.5;
input int    InpMR_streak    = 3;
input double InpMR_dayMovePct= 0.5;       // 当日±0.5%
input int    InpMR_ATR       = 14;        // ATR(D1)
input double InpMR_SLatr     = 1.5;       // SL=1.5*ATR(D1)
input double InpMR_RR        = 1.2;       // TP=RR*SL
input int    InpMR_MaxHoldDays= 8;

input group "=== RP 設定（E5機構と同一）==="
input int    InpLB1=1, InpLB2=3, InpLB3=6, InpLB4=12;
input bool   InpAllowShort = true;
input int    InpAtrPeriodMN1= 6;
input double InpCatATR_RP  = 2.5;

input group "=== 共通 ==="
input double InpMinLot = 0.01;
input double InpMaxLot = 50.0;
input long   InpMagicBase = 940730;       // MR=+1 / RP=+2 (現行Portfolio/Portfolio3と非衝突)
input int    InpSlippagePoints = 30;
input bool   InpVerboseLog = true;

//==================================================================
CTrade        trade;
CPositionInfo posinfo;

string   g_mr[]; string g_rp[];
int      g_atrD1[]; int g_rsiD1[]; int g_atrMN1[];
datetime g_lastMRBar[];    // [mrIdx]
datetime g_lastMonth[];    // [rpIdx]
double   g_initBal=0.0, g_mrrisk=0.15, g_rpleg=0.30, g_maxLossPct=10.0;
bool     g_useTrailing=true, g_useProfitStop=false, g_useDailyStop=false;
double   g_profitPct=0.0, g_dailyStopPct=0.0, g_floorBufPct=1.0;
double   g_peakEquity=0.0, g_trailFloor=0.0, g_dayStartEq=0.0;
datetime g_curDay=0; bool g_halted=false, g_dayBlocked=false;
string   g_scenName="";
long     g_mMR=0, g_mRP=0;

//==================================================================
int SplitCSV(string csv, string &arr[])
{
   string p[]; int k=StringSplit(csv, ',', p); int m=0; ArrayResize(arr,k);
   for(int i=0;i<k;i++){ string s=p[i]; StringTrimLeft(s); StringTrimRight(s);
      if(StringLen(s)>0){ arr[m]=s; m++; } }
   ArrayResize(arr,m); return m;
}
double PipOf(string s){ return (StringFind(s,"JPY")>=0)? 0.01 : 0.0001; }

string ResolveSymbol(string want)
{
   string suf[]={"",".pi",".raw",".ecn",".stp",".pro",".cash",".r",".c",".m","m",".spot","-cash",".sd","+",".i","_SB","_raw",".a",".z"};
   string bases[]; ArrayResize(bases,40); int nb=0;
   bases[nb++]=want;
   string U=want; StringToUpper(U);
   if(StringFind(U,"XAG")>=0 || StringFind(U,"SILVER")>=0){
      bases[nb++]="XAGUSD"; bases[nb++]="SILVER"; bases[nb++]="SILVERUSD"; }
   else if(StringFind(U,"OIL")>=0 || StringFind(U,"WTI")>=0 || StringFind(U,"CRUDE")>=0 || StringFind(U,"USOUSD")>=0){
      bases[nb++]="USOIL"; bases[nb++]="WTI"; bases[nb++]="CL"; bases[nb++]="CRUDE"; bases[nb++]="OILUSD"; bases[nb++]="USOIL.cash"; bases[nb++]="WTICOUSD"; }
   else if(StringFind(U,"UK100")>=0 || StringFind(U,"FTSE")>=0 || StringFind(U,"UK_100")>=0){
      bases[nb++]="UK100"; bases[nb++]="FTSE100"; bases[nb++]="FTSE"; bases[nb++]="GB100"; bases[nb++]="UK100.cash"; bases[nb++]="UK_100"; }
   else if(StringFind(U,"JP225")>=0 || StringFind(U,"NIKKEI")>=0 || StringFind(U,"JPN225")>=0 || StringFind(U,"N225")>=0){
      bases[nb++]="JP225"; bases[nb++]="JPN225"; bases[nb++]="NIKKEI"; bases[nb++]="NI225"; bases[nb++]="JP225.cash"; bases[nb++]="JPN_225"; bases[nb++]="N225"; }
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
   g_mrrisk=InpMRRiskPerTradePct; g_rpleg=InpRPLegRiskPct;
   g_useTrailing=false; g_useProfitStop=false; g_useDailyStop=false;
   g_profitPct=0; g_dailyStopPct=0; g_maxLossPct=InpMaxLossLimitPct;
   g_floorBufPct=MathMax(0.0, InpMaxLossLimitPct-InpAccountFloorDDPct); // 全停止= -InpAccountFloorDDPct
   g_scenName="MANUAL";
   if(InpScenario==PORT_INSTANT){
      // ★インスタント攻め: MR0.30%/RP0.60%・トレーリング枠(代表サイズ・要デモ確定)。
      g_scenName="INSTANT_AGGR"; g_mrrisk=0.30; g_rpleg=0.60;
      g_useTrailing=true; g_useProfitStop=false; g_useDailyStop=false;
   } else if(InpScenario==PORT_PROP_BREAKTHROUGH){
      // ★プロップ突破攻め: MR0.75%/RP1.50%・静的-10%/+8%/日次-4%。
      g_scenName="PROP_AGGR"; g_mrrisk=0.75; g_rpleg=1.50;
      g_useTrailing=false; g_useProfitStop=true; g_profitPct=8.0;
      g_useDailyStop=true; g_dailyStopPct=4.0;
   }
}

int OnInit()
{
   if(!InpAcknowledgeLEAD){ Print("[STOP] MR=v4機構/RP=E5機構を別ユニバースへ。InpAcknowledgeLEAD=trueで承認(デモ/極小)。"); return INIT_FAILED; }
   int nm=SplitCSV(InpMRSymbols,g_mr);
   int nr=SplitCSV(InpRPSymbols,g_rp);
   if(nm==0||nr==0){ Print("シンボルのパース失敗"); return INIT_FAILED; }
   ResolveScenario();
   g_mMR=InpMagicBase+1; g_mRP=InpMagicBase+2;
   g_initBal=(InpInitialBalance>0.0)?InpInitialBalance:AccountInfoDouble(ACCOUNT_BALANCE);
   if(g_initBal<=0.0) g_initBal=AccountInfoDouble(ACCOUNT_EQUITY);

   ArrayResize(g_atrD1,nm); ArrayResize(g_rsiD1,nm); ArrayResize(g_atrMN1,nr);
   ArrayResize(g_lastMRBar,nm); ArrayInitialize(g_lastMRBar,0);
   ArrayResize(g_lastMonth,nr); ArrayInitialize(g_lastMonth,0);

   for(int i=0;i<nm;i++){
      string r=ResolveSymbol(g_mr[i]); g_atrD1[i]=INVALID_HANDLE; g_rsiD1[i]=INVALID_HANDLE;
      if(r==""){ PrintFormat("⚠ MR銘柄 %s 見つからず→スキップ",g_mr[i]); continue; }
      if(r!=g_mr[i]) PrintFormat("[銘柄解決] MR %s → %s",g_mr[i],r);
      g_mr[i]=r;
      g_atrD1[i]=iATR(g_mr[i],PERIOD_D1,InpMR_ATR);
      g_rsiD1[i]=iRSI(g_mr[i],PERIOD_D1,InpMR_RSI,PRICE_CLOSE);
   }
   for(int i=0;i<nr;i++){
      string r=ResolveSymbol(g_rp[i]); g_atrMN1[i]=INVALID_HANDLE;
      if(r==""){ PrintFormat("⚠ RP銘柄 %s 見つからず→スキップ",g_rp[i]); continue; }
      if(r!=g_rp[i]) PrintFormat("[銘柄解決] RP %s → %s",g_rp[i],r);
      g_rp[i]=r; g_atrMN1[i]=iATR(g_rp[i],PERIOD_MN1,InpAtrPeriodMN1);
   }
   trade.SetDeviationInPoints(InpSlippagePoints);
   g_peakEquity=g_initBal; g_trailFloor=g_initBal*(1.0-g_maxLossPct/100.0);
   ResetDay(TimeCurrent());
   PrintFormat("[INIT P2 %s] initBal=%.0f MR/trade=%.2f%% RPleg=%.2f%% trailing=%s profit=%s(%.0f) daily=%s",
      g_scenName,g_initBal,g_mrrisk,g_rpleg,(g_useTrailing?"Y":"N"),
      (g_useProfitStop?"Y":"N"),g_profitPct,(g_useDailyStop?"Y":"N"));
   if(InpVerboseLog) Print("[NOTE] 1チャートに本EA1つだけ。MR+RPを内部運用。Magic分離(",g_mMR,"/",g_mRP,")。別ユニバース=現行と非重複・要デモ。");
   EventSetTimer(30);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){
   EventKillTimer();
   for(int i=0;i<ArraySize(g_atrD1);i++) if(g_atrD1[i]!=INVALID_HANDLE) IndicatorRelease(g_atrD1[i]);
   for(int i=0;i<ArraySize(g_rsiD1);i++) if(g_rsiD1[i]!=INVALID_HANDLE) IndicatorRelease(g_rsiD1[i]);
   for(int i=0;i<ArraySize(g_atrMN1);i++) if(g_atrMN1[i]!=INVALID_HANDLE) IndicatorRelease(g_atrMN1[i]);
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
bool IsMine(long m){ return (m==g_mMR||m==g_mRP); }
void CloseAllMine(string why){
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(IsMine(posinfo.Magic())) trade.PositionClose(tk); }
   if(InpVerboseLog) PrintFormat("[CLOSE ALL %s]",why);
}

//==================================================================
void OnTimer()
{
   datetime now=TimeCurrent();
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

   ManageMRExit();
   ManageRP();

   bool blockNew = (g_useProfitStop && equity>=g_initBal*(1.0+g_profitPct/100.0)) || g_dayBlocked;
   if(blockNew) return;

   EntriesMR();
   EntriesRP();
}

//===== MR (日足k≥4合議・v4機構) =====
int MRSignal(string sym, int rsiHandle)
{
   double c[]; ArraySetAsSeries(c,true);
   int need=MathMax(InpMR_BBwin+2, InpMR_streak+3);
   if(CopyClose(sym,PERIOD_D1,1,need+2,c)<need+1) return 0;   // c[0]=直近確定足
   double rb[1];
   if(rsiHandle==INVALID_HANDLE || CopyBuffer(rsiHandle,0,1,1,rb)<1) return 0;
   double rsi=rb[0];
   double mean=0; for(int k=1;k<=InpMR_BBwin;k++) mean+=c[k]; mean/=InpMR_BBwin;
   double var=0; for(int k=1;k<=InpMR_BBwin;k++) var+=(c[k]-mean)*(c[k]-mean); var/=(InpMR_BBwin-1);
   double sd=MathSqrt(var); double z=(sd>0)?(c[0]-mean)/sd:0.0;
   int down=0; for(int k=0;k<12;k++){ if(c[k]<c[k+1]) down++; else break; }
   int up=0;   for(int k=0;k<12;k++){ if(c[k]>c[k+1]) up++;   else break; }
   double ret=(c[1]!=0)?(c[0]-c[1])/c[1]:0.0; double mv=InpMR_dayMovePct/100.0;
   int buy = (rsi<InpMR_RSIlo?1:0)+(z<-InpMR_BBz?1:0)+(down>=InpMR_streak?1:0)+(ret<-mv?1:0);
   int sell= (rsi>InpMR_RSIhi?1:0)+(z> InpMR_BBz?1:0)+(up  >=InpMR_streak?1:0)+(ret> mv?1:0);
   if(buy>=4 && buy>sell) return 1;
   if(sell>=4 && sell>buy && InpAllowShort) return -1;
   return 0;
}
void ManageMRExit()
{
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()!=g_mMR) continue;
      int heldDays=(int)((TimeCurrent()-(datetime)posinfo.Time())/86400);
      if(heldDays>=InpMR_MaxHoldDays){ if(trade.PositionClose(tk)&&InpVerboseLog)
         PrintFormat("[MR TIME EXIT %dd] %s",heldDays,posinfo.Symbol()); }
   }
}
void EntriesMR()
{
   trade.SetExpertMagicNumber(g_mMR);
   for(int i=0;i<ArraySize(g_mr);i++){
      if(g_atrD1[i]==INVALID_HANDLE) continue;
      string sym=g_mr[i];
      datetime db=(datetime)iTime(sym,PERIOD_D1,0);
      if(db==0 || db==g_lastMRBar[i]) continue;   // 1日1回
      g_lastMRBar[i]=db;
      if(CountPos(sym,g_mMR)>0) continue;          // 既存MR建玉があれば積まない
      int sig=MRSignal(sym,g_rsiD1[i]);
      if(sig==0) continue;
      double atr=AtrAt(g_atrD1[i]); if(atr<=0) continue;
      double sd=InpMR_SLatr*atr; double tpd=InpMR_RR*sd;
      double riskMoney=g_initBal*(g_mrrisk/100.0);
      double lots=LotsFor(sym,sd,riskMoney); if(lots<InpMinLot) continue;
      int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      if(sig>0){ double e=SymbolInfoDouble(sym,SYMBOL_ASK);
         double sl=NormalizeDouble(e-sd,dg), tp=NormalizeDouble(e+tpd,dg);
         if(trade.Buy(lots,sym,0.0,sl,tp,"MR_"+sym) && InpVerboseLog) PrintFormat("[MR ENTRY] LONG %s lots=%.2f SL=%.5f TP=%.5f",sym,lots,sl,tp); }
      else     { double e=SymbolInfoDouble(sym,SYMBOL_BID);
         double sl=NormalizeDouble(e+sd,dg), tp=NormalizeDouble(e-tpd,dg);
         if(trade.Sell(lots,sym,0.0,sl,tp,"MR_"+sym) && InpVerboseLog) PrintFormat("[MR ENTRY] SHORT %s lots=%.2f SL=%.5f TP=%.5f",sym,lots,sl,tp); }
   }
}

//===== RP (E5機構・別バスケット) =====
int RPSignal(string sym)
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
void ManageRP(){ /* RPの新規/反転は EntriesRP で処理(月初)。SLは建玉付帯 */ }
void EntriesRP()
{
   trade.SetExpertMagicNumber(g_mRP);
   for(int i=0;i<ArraySize(g_rp);i++){
      if(g_atrMN1[i]==INVALID_HANDLE) continue;
      string sym=g_rp[i];
      datetime mb=(datetime)iTime(sym,PERIOD_MN1,0);
      if(mb==0 || mb==g_lastMonth[i]) continue;
      g_lastMonth[i]=mb;
      int sig=RPSignal(sym); int cur=DirOf(sym,g_mRP);
      if(sig==0){ if(cur!=0) CloseSymMagic(sym,g_mRP,"RP_FLAT"); continue; }
      if(cur==sig) continue;
      if(cur!=0) CloseSymMagic(sym,g_mRP,"RP_FLIP");
      double atr=AtrAt(g_atrMN1[i]); if(atr<=0) continue;
      double equity=AccountInfoDouble(ACCOUNT_EQUITY);
      double riskMoney=equity*(g_rpleg/100.0);
      double lots=LotsFor(sym,atr,riskMoney); if(lots<InpMinLot) continue;
      double sd=InpCatATR_RP*atr; int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      if(sig>0){ double e=SymbolInfoDouble(sym,SYMBOL_ASK); double sl=NormalizeDouble(e-sd,dg);
         if(trade.Buy(lots,sym,0.0,sl,0.0,"RP_"+sym) && InpVerboseLog) PrintFormat("[RP ENTRY] LONG %s lots=%.2f",sym,lots); }
      else     { double e=SymbolInfoDouble(sym,SYMBOL_BID); double sl=NormalizeDouble(e+sd,dg);
         if(trade.Sell(lots,sym,0.0,sl,0.0,"RP_"+sym) && InpVerboseLog) PrintFormat("[RP ENTRY] SHORT %s lots=%.2f",sym,lots); }
   }
}
//+------------------------------------------------------------------+
//| 残存リスク(誠実な記録):                                          |
//|  ・MR=v4機構(現行ADOPT, docs/42)/RP=E5機構(現行STRONG-LEAD, docs/31)|
//|    だが【別ユニバース】での級・現行との相関は未確定=ユーザーの      |
//|    notebooks/portfolio2_validate(10年Colab)で確定し、本資金前に     |
//|    必ずデモ前進検証(docs/29)。バックテスト級だけで本番に出さない。  |
//|  ・サイズ既定(MR 0.15/0.30/0.75%, RP 0.30/0.60/1.50%)は保守的な     |
//|    出発点=MR:RP≈50:50リスク等配の近似。正確な配分は10年実測+デモで。|
//|  ・2戦略はMagic分離(base+1/+2)。Magicベース940730で現行Portfolio   |
//|    (940710系)/Portfolio3(940710/940720系)と非衝突。                |
//|  ・指数/コモディティCFDの実スプレッド/スワップ/配当/限月ロールは    |
//|    未計上=デモで確認。原油は特にロール/スワップに注意。            |
//|  ・1チャートに本EAは1つだけ(複数/他EAと同口座でMagic衝突回避)。   |
//|  ・v7(円月曜)は意図的に非搭載=現行口座と取引を共有せず並走可能。   |
//+------------------------------------------------------------------+
