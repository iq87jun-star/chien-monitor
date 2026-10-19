//+------------------------------------------------------------------+
//|                                  FundedNext_Stellar_EA_v6.mq5      |
//|   Monday seasonality (week-open JPY-cross drift) — LONG only       |
//|                                                                   |
//|   本番10年(USDJPY/EURJPY/GBPJPY)で、本プロジェクト初めて全フィルタ |
//|   を通過したエッジを実装する。価格指標の方向予測(v1〜v5=全滅)では |
//|   なく『曜日シーズナリティ(週明けのリスクオン/円キャリー需要)』。  |
//|                                                                   |
//|   検証サマリ(research/seasonality_monday.py / 往復~2pipコスト後):  |
//|     ・採用: 月曜 08:00 UTC に LONG、24時間後(火曜同時刻)に時間決済 |
//|     ・全期間 純益+27.6% 勝率58% maxDD -4.6% 順列p=0.012           |
//|     ・OOS(後半5年) 純益+24.2% maxDD -2.2% (=減衰せず増強)         |
//|     ・曜日プラセボ: 月曜だけ突出(火p=.15 水.54 木.77 金.96)       |
//|     ・全年ジャックナイフ: どの年を除いてもp<=0.01                 |
//|     ・時刻プラセボ: 04-10UTC帯で安定(13UTCで消滅)                 |
//|     ・直近2023-26: 4年連続プラス / ボラ低高どちらも+              |
//|     ・★タイトSLはエッジを破壊(SL=1ATRでp=0.73)。時間決済が本質。  |
//|       → SLは災害用に2.5ATRと広く置く(検証でp=0.012維持)。         |
//|     ・複利は低リスク必須(高レバは即-10%失格)。RiskPerTrade<=0.5%。 |
//|                                                                   |
//|   ★ 必ず H4 ではなく任意TFで可。判定は UTC 時刻で行う。           |
//|   ★ デモ/少額で前進検証してから funded 口座へ。シミュレーションは |
//|     将来/ライブ約定を保証しない。詳細は docs/12。                  |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "6.00"
#property strict
#property description "FundedNext Stellar v6 — Monday week-open seasonality (JPY crosses, LONG only, 24h time-exit)"

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>
#include <Trade/SymbolInfo.mqh>

//==================================================================
input group "=== Challenge Rules (FundedNext Stellar 2-Step) ==="
input double InpInitialBalance   = 100000.0;
input double InpProfitTargetPct  = 8.0;     // 到達で新規停止
input double InpMaxLossLimitPct  = 10.0;    // 総合DD失格ライン(参考)

input group "=== Hard Guards (rule のさらに内側で止める) ==="
input double InpDailyStopPct     = 4.0;     // 当日 -4% で当日停止(rule -5%の内側)
input double InpEquityFloorDDPct = 8.0;     // 総合 -8% で全停止(rule -10%の内側)
input bool   InpCloseAllOnGuard  = true;

input group "=== Seasonality signal (UTC) ==="
input int    InpEntryWeekday     = 1;       // 1=Monday (MQL: 0=Sun..6=Sat)
input int    InpEntryHourUTC     = 8;       // 検証最良帯 04-10。既定=8(最低DD)
input int    InpHoldHours        = 24;      // 保有=24h(翌日同時刻に時間決済)
input bool   InpLongOnly         = true;    // 本エッジは LONG のみ(SHORTは減衰)
input bool   InpSkipFirstWeek    = false;   // 月初第1週(雇用統計週)を除外(検証で改善)

input group "=== Risk & Sizing (低リスク必須) ==="
input double InpRiskPerTradePct  = 0.40;    // 1取引リスク% (<=0.5 推奨。高いと即失格)
input double InpMaxOpenPositions = 3;       // 3ペア同時=最大3
input double InpMinLot           = 0.01;
input double InpMaxLot           = 5.0;

