//+------------------------------------------------------------------+
//|                              Chien_GoldToM_Satellite_EA.mq5        |
//|   金(XAUUSD) turn-of-month LONG = 規約クリーンな無相関の小衛星     |
//|                                                                   |
//|   ★ステータス: 弱LEAD(3/6ゲート・順列p0.057, docs/64)。検証済み    |
//|     エッジ「ではない」。本資金禁止＝デモ/極小サイズ(≤5–8%衛星)で    |
//|     のみ運用し、正の期待値・無相関(E-Mon −0.11)・低DD(素−13.1%)が   |
//|     フォワードで再現するかを確認する目的。詳細 docs/64, docs/29。   |
//|                                                                   |
//|   なぜ規約クリーンか:                                              |
//|     金は v4(FX) とも E-Mon(株価指数) とも別資産＝同一/高相関銘柄の   |
//|     反対両建て(FTMO/FundedNext禁止・口座間も)を構造的に作らない。   |
//|     金SHORTは一切建てない(LONGのみ)。                              |
//|                                                                   |
//|   ロジック(docs/64 の XAUUSD ToM-L を実装):                       |
//|     ・対象: XAUUSD(金) を D1 にアタッチ(1チャート1インスタンス)。  |
//|     ・"turn-of-month ウィンドウ" = 月末最終営業日 ＋ 月初3営業日。 |
//|       新D1バーでウィンドウ内かを判定し:                            |
//|         in-window かつ ポジ無し → 成行LONG(1ポジ)                  |
//|         out-window かつ ポジ有り → 手仕舞い                        |
//|       (=最終営業日に建て、月初3営業日経過後に閉じる。1ポジで窓を   |
//|        またぐ＝低コスト・2分超保有でFundedNext短時間フラグ回避)。  |
//|     ・LONGのみ(アノマリーはToM-LONG)。                             |
//|     ・災害SL = InpCatastropheATR × ATR(D1)(広く置く保険)。         |
//|                                                                   |
//|   ガード(−DD枠の内側・docs/02と同思想):                            |
//|     ・当日 −InpDailyStopPct(既定4%) で全決済＋当日新規停止。       |
//|     ・総合 −InpAccountFloorDDPct(既定8%) で全決済＋EA恒久停止。    |
//|     ・1ポジ・SL必須・ナンピン無し・LONG限定 → 禁止手法に非該当。   |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.00"
#property strict
#property description "Gold (XAUUSD) turn-of-month LONG satellite. WEAK-LEAD/DEMO only — NOT a confirmed edge. Rules-clean (no FX/index hedge conflict). Long-only, single position, guarded."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>
#include <Trade/SymbolInfo.mqh>

input group "=== ステータス警告 ==="
input bool   InpAcknowledgeLEAD   = true;   // これは弱LEAD(未検証)。デモ/極小サイズのみ=trueで承認

input group "=== リスク/サイズ ==="
input double InpTradeRiskPct      = 0.30;   // 1トレードのリスク%(災害SL基準)。衛星≤5–8%相当の小サイズ
input double InpDailyStopPct      = 4.0;    // 当日 -4% で全決済＋当日新規停止(規則-5%の手前)
input double InpAccountFloorDDPct = 8.0;    // 総合 -8% で全停止(-10%枠の内側)
input double InpInitialBalance    = 0.0;    // 0=口座残高を自動取得(推奨) / 手動なら口座額
input bool   InpCloseAllOnGuard   = true;

input group "=== turn-of-month ウィンドウ ==="
input int    InpFirstBizDays      = 3;      // 月初の保有営業日数(既定3)
input bool   InpIncludeLastBizDay = true;   // 月末最終営業日も含める(既定ON)

input group "=== サイズ/SL ==="
input int    InpAtrPeriodD1    = 14;        // 災害SL用 ATR(D1)
input double InpCatastropheATR = 2.5;       // 災害SL = 2.5×ATR(D1)
input double InpMinLot = 0.01;
input double InpMaxLot = 50.0;

input group "=== Execution ==="
input long   InpMagic          = 640301;    // GoldToM 衛星(他レッグと分離)
input int    InpSlippagePoints = 30;
input bool   InpVerboseLog     = true;

//==================================================================
CTrade        trade;
CPositionInfo posinfo;
CSymbolInfo   sym;

