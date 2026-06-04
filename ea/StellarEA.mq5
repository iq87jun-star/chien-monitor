//+------------------------------------------------------------------+
//|                                                     StellarEA.mq5 |
//|        Regime-Adaptive Multi-Strategy EA + Prop-Firm Risk Guard   |
//|              Target: FundedNext-style challenges (MT5 / MQL5)     |
//+------------------------------------------------------------------+
//| Strategy summary                                                  |
//|  - Detect market regime with ADX + higher-timeframe EMA bias.     |
//|      * TREND  (ADX >= trend level)  -> pullback trend-following.   |
//|      * RANGE  (ADX <  range level)  -> Bollinger + RSI reversion.  |
//|      * NEUTRAL (between)            -> stand aside.                |
//|  - Position size from % risk of equity using the real SL distance |
//|    (ATR based) and the symbol tick value -> works on any symbol.  |
//|  - Hard prop-firm guards: daily loss limit + max overall          |
//|    drawdown; trading halts automatically when breached.           |
//|                                                                   |
//| DISCLAIMER: No EA can guarantee a profitable "edge". Past results  |
//| do not guarantee future returns. Forward-test on demo first.      |
//+------------------------------------------------------------------+
#property copyright "Stellar EA"
#property link      ""
#property version   "2.00"
#property description "Regime-adaptive EA: trend-follow in trends, mean-revert in ranges, with strict prop-firm drawdown guards."

#include <Trade/Trade.mqh>

//================================ INPUTS ===========================//
input group "=== General ==="
input long            InpMagic          = 870124;       // Magic number
input string          InpComment        = "StellarEA";  // Order comment
input ENUM_TIMEFRAMES InpTradeTF        = PERIOD_M15;    // Trading timeframe
input ENUM_TIMEFRAMES InpHtfTF          = PERIOD_H4;     // Higher timeframe (bias)
input int             InpSlippage       = 30;           // Max slippage (points)

input group "=== Regime Detection ==="
input int    InpAdxPeriod     = 14;     // ADX period
input double InpAdxTrendLevel = 25.0;   // ADX >= this => TREND regime
input double InpAdxRangeLevel = 20.0;   // ADX <  this => RANGE regime
input int    InpHtfEmaPeriod  = 200;    // HTF EMA for directional bias

input group "=== Trend Module ==="
input int    InpFastEma       = 21;     // Fast EMA (trade TF)
input int    InpSlowEma       = 50;     // Slow EMA (trade TF)
input int    InpPullbackEma   = 21;     // Pullback EMA for entries

input group "=== Range Module ==="
input int    InpBbPeriod      = 20;     // Bollinger period
input double InpBbDev         = 2.0;    // Bollinger deviations
input int    InpRsiPeriod     = 14;     // RSI period
input double InpRsiOversold   = 30.0;   // RSI oversold level
input double InpRsiOverbought = 70.0;   // RSI overbought level

input group "=== Stops & Targets ==="
input int    InpAtrPeriod     = 14;     // ATR period
input double InpSlAtrMult     = 2.0;    // Stop loss = ATR * mult
input double InpTrendRR       = 2.0;    // Trend reward:risk
input double InpRangeRR       = 1.2;    // Range reward:risk
input bool   InpUseBreakeven  = true;   // Enable breakeven move
input double InpBeTriggerAtr  = 1.0;    // Move to BE after profit >= ATR*mult
input double InpBeLockAtr     = 0.10;   // Locked profit at BE (ATR*mult)
input bool   InpUseTrailing   = true;   // Enable ATR trailing stop
input double InpTrailAtrMult  = 2.0;    // Trailing distance = ATR * mult

input group "=== Risk Management (Prop-Firm) ==="
input double InpRiskPercent     = 0.75; // Risk per trade (% of equity)
input double InpInitialBalance  = 0.0;  // Account start balance (0 = auto)
input double InpDailyLossPct    = 4.0;  // Daily loss limit (% of day-start equity)
input double InpMaxDrawdownPct  = 8.0;  // Max overall DD (% of initial balance)
input int    InpMaxPositions    = 1;    // Max concurrent positions
input int    InpMaxTradesPerDay = 6;    // Max new trades per day
input bool   InpCloseOnDailyStop= true; // Close all when daily limit hit

input group "=== Filters ==="
input double InpMaxSpreadPoints = 50.0; // Max spread in points (0 = off)
input bool   InpUseSessionFilter= true; // Restrict trading hours
input int    InpSessionStartHour= 7;    // Session start hour (server time)
input int    InpSessionEndHour  = 20;   // Session end hour (server time)

