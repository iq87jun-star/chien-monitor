//+------------------------------------------------------------------+
//|                                         ChienTrendRider_v130.mq5 |
//|                                                                  |
//| VERIFICATION BUILD v1.30                                          |
//|                                                                  |
//| Every value that affects the result is a compile-time constant,   |
//| not an input. The Strategy Tester keeps the parameter set from    |
//| the previous run and does not adopt new defaults after a          |
//| recompile, which silently produced three backtests on stale       |
//| settings. Constants cannot be overridden by a saved .set file,    |
//| so this build always tests the settings it was built with.        |
//|                                                                  |
//| Strategy (fixed)                                                  |
//|   Trend  : EMA50 vs EMA200, closed bars only                      |
//|   Entry  : close of the last closed bar breaks the Donchian(20)   |
//|            channel of the 20 bars before it, in trend direction   |
//|   Stop   : ATR(14) x 2.0                                          |
//|   Target : ATR(14) x 4.0                                          |
//|   Trail  : ATR(14) x 4.0                                          |
//|   BreakEven : OFF (it closed winners early and cut the PF)        |
//|   Risk   : 0.5% of balance per trade                              |
//|   One position at a time. No averaging down, no martingale.       |
//|                                                                  |
//| No account locks, no expiry date, no external DLLs.               |
//+------------------------------------------------------------------+
#property copyright "iq87jun-star"
#property link      "https://www.gogojungle.co.jp/"
#property version   "1.30"

#include <Trade\Trade.mqh>

#define EA_BUILD "v1.30-FIXED"

//--- fixed strategy settings: deliberately NOT inputs ---------------
const int    FIX_FAST_EMA      = 50;     // fast EMA period
const int    FIX_SLOW_EMA      = 200;    // slow EMA period
const int    FIX_DONCHIAN      = 20;     // Donchian channel period
const int    FIX_ATR_PERIOD    = 14;     // ATR period
const double FIX_SL_ATR        = 2.0;    // stop loss  = ATR x this
const double FIX_TP_ATR        = 4.0;    // take profit = ATR x this
const bool   FIX_USE_BREAKEVEN = false;  // break-even: off by design
const bool   FIX_USE_TRAILING  = true;   // ATR trailing stop
const double FIX_TRAIL_ATR     = 4.0;    // trailing distance = ATR x this
const double FIX_RISK_PERCENT  = 0.5;    // risk per trade, % of balance
const double FIX_MAX_LOT       = 10.0;   // lot cap

//--- operational inputs: none of these change the strategy ----------
input long     InpMagicNumber     = 87130;   // Magic number
input string   InpTradeComment    = "CTR130"; // Order comment
input int      InpSlippagePoints  = 10;      // Max slippage (points)
input int      InpMaxSpreadPoints = 30;      // Max spread (points, 0 = off)

//--- globals
CTrade   g_trade;
int      g_hEmaFast = INVALID_HANDLE;
int      g_hEmaSlow = INVALID_HANDLE;
int      g_hAtr     = INVALID_HANDLE;
datetime g_lastBarTime = 0;

