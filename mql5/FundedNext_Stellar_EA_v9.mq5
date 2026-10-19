//+------------------------------------------------------------------+
//|                                  FundedNext_Stellar_EA_v9.mq5      |
//|   Monday weekend-flow — INTRADAY (no-overnight) multi-shot.        |
//|   v7と同じ唯一の検証済みエッジ(週明け月曜のJPYクロス・ドリフト、    |
//|   04-10UTC帯 LONG)を使うが、【保有を12hに短縮して同日中に決済】する。|
//|                                                                   |
//|   ★ v9 が v7 に対して持つ "優位性"(=リスク調整後エッジの改善):      |
//|     研究で「新しい独立シグナル」は出なかった(TOM=棄却 docs/20,       |
//|     金曜SHORT鏡像=棄却 research/edge9)。確実に残るのは月曜LONGのみ。  |
//|     そこで v9 は同じエッジから【より高いCalmar(DD効率)】を引き出す。  |
//|     実証(research/edge9b_v9_design.py, Yahoo H1 2.76年, JPYプール):  |
//|       BASE v7 (24h保有): net+45.4% / maxDD -8.49% / Calmar 5.35    |
//|       v9   (12h保有):    net+29.3% / maxDD -4.08% / Calmar 7.17 ★  |
//|       → 純益は落ちるが【DDがほぼ半減】。OOSも陽性(+2.25)。           |
//|     プロップは -10% 枠が制約 ⇒ DDが半分なら【同じ失格リスクで予算を   |
//|     約2倍】積める = +8%到達が速い。これが v9 の工学的アドバンテージ。 |
//|                                                                   |
//|   ★ 機構的な裏付け(なぜ12hで良いか・恣意的チューニングでない):       |
//|     ・週末フローのドリフトは月曜の London/NY セッションに前傾。       |
//|       4-10UTC建て → 12h後 = 16-22UTC = 同じ月曜内に決済。           |
//|     ・★【オーバーナイト無し】= スワップ符号リスクが消える。           |
//|       v6/v7 の致命的弱点(docs/13: JPYクロスLONGスワップが-1pip/泊だと |
//|       純益半減・DD悪化)を、ロールオーバーを跨がない設計で構造的に排除。|
//|     ・火曜朝の平均回帰/アジア時間のチョップを保有しない → DD低減。    |
//|                                                                   |
//|   ★ 運用: v7同様。3ペア(EURJPY/GBPJPY/USDJPY)のチャートに各1つ。     |
//|     InpWeeklyRiskPct はポートフォリオ週次予算(全インスタンス共通)。   |
//|     各ショット = 予算 / 総ショット数 × ペア重み。                    |
//|   ⚠ データ制約: 本設計のH1検証はYahoo 2.76年=LEAD級(プロトタイプ)。   |
//|     docs/18 の教訓(2.8年DDは10年の約1/3に過小評価)を厳守し、         |
//|     本資金前に【ユーザーの10年H1で12h保有のmaxDDを直接再測】+デモ。   |
//|     既定 InpWeeklyRiskPct は v7と同じ保守値から始める(下記)。         |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "9.00"
#property strict
#property description "FundedNext Stellar v9 — Monday weekend-flow, intraday (12h, no-overnight) multi-shot. Same confirmed edge as v7 at ~half the drawdown. JPY crosses, LONG only, risk-budgeted."

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

input group "=== Weekend-flow signal (UTC) ==="
input int    InpEntryWeekday     = 1;       // 1=Monday (MQL: 0=Sun..6=Sat)
input string InpEntryHoursUTC    = "4,6,8,10"; // 検証帯04-10(v7と同帯・時刻の事後選択をしない)
input int    InpHoldHours        = 12;      // ★v9: 12h保有 = 同日決済(オーバーナイト無し)。v7は24。
input bool   InpLongOnly         = true;    // 本エッジは LONG のみ
input bool   InpSkipFirstWeek    = false;   // 月初第1週除外(10年EURJPYで改善 docs/12 ゲート11・任意)

input group "=== Risk budgeting (★多ショットの要) ==="
input double InpWeeklyRiskPct    = 0.60;    // ★ポートフォリオ週次リスク予算%(全インスタンス共通)。
                                            //   v7既定(10年maxDD~5.9%外挿)を踏襲した保守値から開始。
                                            //   ★v9はDDが約半分ゆえ、10年再測でDDが収まれば 1.0-1.2 へ
                                            //   引き上げ可(同じ-10%枠で速度↑)。だが【10年実測まで上げない】。
