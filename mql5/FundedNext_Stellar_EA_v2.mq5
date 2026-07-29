//+------------------------------------------------------------------+
//|                                 FundedNext_Stellar_EA_v2.mq5      |
//|   FundedNext "Stellar 2-Step" ($100K) 通過特化EA  ― v2           |
//|                                                                  |
//|   v1(トレンド押し目RSI反転)は実データ検証(Lv1-Lv5)でエッジ無しと  |
//|   判明したため破棄。v2は白紙再探索で唯一エッジの兆候を示した       |
//|   「日足RSI平均回帰(逆張り)」を採用。                              |
//|     - RSIが過熱(売られ過ぎ/買われ過ぎ)で反転を狙う逆張り           |
//|     - SL=ATR×倍率, TP=SL×RR, 一定本数で時間切れ手仕舞い           |
//|   リスクガード(日次-4%/累積-8%/固定%リスク/SL必須)はv1から継承。   |
//|                                                                  |
//|   重大な既知の限界(docs/04参照):                                  |
//|     このエッジはレジーム依存。直近数年(2021-)で強いが2016-21は     |
//|     負け。今後継続する保証は無い。本番前にユーザー実データで要再検証。|
//|                                                                  |
//|   免責: バックテスト/シミュレーションは将来やライブ約定を保証しない。|
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Build"
#property version   "2.00"
#property strict
#property description "FundedNext Stellar 2-Step RSI mean-reversion EA (v2, regime-dependent edge)"

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>
#include <Trade/SymbolInfo.mqh>

//====================================================================
// 入力パラメータ
//====================================================================
input group "=== Challenge Rules (FundedNext Stellar 2-Step) ==="
input double InpInitialBalance   = 100000.0; // 初期残高
input double InpProfitTargetPct  = 8.0;      // 利益目標% (Phase1=8, Phase2=5)
input double InpDailyLossLimitPct= 5.0;      // 規則 日次損失上限%
input double InpMaxLossLimitPct  = 10.0;     // 規則 最大損失上限%

input group "=== Hard Guards (stop BEFORE the rule line) ==="
input double InpDailyStopPct     = 4.0;      // 当日-X%で全決済＆当日新規停止
input double InpDailyNoNewPct    = 3.0;      // 当日-X%で新規のみ停止
input double InpEquityFloorDDPct = 8.0;      // 開始残高比-X%で全決済＆EA停止
input bool   InpCloseAllOnGuard  = true;     // ガード発火で全決済

input group "=== Risk & Sizing ==="
input double InpRiskPerTradePct  = 0.40;     // 1トレードのリスク%
input double InpMaxDailyRiskPct  = 1.20;     // 1日合計リスク%上限
input int    InpMaxTradesPerDay  = 3;        // 1日の最大新規数
input int    InpMaxOpenPositions = 1;        // 同時保有上限
input double InpMinLot           = 0.01;     // 最小ロット
input double InpMaxLot           = 5.0;      // 最大ロット

input group "=== Strategy: RSI Mean-Reversion (daily, counter-trend) ==="
input ENUM_TIMEFRAMES InpSignalTF = PERIOD_D1; // シグナル足(研究は日足。H4/H1も可)
input int    InpRsiPeriod        = 14;       // RSI期間
input double InpRsiBuyLevel      = 27.0;     // RSIがこの値未満で売られ過ぎ→買い
input double InpRsiSellLevel     = 73.0;     // RSIがこの値超で買われ過ぎ→売り
input bool   InpRequireRsiTurn   = true;     // RSIが反転(前足比改善)してから入る
input int    InpAtrPeriod        = 14;       // ATR期間
input int    InpMaxHoldBars      = 10;       // この本数を超えたら時間切れ手仕舞い

input group "=== Stops & Targets ==="
input double InpAtrSLMult        = 1.5;      // SL = ATR×この倍率
input double InpRR               = 1.2;      // TP = SL距離 × RR
input double InpMinStopPips      = 12.0;     // 最小SL距離(pips)
input double InpMaxStopPips      = 250.0;    // 最大SL距離(pips, 日足はATRが大)
input bool   InpUseBreakeven     = true;     // 含み益で建値移動
input double InpBreakevenAtR     = 1.0;      // +Rでブレークイーブン

