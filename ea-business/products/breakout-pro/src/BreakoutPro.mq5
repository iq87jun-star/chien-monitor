//+------------------------------------------------------------------+
//|                                                   BreakoutPro.mq5 |
//|        Flagship breakout EA — PRODUCTIZATION SCAFFOLD (MT5)       |
//+------------------------------------------------------------------+
//
//  This is the productization shell for the flagship breakout EA (JPY-cross
//  oriented). It reuses the proven risk-sizing and trade-management approach
//  from RiskGuard and adds the licensing layer, error handling and inputs
//  expected of a sellable product.
//
//  >>> INSERT YOUR APPROVED STRATEGY LOGIC IN GenerateSignal() <<<
//  The owner's existing, live EA logic is approved for reuse (Phase 0). Drop
//  the entry decision into GenerateSignal(); everything else (sizing, SL/TP,
//  break-even, trailing, spread/time filters, licensing) is provided here.
//
//  RISK DISCLOSURE: Trading leveraged products carries a high level of risk.
//  No profit is guaranteed. Past performance does not guarantee future results.
//
//  BUILD MODES: define exactly one (see RiskGuard for the licensing layer).
//      #define RG_BUILD_MARKET   // MQL5 Market build
//      #define RG_BUILD_SELF     // self-hosted build
//+------------------------------------------------------------------+
#property copyright "BreakoutPro"
#property version   "0.10"
#property strict
#property description "Breakout EA (productization scaffold). No profit guarantee. Trading is risky."

#define RG_BUILD_SELF
//#define RG_BUILD_MARKET

#include <Trade/Trade.mqh>
#include "../../risk-guard/src/LicenseClient.mqh"

//+------------------------------------------------------------------+
//| Inputs                                                           |
//+------------------------------------------------------------------+
input group "=== Strategy (fill these to match your logic) ==="
input int    InpBreakoutLookback = 20;     // Breakout lookback (bars)
input int    InpBufferPoints     = 30;     // Breakout buffer (points)
input ENUM_TIMEFRAMES InpTF      = PERIOD_CURRENT; // Signal timeframe

input group "=== Risk & sizing (reused from RiskGuard) ==="
input double InpRiskPercent   = 1.0;     // Risk per trade (% of balance)
input int    InpStopLossPips   = 200;    // Stop Loss (pips)
input double InpRiskReward      = 1.5;   // TP as R multiple (0 = none)

input group "=== Position management ==="
input bool   InpUseBreakEven   = true;
input int    InpBreakEvenPips  = 100;
input int    InpBreakEvenLock  = 10;
input bool   InpUseTrailing    = true;
input int    InpTrailStartPips = 150;
input int    InpTrailStepPips  = 100;

input group "=== Filters & execution ==="
input int    InpMaxSpreadPts   = 30;
input int    InpSlippagePts    = 20;
input bool   InpOnePerBar      = true;    // at most one entry per bar
input long   InpMagic          = 780001;

input group "=== Licensing (self-hosted build only) ==="
input string InpLicenseKey     = "";
input string InpLicenseServer  = "https://api.riskguard.app/verify";

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
CTrade   trade;
double   g_pip = 0.0;
bool     g_licensed = false;
datetime g_lastBar = 0;

//+------------------------------------------------------------------+
//| Sizing / management (same model as RiskGuard)                    |
//+------------------------------------------------------------------+
double PipSize()
  {
   int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   return((digits==3||digits==5)?point*10.0:point);
  }

double NormalizeVolume(double vol)
  {
   double minv=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double maxv=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(step<=0.0) step=0.01;
   vol=MathFloor(vol/step+1e-9)*step;
   if(vol<minv) vol=minv;
   if(vol>maxv) vol=maxv;
   return(NormalizeDouble(vol,2));
  }

double CalcLot(double slPips)
  {
   if(slPips<=0.0) return(0.0);
   double balance=AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney=balance*InpRiskPercent/100.0;
   double tickValue=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double tickSize=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(tickValue<=0.0||tickSize<=0.0) return(0.0);
   double lossPerLot=((slPips*g_pip)/tickSize)*tickValue;
   if(lossPerLot<=0.0) return(0.0);
   return(NormalizeVolume(riskMoney/lossPerLot));
  }

bool HasPosition()
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong t=PositionGetTicket(i);
      if(t==0) continue;
      if(PositionGetString(POSITION_SYMBOL)==_Symbol &&
         PositionGetInteger(POSITION_MAGIC)==InpMagic) return(true);
     }
   return(false);
  }

