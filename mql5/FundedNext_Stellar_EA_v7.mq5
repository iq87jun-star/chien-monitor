//+------------------------------------------------------------------+
//|                                  FundedNext_Stellar_EA_v7.mq5      |
//|   Monday seasonality — MULTI-SHOT portfolio (3 JPY crosses x       |
//|   morning session hours), risk-budgeted. LONG only, time-exit.    |
//|                                                                   |
//|   v6 と同じ「本物の」エッジ(週明け月曜のJPYクロス・ドリフト、     |
//|   04-10UTC帯)を使うが、運用を作り直した。v6の失格原因はエッジ不足 |
//|   ではなく【リスク配分】だった(docs/13: 3ペア×各0.40%同時で合算  |
//|   DD 11.81% > 10% → Phase1 FAIL)。                                |
//|                                                                   |
//|   v7 の設計(=「数を打って成績を上げる」の工学的実装, docs/16):    |
//|     ・1エッジを細かくサンプリング: 月曜 04/06/08/10 UTC の4時刻 ×  |
//|       3ペア = 週12ショット(週1→週12)。タイミング/ペア集中を平準化。|
//|     ・★総リスク予算で建てる: 1ショットのリスク = InpWeeklyRiskPct  |
//|       / InpShotsPerWeek。ショットを増やしても合算エクスポージャは   |
//|       一定 → 合算DDが器(FundedNext)に収まる。                     |
//|     ・FundedNextは時間無制限 → 低DDの正エッジは『+8%到達 vs -10%   |
//|       失格』競争に単調有利。                                       |
//|                                                                   |
//|   検証(research/v7_portfolio_multishot.py, committed 2.8年H1,      |
//|   ブロック・ブートストラップMC 4000パス, 往復2pip):                |
//|     ・ショット間相関: 同ペア別時刻0.78 / ペア間0.61(<1 → 分散効く)|
//|     ・週次シャープ: 単一ショット平均1.29 → 12ショット 1.56(改善)  |
//|     ・同レバ(1.5)比較: v6(3shot) net16.7%/worstDD-6.6%/SR1.24      |
//|                       → v7(12shot) net19.3%/worstDD-4.9%/SR1.56    |
//|       = リターン増 かつ DD減(本物の分散)。                        |
//|     ・採用予算でPhase1合格率~100%(失格0.1%), Phase1+2連続~100%。   |
//|       ※ MCは標本のブートストラップ。エッジ持続が前提。10年追認は    |
//|         research/colab_v7_multishot_validation.py で。            |
//|                                                                   |
//|   ★ 運用: 3ペア(EURJPY/GBPJPY/USDJPY)それぞれのチャートに1つずつ   |
//|     アタッチ。各インスタンスは自分のシンボルだけ扱い、4時刻で建てる。|
//|     InpWeeklyRiskPct はポートフォリオ全体の週次リスク(全インスタンス|
//|     で同じ値にする)。各ショットのサイズ = それを総ショット数で割る。|
//|   ★ デモ/少額で前進検証してから funded へ。詳細は docs/16。        |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "7.00"
#property strict
#property description "FundedNext Stellar v7 — Monday seasonality multi-shot portfolio (JPY crosses x morning hours, risk-budgeted, LONG only, time-exit)"

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>
#include <Trade/SymbolInfo.mqh>

//==================================================================
input group "=== Challenge Rules (FundedNext Stellar 2-Step) ==="
input double InpInitialBalance   = 100000.0;
input double InpProfitTargetPct  = 8.0;     // 到達で新規停止
input double InpMaxLossLimitPct  = 10.0;    // 総合DD失格ライン(参考)

input group "=== Hard Guards (rule の内側で止める) ==="
input double InpDailyStopPct     = 4.0;     // 当日 -4% で当日停止(rule -5%の内側)
input double InpEquityFloorDDPct = 8.0;     // 総合 -8% で全停止(rule -10%の内側)
input bool   InpCloseAllOnGuard  = true;

input group "=== Multi-shot seasonality signal (UTC) ==="
input int    InpEntryWeekday     = 1;       // 1=Monday (MQL: 0=Sun..6=Sat)
input string InpEntryHoursUTC    = "4,6,8,10"; // ★複数時刻(検証帯04-10)。カンマ区切り。
input int    InpHoldHours        = 24;      // 各ショット保有=24h(翌日同時刻に時間決済)
input bool   InpLongOnly         = true;    // 本エッジは LONG のみ
input bool   InpSkipFirstWeek    = false;   // 月初第1週除外(検証で改善・任意)

