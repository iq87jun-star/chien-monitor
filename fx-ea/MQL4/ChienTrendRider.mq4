//+------------------------------------------------------------------+
//|                                              ChienTrendRider.mq4 |
//|                     Trend-following pullback EA for MetaTrader 4 |
//|                                                                  |
//| Strategy summary                                                 |
//|   - Trend filter : Fast EMA vs Slow EMA (closed bars only)       |
//|   - Entry        : Donchian channel breakout in trend direction  |
//|                    (default) or RSI pullback recovery            |
//|   - Stop loss    : ATR-based                                     |
//|   - Take profit  : ATR-based (risk/reward configurable)          |
//|   - Exits        : Optional break-even and ATR trailing stop     |
//|   - Lot sizing   : Fixed lot or risk % of balance                |
//|   - Filters      : Max spread, trading hours, weekday, Friday    |
//|                    flat-close                                    |
//|                                                                  |
//| No account locks, no expiry date, no external DLLs.              |
//| ECN mode opens orders without SL/TP and attaches them by         |
//| OrderModify right after the fill.                                |
//+------------------------------------------------------------------+
#property copyright "iq87jun-star"
#property link      "https://www.gogojungle.co.jp/"
#property version   "1.20"
#property strict

//--- lot sizing mode
enum ENUM_LOT_MODE
  {
   LOT_FIXED = 0,   // Fixed lot
   LOT_RISK_PCT     // Risk % of balance
  };

//--- entry mode
enum ENUM_ENTRY_MODE
  {
   ENTRY_DONCHIAN = 0,  // Donchian breakout (recommended)
   ENTRY_RSI            // RSI pullback recovery
  };

//=== Trade settings ===
extern string  __trade__           = "=== Trade settings ===";
extern int     InpMagicNumber      = 87001;        // Magic number
extern string  InpTradeComment     = "ChienTrendRider";
extern int     InpSlippagePoints   = 10;           // Max slippage (points)
extern bool    InpEcnMode          = false;        // ECN mode (SL/TP via modify)

//=== Strategy ===
extern string  __strategy__        = "=== Strategy ===";
extern ENUM_ENTRY_MODE InpEntryMode = ENTRY_DONCHIAN; // Entry mode
extern int     InpFastEmaPeriod    = 50;           // Fast EMA period
extern int     InpSlowEmaPeriod    = 200;          // Slow EMA period
extern int     InpDonchianPeriod   = 20;           // Donchian channel period
extern int     InpRsiPeriod        = 14;           // RSI period
extern double  InpRsiBuyLevel      = 40.0;         // RSI buy recovery level
extern double  InpRsiSellLevel     = 60.0;         // RSI sell recovery level
extern int     InpAtrPeriod        = 14;           // ATR period
extern double  InpAtrSlMult        = 2.0;          // Stop loss = ATR x this
extern double  InpAtrTpMult        = 4.0;          // Take profit = ATR x this (0 = no TP)
extern bool    InpAllowBuy         = true;         // Allow long trades
extern bool    InpAllowSell        = true;         // Allow short trades

//=== Money management ===
extern string  __money__           = "=== Money management ===";
extern ENUM_LOT_MODE InpLotMode    = LOT_RISK_PCT; // Lot sizing mode
extern double  InpFixedLot         = 0.10;         // Fixed lot size
extern double  InpRiskPercent      = 0.5;          // Risk % per trade
extern double  InpMaxLot           = 10.0;         // Max lot cap

//=== Exit management ===
extern string  __exit__            = "=== Exit management ===";
extern bool    InpUseBreakEven     = false;        // Use break-even (off: it cuts winners short)
extern double  InpBreakEvenAtr     = 1.0;          // Break-even trigger (ATR x)
extern double  InpBreakEvenLockAtr = 0.1;          // Locked profit at BE (ATR x)
extern bool    InpUseTrailing      = true;         // Use ATR trailing stop
extern double  InpTrailAtrMult     = 4.0;          // Trailing distance (ATR x)

//=== Filters ===
extern string  __filters__         = "=== Filters ===";
extern int     InpMaxSpreadPoints  = 30;           // Max spread (points, 0 = off)
extern bool    InpUseTimeFilter    = false;        // Use trading-hours filter
extern int     InpStartHour        = 8;            // Trading start hour (server)
extern int     InpEndHour          = 22;           // Trading end hour (server)
extern bool    InpTradeMonday      = true;
extern bool    InpTradeTuesday     = true;
extern bool    InpTradeWednesday   = true;
extern bool    InpTradeThursday    = true;
extern bool    InpTradeFriday      = true;
extern bool    InpCloseOnFriday    = false;        // Flat-close on Friday
extern int     InpFridayCloseHour  = 21;           // Friday close hour (server)

//--- globals
datetime g_lastBarTime = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpFastEmaPeriod >= InpSlowEmaPeriod)
     {
      Print("Init error: fast EMA period must be smaller than slow EMA period");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpDonchianPeriod < 2)
     {
      Print("Init error: Donchian period must be >= 2");
      return(INIT_PARAMETERS_INCORRECT);
     }

   LogSettings();

   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Log the settings actually in use                                 |
