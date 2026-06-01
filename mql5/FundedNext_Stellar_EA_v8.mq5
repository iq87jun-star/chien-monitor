//+------------------------------------------------------------------+
//|                                  FundedNext_Stellar_EA_v8.mq5      |
//|   SATELLITE strategy #2 — USDCHF Thursday-PM SHORT (CHF-up/USD-    |
//|   down late-week drift). Risk-budgeted multi-shot, time-exit.     |
//|                                                                   |
//|   ★これは v7 とは【別ロジック】の2本目(衛星)。v7=円/月曜/LONG に  |
//|     対し、v8=USDCHF/木曜午後/SHORT。両者の相関は 0.06(ほぼ独立)で、|
//|     合算すると円単独の最大DD -1.8% が -1.1% に下がる(分散効果)。   |
//|                                                                   |
//|   ★★ 正直なグレード = LEAD(本物のエッジ未確定)。v7(CORE)より明確に|
//|     弱い。committed 2.8年H1・往復2pip での実測(research/           |
//|     edge2_candidates.py / edge2_chf_lateweek.py, 全数値JSON検証):  |
//|       ・木曜午後SHORTバスケット: 純益+5.6% 勝率52% maxDD-3.1% n=146 |
//|       ・曜日プラセボ: 木曜だけ+5.6%、他は全てマイナス(Mon-4.0…)    |
//|         → 単なるドル安トレンドではない(曜日特異性あり=良い兆候)   |
//|       ・時刻局在: 午後12-20が+、午前6-10は- (帯で出る)            |
//|       ・★順列 p=0.136(>0.05, 有意未達) ← ここが弱い               |
//|       ・★ジャックナイフ max_p=0.483(ある年除外で消失=年依存疑い)  |
//|       ・コスト感応: 1pip+7.4 / 2+5.6 / 3+3.8 / 4+2.0%(4pipまで+)   |
//|       ・円月曜との相関 0.06(独立)/ 合算 純益+8.9% maxDD-1.1%      |
//|       ・Bonferroni 非生存。OOS p=0.061。                          |
//|                                                                   |
//|   ⇒ 結論: 「円月曜と無相関で曜日/時刻に局在する正の期待値」だが、    |
//|     統計的有意性は弱く、年依存の疑いがある。よって【極小サイズの    |
//|     衛星】に限定し、10年H1追認(research/colab_edge2_chf_           |
//|     validation.py)とデモ前進検証を通るまで本気の資金は置かない。   |
//|     v7 が主力(core)、v8 は分散用の補助(satellite)。            |
//|                                                                   |
//|   ★★ 警告(docs/18): v8は committed 2.8年でしか検証していない。     |
//|     v7は10年実データで「2.8年のmaxDDは約1/3に過小評価」と判明した。 |
//|     v8も同じ罠が、LEADゆえ更に深刻に当てはまる。10年実データで       |
//|     曜日プラセボ・p・JK・10年maxDDを再測するまで本資金は置かない。   |
//|     新既定の極小予算0.40%も10年で要再測(楽観側の可能性大)。       |
//|                                                                   |
//|   ★ 運用: USDCHF チャートに1つアタッチ。木曜 12/14/16/18 UTC に     |
//|     SHORT、各24h時間決済。サイズは週次リスク予算/ショット数で極小。 |
//|   ★ デモ前進検証必須。詳細は docs/17。シミュレーションは将来を保証  |
//|     しない。                                                      |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "8.00"
#property strict
#property description "FundedNext Stellar v8 SATELLITE — USDCHF Thursday-PM SHORT (LEAD grade, diversifier for v7), risk-budgeted, time-exit"

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>
#include <Trade/SymbolInfo.mqh>

//==================================================================
input group "=== Challenge Rules (FundedNext Stellar 2-Step) ==="
input double InpInitialBalance   = 100000.0;
input double InpProfitTargetPct  = 8.0;
input double InpMaxLossLimitPct  = 10.0;

input group "=== Hard Guards ==="
input double InpDailyStopPct     = 4.0;
input double InpEquityFloorDDPct = 8.0;
input bool   InpCloseAllOnGuard  = true;

input group "=== Satellite signal #2 (USDCHF Thu-PM SHORT, UTC) ==="
input int    InpEntryWeekday     = 4;          // 4=Thursday (MQL: 0=Sun..6=Sat)
input string InpEntryHoursUTC    = "12,14,16,18"; // 午後帯(検証で+ p集中)
input bool   InpShortSide        = true;       // ★SHORT(CHF高/USD安)。v7と逆方向
input int    InpHoldHours        = 24;         // 各ショット24h時間決済
input bool   InpSkipFirstWeek    = false;

