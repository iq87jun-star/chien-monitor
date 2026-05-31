//+------------------------------------------------------------------+
//|                                                  TrailManager.mq5 |
//|     Add-on trailing stop & break-even manager for ANY position    |
//|                                                       (MT5, EA)   |
//+------------------------------------------------------------------+
//
//  TrailManager is a utility that MANAGES existing positions. It does NOT open
//  trades and does NOT generate signals. Attach it to a chart and it applies
//  break-even and a trailing stop to positions you (or any other tool / EA /
//  manual order) already opened.
//
//  Three trailing modes:
//    - FIXED : trail at a fixed pip distance once in profit
//    - ATR   : trail at ATR * multiplier (volatility-adaptive)
//    - STEP  : trail only in discrete steps (reduces broker modify spam)
//
//  Plus:
//    - Break-even: move SL to entry (+lock) after a profit threshold
//    - Optional initial SL/TP for positions that have none
//    - Scope filters: current symbol only, and/or match a magic number
//    - On-chart status panel with enable/disable toggle
//
//  Because it sells a FUNCTION (managing stops), every marketing claim is a
//  verifiable fact. No profit is implied or guaranteed.
//
//  RISK DISCLOSURE: Trading leveraged products carries a high level of risk.
//  This tool manages stop-loss orders only; it does not predict markets or
//  guarantee any outcome. Past performance does not guarantee future results.
//
//  BUILD MODES (define exactly one):
//      #define RG_BUILD_MARKET   // MQL5 Market build (platform licensing)
//      #define RG_BUILD_SELF     // Self-hosted build (own license server)
//+------------------------------------------------------------------+
#property copyright "TrailManager"
#property version   "1.00"
#property strict
#property description "Add-on trailing stop & break-even for any existing position (fixed/ATR/step)."
#property description "Utility only. Does not open trades, predict markets, or guarantee profit."

#define RG_BUILD_SELF
//#define RG_BUILD_MARKET

#include <Trade/Trade.mqh>
#include "LicenseClient.mqh"

//+------------------------------------------------------------------+
//| Inputs                                                           |
//+------------------------------------------------------------------+
enum ENUM_TRAIL_MODE { TRAIL_FIXED=0, TRAIL_ATR=1, TRAIL_STEP=2 };

input group "=== Scope ==="
input bool   InpCurrentSymbolOnly = true;   // Manage current chart symbol only
input bool   InpFilterByMagic     = false;  // Only manage positions with InpMagic
input long   InpMagic             = 0;      // Magic to match (when filtering)

input group "=== Break-even ==="
input bool   InpUseBreakEven      = true;   // Move SL to break-even
input int    InpBreakEvenPips     = 100;    // Profit (pips) to trigger break-even
input int    InpBreakEvenLock     = 10;     // Profit (pips) locked at break-even

input group "=== Trailing ==="
input ENUM_TRAIL_MODE InpTrailMode= TRAIL_FIXED; // Trailing mode
input int    InpTrailStartPips    = 150;    // Profit (pips) before trailing starts
input int    InpTrailDistancePips = 100;    // FIXED/STEP: trailing distance (pips)
input int    InpTrailStepPips     = 20;     // STEP: min SL advance per move (pips)
input int    InpATRPeriod         = 14;     // ATR: period
input double InpATRMultiplier     = 2.0;    // ATR: distance multiplier
input ENUM_TIMEFRAMES InpATRTF    = PERIOD_CURRENT; // ATR: timeframe

input group "=== Optional initial protection ==="
input bool   InpSetSLIfMissing    = false;  // Set an initial SL if a position has none
input int    InpInitialSLPips     = 300;    // Initial SL distance (pips)

input group "=== Execution ==="
input int    InpSlippagePts       = 20;     // Max deviation (points)

input group "=== Licensing (self-hosted build only) ==="
input string InpLicenseKey        = "";
input string InpLicenseServer     = "https://api.riskguard.app/verify";

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
CTrade trade;
bool   g_licensed = false;
string g_status   = "";
bool   g_enabled  = true;
int    g_atrHandle= INVALID_HANDLE;

#define TM_PREFIX "TM_"
#define BTN_TOGGLE TM_PREFIX "toggle"
#define LBL_INFO   TM_PREFIX "info"

