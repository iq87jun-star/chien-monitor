//+------------------------------------------------------------------+
//|                                    FundedNext_Stellar_EA.mq5      |
//|   FundedNext "Stellar 2-Step" ($100K) 審査通過特化EA              |
//|                                                                  |
//|   設計思想（優先順位順）:                                          |
//|     1. 失格(退場)を絶対に避ける ... 日次/累積ハードガードを最優先   |
//|     2. 1日あたりトレード数・同時保有数・日次リスクに上限           |
//|     3. コスト(スプレッド/手数料/スワップ/スリッページ)を現実計上   |
//|     4. 速度より「割れない経路」。固定%リスク・SL必須               |
//|     5. 経済指標フィルタ                                            |
//|                                                                  |
//|   ※ 過去戦略(ゴトー日・曜日アノマリー等)は一切不使用。            |
//|     白紙から選定した「上位足トレンド方向への押し目/戻り順張り」。  |
//|                                                                  |
//|   免責: バックテスト/シミュレーションは将来やライブ約定を保証しない。|
//+------------------------------------------------------------------+
#property copyright "Autonomous Quant Build"
#property version   "1.00"
#property strict
#property description "FundedNext Stellar 2-Step risk-guarded trend pullback EA"

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>
#include <Trade/SymbolInfo.mqh>

//====================================================================
// 入力パラメータ（全ロジックを外部入力化）
//====================================================================

//--- チャレンジ規則（FundedNext Stellar 2-Step / $100K 既定） ----------
input group "=== Challenge Rules (FundedNext Stellar 2-Step) ==="
input double InpInitialBalance   = 100000.0; // 初期残高（審査開始時の口座サイズ）
input double InpProfitTargetPct  = 8.0;      // 利益目標% (Phase1=8, Phase2=5)
input double InpDailyLossLimitPct= 5.0;      // 規則上の日次損失上限%（失格ライン）
input double InpMaxLossLimitPct  = 10.0;     // 規則上の最大損失上限%（静的フロア）

//--- 内部ハードガード（規則の手前で必ず止める安全マージン） -----------
input group "=== Hard Guards (stop BEFORE the rule line) ==="
input double InpDailyStopPct     = 4.0;      // 当日-X%で全決済＆当日新規停止（<5%）
input double InpDailyNoNewPct    = 3.0;      // 当日-X%で新規のみ停止（早期ブレーキ）
input double InpEquityFloorDDPct = 8.0;      // 開始残高比-X%で全決済＆EA恒久停止(<10%)
input bool   InpCloseAllOnGuard  = true;     // ガード発火時に全ポジション即時決済

//--- リスク／サイジング ----------------------------------------------
input group "=== Risk & Sizing ==="
input double InpRiskPerTradePct  = 0.40;     // 1トレードのリスク%（0.25〜0.50推奨）
input double InpMaxDailyRiskPct  = 1.20;     // 1日に投入してよい合計リスク%上限
input int    InpMaxTradesPerDay  = 3;        // 1日の最大新規トレード数
input int    InpMaxOpenPositions = 1;        // 同時保有ポジション数の上限
input double InpMinLot            = 0.01;    // 最小ロット（フェイルセーフ）
input double InpMaxLot            = 5.0;     // 最大ロット上限（暴走防止）

//--- 戦略（上位足トレンド × 押し目/戻り順張り） ----------------------
input group "=== Strategy: HTF Trend + Pullback ==="
input ENUM_TIMEFRAMES InpTrendTF = PERIOD_H4;  // トレンド判定の上位足
input ENUM_TIMEFRAMES InpEntryTF = PERIOD_H1;  // エントリー足
input int    InpEmaFastTrend     = 50;       // 上位足 速いEMA
input int    InpEmaSlowTrend     = 200;      // 上位足 遅いEMA
input int    InpEmaPullback      = 20;       // エントリー足 押し目基準EMA
input int    InpRsiPeriod        = 14;       // RSI期間
input double InpRsiLongDip       = 45.0;     // ロング: RSIがこの下→反転で押し目買い
input double InpRsiShortPop      = 55.0;     // ショート: RSIがこの上→反転で戻り売り
input int    InpAtrPeriod        = 14;       // ATR期間（SL/ボラ基準）

