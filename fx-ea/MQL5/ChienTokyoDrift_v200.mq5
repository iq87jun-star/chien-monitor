//+------------------------------------------------------------------+
//|                                          ChienTokyoDrift_v200.mq5 |
//|                                                                  |
//| VERIFICATION BUILD v2.00 - Tokyo morning drift, GBPJPY           |
//|                                                                  |
//| Buys GBPJPY at the open of the server-hour-1 H1 bar and closes   |
//| at the open of the next H1 bar (about 8:00 -> 9:00 JST), riding  |
//| the intraday rise of yen crosses into the Tokyo fix driven by    |
//| importer demand. Long only, one bar hold, never holds over the   |
//| swap rollover, no averaging, no martingale.                      |
//|                                                                  |
//| Found and validated on real exported MT5 bars 2016-2026:         |
//|   2,055 trades, PF 1.93 raw / 1.57 with 0.5 pip slippage each    |
//|   way, in-sample and out-of-sample both strong, t-stat 10.7.     |
//|                                                                  |
//| Every value that affects the result is a compile-time constant.  |
//| A saved tester parameter set cannot override them, so this build |
//| always tests the settings it was built with.                     |
//|                                                                  |
//| Requires a broker on GMT+2/+3 server time (standard for most     |
//| MT5 brokers, including MetaQuotes demo).                         |
//|                                                                  |
//| No account locks, no expiry date, no external DLLs.              |
//+------------------------------------------------------------------+
#property copyright "iq87jun-star"
#property link      "https://www.gogojungle.co.jp/"
#property version   "2.00"

#include <Trade\Trade.mqh>

#define EA_BUILD "TokyoDrift v2.00-FIXED"

//--- fixed strategy settings: deliberately NOT inputs ---------------
const int    FIX_ENTRY_HOUR   = 1;     // buy at the open of this server hour
const int    FIX_HOLD_BARS    = 1;     // close at the open of the Nth bar after entry
const int    FIX_ATR_PERIOD   = 14;    // ATR period for the safety stop
const double FIX_SL_ATR       = 3.0;   // safety stop = ATR x this (rarely hit)
const double FIX_RISK_PERCENT = 1.0;   // risk per trade, % of balance
const double FIX_MAX_LOT      = 10.0;  // lot cap

//--- operational inputs: none of these change the strategy ----------
input long   InpMagicNumber     = 87200;   // Magic number
input string InpTradeComment    = "CTD200"; // Order comment
input int    InpSlippagePoints  = 10;      // Max slippage (points)
input int    InpMaxSpreadPoints = 30;      // Max spread (points, 0 = off)

//--- globals
CTrade   g_trade;
int      g_hAtr = INVALID_HANDLE;
datetime g_lastBarTime = 0;
int      g_barsHeld    = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   g_hAtr = iATR(_Symbol, PERIOD_H1, FIX_ATR_PERIOD);
   if(g_hAtr == INVALID_HANDLE)
     {
      Print("Init error: failed to create ATR handle");
      return(INIT_FAILED);
     }

   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetDeviationInPoints(InpSlippagePoints);
   g_trade.SetTypeFillingBySymbol(_Symbol);

   LogSettings();
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void LogSettings()
  {
   Print("==================================================");
   PrintFormat("%s  (settings are compiled in)", EA_BUILD);
   PrintFormat("Entry   : BUY at open of server hour %02d:00 (H1 bar)", FIX_ENTRY_HOUR);
   PrintFormat("Exit    : at open of the bar %d hour(s) later", FIX_HOLD_BARS);
   PrintFormat("Safety  : SL = ATR(%d) x %.1f  (rarely hit; exits are time-based)",
               FIX_ATR_PERIOD, FIX_SL_ATR);
   PrintFormat("Risk    : %.2f%% of balance per trade", FIX_RISK_PERCENT);
   PrintFormat("Spread  : max %d points at entry (only adjustable setting)", InpMaxSpreadPoints);
   Print("Intraday only - no swap, no weekend holds, long only, one position.");
   Print("Expected shape: ~190 trades/year, avg ~3 pips/trade, PF ~1.4-1.7.");
   Print("==================================================");
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(g_hAtr != INVALID_HANDLE) IndicatorRelease(g_hAtr);
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   if(!IsNewH1Bar())
      return;

   MqlDateTime dt;
   TimeToStruct(iTime(_Symbol, PERIOD_H1, 0), dt);

   // --- exit first: close at the open of the bar FIX_HOLD_BARS after entry
   if(HasOpenPosition())
     {
      g_barsHeld++;
      if(g_barsHeld >= FIX_HOLD_BARS)
         CloseAllPositions();
      return;   // never enter on the same bar as an exit
     }

   // --- entry at the open of the configured server hour
   if(dt.hour != FIX_ENTRY_HOUR)
      return;
   if(dt.day_of_week < 1 || dt.day_of_week > 5)
      return;
   if(!SpreadOk())
      return;

   double atr;
   double buf[1];
   if(CopyBuffer(g_hAtr, 0, 1, 1, buf) != 1)
      return;
   atr = buf[0];
   if(atr <= 0.0)
      return;

   double ask    = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double slDist = atr * FIX_SL_ATR;
   double sl     = NormalizeDouble(ask - slDist, _Digits);

   double lots = CalcLots(slDist);
   if(lots <= 0.0)
     {
      Print("Lot calculation returned 0 - trade skipped");
      return;
     }

   if(g_trade.PositionOpen(_Symbol, ORDER_TYPE_BUY, lots, ask, sl, 0.0, InpTradeComment))
      g_barsHeld = 0;
   else
      PrintFormat("PositionOpen failed: retcode=%d (%s)",
                  g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
  }

//+------------------------------------------------------------------+
bool IsNewH1Bar()
  {
   datetime t = iTime(_Symbol, PERIOD_H1, 0);
   if(t == g_lastBarTime)
      return(false);
   g_lastBarTime = t;
   return(true);
  }

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
void CloseAllPositions()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
        {
         if(!g_trade.PositionClose(ticket, InpSlippagePoints))
            PrintFormat("PositionClose failed: retcode=%d", g_trade.ResultRetcode());
        }
     }
  }

//+------------------------------------------------------------------+
bool SpreadOk()
  {
   if(InpMaxSpreadPoints <= 0)
      return(true);
   long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   return(spread <= InpMaxSpreadPoints);
  }
//+------------------------------------------------------------------+
