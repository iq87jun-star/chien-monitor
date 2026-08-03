//+------------------------------------------------------------------+
//| Chien_RecentFit5_EA.mq5                                          |
//| 直近フィット・トラック v1.0 (docs/174-175)                        |
//|                                                                  |
//| ⚠ 本EAは意図的な「直近12ヶ月フィット」(レジームベット)。          |
//|   10年頑健性は検証しておらず、要求もしていない(docs/174 §1)。     |
//|   正攻法トラック(季節RG3/PD系)とは別枠・別口座で運用すること。     |
//|                                                                  |
//| スリーブ(research/results/recentfit_sweep.json 2026-07-30 焼込):  |
//|  S1: GBPUSD 月曜00:00UTC LONG 12h   (FIT PF3.38 t3.04 / REF PF1.59)|
//|  S2: GBPJPY 月曜08:00UTC LONG 12h   (FIT PF2.79 t2.46 / REF PF1.99)|
//|  S3: USDCHF 木曜16:00UTC SHORT 6h   (FIT PF2.58 t2.20 / REF PF2.15)|
//|  S4: GBPUSD D1 RSI(2) 30/70 逆張り 5日 (FIT PF2.98 / REF PF0.71⚠) |
//|  S5: GBPJPY D1 RSI(2) 20/80 逆張り 3日 (FIT PF2.66 / REF PF1.00⚠) |
//|  S4/S5は前年マイナス〜フラット=純粋な直近レジームベット。          |
//|                                                                  |
//| ガード(プロジェクト標準 v1.44系継承):                             |
//|  - balance基準日次ガード: equity<=日開始balance−4% で全決済+当日停止|
//|    (ティック毎評価・月内3回目で月末まで停止・端末再起動に耐える)    |
//|  - フロア: 初期残高−8%で全決済+恒久停止                           |
//|  - 利益ロック: +Arm%で新規停止 / +Close%で全決済・恒久ロック       |
//|  - 全建玉に3×ATR(D1)の災害SL / 最短保有150秒 / スプレッド上限      |
//|                                                                  |
//| 運用既定: FundedNext Stellar 2-Step想定。                         |
//|  P1: LockArm=8.0 LockClose=8.5 / P2に進んだら 5.0/5.5 に変更。     |
//|  リスク: 1.25%/トレード(docs/175 MC: エッジ半減でも通過80%・       |
//|  規則失格0%。2.0%は速度優先オプションだが剥落時guard_stop25%)。    |
//+------------------------------------------------------------------+
#property copyright "chien-monitor recent-fit track"
#property version   "1.02"
#property strict
#include <Trade/Trade.mqh>

//=== 入力 =========================================================
input group "=== リスク ==="
input double InpRiskPerTradePct   = 1.25;   // 1トレードのリスク%(3×ATR SL基準) docs/175標準
input double InpMultOverride      = 1.0;    // 全体倍率(資金化後の減率などに使用)
input double InpMaxSpreadBps      = 10.0;   // これ超のスプレッドは見送り(bps)

input group "=== ガード(プロジェクト標準) ==="
input double InpBalGuardPct       = 4.0;    // 日次: equity<=日開始balance-この%で全決済+当日停止
input int    InpBalGuardMaxMonth  = 2;      // 月内この回数を超えたら月末まで停止(3回目で停止)
input double InpAccountFloorDDPct = 8.0;    // 初期残高からこの%でEA恒久停止
input double InpInitialBalance    = 0.0;    // 0=自動(初回アタッチ時残高を端末に永続保存)
input bool   InpBaselineReset     = false;  // 新フェーズ開始時のみtrue=基準残高を取り直す

input group "=== 利益ロック(フェーズ通過の確定) ==="
input bool   InpProfitLockEnable  = true;   // 利益ロックを使う
input double InpLockArmPct        = 8.0;    // equity+この%で新規停止(P1=8.0 / P2=5.0)
input double InpLockClosePct      = 8.5;    // equity+この%で全決済・恒久ロック(P1=8.5 / P2=5.5)

