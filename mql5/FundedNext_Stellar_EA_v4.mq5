//+------------------------------------------------------------------+
//|                                 FundedNext_Stellar_EA_v4.mq5      |
//|   FundedNext "Stellar 2-Step" ($100K) ― v4 H4 順張り(継続)        |
//|                                                                  |
//|   v3(D1逆張り・多信号アンサンブル)は実bid/ask検証(Dukascopy 10年)で |
//|   採用不可: 取引が希少(年7件)、Wilson下限>BE=False、fundednext合否  |
//|   =False。修正としてシグナル足を D1→H4 に降ろし頻度を稼いだところ、 |
//|   同じ4条件を『逆張り』ではなく『順張り(トレンド継続)』で読むと     |
//|   手元2.8年のOOSで PF>1 が一貫した(docs/10)。本v4はその順張り版。   |
//|                                                                  |
//|   ロジック(H4確定足・ノールックアヘッド): 4つの行き過ぎ条件のうち   |
//|   K個以上が同方向に立ったら、その『逆方向』(=継続側)にエントリー:   |
//|     (1) RSI(14) < 35 / > 65                                       |
//|     (2) 終値ボリンジャーZ(20) < -1.5 / > +1.5                     |
//|     (3) 連続下落/上昇 ≧3本                                        |
//|     (4) 当日(H4)リターン < -0.25% / > +0.25%                      |
//|   売られすぎ票がK以上 → 継続(SELL)、買われすぎ票がK以上 → 継続(BUY)。|
//|   InpMomentum=false にすると v3 同等の逆張りに戻る(対照群)。        |
//|   SL=1.5ATR(H4), TP=SL×1.2, MaxHoldBars本(H4)で時間切れ。         |
//|                                                                  |
//|   ★★ 重大な前提 ★★                                              |
//|   本EAは検証『前』の仮説段階。research/FundedNext_v4_H4_momentum_   |
//|   validation.ipynb の合否ゲート(Cell16)を長期データで通過するまで、 |
//|   ライブ/funded口座に載せないこと。まずMT5テスター/デモで検証用。   |
//|   手元2.8年の所見は直近偏重で、IS側がマイナスのセルが多い(=v3と同じ |
//|   レジーム依存の罠を排除できていない)。                            |
//|                                                                  |
//|   免責: バックテスト/シミュレーションは将来やライブ約定を保証しない。|
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Build"
#property version   "4.00"
#property strict
#property description "FundedNext Stellar v4 H4 trend-continuation (momentum) EA — VALIDATION-STAGE, not for live until gate passes"

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>
#include <Trade/SymbolInfo.mqh>

//====================================================================
input group "=== Challenge Rules (FundedNext Stellar 2-Step) ==="
input double InpInitialBalance   = 100000.0;
input double InpProfitTargetPct  = 8.0;      // Phase1=8, Phase2=5
input double InpDailyLossLimitPct= 5.0;
input double InpMaxLossLimitPct  = 10.0;

input group "=== Hard Guards (stop BEFORE the rule line) ==="
input double InpDailyStopPct     = 4.0;
input double InpDailyNoNewPct    = 3.0;
input double InpEquityFloorDDPct = 8.0;
input bool   InpCloseAllOnGuard  = true;

input group "=== Risk & Sizing ==="
input double InpRiskPerTradePct  = 0.40;
input double InpMaxDailyRiskPct  = 1.20;
input int    InpMaxTradesPerDay  = 3;
input int    InpMaxOpenPositions = 1;
input double InpMinLot           = 0.01;
input double InpMaxLot           = 5.0;

input group "=== Strategy: H4 trend-continuation (momentum) ==="
input ENUM_TIMEFRAMES InpSignalTF = PERIOD_H4; // シグナル足(研究はH4)
input bool   InpMomentum         = true;     // true=順張り(継続) / false=逆張り(=v3相当の対照群)
input int    InpVotesRequired    = 3;        // 一致が必要な条件数 K (1..4)。プロト最良帯=3
input int    InpRsiPeriod        = 14;       // 条件(1) RSI期間
input double InpRsiBuyLevel      = 35.0;     // 条件(1) RSI<これ で「売られすぎ」票
input double InpRsiSellLevel     = 65.0;     // 条件(1) RSI>これ で「買われすぎ」票
input int    InpBBPeriod         = 20;       // 条件(2) Zスコアの期間(SMA/STD)
input double InpBBZThreshold     = 1.5;      // 条件(2) |Z|>これ で票
input int    InpStreakBars       = 3;        // 条件(3) 連続本数≧これ で票
input double InpRetThreshold     = 0.0025;   // 条件(4) |H4リターン|>これ で票(0.0025=0.25%)
input int    InpAtrPeriod        = 14;       // ATR期間
input int    InpMaxHoldBars      = 12;       // この本数(H4)で時間切れ手仕舞い(=48時間)

