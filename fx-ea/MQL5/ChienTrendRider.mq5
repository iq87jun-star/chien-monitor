//+------------------------------------------------------------------+
//|                                              ChienTrendRider.mq5 |
//|                     Trend-following pullback EA for MetaTrader 5 |
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
//+------------------------------------------------------------------+
#property copyright "iq87jun-star"
#property link      "https://www.gogojungle.co.jp/"
#property version   "1.10"

#include <Trade\Trade.mqh>

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
input group    "=== Trade settings ==="
input long     InpMagicNumber      = 87001;        // Magic number
input string   InpTradeComment     = "ChienTrendRider"; // Order comment
input int      InpSlippagePoints   = 10;           // Max slippage (points)

//=== Strategy ===
input group    "=== Strategy ==="
input ENUM_ENTRY_MODE InpEntryMode = ENTRY_DONCHIAN; // Entry mode
input int      InpFastEmaPeriod    = 50;           // Fast EMA period
input int      InpSlowEmaPeriod    = 200;          // Slow EMA period
input int      InpDonchianPeriod   = 20;           // Donchian channel period
input int      InpRsiPeriod        = 14;           // RSI period
input double   InpRsiBuyLevel      = 40.0;         // RSI buy recovery level
input double   InpRsiSellLevel     = 60.0;         // RSI sell recovery level
input int      InpAtrPeriod        = 14;           // ATR period
input double   InpAtrSlMult        = 2.0;          // Stop loss = ATR x this
input double   InpAtrTpMult        = 3.0;          // Take profit = ATR x this (0 = no TP)
input bool     InpAllowBuy         = true;         // Allow long trades
input bool     InpAllowSell        = true;         // Allow short trades

//=== Money management ===
input group    "=== Money management ==="
input ENUM_LOT_MODE InpLotMode     = LOT_RISK_PCT; // Lot sizing mode
input double   InpFixedLot         = 0.10;         // Fixed lot size
input double   InpRiskPercent      = 1.0;          // Risk % per trade
input double   InpMaxLot           = 10.0;         // Max lot cap

//=== Exit management ===
input group    "=== Exit management ==="
input bool     InpUseBreakEven     = true;         // Use break-even
input double   InpBreakEvenAtr     = 1.0;          // Break-even trigger (ATR x)
input double   InpBreakEvenLockAtr = 0.1;          // Locked profit at BE (ATR x)
input bool     InpUseTrailing      = true;         // Use ATR trailing stop
input double   InpTrailAtrMult     = 2.0;          // Trailing distance (ATR x)

//=== Filters ===
input group    "=== Filters ==="
input int      InpMaxSpreadPoints  = 30;           // Max spread (points, 0 = off)
input bool     InpUseTimeFilter    = false;        // Use trading-hours filter
input int      InpStartHour        = 8;            // Trading start hour (server)
input int      InpEndHour          = 22;           // Trading end hour (server)
input bool     InpTradeMonday      = true;         // Trade on Monday
input bool     InpTradeTuesday     = true;         // Trade on Tuesday
input bool     InpTradeWednesday   = true;         // Trade on Wednesday
input bool     InpTradeThursday    = true;         // Trade on Thursday
input bool     InpTradeFriday      = true;         // Trade on Friday
input bool     InpCloseOnFriday    = false;        // Flat-close on Friday
input int      InpFridayCloseHour  = 21;           // Friday close hour (server)

//--- globals
CTrade   g_trade;
int      g_hEmaFast = INVALID_HANDLE;
int      g_hEmaSlow = INVALID_HANDLE;
int      g_hRsi     = INVALID_HANDLE;
int      g_hAtr     = INVALID_HANDLE;
datetime g_lastBarTime = 0;