input group "=== Risk budgeting (★多ショットの要) ==="
input double InpWeeklyRiskPct    = 1.50;    // ★ポートフォリオ週次リスク予算%(全インスタンス共通)
                                            //   採用=1.5(worstDD~-5%/net~19%)。保守なら0.75-1.0。
input int    InpShotsPerWeek     = 12;      // 総ショット数=ペア数(3)×時刻数(4)。予算をこれで割る。
input double InpMinLot           = 0.01;
input double InpMaxLot           = 5.0;

input group "=== Catastrophe stop (タイトSL厳禁: 広く置く) ==="
input int    InpAtrPeriodH1      = 24;      // H1×24 ≒ 日次ATR
input double InpCatastropheATR   = 2.5;     // SL = 2.5×ATR (検証でp維持の広さ)
input double InpMinStopPips      = 10.0;
input double InpMaxStopPips      = 400.0;

input group "=== Filters ==="
input double InpMaxSpreadPips    = 3.0;     // 超過は見送り(往復>3pipでエッジ弱る)
input bool   InpUseNewsFilter    = true;    // 高インパクトニュース回避
input int    InpNewsBeforeMin    = 30;
input int    InpNewsAfterMin     = 15;

input group "=== Execution ==="
input long   InpMagic            = 920570;  // v7
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

int      g_hours[];                 // パース済みエントリー時刻
datetime g_lastShotBar[];           // 各時刻ごとの二重発注防止(時間足キー)

//==================================================================
int ParseHours(const string csv)
{
   string parts[];
   int k = StringSplit(csv, ',', parts);
   if(k <= 0) return 0;
   ArrayResize(g_hours, k);
   ArrayResize(g_lastShotBar, k);
   int m = 0;
   for(int i = 0; i < k; i++)
   {
      string s = parts[i];
      StringTrimLeft(s); StringTrimRight(s);
      if(StringLen(s) == 0) continue;
      int h = (int)StringToInteger(s);
      if(h < 0 || h > 23) continue;
      g_hours[m] = h; g_lastShotBar[m] = 0; m++;
   }
   ArrayResize(g_hours, m);
   ArrayResize(g_lastShotBar, m);
   return m;
}

int OnInit()
{
   if(!sym.Name(_Symbol)){ Print("Symbol init failed"); return INIT_FAILED; }
   sym.RefreshRates();
   int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   if(digits==3 || digits==5) g_pip=point*10.0; else g_pip=point;

   hAtr=iATR(_Symbol,PERIOD_H1,InpAtrPeriodH1);
   if(hAtr==INVALID_HANDLE){ Print("ATR handle failed"); return INIT_FAILED; }

   if(ParseHours(InpEntryHoursUTC) <= 0){ Print("No valid entry hours parsed"); return INIT_FAILED; }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   ResetDay(TimeCurrent());
   string hrs=""; for(int i=0;i<ArraySize(g_hours);i++) hrs+=(string)g_hours[i]+(i+1<ArraySize(g_hours)?",":"");
   PrintFormat("[INIT v7] %s pip=%.5f wd%d hoursUTC=[%s] hold=%dh weeklyRisk=%.2f%% shots/wk=%d perShot=%.3f%%",
               _Symbol,g_pip,InpEntryWeekday,hrs,InpHoldHours,
               InpWeeklyRiskPct,InpShotsPerWeek,PerShotRiskPct());
   if(InpVerboseLog)
      Print("[NOTE] v7 = Monday multi-shot portfolio. 3ペアのチャートに各1つアタッチ。"
            "総リスク予算をショット数で割って建てる。USDJPY単体は弱いが分散用。デモ前進検証推奨。");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason){ if(hAtr!=INVALID_HANDLE) IndicatorRelease(hAtr); }

//==================================================================
double PerShotRiskPct()
{
   int n = InpShotsPerWeek > 0 ? InpShotsPerWeek : 1;
   return InpWeeklyRiskPct / n;          // ★総予算をショット数で割る = 合算エクスポージャ一定
}

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