input int    InpShotsPerWeek     = 12;      // 総ショット数=ペア数(3)×時刻数(4)。予算をこれで割る。
input double InpPairWeight       = 1.0;     // このペアのショット重み(エッジ加重用)。既定1.0=等加重。
                                            //   過剰最適化回避のため既定は等加重。研究のエッジ加重例(参考):
                                            //   EURJPY 0.29 / GBPJPY 0.46 / USDJPY 0.24(2.76年実現平均比)。
                                            //   ※GBPJPY偏重は円安レジーム由来の可能性(docs/11)→等加重推奨。
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
input long   InpMagic            = 920590;  // v9
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
   if(InpHoldHours >= 18)
      Print("[WARN v9] InpHoldHours>=18 はオーバーナイトを跨ぐ可能性=スワップ符号リスク復活。"
            "v9の利点(同日決済)を保つには 12 推奨。");

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   ResetDay(TimeCurrent());
   string hrs=""; for(int i=0;i<ArraySize(g_hours);i++) hrs+=(string)g_hours[i]+(i+1<ArraySize(g_hours)?",":"");
   PrintFormat("[INIT v9] %s pip=%.5f wd%d hoursUTC=[%s] HOLD=%dh(同日決済) weeklyRisk=%.2f%% shots/wk=%d w=%.2f perShot=%.3f%%",
               _Symbol,g_pip,InpEntryWeekday,hrs,InpHoldHours,
               InpWeeklyRiskPct,InpShotsPerWeek,InpPairWeight,PerShotRiskPct());
   if(InpVerboseLog)
      Print("[NOTE] v9 = 月曜・週末フロー intraday 多ショット。v7と同エッジを12h保有でDDほぼ半減・"
            "オーバーナイト無し=スワップリスク排除。3ペアのチャートに各1つ。10年再測+デモ前進検証推奨。");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason){ if(hAtr!=INVALID_HANDLE) IndicatorRelease(hAtr); }

//==================================================================
double PerShotRiskPct()
{
   int n = InpShotsPerWeek > 0 ? InpShotsPerWeek : 1;
   double w = InpPairWeight > 0.0 ? InpPairWeight : 1.0;
   return (InpWeeklyRiskPct / n) * w;    // ★総予算/ショット数 × ペア重み(既定1.0=等加重)
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

   string cmt=StringFormat("FNStellarV9_Mon_h%d",hourTag);
   if(trade.Buy(lots,_Symbol,0.0,sl,tp,cmt))
      PrintFormat("[ENTRY v9] LONG %s h%dUTC lots=%.2f entry~%.5f SL=%.5f stopPips=%.1f hold=%dh perShot=%.3f%%",
                  _Symbol,hourTag,lots,entry,sl,stopPips,InpHoldHours,PerShotRiskPct());
   else
      PrintFormat("[ENTRY FAIL] ret=%d %s",trade.ResultRetcode(),trade.ResultRetcodeDescription());
}

//==================================================================
double CalcLots(double stopDist)
{
   double riskMoney=InpInitialBalance*(PerShotRiskPct()/100.0);   // ★ショット当たり=週次予算/ショット数×重み
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
// v9 既定12h=同日決済(オーバーナイト無し)。複数ショットを個別管理する。
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
//|  ・新しい独立エッジではない。v7と同じ「月曜の円週明けドリフト」1現象。|
//|    v9の付加価値は【DD効率(Calmar)とスワップ排除】=同じエッジをプロップ|
//|    の-10%枠で速く・安全に積む工学的改良。エッジ自体の出所はv6/v7と同じ。|
//|  ・H1検証はYahoo 2.76年=LEAD級。docs/18の罠(短期はDD過小評価)を厳守。 |
//|    ★本資金前に【ユーザー10年H1で12h保有のmaxDD・順列p・JKを再測】必須。|
//|    2.76年は近年の円安一方向局面を多く含む=楽観側。10年で必ず器を確認。|
//|  ・GBPJPYの強さ(2.76年)はレジーム由来の可能性(docs/11)。エッジ加重は |
//|    既定で使わず等加重を推奨(InpPairWeight=1.0)。10年で再評価する。   |
//|  ・低頻度(週12ショット・各小サイズ)。+8%到達はプロップの時間無制限前提。|
//|  ・TimeGMT()とブローカー時刻の乖離に注意(04-10/16-22帯なら許容)。   |
//|  ・12h保有は週末(土日)を跨がない=金曜建てではない(月曜のみ)。       |
//+------------------------------------------------------------------+