//|                                                                  |
//| The tester keeps the parameter set from the previous run and does |
//| not pick up new defaults after a recompile, so print what is      |
//| really active instead of assuming the defaults apply.             |
//+------------------------------------------------------------------+
void LogSettings()
  {
   PrintFormat("=== ChienTrendRider v1.20 settings in use ===");
   PrintFormat("Entry     : %s (Donchian %d, EMA %d/%d)",
               (InpEntryMode == ENTRY_DONCHIAN) ? "DONCHIAN" : "RSI",
               InpDonchianPeriod, InpFastEmaPeriod, InpSlowEmaPeriod);
   PrintFormat("Exits     : SL=ATR x %.2f  TP=ATR x %.2f  BreakEven=%s  Trailing=%s (ATR x %.2f)",
               InpAtrSlMult, InpAtrTpMult,
               InpUseBreakEven ? "ON" : "off",
               InpUseTrailing  ? "ON" : "off", InpTrailAtrMult);
   PrintFormat("Lots      : %s  risk=%.2f%%  fixed=%.2f",
               (InpLotMode == LOT_RISK_PCT) ? "RISK_PCT" : "FIXED",
               InpRiskPercent, InpFixedLot);
   PrintFormat("Filters   : maxSpread=%d  timeFilter=%s  closeOnFriday=%s",
               InpMaxSpreadPoints,
               InpUseTimeFilter ? "ON" : "off",
               InpCloseOnFriday ? "ON" : "off");

   if(InpUseBreakEven)
      Print("WARNING: break-even is ON. Backtests show it closes winners early "
            "and lowers the profit factor. The tested default is OFF.");
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   // Friday flat-close runs every tick so it is not missed
   if(InpCloseOnFriday && IsFridayCloseTime())
     {
      CloseAllPositions();
      return;
     }

   // exit management runs every tick
   ManageOpenPosition();

   // entries are evaluated once per closed bar
   if(!IsNewBar())
      return;

   if(HasOpenPosition())
      return;

   if(!IsTradingAllowedNow())
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
void CheckEntry()
  {
   double emaFast = iMA(Symbol(), Period(), InpFastEmaPeriod, 0, MODE_EMA, PRICE_CLOSE, 1);
   double emaSlow = iMA(Symbol(), Period(), InpSlowEmaPeriod, 0, MODE_EMA, PRICE_CLOSE, 1);
   double atr     = iATR(Symbol(), Period(), InpAtrPeriod, 1);

   if(atr <= 0.0)
      return;

   bool trendUp   = emaFast > emaSlow;
   bool trendDown = emaFast < emaSlow;

   bool buySignal = false, sellSignal = false;

   if(InpEntryMode == ENTRY_DONCHIAN)
     {
      // channel of the InpDonchianPeriod bars BEFORE the last closed bar;
      // signal = last closed bar breaks out of it in trend direction
      int hiIdx = iHighest(Symbol(), Period(), MODE_HIGH, InpDonchianPeriod, 2);
      int loIdx = iLowest(Symbol(), Period(), MODE_LOW, InpDonchianPeriod, 2);
      if(hiIdx < 0 || loIdx < 0)
         return;
      double donHigh = iHigh(Symbol(), Period(), hiIdx);
      double donLow  = iLow(Symbol(), Period(), loIdx);
      double close1  = iClose(Symbol(), Period(), 1);

      buySignal  = trendUp   && close1 > donHigh;
      sellSignal = trendDown && close1 < donLow;
     }
   else // ENTRY_RSI
     {
      double rsi1 = iRSI(Symbol(), Period(), InpRsiPeriod, PRICE_CLOSE, 1);
      double rsi2 = iRSI(Symbol(), Period(), InpRsiPeriod, PRICE_CLOSE, 2);

      // buy: RSI dipped below the buy level and recovered above it
      buySignal  = trendUp   && rsi2 < InpRsiBuyLevel  && rsi1 >= InpRsiBuyLevel;
      // sell: RSI rose above the sell level and dropped back below it
      sellSignal = trendDown && rsi2 > InpRsiSellLevel && rsi1 <= InpRsiSellLevel;
     }

   if(InpAllowBuy && buySignal)
     {
      OpenPosition(OP_BUY, atr);
      return;
     }
   if(InpAllowSell && sellSignal)
      OpenPosition(OP_SELL, atr);
  }

//+------------------------------------------------------------------+
void OpenPosition(const int type, const double atr)
  {
   RefreshRates();

   double price  = (type == OP_BUY) ? Ask : Bid;
   double slDist = atr * InpAtrSlMult;
   double tpDist = atr * InpAtrTpMult;

   double sl = (type == OP_BUY) ? price - slDist : price + slDist;
   double tp = 0.0;
   if(InpAtrTpMult > 0.0)
      tp = (type == OP_BUY) ? price + tpDist : price - tpDist;

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
double CalcLots(const double slDistance)
  {
   double lots = InpFixedLot;

   if(InpLotMode == LOT_RISK_PCT)
     {
      double tickValue = MarketInfo(Symbol(), MODE_TICKVALUE);
      double tickSize  = MarketInfo(Symbol(), MODE_TICKSIZE);
      if(tickValue <= 0.0 || tickSize <= 0.0 || slDistance <= 0.0)
         return(0.0);

      double lossPerLot = slDistance / tickSize * tickValue;
      if(lossPerLot <= 0.0)
         return(0.0);

      double riskAmount = AccountBalance() * InpRiskPercent / 100.0;
      lots = riskAmount / lossPerLot;
     }

   double minLot  = MarketInfo(Symbol(), MODE_MINLOT);
   double maxLot  = MathMin(MarketInfo(Symbol(), MODE_MAXLOT), InpMaxLot);
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
void ManageOpenPosition()
  {
   if(!InpUseBreakEven && !InpUseTrailing)
      return;

   double atr = iATR(Symbol(), Period(), InpAtrPeriod, 1);
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
      double newSl     = curSl;

      if(OrderType() == OP_BUY)
        {
         double profitDist = Bid - openPrice;

         if(InpUseBreakEven && profitDist >= atr * InpBreakEvenAtr)
           {
            double bePrice = openPrice + atr * InpBreakEvenLockAtr;
            if(newSl < bePrice)
               newSl = bePrice;
           }
         if(InpUseTrailing)
           {
            double trailSl = Bid - atr * InpTrailAtrMult;
            if(trailSl > newSl && trailSl > openPrice)
               newSl = trailSl;
           }

         if(newSl > curSl + Point * 0.5 && newSl < Bid)
           {
            newSl = NormalizeDouble(newSl, Digits);
            if(!OrderModify(OrderTicket(), openPrice, newSl, curTp, 0, clrNONE))
               Print("OrderModify failed: error ", GetLastError());
           }
        }
      else if(OrderType() == OP_SELL)
        {
         double profitDist = openPrice - Ask;

         if(InpUseBreakEven && profitDist >= atr * InpBreakEvenAtr)
           {
            double bePrice = openPrice - atr * InpBreakEvenLockAtr;
            if(curSl == 0.0 || newSl > bePrice)
               newSl = bePrice;
           }
         if(InpUseTrailing)
           {
            double trailSl = Ask + atr * InpTrailAtrMult;
            if((curSl == 0.0 || trailSl < newSl) && trailSl < openPrice)
               newSl = trailSl;
           }

         if((curSl == 0.0 || newSl < curSl - Point * 0.5) && newSl > Ask && newSl != curSl)
           {
            newSl = NormalizeDouble(newSl, Digits);
            if(!OrderModify(OrderTicket(), openPrice, newSl, curTp, 0, clrNONE))
               Print("OrderModify failed: error ", GetLastError());
           }
        }
     }
  }

//+------------------------------------------------------------------+
void CloseAllPositions()
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
         continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != InpMagicNumber)
         continue;

      RefreshRates();

      bool closed = false;
      if(OrderType() == OP_BUY)
         closed = OrderClose(OrderTicket(), OrderLots(), Bid, InpSlippagePoints, clrNONE);
      else if(OrderType() == OP_SELL)
         closed = OrderClose(OrderTicket(), OrderLots(), Ask, InpSlippagePoints, clrNONE);

      if(!closed && (OrderType() == OP_BUY || OrderType() == OP_SELL))
         Print("OrderClose failed: error ", GetLastError());
     }
  }