input group "=== Filters ==="
input double InpMaxSpreadPips    = 3.0;      // 許容最大スプレッド(pips)
input bool   InpUseSession       = false;    // 日足戦略は通常セッション制限不要
input int    InpSessionStartHour = 0;        // (使う場合)取引開始 サーバ時間
input int    InpSessionEndHour   = 23;       // (使う場合)取引終了
input int    InpMinHoldSeconds   = 150;      // 最小保有秒(2分未満フラグ回避)
input bool   InpUseNewsFilter    = true;     // 経済指標フィルタ
input int    InpNewsBeforeMin    = 30;       // 指標前 N分は新規停止
input int    InpNewsAfterMin     = 15;       // 指標後 N分は新規停止
input string InpManualBlackout   = "";       // 手動ブラックアウト "HH:MM-HH:MM;..."

input group "=== Execution ==="
input long   InpMagic            = 920531;   // マジックナンバー(v2)
input int    InpSlippagePoints   = 20;       // 許容スリッページ(points)
input bool   InpVerboseLog       = true;     // 詳細ログ

//====================================================================
// グローバル
//====================================================================
CTrade        trade;
CPositionInfo posinfo;
CSymbolInfo   sym;

int    hRsi=INVALID_HANDLE, hAtr=INVALID_HANDLE;
double g_pip=0.0;
double g_dayStartEquity=0.0;
datetime g_curDay=0;
int    g_tradesToday=0;
double g_riskUsedToday=0.0;
bool   g_eaHalted=false;
bool   g_dayBlocked=false;
datetime g_lastBarTime=0;

//====================================================================
int OnInit()
{
   if(!sym.Name(_Symbol)) { Print("Symbol init failed"); return INIT_FAILED; }
   sym.RefreshRates();

   int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   if(digits==3 || digits==5) g_pip=point*10.0; else g_pip=point;

   hRsi=iRSI(_Symbol,InpSignalTF,InpRsiPeriod,PRICE_CLOSE);
   hAtr=iATR(_Symbol,InpSignalTF,InpAtrPeriod);
   if(hRsi==INVALID_HANDLE || hAtr==INVALID_HANDLE)
   { Print("Indicator handle creation failed"); return INIT_FAILED; }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   if(InpDailyStopPct>=InpDailyLossLimitPct)
      Print("WARNING: DailyStop>=rule daily loss - unsafe!");
   if(InpEquityFloorDDPct>=InpMaxLossLimitPct)
      Print("WARNING: EquityFloorDD>=rule max loss - unsafe!");

   ResetDay(TimeCurrent());
   PrintFormat("[INIT v2] %s pip=%.5f RSI(%d) buy<%.0f sell>%.0f RR=%.2f SLatr=%.2f",
               _Symbol,g_pip,InpRsiPeriod,InpRsiBuyLevel,InpRsiSellLevel,InpRR,InpAtrSLMult);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(hRsi!=INVALID_HANDLE) IndicatorRelease(hRsi);
   if(hAtr!=INVALID_HANDLE) IndicatorRelease(hAtr);
}

