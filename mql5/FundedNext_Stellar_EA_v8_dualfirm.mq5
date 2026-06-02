//+------------------------------------------------------------------+
//|                       FundedNext_Stellar_EA_v8_dualfirm.mq5        |
//|   v7 の戦略ロジックはそのまま（月曜シーズナリティ多ショット・      |
//|   3 JPYクロス × 朝の4時刻・リスク予算・LONG・時間決済）。           |
//|   ★追加: 業者プリセットで「リスク倍率」と「ルール挙動」を一括切替。 |
//|                                                                   |
//|   ■ 業者プリセット（InpFirmPreset）                                |
//|     ① FIRM_CURRENT_PROP_2_5X = 現在運用中のプロップ先              |
//|        ・週次リスク 2.5%（=2.5倍）                                 |
//|        ・FundedNext Stellar 系: 静的 -10%失格 / 日次 -5% / +8%目標 |
//|        ・+8%到達で新規停止、日次ガード有効。                       |
//|     ② FIRM_INSTANT_1_5X = インスタント(資金化済)先 [Blueberry等]   |
//|        ・週次リスク 1.5%（=1.5倍）                                 |
//|        ・-10% トレーリング失格（建値で固定）/ 日次制限なし / 目標なし|
//|        ・目標で止めない（出金しつつ継続）、トレーリング床を追従。  |
//|     ③ FIRM_MANUAL = 下の手動入力をそのまま使用（プリセット無効）。 |
//|                                                                   |
//|   ※「N倍」= 週次リスク N%（基準1倍=1.0%/週）。docs/25 と整合。     |
//|     現行2.5倍=2.5% / インスタント1.5倍=1.5%。値は input で上書き可。|
//|                                                                   |
//|   ■ リスク注記（誠実な記録 / docs/18,23,24,25）                    |
//|     10年実測で maxDD は週次予算にほぼ線形（0.6%→~5.9%）。          |
//|       ・1.5%（インスタント1.5倍）: 10年maxDD ~14.8% → 10%枠を超過。 |
//|         年失格 ~9% / 5年累積 ~38%。インスタントは失格時に掛け金返金 |
//|         なし。承知の上での攻め設定。                              |
//|       ・2.5%（現行2.5倍）: 10年maxDD ~24% 外挿 → 非常に攻撃的。     |
//|         2-step/時間無制限の器で運用する前提のユーザー指定値。      |
//|     ⇒ 本EAは指定倍率を忠実に実装する。守るなら weeklyRisk を下げる。|
//|                                                                   |
//|   ■ 運用: 3ペア(EURJPY/GBPJPY/USDJPY)の各チャートに1つずつアタッチ。|
//|     InpWeeklyRiskPct（=プリセット値）は全インスタンス共通にする。  |
//|     各ショットのサイズ = 週次予算 ÷ 総ショット数(12)。            |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "8.00"
#property strict
#property description "v7 multi-shot (Monday JPY seasonality) + dual-firm preset: Current-Prop 2.5x / Instant 1.5x. Risk-budgeted, LONG only, time-exit."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>
#include <Trade/SymbolInfo.mqh>

//==================================================================
enum ENUM_FIRM_PRESET
{
   FIRM_CURRENT_PROP_2_5X = 0, // 現行プロップ(2.5倍/静的-10%/日次-5%/+8%目標)
   FIRM_INSTANT_1_5X      = 1, // インスタント(1.5倍/-10%トレーリング/制限なし/目標なし)
   FIRM_MANUAL            = 2  // 手動入力を使用(プリセット無効)
};

input group "=== 業者プリセット（最重要・これ1つで倍率とルールを切替）==="
input ENUM_FIRM_PRESET InpFirmPreset = FIRM_INSTANT_1_5X; // ★運用先を選ぶ

input group "=== 口座 ==="
input double InpInitialBalance   = 50000.0;  // 口座初期残高(インスタント$50k想定。現行口座なら変更)

input group "=== Risk budgeting（プリセットが上書き。MANUAL時のみ手動）==="
input double InpWeeklyRiskPct    = 1.50;     // 週次リスク予算%（MANUAL時のみ有効。倍率=この値）
input int    InpShotsPerWeek     = 12;       // 総ショット数=ペア3×時刻4。予算をこれで割る。
input double InpMinLot           = 0.01;
input double InpMaxLot           = 5.0;