//+------------------------------------------------------------------+
//| Expert initialization                                            |
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

   g_hEmaFast = iMA(_Symbol, _Period, InpFastEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   g_hEmaSlow = iMA(_Symbol, _Period, InpSlowEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   g_hRsi     = iRSI(_Symbol, _Period, InpRsiPeriod, PRICE_CLOSE);
   g_hAtr     = iATR(_Symbol, _Period, InpAtrPeriod);

   if(g_hEmaFast == INVALID_HANDLE || g_hEmaSlow == INVALID_HANDLE ||
      g_hRsi == INVALID_HANDLE || g_hAtr == INVALID_HANDLE)
     {
      Print("Init error: failed to create indicator handles");
      return(INIT_FAILED);
     }

   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetDeviationInPoints(InpSlippagePoints);
   g_trade.SetTypeFillingBySymbol(_Symbol);

   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Expert deinitialization                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(g_hEmaFast != INVALID_HANDLE) IndicatorRelease(g_hEmaFast);
   if(g_hEmaSlow != INVALID_HANDLE) IndicatorRelease(g_hEmaSlow);
   if(g_hRsi     != INVALID_HANDLE) IndicatorRelease(g_hRsi);
   if(g_hAtr     != INVALID_HANDLE) IndicatorRelease(g_hAtr);
  }

//+------------------------------------------------------------------+
//| Expert tick                                                      |
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
//| Entry logic                                                      |
//+------------------------------------------------------------------+
void CheckEntry()
  {
   double emaFast, emaSlow, atr;
   if(!GetBufferValue(g_hEmaFast, 1, emaFast)) return;
   if(!GetBufferValue(g_hEmaSlow, 1, emaSlow)) return;
   if(!GetBufferValue(g_hAtr, 1, atr))         return;
   if(atr <= 0.0)                              return;

   bool trendUp   = emaFast > emaSlow;
   bool trendDown = emaFast < emaSlow;

   bool buySignal = false, sellSignal = false;

   if(InpEntryMode == ENTRY_DONCHIAN)
     {
      // channel of the InpDonchianPeriod bars BEFORE the last closed bar;
      // signal = last closed bar breaks out of it in trend direction
      int hiIdx = iHighest(_Symbol, _Period, MODE_HIGH, InpDonchianPeriod, 2);
      int loIdx = iLowest(_Symbol, _Period, MODE_LOW, InpDonchianPeriod, 2);
      if(hiIdx < 0 || loIdx < 0)
         return;
      double donHigh = iHigh(_Symbol, _Period, hiIdx);
      double donLow  = iLow(_Symbol, _Period, loIdx);
      double close1  = iClose(_Symbol, _Period, 1);

      buySignal  = trendUp   && close1 > donHigh;
      sellSignal = trendDown && close1 < donLow;
     }
   else // ENTRY_RSI
     {
      double rsi1, rsi2;
      if(!GetBufferValue(g_hRsi, 1, rsi1)) return;
      if(!GetBufferValue(g_hRsi, 2, rsi2)) return;

      // buy: RSI dipped below the buy level and recovered above it
      buySignal  = trendUp   && rsi2 < InpRsiBuyLevel  && rsi1 >= InpRsiBuyLevel;
      // sell: RSI rose above the sell level and dropped back below it
      sellSignal = trendDown && rsi2 > InpRsiSellLevel && rsi1 <= InpRsiSellLevel;
     }

   if(InpAllowBuy && buySignal)
     {
      OpenPosition(ORDER_TYPE_BUY, atr);
      return;
     }
   if(InpAllowSell && sellSignal)
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

   double slDist = atr * InpAtrSlMult;
   double tpDist = atr * InpAtrTpMult;

   double sl = (type == ORDER_TYPE_BUY) ? price - slDist : price + slDist;
   double tp = 0.0;
   if(InpAtrTpMult > 0.0)
      tp = (type == ORDER_TYPE_BUY) ? price + tpDist : price - tpDist;

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
//| Lot size from risk settings                                      |
//+------------------------------------------------------------------+
double CalcLots(const double slDistance)
  {
   double lots = InpFixedLot;

   if(InpLotMode == LOT_RISK_PCT)
     {
      double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
      double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
      if(tickValue <= 0.0 || tickSize <= 0.0 || slDistance <= 0.0)
         return(0.0);

      double lossPerLot = slDistance / tickSize * tickValue;
      if(lossPerLot <= 0.0)
         return(0.0);

      double riskAmount = AccountInfoDouble(ACCOUNT_BALANCE) * InpRiskPercent / 100.0;
      lots = riskAmount / lossPerLot;
     }

   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = MathMin(SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX), InpMaxLot);
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
//| Break-even and trailing management                               |
//+------------------------------------------------------------------+
void ManageOpenPosition()
  {
   if(!InpUseBreakEven && !InpUseTrailing)
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

      double newSl = curSl;

      if(type == POSITION_TYPE_BUY)
        {
         double profitDist = bid - openPrice;

         if(InpUseBreakEven && profitDist >= atr * InpBreakEvenAtr)
           {
            double bePrice = openPrice + atr * InpBreakEvenLockAtr;
            if(newSl < bePrice)
               newSl = bePrice;
           }
         if(InpUseTrailing)
           {
            double trailSl = bid - atr * InpTrailAtrMult;
            if(trailSl > newSl && trailSl > openPrice)
               newSl = trailSl;
           }

         if(newSl > curSl + _Point * 0.5 && newSl < bid)
           {
            newSl = NormalizeDouble(newSl, _Digits);
            if(!g_trade.PositionModify(ticket, newSl, curTp))
               PrintFormat("PositionModify failed: retcode=%d", g_trade.ResultRetcode());
           }
        }
      else if(type == POSITION_TYPE_SELL)
        {
         double profitDist = openPrice - ask;

         if(InpUseBreakEven && profitDist >= atr * InpBreakEvenAtr)
           {
            double bePrice = openPrice - atr * InpBreakEvenLockAtr;
            if(curSl == 0.0 || newSl > bePrice)
               newSl = bePrice;
           }
         if(InpUseTrailing)
           {
            double trailSl = ask + atr * InpTrailAtrMult;
            if((curSl == 0.0 || trailSl < newSl) && trailSl < openPrice)
               newSl = trailSl;
           }

         if((curSl == 0.0 || newSl < curSl - _Point * 0.5) && newSl > ask && newSl != curSl)
           {
            newSl = NormalizeDouble(newSl, _Digits);
            if(!g_trade.PositionModify(ticket, newSl, curTp))
               PrintFormat("PositionModify failed: retcode=%d", g_trade.ResultRetcode());
           }
        }
     }
  }

//+------------------------------------------------------------------+
//| Close all positions of this EA                                   |
//+------------------------------------------------------------------+
void CloseAllPositions()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         g_trade.PositionClose(ticket, InpSlippagePoints);
     }
  }