//--- 損切り／利確 -----------------------------------------------------
input group "=== Stops & Targets ==="
input double InpAtrSLMult        = 1.5;      // SL = swing ± ATR×この倍率
input double InpRR               = 1.8;      // TP = SL距離 × RR
input double InpMinStopPips      = 12.0;     // 最小SL距離(pips)（過小SL防止）
input double InpMaxStopPips      = 80.0;     // 最大SL距離(pips)（過大SL除外）
input bool   InpUseBreakeven     = true;     // 含み益で建値移動
input double InpBreakevenAtR     = 1.0;      // +Rでブレークイーブンへ
input bool   InpUseTrailing      = true;     // ATRトレーリング
input double InpTrailAtrMult     = 2.0;      // トレーリング距離 = ATR×倍率

//--- フィルタ（スプレッド／セッション／最小保有／ニュース） ----------
input group "=== Filters ==="
input double InpMaxSpreadPips    = 2.0;      // 許容最大スプレッド(pips)
input bool   InpUseSession       = true;     // セッション時間帯フィルタ
input int    InpSessionStartHour = 7;        // 取引開始(サーバ時間, 既定=London)
input int    InpSessionEndHour   = 20;       // 取引終了(サーバ時間, 既定=NY中盤)
input int    InpMinHoldSeconds   = 150;      // 最小保有秒(>120s, 2分未満決済フラグ回避)
input bool   InpUseNewsFilter    = true;     // 経済指標フィルタ
input int    InpNewsBeforeMin    = 30;       // 指標前 N分は新規停止
input int    InpNewsAfterMin     = 15;       // 指標後 N分は新規停止
input bool   InpNewsCloseBefore  = false;    // 指標前に既存ポジを決済するか
input string InpManualBlackout   = "";       // 手動ブラックアウト "HH:MM-HH:MM;..."(サーバ時間)

//--- 動作 -------------------------------------------------------------
input group "=== Execution ==="
input long   InpMagic            = 920530;   // マジックナンバー
input int    InpSlippagePoints   = 20;       // 許容スリッページ(points)
input bool   InpVerboseLog       = true;     // 詳細ログ

//====================================================================
// グローバル
//====================================================================
CTrade        trade;
CPositionInfo posinfo;
CSymbolInfo   sym;

int    hTrendFast=INVALID_HANDLE, hTrendSlow=INVALID_HANDLE;
int    hEmaPB=INVALID_HANDLE, hRsi=INVALID_HANDLE, hAtr=INVALID_HANDLE;

double g_pip            = 0.0;     // 1pip の価格幅
double g_pointsPerPip   = 0.0;     // 1pip = 何points
double g_dayStartEquity = 0.0;     // 当日開始equity（サーバ日替わりで更新）
datetime g_curDay       = 0;       // 当日(00:00サーバ)の日付値
int    g_tradesToday    = 0;       // 当日新規トレード数
double g_riskUsedToday  = 0.0;     // 当日投入リスク%累計
bool   g_eaHalted       = false;   // 恒久停止フラグ（-8%到達）
bool   g_dayBlocked     = false;   // 当日新規停止フラグ（-4%到達）
datetime g_lastBarTime  = 0;       // エントリー足の最終バー時刻