input group "=== ルール挙動（MANUAL時のみ手動。プリセットが上書き）==="
input double InpProfitTargetPct  = 8.0;      // 利益目標%（到達で新規停止。インスタントは無効化）
input bool   InpUseProfitStop    = true;     // 目標到達で新規停止するか
input double InpMaxLossLimitPct  = 10.0;     // 失格ライン%（総合DD）
input bool   InpUseTrailingDD    = false;    // true=トレーリングDD（インスタント） / false=静的
input bool   InpUseDailyStop     = true;     // 日次ストップを使うか（インスタントは無効）
input double InpDailyStopPct     = 4.0;      // 当日 -4% で当日停止（ルール-5%の内側）
input double InpEquityFloorBufPct= 2.0;      // 失格ラインの何%手前で全停止するか（安全マージン）
input bool   InpCloseAllOnGuard  = true;

input group "=== Multi-shot seasonality signal (UTC) ==="
input int    InpEntryWeekday     = 1;        // 1=Monday (MQL: 0=Sun..6=Sat)
input string InpEntryHoursUTC    = "4,6,8,10"; // 複数時刻(検証帯04-10)。カンマ区切り。
input int    InpHoldHours        = 24;       // 各ショット保有=24h
input bool   InpLongOnly         = true;     // 本エッジは LONG のみ
input bool   InpSkipFirstWeek    = false;    // 月初第1週除外(任意)

input group "=== Catastrophe stop (タイトSL厳禁: 広く置く) ==="
input int    InpAtrPeriodH1      = 24;       // H1×24 ≒ 日次ATR
input double InpCatastropheATR   = 2.5;      // SL = 2.5×ATR
input double InpMinStopPips      = 10.0;
input double InpMaxStopPips      = 400.0;

input group "=== Filters ==="
input double InpMaxSpreadPips    = 3.0;
input bool   InpUseNewsFilter    = true;
input int    InpNewsBeforeMin    = 30;
input int    InpNewsAfterMin     = 15;

input group "=== Execution ==="
input long   InpMagic            = 920580;   // v8
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

// ---- プリセット解決後の実効パラメータ ----
double   g_weeklyRisk    = 1.5;
bool     g_useTrailing   = false;
bool     g_useProfitStop = true;
bool     g_useDailyStop  = true;
double   g_maxLossPct    = 10.0;
double   g_profitPct     = 8.0;
double   g_dailyStopPct  = 4.0;
double   g_floorBufPct   = 2.0;
string   g_firmName      = "";

// ---- トレーリングDD用 ----
double   g_peakEquity    = 0.0;
double   g_trailFloor    = 0.0;  // 現在の失格床(ratchetで上昇、Initialで固定)