//=============================== GLOBALS ===========================//
CTrade   trade;

int      hHtfEma = INVALID_HANDLE;
int      hFastEma= INVALID_HANDLE;
int      hSlowEma= INVALID_HANDLE;
int      hPullEma= INVALID_HANDLE;
int      hAdx    = INVALID_HANDLE;
int      hRsi    = INVALID_HANDLE;
int      hBands  = INVALID_HANDLE;
int      hAtr    = INVALID_HANDLE;

datetime g_lastBarTime   = 0;
double   g_initialBalance= 0.0;
double   g_dayStartEquity= 0.0;
int      g_currentDay    = -1;
int      g_tradesToday   = 0;
bool     g_haltToday     = false;
bool     g_haltPermanent = false;

//============================== HELPERS ============================//
// Read a single indicator buffer value at a given shift.
double IndVal(const int handle, const int buffer, const int shift)
{
   double a[];
   if(CopyBuffer(handle, buffer, shift, 1, a) != 1)
      return EMPTY_VALUE;
   return a[0];
}

double NP(const double price) { return NormalizeDouble(price, _Digits); }

bool IsNewBar()
{
   datetime bt = iTime(_Symbol, InpTradeTF, 0);
   if(bt != g_lastBarTime)
   {
      g_lastBarTime = bt;
      return true;
   }
   return false;
}

int CountMyPositions()
{
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      n++;
   }
   return n;
}

void CloseAllMine()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      trade.PositionClose(ticket);
   }
}

//============================== INIT ==============================//
int OnInit()
{
   hHtfEma  = iMA(_Symbol, InpHtfTF,   InpHtfEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   hFastEma = iMA(_Symbol, InpTradeTF, InpFastEma,      0, MODE_EMA, PRICE_CLOSE);
   hSlowEma = iMA(_Symbol, InpTradeTF, InpSlowEma,      0, MODE_EMA, PRICE_CLOSE);
   hPullEma = iMA(_Symbol, InpTradeTF, InpPullbackEma,  0, MODE_EMA, PRICE_CLOSE);
   hAdx     = iADX(_Symbol, InpTradeTF, InpAdxPeriod);
   hRsi     = iRSI(_Symbol, InpTradeTF, InpRsiPeriod, PRICE_CLOSE);
   hBands   = iBands(_Symbol, InpTradeTF, InpBbPeriod, 0, InpBbDev, PRICE_CLOSE);
   hAtr     = iATR(_Symbol, InpTradeTF, InpAtrPeriod);

   if(hHtfEma==INVALID_HANDLE || hFastEma==INVALID_HANDLE || hSlowEma==INVALID_HANDLE ||
      hPullEma==INVALID_HANDLE || hAdx==INVALID_HANDLE || hRsi==INVALID_HANDLE ||
      hBands==INVALID_HANDLE || hAtr==INVALID_HANDLE)
   {
      Print("StellarEA: failed to create one or more indicator handles.");
      return INIT_FAILED;
   }

   if(InpAdxRangeLevel > InpAdxTrendLevel)
      Print("StellarEA: warning - range level above trend level; NEUTRAL zone is inverted.");

   g_initialBalance = (InpInitialBalance > 0.0) ? InpInitialBalance
                                                : AccountInfoDouble(ACCOUNT_BALANCE);

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippage);
   trade.SetTypeFillingBySymbol(_Symbol);

   UpdateDayState(true);

   PrintFormat("StellarEA initialised. InitialBalance=%.2f  TradeTF=%s  HTF=%s",
               g_initialBalance, EnumToString(InpTradeTF), EnumToString(InpHtfTF));
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   IndicatorRelease(hHtfEma);
   IndicatorRelease(hFastEma);
   IndicatorRelease(hSlowEma);
   IndicatorRelease(hPullEma);
   IndicatorRelease(hAdx);
   IndicatorRelease(hRsi);
   IndicatorRelease(hBands);
   IndicatorRelease(hAtr);
}

//============================== TICK =============================//
void OnTick()
{
   UpdateDayState(false);
   CheckRiskGuards();

   // Manage open trades on every tick (trailing / breakeven).
   ManageOpenPositions();

   if(g_haltPermanent || g_haltToday)
      return;

   // Entry decisions only on a freshly closed bar.
   if(!IsNewBar())
      return;

   TryEntry();
}

