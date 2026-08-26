//+------------------------------------------------------------------+
//|                                    ChienQuadraReversal_v320.mq5 |
//|                                                                  |
//| VERIFICATION BUILD v3.20 - multi-symbol, single tester run       |
//|                                                                  |
//| Same four-condition consensus reversal as v3.10, but this build  |
//| trades ALL seven pairs from ONE chart so a single tester run      |
//| measures the true aggregate drawdown, including days when        |
//| several pairs signal at once.                                    |
//|                                                                  |
//| That matters here in a way it did not for MondayYen. The four    |
//| conditions all describe an exhausted move, so they tend to fire  |
//| on risk-off days when every dollar pair moves together. Running  |
//| seven single-symbol tests and adding the results would understate|
//| the drawdown, because it never books the concurrent positions.   |
//|                                                                  |
//| Signal (all four must agree on the completed daily bar):         |
//|   1. RSI(14) below 35 (above 65 for shorts)                      |
//|   2. close more than 1.5 sample SD from the mean of the 20       |
//|      closes before it                                            |
//|   3. at least three consecutive down (up) closes                 |
//|   4. that day moved more than 0.5% against the trade direction   |
//| Entry at the 02:00 bar the next trading day, stop 1.5 x daily    |
//| ATR(14), target 1.2 x the stop, time exit after 8 daily bars.    |
//| One position per symbol, no averaging, no martingale.            |
//|                                                                  |
//| Every value that affects the result is a compile-time constant,  |
//| so a saved tester parameter set cannot change what is tested.    |
//| Risk is fixed at 0.5% per trade to match the MondayYen v3.10     |
//| verification basis, so the two products can be combined.         |
//|                                                                  |
//| Attach to ONE chart, H1, any of the seven symbols. The tester    |
//| must run in "every tick" or "1 minute OHLC" mode with all seven  |
//| symbols available in Market Watch.                               |
//|                                                                  |
//| No account locks, no expiry date, no external DLLs.              |
//+------------------------------------------------------------------+
#property copyright "iq87jun-star"
#property link      "https://www.gogojungle.co.jp/"
#property version   "3.20"

#include <Trade\Trade.mqh>

#define EA_BUILD "QuadraReversal v3.20-MULTI-FIXED"
#define NSYM 7

//--- fixed strategy settings: deliberately NOT inputs ---------------
const int    FIX_ENTRY_HOUR   = 2;     // enter at the open of this server hour
const int    FIX_RSI_PERIOD   = 14;
const double FIX_RSI_BUY      = 35.0;  // oversold threshold
const double FIX_RSI_SELL     = 65.0;  // overbought threshold
const int    FIX_ZWIN         = 20;    // window for the z-score
const double FIX_Z            = 1.5;   // z-score threshold
const int    FIX_RUN          = 3;     // consecutive closes required
const double FIX_MOVE         = 0.005; // daily move required (0.5%)
const int    FIX_NEED         = 4;     // conditions that must agree (all four)
const int    FIX_ATR_PERIOD   = 14;
const double FIX_SL_ATR       = 1.5;   // stop = daily ATR x this
const double FIX_RR           = 1.2;   // target = stop x this
const int    FIX_MAX_HOLD     = 8;     // daily bars before the time exit
const double FIX_RISK_PERCENT = 0.5;   // risk per trade, % of balance
const double FIX_MAX_LOT      = 10.0;

//--- the seven symbols, without broker suffixes
string BASE_SYMBOLS[NSYM] =
  {"USDJPY","EURJPY","GBPJPY","GBPUSD","AUDUSD","USDCAD","USDCHF"};

//=== Operational: none of these change the strategy =================
input long   InpMagicNumber     = 87500;    // Magic number (base)
input string InpTradeComment    = "CQR320"; // Order comment
input int    InpSlippagePoints  = 20;       // Max slippage (points)
input int    InpMaxSpreadPoints = 60;       // Max spread at entry (points, 0 = off)

//--- globals
CTrade   g_trade;
string   g_sym[NSYM];          // resolved symbol names
long     g_magicOf[NSYM];
int      g_hRsi[NSYM];
int      g_hAtr[NSYM];
bool     g_live[NSYM];         // symbol usable
datetime g_lastBar = 0;
int      g_signalCount[NSYM];

