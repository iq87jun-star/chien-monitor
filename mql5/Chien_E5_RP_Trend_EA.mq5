//+------------------------------------------------------------------+
//|                                Chien_E5_RP_Trend_EA.mq5            |
//|   E5 = リスクパリティ多資産トレンド（金+株価指数の時系列モメンタム） |
//|   ★ステータス: LEAD（検証済みエッジではない）。本資金禁止＝デモ/    |
//|     極小サイズの衛星でのみ運用し、正の期待値とv7低相関がフォワードで |
//|     再現するかを確認する目的。詳細 docs/27, docs/29。               |
//|                                                                   |
//|   ロジック(月次・docs/27 のE5を実装):                              |
//|     ・対象: XAUUSD / US500 / NAS100 / GER40 を1本ずつチャートに    |
//|       アタッチ(v7と同じ"各シンボルに1インスタンス"運用)。          |
//|     ・毎月初(MN1新バー)に時系列モメンタム符号で方向決定:           |
//|         signal = sign( Σ_{L∈{1,3,6,12}} sign( C[1]/C[1+L] − 1 ) )  |
//|       (直近確定月の終値を、過去1/3/6/12ヶ月前と比較した多数決)。   |
//|     ・LONG/SHORT 両方向。signal=0 なら手仕舞いして待機。           |
//|     ・サイズ=リスクパリティ: 各レッグを「月次P&L標準偏差 ≒          |
//|       InpLegMonthlyRiskPct% of equity」に揃える(=低ボラ資産ほど   |
//|       ロット大)。月次ボラ代理に ATR(MN1) を用いる。               |
//|     ・1ヶ月保有→翌月初に再評価(同方向なら継続、逆なら転換)。       |
//|     ・災害SL = InpCatastropheATR × ATR(MN1)(広く置く)。            |
//|                                                                   |
//|   ★−10%口座向け既定: 4レッグ独立・各 0.55%/月 → ポート月次ボラ≈    |
//|     1.1% → 10年想定maxDD ≈ −6%(−10%に4%マージン, docs/29の試算)。   |
//|     ※指数/金CFDの実約定・スワップ・配当調整はデモで要確認。素の     |
//|       バックテストは price index(配当除く)・月次終値モデル。       |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.00"
#property strict
#property description "E5 risk-parity multi-asset TSMOM (gold+indices). LEAD/DEMO satellite — NOT a confirmed edge. Monthly, long/short, risk-budgeted."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>
#include <Trade/SymbolInfo.mqh>

input group "=== ステータス警告 ==="
input bool   InpAcknowledgeLEAD   = true;   // これはLEAD(未検証)。デモ/極小サイズのみ=trueで承認

input group "=== リスク(リスクパリティ・各レッグ独立) ==="
input double InpLegMonthlyRiskPct = 0.55;   // 1レッグの月次P&L目標σ(%of equity)。4レッグ独立で
                                            //   ポート月次ボラ≈0.55×√4/?…実効≈1.1%→maxDD≈-6%(docs/29)
input double InpAccountFloorDDPct = 8.0;    // 総合 -8% で全停止(−10%枠の内側・安全)
input double InpInitialBalance    = 50000.0;// 口座初期残高
input bool   InpCloseAllOnGuard   = true;

input group "=== TSMOM シグナル(月次) ==="
input int    InpLB1 = 1;                    // ルックバック(月)
input int    InpLB2 = 3;
input int    InpLB3 = 6;
input int    InpLB4 = 12;
input bool   InpAllowShort = true;          // SHORTを許可(E5は両方向)

input group "=== サイズ/SL ==="
input int    InpAtrPeriodMN1   = 6;         // 月次ボラ代理 ATR(MN1,6)
input double InpCatastropheATR = 2.5;       // 災害SL = 2.5×ATR(MN1)
input double InpMinLot = 0.01;
input double InpMaxLot = 50.0;