//+------------------------------------------------------------------+
//| Expert initialization                                            |
//+------------------------------------------------------------------+
int OnInit()
  {
   g_hEmaFast = iMA(_Symbol, _Period, FIX_FAST_EMA, 0, MODE_EMA, PRICE_CLOSE);
   g_hEmaSlow = iMA(_Symbol, _Period, FIX_SLOW_EMA, 0, MODE_EMA, PRICE_CLOSE);
   g_hAtr     = iATR(_Symbol, _Period, FIX_ATR_PERIOD);

   if(g_hEmaFast == INVALID_HANDLE || g_hEmaSlow == INVALID_HANDLE ||
      g_hAtr == INVALID_HANDLE)
     {
      Print("Init error: failed to create indicator handles");
      return(INIT_FAILED);
     }

   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetDeviationInPoints(InpSlippagePoints);
   g_trade.SetTypeFillingBySymbol(_Symbol);

   LogSettings();

   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Print the settings this build was compiled with                  |
//+------------------------------------------------------------------+
void LogSettings()
  {
   Print("==================================================");
   PrintFormat("ChienTrendRider %s  (settings are compiled in)", EA_BUILD);
   PrintFormat("Entry   : DONCHIAN %d + EMA %d/%d",
               FIX_DONCHIAN, FIX_FAST_EMA, FIX_SLOW_EMA);
   PrintFormat("Exits   : SL=ATR x %.2f   TP=ATR x %.2f", FIX_SL_ATR, FIX_TP_ATR);
   PrintFormat("Manage  : BreakEven=%s   Trailing=%s (ATR x %.2f)",
               FIX_USE_BREAKEVEN ? "ON" : "OFF",
               FIX_USE_TRAILING  ? "ON" : "OFF", FIX_TRAIL_ATR);
   PrintFormat("Risk    : %.2f%% of balance per trade", FIX_RISK_PERCENT);
   PrintFormat("Spread  : max %d points (only adjustable setting)", InpMaxSpreadPoints);
   Print("Expected shape: win rate near 40%, average win about 2x average loss.");
   Print("A win rate above 60% means an older build is running.");
   Print("==================================================");
  }

//+------------------------------------------------------------------+
//| Expert deinitialization                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(g_hEmaFast != INVALID_HANDLE) IndicatorRelease(g_hEmaFast);
   if(g_hEmaSlow != INVALID_HANDLE) IndicatorRelease(g_hEmaSlow);
   if(g_hAtr     != INVALID_HANDLE) IndicatorRelease(g_hAtr);
  }

//+------------------------------------------------------------------+
//| Expert tick                                                      |
//+------------------------------------------------------------------+
void OnTick()
  {
   ManageOpenPosition();

   if(!IsNewBar())
      return;

   if(HasOpenPosition())
      return;

   if(!IsWeekday())
      return;

   if(!SpreadOk())
      return;

   CheckEntry();
  }

//+------------------------------------------------------------------+
//| New-bar detection                                                |
//+------------------------------------------------------------------+
bool IsNewBar()
  {
   datetime t = iTime(_Symbol, _Period, 0);
   if(t == g_lastBarTime)
      return(false);
   g_lastBarTime = t;
   return(true);
  }

//+------------------------------------------------------------------+
//| Copy one value from an indicator buffer                          |
//+------------------------------------------------------------------+
bool GetBufferValue(const int handle, const int shift, double &value)
  {
   double buf[1];
   if(CopyBuffer(handle, 0, shift, 1, buf) != 1)
      return(false);
   value = buf[0];
   return(true);
  }

//+------------------------------------------------------------------+
//| Entry logic: Donchian breakout in the direction of the trend     |
//+------------------------------------------------------------------+
void CheckEntry()
  {
   double emaFast, emaSlow, atr;
   if(!GetBufferValue(g_hEmaFast, 1, emaFast)) return;
   if(!GetBufferValue(g_hEmaSlow, 1, emaSlow)) return;
   if(!GetBufferValue(g_hAtr, 1, atr))         return;
   if(atr <= 0.0)                              return;

   // channel of the FIX_DONCHIAN bars BEFORE the last closed bar
   int hiIdx = iHighest(_Symbol, _Period, MODE_HIGH, FIX_DONCHIAN, 2);
   int loIdx = iLowest(_Symbol, _Period, MODE_LOW, FIX_DONCHIAN, 2);
   if(hiIdx < 0 || loIdx < 0)
      return;

   double donHigh = iHigh(_Symbol, _Period, hiIdx);
   double donLow  = iLow(_Symbol, _Period, loIdx);
   double close1  = iClose(_Symbol, _Period, 1);

   if(emaFast > emaSlow && close1 > donHigh)
     {
      OpenPosition(ORDER_TYPE_BUY, atr);
      return;
     }
   if(emaFast < emaSlow && close1 < donLow)
      OpenPosition(ORDER_TYPE_SELL, atr);
  }

