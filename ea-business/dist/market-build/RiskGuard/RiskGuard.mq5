//+------------------------------------------------------------------+
//|                                                     RiskGuard.mq5 |
//|         Risk-based lot sizing + trade execution / management tool |
//|                                                       (MT5, EA)   |
//+------------------------------------------------------------------+
//
//  RiskGuard is a manual-trading assistant. It does NOT generate signals
//  or trade on its own. The trader presses Buy/Sell; RiskGuard computes the
//  position size from a fixed account-risk %, places protective Stop Loss /
//  Take Profit, and then manages the position (break-even, trailing stop,
//  spread guard).
//
//  RISK DISCLOSURE: Trading leveraged products carries a high level of risk.
//  RiskGuard is a tool for position sizing and order management only. It does
//  not predict markets and provides no guarantee of profit. Past performance
//  does not guarantee future results. Use at your own risk.
//
//  BUILD MODES (uncomment exactly one before compiling):
//      #define RG_BUILD_MARKET   // MQL5 Market build (platform licensing)
//      #define RG_BUILD_SELF     // Self-hosted build (own license server)
//+------------------------------------------------------------------+
#property copyright "RiskGuard"
#property version   "1.00"
#property strict
#property description "Risk-% based lot sizing + trade execution & management assistant."
#property description "Manual tool. Not a signal generator. No profit guarantee. Trading is risky."

//--- choose ONE build mode (default: self-hosted). For Market upload, switch.
#define RG_BUILD_MARKET
//#define RG_BUILD_SELF

#include <Trade/Trade.mqh>
#include "LicenseClient.mqh"

//+------------------------------------------------------------------+
//| Inputs                                                           |
//+------------------------------------------------------------------+
input group "=== Risk & sizing ==="
input double InpRiskPercent   = 1.0;    // Risk per trade (% of balance)
input double InpFixedLot       = 0.0;    // Fixed lot (>0 overrides risk %)
input int    InpStopLossPips   = 200;    // Stop Loss (pips, 0 = no SL -> trade blocked)
input double InpRiskReward      = 1.5;   // Take Profit as R multiple (0 = no TP)

input group "=== Position management ==="
input bool   InpUseBreakEven   = true;   // Move SL to break-even
input int    InpBreakEvenPips  = 100;    // Profit (pips) to trigger break-even
input int    InpBreakEvenLock  = 10;     // Lock-in (pips) above entry at BE
input bool   InpUseTrailing    = true;   // Use trailing stop
input int    InpTrailStartPips = 150;    // Profit (pips) before trailing starts
input int    InpTrailStepPips  = 100;    // Trailing distance (pips)

input group "=== Filters & execution ==="
input int    InpMaxSpreadPts   = 30;     // Max spread (points) to allow entry
input int    InpSlippagePts    = 20;     // Max deviation (points)
input long   InpMagic          = 770001; // Magic number

input group "=== Licensing (self-hosted build only) ==="
input string InpLicenseKey     = "";                         // License key
input string InpLicenseServer  = "https://api.riskguard.app/verify"; // License API URL

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
CTrade        trade;
double        g_pip          = 0.0;     // pip size in price terms
double        g_pointsPerPip = 1.0;     // points per pip (for 3/5-digit)
bool          g_licensed     = false;
string        g_status       = "";

#define RG_PREFIX "RG_"
#define BTN_BUY   RG_PREFIX "btnBuy"
#define BTN_SELL  RG_PREFIX "btnSell"
#define BTN_CLOSE RG_PREFIX "btnClose"
#define LBL_INFO  RG_PREFIX "lblInfo"

//+------------------------------------------------------------------+
//| Helpers                                                          |
//+------------------------------------------------------------------+
double PipSize()
  {
   int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   // 3 and 5 digit quotes: 1 pip = 10 points
   if(digits==3 || digits==5)
      return(point*10.0);
   return(point);
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

//--- lot from risk %: risk_money = balance * risk% ; loss for 1 lot over SL
double CalcLot(double slPips)
  {
   if(InpFixedLot>0.0)
      return(NormalizeVolume(InpFixedLot));

   if(slPips<=0.0)
      return(0.0);

   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance*InpRiskPercent/100.0;

   double tickValue = SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(tickValue<=0.0 || tickSize<=0.0)
      return(0.0);

   double slPrice   = slPips*g_pip;                 // SL distance in price
   double lossPerLot= (slPrice/tickSize)*tickValue; // loss for 1.0 lot
   if(lossPerLot<=0.0)
      return(0.0);

   double lot=riskMoney/lossPerLot;
   return(NormalizeVolume(lot));
  }

bool SpreadOK()
  {
   long spread=SymbolInfoInteger(_Symbol,SYMBOL_SPREAD);
   return(spread<=InpMaxSpreadPts);
  }

//+------------------------------------------------------------------+
//| Trade open                                                       |
//+------------------------------------------------------------------+
void OpenTrade(bool isBuy)
  {
   if(!g_licensed)
     { Print("RiskGuard: not licensed, order ignored."); return; }

   if(InpStopLossPips<=0)
     { Alert("RiskGuard: Stop Loss is 0. For risk control, set a Stop Loss."); return; }

   if(!SpreadOK())
     { Print("RiskGuard: spread too wide, entry skipped."); return; }

   double lot=CalcLot(InpStopLossPips);
   if(lot<=0.0)
     { Print("RiskGuard: computed lot is 0 (check risk %, SL, symbol specs)."); return; }

   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double slDist=InpStopLossPips*g_pip;
   double tpDist=(InpRiskReward>0.0)?InpStopLossPips*InpRiskReward*g_pip:0.0;

   double price,sl,tp;
   if(isBuy)
     {
      price=ask;
      sl=price-slDist;
      tp=(tpDist>0.0)?price+tpDist:0.0;
     }
   else
     {
      price=bid;
      sl=price+slDist;
      tp=(tpDist>0.0)?price-tpDist:0.0;
     }

   int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   sl=NormalizeDouble(sl,digits);
   tp=NormalizeDouble(tp,digits);

   trade.SetDeviationInPoints(InpSlippagePts);
   trade.SetExpertMagicNumber(InpMagic);

   bool ok = isBuy ? trade.Buy(lot,_Symbol,0.0,sl,tp,"RiskGuard")
                   : trade.Sell(lot,_Symbol,0.0,sl,tp,"RiskGuard");
   if(!ok)
      Print("RiskGuard: order failed. retcode=",trade.ResultRetcode()," ",trade.ResultRetcodeDescription());
  }

void CloseAll()
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0) continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC)!=InpMagic) continue;
      trade.PositionClose(ticket);
     }
  }