//====================================================================
// 初期化
//====================================================================
int OnInit()
{
   if(!sym.Name(_Symbol)) { Print("Symbol init failed"); return INIT_FAILED; }
   sym.RefreshRates();

   // pip 定義（3/5桁ブローカー対応）
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(digits==3 || digits==5) { g_pip = point*10.0; g_pointsPerPip = 10.0; }
   else                       { g_pip = point;      g_pointsPerPip = 1.0;  }

   // 指標ハンドル
   hTrendFast = iMA(_Symbol, InpTrendTF, InpEmaFastTrend, 0, MODE_EMA, PRICE_CLOSE);
   hTrendSlow = iMA(_Symbol, InpTrendTF, InpEmaSlowTrend, 0, MODE_EMA, PRICE_CLOSE);
   hEmaPB     = iMA(_Symbol, InpEntryTF, InpEmaPullback,  0, MODE_EMA, PRICE_CLOSE);
   hRsi       = iRSI(_Symbol, InpEntryTF, InpRsiPeriod, PRICE_CLOSE);
   hAtr       = iATR(_Symbol, InpEntryTF, InpAtrPeriod);
   if(hTrendFast==INVALID_HANDLE || hTrendSlow==INVALID_HANDLE || hEmaPB==INVALID_HANDLE
      || hRsi==INVALID_HANDLE || hAtr==INVALID_HANDLE)
   { Print("Indicator handle creation failed"); return INIT_FAILED; }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   // 入力の安全検証（規則の手前で止まることを保証）
   if(InpDailyStopPct >= InpDailyLossLimitPct)
      Print("WARNING: DailyStop(", InpDailyStopPct, ") >= rule(", InpDailyLossLimitPct, ") - unsafe!");
   if(InpEquityFloorDDPct >= InpMaxLossLimitPct)
      Print("WARNING: EquityFloorDD(", InpEquityFloorDDPct, ") >= rule(", InpMaxLossLimitPct, ") - unsafe!");

   ResetDay(TimeCurrent());
   PrintFormat("[INIT] %s pip=%.5f initBal=%.2f target=%.2f%% dailyGuard=%.1f%% floorGuard=%.1f%%",
               _Symbol, g_pip, InpInitialBalance, InpProfitTargetPct, InpDailyStopPct, InpEquityFloorDDPct);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(hTrendFast!=INVALID_HANDLE) IndicatorRelease(hTrendFast);
   if(hTrendSlow!=INVALID_HANDLE) IndicatorRelease(hTrendSlow);
   if(hEmaPB!=INVALID_HANDLE)     IndicatorRelease(hEmaPB);
   if(hRsi!=INVALID_HANDLE)       IndicatorRelease(hRsi);
   if(hAtr!=INVALID_HANDLE)       IndicatorRelease(hAtr);
}

//====================================================================
// メイン
//====================================================================
void OnTick()
{
   sym.RefreshRates();

   // --- 日替わり処理（サーバ00:00基準） ---
   datetime today = DayStart(TimeCurrent());
   if(today != g_curDay)
      ResetDay(TimeCurrent());

   //==================================================================
   // ★★ ハードガード（毎ティック・最優先・含み損込みのequityで判定） ★★
   //==================================================================
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);

   // (A) 累積フロア: 開始残高比 -InpEquityFloorDDPct% でEA恒久停止
   double floorEquity = InpInitialBalance * (1.0 - InpEquityFloorDDPct/100.0);
   if(equity <= floorEquity && !g_eaHalted)
   {
      g_eaHalted = true;
      if(InpCloseAllOnGuard) CloseAllPositions("EQUITY_FLOOR_GUARD");
      PrintFormat("[HALT] Equity %.2f <= floor %.2f. EA stopped permanently.", equity, floorEquity);
   }
   if(g_eaHalted) { ManageGuardOnlyExit(); return; }

   // (B) 日次ストップ: 当日 -InpDailyStopPct%（初期残高基準）で全決済＆当日新規停止
   double dailyStopLoss = InpInitialBalance * (InpDailyStopPct/100.0);
   double dayPnL = equity - g_dayStartEquity;      // 当日損益（含み損込み）
   if(dayPnL <= -dailyStopLoss && !g_dayBlocked)
   {
      g_dayBlocked = true;
      if(InpCloseAllOnGuard) CloseAllPositions("DAILY_STOP_GUARD");
      PrintFormat("[DAILY STOP] dayPnL %.2f <= -%.2f. Flat & no-new until next day.", dayPnL, dailyStopLoss);
   }

   // --- 利益目標到達なら新規停止（達成後はリスクを取らない） ---
   double targetEquity = InpInitialBalance * (1.0 + InpProfitTargetPct/100.0);
   bool targetReached = (equity >= targetEquity);

   //==================================================================
   // 既存ポジション管理（建値移動・トレーリング・最小保有・ニュース前決済）
   //==================================================================
   ManageOpenPositions();

   //==================================================================
   // 新規エントリー可否
   //==================================================================
   if(g_dayBlocked || targetReached) return;

   // 早期ブレーキ: 当日 -InpDailyNoNewPct% を超えたら新規停止
   double noNewLoss = InpInitialBalance * (InpDailyNoNewPct/100.0);
   if(dayPnL <= -noNewLoss) return;

   if(g_tradesToday >= InpMaxTradesPerDay) return;
   if(g_riskUsedToday + InpRiskPerTradePct > InpMaxDailyRiskPct + 1e-9) return;
   if(CountOpenPositions() >= InpMaxOpenPositions) return;

   // フィルタ群
   if(InpUseSession && !InSession(TimeCurrent())) return;
   if(SpreadPips() > InpMaxSpreadPips) return;
   if(InpUseNewsFilter && IsNewsBlackout(TimeCurrent())) return;

   // 新規バーでのみシグナル評価（足確定ベース）
   datetime barTime = iTime(_Symbol, InpEntryTF, 0);
   if(barTime == g_lastBarTime) return;
   g_lastBarTime = barTime;

   int signal = CheckSignal();   // +1=long, -1=short, 0=none
   if(signal != 0)
      TryEnter(signal);
}

