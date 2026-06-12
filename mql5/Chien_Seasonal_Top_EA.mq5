//+------------------------------------------------------------------+
//|                                     Chien_Seasonal_Top_EA.mq5      |
//|   季節フォワード検証EA — 月別ランキング上位の合成(docs/87)          |
//|                                                                   |
//|   ★ステータス: フォワード検証用(デモ専用)。月別配分は記述統計に     |
//|     基づく試走であり、検証級の裏付けは各エッジ個別のもの(docs/86)。 |
//|                                                                   |
//|   シナリオ(内蔵・10年実績ベース, Yahoo近似):                       |
//|   ◆ JUNE_TOP5  (6月のみ稼働・倍率2.0x)                             |
//|     v4 41.4% + E5 21.9% + E-Mon 16.0% + E-Mon横 13.3% + v7横 7.4%  |
//|     10年平均月利+3.05%(2.0x) / 最悪月−3.3% / 最悪月中DD−6.1%       |
//|   ◆ JULY_TOP2  (7月のみ稼働・倍率1.3x)                             |
//|     S-Jul 68.5%(US500+NAS100買い持ち) + E5 31.5%                   |
//|     10年平均月利+3.81%(1.3x) / 全年プラス / 最悪月中DD−7.5%        |
//|                                                                   |
//|   実装方式: シミュレーションと同じ「資本比例ノーショナル」          |
//|     1スリーブの建玉額 = equity × weight × mult (リスク予算化でなく |
//|     注文金額比例)。対象月以外は自動で全決済・何もしない=挿しっぱOK。|
//|   ガード: 日次−4%(当日停止) / フロア−8%(全停止) / スプレッド超過    |
//|     スキップ(プロジェクト標準)。                                   |
//|   ⚠ 横展開レッグ(AUDJPY等4クロス/JP225等3指数)はEA初実装=          |
//|     機構確認(docs/86 H14c/d)のみでEA実績ゼロ。必ずデモから。        |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.00"
#property strict
#property description "Seasonal top-ranked mini-portfolios (JUNE_TOP5 2.0x / JULY_TOP2 1.3x). Forward-validation EA, demo-first. Inactive outside its month."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

enum ENUM_SEASONAL_SCN { SCN_JUNE_TOP5=0, SCN_JULY_TOP2=1, SCN_AUG_TOP4=2 };

input group "=== シナリオ ==="
input ENUM_SEASONAL_SCN InpScenario = SCN_JUNE_TOP5; // 6月版/7月版
input bool   InpAcknowledgeDemo = true;   // デモ専用を承認(本資金不可)
input double InpMultOverride    = 0.0;    // 0=推奨倍率(6月2.0/7月1.3) >0で手動

input group "=== ガード(プロジェクト標準) ==="
input double InpDailyStopPct      = 4.0;  // 日次この%負けたら当日停止+全決済
input double InpAccountFloorDDPct = 8.0;  // 初期残高からこの%でEA恒久停止
input double InpInitialBalance    = 0.0;  // 0=自動取得

input group "=== 銘柄名(業者表記が違う場合のみ変更) ==="
input string InpV4Pairs  = "EURUSD,GBPUSD,USDJPY,AUDUSD,USDCHF,USDCAD,NZDUSD,EURJPY,GBPJPY";
input string InpE5Assets = "XAUUSD,US500,NAS100,GER40";
input string InpEMon     = "US500,NAS100,GER40";
input string InpEMonX    = "JP225,UK100,FR40";
input string InpV7X      = "AUDJPY,NZDJPY,CADJPY,CHFJPY";
input string InpSJul     = "US500,NAS100";

input group "=== 詳細 ==="
input int    InpHoldHoursMonday = 24;     // 月曜系の保有時間
input int    InpV4MaxHoldDays   = 8;      // v4の時間切れ(D1バー)
input int    InpV4MaxConcurrent = 4;      // v4同時保有上限(証拠金安全弁)
input double InpMaxSpreadBps    = 10.0;   // これ超のスプレッドは見送り
input long   InpMagicBase       = 930700; // +1=v4 +2=E5 +3=EMon +4=EMonX +5=v7x +6=SJul
input bool   InpVerboseLog      = true;

