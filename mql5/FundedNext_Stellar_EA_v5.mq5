//+------------------------------------------------------------------+
//|                                  FundedNext_Stellar_EA_v5.mq5      |
//|   H4 Time-Series Momentum (TSMOM) + EMA200 trend filter           |
//|                                                                   |
//|   ★★ 検証結果: ❌ NO-GO。本番/funded 口座に載せないこと。 ★★     |
//|                                                                   |
//|   本番10年(USDJPY/GBPJPY/EURJPY)・厳格ハーネスで不採用:          |
//|     ・順列検定 p<0.05  : 1/3 のみ (USDJPY 0.78 / EURJPY 0.87 /   |
//|                          GBPJPY 0.015)。GBP以外はエッジ皆無。    |
//|     ・halt-OFF 真MaxDD : −35〜−150%(全ペアで -10% を大破)        |
//|     ・OOS / 年次WF も USDJPY/EURJPY で不合格。                    |
//|   スイープのプールPF1.18は相関JPYクロスを束ねた錯覚で、ペア別＋   |
//|   順列で消滅(GBPJPY単独の円トレンド・フロック)。詳細 docs/11。   |
//|                                                                   |
//|   本ファイルは「実装の参考(研究用)」として残す負の結果である。   |
//|   シミュレーションは将来/ライブ約定を保証しない。                |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "5.00"
#property strict

//==================================================================
// 入力パラメータ
//==================================================================
input group "=== シグナル(H4 時系列モメンタム) ==="
input int    InpLookback       = 40;     // モメンタム参照本数(終値 > Lookback本前で上昇)
input int    InpTrendEma       = 200;    // トレンドフィルタEMA期間(H4)
input int    InpAtrPeriod      = 14;     // ATR期間
input double InpAtrSLMult      = 2.0;    // SL = ATR × 係数
input double InpRR             = 3.0;    // リワード:リスク(TP距離 = RR×SL)
input int    InpHoldH4Bars     = 60;     // 最大保有(H4本数=約10営業日)で時間切れ決済
input double InpMinStopPips    = 6.0;    // 最小SL(pips)
input double InpMaxStopPips    = 400.0;  // 最大SL(pips)

input group "=== 資金/FundedNext ルール ==="
input double InpRiskPerTradePct = 0.25;  // 1取引リスク% (検証で真DD<-10%を満たす水準)
input double InpProfitTargetPct = 8.0;   // Phase1 利益目標(到達で停止)
input double InpEquityFloorDDPct= 10.0;  // 総合DD失格ライン(到達で停止)
input double InpDailyStopPct    = 5.0;   // 日次DD失格ライン(当日発注停止)
input int    InpMaxTradesPerDay = 3;     // 1日の最大新規
input double InpMaxDailyRiskPct = 0.75;  // 1日の合計リスク上限%
input double InpMinLot          = 0.01;
input double InpMaxSpreadPips   = 3.0;    // スプレッド上限(超過時は見送り)
input int    InpMagic           = 540005;

//==================================================================
// グローバル
//==================================================================
int    hAtr=INVALID_HANDLE, hEma=INVALID_HANDLE;
datetime g_lastBarTime=0;
double g_dayStartEquity=0.0;
datetime g_curDay=0;
int    g_tradesToday=0;
double g_riskUsedToday=0.0;
bool   g_dayBlocked=false;
bool   g_halted=false;
double g_initialBalance=0.0;

//==================================================================
// ユーティリティ
//==================================================================
double PipSize(){ return (StringFind(_Symbol,"JPY")>=0)?0.01:0.0001; }

int OnInit()
{
   hAtr = iATR(_Symbol, PERIOD_H4, InpAtrPeriod);
   hEma = iMA(_Symbol, PERIOD_H4, InpTrendEma, 0, MODE_EMA, PRICE_CLOSE);
   if(hAtr==INVALID_HANDLE || hEma==INVALID_HANDLE)
      return INIT_FAILED;
   g_initialBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   g_dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   PrintFormat("FundedNext Stellar EA v5 (TSMOM) init. Balance=%.2f  Lookback=%d EMA=%d RR=%.1f",
               g_initialBalance, InpLookback, InpTrendEma, InpRR);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason){ }

