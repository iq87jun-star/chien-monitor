//+------------------------------------------------------------------+
//|                                                   TradeCloser.mq5 |
//|          One-click position & order closing / management panel    |
//|                                                       (MT5, EA)   |
//+------------------------------------------------------------------+
//
//  TradeCloser is a utility. It does NOT open trades and does NOT generate
//  signals. It gives you fast, reliable ways to CLOSE and manage existing
//  positions and pending orders from one on-chart panel:
//
//    - Close ALL / close current symbol only
//    - Close winners only / close losers only
//    - Partial close by % of volume
//    - Basket targets: auto-close everything when total floating P/L reaches
//      a money or %-of-balance profit target, or a loss stop
//    - Delete all pending orders
//    - Panic button: close all positions + delete all pendings at once
//
//  Because it sells a FUNCTION (closing trades), not performance, every claim
//  in its marketing is a verifiable fact. No profit is implied or guaranteed.
//
//  RISK DISCLOSURE: Trading leveraged products carries a high level of risk.
//  This tool manages order closing only; it does not predict markets or
//  guarantee any outcome. Past performance does not guarantee future results.
//
//  BUILD MODES (define exactly one):
//      #define RG_BUILD_MARKET   // MQL5 Market build (platform licensing)
//      #define RG_BUILD_SELF     // Self-hosted build (own license server)
//+------------------------------------------------------------------+
#property copyright "TradeCloser"
#property version   "1.00"
#property strict
#property description "One-click closing & basket management for open positions and pending orders."
#property description "Utility only. Does not open trades, predict markets, or guarantee profit."

#define RG_BUILD_SELF
//#define RG_BUILD_MARKET

#include <Trade/Trade.mqh>
#include "../../risk-guard/src/LicenseClient.mqh"

//+------------------------------------------------------------------+
//| Inputs                                                           |
//+------------------------------------------------------------------+
input group "=== Scope ==="
input bool   InpCurrentSymbolOnly = false;  // Act on the current chart symbol only
input bool   InpFilterByMagic     = false;  // Only touch positions with InpMagic
input long   InpMagic             = 0;      // Magic to match (when filtering)

input group "=== Partial close ==="
input double InpPartialPercent    = 50.0;   // % of volume to close on "Close %"

input group "=== Basket auto-close (0 = off) ==="
input double InpTargetProfitMoney = 0.0;    // Close all when total P/L >= this (account ccy)
input double InpTargetProfitPct   = 0.0;    // ...or >= this % of balance
input double InpStopLossMoney     = 0.0;    // Close all when total P/L <= -this (account ccy)
input double InpStopLossPct       = 0.0;    // ...or <= -this % of balance
input bool   InpBasketIncludesSwap= true;   // Include swap+commission in basket P/L

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

#define TC_PREFIX "TC_"
#define BTN_ALL      TC_PREFIX "all"
#define BTN_SYM      TC_PREFIX "sym"
#define BTN_WIN      TC_PREFIX "win"
#define BTN_LOSS     TC_PREFIX "loss"
#define BTN_PARTIAL  TC_PREFIX "partial"
#define BTN_PENDING  TC_PREFIX "pending"
#define BTN_PANIC    TC_PREFIX "panic"
#define LBL_INFO     TC_PREFIX "info"

//+------------------------------------------------------------------+
//| Selection helpers                                                |
//+------------------------------------------------------------------+
//--- does this position match the active scope filters?
bool PosInScope(const ulong ticket)
  {
   if(!PositionSelectByTicket(ticket)) return(false);
   if(InpCurrentSymbolOnly && PositionGetString(POSITION_SYMBOL)!=_Symbol) return(false);
   if(InpFilterByMagic && PositionGetInteger(POSITION_MAGIC)!=InpMagic)    return(false);
   return(true);
  }

//--- floating P/L of a selected position (optionally incl. swap+commission)
double PosPL(const bool inclCosts)
  {
   double pl=PositionGetDouble(POSITION_PROFIT);
   if(inclCosts)
      pl+=PositionGetDouble(POSITION_SWAP); // commission is realized on close; swap is the carry
   return(pl);
  }

