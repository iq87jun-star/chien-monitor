//+------------------------------------------------------------------+
//|                      Chien_MondayTokyo_Prop.mq5                   |
//|  月曜・東京オープン バスケット (theoption検証群のスポット移植):      |
//|    A) EURJPY/AUDJPY/NZDJPY 買い  日曜22:00GMT(=月曜7:00JST)        |
//|         → 月曜21:00GMT(=火曜6:00JST) 時間決済 (保有23h)            |
//|    B) GBPJPY 買い 日曜22:00GMT → 日曜23:00GMT (保有1h)             |
//|                                                                   |
//|  ★使い方: チャートにドロップ → OK。残高自動取得・.set不要。        |
//|                                                                   |
//|  ■ 根拠 (theoption_validation 追補7/12, Dukascopy 2016-2026/09):   |
//|    全ゲート合格(家族内Bonferroni/前後半/年抜きJK/順列)。            |
//|    ネット期待(往復コスト控除後): EURJPY +10.9p / AUDJPY +9.6p /    |
//|    NZDJPY +6.0p / GBPJPY +4.8p per trade。OOS(26年6-9月)もプラス。 |
//|                                                                   |
//|  ⚠ 併走警告: v7系EA(円クロス月曜マルチショット)と同一アノマリー。   |
//|    v7稼働口座では InpLegEURJPY/InpLegGBPJPY を false にして         |
//|    AUDJPY/NZDJPY(v7未使用銘柄)のみ追加するか、別口座で運用する。    |
//|  ⚠ 本資金前にデモ必須。週明けのスプレッド拡大はcap+再試行で防御。    |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.01"
#property strict
#property description "Monday Tokyo-open basket (spot port of validated binary anomalies). Entry Sun 22:00 GMT, time-based exits (23h cross-JPY / 1h GBPJPY). ATR catastrophe SL, daily/floor guards, push notify."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

input group "=== レッグON/OFF (v7併走口座ではEURJPY/GBPJPYをOFF) ==="
input bool   InpLegEURJPY = true;
input bool   InpLegAUDJPY = true;
input bool   InpLegNZDJPY = true;
input bool   InpLegGBPJPY = true;

input group "=== リスク(1トレードあたり・災害SL到達時の損失%) ==="
input double InpRiskEURJPY = 0.30;
input double InpRiskAUDJPY = 0.30;
input double InpRiskNZDJPY = 0.25;
input double InpRiskGBPJPY = 0.15;

input group "=== スケジュール(GMT基準・JST=GMT+9固定なのでDST無関係) ==="
input int    InpEntryHourGMT    = 22;   // 日曜のこの時(GMT)に成行買い(=月曜7:00 JST)
input int    InpEntryWindowMin  = 25;   // 窓: この分数内にスプレッド条件を満たせば執行、過ぎたら今週は見送り
input int    InpExitHourGMT_ON  = 21;   // 月曜のこの時(GMT)にクロス円3本を決済(=火曜6:00 JST)
input int    InpExitHourGMT_GBP = 23;   // 日曜のこの時(GMT)にGBPJPYを決済(=月曜8:00 JST)

input group "=== 執行防御 ==="
input string InpSpreadCapsPips  = "EURJPY:3.0,AUDJPY:3.0,NZDJPY:4.0,GBPJPY:4.0"; // 超過中は待機(窓内のみ)
input double InpCatastropheATR  = 2.5;   // 災害SL = ATR(H1,24)×この係数
input double InpMinStopPips     = 15.0;
input double InpMaxStopPips     = 400.0;

input group "=== 口座ガード(prop規約準拠・既存EA群と同値) ==="
input double InpDailyStopPct    = 4.0;   // 日次−この%で当日全決済+新規停止(規約−5%の手前)
input double InpAccountFloorPct = 9.0;   // 基準残高−この%で恒久停止(失格−10%の手前)
input double InpProfitStopPct   = 8.0;   // 基準残高+この%で新規停止(フェーズ通過圏)
input double InpInitialBalance  = 0.0;   // 0=初回アタッチ時の残高を端末に永続保存

input group "=== 通知(MT5モバイル, 要MetaQuotes ID) ==="
input bool   InpNotifyEnable    = true;

input long   InpMagic           = 261026;

CTrade gTrade;
string SYMS[4] = {"EURJPY","AUDJPY","NZDJPY","GBPJPY"};

bool LegOn(int i){ bool f[4]={InpLegEURJPY,InpLegAUDJPY,InpLegNZDJPY,InpLegGBPJPY}; return f[i]; }
double LegRisk(int i){ double r[4]={InpRiskEURJPY,InpRiskAUDJPY,InpRiskNZDJPY,InpRiskGBPJPY}; return r[i]; }
bool IsGBP(int i){ return i==3; }

//--- 基準残高(再アタッチ耐性: GlobalVariableに永続)
double BaseBalance()
{
   string key = "ChienMT_base_" + (string)AccountInfoInteger(ACCOUNT_LOGIN);
   if(InpInitialBalance > 0.0) return InpInitialBalance;
   if(GlobalVariableCheck(key)) return GlobalVariableGet(key);
   double b = AccountInfoDouble(ACCOUNT_BALANCE);
   GlobalVariableSet(key, b);
   return b;
}