input group "=== Catastrophe stop (タイトSL厳禁: 広く置く) ==="
input int    InpAtrPeriodH1      = 24;      // H1×24 ≒ 日次ATR
input double InpCatastropheATR   = 2.5;     // SL = 2.5×ATR (検証でp維持の広さ)
input double InpMinStopPips      = 10.0;
input double InpMaxStopPips      = 400.0;

input group "=== Filters ==="
input double InpMaxSpreadPips    = 3.0;     // 超過時は見送り(コスト感応: 往復>3pipで弱る)
input bool   InpUseNewsFilter    = true;    // 高インパクトニュース回避(検証で有益)
input int    InpNewsBeforeMin    = 30;
input int    InpNewsAfterMin     = 15;

input group "=== Execution ==="
input long   InpMagic            = 920560;  // v6
input int    InpSlippagePoints   = 20;
input bool   InpVerboseLog       = true;

//==================================================================
CTrade        trade;
CPositionInfo posinfo;
CSymbolInfo   sym;

int      hAtr = INVALID_HANDLE;
double   g_pip = 0.0;
double   g_dayStartEquity = 0.0;
datetime g_curDay = 0;
bool     g_eaHalted = false;
bool     g_dayBlocked = false;
datetime g_lastEntryBar = 0;     // 同一エントリー足の二重発注防止

//==================================================================
int OnInit()
{
   if(!sym.Name(_Symbol)){ Print("Symbol init failed"); return INIT_FAILED; }
   sym.RefreshRates();
   int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   if(digits==3 || digits==5) g_pip=point*10.0; else g_pip=point;

   hAtr=iATR(_Symbol,PERIOD_H1,InpAtrPeriodH1);
   if(hAtr==INVALID_HANDLE){ Print("ATR handle failed"); return INIT_FAILED; }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   ResetDay(TimeCurrent());
   PrintFormat("[INIT v6] %s pip=%.5f entry=wd%d %02d:00UTC hold=%dh longOnly=%s risk=%.2f%%",
               _Symbol,g_pip,InpEntryWeekday,InpEntryHourUTC,InpHoldHours,
               (InpLongOnly?"true":"false"),InpRiskPerTradePct);
   if(InpVerboseLog)
      Print("[NOTE] v6 = Monday week-open seasonality. デモ前進検証推奨。USDJPYは単体非有意、主力はEUR/GBPJPY。");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason){ if(hAtr!=INVALID_HANDLE) IndicatorRelease(hAtr); }

//==================================================================
datetime DayStart(datetime t){ MqlDateTime s; TimeToStruct(t,s); s.hour=0;s.min=0;s.sec=0; return StructToTime(s); }

void ResetDay(datetime t)
{
   g_curDay=DayStart(t);
   g_dayStartEquity=AccountInfoDouble(ACCOUNT_EQUITY);
   g_dayBlocked=false;
}

double SpreadPips(){ return (sym.Ask()-sym.Bid())/g_pip; }

int CountOpenByMagic()
{
   int n=0;
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()==InpMagic) n++;
   }
   return n;
}

bool HasPositionThisSymbol()
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Symbol()==_Symbol && posinfo.Magic()==InpMagic) return true;
   }
   return false;
}