//+------------------------------------------------------------------+
//| Helpers                                                          |
//+------------------------------------------------------------------+
double PipSize(const string sym)
  {
   int digits=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
   double point=SymbolInfoDouble(sym,SYMBOL_POINT);
   return((digits==3||digits==5)?point*10.0:point);
  }

bool PosInScope(const ulong ticket)
  {
   if(!PositionSelectByTicket(ticket)) return(false);
   if(InpCurrentSymbolOnly && PositionGetString(POSITION_SYMBOL)!=_Symbol) return(false);
   if(InpFilterByMagic && PositionGetInteger(POSITION_MAGIC)!=InpMagic)    return(false);
   return(true);
  }

//--- current ATR distance (price terms) for the position's symbol
double ATRDistance()
  {
   if(g_atrHandle==INVALID_HANDLE) return(0.0);
   double buf[];
   if(CopyBuffer(g_atrHandle,0,0,1,buf)<1) return(0.0);
   return(buf[0]*InpATRMultiplier);
  }

//+------------------------------------------------------------------+
//| Core: manage one position                                        |
//+------------------------------------------------------------------+
void ManageOne(const ulong ticket)
  {
   string sym = PositionGetString(POSITION_SYMBOL);
   long   type= PositionGetInteger(POSITION_TYPE);
   double open= PositionGetDouble(POSITION_PRICE_OPEN);
   double curSL=PositionGetDouble(POSITION_SL);
   double curTP=PositionGetDouble(POSITION_TP);
   double pip = PipSize(sym);
   int    digits=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
   double bid = SymbolInfoDouble(sym,SYMBOL_BID);
   double ask = SymbolInfoDouble(sym,SYMBOL_ASK);

   //--- optionally place an initial SL when the position has none
   if(InpSetSLIfMissing && curSL==0.0)
     {
      double sl = (type==POSITION_TYPE_BUY) ? open-InpInitialSLPips*pip
                                            : open+InpInitialSLPips*pip;
      sl=NormalizeDouble(sl,digits);
      if(trade.PositionModify(ticket,sl,curTP)) curSL=sl;
     }

   double newSL=curSL;

   if(type==POSITION_TYPE_BUY)
     {
      double profitPips=(bid-open)/pip;

      //--- break-even
      if(InpUseBreakEven && profitPips>=InpBreakEvenPips)
        {
         double be=open+InpBreakEvenLock*pip;
         if(be>newSL) newSL=be;
        }

      //--- trailing
      if(profitPips>=InpTrailStartPips)
        {
         double dist;
         if(InpTrailMode==TRAIL_ATR) dist=ATRDistance();
         else                        dist=InpTrailDistancePips*pip;
         if(dist>0.0)
           {
            double tr=bid-dist;
            if(InpTrailMode==TRAIL_STEP)
              {
               // advance only if the gain over current SL exceeds the step
               if(tr-newSL>=InpTrailStepPips*pip && tr>newSL) newSL=tr;
              }
            else if(tr>newSL) newSL=tr;
           }
        }

      newSL=NormalizeDouble(newSL,digits);
      if(newSL>curSL && newSL<bid)
         trade.PositionModify(ticket,newSL,curTP);
     }
   else if(type==POSITION_TYPE_SELL)
     {
      double profitPips=(open-ask)/pip;

      if(InpUseBreakEven && profitPips>=InpBreakEvenPips)
        {
         double be=open-InpBreakEvenLock*pip;
         if(curSL==0.0 || be<newSL) newSL=be;
        }

      if(profitPips>=InpTrailStartPips)
        {
         double dist;
         if(InpTrailMode==TRAIL_ATR) dist=ATRDistance();
         else                        dist=InpTrailDistancePips*pip;
         if(dist>0.0)
           {
            double tr=ask+dist;
            if(InpTrailMode==TRAIL_STEP)
              {
               if(newSL-tr>=InpTrailStepPips*pip && (curSL==0.0 || tr<newSL)) newSL=tr;
              }
            else if(curSL==0.0 || tr<newSL) newSL=tr;
           }
        }

      newSL=NormalizeDouble(newSL,digits);
      if((curSL==0.0 || newSL<curSL) && newSL>ask)
         trade.PositionModify(ticket,newSL,curTP);
     }
  }

void ManageAll()
  {
   if(!g_licensed || !g_enabled) return;
   trade.SetDeviationInPoints(InpSlippagePts);
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PosInScope(ticket)) continue;
      ManageOne(ticket);
     }
  }