input group "=== Risk budgeting (★衛星=極小サイズ) ==="
input double InpWeeklyRiskPct    = 0.40;       // ★衛星は極小予算(v7主力は0.60)。LEAD&10年未追認ゆえ控えめ。
input int    InpShotsPerWeek     = 4;          // USDCHF×4時刻。予算をこれで割る。
input double InpMinLot           = 0.01;
input double InpMaxLot           = 5.0;

input group "=== Catastrophe stop (タイトSL厳禁: 広く置く) ==="
input int    InpAtrPeriodH1      = 24;
input double InpCatastropheATR   = 2.5;
input double InpMinStopPips      = 10.0;
input double InpMaxStopPips      = 400.0;

input group "=== Filters ==="
input double InpMaxSpreadPips    = 3.0;
input bool   InpUseNewsFilter    = true;
input int    InpNewsBeforeMin    = 30;
input int    InpNewsAfterMin     = 15;

input group "=== Execution ==="
input long   InpMagic            = 920580;     // v8(v6=...560, v7=...570 と別)
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

int      g_hours[];
datetime g_lastShotBar[];

//==================================================================
int ParseHours(const string csv)
{
   string parts[];
   int k = StringSplit(csv, ',', parts);
   if(k <= 0) return 0;
   ArrayResize(g_hours, k); ArrayResize(g_lastShotBar, k);
   int m = 0;
   for(int i = 0; i < k; i++)
   {
      string s = parts[i]; StringTrimLeft(s); StringTrimRight(s);
      if(StringLen(s) == 0) continue;
      int h = (int)StringToInteger(s);
      if(h < 0 || h > 23) continue;
      g_hours[m] = h; g_lastShotBar[m] = 0; m++;
   }
   ArrayResize(g_hours, m); ArrayResize(g_lastShotBar, m);
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
   if(ParseHours(InpEntryHoursUTC) <= 0){ Print("No valid entry hours"); return INIT_FAILED; }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   ResetDay(TimeCurrent());
   string hrs=""; for(int i=0;i<ArraySize(g_hours);i++) hrs+=(string)g_hours[i]+(i+1<ArraySize(g_hours)?",":"");
   PrintFormat("[INIT v8 SATELLITE] %s pip=%.5f wd%d hoursUTC=[%s] side=%s hold=%dh weeklyRisk=%.2f%% shots=%d perShot=%.3f%%",
               _Symbol,g_pip,InpEntryWeekday,hrs,(InpShortSide?"SHORT":"LONG"),InpHoldHours,
               InpWeeklyRiskPct,InpShotsPerWeek,PerShotRiskPct());
   if(InpVerboseLog)
   {
      Print("[NOTE] v8 = USDCHF Thursday-PM SHORT (LEAD grade, p=0.136). v7の分散用衛星。");
      Print("[WARN] 統計的有意性は弱い(JK年依存疑い)。極小サイズ・10年追認・デモ前進検証まで本資金禁止。");
      if(_Symbol!="USDCHF" && StringFind(_Symbol,"USDCHF")<0)
         Print("[WARN] このEAはUSDCHF前提。別シンボルでの挙動は未検証。");
   }
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason){ if(hAtr!=INVALID_HANDLE) IndicatorRelease(hAtr); }

//==================================================================
double PerShotRiskPct(){ int n=InpShotsPerWeek>0?InpShotsPerWeek:1; return InpWeeklyRiskPct/n; }
datetime DayStart(datetime t){ MqlDateTime s; TimeToStruct(t,s); s.hour=0;s.min=0;s.sec=0; return StructToTime(s); }
void ResetDay(datetime t){ g_curDay=DayStart(t); g_dayStartEquity=AccountInfoDouble(ACCOUNT_EQUITY); g_dayBlocked=false; }
double SpreadPips(){ return (sym.Ask()-sym.Bid())/g_pip; }

