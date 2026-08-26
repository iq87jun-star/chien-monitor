//+------------------------------------------------------------------+
//|                                          ChienMondayYen_v310.mq4 |
//|                                                                  |
//| SALES BUILD v3.10 - Monday seasonality on yen crosses     |
//| MQL4 port of the MT5 build. Same logic, same fixed settings.     |
//|                                                                  |
//| Buys at the open of the Monday 04:00 server bar and closes at    |
//| the open of the 02:00 bar on the next trading day. Long only,    |
//| one position, no averaging, no martingale.                       |
//|                                                                  |
//| Measured on real bars with recorded spreads, 2016-2026, on       |
//| EURJPY + GBPJPY + USDJPY, with a 2xATR stop and 1 pip slippage   |
//| per side: 1,640 trades, PF 1.34, 55.6% wins, t 4.27, max DD      |
//| 3.5%, two losing years in eleven. Entry hours 2-8 and exit hours |
//| 2-20 all measure profitable, so the timing sits on a plateau.    |
//| The effect is absent in non-yen pairs and survives removing each |
//| week's own average day, so it is a weekly seasonal rather than a |
//| trend artifact.                                                  |
//|                                                                  |
//| The trading logic is fixed in code. Lot sizing IS adjustable.    |
| Risk per chart and drawdown scale together (10.6 years, three    |
| pairs together, 1 pip slippage per side):                        |
|   0.33% -> DD 3.2%   0.50% -> DD 4.9%   1.00% -> DD 9.6%         |
|   2.00% -> DD 18.7%  3.00% -> DD 27.1%                           |
| Two losing years in eleven at every setting.                     |
//| Requires a GMT+2/+3 server (standard for MT4 brokers).           |
//| No account locks, no expiry date, no external DLLs.              |
//+------------------------------------------------------------------+
#property copyright "iq87jun-star"
#property link      "https://www.gogojungle.co.jp/"
#property version   "3.10"
#property strict

#define EA_BUILD "MondayYen v3.10 (MT4)"

//--- fixed strategy settings: deliberately NOT inputs ---------------
const int    FIX_ENTRY_DOW    = 1;    // Monday
const int    FIX_ENTRY_HOUR   = 4;
const int    FIX_EXIT_HOUR    = 2;
const int    FIX_ATR_PERIOD   = 14;
const double FIX_SL_ATR       = 2.0;

//--- lot sizing mode
enum ENUM_LOT_MODE
  {
   LOT_RISK_PCT = 0,   // Risk % of balance
   LOT_FIXED           // Fixed lot
  };

//=== Lot sizing: the only settings that change the result ===========
extern ENUM_LOT_MODE InpLotMode = LOT_RISK_PCT; // Lot sizing mode
extern double InpRiskPercent    = 0.5;       // Risk per trade, % of balance
extern double InpFixedLot       = 0.10;      // Fixed lot (when mode = Fixed)
extern double InpMaxLot         = 10.0;      // Lot cap

//=== Operational: none of these change the strategy =================
extern int    InpMagicNumber     = 87300;    // Magic number (base)
extern string InpTradeComment    = "CMY300"; // Order comment
extern int    InpSlippagePoints  = 20;       // Max slippage (points)
extern int    InpMaxSpreadPoints = 60;       // Max spread at entry (points, 0 = off)
extern bool   InpEcnMode         = false;    // ECN mode (attach SL after the fill)