input group "=== Stops & Targets ==="
input double InpAtrSLMult        = 1.5;      // SL = ATR×倍率
input double InpRR               = 1.0;      // TP = SL距離 × RR(プロトでOOS堅牢だった1.0)
input double InpMinStopPips      = 6.0;      // H4のATRは小さいので下限を緩和
input double InpMaxStopPips      = 250.0;
input bool   InpUseBreakeven     = true;
input double InpBreakevenAtR     = 1.0;

input group "=== Filters ==="
input double InpMaxSpreadPips    = 3.0;
input bool   InpUseSession       = false;
input int    InpSessionStartHour = 0;
input int    InpSessionEndHour   = 23;
input int    InpMinHoldSeconds   = 150;
input bool   InpUseNewsFilter    = true;
input int    InpNewsBeforeMin    = 30;
input int    InpNewsAfterMin     = 15;
input string InpManualBlackout   = "";

input group "=== Execution ==="
input long   InpMagic            = 920540;   // v4
input int    InpSlippagePoints   = 20;
input bool   InpVerboseLog       = true;

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
   if(!sym.Name(_Symbol)){ Print("Symbol init failed"); return INIT_FAILED; }
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

   if(InpDailyStopPct>=InpDailyLossLimitPct) Print("WARNING: DailyStop>=rule - unsafe!");
   if(InpEquityFloorDDPct>=InpMaxLossLimitPct) Print("WARNING: EquityFloorDD>=rule - unsafe!");
   if(InpVotesRequired<1 || InpVotesRequired>4) Print("WARNING: VotesRequired should be 1..4");

   ResetDay(TimeCurrent());
   PrintFormat("[INIT v4] %s pip=%.5f TF=%d momentum=%s K=%d RSI(%d)<%.0f/>%.0f BBz>%.1f streak>=%d ret>%.4f RR=%.2f hold=%d",
               _Symbol,g_pip,InpSignalTF,(InpMomentum?"true":"false"),InpVotesRequired,
               InpRsiPeriod,InpRsiBuyLevel,InpRsiSellLevel,InpBBZThreshold,InpStreakBars,
               InpRetThreshold,InpRR,InpMaxHoldBars);
   if(InpVerboseLog)
      Print("[NOTE] v4 is VALIDATION-STAGE. Do NOT run live/funded until the .ipynb gate (Cell16) passes on long-term data.");
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

   // ===== ハードガード(毎ティック・含み損込みequity) =====
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);

   double floorEquity=InpInitialBalance*(1.0-InpEquityFloorDDPct/100.0);
   if(equity<=floorEquity && !g_eaHalted)
   {
      g_eaHalted=true;
      if(InpCloseAllOnGuard) CloseAllPositions("EQUITY_FLOOR_GUARD");
      PrintFormat("[HALT] Equity %.2f <= floor %.2f.",equity,floorEquity);
   }
   if(g_eaHalted){ ManageGuardOnlyExit(); return; }

   double dailyStopLoss=InpInitialBalance*(InpDailyStopPct/100.0);
   double dayPnL=equity-g_dayStartEquity;
   if(dayPnL<=-dailyStopLoss && !g_dayBlocked)
   {
      g_dayBlocked=true;
      if(InpCloseAllOnGuard) CloseAllPositions("DAILY_STOP_GUARD");
      PrintFormat("[DAILY STOP] dayPnL %.2f <= -%.2f.",dayPnL,dailyStopLoss);
   }

   double targetEquity=InpInitialBalance*(1.0+InpProfitTargetPct/100.0);
   bool targetReached=(equity>=targetEquity);

   ManageOpenPositions();

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
// シグナル: 4条件の票を集計。確定足ベース・ノールックアヘッド。
//   research/colab_h4_momentum_validation.py compute_signals_h4 の忠実移植。
//   全判定は直近確定足 index=1 (とその過去) で行う。
//   InpMomentum=true のとき最終シグナルの符号を反転(=順張り/継続)。
//====================================================================
int CheckSignal()
{
   // RSI: index1=直近確定足
   double rsi[];
   ArraySetAsSeries(rsi,true);
   if(CopyBuffer(hRsi,0,0,3,rsi)<3) return 0;
   double r1=rsi[1];

   int need = InpBBPeriod + InpStreakBars + 5;
   double close[];
   ArraySetAsSeries(close,true);
   if(CopyClose(_Symbol,InpSignalTF,0,need,close)<need) return 0;
   // close[1]=直近確定足終値, close[2]=その前 ...

   // --- 条件(2) ボリンジャーZ: 母集団=close[2..(BBPeriod+1)] の n本、対象=close[1] ---
   double sum=0.0;
   for(int j=2;j<2+InpBBPeriod;j++) sum+=close[j];
   double mean=sum/InpBBPeriod;
   double var=0.0;
   for(int j=2;j<2+InpBBPeriod;j++){ double d=close[j]-mean; var+=d*d; }
   var/= (InpBBPeriod-1);                 // 標本分散(ddof=1)
   double sd=MathSqrt(var);
   double z=(sd>0.0)?(close[1]-mean)/sd : 0.0;
   bool zlo=(sd>0.0)&&(z<-InpBBZThreshold);
   bool zhi=(sd>0.0)&&(z> InpBBZThreshold);

   // --- 条件(3) 連続下落/上昇本数: close[1]時点 ---
   int downStreak=0, upStreak=0;
   for(int j=1;j<1+InpStreakBars+2;j++)
   {
      if(close[j]<close[j+1]) downStreak++; else break;
   }
   for(int j=1;j<1+InpStreakBars+2;j++)
   {
      if(close[j]>close[j+1]) upStreak++; else break;
   }

   // --- 条件(4) 当日(確定足[1])リターン = (close[1]-close[2])/close[2] ---
   double ret=(close[2]!=0.0)?(close[1]-close[2])/close[2] : 0.0;

   // --- 票集計(売られすぎ=buy_votes, 買われすぎ=sell_votes) ---
   int buy_votes = (r1<InpRsiBuyLevel?1:0) + (zlo?1:0)
                 + (downStreak>=InpStreakBars?1:0) + (ret<-InpRetThreshold?1:0);
   int sell_votes= (r1>InpRsiSellLevel?1:0) + (zhi?1:0)
                 + (upStreak>=InpStreakBars?1:0) + (ret> InpRetThreshold?1:0);

   // 逆張りの素シグナル: 売られすぎ→+1(買), 買われすぎ→-1(売)
   int raw=0;
   if(buy_votes>=InpVotesRequired && buy_votes>sell_votes) raw=+1;
   else if(sell_votes>=InpVotesRequired && sell_votes>buy_votes) raw=-1;
   if(raw==0) return 0;

   // 順張り(継続)なら符号反転
   int dir = InpMomentum ? -raw : raw;

   if(InpVerboseLog)
      PrintFormat("[SIGNAL] %s votes(buy=%d sell=%d) raw=%d -> dir=%d (rsi=%.1f z=%.2f down=%d up=%d ret=%.4f)",
                  (dir>0?"BUY":"SELL"),buy_votes,sell_votes,raw,dir,r1,z,downStreak,upStreak,ret);
   return dir;
}