//==================================================================
void OnTick()
{
   sym.RefreshRates();
   datetime now=TimeCurrent();
   datetime nowUtc=TimeGMT();
   if(DayStart(now)!=g_curDay) ResetDay(now);

   double equity=AccountInfoDouble(ACCOUNT_EQUITY);

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

   ManageTimeExit();

   if(equity>=InpInitialBalance*(1.0+InpProfitTargetPct/100.0)) return;
   if(g_dayBlocked) return;

   MqlDateTime u; TimeToStruct(nowUtc,u);
   if(u.day_of_week!=InpEntryWeekday) return;
   if(InpSkipFirstWeek){ int wom=(u.day-1)/7+1; if(wom==1) return; }

   int slot=-1;
   for(int i=0;i<ArraySize(g_hours);i++) if(u.hour==g_hours[i]){ slot=i; break; }
   if(slot<0) return;

   datetime hourBar=nowUtc - (nowUtc % 3600);
   if(hourBar==g_lastShotBar[slot]) return;

   if(SpreadPips()>InpMaxSpreadPips){ if(InpVerboseLog) Print("[SKIP] spread高"); return; }
   if(InpUseNewsFilter && IsNewsBlackout(nowUtc)){ if(InpVerboseLog) Print("[SKIP] news"); return; }

   g_lastShotBar[slot]=hourBar;
   EnterShot(g_hours[slot]);
}

//==================================================================
void EnterShot(int hourTag)
{
   double atr[1];
   if(CopyBuffer(hAtr,0,1,1,atr)<1) return;
   double atrPrice=atr[0]; if(atrPrice<=0) return;

   double stopDist=InpCatastropheATR*atrPrice;
   double stopPips=stopDist/g_pip;
   if(stopPips<InpMinStopPips){ stopPips=InpMinStopPips; stopDist=stopPips*g_pip; }
   if(stopPips>InpMaxStopPips){ if(InpVerboseLog) Print("[SKIP] stop広すぎ"); return; }

   double lots=CalcLots(stopDist);
   if(lots<InpMinLot){ if(InpVerboseLog) Print("[SKIP] lots<min"); return; }

   int d=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   long stopLevel=SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL);
   double minDist=stopLevel*SymbolInfoDouble(_Symbol,SYMBOL_POINT);

   bool ok=false; double entry,sl;
   string cmt=StringFormat("FNStellarV8_ChfThu_h%d",hourTag);
   if(InpShortSide)
   {
      entry=sym.Bid(); sl=NormalizeDouble(entry+stopDist,d);          // SHORT: SLは上
      if(MathAbs(sl-entry)<minDist){ if(InpVerboseLog) Print("[SKIP] SL broker stop内"); return; }
      ok=trade.Sell(lots,_Symbol,0.0,sl,0.0,cmt);
   }
   else
   {
      entry=sym.Ask(); sl=NormalizeDouble(entry-stopDist,d);
      if(MathAbs(entry-sl)<minDist){ if(InpVerboseLog) Print("[SKIP] SL broker stop内"); return; }
      ok=trade.Buy(lots,_Symbol,0.0,sl,0.0,cmt);
   }
   if(ok)
      PrintFormat("[ENTRY v8] %s %s h%dUTC lots=%.2f entry~%.5f SL=%.5f stopPips=%.1f perShot=%.3f%%",
                  (InpShortSide?"SHORT":"LONG"),_Symbol,hourTag,lots,entry,sl,stopPips,PerShotRiskPct());
   else
      PrintFormat("[ENTRY FAIL] ret=%d %s",trade.ResultRetcode(),trade.ResultRetcodeDescription());
}

//==================================================================
double CalcLots(double stopDist)
{
   double riskMoney=InpInitialBalance*(PerShotRiskPct()/100.0);
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
//| 残存リスク(誠実な記録 — v8は v7より弱いことを忘れない):           |
//|  ・★LEADグレード: 順列p=0.136(有意未達), ジャックナイフmax_p=0.483|
//|    (ある年を除くと消える=特定年依存の疑い)。Bonferroni非生存。    |
//|    docs/15のスキャンで個別セルがp=0.003に見えたのは1061セルからの  |
//|    後付け選択バイアス。素直に午後帯を束ねるとp=0.136に戻る。        |
//|  ・良い点: 曜日特異性(木だけ+)・時刻局在(午後)・円月曜と相関0.06  |
//|    (独立)。合算で円単独DD-1.8%→-1.1%に改善する分散効果は実在。    |
//|  ・1ペア(USDCHF)のみ=ペア内分散なし。スワップ・週後半の地政学      |
//|    イベントに脆弱。スプレッドはCHFで広めになりがち→MaxSpread厳守。 |
//|  ・2.8年標本。10年追認(colab_edge2_chf_validation.py)で曜日       |
//|    プラセボ/p/JKが再現するまで衛星=極小サイズ厳守。崩れたら破棄。   |
//|  ・主力はあくまで v7(円月曜CORE)。v8は「無相関の補助」с限定。     |
//+------------------------------------------------------------------+