//==================================================================
void ResolveFirmPreset()
{
   // 既定 = 手動入力をそのまま採用（MANUAL の挙動）
   g_weeklyRisk    = InpWeeklyRiskPct;
   g_useTrailing   = InpUseTrailingDD;
   g_useProfitStop = InpUseProfitStop;
   g_useDailyStop  = InpUseDailyStop;
   g_maxLossPct    = InpMaxLossLimitPct;
   g_profitPct     = InpProfitTargetPct;
   g_dailyStopPct  = InpDailyStopPct;
   g_floorBufPct   = InpEquityFloorBufPct;
   g_firmName      = "MANUAL";

   if(InpFirmPreset == FIRM_CURRENT_PROP_2_5X)
   {
      g_firmName      = "CURRENT_PROP_2.5x";
      g_weeklyRisk    = 2.50;   // 2.5倍
      g_useTrailing   = false;  // 静的 -10%
      g_useProfitStop = true;   // +8%到達で新規停止
      g_useDailyStop  = true;   // 日次 -5% ルール → 内側 -4% で停止
      g_maxLossPct    = 10.0;
      g_profitPct     = 8.0;
      g_dailyStopPct  = 4.0;
      g_floorBufPct   = 2.0;    // -10% の 2% 手前(=-8%)で全停止
   }
   else if(InpFirmPreset == FIRM_INSTANT_1_5X)
   {
      g_firmName      = "INSTANT_1.5x";
      g_weeklyRisk    = 1.50;   // 1.5倍
      g_useTrailing   = true;   // -10% トレーリング(建値で固定)
      g_useProfitStop = false;  // 目標で止めない(出金しつつ継続)
      g_useDailyStop  = false;  // 日次制限なし
      g_maxLossPct    = 10.0;
      g_profitPct     = 0.0;
      g_dailyStopPct  = 0.0;
      g_floorBufPct   = 2.0;    // トレーリング床の 2% 手前で全停止
   }
}

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

   ResolveFirmPreset();

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   // トレーリングDD床の初期化（peak=初期残高、床=初期残高-最大損失）
   g_peakEquity = InpInitialBalance;
   g_trailFloor = InpInitialBalance*(1.0 - g_maxLossPct/100.0);

   ResetDay(TimeCurrent());

   string hrs=""; for(int i=0;i<ArraySize(g_hours);i++) hrs+=(string)g_hours[i]+(i+1<ArraySize(g_hours)?",":"");
   PrintFormat("[INIT v8] FIRM=%s %s pip=%.5f wd%d hoursUTC=[%s] hold=%dh",
               g_firmName,_Symbol,g_pip,InpEntryWeekday,hrs,InpHoldHours);
   PrintFormat("[INIT v8] weeklyRisk=%.2f%% shots/wk=%d perShot=%.3f%% | trailingDD=%s profitStop=%s(%.1f%%) dailyStop=%s(%.1f%%) maxLoss=%.1f%% buf=%.1f%%",
               g_weeklyRisk,InpShotsPerWeek,PerShotRiskPct(),
               (g_useTrailing?"YES":"no"),(g_useProfitStop?"YES":"no"),g_profitPct,
               (g_useDailyStop?"YES":"no"),g_dailyStopPct,g_maxLossPct,g_floorBufPct);
   if(InpVerboseLog)
      Print("[NOTE v8] 戦略はv7(月曜多ショット)のまま。業者プリセットでリスク倍率/ルールのみ切替。"
            "3ペアのチャートに各1つアタッチ。週次予算をショット数で割って建てる。");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason){ if(hAtr!=INVALID_HANDLE) IndicatorRelease(hAtr); }

//==================================================================
double PerShotRiskPct()
{
   int n = InpShotsPerWeek > 0 ? InpShotsPerWeek : 1;
   return g_weeklyRisk / n;   // ★総予算をショット数で割る = 合算エクスポージャ一定
}

datetime DayStart(datetime t){ MqlDateTime s; TimeToStruct(t,s); s.hour=0;s.min=0;s.sec=0; return StructToTime(s); }

void ResetDay(datetime t)
{
   g_curDay=DayStart(t);
   g_dayStartEquity=AccountInfoDouble(ACCOUNT_EQUITY);
   g_dayBlocked=false;
}

double SpreadPips(){ return (sym.Ask()-sym.Bid())/g_pip; }

// トレーリングDD床を更新して現在の「失格床」を返す。静的なら一定値。
double UpdateAndGetBreachFloor(double equity)
{
   if(!g_useTrailing)
      return InpInitialBalance*(1.0 - g_maxLossPct/100.0);

   if(equity > g_peakEquity) g_peakEquity = equity;
   // 生のトレーリング床 = ピーク - 最大損失額。初期残高で固定(=それ以上は上がらない)。
   double raw  = g_peakEquity - InpInitialBalance*g_maxLossPct/100.0;
   double capped = MathMin(raw, InpInitialBalance);   // 建値で固定
   if(capped > g_trailFloor) g_trailFloor = capped;   // ratchet(下げない)
   return g_trailFloor;
}