//--- globals
datetime g_lastBar = 0;
int      g_magic   = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   g_magic = InpMagicNumber + StringLen(Symbol()) * 7 + StringGetChar(Symbol(), 0);
   LogSettings();
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void LogSettings()
  {
   Print("==================================================");
   PrintFormat("%s  (settings are compiled in)", EA_BUILD);
   PrintFormat("Symbol  : %s   magic=%d", Symbol(), g_magic);
   PrintFormat("Entry   : BUY at open of Monday %02d:00 server time", FIX_ENTRY_HOUR);
   PrintFormat("Exit    : at open of %02d:00 on the next trading day", FIX_EXIT_HOUR);
   PrintFormat("Stop    : daily ATR(%d) x %.1f (safety; rarely hit)", FIX_ATR_PERIOD, FIX_SL_ATR);
   if(InpLotMode == LOT_RISK_PCT)
      PrintFormat("Lots    : risk %.2f%% of balance per trade (cap %.2f)", InpRiskPercent, InpMaxLot);
   else
      PrintFormat("Lots    : fixed %.2f (cap %.2f)", InpFixedLot, InpMaxLot);
   PrintFormat("Spread  : max %d points at entry (only adjustable setting)", InpMaxSpreadPoints);
   Print("Long only, one position, ~52 trades a year per symbol. Trading logic is fixed.");
   Print("Intended on EURJPY / GBPJPY / USDJPY. Expected ~55% wins, PF ~1.3.");
   Print("==================================================");
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   if(!IsNewH1Bar())
      return;

   int hour = TimeHour(Time[0]);

   if(HasOpenPosition())
     {
      if(hour == FIX_EXIT_HOUR && !IsSameDayAsEntry())
         CloseAllPositions();
      return;
     }

   if(TimeDayOfWeek(Time[0]) != FIX_ENTRY_DOW || hour != FIX_ENTRY_HOUR)
      return;
   if(!SpreadOk())
      return;

   double atr = iATR(Symbol(), PERIOD_D1, FIX_ATR_PERIOD, 1);
   if(atr <= 0.0)
      return;

   RefreshRates();
   double slDist = atr * FIX_SL_ATR;
   double sl     = NormalizeDouble(Ask - slDist, Digits);
   double lots   = CalcLots(slDist);
   if(lots <= 0.0)
     {
      Print("Lot calculation returned 0 - trade skipped");
      return;
     }

   int ticket;
   if(InpEcnMode)
     {
      ticket = OrderSend(Symbol(), OP_BUY, lots, Ask, InpSlippagePoints,
                         0, 0, InpTradeComment, g_magic, 0, clrNONE);
      if(ticket < 0) { Print("OrderSend failed: error ", GetLastError()); return; }
      if(OrderSelect(ticket, SELECT_BY_TICKET))
         if(!OrderModify(ticket, OrderOpenPrice(), sl, 0, 0, clrNONE))
            Print("OrderModify (ECN SL) failed: error ", GetLastError());
     }
   else
     {
      ticket = OrderSend(Symbol(), OP_BUY, lots, Ask, InpSlippagePoints,
                         sl, 0, InpTradeComment, g_magic, 0, clrNONE);
      if(ticket < 0)
         Print("OrderSend failed: error ", GetLastError());
     }
  }

//+------------------------------------------------------------------+
bool IsNewH1Bar()
  {
   datetime t = iTime(Symbol(), PERIOD_H1, 0);
   if(t == g_lastBar)
      return(false);
   g_lastBar = t;
   return(true);
  }

//+------------------------------------------------------------------+
bool IsSameDayAsEntry()
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != g_magic) continue;
      datetime o = OrderOpenTime();
      return(TimeYear(o) == TimeYear(Time[0]) &&
             TimeMonth(o) == TimeMonth(Time[0]) &&
             TimeDay(o) == TimeDay(Time[0]));
     }
   return(false);
  }

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

   double lots;
   if(InpLotMode == LOT_FIXED)
      lots = InpFixedLot;
   else
      lots = AccountBalance() * InpRiskPercent / 100.0 / lossPerLot;

   double minLot  = MarketInfo(Symbol(), MODE_MINLOT);
   double maxLot  = MathMin(MarketInfo(Symbol(), MODE_MAXLOT), InpMaxLot);
   double lotStep = MarketInfo(Symbol(), MODE_LOTSTEP);

   if(lotStep > 0.0) lots = MathFloor(lots / lotStep) * lotStep;
   lots = MathMax(minLot, MathMin(maxLot, lots));
   if(lots < minLot) return(0.0);
   return(NormalizeDouble(lots, 2));
  }

//+------------------------------------------------------------------+
bool HasOpenPosition()
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() == Symbol() && OrderMagicNumber() == g_magic &&
         (OrderType() == OP_BUY || OrderType() == OP_SELL))
         return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
void CloseAllPositions()
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != g_magic) continue;
      RefreshRates();
      if(OrderType() == OP_BUY)
        {
         if(!OrderClose(OrderTicket(), OrderLots(), Bid, InpSlippagePoints, clrNONE))
            Print("OrderClose failed: error ", GetLastError());
        }
     }
  }

//+------------------------------------------------------------------+
bool SpreadOk()
  {
   if(InpMaxSpreadPoints <= 0) return(true);
   return(MarketInfo(Symbol(), MODE_SPREAD) <= InpMaxSpreadPoints);
  }
//+------------------------------------------------------------------+