//+------------------------------------------------------------------+
bool IsTradingAllowedNow()
  {
   int dow  = TimeDayOfWeek(TimeCurrent());
   int hour = TimeHour(TimeCurrent());

   switch(dow)
     {
      case 1: if(!InpTradeMonday)    return(false); break;
      case 2: if(!InpTradeTuesday)   return(false); break;
      case 3: if(!InpTradeWednesday) return(false); break;
      case 4: if(!InpTradeThursday)  return(false); break;
      case 5: if(!InpTradeFriday)    return(false); break;
      default: return(false); // Saturday / Sunday
     }

   if(InpCloseOnFriday && dow == 5 && hour >= InpFridayCloseHour)
      return(false);

   if(InpUseTimeFilter)
     {
      if(InpStartHour <= InpEndHour)
        {
         if(hour < InpStartHour || hour >= InpEndHour)
            return(false);
        }
      else // overnight window (e.g. 22 -> 6)
        {
         if(hour < InpStartHour && hour >= InpEndHour)
            return(false);
        }
     }
   return(true);
  }

//+------------------------------------------------------------------+
bool IsFridayCloseTime()
  {
   return(TimeDayOfWeek(TimeCurrent()) == 5 && TimeHour(TimeCurrent()) >= InpFridayCloseHour);
  }

//+------------------------------------------------------------------+
bool SpreadOk()
  {
   if(InpMaxSpreadPoints <= 0)
      return(true);
   double spread = MarketInfo(Symbol(), MODE_SPREAD);
   return(spread <= InpMaxSpreadPoints);
  }
//+------------------------------------------------------------------+