//+------------------------------------------------------------------+
//| Resolve a base symbol against the broker's naming                |
//+------------------------------------------------------------------+
string ResolveSymbol(const string base)
  {
   string suf[] = {"", ".a", ".b", ".c", ".e", ".i", ".m", ".p", ".r", ".s", ".z",
                   "m", "c", "_", "-", ".raw", ".ecn", ".pro", ".stp", ".sd", "+",
                   ".micro", ".std", "#", ".fx", "_SB", ".pi"};
   for(int i = 0; i < ArraySize(suf); i++)
     {
      string cand = base + suf[i];
      if(SymbolSelect(cand, true))
         return(cand);
     }
   // fallback: scan the whole symbol table for a name containing the base
   int total = SymbolsTotal(false);
   string best = "";
   for(int i = 0; i < total; i++)
     {
      string nm = SymbolName(i, false);
      string up = nm; StringToUpper(up);
      string ub = base; StringToUpper(ub);
      if(StringFind(up, ub) < 0)
         continue;
      if(best == "" || StringLen(nm) < StringLen(best))
         best = nm;
     }
   if(best != "" && SymbolSelect(best, true))
      return(best);
   return("");
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   g_trade.SetDeviationInPoints(InpSlippagePoints);

   int ready = 0;
   for(int s = 0; s < NSYM; s++)
     {
      g_live[s] = false;
      g_hRsi[s] = INVALID_HANDLE;
      g_hAtr[s] = INVALID_HANDLE;
      g_signalCount[s] = 0;

      g_sym[s] = ResolveSymbol(BASE_SYMBOLS[s]);
      if(g_sym[s] == "")
        {
         PrintFormat("WARNING %s could not be resolved on this broker - skipped",
                     BASE_SYMBOLS[s]);
         continue;
        }
      if(g_sym[s] != BASE_SYMBOLS[s])
         PrintFormat("[symbol] %s -> %s", BASE_SYMBOLS[s], g_sym[s]);

      g_hRsi[s] = iRSI(g_sym[s], PERIOD_D1, FIX_RSI_PERIOD, PRICE_CLOSE);
      g_hAtr[s] = iATR(g_sym[s], PERIOD_D1, FIX_ATR_PERIOD);
      if(g_hRsi[s] == INVALID_HANDLE || g_hAtr[s] == INVALID_HANDLE)
        {
         PrintFormat("WARNING %s indicator handles failed - skipped", g_sym[s]);
         continue;
        }
      // distinct magic per symbol, same offsetting rule as v3.10
      g_magicOf[s] = InpMagicNumber
                   + (long)(StringLen(g_sym[s]) * 7 + StringGetCharacter(g_sym[s], 0))
                   + (long)s;
      g_live[s] = true;
      ready++;
     }

   LogSettings(ready);

   if(ready == 0)
     {
      Print("No symbols could be resolved - aborting");
      return(INIT_FAILED);
     }
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void LogSettings(const int ready)
  {
   Print("==================================================");
   PrintFormat("%s  (settings are compiled in)", EA_BUILD);
   PrintFormat("Signal  : ALL %d of  RSI(%d)<%.0f / |z(%d)|>%.1f / run>=%d / move>%.1f%%",
               FIX_NEED, FIX_RSI_PERIOD, FIX_RSI_BUY, FIX_ZWIN, FIX_Z, FIX_RUN,
               FIX_MOVE * 100);
   PrintFormat("Entry   : next trading day at %02d:00 server time", FIX_ENTRY_HOUR);
   PrintFormat("Exits   : SL=dailyATR(%d) x %.1f   TP=SL x %.1f   time exit %d bars",
               FIX_ATR_PERIOD, FIX_SL_ATR, FIX_RR, FIX_MAX_HOLD);
   PrintFormat("Risk    : %.2f%% of balance per trade, cap %.2f lots",
               FIX_RISK_PERCENT, FIX_MAX_LOT);
   PrintFormat("Symbols : %d of %d resolved", ready, NSYM);
   string list = "";
   for(int s = 0; s < NSYM; s++)
      if(g_live[s]) list += (list == "" ? "" : ", ") + g_sym[s];
   PrintFormat("          %s", list);
   Print("All seven trade from THIS chart, so the tester books concurrent");
   Print("positions and reports the true aggregate drawdown.");
   Print("Expect roughly 6 trades a year per symbol - few by design.");
   Print("==================================================");
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   int tot = 0;
   for(int s = 0; s < NSYM; s++)
     {
      if(g_hRsi[s] != INVALID_HANDLE) IndicatorRelease(g_hRsi[s]);
      if(g_hAtr[s] != INVALID_HANDLE) IndicatorRelease(g_hAtr[s]);
      if(g_live[s])
        {
         PrintFormat("[signals] %-8s %d", g_sym[s], g_signalCount[s]);
         tot += g_signalCount[s];
        }
     }
   PrintFormat("[signals] TOTAL    %d", tot);
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   if(!IsNewH1Bar())
      return;

   for(int s = 0; s < NSYM; s++)
     {
      if(!g_live[s])
         continue;

      if(HasOpenPosition(s))
        {
         CheckTimeExit(s);
         continue;
        }

      datetime bt = iTime(g_sym[s], PERIOD_H1, 0);
      if(bt == 0)
         continue;

      MqlDateTime dt;
      TimeToStruct(bt, dt);
      if(dt.hour != FIX_ENTRY_HOUR)
         continue;
      if(dt.day_of_week < 1 || dt.day_of_week > 5)
         continue;
      if(!SpreadOk(s))
         continue;

      int sig = Signal(s);
      if(sig == 0)
         continue;

      g_signalCount[s]++;
      OpenTrade(s, sig);
     }
  }

//+------------------------------------------------------------------+
void OpenTrade(const int s, const int sig)
  {
   double atr;
   if(!DailyBuf(g_hAtr[s], 1, atr) || atr <= 0.0)
      return;

   double price  = (sig > 0) ? SymbolInfoDouble(g_sym[s], SYMBOL_ASK)
                             : SymbolInfoDouble(g_sym[s], SYMBOL_BID);
   if(price <= 0.0)
      return;

   int    digits = (int)SymbolInfoInteger(g_sym[s], SYMBOL_DIGITS);
   double slDist = atr * FIX_SL_ATR;
   double tpDist = slDist * FIX_RR;
   double sl = NormalizeDouble(sig > 0 ? price - slDist : price + slDist, digits);
   double tp = NormalizeDouble(sig > 0 ? price + tpDist : price - tpDist, digits);

   double lots = CalcLots(s, slDist);
   if(lots <= 0.0)
     {
      PrintFormat("%s: lot calculation returned 0 - trade skipped", g_sym[s]);
      return;
     }

   g_trade.SetExpertMagicNumber(g_magicOf[s]);
   g_trade.SetTypeFillingBySymbol(g_sym[s]);

   ENUM_ORDER_TYPE type = (sig > 0) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   if(!g_trade.PositionOpen(g_sym[s], type, lots, price, sl, tp, InpTradeComment))
      PrintFormat("%s: PositionOpen failed retcode=%d (%s)", g_sym[s],
                  g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
  }

//+------------------------------------------------------------------+
//| Four-condition consensus on the completed daily bar (index 1)    |
//+------------------------------------------------------------------+
int Signal(const int s)
  {
   string sym = g_sym[s];

   double rsi;
   if(!DailyBuf(g_hRsi[s], 1, rsi))
      return(0);

   // sample mean and SD of the 20 closes that precede the signal bar
   double sum = 0.0, sum2 = 0.0;
   for(int k = 2; k <= FIX_ZWIN + 1; k++)
     {
      double c = iClose(sym, PERIOD_D1, k);
      if(c <= 0.0) return(0);
      sum += c; sum2 += c * c;
     }
   double mean = sum / FIX_ZWIN;
   double var  = (sum2 - FIX_ZWIN * mean * mean) / (FIX_ZWIN - 1);
   if(var <= 0.0) return(0);
   double sd = MathSqrt(var);

   double c1 = iClose(sym, PERIOD_D1, 1);
   double c2 = iClose(sym, PERIOD_D1, 2);
   if(c1 <= 0.0 || c2 <= 0.0) return(0);
   double z = (c1 - mean) / sd;

   int down = 0, up = 0;
   for(int k = 0; k < 12; k++)
     {
      double a = iClose(sym, PERIOD_D1, 1 + k);
      double b = iClose(sym, PERIOD_D1, 2 + k);
      if(a <= 0.0 || b <= 0.0) break;
      if(a < b) down++; else break;
     }
   for(int k = 0; k < 12; k++)
     {
      double a = iClose(sym, PERIOD_D1, 1 + k);
      double b = iClose(sym, PERIOD_D1, 2 + k);
      if(a <= 0.0 || b <= 0.0) break;
      if(a > b) up++; else break;
     }

   double ret = (c1 - c2) / c2;

   int buy  = (rsi < FIX_RSI_BUY)  + (z < -FIX_Z) + (down >= FIX_RUN) + (ret < -FIX_MOVE);
   int sell = (rsi > FIX_RSI_SELL) + (z >  FIX_Z) + (up   >= FIX_RUN) + (ret >  FIX_MOVE);

   if(buy  >= FIX_NEED && buy  > sell) return(1);
   if(sell >= FIX_NEED && sell > buy)  return(-1);
   return(0);
  }

//+------------------------------------------------------------------+
void CheckTimeExit(const int s)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != g_sym[s] ||
         PositionGetInteger(POSITION_MAGIC) != g_magicOf[s])
         continue;

      datetime opened = (datetime)PositionGetInteger(POSITION_TIME);
      int bars = Bars(g_sym[s], PERIOD_D1, opened, TimeCurrent());
      if(bars > FIX_MAX_HOLD)
        {
         g_trade.SetExpertMagicNumber(g_magicOf[s]);
         g_trade.SetTypeFillingBySymbol(g_sym[s]);
         if(!g_trade.PositionClose(ticket, InpSlippagePoints))
            PrintFormat("%s: PositionClose failed retcode=%d", g_sym[s],
                        g_trade.ResultRetcode());
        }
     }
  }

