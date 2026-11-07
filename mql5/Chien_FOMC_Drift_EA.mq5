//+------------------------------------------------------------------+
//|                                     Chien_FOMC_Drift_EA.mq5        |
//|   G3 = FOMC声明前24hドリフト（Lucca–Moench pre-FOMC drift）         |
//|   ★ステータス: ADOPT（edge12 6/6ゲート全通過, docs/81-82）。        |
//|     探索バッチから直接ADOPTが出たのは本プロジェクト初。但し規律     |
//|     どおり本資金前にデモ前進検証必須（docs/53 §5。年8イベントゆえ   |
//|     3〜4イベントが backtest 分布内かを確認してから資金化口座へ）。   |
//|                                                                   |
//|   検証実績（Dukascopy H1 10年, 2016-2026, docs/82）:                |
//|     純益+16.1% / maxDD−2.9% / n=79 / 勝率59% / 頑健p=0.005(Bonferroni|
//|     通過) / JKmax=0.058 / IS+5.7→OOS+9.9(減衰なし) / プラセボ−4.2%   |
//|     / コスト×4でも+13.4% / スワップ4bps晩でも+14.8% / ρv7=0.16       |
//|     / ρE-Mon=−0.12（既存全エッジと無相関の衛星）                    |
//|                                                                   |
//|   v1.10(docs/214・2026-09-05): EURUSD を第2銘柄として追加。        |
//|     Dukascopy H1 2003-2026 n=187 で FOMC前24h EURUSDロング=LEAD    |
//|     (+12.2bps/event, 同曜日非事象日プール比 p=0.0012, JK 0.005,    |
//|     IS+16.2/OOS+8.3, 2016以降のみ+6.4bps p=0.10 = 減衰あり)。      |
//|     ロジックは同一(_Symbol 汎用)。EURUSD チャートに別インスタンス   |
//|     としてアタッチし、InpMagic を 930613 にする(US500 は 930612)。  |
//|     期待値は 1x で +0.5〜1%/年の衛星。G3(株)の同日 FX 版であり    |
//|     独立エッジではない。MT5 バックテストは未実施(要デモ)。         |
//|   注記(docs/214 §4.2): G3 US500 の「FOMC 固有」成分は同曜日の     |
//|     非事象日プール比では p=0.12〜0.18。符号反転検定(docs/82)では   |
//|     再現(p=0.002)。ADOPT は維持するが、統計的には未確定と記録。    |
//|   14074882(季節RG3 EA)には G3 US500 が InpG3Enable 既定ON で内蔵   |
//|     済み。同口座で本 EA を使うのは EURUSD チャートのみ(US500 二重  |
//|     建て防止)。                                                  |
//|                                                                   |
//|   ロジック（docs/81 §1 で事前登録した窓のまま・最適化していない）:  |
//|     ・US500 チャートに1枚アタッチ。                               |
//|     ・FOMC声明日（入力リスト・Fed公式カレンダーから毎年更新）の     |
//|       前日14:00 ET に LONG → 当日13:55 ET に手仕舞い。              |
//|       （検証は14:00決済。5分早い手仕舞いは発表ボラを取らない保守側）|
//|     ・ET変換は DST 自動（米国: 3月第2日曜〜11月第1日曜）。          |
//|     ・年8回・1晩のみ保有 → スワップ/コスト影響は実測済みで微小。    |
//|                                                                   |
//|   サイズ: ATR(D1)動いた時の損益 ≒ InpEventRiskPct% of equity。      |
//|     既定1.0% ≒ 検証の素サイズ（10年maxDD−2.9%）。2倍でも−6%級。     |
//|   ガード: 災害SL=2.5×ATR(D1) / 口座フロア−8%全停止 / 異常スプレッド  |
//|     スキップ（プロジェクト標準）。                                  |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.10"
#property strict
#property description "G3 pre-FOMC drift: US500 (ADOPT, edge12 6/6) and EURUSD (LEAD, docs/214). Long 24h before FOMC statement, exit 13:55 ET. One chart per symbol, distinct magic. Demo-first per project discipline."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>
#include <Trade/SymbolInfo.mqh>

input group "=== ステータス（規律） ==="
input bool   InpAcknowledgeDemoFirst = true; // ADOPTでも本資金前デモ必須=trueで承認(docs/53 §5)