//=========================== DAY / RISK ==========================//
void UpdateDayState(const bool force)
{
   MqlDateTime t;
   TimeToStruct(TimeCurrent(), t);
   if(force || t.day_of_year != g_currentDay)
   {
      g_currentDay     = t.day_of_year;
      g_dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
      g_tradesToday    = 0;
      g_haltToday      = false;
   }
}

void CheckRiskGuards()
{
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);

   // Daily loss limit (relative to equity at the start of the trading day).
   if(!g_haltToday && InpDailyLossPct > 0.0)
   {
      double floor = g_dayStartEquity * (1.0 - InpDailyLossPct / 100.0);
      if(eq <= floor)
      {
         g_haltToday = true;
         if(InpCloseOnDailyStop) CloseAllMine();
         PrintFormat("StellarEA: daily loss limit hit (equity %.2f <= %.2f). Halt for today.", eq, floor);
      }
   }

   // Max overall drawdown (relative to the configured initial balance).
   if(!g_haltPermanent && InpMaxDrawdownPct > 0.0)
   {
      double floor = g_initialBalance * (1.0 - InpMaxDrawdownPct / 100.0);
      if(eq <= floor)
      {
         g_haltPermanent = true;
         CloseAllMine();
         PrintFormat("StellarEA: max drawdown hit (equity %.2f <= %.2f). Halt permanently.", eq, floor);
      }
   }
}

//============================ FILTERS ============================//
bool PassFilters()
{
   if(InpMaxSpreadPoints > 0.0)
   {
      double spread = (double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
      if(spread > InpMaxSpreadPoints)
         return false;
   }

   if(InpUseSessionFilter)
   {
      MqlDateTime t;
      TimeToStruct(TimeCurrent(), t);
      int h = t.hour;
      bool inSession;
      if(InpSessionStartHour <= InpSessionEndHour)
         inSession = (h >= InpSessionStartHour && h < InpSessionEndHour);
      else // session wraps past midnight
         inSession = (h >= InpSessionStartHour || h < InpSessionEndHour);
      if(!inSession)
         return false;
   }
   return true;
}

//============================= ENTRY ============================//
void TryEntry()
{
   if(CountMyPositions() >= InpMaxPositions) return;
   if(g_tradesToday      >= InpMaxTradesPerDay) return;
   if(!PassFilters()) return;

   double adx1   = IndVal(hAdx,    0, 1);
   double htfEma = IndVal(hHtfEma, 0, 1);
   double fast1  = IndVal(hFastEma,0, 1);
   double slow1  = IndVal(hSlowEma,0, 1);
   double pull1  = IndVal(hPullEma,0, 1);
   double atr1   = IndVal(hAtr,    0, 1);

   if(adx1==EMPTY_VALUE || htfEma==EMPTY_VALUE || fast1==EMPTY_VALUE ||
      slow1==EMPTY_VALUE || pull1==EMPTY_VALUE || atr1==EMPTY_VALUE || atr1<=0.0)
      return;

   double close1 = iClose(_Symbol, InpTradeTF, 1);
   double low1   = iLow  (_Symbol, InpTradeTF, 1);
   double high1  = iHigh (_Symbol, InpTradeTF, 1);

   bool biasUp = (close1 > htfEma && fast1 > slow1);
   bool biasDn = (close1 < htfEma && fast1 < slow1);

   bool longSig = false, shortSig = false;
   double rr = InpTrendRR;

   if(adx1 >= InpAdxTrendLevel)              // ---- TREND: pullback continuation ----
   {
      if(biasUp && low1  <= pull1 && close1 > pull1) longSig  = true;
      if(biasDn && high1 >= pull1 && close1 < pull1) shortSig = true;
      rr = InpTrendRR;
   }
   else if(adx1 < InpAdxRangeLevel)          // ---- RANGE: mean reversion ----
   {
      double upper1 = IndVal(hBands, 1, 1);
      double lower1 = IndVal(hBands, 2, 1);
      double rsi1   = IndVal(hRsi,   0, 1);
      if(upper1==EMPTY_VALUE || lower1==EMPTY_VALUE || rsi1==EMPTY_VALUE)
         return;
      if(close1 <= lower1 && rsi1 < InpRsiOversold)   longSig  = true;
      if(close1 >= upper1 && rsi1 > InpRsiOverbought)  shortSig = true;
      rr = InpRangeRR;
   }
   // else NEUTRAL zone -> no trade.

   if(longSig)       OpenTrade(ORDER_TYPE_BUY,  atr1, rr);
   else if(shortSig) OpenTrade(ORDER_TYPE_SELL, atr1, rr);
}

void OpenTrade(const ENUM_ORDER_TYPE type, const double atr, const double rr)
{
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   bool   buy = (type == ORDER_TYPE_BUY);
   double entry = buy ? ask : bid;

   double slDist = atr * InpSlAtrMult;
   double stopsLvl = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   if(slDist < stopsLvl) slDist = stopsLvl * 1.5;
   if(slDist <= 0.0) return;

   double sl, tp;
   if(buy) { sl = entry - slDist; tp = entry + slDist * rr; }
   else    { sl = entry + slDist; tp = entry - slDist * rr; }

   double lot = CalcLot(slDist);
   if(lot <= 0.0)
   {
      Print("StellarEA: computed lot below symbol minimum for the risk budget; skipping trade.");
      return;
   }

   bool ok;
   if(buy) ok = trade.Buy (lot, _Symbol, 0.0, NP(sl), NP(tp), InpComment);
   else    ok = trade.Sell(lot, _Symbol, 0.0, NP(sl), NP(tp), InpComment);

   if(ok)
   {
      g_tradesToday++;
      PrintFormat("StellarEA: %s %.2f lots @~%.5f  SL=%.5f TP=%.5f (trade %d/%d today)",
                  (buy?"BUY":"SELL"), lot, entry, sl, tp, g_tradesToday, InpMaxTradesPerDay);
   }
   else
   {
      PrintFormat("StellarEA: order failed. retcode=%d  %s", trade.ResultRetcode(),
                  trade.ResultRetcodeDescription());
   }
}

// Position size from % equity risk and the real stop distance (any symbol).
double CalcLot(const double slDistPrice)
{
   double eq       = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskAmt  = eq * InpRiskPercent / 100.0;
   double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickVal <= 0.0 || tickSize <= 0.0 || slDistPrice <= 0.0)
      return 0.0;

   double moneyPerPricePerLot = tickVal / tickSize;     // money per 1.0 price move / lot
   double lossPerLot = slDistPrice * moneyPerPricePerLot;
   if(lossPerLot <= 0.0) return 0.0;

   double lot = riskAmt / lossPerLot;

   double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step <= 0.0) step = 0.01;

   lot = MathFloor(lot / step) * step;
   if(lot > maxLot) lot = maxLot;
   if(lot < minLot) return 0.0;   // refuse to over-risk: skip rather than force min lot
   return lot;
}