//====================================================================
void OnTick()
{
   sym.RefreshRates();

   datetime today=DayStart(TimeCurrent());
   if(today!=g_curDay) ResetDay(TimeCurrent());

   //==================================================================
   // ハードガード(毎ティック・equity=含み損込みで判定)
   //==================================================================
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);

   double floorEquity=InpInitialBalance*(1.0-InpEquityFloorDDPct/100.0);
   if(equity<=floorEquity && !g_eaHalted)
   {
      g_eaHalted=true;
      if(InpCloseAllOnGuard) CloseAllPositions("EQUITY_FLOOR_GUARD");
      PrintFormat("[HALT] Equity %.2f <= floor %.2f. EA stopped.",equity,floorEquity);
   }
   if(g_eaHalted){ ManageGuardOnlyExit(); return; }

   double dailyStopLoss=InpInitialBalance*(InpDailyStopPct/100.0);
   double dayPnL=equity-g_dayStartEquity;
   if(dayPnL<=-dailyStopLoss && !g_dayBlocked)
   {
      g_dayBlocked=true;
      if(InpCloseAllOnGuard) CloseAllPositions("DAILY_STOP_GUARD");
      PrintFormat("[DAILY STOP] dayPnL %.2f <= -%.2f. Flat & no-new today.",dayPnL,dailyStopLoss);
   }

   double targetEquity=InpInitialBalance*(1.0+InpProfitTargetPct/100.0);
   bool targetReached=(equity>=targetEquity);

   //==================================================================
   // 既存ポジ管理(建値移動・時間切れ手仕舞い・最小保有)
   //==================================================================
   ManageOpenPositions();

   //==================================================================
   // 新規エントリー可否
   //==================================================================
   if(g_dayBlocked || targetReached) return;

   double noNewLoss=InpInitialBalance*(InpDailyNoNewPct/100.0);
   if(dayPnL<=-noNewLoss) return;

   if(g_tradesToday>=InpMaxTradesPerDay) return;
   if(g_riskUsedToday+InpRiskPerTradePct>InpMaxDailyRiskPct+1e-9) return;
   if(CountOpenPositions()>=InpMaxOpenPositions) return;

   if(InpUseSession && !InSession(TimeCurrent())) return;
   if(SpreadPips()>InpMaxSpreadPips) return;
   if(InpUseNewsFilter && IsNewsBlackout(TimeCurrent())) return;

   datetime barTime=iTime(_Symbol,InpSignalTF,0);
   if(barTime==g_lastBarTime) return;
   g_lastBarTime=barTime;

   int signal=CheckSignal();
   if(signal!=0) TryEnter(signal);
}

//====================================================================
// シグナル: RSI平均回帰(逆張り)。確定足ベース・ノールックアヘッド。
//   買い: 直近確定足(1)のRSIが買いレベル未満。任意で反転(rsi[1]>rsi[2])確認。
//   売り: 直近確定足(1)のRSIが売りレベル超。任意で反転(rsi[1]<rsi[2])確認。
//====================================================================
int CheckSignal()
{
   double rsi[];
   ArraySetAsSeries(rsi,true);
   // index 0=現在形成中, 1=直近確定足, 2=その前
   if(CopyBuffer(hRsi,0,0,3,rsi)<3) return 0;

   double r1=rsi[1], r2=rsi[2];

   // 買われ過ぎ/売られ過ぎ判定は確定足[1]
   if(r1<InpRsiBuyLevel)
   {
      if(!InpRequireRsiTurn || r1>r2)   // 反転(下げ止まり)確認
         return +1;
   }
   if(r1>InpRsiSellLevel)
   {
      if(!InpRequireRsiTurn || r1<r2)   // 反転(上げ止まり)確認
         return -1;
   }
   return 0;
}

//====================================================================
// エントリー(SL必須・固定%リスク・TP=RR)
//====================================================================
void TryEnter(int dir)
{
   double atr[1];
   if(CopyBuffer(hAtr,0,1,1,atr)<1) return;   // 直近確定足のATR
   double atrPrice=atr[0];
   if(atrPrice<=0) return;

   double ask=sym.Ask();
   double bid=sym.Bid();
   double entry=(dir>0)?ask:bid;

   double stopDistPrice=InpAtrSLMult*atrPrice;
   if(stopDistPrice<=0) return;

   double stopPips=stopDistPrice/g_pip;
   if(stopPips<InpMinStopPips || stopPips>InpMaxStopPips)
   {
      if(InpVerboseLog) PrintFormat("[SKIP] stopPips %.1f out of [%.1f,%.1f]",stopPips,InpMinStopPips,InpMaxStopPips);
      return;
   }

   double sl,tp;
   if(dir>0){ sl=entry-stopDistPrice; tp=entry+InpRR*stopDistPrice; }
   else     { sl=entry+stopDistPrice; tp=entry-InpRR*stopDistPrice; }

   double lots=CalcLots(stopDistPrice);
   if(lots<InpMinLot){ if(InpVerboseLog) Print("[SKIP] lots<min"); return; }

   int d=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   sl=NormalizeDouble(sl,d); tp=NormalizeDouble(tp,d);

   long stopLevelPts=SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL);
   double minDist=stopLevelPts*SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   if(MathAbs(entry-sl)<minDist || MathAbs(tp-entry)<minDist)
   { if(InpVerboseLog) Print("[SKIP] SL/TP within broker stop level"); return; }

   bool ok=false;
   string cmt="FNStellarV2";
   if(dir>0) ok=trade.Buy(lots,_Symbol,0.0,sl,tp,cmt);
   else      ok=trade.Sell(lots,_Symbol,0.0,sl,tp,cmt);

   if(ok)
   {
      g_tradesToday++;
      g_riskUsedToday+=InpRiskPerTradePct;
      PrintFormat("[ENTRY v2] %s lots=%.2f entry~%.5f SL=%.5f TP=%.5f stopPips=%.1f tradesToday=%d",
                  (dir>0?"BUY":"SELL"),lots,entry,sl,tp,stopPips,g_tradesToday);
   }
   else
      PrintFormat("[ENTRY FAIL] ret=%d %s",trade.ResultRetcode(),trade.ResultRetcodeDescription());
}