//+------------------------------------------------------------------+
//| Count managed positions (for the status label)                   |
//+------------------------------------------------------------------+
int CountInScope()
  {
   int n=0;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PosInScope(ticket)) continue;
      n++;
     }
   return(n);
  }

//+------------------------------------------------------------------+
//| UI                                                               |
//+------------------------------------------------------------------+
void Button(const string name,const int x,const int y,const int w,const int h,
            const string text,const color bg)
  {
   if(ObjectFind(0,name)>=0) ObjectDelete(0,name);
   ObjectCreate(0,name,OBJ_BUTTON,0,0,0);
   ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,name,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(0,name,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(0,name,OBJPROP_XSIZE,w);
   ObjectSetInteger(0,name,OBJPROP_YSIZE,h);
   ObjectSetString(0,name,OBJPROP_TEXT,text);
   ObjectSetInteger(0,name,OBJPROP_COLOR,clrWhite);
   ObjectSetInteger(0,name,OBJPROP_BGCOLOR,bg);
   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,9);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
  }

void Label(const string name,const int x,const int y,const string text)
  {
   if(ObjectFind(0,name)>=0) ObjectDelete(0,name);
   ObjectCreate(0,name,OBJ_LABEL,0,0,0);
   ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,name,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(0,name,OBJPROP_YDISTANCE,y);
   ObjectSetString(0,name,OBJPROP_TEXT,text);
   ObjectSetInteger(0,name,OBJPROP_COLOR,clrGainsboro);
   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,9);
  }

string ModeName()
  {
   switch(InpTrailMode)
     {
      case TRAIL_ATR:  return("ATR");
      case TRAIL_STEP: return("STEP");
      default:         return("FIXED");
     }
  }

void UpdateInfo()
  {
   if(ObjectFind(0,LBL_INFO)<0) return;
   string scope=InpCurrentSymbolOnly?_Symbol:"ALL";
   ObjectSetString(0,LBL_INFO,OBJPROP_TEXT,
      StringFormat("TrailManager | %s | mode:%s | managing:%d | %s",
                   scope,ModeName(),CountInScope(),
                   g_licensed?(g_enabled?"ON":"OFF"):g_status));
   if(ObjectFind(0,BTN_TOGGLE)>=0)
     {
      ObjectSetString(0,BTN_TOGGLE,OBJPROP_TEXT,g_enabled?"PAUSE":"RESUME");
      ObjectSetInteger(0,BTN_TOGGLE,OBJPROP_BGCOLOR,g_enabled?clrSeaGreen:clrDimGray);
     }
  }

void BuildPanel()
  {
   int x=10,y=22;
   Label(LBL_INFO,x,y,"TrailManager"); y+=18;
   Button(BTN_TOGGLE,x,y,120,24,"PAUSE",clrSeaGreen);
   UpdateInfo();
   ChartRedraw();
  }

void RemovePanel()
  {
   ObjectDelete(0,BTN_TOGGLE);
   ObjectDelete(0,LBL_INFO);
  }

//+------------------------------------------------------------------+
//| Lifecycle                                                        |
//+------------------------------------------------------------------+
int OnInit()
  {
   RGLicenseResult lic=RGCheckLicense("trail-manager",InpLicenseKey,InpLicenseServer);
   g_licensed=lic.ok;
   g_status=lic.message;

   if(InpTrailMode==TRAIL_ATR)
     {
      g_atrHandle=iATR(_Symbol,InpATRTF,InpATRPeriod);
      if(g_atrHandle==INVALID_HANDLE)
         Print("TrailManager: failed to create ATR handle.");
     }

   if(!g_licensed)
     {
      Comment("TrailManager: license check failed -> ",lic.message,"\nManagement is disabled.");
      Print("TrailManager license: ",lic.message);
     }
   else
      Comment("");

   BuildPanel();
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   if(g_atrHandle!=INVALID_HANDLE) IndicatorRelease(g_atrHandle);
   RemovePanel();
   Comment("");
  }

void OnTick()
  {
   ManageAll();
   UpdateInfo();
  }

void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)
  {
   if(id!=CHARTEVENT_OBJECT_CLICK) return;
   if(sparam==BTN_TOGGLE)
     {
      g_enabled=!g_enabled;
      ObjectSetInteger(0,sparam,OBJPROP_STATE,false);
      UpdateInfo();
      ChartRedraw();
     }
  }
//+------------------------------------------------------------------+