input group "=== Execution ==="
input long   InpMagic          = 930610;    // E5
input int    InpSlippagePoints = 30;
input bool   InpVerboseLog     = true;

//==================================================================
CTrade        trade;
CPositionInfo posinfo;
CSymbolInfo   sym;

int      hAtrMN1 = INVALID_HANDLE;
double   g_pip = 0.0;
datetime g_lastMonthBar = 0;
bool     g_halted = false;

int OnInit()
{
   if(!InpAcknowledgeLEAD)
   {
      Print("[STOP] E5はLEAD(未検証)。InpAcknowledgeLEAD=true(デモ/極小のみ)で承認してください。");
      return INIT_FAILED;
   }
   if(!sym.Name(_Symbol)){ Print("Symbol init failed"); return INIT_FAILED; }
   sym.RefreshRates();
   int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   if(digits==3 || digits==5) g_pip=point*10.0; else g_pip=point;

   hAtrMN1=iATR(_Symbol,PERIOD_MN1,InpAtrPeriodMN1);
   if(hAtrMN1==INVALID_HANDLE){ Print("ATR(MN1) handle failed"); return INIT_FAILED; }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   PrintFormat("[INIT E5/%s] LEAD demo satellite. legRisk=%.2f%%/月 floorDD=%.1f%% LB=%d/%d/%d/%d short=%s",
               _Symbol,InpLegMonthlyRiskPct,InpAccountFloorDDPct,InpLB1,InpLB2,InpLB3,InpLB4,
               (InpAllowShort?"Y":"N"));
   if(InpVerboseLog)
      Print("[NOTE E5] 検証済みエッジではない(LEAD)。XAUUSD/US500/NAS100/GER40 に各1アタッチ。"
            "月初に時系列モメンタムで建て直し。デモで正期待値とv7低相関の再現を確認するまで本資金禁止。");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason){ if(hAtrMN1!=INVALID_HANDLE) IndicatorRelease(hAtrMN1); }

//==================================================================
// 月次TSMOMシグナル: 直近確定月(idx1)を過去L月前と比較した符号の多数決。
int Signal()
{
   int need = InpLB4 + 2;
   double c[];
   if(CopyClose(_Symbol, PERIOD_MN1, 0, need+1, c) < need+1) return 0;  // c[]は時系列順(古→新)
   int n = ArraySize(c);
   // 確定済み直近月 = 末尾から2番目(末尾は形成中の当月)
   int i1 = n-2;
   if(i1 <= InpLB4) return 0;
   int lbs[4]; lbs[0]=InpLB1; lbs[1]=InpLB2; lbs[2]=InpLB3; lbs[3]=InpLB4;
   double comp=0.0;
   for(int k=0;k<4;k++)
   {
      int j = i1 - lbs[k];
      if(j < 0) continue;
      double r = c[i1]/c[j] - 1.0;
      comp += (r>0? 1.0 : (r<0? -1.0 : 0.0));
   }
   int s = (comp>0? 1 : (comp<0? -1 : 0));
   if(s<0 && !InpAllowShort) return 0;
   return s;
}

double AtrMN1()
{
   double a[1];
   if(CopyBuffer(hAtrMN1,0,1,1,a)<1) return 0.0;
   return a[0];
}

// リスクパリティ: 月次σ(価格)=ATR(MN1) として、月次P&L σ ≒ legRisk%×equity となる lot。
double CalcLots()
{
   double atr=AtrMN1();
   if(atr<=0) return 0.0;
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   double riskMoney=equity*(InpLegMonthlyRiskPct/100.0);
   double tickValue=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double tickSize =SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(tickValue<=0 || tickSize<=0) return 0.0;
   double moneyPerLotPer1Sigma=(atr/tickSize)*tickValue;   // 1ロットがATR(=月次σ)動いた時の損益
   if(moneyPerLotPer1Sigma<=0) return 0.0;
   double lots=riskMoney/moneyPerLotPer1Sigma;
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   double vmin=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double vmax=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   if(step>0) lots=MathFloor(lots/step)*step;
   lots=MathMin(lots,MathMin(InpMaxLot,vmax));
   if(lots<MathMax(InpMinLot,vmin)) return 0.0;
   return lots;
}