//==================================================================
CTrade        trade;
CPositionInfo posinfo;

int      g_month   = 6;
double   g_mult    = 2.0;
double   g_initBal = 0.0;
bool     g_halted  = false;
bool     g_dayHalt = false;
int      g_dayKey  = -1;
double   g_dayStartEq = 0.0;
datetime g_lastD1  = 0;
int      g_e5MonthKey = -1, g_sjulMonthKey = -1, g_monWeekKey[64];

#define SL_V4   1
#define SL_E5   2
#define SL_EMON 3
#define SL_EMONX 4
#define SL_V7X  5
#define SL_SJUL 6

string g_v4[16], g_e5[8], g_emon[8], g_emonx[8], g_v7x[8], g_sjul[8];
int    g_nv4=0, g_ne5=0, g_nemon=0, g_nemonx=0, g_nv7x=0, g_nsjul=0;

//------------------------------------------------------------------
string ResolveSymbol(string want)
{
   string suf[]={"",".pi",".raw",".ecn",".stp",".pro",".cash",".r",".c",".m","m",".spot","-cash",".sd","+",".i","_SB","_raw",".a",".z"};
   string bases[]; ArrayResize(bases,40); int nb=0;
   bases[nb++]=want;
   string U=want; StringToUpper(U);
   if(StringFind(U,"XAU")>=0 || StringFind(U,"GOLD")>=0){
      bases[nb++]="XAUUSD"; bases[nb++]="GOLD"; bases[nb++]="GOLDUSD"; }
   else if(StringFind(U,"SPX")>=0 || StringFind(U,"US500")>=0 || StringFind(U,"500")==0){
      bases[nb++]="US500"; bases[nb++]="SPX500"; bases[nb++]="SP500"; bases[nb++]="USA500"; bases[nb++]="US500Cash"; bases[nb++]="SPX"; }
   else if(StringFind(U,"NAS")>=0 || StringFind(U,"USTEC")>=0 || StringFind(U,"NDX")>=0 || StringFind(U,"US100")>=0){
      bases[nb++]="NAS100"; bases[nb++]="USTEC"; bases[nb++]="US100"; bases[nb++]="NDX100"; bases[nb++]="USTECH"; bases[nb++]="NDX"; }
   else if(StringFind(U,"GER")>=0 || StringFind(U,"DAX")>=0 || StringFind(U,"DE40")>=0){
      bases[nb++]="GER40"; bases[nb++]="DE40"; bases[nb++]="DAX40"; bases[nb++]="GERMANY40"; bases[nb++]="DAX"; }
   else if(StringFind(U,"JP225")>=0 || StringFind(U,"JPN")>=0 || StringFind(U,"NIK")>=0){
      bases[nb++]="JP225"; bases[nb++]="JPN225"; bases[nb++]="NIKKEI225"; bases[nb++]="JP225Cash"; bases[nb++]="NI225"; bases[nb++]="JPN225.cash"; }
   else if(StringFind(U,"UK100")>=0 || StringFind(U,"FTSE")>=0){
      bases[nb++]="UK100"; bases[nb++]="FTSE100"; bases[nb++]="UK100Cash"; bases[nb++]="GB100"; }
   else if(StringFind(U,"FR40")>=0 || StringFind(U,"CAC")>=0 || StringFind(U,"FRA40")>=0){
      bases[nb++]="FR40"; bases[nb++]="FRA40"; bases[nb++]="CAC40"; bases[nb++]="F40"; bases[nb++]="FRA40.cash"; }
   ArrayResize(bases,nb);
   for(int b=0;b<nb;b++)
      for(int s=0;s<ArraySize(suf);s++){
         string cand=bases[b]+suf[s];
         if(SymbolSelect(cand,true)) return cand;
      }
   return "";
}

int SplitResolve(string csv, string &arr[], int maxn, string label)
{
   string parts[]; int n=StringSplit(csv,',',parts); int k=0;
   for(int i=0;i<n && k<maxn;i++){
      string s=parts[i]; StringTrimLeft(s); StringTrimRight(s);
      if(StringLen(s)==0) continue;
      string r=ResolveSymbol(s);
      if(r==""){ PrintFormat("[WARN] %s: 銘柄'%s'を解決できず(スキップ)",label,s); continue; }
      arr[k++]=r;
   }
   return k;
}