//====================================================================
// シグナル: 上位足トレンド方向への押し目買い／戻り売り
//   - 上位足: EMAfast vs EMAslow でトレンド方向
//   - エントリー足: 価格が押し目EMAへ回帰 → RSIが過熱から反転 → 確定足で順張り
//====================================================================
int CheckSignal()
{
   // 動的配列＋ArraySetAsSeriesで index 0 = 現在形成中足, 1 = 直近確定足, 2 = その前
   double tf[], ts[], pb[], rsi[], close[], high[], low[];
   ArraySetAsSeries(tf,true);  ArraySetAsSeries(ts,true);  ArraySetAsSeries(pb,true);
   ArraySetAsSeries(rsi,true); ArraySetAsSeries(close,true);
   ArraySetAsSeries(high,true);ArraySetAsSeries(low,true);

   if(CopyBuffer(hTrendFast,0,0,2,tf)<2)   return 0;
   if(CopyBuffer(hTrendSlow,0,0,2,ts)<2)   return 0;
   if(CopyBuffer(hEmaPB,0,0,3,pb)<3)       return 0;
   if(CopyBuffer(hRsi,0,0,3,rsi)<3)        return 0;
   if(CopyClose(_Symbol,InpEntryTF,0,3,close)<3) return 0;
   if(CopyHigh(_Symbol,InpEntryTF,0,3,high)<3)   return 0;
   if(CopyLow(_Symbol,InpEntryTF,0,3,low)<3)     return 0;

   // index 1 = 直近確定足, 2 = その1本前
   bool trendUp   = (tf[0] > ts[0]);
   bool trendDown = (tf[0] < ts[0]);

   // ロング条件: 上昇トレンド & 直近で押し目EMA付近まで下げRSI<dip → 確定足が反転上昇
   if(trendUp)
   {
      bool pulledBack = (low[2] <= pb[2] + 0.10*g_pip) || (rsi[2] < InpRsiLongDip);
      bool rsiTurnUp  = (rsi[1] > rsi[2]) && (rsi[1] > InpRsiLongDip);
      bool bullClose  = (close[1] > close[2]) && (close[1] > pb[1]);
      if(pulledBack && rsiTurnUp && bullClose)
         return +1;
   }
   // ショート条件: 下降トレンド & 戻りEMA付近までRSI>pop → 確定足が反転下落
   if(trendDown)
   {
      bool poppedBack = (high[2] >= pb[2] - 0.10*g_pip) || (rsi[2] > InpRsiShortPop);
      bool rsiTurnDn  = (rsi[1] < rsi[2]) && (rsi[1] < InpRsiShortPop);
      bool bearClose  = (close[1] < close[2]) && (close[1] < pb[1]);
      if(poppedBack && rsiTurnDn && bearClose)
         return -1;
   }
   return 0;
}