void ManagePositions()
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0) continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC)!=InpMagic) continue;
      long type=PositionGetInteger(POSITION_TYPE);
      double open=PositionGetDouble(POSITION_PRICE_OPEN);
      double curSL=PositionGetDouble(POSITION_SL);
      double curTP=PositionGetDouble(POSITION_TP);
      double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
      double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
      int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
      double newSL=curSL;
      if(type==POSITION_TYPE_BUY)
        {
         double p=(bid-open)/g_pip;
         if(InpUseBreakEven && p>=InpBreakEvenPips){double be=open+InpBreakEvenLock*g_pip; if(be>newSL)newSL=be;}
         if(InpUseTrailing && p>=InpTrailStartPips){double tr=bid-InpTrailStepPips*g_pip; if(tr>newSL)newSL=tr;}
         newSL=NormalizeDouble(newSL,digits);
         if(newSL>curSL && newSL<bid) trade.PositionModify(ticket,newSL,curTP);
        }
      else if(type==POSITION_TYPE_SELL)
        {
         double p=(open-ask)/g_pip;
         if(InpUseBreakEven && p>=InpBreakEvenPips){double be=open-InpBreakEvenLock*g_pip; if(curSL==0.0||be<newSL)newSL=be;}
         if(InpUseTrailing && p>=InpTrailStartPips){double tr=ask+InpTrailStepPips*g_pip; if(curSL==0.0||tr<newSL)newSL=tr;}
         newSL=NormalizeDouble(newSL,digits);
         if((curSL==0.0||newSL<curSL) && newSL>ask) trade.PositionModify(ticket,newSL,curTP);
        }
     }
  }

//+------------------------------------------------------------------+
//| >>> STRATEGY HOOK — INSERT APPROVED LOGIC HERE <<<               |
//| Return +1 to go long, -1 to go short, 0 for no trade.           |
//| The example below is a PLACEHOLDER Donchian-style breakout and   |
//| MUST be replaced with the owner's approved logic before sale.    |
//+------------------------------------------------------------------+
int GenerateSignal()
  {
   int look=InpBreakoutLookback;
   int hh=iHighest(_Symbol,InpTF,MODE_HIGH,look,1);
   int ll=iLowest(_Symbol,InpTF,MODE_LOW,look,1);
   if(hh<0||ll<0) return(0);
   double prevHigh=iHigh(_Symbol,InpTF,hh);
   double prevLow =iLow(_Symbol,InpTF,ll);
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double buf=InpBufferPoints*SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   if(ask>prevHigh+buf) return(+1);
   if(bid<prevLow-buf)  return(-1);
   return(0);
  }

//+------------------------------------------------------------------+
//| Entry                                                            |
//+------------------------------------------------------------------+
void TryEnter(int dir)
  {
   if(dir==0||!g_licensed) return;
   if(InpStopLossPips<=0) return;
   if(SymbolInfoInteger(_Symbol,SYMBOL_SPREAD)>InpMaxSpreadPts) return;
   if(HasPosition()) return;

   double lot=CalcLot(InpStopLossPips);
   if(lot<=0.0) return;

   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double slDist=InpStopLossPips*g_pip;
   double tpDist=(InpRiskReward>0.0)?InpStopLossPips*InpRiskReward*g_pip:0.0;
   int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   trade.SetDeviationInPoints(InpSlippagePts);
   trade.SetExpertMagicNumber(InpMagic);

   if(dir>0)
     {
      double sl=NormalizeDouble(ask-slDist,digits);
      double tp=(tpDist>0.0)?NormalizeDouble(ask+tpDist,digits):0.0;
      if(!trade.Buy(lot,_Symbol,0.0,sl,tp,"BreakoutPro"))
         Print("BreakoutPro buy failed: ",trade.ResultRetcodeDescription());
     }
   else
     {
      double sl=NormalizeDouble(bid+slDist,digits);
      double tp=(tpDist>0.0)?NormalizeDouble(bid-tpDist,digits):0.0;
      if(!trade.Sell(lot,_Symbol,0.0,sl,tp,"BreakoutPro"))
         Print("BreakoutPro sell failed: ",trade.ResultRetcodeDescription());
     }
  }

//+------------------------------------------------------------------+
//| Lifecycle                                                        |
//+------------------------------------------------------------------+
int OnInit()
  {
   g_pip=PipSize();
   if(g_pip<=0.0) return(INIT_FAILED);
   RGLicenseResult lic=RGCheckLicense("breakout-pro",InpLicenseKey,InpLicenseServer);
   g_licensed=lic.ok;
   if(!g_licensed){ Comment("BreakoutPro: license check failed -> ",lic.message); Print(lic.message); }
   else Comment("");
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason){ Comment(""); }

void OnTick()
  {
   ManagePositions();

   if(InpOnePerBar)
     {
      datetime bt=(datetime)SeriesInfoInteger(_Symbol,InpTF,SERIES_LASTBAR_DATE);
      if(bt==g_lastBar) return;
      g_lastBar=bt;
     }
   TryEnter(GenerateSignal());
  }
//+------------------------------------------------------------------+