//------------------------------------------------------------------
int OnInit()
{
   if(!InpAcknowledgeDemo){ Print("[STOP] デモ専用EA。InpAcknowledgeDemo=trueで承認してください。"); return INIT_FAILED; }
   if(InpScenario==SCN_JUNE_TOP5)      { g_month=6; g_mult=2.0; }
   else if(InpScenario==SCN_JULY_TOP2) { g_month=7; g_mult=1.3; }
   else                                { g_month=8; g_mult=0.6; }   // 8月: 2024/8/5型の月曜クラッシュで日次ガード拘束→1倍未満が上限(docs/87)
   if(InpMultOverride>0.0) g_mult=InpMultOverride;
   g_initBal=(InpInitialBalance>0.0)? InpInitialBalance : AccountInfoDouble(ACCOUNT_BALANCE);
   if(g_initBal<=0.0) g_initBal=AccountInfoDouble(ACCOUNT_EQUITY);

   g_nv4   =SplitResolve(InpV4Pairs, g_v4, 16,"v4");
   g_ne5   =SplitResolve(InpE5Assets,g_e5,  8,"E5");
   g_nemon =SplitResolve(InpEMon,   g_emon, 8,"E-Mon");
   g_nemonx=SplitResolve(InpEMonX,  g_emonx,8,"E-Mon横");
   g_nv7x  =SplitResolve(InpV7X,    g_v7x,  8,"v7横");
   g_nsjul =SplitResolve(InpSJul,   g_sjul, 8,"S-Jul");
   ArrayInitialize(g_monWeekKey,-1);

   trade.SetDeviationInPoints(50);
   EventSetTimer(60);
   PrintFormat("[INIT Seasonal %s] 稼働月=%d月 倍率=%.1fx initBal=%.0f | v4:%d E5:%d EMon:%d EMonX:%d v7x:%d SJul:%d",
      (InpScenario==SCN_JUNE_TOP5?"JUNE_TOP5":"JULY_TOP2"),g_month,g_mult,g_initBal,
      g_nv4,g_ne5,g_nemon,g_nemonx,g_nv7x,g_nsjul);
   Print("[NOTE] デモ専用・対象月以外は自動で全決済して待機。横展開レッグはEA初実装(docs/86)。");
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){ EventKillTimer(); }

//------------------------------------------------------------------
double SpreadBps(string s)
{
   double a=SymbolInfoDouble(s,SYMBOL_ASK), b=SymbolInfoDouble(s,SYMBOL_BID);
   if(a<=0||b<=0) return 1e9;
   return (a-b)/((a+b)/2.0)*1e4;
}
double LotsForNotional(string s, double notional)
{
   double price=SymbolInfoDouble(s,SYMBOL_ASK);
   double tv=SymbolInfoDouble(s,SYMBOL_TRADE_TICK_VALUE);
   double ts=SymbolInfoDouble(s,SYMBOL_TRADE_TICK_SIZE);
   if(price<=0||tv<=0||ts<=0) return 0.0;
   double valuePerLot=price*(tv/ts);        // 1ロットの建玉評価額(口座通貨)
   if(valuePerLot<=0) return 0.0;
   double lots=notional/valuePerLot;
   double step=SymbolInfoDouble(s,SYMBOL_VOLUME_STEP);
   double vmin=SymbolInfoDouble(s,SYMBOL_VOLUME_MIN);
   double vmax=SymbolInfoDouble(s,SYMBOL_VOLUME_MAX);
   if(step>0) lots=MathFloor(lots/step)*step;
   if(lots>vmax) lots=vmax;
   if(lots<vmin) return 0.0;
   return lots;
}
long MagicOf(int sleeve){ return InpMagicBase+sleeve; }