//+------------------------------------------------------------------+
//| Trading-hours / weekday filter                                   |
//+------------------------------------------------------------------+
bool IsTradingAllowedNow()
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);

   switch(dt.day_of_week)
     {
      case 1: if(!InpTradeMonday)    return(false); break;
      case 2: if(!InpTradeTuesday)   return(false); break;
      case 3: if(!InpTradeWednesday) return(false); break;
      case 4: if(!InpTradeThursday)  return(false); break;
      case 5: if(!InpTradeFriday)    return(false); break;
      default: return(false); // Saturday / Sunday
     }

   if(InpCloseOnFriday && dt.day_of_week == 5 && dt.hour >= InpFridayCloseHour)
      return(false);

   if(InpUseTimeFilter)
     {
      if(InpStartHour <= InpEndHour)
        {
         if(dt.hour < InpStartHour || dt.hour >= InpEndHour)
            return(false);
        }
      else // overnight window (e.g. 22 -> 6)
        {
         if(dt.hour < InpStartHour && dt.hour >= InpEndHour)
            return(false);
        }
     }
   return(true);
  }

//+------------------------------------------------------------------+
//| Friday flat-close time check                                     |
//+------------------------------------------------------------------+
bool IsFridayCloseTime()
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   return(dt.day_of_week == 5 && dt.hour >= InpFridayCloseHour);
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