input group "=== スリーブ有効化 ==="
input bool   InpS1_GbpUsdMon      = true;   // S1: GBPUSD 月曜00UTC L12h
input bool   InpS2_GbpJpyMon      = true;   // S2: GBPJPY 月曜08UTC L12h
input bool   InpS3_UsdChfThu      = true;   // S3: USDCHF 木曜16UTC S6h
input bool   InpS4_GbpUsdRsi      = true;   // S4: GBPUSD RSI2 30/70 5日
input bool   InpS5_GbpJpyRsi      = true;   // S5: GBPJPY RSI2 20/80 3日

input group "=== 銘柄名(業者表記が違う場合のみ変更) ==="
input string InpSymGBPUSD         = "GBPUSD";
input string InpSymGBPJPY         = "GBPJPY";
input string InpSymUSDCHF         = "USDCHF";

input group "=== 詳細 ==="
input int    InpServerToUtcHours  = -999;   // -999=TimeGMT()使用(ライブ推奨) / 他=サーバ時刻-この時間をUTCとみなす(テスター用: FN系は夏3冬2)
input long   InpMagicBase         = 941200; // Magic基底(スリーブ=+1..+5)
input double InpSlAtrMult         = 3.0;    // 災害SL=この×ATR14(D1)。R換算と一致(変更不可推奨)
input int    InpMinHoldSeconds    = 150;    // 最短保有(2分未満保有のフラグ対策)
input bool   InpNotifyEnable      = false;  // SendNotification(要MetaQuotes ID)

//=== 定数: スリーブ定義(recentfit_sweep.json焼き込み) =============
#define NSLV 5
// family: 0=週次時刻(A) / 1=日足RSI逆張り(C)
struct SleeveDef {
   int    family;
   int    dow;        // A: 曜日(0=月..4=金, UTC)
   int    hourUtc;    // A: エントリー時刻(UTC)
   int    holdHours;  // A: 保有時間
   int    dir;        // A: +1=LONG -1=SHORT
   int    rsiPeriod;  // C: RSI期間
   double rsiLo;      // C: これ未満でLONG
   double rsiHi;      // C: これ超でSHORT
   int    holdDays;   // C: 保有D1バー数
};
SleeveDef g_def[NSLV];
string    g_sym[NSLV];
bool      g_ena[NSLV];

//=== 状態 =========================================================
CTrade   g_trade;
double   g_initBal=0.0;
bool     g_halted=false;
bool     g_dayHalt=false;
int      g_dayKey=-1;
double   g_dayStartBal=0.0;
int      g_balBlockDayKey=-1, g_balFireMonth=-1, g_balFires=0;
bool     g_balMonthHalt=false;
bool     g_lockDone=false, g_lockArmed=false;
string   g_gvName="";
int      g_weekKey[NSLV];          // 族A: 週1回のエントリー管理
datetime g_lastD1[NSLV];           // 族C: 新バー検出
int      g_atrH[NSLV];             // ATR14(D1)ハンドル(銘柄ごと)

//=== ユーティリティ ===============================================
void Notify(string msg){ if(InpNotifyEnable) SendNotification("RecentFit5: "+msg); }

string ResolveSymbol(string want)
{
   string suf[]={"",".pi",".raw",".ecn",".stp",".pro",".r",".c",".m","m",".sd","+",".i",".a",".z","_raw"};
   for(int s=0;s<ArraySize(suf);s++){
      string cand=want+suf[s];
      if(SymbolSelect(cand,true)) return cand;
   }
   // v1.45方式: 全銘柄走査フォールバック(基底名を含む最短の銘柄名)
   string best=""; int bestLen=INT_MAX;
   int total=SymbolsTotal(false);
   for(int i=0;i<total;i++){
      string s=SymbolName(i,false);
      string U=s; StringToUpper(U);
      if(StringFind(U,want)>=0 && StringLen(s)<bestLen){ best=s; bestLen=StringLen(s); }
   }
   if(best!="" && SymbolSelect(best,true)) return best;
   return "";
}

double SpreadBps(string s)
{
   double bid=SymbolInfoDouble(s,SYMBOL_BID), ask=SymbolInfoDouble(s,SYMBOL_ASK);
   if(bid<=0) return 1e9;
   return (ask-bid)/bid*10000.0;
}