//+------------------------------------------------------------------+
//| Position management: break-even + trailing                       |
//+------------------------------------------------------------------+
void ManagePositions()
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0) continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC)!=InpMagic) continue;

      long   type   = PositionGetInteger(POSITION_TYPE);
      double open   = PositionGetDouble(POSITION_PRICE_OPEN);
      double curSL  = PositionGetDouble(POSITION_SL);
      double curTP  = PositionGetDouble(POSITION_TP);
      double bid    = SymbolInfoDouble(_Symbol,SYMBOL_BID);
      double ask    = SymbolInfoDouble(_Symbol,SYMBOL_ASK);
      int    digits = (int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);

      double newSL=curSL;

      if(type==POSITION_TYPE_BUY)
        {
         double profitPips=(bid-open)/g_pip;
         if(InpUseBreakEven && profitPips>=InpBreakEvenPips)
           {
            double be=open+InpBreakEvenLock*g_pip;
            if(be>newSL) newSL=be;
           }
         if(InpUseTrailing && profitPips>=InpTrailStartPips)
           {
            double tr=bid-InpTrailStepPips*g_pip;
            if(tr>newSL) newSL=tr;
           }
         newSL=NormalizeDouble(newSL,digits);
         if(newSL>curSL && newSL<bid)
            trade.PositionModify(ticket,newSL,curTP);
        }
      else if(type==POSITION_TYPE_SELL)
        {
         double profitPips=(open-ask)/g_pip;
         if(InpUseBreakEven && profitPips>=InpBreakEvenPips)
           {
            double be=open-InpBreakEvenLock*g_pip;
            if(curSL==0.0 || be<newSL) newSL=be;
           }
         if(InpUseTrailing && profitPips>=InpTrailStartPips)
           {
            double tr=ask+InpTrailStepPips*g_pip;
            if(curSL==0.0 || tr<newSL) newSL=tr;
           }
         newSL=NormalizeDouble(newSL,digits);
         if((curSL==0.0 || newSL<curSL) && newSL>ask)
            trade.PositionModify(ticket,newSL,curTP);
        }
     }
  }

//+------------------------------------------------------------------+
//| UI panel                                                         |
//+------------------------------------------------------------------+
void CreateButton(const string name,const int x,const int y,const int w,const int h,
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
   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,10);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
  }

void CreateLabel(const string name,const int x,const int y,const string text)
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
   double lot=CalcLot(InpStopLossPips);
   string txt=StringFormat("RiskGuard | %s | risk %.2f%% | lot %.2f | %s",
                           _Symbol,InpRiskPercent,lot,g_status);
   if(ObjectFind(0,LBL_INFO)>=0)
      ObjectSetString(0,LBL_INFO,OBJPROP_TEXT,txt);
  }

void BuildPanel()
  {
   int x=10,y=22;
   CreateLabel(LBL_INFO,x,y,"RiskGuard");
   y+=18;
   CreateButton(BTN_BUY,  x,    y,80,26,"BUY",  clrSeaGreen);
   CreateButton(BTN_SELL, x+86, y,80,26,"SELL", clrFireBrick);
   y+=30;
   CreateButton(BTN_CLOSE,x,    y,166,24,"CLOSE ALL",clrDimGray);
   UpdateInfo();
   ChartRedraw();
  }

void RemovePanel()
  {
   ObjectDelete(0,BTN_BUY);
   ObjectDelete(0,BTN_SELL);
   ObjectDelete(0,BTN_CLOSE);
   ObjectDelete(0,LBL_INFO);
  }

//+------------------------------------------------------------------+
//| Lifecycle                                                        |
//+------------------------------------------------------------------+
int OnInit()
  {
   g_pip=PipSize();
   if(g_pip<=0.0)
     { Print("RiskGuard: cannot resolve pip size."); return(INIT_FAILED); }

   RGLicenseResult lic=RGCheckLicense("risk-guard",InpLicenseKey,InpLicenseServer);
   g_licensed=lic.ok;
   g_status=lic.message;

   if(!g_licensed)
     {
      Comment("RiskGuard: license check failed -> ",lic.message,
              "\nTrading actions are disabled.");
      Print("RiskGuard license: ",lic.message);
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
   ManagePositions();
   UpdateInfo();
  }

void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)
  {
   if(id!=CHARTEVENT_OBJECT_CLICK) return;

   if(sparam==BTN_BUY)        OpenTrade(true);
   else if(sparam==BTN_SELL)  OpenTrade(false);
   else if(sparam==BTN_CLOSE) CloseAll();

   // release the button visual state
   if(sparam==BTN_BUY || sparam==BTN_SELL || sparam==BTN_CLOSE)
     {
      ObjectSetInteger(0,sparam,OBJPROP_STATE,false);
      ChartRedraw();
     }
  }
//+------------------------------------------------------------------+