double   g_initBal = 0.0;
int      hAtrD1 = INVALID_HANDLE;
datetime g_lastDayBar = 0;
bool     g_halted = false;       // 恒久停止(フロア抵触)
int      g_dailyStopDay = -1;    // 当日ストップ済みの日(YYYYMMDD)
double   g_dayStartEquity = 0.0;
int      g_curDayKey = -1;

int OnInit()
{
   if(!InpAcknowledgeLEAD)
   {
      Print("[STOP] 金ToMは弱LEAD(未検証)。InpAcknowledgeLEAD=true(デモ/極小のみ)で承認してください。");
      return INIT_FAILED;
   }
   if(!sym.Name(_Symbol)){ Print("Symbol init failed"); return INIT_FAILED; }

   g_initBal = (InpInitialBalance>0.0)? InpInitialBalance : AccountInfoDouble(ACCOUNT_BALANCE);
   if(g_initBal<=0.0) g_initBal=AccountInfoDouble(ACCOUNT_EQUITY);

   hAtrD1=iATR(_Symbol,PERIOD_D1,InpAtrPeriodD1);
   if(hAtrD1==INVALID_HANDLE){ Print("ATR(D1) handle failed"); return INIT_FAILED; }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   PrintFormat("[INIT GoldToM/%s] WEAK-LEAD demo satellite. risk=%.2f%%/trade dailyStop=%.1f%% floorDD=%.1f%% window=last%s+first%d",
               _Symbol,InpTradeRiskPct,InpDailyStopPct,InpAccountFloorDDPct,
               (InpIncludeLastBizDay?"BizDay":"(off)"),InpFirstBizDays);
   if(InpVerboseLog)
      Print("[NOTE GoldToM] 検証済みエッジではない(弱LEAD 3/6, 順列p0.057, docs/64)。金=FX/指数と非衝突=規約クリーン。"
            "LONG限定・1ポジ・SL必須。デモで正期待値・無相関・低DDの再現を確認するまで本資金禁止。");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason){ if(hAtrD1!=INVALID_HANDLE) IndicatorRelease(hAtrD1); }

//==================================================================
// 指定日が "turn-of-month ウィンドウ" 内か(営業日=Mon..Fri で近似)。
bool IsWeekday(int y,int m,int d)
{
   MqlDateTime s; s.year=y; s.mon=m; s.day=d; s.hour=12; s.min=0; s.sec=0;
   datetime t=StructToTime(s);
   MqlDateTime r; TimeToStruct(t,r);
   return (r.day_of_week>=1 && r.day_of_week<=5); // 1=Mon..5=Fri
}
int DaysInMonth(int y,int m)
{
   int dim[12]={31,28,31,30,31,30,31,31,30,31,30,31};
   if(m==2 && ((y%4==0 && y%100!=0)||(y%400==0))) return 29;
   return dim[m-1];
}
bool InToMWindow(datetime t)
{
   MqlDateTime r; TimeToStruct(t,r);
   int y=r.year, m=r.mon, d=r.day;
   if(!IsWeekday(y,m,d)) return false; // 週末は対象外

   // (a) 月初 InpFirstBizDays 営業日に入っているか
   int biz=0;
   for(int dd=1; dd<=DaysInMonth(y,m); dd++)
   {
      if(IsWeekday(y,m,dd)) biz++;
      if(dd==d) { if(biz<=InpFirstBizDays) return true; else break; }
   }

   // (b) 月末最終営業日か
   if(InpIncludeLastBizDay)
   {
      int lastBiz=0;
      for(int dd=DaysInMonth(y,m); dd>=1; dd--){ if(IsWeekday(y,m,dd)){ lastBiz=dd; break; } }
      if(d==lastBiz) return true;
   }
   return false;
}

double AtrD1()
{
   double a[1];
   if(CopyBuffer(hAtrD1,0,1,1,a)<1) return 0.0;
   return a[0];
}