input group "=== FOMC声明日（ET・毎年Fed公式から更新） ==="
input string InpFomcDates = "2026.01.28,2026.03.18,2026.04.29,2026.06.17,2026.07.29,2026.09.16,2026.10.28,2026.12.09";
                                            // 定例会合2日目(声明14:00 ET)。臨時会合は対象外(docs/81)
input int    InpEntryHourET   = 14;         // エントリ=声明24h前(前日のこの時刻ET)
input int    InpExitMinBefore = 5;          // 声明何分前に手仕舞うか(検証=0分。既定5分は保守側)
input int    InpMinRemainHours = 2;         // 窓の残りがこれ未満なら遅延エントリしない

input group "=== リスク ==="
input double InpEventRiskPct      = 1.0;    // 1イベントのリスク予算(ATR(D1)変動≒この%損益)。DD余白が小さい口座は0.5(docs/217)
                                            //   1.0≒検証素サイズ(10年maxDD−2.9%)
input double InpAccountFloorDDPct = 8.0;    // 総合−8%で全停止(−10%枠の内側)
input double InpInitialBalance    = 0.0;    // 0=口座残高を自動取得
input bool   InpCloseAllOnGuard   = true;

input group "=== SL/サイズ ==="
input int    InpAtrPeriodD1    = 14;        // 日次ボラ代理 ATR(D1,14)
input double InpCatastropheATR = 2.5;       // 災害SL = 2.5×ATR(D1)
input double InpMinLot = 0.01;
input double InpMaxLot = 50.0;

input group "=== Execution ==="
input double InpMaxSpreadBps   = 5.0;       // スプレッドがこれ(bps)超なら見送り(US500 検証1bps×安全率。EURUSD 実測0.3-1bps・docs/216)
input long   InpMagic          = 930612;    // edge12/G3: US500=930612 / EURUSD=930613(銘柄ごとに変える)
input int    InpSlippagePoints = 30;
input bool   InpVerboseLog     = true;

//==================================================================
CTrade        trade;
CPositionInfo posinfo;
CSymbolInfo   sym;
int      hAtrD1 = INVALID_HANDLE;
double   g_initBal = 0.0;
bool     g_halted = false;
datetime g_winStartUtc[64];                 // 各イベントの窓開始(UTC)
datetime g_winEndUtc[64];                   // 各イベントの窓終了(UTC)
int      g_nWin = 0;
datetime g_enteredWin = 0;                  // 二重エントリ防止(同一窓で1回だけ)

//------------------------------------------------------------------
// 米国DST: 3月第2日曜 02:00 ET 〜 11月第1日曜 02:00 ET。
// UTC基準では DST開始=3月第2日曜07:00UTC / 終了=11月第1日曜06:00UTC。
datetime NthSundayUtc(int year,int month,int nth,int utcHour)
{
   MqlDateTime t; ZeroMemoryStruct(t);
   t.year=year; t.mon=month; t.day=1; t.hour=0;
   datetime d1=StructToTime(t);
   MqlDateTime w; TimeToStruct(d1,w);
   int firstSun = 1 + ((7 - w.day_of_week) % 7);
   int day = firstSun + 7*(nth-1);
   t.day=day; t.hour=utcHour;
   return StructToTime(t);
}
void ZeroMemoryStruct(MqlDateTime &t){ t.year=0;t.mon=0;t.day=0;t.hour=0;t.min=0;t.sec=0;t.day_of_week=0;t.day_of_year=0; }

bool IsDstUS(datetime utc)
{
   MqlDateTime t; TimeToStruct(utc,t);
   datetime dstStart=NthSundayUtc(t.year,3,2,7);   // 3月第2日曜 07:00 UTC
   datetime dstEnd  =NthSundayUtc(t.year,11,1,6);  // 11月第1日曜 06:00 UTC
   return (utc>=dstStart && utc<dstEnd);
}
// ETの暦日+時刻 → UTC（DST自動）。
datetime EtToUtc(int year,int mon,int day,int hourEt,int minEt)
{
   MqlDateTime t; ZeroMemoryStruct(t);
   t.year=year; t.mon=mon; t.day=day; t.hour=hourEt; t.min=minEt;
   datetime asUtc=StructToTime(t);                 // まず素朴にUTC扱い
   int offset = IsDstUS(asUtc+5*3600) ? 4 : 5;     // EDT=UTC-4 / EST=UTC-5(境界週は±1h誤差あり=FOMC日には無い)
   return asUtc + offset*3600;
}