//+------------------------------------------------------------------+
bool DailyBuf(const int handle, const int shift, double &value)
  {
   double buf[1];
   if(CopyBuffer(handle, 0, shift, 1, buf) != 1)
      return(false);
   value = buf[0];
   return(true);
  }

//+------------------------------------------------------------------+
bool IsNewH1Bar()
  {
   datetime t = iTime(_Symbol, PERIOD_H1, 0);
   if(t == 0 || t == g_lastBar)
      return(false);
   g_lastBar = t;
   return(true);
  }

//+------------------------------------------------------------------+
double CalcLots(const int s, const double slDistance)
  {
   string sym = g_sym[s];
   double tickValue = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE);
   if(tickValue <= 0.0 || tickSize <= 0.0 || slDistance <= 0.0)
      return(0.0);

   double lossPerLot = slDistance / tickSize * tickValue;
   if(lossPerLot <= 0.0)
      return(0.0);

   double lots = AccountInfoDouble(ACCOUNT_BALANCE) * FIX_RISK_PERCENT / 100.0 / lossPerLot;

   double minLot  = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
   double maxLot  = MathMin(SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX), FIX_MAX_LOT);
   double lotStep = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);

   if(lotStep > 0.0)
      lots = MathFloor(lots / lotStep) * lotStep;
   lots = MathMax(minLot, MathMin(maxLot, lots));

   if(lots < minLot)
      return(0.0);

   int lotDigits = 2;
   if(lotStep > 0.0)
     {
      lotDigits = 0;
      double st = lotStep;
      while(st < 1.0 && lotDigits < 8) { st *= 10.0; lotDigits++; }
     }
   return(NormalizeDouble(lots, lotDigits));
  }

//+------------------------------------------------------------------+
bool HasOpenPosition(const int s)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) == g_sym[s] &&
         PositionGetInteger(POSITION_MAGIC) == g_magicOf[s])
         return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
bool SpreadOk(const int s)
  {
   if(InpMaxSpreadPoints <= 0)
      return(true);
   long spread = SymbolInfoInteger(g_sym[s], SYMBOL_SPREAD);
   return(spread <= InpMaxSpreadPoints);
  }
//+------------------------------------------------------------------+