void Notify(string msg)
{
   Print("[MondayTokyo] ", msg);
   if(InpNotifyEnable)
      if(!SendNotification("MondayTokyo: " + msg))
         PrintFormat("[NOTIFY失敗 err=%d] %s (ツール→オプション→通知のMetaQuotes ID設定を確認)", GetLastError(), msg);
}

//--- 実行ログCSV(共有Files: 週次突合の自動回収用。列: 時刻GMT,イベント,銘柄,ロット,SLpips,スプレッドpips,equity)
void LogCsv(string ev, string sym, double lot, double slp, double spr)
{
   string fn = "ChienMT_log_" + (string)AccountInfoInteger(ACCOUNT_LOGIN) + ".csv";
   int h = FileOpen(fn, FILE_COMMON | FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(h == INVALID_HANDLE) return;
   FileSeek(h, 0, SEEK_END);
   if(FileTell(h) == 0) FileWriteString(h, "time_gmt,event,symbol,lot,sl_pips,spread_pips,equity\n");
   FileWriteString(h, StringFormat("%s,%s,%s,%.2f,%.1f,%.2f,%.0f\n",
      TimeToString(TimeGMT(), TIME_DATE | TIME_SECONDS), ev, sym, lot, slp, spr,
      AccountInfoDouble(ACCOUNT_EQUITY)));
   FileClose(h);
}

//--- 業者の実銘柄名に解決(サフィックス対応: 既存EA群と同方式)
string Resolve(string base)
{
   if(SymbolSelect(base, true)) return base;
   int total = SymbolsTotal(false);
   for(int k = 0; k < total; k++)
   {
      string s = SymbolName(k, false);
      if(StringFind(s, base) == 0){ SymbolSelect(s, true); return s; }
   }
   return "";
}

double SpreadCapPips(string base)
{
   string parts[];
   int n = StringSplit(InpSpreadCapsPips, ',', parts);
   for(int k = 0; k < n; k++)
   {
      string kv[];
      if(StringSplit(parts[k], ':', kv) == 2 && kv[0] == base) return StringToDouble(kv[1]);
   }
   return 4.0;
}

double PipSize(string sym)
{
   int d = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   return (d == 3 || d == 5) ? 10 * SymbolInfoDouble(sym, SYMBOL_POINT) : SymbolInfoDouble(sym, SYMBOL_POINT);
}

double SpreadPips(string sym)
{
   return (SymbolInfoDouble(sym, SYMBOL_ASK) - SymbolInfoDouble(sym, SYMBOL_BID)) / PipSize(sym);
}

//--- 災害SL幅(pips)
double StopPips(string sym)
{
   double atr[1];
   int h = iATR(sym, PERIOD_H1, 24);
   if(h == INVALID_HANDLE || CopyBuffer(h, 0, 1, 1, atr) != 1) return InpMaxStopPips;
   double p = atr[0] / PipSize(sym) * InpCatastropheATR;
   return MathMin(MathMax(p, InpMinStopPips), InpMaxStopPips);
}

//--- ロット: リスク%・SL幅から算定(ティックバリュー経路+名目経路の低い方=docs/153の健全性方式)
double CalcLot(string sym, double riskPct, double slPips)
{
   double riskMoney = AccountInfoDouble(ACCOUNT_BALANCE) * riskPct / 100.0;
   double tv  = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE);
   double ts  = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE);
   double lot1 = 0, lot2 = 0;
   if(tv > 0 && ts > 0)
      lot1 = riskMoney / (slPips * PipSize(sym) / ts * tv);
   double contract = SymbolInfoDouble(sym, SYMBOL_TRADE_CONTRACT_SIZE);
   double usdjpy = SymbolInfoDouble(Resolve("USDJPY"), SYMBOL_BID);
   if(contract > 0 && usdjpy > 0)  // 円クロスのpip価値(口座通貨USD想定): contract×pip / USDJPY
      lot2 = riskMoney / (slPips * PipSize(sym) * contract / usdjpy);
   double lot = (lot1 > 0 && lot2 > 0) ? MathMin(lot1, lot2) : MathMax(lot1, lot2);
   double step = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX);
   lot = MathFloor(lot / step) * step;
   return MathMin(MathMax(lot, vmin), vmax);
}

bool HasPosition(string sym)
{
   for(int k = PositionsTotal() - 1; k >= 0; k--)
   {
      ulong t = PositionGetTicket(k);
      if(PositionSelectByTicket(t) && PositionGetInteger(POSITION_MAGIC) == InpMagic
         && PositionGetString(POSITION_SYMBOL) == sym) return true;
   }
   return false;
}