//==================================================================
// 日次リセット
//==================================================================
void UpdateDayState()
{
   datetime now = TimeCurrent();
   MqlDateTime dt; TimeToStruct(now, dt);
   datetime today = StringToTime(StringFormat("%04d.%02d.%02d", dt.year, dt.mon, dt.day));
   if(today != g_curDay)
   {
      g_curDay = today;
      g_dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
      g_tradesToday = 0;
      g_riskUsedToday = 0.0;
      g_dayBlocked = false;
   }
}

//==================================================================
// シグナル計算(確定足[1]で評価)
//   TSMOM: 終値[1] > 終値[1+Lookback] かつ 終値[1] > EMA[1] → 買い
//          終値[1] < 終値[1+Lookback] かつ 終値[1] < EMA[1] → 売り
//==================================================================
int ComputeSignal(double &atr_out, double &stop_pips_out)
{
   double atr[], ema[], close[];
   ArraySetAsSeries(atr,true); ArraySetAsSeries(ema,true); ArraySetAsSeries(close,true);

   int need = InpLookback + 2;          // close[1] と close[1+Lookback] を確保
   if(CopyBuffer(hAtr,0,0,3,atr)<3) return 0;
   if(CopyBuffer(hEma,0,0,3,ema)<3) return 0;
   if(CopyClose(_Symbol,PERIOD_H4,0,need,close)<need) return 0;
   if(atr[1]<=0.0) return 0;

   double c1   = close[1];              // 直近確定足
   double cN   = close[1+InpLookback];  // Lookback本前の確定足
   double emaV = ema[1];

   bool momUp = (c1 > cN);
   int sig = 0;
   if(momUp && c1 > emaV)        sig = 1;
   else if(!momUp && c1 < emaV)  sig = -1;

   atr_out = atr[1];
   stop_pips_out = (InpAtrSLMult*atr[1]) / PipSize();
   return sig;
}

//==================================================================
// 発注
//==================================================================
void TryEnter()
{
   if(g_halted) return;
   UpdateDayState();
   if(g_dayBlocked) return;

   // halt: 利益目標到達 or フロア割れ(到達で当チャレンジ終了→新規停止)
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq >= g_initialBalance*(1+InpProfitTargetPct/100.0)){ g_halted=true; Print("v5: profit target reached, halt."); return; }
   if(eq <= g_initialBalance*(1-InpEquityFloorDDPct/100.0)){ g_halted=true; Print("v5: equity floor breached, halt."); return; }

   // 日次DDガード(当日 -DailyStop% で当日発注停止)
   if(eq - g_dayStartEquity <= -g_initialBalance*InpDailyStopPct/100.0){ g_dayBlocked=true; return; }

   // スプレッド確認
   long spr = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   double spreadPips = (double)spr * _Point / PipSize();
   if(spreadPips > InpMaxSpreadPips) return;

   double atrTmp=0.0, stopPips=0.0;
   int sig = ComputeSignal(atrTmp, stopPips);
   if(sig==0) return;
   if(stopPips < InpMinStopPips || stopPips > InpMaxStopPips) return;

   if(g_tradesToday >= InpMaxTradesPerDay) return;
   if(g_riskUsedToday + InpRiskPerTradePct > InpMaxDailyRiskPct + 1e-9) return;

   // 1銘柄1ポジ
   if(PositionSelect(_Symbol)) return;

   double sd_price = InpAtrSLMult*atrTmp;
   double riskUsd  = g_initialBalance*InpRiskPerTradePct/100.0;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double entry = (sig>0)?ask:bid;
   double sl = (sig>0)?entry - sd_price : entry + sd_price;
   double tp = (sig>0)?entry + InpRR*sd_price : entry - InpRR*sd_price;

   // ロット計算(リスク$ / SL距離$)
   double tickVal = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize= SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double lossPerLot = (tickSize>0)? (sd_price/tickSize)*tickVal : 0.0;
   double lots = (lossPerLot>0)? riskUsd/lossPerLot : InpMinLot;
   double minLot=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double maxLot=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double lotStep=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(lotStep<=0) lotStep=0.01;
   lots = MathFloor(lots/lotStep)*lotStep;
   lots = MathMax(minLot, MathMin(maxLot, lots));

   MqlTradeRequest req; MqlTradeResult res;
   ZeroMemory(req); ZeroMemory(res);
   req.action=TRADE_ACTION_DEAL; req.symbol=_Symbol; req.volume=lots;
   req.type=(sig>0)?ORDER_TYPE_BUY:ORDER_TYPE_SELL;
   req.price=entry; req.sl=sl; req.tp=tp;
   req.deviation=10; req.magic=InpMagic; req.type_filling=ORDER_FILLING_FOK;
   req.comment="v5_tsmom";
   bool ok=OrderSend(req,res);
   if(ok && (res.retcode==TRADE_RETCODE_DONE||res.retcode==TRADE_RETCODE_PLACED)){
      g_tradesToday++; g_riskUsedToday+=InpRiskPerTradePct;
   } else {
      PrintFormat("v5: OrderSend failed retcode=%d", res.retcode);
   }
}