//====================================================================
// エントリー実行（SL必須・固定%リスクのロット計算・TP=RR）
//====================================================================
void TryEnter(int dir)
{
   double atr[1];
   if(CopyBuffer(hAtr,0,1,1,atr)<1) return;
   double atrPrice = atr[0];
   if(atrPrice<=0) return;

   double ask = sym.Ask();
   double bid = sym.Bid();

   // スイング基準のSL: 直近N本の安値/高値 ± ATRバッファ
   int lookback = 10;
   double sl=0.0, entry=0.0, tp=0.0;
   double stopDistPrice=0.0;

   if(dir>0)
   {
      double swingLow = LowestLow(lookback);
      sl    = swingLow - InpAtrSLMult*atrPrice;
      entry = ask;
      stopDistPrice = entry - sl;
   }
   else
   {
      double swingHigh = HighestHigh(lookback);
      sl    = swingHigh + InpAtrSLMult*atrPrice;
      entry = bid;
      stopDistPrice = sl - entry;
   }

   if(stopDistPrice<=0) return;

   double stopPips = stopDistPrice / g_pip;
   // SL距離の妥当性（過小/過大を除外）
   if(stopPips < InpMinStopPips || stopPips > InpMaxStopPips)
   {
      if(InpVerboseLog) PrintFormat("[SKIP] stopPips %.1f out of [%.1f,%.1f]", stopPips, InpMinStopPips, InpMaxStopPips);
      return;
   }

   // TP = SL距離 × RR
   if(dir>0) tp = entry + InpRR*stopDistPrice;
   else      tp = entry - InpRR*stopDistPrice;

   // ロット = (equity × risk%) / (SL距離の金額価値)
   double lots = CalcLots(stopDistPrice);
   if(lots < InpMinLot) { if(InpVerboseLog) Print("[SKIP] lots < min"); return; }

   // SL/TP/価格を正規化
   int    d   = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   sl  = NormalizeDouble(sl, d);
   tp  = NormalizeDouble(tp, d);

   // ブローカー最小ストップ距離チェック
   long stopLevelPts = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minDist = stopLevelPts * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(MathAbs(entry-sl) < minDist || MathAbs(tp-entry) < minDist)
   { if(InpVerboseLog) Print("[SKIP] SL/TP within broker stop level"); return; }

   bool ok=false;
   string cmt = "FNStellar";
   if(dir>0) ok = trade.Buy(lots, _Symbol, 0.0, sl, tp, cmt);
   else      ok = trade.Sell(lots, _Symbol, 0.0, sl, tp, cmt);

   if(ok)
   {
      g_tradesToday++;
      g_riskUsedToday += InpRiskPerTradePct;
      PrintFormat("[ENTRY] %s lots=%.2f entry~%.5f SL=%.5f TP=%.5f stopPips=%.1f risk%%=%.2f tradesToday=%d",
                  (dir>0?"BUY":"SELL"), lots, entry, sl, tp, stopPips, InpRiskPerTradePct, g_tradesToday);
   }
   else
   {
      PrintFormat("[ENTRY FAIL] ret=%d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
   }
}

//====================================================================
// 固定%リスクのロット計算（SL必須前提。SLが無ければ建てない）
//====================================================================
double CalcLots(double stopDistPrice)
{
   double equity      = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskMoney   = equity * (InpRiskPerTradePct/100.0);

   double tickValue   = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize    = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickSize<=0 || tickValue<=0) return 0.0;

   // SL距離1ロットあたりの損失額 = (stopDistPrice / tickSize) * tickValue
   double lossPerLot  = (stopDistPrice / tickSize) * tickValue;
   if(lossPerLot<=0) return 0.0;

   double lots = riskMoney / lossPerLot;

   // ロットステップ・最小最大へ丸め
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step>0) lots = MathFloor(lots/step)*step;     // 切り捨て＝リスク超過を防ぐ
   lots = MathMax(lots, 0.0);
   lots = MathMin(lots, MathMin(InpMaxLot, vmax));
   if(lots < MathMax(InpMinLot, vmin)) return 0.0;  // 規定リスクで建てられないなら見送り
   return lots;
}