//==================================================================
void OnTick()
{
   sym.RefreshRates();
   datetime now=TimeCurrent();
   datetime nowUtc=TimeGMT();

   if(DayStart(now)!=g_curDay) ResetDay(now);

   double equity=AccountInfoDouble(ACCOUNT_EQUITY);

   // ===== ハードガード（失格ラインの内側で止める） =====
   double breachFloor = UpdateAndGetBreachFloor(equity);
   double guardFloor  = breachFloor + InpInitialBalance*g_floorBufPct/100.0; // 床の手前で停止
   if(equity<=guardFloor && !g_eaHalted)
   {
      g_eaHalted=true;
      if(InpCloseAllOnGuard) CloseAllByMagic("EQUITY_FLOOR");
      PrintFormat("[HALT] equity %.2f <= guard %.2f (breachFloor %.2f, trailing=%s)",
                  equity,guardFloor,breachFloor,(g_useTrailing?"Y":"N"));
   }
   if(g_eaHalted){ if(InpCloseAllOnGuard) CloseAllByMagic("HALTED"); return; }

   // 日次ストップ（プリセットで無効化されることがある）
   if(g_useDailyStop)
   {
      double dayPnL=equity-g_dayStartEquity;
      if(dayPnL<=-InpInitialBalance*g_dailyStopPct/100.0 && !g_dayBlocked)
      {
         g_dayBlocked=true;
         if(InpCloseAllOnGuard) CloseAllByMagic("DAILY_STOP");
         PrintFormat("[DAILY STOP] dayPnL %.2f",dayPnL);
      }
   }

   // 時間決済は常に評価
   ManageTimeExit();

   // 利益目標で新規停止（インスタントは無効＝止めずに継続）
   if(g_useProfitStop && equity>=InpInitialBalance*(1.0+g_profitPct/100.0)) return;
   if(g_dayBlocked) return;

   // ===== エントリー判定(UTC 曜日 × 複数時刻) =====
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
   double sl=entry-stopDist;
   double tp=0.0;

   double lots=CalcLots(stopDist);
   if(lots<InpMinLot){ if(InpVerboseLog) Print("[SKIP] lots<min"); return; }

   int d=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   sl=NormalizeDouble(sl,d);
   long stopLevel=SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL);
   double minDist=stopLevel*SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   if(MathAbs(entry-sl)<minDist){ if(InpVerboseLog) Print("[SKIP] SL broker stop内"); return; }

   string cmt=StringFormat("FNv8_%s_Mon_h%d",g_firmName,hourTag);
   if(trade.Buy(lots,_Symbol,0.0,sl,tp,cmt))
      PrintFormat("[ENTRY v8/%s] LONG %s h%dUTC lots=%.2f entry~%.5f SL=%.5f stopPips=%.1f perShot=%.3f%%",
                  g_firmName,_Symbol,hourTag,lots,entry,sl,stopPips,PerShotRiskPct());
   else
      PrintFormat("[ENTRY FAIL] ret=%d %s",trade.ResultRetcode(),trade.ResultRetcodeDescription());
}

//==================================================================
double CalcLots(double stopDist)
{
   double riskMoney=InpInitialBalance*(PerShotRiskPct()/100.0);   // ショット当たり=週次予算/ショット数
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
//| 残存リスク / 運用上の注意（誠実な記録）:                          |
//|  ・「N倍」=週次リスクN%。現行2.5倍=2.5% / インスタント1.5倍=1.5%。 |
//|    倍率は業者プリセットが自動設定（MANUALなら手動値）。           |
//|  ・トレーリングDD(インスタント)は本EAでは equity ピーク基準で実装。 |
//|    Blueberry等の正確な床(equity/balance基準・固定条件)は業者規約で |
//|    要確認。ズレる場合は g_floorBufPct を厚めにして安全側へ。      |
//|  ・3ペアは全てJPYクロスで相関0.6-0.78。独立ではないが相関<1で分散有。|
//|  ・スワップ: 各ショット1泊。JPYクロスLONGスワップ符号は金利局面で  |
//|    変動。実口座で要確認(不利なら収益が目減り)。                  |
//|  ・10年実測 maxDD は予算に線形: 1.5%→~14.8% / 2.5%→~24%。10%枠を   |
//|    超えるため失格リスクは高い（年~9%/5年~38% @1.5%）。承知の上で   |
//|    の倍率。守るなら weeklyRisk を下げる(0.6%で~5.9%)。            |
//|  ・低頻度(週12ショット)。インスタントは目標停止なし＝出金運用。   |
//|  ・必ずデモ/小額で1-2週、約定・スプレッド・スワップ・トレーリング |
//|    床の挙動を実地確認してから本番へ。詳細 docs/16,18,24,25。      |
//+------------------------------------------------------------------+