//--- 今週すでに建てた/試みたか(週キーをGlobalVariableに記録)
long WeekKey(datetime gmt){ return (long)((gmt - 4 * 86400) / (7 * 86400)); } // 木曜起点→日曜開始週
bool DoneThisWeek(string base, datetime gmt)
{
   string key = "ChienMT_wk_" + base + "_" + (string)AccountInfoInteger(ACCOUNT_LOGIN);
   return GlobalVariableCheck(key) && (long)GlobalVariableGet(key) == WeekKey(gmt);
}
void MarkDone(string base, datetime gmt)
{
   string key = "ChienMT_wk_" + base + "_" + (string)AccountInfoInteger(ACCOUNT_LOGIN);
   GlobalVariableSet(key, (double)WeekKey(gmt));
}

//--- 日次ガード用
double gDayStartEquity = 0; int gDayOfYear = -1; bool gHaltedToday = false;

int OnInit()
{
   gTrade.SetExpertMagicNumber(InpMagic);
   gTrade.SetDeviationInPoints(30);
   EventSetTimer(15);
   Notify(StringFormat("起動 v1.01 基準残高=%.0f", BaseBalance()));
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){ EventKillTimer(); }

void CloseAllBasket(string reason)
{
   for(int k = PositionsTotal() - 1; k >= 0; k--)
   {
      ulong t = PositionGetTicket(k);
      if(PositionSelectByTicket(t) && PositionGetInteger(POSITION_MAGIC) == InpMagic)
         gTrade.PositionClose(t);
   }
   if(reason != ""){ Notify("全決済: " + reason); LogCsv("guard", reason, 0, 0, 0); }
}

void OnTimer()
{
   datetime gmt = TimeGMT();
   MqlDateTime g; TimeToStruct(gmt, g);

   //--- 日次リセット&ガード
   if(g.day_of_year != gDayOfYear)
   { gDayOfYear = g.day_of_year; gDayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY); gHaltedToday = false; }
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   double base = BaseBalance();
   if(!gHaltedToday && gDayStartEquity > 0 && eq <= gDayStartEquity * (1 - InpDailyStopPct / 100.0))
   { gHaltedToday = true; CloseAllBasket(StringFormat("日次-%.1f%%ガード", InpDailyStopPct)); }
   static bool floorHit = false;
   if(!floorHit && eq <= base * (1 - InpAccountFloorPct / 100.0))
   { floorHit = true; CloseAllBasket(StringFormat("フロア-%.1f%%恒久停止", InpAccountFloorPct)); }
   if(floorHit || gHaltedToday) return;
   bool profitStop = (eq >= base * (1 + InpProfitStopPct / 100.0));

   //--- 決済(時間ベース)
   // GBPJPY: 日曜23:00GMT以降 / クロス円: 月曜21:00GMT以降(窓は3時間みる)
   for(int i = 0; i < 4; i++)
   {
      if(!LegOn(i)) continue;
      string sym = Resolve(SYMS[i]);
      if(sym == "" || !HasPosition(sym)) continue;
      bool exitNow = false;
      if(IsGBP(i))  exitNow = (g.day_of_week == 0 && g.hour >= InpExitHourGMT_GBP) || g.day_of_week == 1;
      else          exitNow = (g.day_of_week == 1 && g.hour >= InpExitHourGMT_ON) || g.day_of_week == 2;
      if(exitNow)
      {
         for(int k = PositionsTotal() - 1; k >= 0; k--)
         {
            ulong t = PositionGetTicket(k);
            if(PositionSelectByTicket(t) && PositionGetInteger(POSITION_MAGIC) == InpMagic
               && PositionGetString(POSITION_SYMBOL) == sym)
               if(gTrade.PositionClose(t)){ Notify(sym + " 時間決済"); LogCsv("exit", sym, 0, 0, SpreadPips(sym)); }
         }
      }
   }

   //--- エントリー(日曜 InpEntryHourGMT:00〜+WindowMin)
   if(g.day_of_week != 0 || g.hour != InpEntryHourGMT || g.min > InpEntryWindowMin) return;
   if(profitStop) return;
   for(int i = 0; i < 4; i++)
   {
      if(!LegOn(i)) continue;
      string base_s = SYMS[i];
      string sym = Resolve(base_s);
      if(sym == "" || HasPosition(sym) || DoneThisWeek(base_s, gmt)) continue;
      if(SpreadPips(sym) > SpreadCapPips(base_s))
      {
         if(g.min >= InpEntryWindowMin - 1){ LogCsv("skip_spread", sym, 0, 0, SpreadPips(sym)); MarkDone(base_s, gmt); Notify(sym + " スプレッド超過で今週見送り"); }
         continue;   // 窓内の次のタイマーで再試行
      }
      double slp = StopPips(sym);
      double lot = CalcLot(sym, LegRisk(i), slp);
      if(lot <= 0) continue;
      double ask = SymbolInfoDouble(sym, SYMBOL_ASK);
      double sl  = ask - slp * PipSize(sym);
      if(gTrade.Buy(lot, sym, 0.0, sl, 0.0, "MondayTokyo"))
      {
         MarkDone(base_s, gmt);
         Notify(StringFormat("%s 買い %.2flot SL=%.1fpips", sym, lot, slp));
         LogCsv("entry", sym, lot, slp, SpreadPips(sym));
      }
   }
}
//+------------------------------------------------------------------+