//------------------------------------------------------------------
bool ParseFomcWindows()
{
   g_nWin=0;
   string parts[];
   int n=StringSplit(InpFomcDates,',',parts);
   for(int i=0;i<n && g_nWin<64;i++)
   {
      string s=parts[i];
      StringTrimLeft(s); StringTrimRight(s);
      if(StringLen(s)<8) continue;
      string ymd[];
      if(StringSplit(s,'.',ymd)!=3) continue;
      int y=(int)StringToInteger(ymd[0]), m=(int)StringToInteger(ymd[1]), d=(int)StringToInteger(ymd[2]);
      if(y<2020 || m<1 || m>12 || d<1 || d>31) continue;
      datetime ann = EtToUtc(y,m,d,InpEntryHourET,0);          // 声明=当日14:00 ET
      g_winStartUtc[g_nWin]=ann-24*3600;                       // 前日14:00 ET
      g_winEndUtc[g_nWin]  =ann-InpExitMinBefore*60;           // 13:55 ET(既定)
      g_nWin++;
   }
   return (g_nWin>0);
}

//------------------------------------------------------------------
int OnInit()
{
   if(!InpAcknowledgeDemoFirst)
   {
      Print("[STOP] ADOPTでも本資金前デモ必須(docs/53 §5)。InpAcknowledgeDemoFirst=trueで承認してください。");
      return INIT_FAILED;
   }
   if(!sym.Name(_Symbol)){ Print("Symbol init failed"); return INIT_FAILED; }
   if(!ParseFomcWindows()){ Print("[STOP] FOMC日程の解析失敗: ",InpFomcDates); return INIT_FAILED; }
   g_initBal=(InpInitialBalance>0.0)? InpInitialBalance : AccountInfoDouble(ACCOUNT_BALANCE);
   if(g_initBal<=0.0) g_initBal=AccountInfoDouble(ACCOUNT_EQUITY);
   hAtrD1=iATR(_Symbol,PERIOD_D1,InpAtrPeriodD1);
   if(hAtrD1==INVALID_HANDLE){ Print("ATR(D1) handle failed"); return INIT_FAILED; }
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);
   PrintFormat("[INIT G3-FOMC/%s] ADOPT(demo-first). events=%d eventRisk=%.2f%% floorDD=%.1f%% exit=声明%d分前",
               _Symbol,g_nWin,InpEventRiskPct,InpAccountFloorDDPct,InpExitMinBefore);
   if(InpVerboseLog)
      Print("[NOTE G3] US500に1枚のみ。FOMC日程は毎年 federalreserve.gov の定例会合カレンダーで更新すること。",
            "臨時会合・日程変更時は対象外(入力リストに無い日は何もしない)。");
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){ if(hAtrD1!=INVALID_HANDLE) IndicatorRelease(hAtrD1); }

//------------------------------------------------------------------
double AtrD1()
{
   double a[1];
   if(CopyBuffer(hAtrD1,0,1,1,a)<1) return 0.0;
   return a[0];
}
double CalcLots()
{
   double atr=AtrD1(); if(atr<=0) return 0.0;
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   double riskMoney=equity*(InpEventRiskPct/100.0);
   double tickValue=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double tickSize =SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(tickValue<=0 || tickSize<=0) return 0.0;
   double moneyPerLotPerAtr=(atr/tickSize)*tickValue;
   if(moneyPerLotPerAtr<=0) return 0.0;
   double lots=riskMoney/moneyPerLotPerAtr;
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   double vmin=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double vmax=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   if(step>0) lots=MathFloor(lots/step)*step;
   lots=MathMin(lots,MathMin(InpMaxLot,vmax));
   if(lots<MathMax(InpMinLot,vmin)) return 0.0;
   return lots;
}
bool HavePosition()
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Symbol()==_Symbol && posinfo.Magic()==InpMagic) return true;
   }
   return false;
}
void CloseMine(string why)
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Symbol()!=_Symbol || posinfo.Magic()!=InpMagic) continue;
      if(trade.PositionClose(tk)){ if(InpVerboseLog) PrintFormat("[CLOSE %s] %s %I64u",why,_Symbol,tk); }
   }
}
double SpreadBps()
{
   double ask=sym.Ask(), bid=sym.Bid();
   if(ask<=0 || bid<=0) return 1e9;
   return (ask-bid)/((ask+bid)/2.0)*1e4;
}