double AtrD1(int idx)
{
   if(g_atrH[idx]==INVALID_HANDLE) return 0.0;
   double b[]; if(CopyBuffer(g_atrH[idx],0,1,1,b)!=1) return 0.0;  // 確定足のATR
   return b[0];
}

double LotsForRisk(string s, double slDist)
{
   if(slDist<=0) return 0.0;
   double riskMoney=AccountInfoDouble(ACCOUNT_BALANCE)*InpRiskPerTradePct/100.0*InpMultOverride;
   double tickSize=SymbolInfoDouble(s,SYMBOL_TRADE_TICK_SIZE);
   double tickVal =SymbolInfoDouble(s,SYMBOL_TRADE_TICK_VALUE);
   if(tickSize<=0||tickVal<=0) return 0.0;
   double lossPerLot=slDist/tickSize*tickVal;
   if(lossPerLot<=0) return 0.0;
   double lots=riskMoney/lossPerLot;
   double step=SymbolInfoDouble(s,SYMBOL_VOLUME_STEP);
   double vmin=SymbolInfoDouble(s,SYMBOL_VOLUME_MIN);
   double vmax=SymbolInfoDouble(s,SYMBOL_VOLUME_MAX);
   if(step>0) lots=MathFloor(lots/step)*step;
   if(lots<vmin) return 0.0;                       // 最小ロット未満=建てない(リスク超過を許さない)
   if(lots>vmax) lots=vmax;
   return lots;
}

int CountSleeve(int idx)
{
   int n=0;
   for(int i=PositionsTotal()-1;i>=0;i--){
      ulong tk=PositionGetTicket(i);
      if(tk==0||!PositionSelectByTicket(tk)) continue;
      if(PositionGetInteger(POSITION_MAGIC)==InpMagicBase+idx+1) n++;
   }
   return n;
}

void CloseSleeve(int idx, string why)
{
   for(int i=PositionsTotal()-1;i>=0;i--){
      ulong tk=PositionGetTicket(i);
      if(tk==0||!PositionSelectByTicket(tk)) continue;
      if(PositionGetInteger(POSITION_MAGIC)!=InpMagicBase+idx+1) continue;
      g_trade.PositionClose(tk);
      PrintFormat("[CLOSE S%d] %s (%s)",idx+1,PositionGetString(POSITION_SYMBOL),why);
   }
}

void CloseAllMine(string why)
{
   for(int i=PositionsTotal()-1;i>=0;i--){
      ulong tk=PositionGetTicket(i);
      if(tk==0||!PositionSelectByTicket(tk)) continue;
      long mg=PositionGetInteger(POSITION_MAGIC);
      if(mg<InpMagicBase+1||mg>InpMagicBase+NSLV) continue;
      g_trade.PositionClose(tk);
      PrintFormat("[CLOSE ALL] %s magic=%I64d (%s)",PositionGetString(POSITION_SYMBOL),mg,why);
   }
}

bool OpenSleeve(int idx, int dir, string tag)
{
   string s=g_sym[idx];
   if(SpreadBps(s)>InpMaxSpreadBps){ PrintFormat("[SKIP S%d] spread %.1fbps > %.1f",idx+1,SpreadBps(s),InpMaxSpreadBps); return false; }
   double atr=AtrD1(idx);
   if(atr<=0){ PrintFormat("[SKIP S%d] ATR未取得",idx+1); return false; }
   double slDist=InpSlAtrMult*atr;
   double lots=LotsForRisk(s,slDist);
   if(lots<=0){ PrintFormat("[SKIP S%d] lots=0 (最小ロット未満/口座小)",idx+1); return false; }
   double px = (dir>0)? SymbolInfoDouble(s,SYMBOL_ASK) : SymbolInfoDouble(s,SYMBOL_BID);
   double sl = (dir>0)? px-slDist : px+slDist;
   int dg=(int)SymbolInfoInteger(s,SYMBOL_DIGITS);
   sl=NormalizeDouble(sl,dg);
   g_trade.SetExpertMagicNumber(InpMagicBase+idx+1);
   bool ok = (dir>0)? g_trade.Buy(lots,s,0.0,sl,0.0,tag)
                    : g_trade.Sell(lots,s,0.0,sl,0.0,tag);
   if(ok){ PrintFormat("[ENTRY S%d] %s %s %.2flot SL=%.5f (%s)",idx+1,s,(dir>0?"BUY":"SELL"),lots,sl,tag);
           Notify(StringFormat("S%d %s %s",idx+1,s,(dir>0?"BUY":"SELL"))); }
   else    PrintFormat("[ERR S%d] open失敗 ret=%d",idx+1,(int)g_trade.ResultRetcode());
   return ok;
}