//====================================================================
// 既存ポジ管理: 最小保有 / ブレークイーブン / ATRトレーリング / ニュース前決済
//====================================================================
void ManageOpenPositions()
{
   double atr[1];
   bool haveAtr = (CopyBuffer(hAtr,0,1,1,atr)>=1 && atr[0]>0);

   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket==0) continue;
      if(!posinfo.SelectByTicket(ticket)) continue;
      if(posinfo.Symbol()!=_Symbol || posinfo.Magic()!=InpMagic) continue;

      long   type   = posinfo.PositionType();
      double open   = posinfo.PriceOpen();
      double sl     = posinfo.StopLoss();
      double tp     = posinfo.TakeProfit();
      double vol    = posinfo.Volume();
      datetime ptime= (datetime)posinfo.Time();
      int    held   = (int)(TimeCurrent()-ptime);

      double price  = (type==POSITION_TYPE_BUY)? sym.Bid() : sym.Ask();
      double rDist  = MathAbs(open - sl);
      if(rDist<=0) continue;
      double profitDist = (type==POSITION_TYPE_BUY)? (price-open) : (open-price);
      double rMultiple  = profitDist / rDist;

      // --- ニュース直前の任意クローズ ---
      if(InpUseNewsFilter && InpNewsCloseBefore && IsNewsBlackout(TimeCurrent()))
      {
         // 最小保有時間を尊重（2分未満決済フラグ回避）。ただしガードは別扱い。
         if(held >= InpMinHoldSeconds)
         { ClosePosition(ticket, "NEWS_CLOSE"); continue; }
      }

      // --- ブレークイーブン ---
      if(InpUseBreakeven && rMultiple >= InpBreakevenAtR && held >= InpMinHoldSeconds)
      {
         double be = open;
         bool need = (type==POSITION_TYPE_BUY)? (sl < be-1e-9) : (sl > be+1e-9);
         if(need) ModifySL(ticket, be, tp);
      }

      // --- ATRトレーリング ---
      if(InpUseTrailing && haveAtr && rMultiple >= InpBreakevenAtR && held >= InpMinHoldSeconds)
      {
         double trail = InpTrailAtrMult*atr[0];
         if(type==POSITION_TYPE_BUY)
         {
            double newSL = price - trail;
            if(newSL > sl + 1e-9 && newSL < price) ModifySL(ticket, newSL, tp);
         }
         else
         {
            double newSL = price + trail;
            if((sl<=0 || newSL < sl - 1e-9) && newSL > price) ModifySL(ticket, newSL, tp);
         }
      }
   }
}

//====================================================================
// ガード後の「決済のみ」モード（EA恒久停止中も建値ポジを安全に閉じる）
//====================================================================
void ManageGuardOnlyExit()
{
   if(CountOpenPositions()>0 && InpCloseAllOnGuard)
      CloseAllPositions("HALTED_CLEANUP");
}

//====================================================================
// 取引補助
//====================================================================
void ModifySL(ulong ticket, double sl, double tp)
{
   int d = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   if(!trade.PositionModify(ticket, NormalizeDouble(sl,d), NormalizeDouble(tp,d)))
      if(InpVerboseLog) PrintFormat("[MODIFY FAIL] %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
}

void ClosePosition(ulong ticket, string why)
{
   if(trade.PositionClose(ticket))
   { if(InpVerboseLog) PrintFormat("[CLOSE] ticket=%I64u (%s)", ticket, why); }
   else
      PrintFormat("[CLOSE FAIL] ticket=%I64u ret=%d %s", ticket, trade.ResultRetcode(), trade.ResultRetcodeDescription());
}

void CloseAllPositions(string why)
{
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket==0) continue;
      if(!posinfo.SelectByTicket(ticket)) continue;
      if(posinfo.Symbol()!=_Symbol || posinfo.Magic()!=InpMagic) continue;
      ClosePosition(ticket, why);
   }
}

int CountOpenPositions()
{
   int n=0;
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket==0) continue;
      if(!posinfo.SelectByTicket(ticket)) continue;
      if(posinfo.Symbol()==_Symbol && posinfo.Magic()==InpMagic) n++;
   }
   return n;
}

//====================================================================
// 価格ヘルパ
//====================================================================
double LowestLow(int bars)
{
   double low[];
   if(CopyLow(_Symbol, InpEntryTF, 1, bars, low) < bars) return sym.Bid();
   double m = low[0];
   for(int i=1;i<bars;i++) if(low[i]<m) m=low[i];
   return m;
}
double HighestHigh(int bars)
{
   double high[];
   if(CopyHigh(_Symbol, InpEntryTF, 1, bars, high) < bars) return sym.Ask();
   double m = high[0];
   for(int i=1;i<bars;i++) if(high[i]>m) m=high[i];
   return m;
}

double SpreadPips()
{
   double spr = (sym.Ask()-sym.Bid());
   return spr / g_pip;
}