//==================================================================
void OnTick()
{
   sym.RefreshRates();
   datetime now=TimeCurrent();   // サーバ時刻。多くのFXブローカーはUTC近傍だが、
                                 // 厳密にはサーバ-UTCオフセットを確認すること(下記 UtcNow)。
   datetime nowUtc=TimeGMT();    // ターミナルのGMT(UTC)時刻を使用 → ブローカー時刻に依存しない

   if(DayStart(now)!=g_curDay) ResetDay(now);

   double equity=AccountInfoDouble(ACCOUNT_EQUITY);

   // ===== ハードガード =====
   double floorEq=InpInitialBalance*(1.0-InpEquityFloorDDPct/100.0);
   if(equity<=floorEq && !g_eaHalted)
   {
      g_eaHalted=true;
      if(InpCloseAllOnGuard) CloseAllByMagic("EQUITY_FLOOR");
      PrintFormat("[HALT] equity %.2f <= floor %.2f",equity,floorEq);
   }
   if(g_eaHalted){ if(InpCloseAllOnGuard) CloseAllByMagic("HALTED"); return; }

   double dayPnL=equity-g_dayStartEquity;
   if(dayPnL<=-InpInitialBalance*InpDailyStopPct/100.0 && !g_dayBlocked)
   {
      g_dayBlocked=true;
      if(InpCloseAllOnGuard) CloseAllByMagic("DAILY_STOP");
      PrintFormat("[DAILY STOP] dayPnL %.2f",dayPnL);
   }

   // 時間決済(保有>=InpHoldHours)は常に評価(ガード中でもクローズはする)
   ManageTimeExit(nowUtc);

   // 利益目標到達で新規停止
   if(equity>=InpInitialBalance*(1.0+InpProfitTargetPct/100.0)) return;
   if(g_dayBlocked) return;

   // ===== エントリー判定(UTC 曜日×時刻) =====
   MqlDateTime u; TimeToStruct(nowUtc,u);
   if(u.day_of_week!=InpEntryWeekday) return;
   if(u.hour!=InpEntryHourUTC) return;

   // この時間足での二重発注防止(同じ時)
   datetime hourBar=nowUtc - (nowUtc % 3600);
   if(hourBar==g_lastEntryBar) return;

   if(InpSkipFirstWeek)
   {
      int weekOfMonth=(u.day-1)/7+1;
      if(weekOfMonth==1) return;
   }

   if(HasPositionThisSymbol()) return;
   if(CountOpenByMagic()>=(int)InpMaxOpenPositions) return;
   if(SpreadPips()>InpMaxSpreadPips){ if(InpVerboseLog) Print("[SKIP] spread高"); return; }
   if(InpUseNewsFilter && IsNewsBlackout(nowUtc)){ if(InpVerboseLog) Print("[SKIP] news"); return; }

   g_lastEntryBar=hourBar;
   EnterLong();
}

//==================================================================
void EnterLong()
{
   double atr[1];
   if(CopyBuffer(hAtr,0,1,1,atr)<1) return;
   double atrPrice=atr[0];
   if(atrPrice<=0) return;

   double stopDist=InpCatastropheATR*atrPrice;     // 広い災害用SL
   double stopPips=stopDist/g_pip;
   if(stopPips<InpMinStopPips) stopPips=InpMinStopPips, stopDist=stopPips*g_pip;
   if(stopPips>InpMaxStopPips){ if(InpVerboseLog) Print("[SKIP] stop広すぎ"); return; }

   double entry=sym.Ask();
   double sl=entry-stopDist;                        // LONGのみ
   double tp=0.0;                                   // TPは置かない(時間決済が本質)

   double lots=CalcLots(stopDist);
   if(lots<InpMinLot){ if(InpVerboseLog) Print("[SKIP] lots<min"); return; }

   int d=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   sl=NormalizeDouble(sl,d);
   long stopLevel=SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL);
   double minDist=stopLevel*SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   if(MathAbs(entry-sl)<minDist){ if(InpVerboseLog) Print("[SKIP] SL broker stop内"); return; }

   if(trade.Buy(lots,_Symbol,0.0,sl,tp,"FNStellarV6_Mon"))
      PrintFormat("[ENTRY v6] LONG %s lots=%.2f entry~%.5f SL=%.5f stopPips=%.1f",
                  _Symbol,lots,entry,sl,stopPips);
   else
      PrintFormat("[ENTRY FAIL] ret=%d %s",trade.ResultRetcode(),trade.ResultRetcodeDescription());
}