double RsiD1(string s, int period)
{
   // 確定D1終値からWilder RSIを直接計算(前足確定値のみ使用=ノールックアヘッド)
   double c[]; int need=period+200;
   int got=CopyClose(s,PERIOD_D1,1,need,c);          // shift1=確定足まで
   if(got<period+20) return 50.0;
   double au=0,ad=0;
   for(int i=1;i<got;i++){
      double d=c[i]-c[i-1];
      double up=(d>0)?d:0, dn=(d<0)?-d:0;
      if(i==1){ au=up; ad=dn; }
      else    { au=(au*(period-1)+up)/period; ad=(ad*(period-1)+dn)/period; }
   }
   if(ad==0) return 100.0;
   double rs=au/ad;
   return 100.0-100.0/(1.0+rs);
}

//=== ガード(v1.44系) ==============================================
bool BalGuardActive()
{
   MqlDateTime bt; TimeToStruct(TimeCurrent(),bt);
   int bdk=bt.year*1000+bt.day_of_year;
   return (g_balMonthHalt || bdk==g_balBlockDayKey);
}

void BalGuardCheck()
{
   if(InpBalGuardPct<=0.0 || g_lockDone || g_halted) return;
   MqlDateTime bt; TimeToStruct(TimeCurrent(),bt);
   int bdk=bt.year*1000+bt.day_of_year, bmk=bt.year*100+bt.mon;
   double beq=AccountInfoDouble(ACCOUNT_EQUITY);
   if(bdk!=g_dayKey){ g_dayKey=bdk; g_dayHalt=false;
      g_dayStartBal=AccountInfoDouble(ACCOUNT_BALANCE);
      if(g_gvName!=""){ GlobalVariableSet(g_gvName+"_dk",(double)bdk);        // v1.02: 日次基準を永続化
                        GlobalVariableSet(g_gvName+"_db",g_dayStartBal); } }
   if(bmk!=g_balFireMonth){
      g_balFireMonth=bmk; g_balFires=0; g_balMonthHalt=false;
      string bgv=g_gvName+"_bg";
      if(g_gvName!="" && GlobalVariableCheck(bgv)){
         long v=(long)GlobalVariableGet(bgv);
         if((int)(v/100)==bmk){ g_balFires=(int)(v%100); g_balMonthHalt=(g_balFires>InpBalGuardMaxMonth); }
      }
   }
   if(BalGuardActive() || g_dayHalt || g_dayStartBal<=0.0) return;
   if(beq>g_dayStartBal*(1.0-InpBalGuardPct/100.0)) return;
   g_balBlockDayKey=bdk; g_balFires++; g_dayHalt=true;
   if(g_balFires>InpBalGuardMaxMonth) g_balMonthHalt=true;
   if(g_gvName!=""){ GlobalVariableSet(g_gvName+"_bg",(double)((long)bmk*100+g_balFires));
                     GlobalVariableSet(g_gvName+"_bd",(double)bdk); }         // v1.02: 当日停止も永続化
   CloseAllMine("BAL_GUARD");
   PrintFormat("[BAL GUARD] eq %.2f <= 日開始bal %.2f -%.1f%% → 全決済・当日停止(月内%d回目%s)",
               beq,g_dayStartBal,InpBalGuardPct,g_balFires,(g_balMonthHalt?"・月末まで停止":""));
   Notify(StringFormat("BAL_GUARD -%.1f%% 全決済・当日停止(%d/月)",InpBalGuardPct,g_balFires));
}