int CurrentDir()
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Symbol()!=_Symbol || posinfo.Magic()!=InpMagic) continue;
      return (posinfo.PositionType()==POSITION_TYPE_BUY? 1 : -1);
   }
   return 0;
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

void OpenDir(int dir)
{
   double atr=AtrMN1(); if(atr<=0) return;
   double lots=CalcLots(); if(lots<InpMinLot){ if(InpVerboseLog) Print("[SKIP] lots<min"); return; }
   double stopDist=InpCatastropheATR*atr;
   int d=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   double sl;
   bool ok;
   if(dir>0){ double e=sym.Ask(); sl=NormalizeDouble(e-stopDist,d); ok=trade.Buy (lots,_Symbol,0.0,sl,0.0,"E5_RP_LONG"); }
   else     { double e=sym.Bid(); sl=NormalizeDouble(e+stopDist,d); ok=trade.Sell(lots,_Symbol,0.0,sl,0.0,"E5_RP_SHORT"); }
   if(ok) PrintFormat("[ENTRY E5/%s] %s lots=%.2f SL=%.5f atrMN1=%.5f legRisk=%.2f%%",
                      _Symbol,(dir>0?"LONG":"SHORT"),lots,sl,atr,InpLegMonthlyRiskPct);
   else   PrintFormat("[ENTRY FAIL] ret=%d %s",trade.ResultRetcode(),trade.ResultRetcodeDescription());
}

//==================================================================
void OnTick()
{
   sym.RefreshRates();
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);

   // 総合ガード(−10%枠の内側)
   double floorEq=InpInitialBalance*(1.0-InpAccountFloorDDPct/100.0);
   if(equity<=floorEq && !g_halted)
   {
      g_halted=true;
      if(InpCloseAllOnGuard) CloseMine("EQUITY_FLOOR");
      PrintFormat("[HALT] equity %.2f <= floor %.2f",equity,floorEq);
   }
   if(g_halted){ if(InpCloseAllOnGuard) CloseMine("HALTED"); return; }

   // 月初(MN1新バー)だけ再評価
   datetime mb=(datetime)iTime(_Symbol,PERIOD_MN1,0);
   if(mb==g_lastMonthBar) return;
   g_lastMonthBar=mb;

   int sig=Signal();
   int cur=CurrentDir();
   if(sig==0){ if(cur!=0) CloseMine("SIGNAL_FLAT"); return; }
   if(cur==sig) return;            // 同方向継続
   if(cur!=0) CloseMine("FLIP");   // 逆/新規なので一旦手仕舞い
   OpenDir(sig);
}
//+------------------------------------------------------------------+
//| 残存リスク(誠実な記録):                                          |
//|  ・E5はLEAD=有意水準未達(頑健p0.042/JKmax0.171, docs/27)。本資金禁止。|
//|  ・素のmaxDD−17.8%→ legRisk%でスケールして−10%枠に収める設計。     |
//|    実maxDDがデモで想定(−6%)に収まるか監視し、超えるなら legRisk を |
//|    下げる(maxDDは概ね線形)。                                       |
//|  ・指数/金は price index・月次終値モデル。実CFDのスワップ/配当調整/  |
//|    スプレッド/ギャップで結果がずれうる→デモで実測。              |
//|  ・v7との月次相関≈+0.07(ほぼ無相関)。分散効果は『緩やか』(Sharpe   |
//|    1.47→約1.67@配分25-35%, docs/29)。劇的ではない点を誇張しない。  |
//|  ・ATR(MN1)が短い銘柄/上場新しいCFDでは過小。十分な月数が必要。     |
//+------------------------------------------------------------------+