double NormalizeVolume(const string sym,double vol)
  {
   double minv=SymbolInfoDouble(sym,SYMBOL_VOLUME_MIN);
   double step=SymbolInfoDouble(sym,SYMBOL_VOLUME_STEP);
   if(step<=0.0) step=0.01;
   vol=MathFloor(vol/step+1e-9)*step;
   if(vol<minv) vol=0.0; // below min -> cannot partial-close this leg
   return(NormalizeDouble(vol,2));
  }

//+------------------------------------------------------------------+
//| Close actions                                                    |
//+------------------------------------------------------------------+
//--- mode: 0=all in scope, 1=winners only, 2=losers only
int ClosePositions(const int mode)
  {
   if(!g_licensed) return(0);
   trade.SetDeviationInPoints(InpSlippagePts);
   int closed=0;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PosInScope(ticket)) continue;
      double pl=PosPL(true);
      if(mode==1 && pl<=0.0) continue;   // winners only
      if(mode==2 && pl>=0.0) continue;   // losers only
      if(trade.PositionClose(ticket)) closed++;
     }
   return(closed);
  }

int PartialClose(const double percent)
  {
   if(!g_licensed) return(0);
   double pct=MathMax(0.0,MathMin(100.0,percent));
   if(pct<=0.0) return(0);
   trade.SetDeviationInPoints(InpSlippagePts);
   int done=0;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PosInScope(ticket)) continue;
      string sym=PositionGetString(POSITION_SYMBOL);
      double vol=PositionGetDouble(POSITION_VOLUME);
      double cut=NormalizeVolume(sym,vol*pct/100.0);
      if(cut<=0.0) continue;
      if(cut>=vol) { if(trade.PositionClose(ticket)) done++; }
      else         { if(trade.PositionClosePartial(ticket,cut)) done++; }
     }
   return(done);
  }

int DeletePendings()
  {
   if(!g_licensed) return(0);
   int deleted=0;
   for(int i=OrdersTotal()-1;i>=0;i--)
     {
      ulong ticket=OrderGetTicket(i);
      if(ticket==0) continue;
      if(!OrderSelect(ticket)) continue;
      if(InpCurrentSymbolOnly && OrderGetString(ORDER_SYMBOL)!=_Symbol) continue;
      if(InpFilterByMagic && OrderGetInteger(ORDER_MAGIC)!=InpMagic)    continue;
      if(trade.OrderDelete(ticket)) deleted++;
     }
   return(deleted);
  }

void Panic()
  {
   int c=ClosePositions(0);
   int d=DeletePendings();
   Print("TradeCloser PANIC: closed ",c," positions, deleted ",d," pendings.");
  }

//+------------------------------------------------------------------+
//| Basket P/L monitoring                                            |
//+------------------------------------------------------------------+
double BasketPL()
  {
   double sum=0.0;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PosInScope(ticket)) continue;
      sum+=PosPL(InpBasketIncludesSwap);
     }
   return(sum);
  }