void FloorAndLockCheck()
{
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   if(g_initBal<=0) return;
   if(eq<=g_initBal*(1.0-InpAccountFloorDDPct/100.0) && !g_halted){
      g_halted=true; CloseAllMine("FLOOR");
      PrintFormat("[HALT] equity %.2f <= floor -%.1f%% 恒久停止",eq,InpAccountFloorDDPct);
      Notify(StringFormat("FLOOR -%.1f%% 全決済・恒久停止",InpAccountFloorDDPct));
   }
   if(g_halted){ CloseAllMine("HALTED"); return; }
   if(InpProfitLockEnable){
      double gainPct=(eq-g_initBal)/g_initBal*100.0;
      if(!g_lockDone && gainPct>=InpLockClosePct){
         g_lockDone=true; CloseAllMine("PROFIT_LOCK");
         PrintFormat("[PASS LOCK] %+.2f%% >= +%.2f%% 全決済・恒久ロック(再開はEA再アタッチ)",gainPct,InpLockClosePct);
         Notify(StringFormat("PASS_LOCK %+.2f%% 全決済",gainPct));
      }
      bool armNow=(!g_lockDone && gainPct>=InpLockArmPct);
      if(armNow!=g_lockArmed){
         g_lockArmed=armNow;
         PrintFormat("[LOCK %s] equity %+.2f%%",(armNow?"ARMED=新規停止":"DISARM=新規再開"),gainPct);
      }
   }
}

bool EntriesBlocked(){ return (g_halted || g_dayHalt || g_lockDone || g_lockArmed || BalGuardActive()); }

//=== ロジック =====================================================
void ManageTimeExits()
{
   datetime now=TimeCurrent();
   for(int i=PositionsTotal()-1;i>=0;i--){
      ulong tk=PositionGetTicket(i);
      if(tk==0||!PositionSelectByTicket(tk)) continue;
      long mg=PositionGetInteger(POSITION_MAGIC);
      if(mg<InpMagicBase+1||mg>InpMagicBase+NSLV) continue;
      int idx=(int)(mg-InpMagicBase-1);
      datetime opened=(datetime)PositionGetInteger(POSITION_TIME);
      int heldSec=(int)(now-opened);
      if(heldSec<InpMinHoldSeconds) continue;
      if(g_def[idx].family==0){
         if(heldSec>=g_def[idx].holdHours*3600) { g_trade.PositionClose(tk); PrintFormat("[EXIT S%d] time %dh",idx+1,g_def[idx].holdHours); }
      }else{
         // 族C: 保有D1バー数で決済(新バー始値決済の近似)
         // v1.02修正: Bars(opened,barNow)-1はライブだとエントリーバー(始値の数秒後に
         // 建つためBars()に数えられない)が欠落し1日長く保有した。iBarShiftは
         // エントリーバー=0で数えるためテスターとライブで一致する。
         int barsHeld=iBarShift(g_sym[idx],PERIOD_D1,opened);
         if(barsHeld>=g_def[idx].holdDays){ g_trade.PositionClose(tk); PrintFormat("[EXIT S%d] %d D1 bars",idx+1,barsHeld); }
      }
   }
}

datetime UtcNow()
{
   if(InpServerToUtcHours==-999) return TimeGMT();
   return TimeCurrent()-InpServerToUtcHours*3600;
}

void TrySleeveA(int idx)
{
   MqlDateTime gt; TimeToStruct(UtcNow(),gt);
   int dowMon0=(gt.day_of_week+6)%7;                    // 0=月..6=日
   if(dowMon0!=g_def[idx].dow || gt.hour!=g_def[idx].hourUtc) return;
   int wk=gt.year*100+ (gt.day_of_year/7);              // 週キー(同週の再建て防止)
   if(g_weekKey[idx]==wk) return;
   if(CountSleeve(idx)>0) return;
   if(OpenSleeve(idx,g_def[idx].dir,StringFormat("RF5-S%d",idx+1)))
      g_weekKey[idx]=wk;
}

datetime g_cTryStart[NSLV];   // v1.02: 族C再試行の開始時刻(断念判定は経過時間基準)
datetime g_cLastTry[NSLV];    // v1.02: 直近試行時刻(失敗後の再試行は30秒間隔)