//+------------------------------------------------------------------+
//| Open a market position with ATR-based SL/TP                      |
//+------------------------------------------------------------------+
void OpenPosition(const ENUM_ORDER_TYPE type, const double atr)
  {
   double price = (type == ORDER_TYPE_BUY)
                  ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                  : SymbolInfoDouble(_Symbol, SYMBOL_BID);

   double slDist = atr * FIX_SL_ATR;
   double tpDist = atr * FIX_TP_ATR;

   double sl = (type == ORDER_TYPE_BUY) ? price - slDist : price + slDist;
   double tp = (type == ORDER_TYPE_BUY) ? price + tpDist : price - tpDist;

   sl = NormalizeDouble(sl, _Digits);
   tp = NormalizeDouble(tp, _Digits);

   double lots = CalcLots(slDist);
   if(lots <= 0.0)
     {
      Print("Lot calculation returned 0 - trade skipped");
      return;
     }

   if(!g_trade.PositionOpen(_Symbol, type, lots, price, sl, tp, InpTradeComment))
      PrintFormat("PositionOpen failed: retcode=%d (%s)",
                  g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
  }

//+------------------------------------------------------------------+
//| Lot size from the fixed risk percentage                          |
//+------------------------------------------------------------------+
double CalcLots(const double slDistance)
  {
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickValue <= 0.0 || tickSize <= 0.0 || slDistance <= 0.0)
      return(0.0);

   double lossPerLot = slDistance / tickSize * tickValue;
   if(lossPerLot <= 0.0)
      return(0.0);

   double riskAmount = AccountInfoDouble(ACCOUNT_BALANCE) * FIX_RISK_PERCENT / 100.0;
   double lots       = riskAmount / lossPerLot;

   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = MathMin(SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX), FIX_MAX_LOT);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   if(lotStep > 0.0)
      lots = MathFloor(lots / lotStep) * lotStep;
   lots = MathMax(minLot, MathMin(maxLot, lots));

   if(lots < minLot)
      return(0.0);
   return(NormalizeDouble(lots, 2));
  }

//+------------------------------------------------------------------+
//| Position lookup (this symbol + magic)                            |
//+------------------------------------------------------------------+
bool HasOpenPosition()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
//| ATR trailing stop (break-even is off in this build)              |
//+------------------------------------------------------------------+
void ManageOpenPosition()
  {
   if(!FIX_USE_TRAILING)
      return;

   double atr;
   if(!GetBufferValue(g_hAtr, 1, atr) || atr <= 0.0)
      return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol ||
         PositionGetInteger(POSITION_MAGIC) != InpMagicNumber)
         continue;

      long   type      = PositionGetInteger(POSITION_TYPE);
      double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      double curSl     = PositionGetDouble(POSITION_SL);
      double curTp     = PositionGetDouble(POSITION_TP);
      double bid       = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double ask       = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

      if(type == POSITION_TYPE_BUY)
        {
         double trailSl = bid - atr * FIX_TRAIL_ATR;
         if(trailSl > openPrice && trailSl > curSl + _Point * 0.5 && trailSl < bid)
           {
            trailSl = NormalizeDouble(trailSl, _Digits);
            if(!g_trade.PositionModify(ticket, trailSl, curTp))
               PrintFormat("PositionModify failed: retcode=%d", g_trade.ResultRetcode());
           }
        }
      else if(type == POSITION_TYPE_SELL)
        {
         double trailSl = ask + atr * FIX_TRAIL_ATR;
         if(trailSl < openPrice && trailSl < curSl - _Point * 0.5 && trailSl > ask)
           {
            trailSl = NormalizeDouble(trailSl, _Digits);
            if(!g_trade.PositionModify(ticket, trailSl, curTp))
               PrintFormat("PositionModify failed: retcode=%d", g_trade.ResultRetcode());
           }
        }
     }
  }

//+------------------------------------------------------------------+
//| Weekday check                                                    |
//+------------------------------------------------------------------+
bool IsWeekday()
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   return(dt.day_of_week >= 1 && dt.day_of_week <= 5);
  }

//+------------------------------------------------------------------+
//| Spread filter                                                    |
//+------------------------------------------------------------------+
bool SpreadOk()
  {
   if(InpMaxSpreadPoints <= 0)
      return(true);
   long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   return(spread <= InpMaxSpreadPoints);
  }
//+------------------------------------------------------------------+
