//+------------------------------------------------------------------+
//|                                         ChienTrendRider_v140.mq4 |
//|                                                                  |
//| VERIFICATION BUILD v1.40                                          |
//|                                                                  |
//| Every value that affects the result is a compile-time constant,   |
//| not an input, so a saved tester parameter set cannot override it. |
//| Same strategy and settings as the MT5 build of the same version.  |
//|                                                                  |
//|   Trend  : EMA50 vs EMA200, closed bars only                      |
//|   Entry  : close of the last closed bar breaks the Donchian(20)   |
//|            channel of the 20 bars before it, in trend direction   |
//|   Stop   : ATR(14) x 2.0    Target : ATR(14) x 4.0                |
//|   Trail  : ATR(14) x 4.0    BreakEven : OFF                       |
|   Regime : trade only when |EMA50-EMA200| >= ATR x 2.0            |
//|   Risk   : 0.5% of balance per trade                              |
//|   One position at a time. No averaging down, no martingale.       |
//+------------------------------------------------------------------+
#property copyright "iq87jun-star"
#property link      "https://www.gogojungle.co.jp/"
#property version   "1.40"
#property strict

#define EA_BUILD "v1.40-FIXED"

//--- fixed strategy settings: deliberately NOT inputs ---------------
const int    FIX_FAST_EMA      = 50;
const int    FIX_SLOW_EMA      = 200;
const int    FIX_DONCHIAN      = 20;
const int    FIX_ATR_PERIOD    = 14;
const double FIX_SL_ATR        = 2.0;
const double FIX_TP_ATR        = 4.0;
const bool   FIX_USE_BREAKEVEN = false;
const bool   FIX_USE_TRAILING  = true;
const double FIX_TRAIL_ATR     = 4.0;
const double FIX_RISK_PERCENT  = 0.5;
const double FIX_MAX_LOT       = 10.0;
const double FIX_MIN_EMA_SEP   = 2.0;    // require |EMA50-EMA200| >= ATR x this

//--- operational inputs: none of these change the strategy ----------
extern int    InpMagicNumber     = 87140;    // Magic number
extern string InpTradeComment    = "CTR140"; // Order comment
extern int    InpSlippagePoints  = 10;       // Max slippage (points)
extern int    InpMaxSpreadPoints = 30;       // Max spread (points, 0 = off)
extern bool   InpEcnMode         = false;    // ECN mode (SL/TP via modify)

//--- globals
datetime g_lastBarTime = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
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
   PrintFormat("Regime  : trade only when |EMA50-EMA200| >= ATR x %.2f", FIX_MIN_EMA_SEP);
   PrintFormat("Risk    : %.2f%% of balance per trade", FIX_RISK_PERCENT);
   PrintFormat("Spread  : max %d points (only adjustable setting)", InpMaxSpreadPoints);
   Print("Expected shape: win rate near 40%, average win about 2x average loss.");
   Print("A win rate above 60% means an older build is running.");
   Print("==================================================");
  }

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
bool IsNewBar()
  {
   datetime t = iTime(Symbol(), Period(), 0);
   if(t == g_lastBarTime)
      return(false);
   g_lastBarTime = t;
   return(true);
  }

//+------------------------------------------------------------------+
//| Entry logic: Donchian breakout in the direction of the trend     |
//+------------------------------------------------------------------+
void CheckEntry()
  {
   double emaFast = iMA(Symbol(), Period(), FIX_FAST_EMA, 0, MODE_EMA, PRICE_CLOSE, 1);
   double emaSlow = iMA(Symbol(), Period(), FIX_SLOW_EMA, 0, MODE_EMA, PRICE_CLOSE, 1);
   double atr     = iATR(Symbol(), Period(), FIX_ATR_PERIOD, 1);

   if(atr <= 0.0)
      return;

   // regime filter: stand aside until the trend is established
   if(MathAbs(emaFast - emaSlow) < FIX_MIN_EMA_SEP * atr)
      return;

   // channel of the FIX_DONCHIAN bars BEFORE the last closed bar
   int hiIdx = iHighest(Symbol(), Period(), MODE_HIGH, FIX_DONCHIAN, 2);
   int loIdx = iLowest(Symbol(), Period(), MODE_LOW, FIX_DONCHIAN, 2);
   if(hiIdx < 0 || loIdx < 0)
      return;

   double donHigh = iHigh(Symbol(), Period(), hiIdx);
   double donLow  = iLow(Symbol(), Period(), loIdx);
   double close1  = iClose(Symbol(), Period(), 1);

   if(emaFast > emaSlow && close1 > donHigh)
     {
      OpenPosition(OP_BUY, atr);
      return;
     }
   if(emaFast < emaSlow && close1 < donLow)
      OpenPosition(OP_SELL, atr);
  }