void TrySleeveC(int idx)
{
   datetime cur=(datetime)SeriesInfoInteger(g_sym[idx],PERIOD_D1,SERIES_LASTBAR_DATE);
   if(cur==0||cur==g_lastD1[idx]) return;               // 新D1バーのみ判定(始値エントリーの近似)
   // v1.01修正: バー消費はエントリー成立/シグナルなし時のみ。
   // 旧実装は試行前に消費していたため、バー切替直後のスプレッド拡大や市場閉で
   // スキップすると当日中に再試行されずスリーブが1日空振りした(2026-08-03 S5事象)。
   // v1.02修正: 断念判定を試行回数(OnTick駆動=ティック毎加算で活発な相場では
   // 数十秒で120回に到達し、ロールオーバーのスプレッド拡大を待ちきれず当日
   // 空振りが再発し得た)から経過時間に変更。初回失敗から1時間、30秒間隔で再試行。
   if(g_cTryStart[idx]!=0 && TimeCurrent()-g_cLastTry[idx]<30) return;
   if(CountSleeve(idx)>0){ g_lastD1[idx]=cur; g_cTryStart[idx]=0; return; }
   double r=RsiD1(g_sym[idx],g_def[idx].rsiPeriod);
   int dir=0;
   if(r<g_def[idx].rsiLo) dir=1;
   else if(r>g_def[idx].rsiHi) dir=-1;
   if(dir==0){ g_lastD1[idx]=cur; g_cTryStart[idx]=0; return; }
   if(OpenSleeve(idx,dir,StringFormat("RF5-S%d RSI%.0f",idx+1,r))){
      g_lastD1[idx]=cur; g_cTryStart[idx]=0;
   }else{
      datetime now=TimeCurrent();
      if(g_cTryStart[idx]==0) g_cTryStart[idx]=now;
      g_cLastTry[idx]=now;
      if(now-g_cTryStart[idx]>=3600){
         PrintFormat("[GIVEUP S%d] 1時間再試行しても建てられず→当バーを断念",idx+1);
         g_lastD1[idx]=cur; g_cTryStart[idx]=0;
      }
   }
}