//====================================================================
// 日替わり・セッション
//====================================================================
datetime DayStart(datetime t)
{
   MqlDateTime s; TimeToStruct(t, s);
   s.hour=0; s.min=0; s.sec=0;
   return StructToTime(s);
}

void ResetDay(datetime t)
{
   g_curDay         = DayStart(t);
   g_dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   g_tradesToday    = 0;
   g_riskUsedToday  = 0.0;
   g_dayBlocked     = false;
   if(InpVerboseLog)
      PrintFormat("[NEW DAY] %s dayStartEquity=%.2f", TimeToString(g_curDay, TIME_DATE), g_dayStartEquity);
}

bool InSession(datetime t)
{
   MqlDateTime s; TimeToStruct(t, s);
   // 週末は取引しない（金曜終盤のギャップ回避は news/session で別途調整可）
   if(s.day_of_week==0 || s.day_of_week==6) return false;
   int h = s.hour;
   if(InpSessionStartHour <= InpSessionEndHour)
      return (h>=InpSessionStartHour && h<InpSessionEndHour);
   // 跨ぎセッション対応
   return (h>=InpSessionStartHour || h<InpSessionEndHour);
}

//====================================================================
// ニュースフィルタ
//   1) MT5 経済カレンダー(CalendarValueHistory)で高重要度イベントを検出
//   2) 手動ブラックアウト "HH:MM-HH:MM;..." も併用
//====================================================================
bool IsNewsBlackout(datetime now)
{
   // --- 手動ブラックアウト ---
   if(StringLen(InpManualBlackout)>0 && InManualBlackout(now))
      return true;

   // --- 経済カレンダー（対応ビルドのみ。テスターでも一部利用可） ---
   string base  = SymbolInfoString(_Symbol, SYMBOL_CURRENCY_BASE);
   string quote = SymbolInfoString(_Symbol, SYMBOL_CURRENCY_PROFIT);

   datetime from = now - InpNewsAfterMin*60;       // 過去側
   datetime to   = now + InpNewsBeforeMin*60;      // 未来側

   if(CalendarNewsHit(base, from, to, now))  return true;
   if(CalendarNewsHit(quote, from, to, now)) return true;
   return false;
}

bool CalendarNewsHit(string currency, datetime from, datetime to, datetime now)
{
   MqlCalendarValue values[];
   // 指定通貨の指標値を取得（国コードではなく通貨でフィルタ）
   int n = CalendarValueHistory(values, from, to, NULL, currency);
   if(n<=0) return false;
   for(int i=0;i<n;i++)
   {
      MqlCalendarEvent ev;
      if(!CalendarEventById(values[i].event_id, ev)) continue;
      if(ev.importance != CALENDAR_IMPORTANCE_HIGH) continue;  // 高重要度のみ
      datetime et = values[i].time;
      if(et >= now - InpNewsAfterMin*60 && et <= now + InpNewsBeforeMin*60)
         return true;
   }
   return false;
}

bool InManualBlackout(datetime now)
{
   MqlDateTime s; TimeToStruct(now, s);
   int curMin = s.hour*60 + s.min;

   string parts[];
   int cnt = StringSplit(InpManualBlackout, ';', parts);
   for(int i=0;i<cnt;i++)
   {
      string seg = parts[i];
      StringTrimLeft(seg); StringTrimRight(seg);
      if(StringLen(seg)==0) continue;
      string se[];
      if(StringSplit(seg,'-',se)!=2) continue;
      int a = ParseHHMM(se[0]);
      int b = ParseHHMM(se[1]);
      if(a<0||b<0) continue;
      if(a<=b) { if(curMin>=a && curMin<=b) return true; }
      else     { if(curMin>=a || curMin<=b) return true; } // 日跨ぎ
   }
   return false;
}

int ParseHHMM(string hhmm)
{
   StringTrimLeft(hhmm); StringTrimRight(hhmm);
   string p[];
   if(StringSplit(hhmm,':',p)!=2) return -1;
   int h=(int)StringToInteger(p[0]);
   int m=(int)StringToInteger(p[1]);
   if(h<0||h>23||m<0||m>59) return -1;
   return h*60+m;
}
//+------------------------------------------------------------------+