//==================================================================
// 時間切れクローズ(HoldH4Bars 経過で成行決済)
//==================================================================
void ManageOpenPosition()
{
   if(!PositionSelect(_Symbol)) return;
   if(PositionGetInteger(POSITION_MAGIC)!=InpMagic) return;
   datetime opent=(datetime)PositionGetInteger(POSITION_TIME);
   int barsHeld=iBarShift(_Symbol,PERIOD_H4,opent,false);
   if(barsHeld>=InpHoldH4Bars){
      double vol=PositionGetDouble(POSITION_VOLUME);
      long ptype=PositionGetInteger(POSITION_TYPE);
      MqlTradeRequest req; MqlTradeResult res; ZeroMemory(req);ZeroMemory(res);
      req.action=TRADE_ACTION_DEAL; req.symbol=_Symbol; req.volume=vol;
      req.type=(ptype==POSITION_TYPE_BUY)?ORDER_TYPE_SELL:ORDER_TYPE_BUY;
      req.price=(ptype==POSITION_TYPE_BUY)?SymbolInfoDouble(_Symbol,SYMBOL_BID):SymbolInfoDouble(_Symbol,SYMBOL_ASK);
      req.deviation=10; req.magic=InpMagic; req.type_filling=ORDER_FILLING_FOK;
      OrderSend(req,res);
   }
}

//==================================================================
// メインループ(新規H4バーで評価)
//==================================================================
void OnTick()
{
   ManageOpenPosition();
   datetime t=iTime(_Symbol,PERIOD_H4,0);
   if(t==g_lastBarTime) return;     // 新規H4バーのみ発注判定(確定足ベース)
   g_lastBarTime=t;
   TryEnter();
}
//+------------------------------------------------------------------+
//| NOTE / なぜ不採用か(誠実な記録):                                |
//|  ・USDJPY/EURJPY は順列検定でエッジ皆無(p=0.78/0.87)。GBPJPY    |
//|    のみ p=0.015 だが、単一JPYペアの円トレンド依存フロック。     |
//|  ・全ペアで halt-OFF 真MaxDD が −10% を大破(−35〜−150%)。       |
//|  ・スイープのプール優位は相関JPYクロスを束ねた錯覚だった。      |
//|  ・スプレッドは固定近似(実bid/ask・スワップ未計上)。           |
//|  → 本番投入不可。前進検証の対象にもしない(根拠不足)。docs/11。  |
//+------------------------------------------------------------------+