//====================================================================
void TryEnter(int dir)
{
   double atr[1];
   if(CopyBuffer(hAtr,0,1,1,atr)<1) return;
   double atrPrice=atr[0];
   if(atrPrice<=0) return;

   double entry=(dir>0)?sym.Ask():sym.Bid();
   double stopDistPrice=InpAtrSLMult*atrPrice;
   if(stopDistPrice<=0) return;

   double stopPips=stopDistPrice/g_pip;
   if(stopPips<InpMinStopPips || stopPips>InpMaxStopPips)
   { if(InpVerboseLog) PrintFormat("[SKIP] stopPips %.1f out of range",stopPips); return; }

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
   string cmt="FNStellarV4";
   if(dir>0) ok=trade.Buy(lots,_Symbol,0.0,sl,tp,cmt);
   else      ok=trade.Sell(lots,_Symbol,0.0,sl,tp,cmt);

   if(ok)
   {
      g_tradesToday++;
      g_riskUsedToday+=InpRiskPerTradePct;
      PrintFormat("[ENTRY v4] %s lots=%.2f entry~%.5f SL=%.5f TP=%.5f stopPips=%.1f tradesToday=%d",
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
   if(CountOpenPositions()>0 && InpCloseAllOnGuard) CloseAllPositions("HALTED_CLEANUP");
}

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

double SpreadPips(){ return (sym.Ask()-sym.Bid())/g_pip; }

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
   if(InpVerboseLog) PrintFormat("[NEW DAY] %s dayStartEquity=%.2f",TimeToString(g_curDay,TIME_DATE),g_dayStartEquity);
}

bool InSession(datetime t)
{
   MqlDateTime s; TimeToStruct(t,s);
   if(s.day_of_week==0 || s.day_of_week==6) return false;
   int h=s.hour;
   if(InpSessionStartHour<=InpSessionEndHour) return (h>=InpSessionStartHour && h<=InpSessionEndHour);
   return (h>=InpSessionStartHour || h<=InpSessionEndHour);
}

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