//==================================================================
double CalcLots(double stopDist)
{
   double riskMoney=InpInitialBalance*(InpRiskPerTradePct/100.0);  // 初期残高基準(定額R)
   double tickValue=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double tickSize =SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(tickSize<=0 || tickValue<=0) return 0.0;
   double lossPerLot=(stopDist/tickSize)*tickValue;
   if(lossPerLot<=0) return 0.0;
   double lots=riskMoney/lossPerLot;
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   double vmin=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double vmax=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   if(step>0) lots=MathFloor(lots/step)*step;
   lots=MathMin(lots,MathMin(InpMaxLot,vmax));
   if(lots<MathMax(InpMinLot,vmin)) return 0.0;
   return lots;
}

//==================================================================
// 時間決済: ポジション保有が InpHoldHours 以上で成行クローズ
void ManageTimeExit(datetime nowUtc)
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Symbol()!=_Symbol || posinfo.Magic()!=InpMagic) continue;
      datetime opened=(datetime)posinfo.Time();
      // 経過はサーバ時刻ベースのTimeCurrentで計算(open も同じ系)
      int heldSec=(int)(TimeCurrent()-opened);
      if(heldSec>=InpHoldHours*3600)
      {
         if(trade.PositionClose(tk))
            { if(InpVerboseLog) PrintFormat("[TIME EXIT] %s ticket=%I64u held=%dh",_Symbol,tk,heldSec/3600); }
         else
            PrintFormat("[CLOSE FAIL] ret=%d %s",trade.ResultRetcode(),trade.ResultRetcodeDescription());
      }
   }
}

void CloseAllByMagic(string why)
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Symbol()!=_Symbol || posinfo.Magic()!=InpMagic) continue;
      if(trade.PositionClose(tk)) { if(InpVerboseLog) PrintFormat("[CLOSE %s] %I64u",why,tk); }
   }
}

//==================================================================
bool IsNewsBlackout(datetime nowUtc)
{
   string base =SymbolInfoString(_Symbol,SYMBOL_CURRENCY_BASE);
   string quote=SymbolInfoString(_Symbol,SYMBOL_CURRENCY_PROFIT);
   if(CalendarHit(base,nowUtc)) return true;
   if(CalendarHit(quote,nowUtc)) return true;
   return false;
}

bool CalendarHit(string ccy,datetime nowUtc)
{
   MqlCalendarValue vals[];
   datetime from=nowUtc-InpNewsAfterMin*60;
   datetime to  =nowUtc+InpNewsBeforeMin*60;
   int n=CalendarValueHistory(vals,from,to,NULL,ccy);
   if(n<=0) return false;
   for(int i=0;i<n;i++)
   {
      MqlCalendarEvent ev;
      if(!CalendarEventById(vals[i].event_id,ev)) continue;
      if(ev.importance==CALENDAR_IMPORTANCE_HIGH) return true;
   }
   return false;
}
//+------------------------------------------------------------------+
//| 残存リスク(誠実な記録):                                          |
//|  ・3ペアは全てJPYクロスで相関0.6-0.76。独立3証拠ではなく『円の   |
//|    週明けシーズナリティ』1現象。USDJPY単体は順列p=0.106(非有意)。 |
//|    主力は EUR/GBPJPY。分散目的でUSDJPYも併用するが過信しない。    |
//|  ・スワップ: 月曜LONGを火曜まで1泊。JPYクロスLONGのスワップ符号は |
//|    ブローカー・金利局面で変わる(日銀利上げで縮小)。要確認。      |
//|  ・TimeGMT()はターミナルのGMT。ブローカーのサーバ時刻と乖離する   |
//|    場合、エントリー時刻がずれる。検証(04-10UTCで安定)の範囲内なら |
//|    多少のズレは許容だが、デモで実エントリー時刻を必ず確認。       |
//|  ・低頻度(約50回/年・ペア)。+8%到達は数ヶ月〜年単位。プロップの   |
//|    時間無制限が前提。収益を急ぎ高リスクにすると即-10%失格。       |
//+------------------------------------------------------------------+