//=== ライフサイクル ===============================================
int OnInit()
{
   // スリーブ定義(焼き込み)
   SleeveDef d;
   d.family=0; d.dow=0; d.hourUtc=0;  d.holdHours=12; d.dir=+1; d.rsiPeriod=0; d.rsiLo=0; d.rsiHi=0; d.holdDays=0; g_def[0]=d; // S1
   d.family=0; d.dow=0; d.hourUtc=8;  d.holdHours=12; d.dir=+1;                                              g_def[1]=d; // S2
   d.family=0; d.dow=3; d.hourUtc=16; d.holdHours=6;  d.dir=-1;                                              g_def[2]=d; // S3
   d.family=1; d.dow=0; d.hourUtc=0; d.holdHours=0; d.dir=0; d.rsiPeriod=2; d.rsiLo=30; d.rsiHi=70; d.holdDays=5; g_def[3]=d; // S4
   d.family=1; d.rsiPeriod=2; d.rsiLo=20; d.rsiHi=80; d.holdDays=3;                                          g_def[4]=d; // S5

   string wantSym[NSLV]; bool wantEna[NSLV];
   wantSym[0]=InpSymGBPUSD; wantEna[0]=InpS1_GbpUsdMon;
   wantSym[1]=InpSymGBPJPY; wantEna[1]=InpS2_GbpJpyMon;
   wantSym[2]=InpSymUSDCHF; wantEna[2]=InpS3_UsdChfThu;
   wantSym[3]=InpSymGBPUSD; wantEna[3]=InpS4_GbpUsdRsi;
   wantSym[4]=InpSymGBPJPY; wantEna[4]=InpS5_GbpJpyRsi;
   for(int i=0;i<NSLV;i++){
      g_ena[i]=wantEna[i]; g_weekKey[i]=-1; g_lastD1[i]=0; g_cTryStart[i]=0; g_cLastTry[i]=0; g_atrH[i]=INVALID_HANDLE;
      g_sym[i]=ResolveSymbol(wantSym[i]);
      if(g_sym[i]==""){
         if(g_ena[i]) PrintFormat("[WARN] S%d: 銘柄'%s'を解決できず→スリーブ無効",i+1,wantSym[i]);
         g_ena[i]=false; continue;
      }
      g_atrH[i]=iATR(g_sym[i],PERIOD_D1,14);
      if(g_atrH[i]==INVALID_HANDLE){ PrintFormat("[WARN] S%d: ATRハンドル失敗→無効",i+1); g_ena[i]=false; }
   }

   // 基準残高(端末永続・再アタッチ耐性)
   long acc=AccountInfoInteger(ACCOUNT_LOGIN);
   g_gvName=StringFormat("RF5_init_%I64d_%I64d",acc,InpMagicBase);
   if(InpInitialBalance>0){ g_initBal=InpInitialBalance; GlobalVariableSet(g_gvName,g_initBal); }
   else if(InpBaselineReset || !GlobalVariableCheck(g_gvName)){
      g_initBal=AccountInfoDouble(ACCOUNT_BALANCE);
      GlobalVariableSet(g_gvName,g_initBal);
   }else g_initBal=GlobalVariableGet(g_gvName);

   // v1.02: 日次ガード基準の復元(同日中の再起動で基準が現在残高に
   // 再アンカーされ、実質の日次許容損失が広がるのを防ぐ)
   {
      MqlDateTime t0; TimeToStruct(TimeCurrent(),t0);
      int nowKey=t0.year*1000+t0.day_of_year;
      if(GlobalVariableCheck(g_gvName+"_dk") && (int)GlobalVariableGet(g_gvName+"_dk")==nowKey){
         double db=GlobalVariableCheck(g_gvName+"_db")? GlobalVariableGet(g_gvName+"_db") : 0.0;
         if(db>0.0){ g_dayKey=nowKey; g_dayStartBal=db;
            PrintFormat("[日次基準復元] 日開始balance=%.2f",db); }
      }
      if(GlobalVariableCheck(g_gvName+"_bd") && (int)GlobalVariableGet(g_gvName+"_bd")==nowKey){
         g_balBlockDayKey=nowKey; g_dayHalt=true;
         Print("[日次基準復元] 当日はBAL_GUARD発動済み→新規停止を継続");
      }
   }

   g_trade.SetDeviationInPoints(30);
   EventSetTimer(30);
   PrintFormat("[INIT] RecentFit5 v1.02 risk=%.2f%%×%.2fx magic=%I64d+1..%d 基準残高=%.2f guard=日次-%.1f%%/floor-%.1f%%/lock+%.1f→+%.1f%%",
               InpRiskPerTradePct,InpMultOverride,InpMagicBase,NSLV,g_initBal,
               InpBalGuardPct,InpAccountFloorDDPct,InpLockArmPct,InpLockClosePct);
   for(int i=0;i<NSLV;i++)
      PrintFormat("[INIT] S%d %s -> %s (%s)",i+1,wantSym[i],(g_sym[i]==""?"<未解決>":g_sym[i]),(g_ena[i]?"ON":"OFF"));
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   for(int i=0;i<NSLV;i++) if(g_atrH[i]!=INVALID_HANDLE) IndicatorRelease(g_atrH[i]);
}

void OnTick()
{
   BalGuardCheck();          // ティック毎: balance基準日次ガード(最優先)
   if(g_halted) return;
   ManageTimeExits();
   if(EntriesBlocked()) return;
   for(int i=0;i<NSLV;i++){
      if(!g_ena[i]) continue;
      if(g_def[i].family==0) TrySleeveA(i);
      else                   TrySleeveC(i);
   }
}

void OnTimer()
{
   FloorAndLockCheck();      // 30秒毎: フロア/利益ロック
   // GlobalVariableの4週失効対策: 日次タッチ
   static int s_touchDay=-1;
   MqlDateTime t; TimeToStruct(TimeCurrent(),t);
   int dk=t.year*1000+t.day_of_year;
   if(dk!=s_touchDay && g_gvName!=""){
      s_touchDay=dk;
      GlobalVariableSet(g_gvName,g_initBal);
      if(GlobalVariableCheck(g_gvName+"_bg")) GlobalVariableSet(g_gvName+"_bg",GlobalVariableGet(g_gvName+"_bg"));
   }
}
//+------------------------------------------------------------------+