//+------------------------------------------------------------------+
void OpenPosition(const int type, const double atr)
  {
   RefreshRates();

   double price  = (type == OP_BUY) ? Ask : Bid;
   double slDist = atr * FIX_SL_ATR;
   double tpDist = atr * FIX_TP_ATR;

   double sl = (type == OP_BUY) ? price - slDist : price + slDist;
   double tp = (type == OP_BUY) ? price + tpDist : price - tpDist;

   sl = NormalizeDouble(sl, Digits);
   tp = NormalizeDouble(tp, Digits);

   double lots = CalcLots(slDist);
   if(lots <= 0.0)
     {
      Print("Lot calculation returned 0 - trade skipped");
      return;
     }

   int ticket;
   if(InpEcnMode)
     {
      ticket = OrderSend(Symbol(), type, lots, price, InpSlippagePoints,
                         0, 0, InpTradeComment, InpMagicNumber, 0, clrNONE);
      if(ticket < 0)
        {
         Print("OrderSend failed: error ", GetLastError());
         return;
        }
      if(OrderSelect(ticket, SELECT_BY_TICKET))
        {
         if(!OrderModify(ticket, OrderOpenPrice(), sl, tp, 0, clrNONE))
            Print("OrderModify (ECN SL/TP) failed: error ", GetLastError());
        }
     }
   else
     {
      ticket = OrderSend(Symbol(), type, lots, price, InpSlippagePoints,
                         sl, tp, InpTradeComment, InpMagicNumber, 0, clrNONE);
      if(ticket < 0)
         Print("OrderSend failed: error ", GetLastError());
     }
  }

//+------------------------------------------------------------------+
//| Lot size from the fixed risk percentage                          |
//+------------------------------------------------------------------+
double CalcLots(const double slDistance)
  {
   double tickValue = MarketInfo(Symbol(), MODE_TICKVALUE);
   double tickSize  = MarketInfo(Symbol(), MODE_TICKSIZE);
   if(tickValue <= 0.0 || tickSize <= 0.0 || slDistance <= 0.0)
      return(0.0);

   double lossPerLot = slDistance / tickSize * tickValue;
   if(lossPerLot <= 0.0)
      return(0.0);

   double riskAmount = AccountBalance() * FIX_RISK_PERCENT / 100.0;
   double lots       = riskAmount / lossPerLot;

   double minLot  = MarketInfo(Symbol(), MODE_MINLOT);
   double maxLot  = MathMin(MarketInfo(Symbol(), MODE_MAXLOT), FIX_MAX_LOT);
   double lotStep = MarketInfo(Symbol(), MODE_LOTSTEP);

   if(lotStep > 0.0)
      lots = MathFloor(lots / lotStep) * lotStep;
   lots = MathMax(minLot, MathMin(maxLot, lots));

   if(lots < minLot)
      return(0.0);
   return(NormalizeDouble(lots, 2));
  }

//+------------------------------------------------------------------+
bool HasOpenPosition()
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
         continue;
      if(OrderSymbol() == Symbol() && OrderMagicNumber() == InpMagicNumber &&
         (OrderType() == OP_BUY || OrderType() == OP_SELL))
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

   double atr = iATR(Symbol(), Period(), FIX_ATR_PERIOD, 1);
   if(atr <= 0.0)
      return;

   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
         continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != InpMagicNumber)
         continue;

      RefreshRates();

      double openPrice = OrderOpenPrice();
      double curSl     = OrderStopLoss();
      double curTp     = OrderTakeProfit();

      if(OrderType() == OP_BUY)
        {
         double trailSl = Bid - atr * FIX_TRAIL_ATR;
         if(trailSl > openPrice && trailSl > curSl + Point * 0.5 && trailSl < Bid)
           {
            trailSl = NormalizeDouble(trailSl, Digits);
            if(!OrderModify(OrderTicket(), openPrice, trailSl, curTp, 0, clrNONE))
               Print("OrderModify failed: error ", GetLastError());
           }
        }
      else if(OrderType() == OP_SELL)
        {
         double trailSl = Ask + atr * FIX_TRAIL_ATR;
         if(trailSl < openPrice && trailSl < curSl - Point * 0.5 && trailSl > Ask)
           {
            trailSl = NormalizeDouble(trailSl, Digits);
            if(!OrderModify(OrderTicket(), openPrice, trailSl, curTp, 0, clrNONE))
               Print("OrderModify failed: error ", GetLastError());
           }
        }
     }
  }

//+------------------------------------------------------------------+
bool IsWeekday()
  {
   int dow = TimeDayOfWeek(TimeCurrent());
   return(dow >= 1 && dow <= 5);
  }

//+------------------------------------------------------------------+
bool SpreadOk()
  {
   if(InpMaxSpreadPoints <= 0)
      return(true);
   return(MarketInfo(Symbol(), MODE_SPREAD) <= InpMaxSpreadPoints);
  }
//+------------------------------------------------------------------+