void CheckBasketTargets()
  {
   bool anyTarget = (InpTargetProfitMoney>0.0 || InpTargetProfitPct>0.0 ||
                     InpStopLossMoney>0.0   || InpStopLossPct>0.0);
   if(!anyTarget) return;

   double pl=BasketPL();
   double balance=AccountInfoDouble(ACCOUNT_BALANCE);

   double profitTrigger=0.0;
   if(InpTargetProfitMoney>0.0) profitTrigger=InpTargetProfitMoney;
   if(InpTargetProfitPct>0.0)
     {
      double byPct=balance*InpTargetProfitPct/100.0;
      profitTrigger=(profitTrigger>0.0)?MathMin(profitTrigger,byPct):byPct;
     }

   double lossTrigger=0.0;
   if(InpStopLossMoney>0.0) lossTrigger=InpStopLossMoney;
   if(InpStopLossPct>0.0)
     {
      double byPct=balance*InpStopLossPct/100.0;
      lossTrigger=(lossTrigger>0.0)?MathMin(lossTrigger,byPct):byPct;
     }

   if(profitTrigger>0.0 && pl>=profitTrigger)
     { Print("TradeCloser: profit target hit (",pl,"). Closing basket."); ClosePositions(0); }
   else if(lossTrigger>0.0 && pl<=-lossTrigger)
     { Print("TradeCloser: loss stop hit (",pl,"). Closing basket."); ClosePositions(0); }
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

void UpdateInfo()
  {
   if(ObjectFind(0,LBL_INFO)<0) return;
   double pl=BasketPL();
   string scope=InpCurrentSymbolOnly?_Symbol:"ALL";
   ObjectSetString(0,LBL_INFO,OBJPROP_TEXT,
      StringFormat("TradeCloser | scope:%s | basket P/L: %.2f | %s",scope,pl,g_status));
  }

void BuildPanel()
  {
   int x=10,y=22,w=110,h=22,gap=4;
   Label(LBL_INFO,x,y,"TradeCloser"); y+=18;
   Button(BTN_ALL,    x,           y, w,h,"CLOSE ALL",    clrFireBrick);
   Button(BTN_SYM,    x+w+gap,     y, w,h,"CLOSE SYMBOL", clrIndianRed); y+=h+gap;
   Button(BTN_WIN,    x,           y, w,h,"CLOSE WINNERS",clrSeaGreen);
   Button(BTN_LOSS,   x+w+gap,     y, w,h,"CLOSE LOSERS", clrDarkOrange); y+=h+gap;
   Button(BTN_PARTIAL,x,           y, w,h,"CLOSE %",      clrSteelBlue);
   Button(BTN_PENDING,x+w+gap,     y, w,h,"DEL PENDINGS", clrDimGray); y+=h+gap;
   Button(BTN_PANIC,  x,        y, w*2+gap,h+4,"PANIC: CLOSE EVERYTHING", clrCrimson);
   UpdateInfo();
   ChartRedraw();
  }

void RemovePanel()
  {
   string names[]={BTN_ALL,BTN_SYM,BTN_WIN,BTN_LOSS,BTN_PARTIAL,BTN_PENDING,BTN_PANIC,LBL_INFO};
   for(int i=0;i<ArraySize(names);i++) ObjectDelete(0,names[i]);
  }

//+------------------------------------------------------------------+
//| Lifecycle                                                        |
//+------------------------------------------------------------------+
int OnInit()
  {
   RGLicenseResult lic=RGCheckLicense("trade-closer",InpLicenseKey,InpLicenseServer);
   g_licensed=lic.ok;
   g_status=lic.message;
   if(!g_licensed)
     {
      Comment("TradeCloser: license check failed -> ",lic.message,"\nButtons are disabled.");
      Print("TradeCloser license: ",lic.message);
     }
   else
      Comment("");
   BuildPanel();
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   RemovePanel();
   Comment("");
  }

void OnTick()
  {
   CheckBasketTargets();
   UpdateInfo();
  }

void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)
  {
   if(id!=CHARTEVENT_OBJECT_CLICK) return;

   if(sparam==BTN_ALL)          Print("TradeCloser: closed ",ClosePositions(0)," positions.");
   else if(sparam==BTN_SYM)     { /* honor symbol scope for this click */ Print("TradeCloser: closed ",CloseCurrentSymbol()," positions on ",_Symbol,"."); }
   else if(sparam==BTN_WIN)     Print("TradeCloser: closed ",ClosePositions(1)," winners.");
   else if(sparam==BTN_LOSS)    Print("TradeCloser: closed ",ClosePositions(2)," losers.");
   else if(sparam==BTN_PARTIAL) Print("TradeCloser: partial-closed ",PartialClose(InpPartialPercent)," positions.");
   else if(sparam==BTN_PENDING) Print("TradeCloser: deleted ",DeletePendings()," pendings.");
   else if(sparam==BTN_PANIC)   Panic();

   // reset button visual state
   if(StringFind(sparam,TC_PREFIX)==0)
     {
      ObjectSetInteger(0,sparam,OBJPROP_STATE,false);
      ChartRedraw();
     }
  }

//--- CLOSE SYMBOL: force current-symbol scope regardless of InpCurrentSymbolOnly
int CloseCurrentSymbol()
  {
   if(!g_licensed) return(0);
   trade.SetDeviationInPoints(InpSlippagePts);
   int closed=0;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol) continue;
      if(InpFilterByMagic && PositionGetInteger(POSITION_MAGIC)!=InpMagic) continue;
      if(trade.PositionClose(ticket)) closed++;
     }
   return(closed);
  }
//+------------------------------------------------------------------+