//====================================================================
double CalcLots(double stopDistPrice)
{
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   double riskMoney=equity*(InpRiskPerTradePct/100.0);

   double tickValue=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double tickSize =SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(tickSize<=0 || tickValue<=0) return 0.0;

   double lossPerLot=(stopDistPrice/tickSize)*tickValue;
   if(lossPerLot<=0) return 0.0;

   double lots=riskMoney/lossPerLot;

   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   double vmin=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double vmax=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   if(step>0) lots=MathFloor(lots/step)*step;   // 切り捨て=リスク超過防止
   lots=MathMax(lots,0.0);
   lots=MathMin(lots,MathMin(InpMaxLot,vmax));
   if(lots<MathMax(InpMinLot,vmin)) return 0.0;
   return lots;
}

//====================================================================
// 既存ポジ管理: 時間切れ手仕舞い / ブレークイーブン / 最小保有 / ニュース
//====================================================================
void ManageOpenPositions()
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0) continue;
      if(!posinfo.SelectByTicket(ticket)) continue;
      if(posinfo.Symbol()!=_Symbol || posinfo.Magic()!=InpMagic) continue;

      long   type=posinfo.PositionType();
      double open=posinfo.PriceOpen();
      double sl  =posinfo.StopLoss();
      double tp  =posinfo.TakeProfit();
      datetime ptime=(datetime)posinfo.Time();
      int    held=(int)(TimeCurrent()-ptime);

      double price=(type==POSITION_TYPE_BUY)?sym.Bid():sym.Ask();
      double rDist=MathAbs(open-sl);
      if(rDist<=0) continue;
      double profitDist=(type==POSITION_TYPE_BUY)?(price-open):(open-price);
      double rMultiple=profitDist/rDist;

      // 時間切れ手仕舞い(InpMaxHoldBars本 経過、最小保有秒も尊重)
      int barSec=PeriodSeconds(InpSignalTF);
      if(barSec>0 && held>=InpMaxHoldBars*barSec && held>=InpMinHoldSeconds)
      { ClosePosition(ticket,"TIME_EXIT"); continue; }

      // ニュース直前の任意クローズは行わない(逆張りは保有が前提)。ガードは別途作動。

      // ブレークイーブン
      if(InpUseBreakeven && rMultiple>=InpBreakevenAtR && held>=InpMinHoldSeconds)
      {
         double be=open;
         bool need=(type==POSITION_TYPE_BUY)?(sl<be-1e-9):(sl>be+1e-9);
         if(need) ModifySL(ticket,be,tp);
      }
   }
}

void ManageGuardOnlyExit()
{
   if(CountOpenPositions()>0 && InpCloseAllOnGuard)
      CloseAllPositions("HALTED_CLEANUP");
}

//====================================================================
void ModifySL(ulong ticket,double sl,double tp)
{
   int d=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   if(!trade.PositionModify(ticket,NormalizeDouble(sl,d),NormalizeDouble(tp,d)))
      if(InpVerboseLog) PrintFormat("[MODIFY FAIL] %d %s",trade.ResultRetcode(),trade.ResultRetcodeDescription());
}

void ClosePosition(ulong ticket,string why)
{
   if(trade.PositionClose(ticket))
   { if(InpVerboseLog) PrintFormat("[CLOSE] ticket=%I64u (%s)",ticket,why); }
   else
      PrintFormat("[CLOSE FAIL] ticket=%I64u ret=%d %s",ticket,trade.ResultRetcode(),trade.ResultRetcodeDescription());
}