//------------------------------------------------------------------
void OnTick()
{
   sym.RefreshRates();
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);

   // 総合ガード(−10%枠の内側)
   double floorEq=g_initBal*(1.0-InpAccountFloorDDPct/100.0);
   if(equity<=floorEq && !g_halted)
   {
      g_halted=true;
      if(InpCloseAllOnGuard) CloseMine("EQUITY_FLOOR");
      PrintFormat("[HALT] equity %.2f <= floor %.2f",equity,floorEq);
   }
   if(g_halted){ if(InpCloseAllOnGuard) CloseMine("HALTED"); return; }

   datetime now=TimeGMT();
   int active=-1;
   for(int i=0;i<g_nWin;i++)
      if(now>=g_winStartUtc[i] && now<g_winEndUtc[i]){ active=i; break; }

   bool have=HavePosition();
   if(active<0)
   {
      if(have) CloseMine("WINDOW_END");     // 13:55 ET(既定)で手仕舞い
      return;
   }
   if(have) return;                          // 窓内・保有中=何もしない
   if(g_enteredWin==g_winStartUtc[active]) return;   // 同一窓で再エントリしない(SL後など)

   // 遅延エントリ制限: 残り時間が短すぎるならコストに見合わない
   if((g_winEndUtc[active]-now) < InpMinRemainHours*3600)
   { if(InpVerboseLog) Print("[SKIP] 窓の残り<",InpMinRemainHours,"h"); return; }
   if(SpreadBps()>InpMaxSpreadBps)
   { if(InpVerboseLog) PrintFormat("[SKIP] spread %.1fbps > %.1f",SpreadBps(),InpMaxSpreadBps); return; }

   double atr=AtrD1(); if(atr<=0) return;
   double lots=CalcLots();
   if(lots<InpMinLot){ if(InpVerboseLog) Print("[SKIP] lots<min"); return; }
   int d=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   double e=sym.Ask();
   double sl=NormalizeDouble(e-InpCatastropheATR*atr,d);
   if(trade.Buy(lots,_Symbol,0.0,sl,0.0,"G3_FOMC_LONG"))
   {
      g_enteredWin=g_winStartUtc[active];
      PrintFormat("[ENTRY G3/%s] LONG lots=%.2f SL=%.2f atrD1=%.2f 窓=%s→%s",
                  _Symbol,lots,sl,atr,
                  TimeToString(g_winStartUtc[active]),TimeToString(g_winEndUtc[active]));
   }
   else PrintFormat("[ENTRY FAIL] ret=%d %s",trade.ResultRetcode(),trade.ResultRetcodeDescription());
}
//+------------------------------------------------------------------+
//| 残存リスク(誠実な記録):                                          |
//|  ・ADOPT=10年バックテスト全ゲート通過であり将来の保証ではない。    |
//|    年8標本ゆえフォワード1-2年で統計判定は不可=分布内かの確認のみ。 |
//|  ・期待値は素サイズで≈+1.5%/年と小さい。価値は無相関衛星(ρv7=0.16, |
//|    ρE-Mon=−0.12)・年8日しか市場に居ない点。誇張しない(docs/82 §3)。 |
//|  ・FOMC日程は手動更新(毎年12月頃に翌年分をFed公式で確認)。臨時会合 |
//|    は対象外。日程が間違っていれば「ただの1晩ロング」になる。       |
//|  ・DST境界週のET変換は±1hの誤差があり得る設計(FOMC週には重ならない |
//|    ことを確認済みだが、毎年の日程更新時に3月/11月の会合は要注意)。 |
//|  ・ブローカーのUS500銘柄名/取引時間/1晩スワップはデモで実測する事。 |
//+------------------------------------------------------------------+