int CountSleeve(int sleeve, string sym="")
{
   int c=0;
   for(int i=PositionsTotal()-1;i>=0;i--){
      ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()!=MagicOf(sleeve)) continue;
      if(sym!="" && posinfo.Symbol()!=sym) continue;
      c++;
   }
   return c;
}
void CloseSleeve(int sleeve, string why, int olderThanSec=0, int maxBarsD1=0)
{
   for(int i=PositionsTotal()-1;i>=0;i--){
      ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()!=MagicOf(sleeve)) continue;
      if(olderThanSec>0 && (TimeCurrent()-posinfo.Time())<olderThanSec) continue;
      if(maxBarsD1>0){
         int sh=iBarShift(posinfo.Symbol(),PERIOD_D1,posinfo.Time());
         if(sh<maxBarsD1) continue;
      }
      if(trade.PositionClose(tk) && InpVerboseLog)
         PrintFormat("[CLOSE %s] %s",why,posinfo.Symbol());
   }
}
void CloseAllMine(string why)
{
   for(int sl=SL_V4; sl<=SL_SJUL; sl++) CloseSleeve(sl,why);
}
bool OpenNotional(string s, int sleeve, int dir, double notional, double slPrice=0.0, double tpPrice=0.0, string tag="")
{
   if(SpreadBps(s)>InpMaxSpreadBps){
      if(InpVerboseLog) PrintFormat("[SKIP] %s spread %.1fbps",s,SpreadBps(s));
      return false;
   }
   double lots=LotsForNotional(s,notional);
   if(lots<=0){ if(InpVerboseLog) PrintFormat("[SKIP] %s lots=0 (notional %.0f)",s,notional); return false; }
   trade.SetExpertMagicNumber(MagicOf(sleeve));
   bool ok=(dir>0)? trade.Buy(lots,s,0.0,slPrice,tpPrice,tag)
                  : trade.Sell(lots,s,0.0,slPrice,tpPrice,tag);
   if(ok && InpVerboseLog) PrintFormat("[ENTRY %s] %s %s lots=%.2f notional=%.0f",tag,s,(dir>0?"L":"S"),lots,notional);
   return ok;
}

//------------------------------------------------------------------ 指標(配列・直近確定基準)
double RsiW(const double &c[], int i, int n=14)
{
   if(i<n+2) return 50.0;
   double au=0,ad=0;
   for(int k=1;k<=i;k++){
      double d=c[k]-c[k-1]; double up=(d>0? d:0), dn=(d<0? -d:0);
      if(k==1){ au=up; ad=dn; }
      else    { au=(up+(n-1)*au)/n; ad=(dn+(n-1)*ad)/n; }
   }
   if(ad<=0) return 100.0;
   return 100.0-100.0/(1.0+au/ad);
}

//------------------------------------------------------------------ v4 スリーブ(D1新バーで判定)
void SleeveV4(double W)
{
   datetime d1=(datetime)iTime(_Symbol,PERIOD_D1,0);
   if(d1==g_lastD1) { CloseSleeve(SL_V4,"V4_TIMEOUT",0,InpV4MaxHoldDays); return; }
   g_lastD1=d1;
   CloseSleeve(SL_V4,"V4_TIMEOUT",0,InpV4MaxHoldDays);
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   for(int p=0;p<g_nv4;p++){
      string s=g_v4[p];
      if(CountSleeve(SL_V4,s)>0) continue;
      if(CountSleeve(SL_V4)>=InpV4MaxConcurrent) break;
      double c[],h[],l[];
      if(CopyClose(s,PERIOD_D1,1,40,c)<40) continue;   // [0]=最古..[39]=直近確定
      if(CopyHigh (s,PERIOD_D1,1,40,h)<40) continue;
      if(CopyLow  (s,PERIOD_D1,1,40,l)<40) continue;
      int i=39;
      double mean=0,sd=0;
      for(int k=i-20;k<i;k++) mean+=c[k]; mean/=20.0;
      for(int k=i-20;k<i;k++) sd+=(c[k]-mean)*(c[k]-mean);
      sd=MathSqrt(sd/19.0);
      double z=(sd>0? (c[i]-mean)/sd : 0.0);
      int down=0; for(int k=0;k<12 && i-k-1>=0;k++){ if(c[i-k]<c[i-k-1]) down++; else break; }
      int up=0;   for(int k=0;k<12 && i-k-1>=0;k++){ if(c[i-k]>c[i-k-1]) up++;   else break; }
      double ret=(c[i-1]>0? c[i]/c[i-1]-1.0 : 0.0);
      double rsi=RsiW(c,i,14);
      int buy =(rsi<35?1:0)+(z<-1.5?1:0)+(down>=3?1:0)+(ret<-0.005?1:0);
      int sell=(rsi>65?1:0)+(z>1.5?1:0)+(up>=3?1:0)+(ret>0.005?1:0);
      int sig=(buy>=4 && buy>sell)? 1 : ((sell>=4 && sell>buy)? -1 : 0);
      if(sig==0) continue;
      double atr=0;
      for(int k=i-13;k<=i;k++){
         double tr=MathMax(h[k]-l[k],MathMax(MathAbs(h[k]-c[k-1]),MathAbs(l[k]-c[k-1])));
         atr=(k==i-13? tr : (tr+13.0*atr)/14.0);
      }
      if(atr<=0) continue;
      double px=(sig>0? SymbolInfoDouble(s,SYMBOL_ASK):SymbolInfoDouble(s,SYMBOL_BID));
      int dg=(int)SymbolInfoInteger(s,SYMBOL_DIGITS);
      double sl=NormalizeDouble(px-sig*1.5*atr,dg);
      double tp=NormalizeDouble(px+sig*1.8*atr,dg);   // 1.2×(1.5ATR)
      OpenNotional(s,SL_V4,sig,eq*W*g_mult,sl,tp,"V4_K4");
   }
}