// リスク%/災害SL距離 でロット算出(切り捨て=リスク超過防止)。
double CalcLots(double stopDist)
{
   if(stopDist<=0) return 0.0;
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   double riskMoney=equity*(InpTradeRiskPct/100.0);
   double tickValue=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double tickSize =SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(tickValue<=0 || tickSize<=0) return 0.0;
   double moneyPerLot=(stopDist/tickSize)*tickValue;  // 1ロットがSL距離動いた時の損失
   if(moneyPerLot<=0) return 0.0;
   double lots=riskMoney/moneyPerLot;
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

void OpenLong()
{
   double atr=AtrD1(); if(atr<=0){ if(InpVerboseLog) Print("[SKIP] atr<=0"); return; }
   double stopDist=InpCatastropheATR*atr;
   double lots=CalcLots(stopDist); if(lots<InpMinLot){ if(InpVerboseLog) Print("[SKIP] lots<min"); return; }
   int d=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   double e=sym.Ask();
   double sl=NormalizeDouble(e-stopDist,d);
   if(trade.Buy(lots,_Symbol,0.0,sl,0.0,"GoldToM_LONG"))
      PrintFormat("[ENTRY GoldToM/%s] LONG lots=%.2f SL=%.3f atrD1=%.3f risk=%.2f%%",
                  _Symbol,lots,sl,atr,InpTradeRiskPct);
   else
      PrintFormat("[ENTRY FAIL] ret=%d %s",trade.ResultRetcode(),trade.ResultRetcodeDescription());
}

//==================================================================
void OnTick()
{
   sym.RefreshRates();
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);

   // 総合フロアガード(恒久停止・-10%枠の内側)
   double floorEq=g_initBal*(1.0-InpAccountFloorDDPct/100.0);
   if(equity<=floorEq && !g_halted)
   {
      g_halted=true;
      if(InpCloseAllOnGuard) CloseMine("EQUITY_FLOOR");
      PrintFormat("[HALT] equity %.2f <= floor %.2f",equity,floorEq);
   }
   if(g_halted){ if(InpCloseAllOnGuard) CloseMine("HALTED"); return; }

   // 当日キー更新(サーバ時間00:00基準) と 当日ストップ判定
   MqlDateTime nt; TimeToStruct(TimeCurrent(),nt);
   int dayKey=nt.year*10000+nt.mon*100+nt.day;
   if(dayKey!=g_curDayKey)
   {
      g_curDayKey=dayKey;
      g_dayStartEquity=equity;   // 当日開始equity起点(docs/01の保守判定)
   }
   if(g_dayStartEquity>0.0)
   {
      double dayDD=(equity-g_dayStartEquity)/g_dayStartEquity*100.0;
      if(dayDD<=-InpDailyStopPct && g_dailyStopDay!=dayKey)
      {
         g_dailyStopDay=dayKey;
         if(InpCloseAllOnGuard) CloseMine("DAILY_STOP");
         PrintFormat("[DAILY STOP] dayDD %.2f%% <= -%.1f%%",dayDD,InpDailyStopPct);
      }
   }

   // 新D1バーだけ評価
   datetime db=(datetime)iTime(_Symbol,PERIOD_D1,0);
   if(db==g_lastDayBar) return;
   g_lastDayBar=db;

   bool inWin=InToMWindow(TimeCurrent());
   bool have=HavePosition();

   if(inWin)
   {
      if(g_dailyStopDay==dayKey) return;     // 当日ストップ中は新規しない
      if(!have) OpenLong();                  // 窓に入った→LONG建て(1ポジ)
   }
   else
   {
      if(have) CloseMine("WINDOW_END");      // 窓を抜けた→手仕舞い
   }
}
//+------------------------------------------------------------------+
//| 残存リスク(誠実な記録):                                          |
//|  ・金ToM-L は弱LEAD=有意水準未達(順列p0.057・JKmax0.179, docs/64)。 |
//|    1年の寄与に偏りがある。本資金禁止・デモ前進検証必須。           |
//|  ・素maxDD−13.1% → 衛星≤5–8%・小risk%で-DD枠の内側に収める設計。   |
//|    実maxDDがデモで想定に収まるか監視し、超えるなら risk% を下げる。 |
//|  ・金は Yahoo期近先物モデル(ロール/スワップ無し)。実CFDの         |
//|    スプレッド/スワップ/ギャップで結果がずれうる→デモで実測。      |
//|  ・E-Mon −0.11/指数β +0.12=無相関だが、分散効果は"緩やか"。劇的    |
//|    ではない点を誇張しない(docs/64 §4)。                            |
//|  ・営業日判定は Mon..Fri 近似(取引所休場日は考慮しない)。祝日の    |
//|    影響は限定的だが、業者カレンダーと差異が出うる。                |
//+------------------------------------------------------------------+