//==================================================================
void OnTick()
{
   sym.RefreshRates();
   datetime now=TimeCurrent();
   datetime nowUtc=TimeGMT();        // ブローカー時刻に依存しないGMT

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

   // 時間決済は常に評価(ガード中でもクローズはする)
   ManageTimeExit();

   if(equity>=InpInitialBalance*(1.0+InpProfitTargetPct/100.0)) return; // 目標到達で新規停止
   if(g_dayBlocked) return;

   // ===== エントリー判定(UTC 曜日 × 複数時刻) =====
   MqlDateTime u; TimeToStruct(nowUtc,u);
   if(u.day_of_week!=InpEntryWeekday) return;

   if(InpSkipFirstWeek){ int wom=(u.day-1)/7+1; if(wom==1) return; }

   int slot=-1;
   for(int i=0;i<ArraySize(g_hours);i++) if(u.hour==g_hours[i]){ slot=i; break; }
   if(slot<0) return;                                    // 今は対象時刻でない

   datetime hourBar=nowUtc - (nowUtc % 3600);
   if(hourBar==g_lastShotBar[slot]) return;              // この時刻スロットは発注済み

   if(SpreadPips()>InpMaxSpreadPips){ if(InpVerboseLog) Print("[SKIP] spread高"); return; }
   if(InpUseNewsFilter && IsNewsBlackout(nowUtc)){ if(InpVerboseLog) Print("[SKIP] news"); return; }

   g_lastShotBar[slot]=hourBar;
   EnterLong(g_hours[slot]);
}

//==================================================================
void EnterLong(int hourTag)
{
   double atr[1];
   if(CopyBuffer(hAtr,0,1,1,atr)<1) return;
   double atrPrice=atr[0];
   if(atrPrice<=0) return;

   double stopDist=InpCatastropheATR*atrPrice;
   double stopPips=stopDist/g_pip;
   if(stopPips<InpMinStopPips){ stopPips=InpMinStopPips; stopDist=stopPips*g_pip; }
   if(stopPips>InpMaxStopPips){ if(InpVerboseLog) Print("[SKIP] stop広すぎ"); return; }

   double entry=sym.Ask();
   double sl=entry-stopDist;          // LONGのみ・災害用
   double tp=0.0;                     // TPなし(時間決済が本質)

   double lots=CalcLots(stopDist);
   if(lots<InpMinLot){ if(InpVerboseLog) Print("[SKIP] lots<min"); return; }

   int d=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   sl=NormalizeDouble(sl,d);
   long stopLevel=SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL);
   double minDist=stopLevel*SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   if(MathAbs(entry-sl)<minDist){ if(InpVerboseLog) Print("[SKIP] SL broker stop内"); return; }

   string cmt=StringFormat("FNStellarV7_Mon_h%d",hourTag);
   if(trade.Buy(lots,_Symbol,0.0,sl,tp,cmt))
      PrintFormat("[ENTRY v7] LONG %s h%dUTC lots=%.2f entry~%.5f SL=%.5f stopPips=%.1f perShot=%.3f%%",
                  _Symbol,hourTag,lots,entry,sl,stopPips,PerShotRiskPct());
   else
      PrintFormat("[ENTRY FAIL] ret=%d %s",trade.ResultRetcode(),trade.ResultRetcodeDescription());
}

//==================================================================
double CalcLots(double stopDist)
{
   double riskMoney=InpInitialBalance*(PerShotRiskPct()/100.0);   // ★ショット当たり=週次予算/ショット数
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
// 時間決済: 各ポジションを建玉から InpHoldHours 経過で成行クローズ。
// 複数ショット(別時刻に建てた別ポジション)を個別に管理する。
void ManageTimeExit()
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Symbol()!=_Symbol || posinfo.Magic()!=InpMagic) continue;
      datetime opened=(datetime)posinfo.Time();
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
//|  ・3ペアは全てJPYクロスで相関0.6-0.78(同ペア別時刻0.78/ペア間0.61)|
//|    独立ではない。だが相関<1ゆえ多ショットで分散は実効(SR1.29→1.56)|
//|    『円の週明けシーズナリティ』1現象を細かくサンプリングしている。  |
//|  ・スワップ: 各ショットを翌日まで1泊。JPYクロスLONGスワップ符号は   |
//|    金利局面・ブローカーで変わる(docs/13で-1pip/泊だと半減)。要確認。|
//|  ・MC合格率~100%は『committed 2.8年標本のブロック・ブートストラップ|
//|    かつエッジ持続が前提』。将来のレジーム変化(日銀金利・裁定減衰)は|
//|    保証外。10年追認は research/colab_v7_multishot_validation.py。  |
//|  ・TimeGMT()とブローカー・サーバ時刻の乖離に注意(04-10帯なら許容)。|
//|  ・低頻度(週12ショット・各小サイズ)。+8%到達は中央値~58週(MC)。   |
//|    プロップの時間無制限が前提。急いで高リスク化すると失格。        |
//+------------------------------------------------------------------+