//------------------------------------------------------------------ 月曜スリーブ(E-Mon/E-Mon横/v7横)
void SleeveMonday(int sleeve, string &syms[], int nsym, double W, int slot)
{
   CloseSleeve(sleeve,"MON_24H",InpHoldHoursMonday*3600);
   MqlDateTime t; TimeToStruct(TimeCurrent(),t);
   if(t.day_of_week!=1) return;
   int wk=t.year*100+(t.day_of_year/7);
   if(g_monWeekKey[slot]==wk) return;
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   int done=0;
   for(int i=0;i<nsym;i++){
      if(CountSleeve(sleeve,syms[i])>0){ done++; continue; }
      if(OpenNotional(syms[i],sleeve,+1,eq*W*g_mult/nsym,0,0,
         (sleeve==SL_V7X?"V7X_MON":(sleeve==SL_EMONX?"EMONX_MON":"EMON_MON")))) done++;
   }
   if(done>=nsym) g_monWeekKey[slot]=wk;   // 全建て完了で当週終了(未約定銘柄は再試行)
}

//------------------------------------------------------------------ E5 スリーブ(月初)
void SleeveE5(double W)
{
   MqlDateTime t; TimeToStruct(TimeCurrent(),t);
   int mk=t.year*100+t.mon;
   if(g_e5MonthKey==mk) return;
   double sgn[8], invv[8], sumInv=0;
   for(int i=0;i<g_ne5;i++){
      sgn[i]=0; invv[i]=0;
      double c[];
      if(CopyClose(g_e5[i],PERIOD_MN1,0,16,c)<16) continue;  // [0]=最古..[15]=当月(形成中)
      int i1=14;                                             // 直近確定月
      double comp=0;
      int lbs[4]={1,3,6,12};
      for(int k=0;k<4;k++){
         int j=i1-lbs[k]; if(j<0) continue;
         double r=c[i1]/c[j]-1.0;
         comp+=(r>0?1:(r<0?-1:0));
      }
      if(comp==0) continue;
      double m=0,v=0, rets[12];
      for(int k=0;k<12;k++){ rets[k]=c[i1-k]/c[i1-k-1]-1.0; m+=rets[k]; }
      m/=12.0;
      for(int k=0;k<12;k++) v+=(rets[k]-m)*(rets[k]-m);
      double sd2=MathSqrt(v/12.0);
      if(sd2<=0) continue;
      sgn[i]=(comp>0?1:-1); invv[i]=1.0/sd2; sumInv+=invv[i];
   }
   if(sumInv<=0){ g_e5MonthKey=mk; return; }
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   int done=0, want=0;
   for(int i=0;i<g_ne5;i++){
      if(sgn[i]==0) continue;
      want++;
      if(CountSleeve(SL_E5,g_e5[i])>0){ done++; continue; }
      if(OpenNotional(g_e5[i],SL_E5,(int)sgn[i],eq*W*g_mult*invv[i]/sumInv,0,0,"E5_TSMOM")) done++;
   }
   if(done>=want) g_e5MonthKey=mk;
}