//======================= POSITION MANAGEMENT ====================//
void ManageOpenPositions()
{
   if(!InpUseBreakeven && !InpUseTrailing) return;

   double atrNow = IndVal(hAtr, 0, 0);
   if(atrNow == EMPTY_VALUE || atrNow <= 0.0)
      atrNow = IndVal(hAtr, 0, 1);
   if(atrNow == EMPTY_VALUE || atrNow <= 0.0) return;

   double stopsLvl = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;

      long   ptype  = PositionGetInteger(POSITION_TYPE);
      double openP  = PositionGetDouble(POSITION_PRICE_OPEN);
      double curSL  = PositionGetDouble(POSITION_SL);
      double curTP  = PositionGetDouble(POSITION_TP);

      if(ptype == POSITION_TYPE_BUY)
      {
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double newSL = curSL;
         if(InpUseBreakeven && (bid - openP) >= atrNow * InpBeTriggerAtr)
         {
            double be = openP + atrNow * InpBeLockAtr;
            if(be > newSL) newSL = be;
         }
         if(InpUseTrailing)
         {
            double tr = bid - atrNow * InpTrailAtrMult;
            if(tr > newSL) newSL = tr;
         }
         if(newSL > curSL + _Point && newSL < bid - stopsLvl)
            trade.PositionModify(ticket, NP(newSL), curTP);
      }
      else if(ptype == POSITION_TYPE_SELL)
      {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double newSL = curSL;
         if(InpUseBreakeven && (openP - ask) >= atrNow * InpBeTriggerAtr)
         {
            double be = openP - atrNow * InpBeLockAtr;
            if(curSL == 0.0 || be < newSL) newSL = be;
         }
         if(InpUseTrailing)
         {
            double tr = ask + atrNow * InpTrailAtrMult;
            if(curSL == 0.0 || tr < newSL) newSL = tr;
         }
         if(newSL > 0.0 && (curSL == 0.0 || newSL < curSL - _Point) && newSL > ask + stopsLvl)
            trade.PositionModify(ticket, NP(newSL), curTP);
      }
   }
}
//+------------------------------------------------------------------+