void CloseAllPositions(string why)
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0) continue;
      if(!posinfo.SelectByTicket(ticket)) continue;
      if(posinfo.Symbol()!=_Symbol || posinfo.Magic()!=InpMagic) continue;
      ClosePosition(ticket,why);
   }
}

int CountOpenPositions()
{
   int n=0;
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0) continue;
      if(!posinfo.SelectByTicket(ticket)) continue;
      if(posinfo.Symbol()==_Symbol && posinfo.Magic()==InpMagic) n++;
   }
   return n;
}

double SpreadPips()
{
   return (sym.Ask()-sym.Bid())/g_pip;
}

//====================================================================
// 日替わり・セッション
//====================================================================
datetime DayStart(datetime t)
{
   MqlDateTime s; TimeToStruct(t,s);
   s.hour=0; s.min=0; s.sec=0;
   return StructToTime(s);
}

void ResetDay(datetime t)
{
   g_curDay=DayStart(t);
   g_dayStartEquity=AccountInfoDouble(ACCOUNT_EQUITY);
   g_tradesToday=0;
   g_riskUsedToday=0.0;
   g_dayBlocked=false;
   if(InpVerboseLog)
      PrintFormat("[NEW DAY] %s dayStartEquity=%.2f",TimeToString(g_curDay,TIME_DATE),g_dayStartEquity);
}

bool InSession(datetime t)
{
   MqlDateTime s; TimeToStruct(t,s);
   if(s.day_of_week==0 || s.day_of_week==6) return false;
   int h=s.hour;
   if(InpSessionStartHour<=InpSessionEndHour)
      return (h>=InpSessionStartHour && h<=InpSessionEndHour);
   return (h>=InpSessionStartHour || h<=InpSessionEndHour);
}

//====================================================================
// ニュースフィルタ(MT5経済カレンダー＋手動ブラックアウト)
//====================================================================
bool IsNewsBlackout(datetime now)
{
   if(StringLen(InpManualBlackout)>0 && InManualBlackout(now)) return true;
   string base =SymbolInfoString(_Symbol,SYMBOL_CURRENCY_BASE);
   string quote=SymbolInfoString(_Symbol,SYMBOL_CURRENCY_PROFIT);
   datetime from=now-InpNewsAfterMin*60;
   datetime to  =now+InpNewsBeforeMin*60;
   if(CalendarNewsHit(base,from,to,now)) return true;
   if(CalendarNewsHit(quote,from,to,now)) return true;
   return false;
}

bool CalendarNewsHit(string currency,datetime from,datetime to,datetime now)
{
   MqlCalendarValue values[];
   int n=CalendarValueHistory(values,from,to,NULL,currency);
   if(n<=0) return false;
   for(int i=0;i<n;i++)
   {
      MqlCalendarEvent ev;
      if(!CalendarEventById(values[i].event_id,ev)) continue;
      if(ev.importance!=CALENDAR_IMPORTANCE_HIGH) continue;
      datetime et=values[i].time;
      if(et>=now-InpNewsAfterMin*60 && et<=now+InpNewsBeforeMin*60) return true;
   }
   return false;
}

bool InManualBlackout(datetime now)
{
   MqlDateTime s; TimeToStruct(now,s);
   int curMin=s.hour*60+s.min;
   string parts[];
   int cnt=StringSplit(InpManualBlackout,';',parts);
   for(int i=0;i<cnt;i++)
   {
      string seg=parts[i];
      StringTrimLeft(seg); StringTrimRight(seg);
      if(StringLen(seg)==0) continue;
      string se[];
      if(StringSplit(seg,'-',se)!=2) continue;
      int a=ParseHHMM(se[0]); int b=ParseHHMM(se[1]);
      if(a<0||b<0) continue;
      if(a<=b){ if(curMin>=a && curMin<=b) return true; }
      else    { if(curMin>=a || curMin<=b) return true; }
   }
   return false;
}

int ParseHHMM(string hhmm)
{
   StringTrimLeft(hhmm); StringTrimRight(hhmm);
   string p[];
   if(StringSplit(hhmm,':',p)!=2) return -1;
   int h=(int)StringToInteger(p[0]); int m=(int)StringToInteger(p[1]);
   if(h<0||h>23||m<0||m>59) return -1;
   return h*60+m;
}
//+------------------------------------------------------------------+