//------------------------------------------------------------------ S-Jul スリーブ(月初買い持ち)
void SleeveSJul(double W)
{
   MqlDateTime t; TimeToStruct(TimeCurrent(),t);
   int mk=t.year*100+t.mon;
   if(g_sjulMonthKey==mk) return;
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   int done=0;
   for(int i=0;i<g_nsjul;i++){
      if(CountSleeve(SL_SJUL,g_sjul[i])>0){ done++; continue; }
      if(OpenNotional(g_sjul[i],SL_SJUL,+1,eq*W*g_mult/g_nsjul,0,0,"SJUL")) done++;
   }
   if(done>=g_nsjul) g_sjulMonthKey=mk;
}

//------------------------------------------------------------------
void OnTimer()
{
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);

   // フロア(恒久停止)
   if(eq<=g_initBal*(1.0-InpAccountFloorDDPct/100.0) && !g_halted){
      g_halted=true; CloseAllMine("FLOOR");
      PrintFormat("[HALT] equity %.2f <= floor",eq);
   }
   if(g_halted){ CloseAllMine("HALTED"); return; }

   // 日次ガード
   MqlDateTime t; TimeToStruct(TimeCurrent(),t);
   int dk=t.year*1000+t.day_of_year;
   if(dk!=g_dayKey){ g_dayKey=dk; g_dayStartEq=eq; g_dayHalt=false; }
   if(!g_dayHalt && eq<=g_dayStartEq*(1.0-InpDailyStopPct/100.0)){
      g_dayHalt=true; CloseAllMine("DAILY_STOP");
      PrintFormat("[DAILY HALT] %.2f%%",InpDailyStopPct);
   }
   if(g_dayHalt) return;

   // 月ゲート: 対象月以外は全決済して待機
   if(t.mon!=g_month){ CloseAllMine("MONTH_GATE"); return; }

   if(InpScenario==SCN_JUNE_TOP5){
      SleeveV4(0.414);
      SleeveE5(0.219);
      SleeveMonday(SL_EMON, g_emon, g_nemon, 0.160, 0);
      SleeveMonday(SL_EMONX,g_emonx,g_nemonx,0.133, 1);
      SleeveMonday(SL_V7X,  g_v7x,  g_nv7x,  0.074, 2);
   }else if(InpScenario==SCN_JULY_TOP2){
      SleeveSJul(0.685);
      SleeveE5(0.315);
   }else{ // SCN_AUG_TOP4: v4 66.0% / E-Mon横 18.7% / E-Mon 8.1% / E5 7.2%
      SleeveV4(0.660);
      SleeveE5(0.072);
      SleeveMonday(SL_EMON, g_emon, g_nemon, 0.081, 0);
      SleeveMonday(SL_EMONX,g_emonx,g_nemonx,0.187, 1);
   }
}
void OnTick(){ /* 主処理はOnTimer(60s) */ }
//+------------------------------------------------------------------+
//| 残存リスク(誠実な記録):                                          |
//|  ・月別配分は10年の記述統計(in-sample重み)。フォワードの目的は     |
//|    「分布内か」の確認でありこの月利の保証ではない(docs/87)。       |
//|  ・横展開4クロス/3指数はEA実装・約定実績ゼロ→デモで要確認。        |
//|  ・v4はSL/TP到達を足内で判定する実装(バックテストはD1高安)。       |
//|    月末跨ぎのv4建玉は月ゲートで強制決済(検証との小差・保守側)。    |
//|  ・サーバ時刻基準で月曜/月初を判定(UTCとのズレは数時間・影響小)。  |
//|  ・指数の取引時間外は約定失敗→次のタイマーで再試行する設計。       |
//|  ・gross露出は6月版で最大≈200%+v4重複分。証拠金率の低い業者では    |
//|    InpV4MaxConcurrentを下げる。                                    |
//+------------------------------------------------------------------+
