//+------------------------------------------------------------------+
//|              Chien_Seasonal_Portfolio_AllInOne_PROP.mq5           |
//|   第3並走ポートフォリオ = 季節性カレンダー(オーバーレイ口座)        |
//|   FundedNext Stellar 2-Step($100K) 向け・1チャート1EA。            |
//|                                                                   |
//|   ■ 位置づけ(docs/65): 既存の並走                                 |
//|       口座1 = v7+v4+E5 (Chien_Portfolio3_AllInOne_PROP)            |
//|       口座2 = E-Mon+E5 (Chien_Parallel_AllInOne_PROP)             |
//|     に対する【第3の器】。核は"季節性(month-of-year)"。            |
//|     既存の Chien_Seasonal_Index_EA(単一バスケット)を、            |
//|     ★窓ごとに資産が異なる「季節カレンダー」へ拡張したもの。        |
//|                                                                   |
//|   ■ なぜ季節核が並走に効くか(docs/64,65・一次=10年):              |
//|     ・核 S-Jul(US500+NAS100 7月L): 年平均+3.04%/最悪年-0.4%/      |
//|       陽性年80%/年次ブロックp=0.0045/maxDD-5.7%。                  |
//|       ★E-Mon(口座2)と相関 −0.31(負)=指数月曜の真の分散源。        |
//|     ・第2窓 XAU-Dec(金 12月L): 別資産・別月でカレンダーを埋める。  |
//|       ただし★弱い(OOS perm_p=0.26 非有意 / 年次JK_max=0.123 不合格/ |
//|       コスト3xで+2.4%脆)。∴ 小サイズ衛星・既定は半分サイズ。      |
//|     ・S-Nov(指数11月)は E-Mon相関+0.55(冗長)ゆえ不採用。           |
//|                                                                   |
//|   ■ 正直な限界(数字を盛らない/docs/65):                          |
//|     ・季節性=実サンプルは年数(10)のみ=構造的に薄い。              |
//|       Bonferroni(N=164)未達=v7/E-Mon と同じ天井。SEASONAL-LEAD     |
//|       であって ADOPT ではない。本資金前デモ前進検証(docs/29)必須。 |
//|     ・年1-2窓しか発火しない=【遅い】。No-time-limitの2-Step通過MC  |
//|       (docs/65)で 小サイズ(≤1.5x)・失格ほぼ0%だが通過は中央~3年    |
//|       (素サイズなら~6年)。本口座の価値は"速さ"でなく              |
//|       "口座2と同時にDDしない生存・分散"。主軸にしない。            |
//|     ・-10%枠ゆえ小サイズ限定(核の素maxDD-5.7%が既に枠の過半)。     |
//|       核の実効リスクは概ね≤1.5x(1.7x超は単一窓で枠割れ・docs/65)。 |
//|                                                                   |
//|   ■ ガードは全EA共通(docs/01規約準拠):                            |
//|     equityフロア(既定-8%)・日次-4%(規約-5%手前)・毎ティックequity   |
//|     監視・SL必須・ナンピン無し・1窓1建て。                        |
//|                                                                   |
//|   ★口座2(950720)とは別口座/別業者で並走推奨。同口座併存でも        |
//|     Magic帯 950740 で分離。1チャートに本EAを1つだけドロップ。      |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.00"
#property strict
#property description "Seasonal calendar overlay (3rd parallel account). Jul index basket + Dec gold. SEASONAL-LEAD=demo first. FundedNext 2-Step guards built-in."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

input group "=== 季節カレンダー(窓ごとに資産が異なる)==="
// 書式: "月:銘柄CSV[:サイズ倍率]" を ; 区切り。倍率省略=1.0。
// 既定 = 7月に指数バスケット(核) + 12月に金(弱窓・半分サイズ)。
input string InpCalendar = "7:US500,NAS100:1.0; 12:XAUUSD:0.5";
input int    InpEntryDom  = 1;            // 月内 何営業日目に建てるか(1=月初第1営業日)。月跨ぎで自動決済

input group "=== サイズ(季節性=小サイズ・-10%枠厳守)==="
input bool   InpAcknowledgeLEAD = true;   // S-Jul=SEASONAL-LEAD。デモ/小サイズで承認=true
input double InpWindowRiskPct   = 1.30;   // 1窓あたりの総リスク%(核の実効サイズ。≤1.5%目安・docs/65)
input double InpCatastropheATR  = 2.5;    // 災害SL=2.5×ATR(D1)
input double InpMinStopPtsIndex = 50.0;   // 指数の最小SL(ポイント)
input double InpMinStopPtsGold  = 100.0;  // 金の最小SL(ポイント)
input double InpMaxSpreadPtsIdx = 1500.0; // 指数スプレッド上限(ポイント)
input double InpMaxSpreadPtsXau = 800.0;  // 金スプレッド上限(ポイント)
input int    InpAtrPeriodD1     = 14;     // 日次ATR期間

input group "=== 口座/ガード(docs/01規約準拠)==="
input double InpInitialBalance    = 0.0;  // 0=口座残高を自動取得
input double InpMaxLossLimitPct   = 10.0; // 失格ライン%(最終backstop)
input double InpAccountFloorDDPct = 8.0;  // 全停止ライン%(規約-10%の手前。守り=8.0)
input double InpDailyStopPct      = 4.0;  // 日次全決済%(規約-5%の手前)。0で無効

input group "=== 共通 ==="
input double InpMinLot = 0.01;
input double InpMaxLot = 50.0;
input long   InpMagicBase = 950740;       // 第3口座=季節カレンダー専用帯(窓ごと +月)
input int    InpSlippagePoints = 30;
input bool   InpVerboseLog = true;

//==================================================================
CTrade        trade;
CPositionInfo posinfo;

// 窓(=暦月ごとの資産バスケット+サイズ倍率)を保持
struct SeasonWindow {
   int      month;        // 暦月(1-12)
   string   syms[];       // 解決済み銘柄
   int      atrD1[];      // 各銘柄のD1 ATRハンドル
   double   sizeMult;     // この窓のサイズ倍率(InpWindowRiskPct × これ)
   long     magic;        // この窓のMagic(= base + month)
   datetime lastEntryMon; // 二重建て防止
};
SeasonWindow g_win[];

double   g_initBal=0.0;
double   g_peakEquity=0.0, g_dayStartEq=0.0;
datetime g_curDay=0; bool g_halted=false, g_dayBlocked=false;

//==================================================================
int SplitCSV(string csv, string &arr[])
{
   string p[]; int k=StringSplit(csv, ',', p); int m=0; ArrayResize(arr,k);
   for(int i=0;i<k;i++){ string s=p[i]; StringTrimLeft(s); StringTrimRight(s);
      if(StringLen(s)>0){ arr[m]=s; m++; } }
   ArrayResize(arr,m); return m;
}

string ResolveSymbol(string want)
{
   string suf[]={"",".pi",".raw",".ecn",".stp",".pro",".cash",".r",".c",".m","m",".spot","-cash",".sd","+",".i","_SB","_raw",".a",".z"};
   string bases[]; ArrayResize(bases,40); int nb=0;
   bases[nb++]=want;
   string U=want; StringToUpper(U);
   if(StringFind(U,"SPX")>=0 || StringFind(U,"500")>=0){
      bases[nb++]="US500"; bases[nb++]="SPX500"; bases[nb++]="SP500"; bases[nb++]="USA500"; bases[nb++]="US500Cash"; bases[nb++]="US_500"; bases[nb++]="SPX"; bases[nb++]="US500.cash"; }
   else if(StringFind(U,"NAS")>=0 || StringFind(U,"USTEC")>=0 || StringFind(U,"NDX")>=0 || StringFind(U,"US100")>=0 || StringFind(U,"TECH")>=0){
      bases[nb++]="NAS100"; bases[nb++]="USTEC"; bases[nb++]="US100"; bases[nb++]="NDX100"; bases[nb++]="USTECH"; bases[nb++]="NDX"; bases[nb++]="US_TECH100"; bases[nb++]="NAS100.cash"; }
   else if(StringFind(U,"GER")>=0 || StringFind(U,"DAX")>=0 || StringFind(U,"DE40")>=0 || StringFind(U,"DE30")>=0){
      bases[nb++]="GER40"; bases[nb++]="DE40"; bases[nb++]="DAX40"; bases[nb++]="GER30"; bases[nb++]="DE30"; bases[nb++]="GERMANY40"; bases[nb++]="DAX"; bases[nb++]="GER40.cash"; }
   else if(StringFind(U,"XAU")>=0 || StringFind(U,"GOLD")>=0){
      bases[nb++]="XAUUSD"; bases[nb++]="GOLD"; bases[nb++]="XAUUSD."; bases[nb++]="GOLDUSD"; bases[nb++]="XAU_USD"; bases[nb++]="GOLDmicro"; }
   ArrayResize(bases,nb);
   for(int b=0;b<nb;b++)
      for(int s=0;s<ArraySize(suf);s++){
         string cand=bases[b]+suf[s];
         if(SymbolSelect(cand,true)) return cand;
      }
   return "";
}

bool IsGold(string sym){ string U=sym; StringToUpper(U);
   return (StringFind(U,"XAU")>=0 || StringFind(U,"GOLD")>=0); }

// "月:銘柄CSV[:倍率]" を1窓へパース
bool ParseWindow(string spec, SeasonWindow &w)
{
   string part[]; int k=StringSplit(spec, ':', part);
   if(k<2) return false;
   string ms=part[0]; StringTrimLeft(ms); StringTrimRight(ms);
   w.month=(int)StringToInteger(ms);
   if(w.month<1 || w.month>12) return false;
   string symcsv=part[1];
   string raw[]; int ns=SplitCSV(symcsv,raw);
   if(ns==0) return false;
   w.sizeMult = (k>=3) ? StringToDouble(part[2]) : 1.0;
   if(w.sizeMult<=0) w.sizeMult=1.0;
   ArrayResize(w.syms,0); ArrayResize(w.atrD1,0);
   for(int i=0;i<ns;i++){
      string r=ResolveSymbol(raw[i]);
      if(r==""){ PrintFormat("⚠ [窓%d月] 銘柄 %s 見つからず→スキップ",w.month,raw[i]); continue; }
      if(r!=raw[i]) PrintFormat("[銘柄解決] %s → %s",raw[i],r);
      int idx=ArraySize(w.syms);
      ArrayResize(w.syms,idx+1); ArrayResize(w.atrD1,idx+1);
      w.syms[idx]=r; w.atrD1[idx]=iATR(r,PERIOD_D1,InpAtrPeriodD1);
   }
   w.magic=InpMagicBase+w.month;   // 窓ごとに +月 でMagic分離
   w.lastEntryMon=0;
   return (ArraySize(w.syms)>0);
}

int OnInit()
{
   if(!InpAcknowledgeLEAD){ Print("[STOP] 季節核=SEASONAL-LEAD。InpAcknowledgeLEAD=trueで承認(デモ/小サイズ)。"); return INIT_FAILED; }
   // カレンダーをパース
   string specs[]; int nw=StringSplit(InpCalendar, ';', specs);
   ArrayResize(g_win,0);
   for(int i=0;i<nw;i++){
      string s=specs[i]; StringTrimLeft(s); StringTrimRight(s);
      if(StringLen(s)==0) continue;
      SeasonWindow w;
      if(ParseWindow(s,w)){ int idx=ArraySize(g_win); ArrayResize(g_win,idx+1); g_win[idx]=w; }
      else PrintFormat("⚠ 窓パース失敗: '%s'",s);
   }
   if(ArraySize(g_win)==0){ Print("有効な季節窓が無い"); return INIT_FAILED; }

   g_initBal=(InpInitialBalance>0.0)?InpInitialBalance:AccountInfoDouble(ACCOUNT_BALANCE);
   if(g_initBal<=0.0) g_initBal=AccountInfoDouble(ACCOUNT_EQUITY);
   trade.SetDeviationInPoints(InpSlippagePoints);
   g_peakEquity=g_initBal;
   ResetDay(TimeCurrent());

   PrintFormat("[INIT SEASONAL-PORT] initBal=%.0f windows=%d windowRisk=%.2f%% floor=-%.1f%% daily=-%.1f%%",
      g_initBal,ArraySize(g_win),InpWindowRiskPct,InpAccountFloorDDPct,InpDailyStopPct);
   for(int i=0;i<ArraySize(g_win);i++){
      string sl=""; for(int j=0;j<ArraySize(g_win[i].syms);j++) sl+=(j>0?",":"")+g_win[i].syms[j];
      PrintFormat("  窓: %d月 [%s] sizeMult=%.2f magic=%d",g_win[i].month,sl,g_win[i].sizeMult,(int)g_win[i].magic);
   }
   if(InpVerboseLog) Print("[NOTE] 第3並走口座=季節カレンダー(SEASONAL-LEAD,docs/65)。遅い=生存/分散が価値。本資金前デモ必須。");
   EventSetTimer(30);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){
   EventKillTimer();
   for(int i=0;i<ArraySize(g_win);i++)
      for(int j=0;j<ArraySize(g_win[i].atrD1);j++)
         if(g_win[i].atrD1[j]!=INVALID_HANDLE) IndicatorRelease(g_win[i].atrD1[j]);
}

datetime DayStart(datetime t){ MqlDateTime s; TimeToStruct(t,s); s.hour=0;s.min=0;s.sec=0; return StructToTime(s); }
void ResetDay(datetime t){ g_curDay=DayStart(t); g_dayStartEq=AccountInfoDouble(ACCOUNT_EQUITY); g_dayBlocked=false; }
double AtrAt(int handle){ double a[1]; if(handle==INVALID_HANDLE||CopyBuffer(handle,0,1,1,a)<1) return 0.0; return a[0]; }
double PointOf(string s){ return SymbolInfoDouble(s,SYMBOL_POINT); }

double LotsFor(string sym, double priceMove, double riskMoney)
{
   if(priceMove<=0||riskMoney<=0) return 0.0;
   double tv=SymbolInfoDouble(sym,SYMBOL_TRADE_TICK_VALUE);
   double ts=SymbolInfoDouble(sym,SYMBOL_TRADE_TICK_SIZE);
   if(tv<=0||ts<=0) return 0.0;
   double lossPerLot=(priceMove/ts)*tv; if(lossPerLot<=0) return 0.0;
   double lots=riskMoney/lossPerLot;
   double step=SymbolInfoDouble(sym,SYMBOL_VOLUME_STEP);
   double vmin=SymbolInfoDouble(sym,SYMBOL_VOLUME_MIN);
   double vmax=SymbolInfoDouble(sym,SYMBOL_VOLUME_MAX);
   if(step>0) lots=MathFloor(lots/step)*step;
   lots=MathMin(lots,MathMin(InpMaxLot,vmax));
   if(lots<MathMax(InpMinLot,vmin)) return 0.0;
   return lots;
}

int CountMagic(long magic){
   int n=0;
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()==magic) n++; }
   return n;
}
void CloseMagic(long magic, string why){
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()==magic) trade.PositionClose(tk); }
   if(InpVerboseLog) PrintFormat("[CLOSE magic=%d %s]",(int)magic,why);
}
void CloseAllMine(string why){
   for(int i=0;i<ArraySize(g_win);i++) CloseMagic(g_win[i].magic,why);
}

// 当月の最初の取引日から数えて何営業日目か(D1足の日付で概算)。
int DomFromStart(string sym, datetime now)
{
   MqlDateTime n; TimeToStruct(now,n);
   int cnt=0;
   for(int i=0;i<40;i++){
      datetime bt=(datetime)iTime(sym,PERIOD_D1,i);
      if(bt==0) break;
      MqlDateTime b; TimeToStruct(bt,b);
      if(b.mon!=n.mon || b.year!=n.year) break;
      cnt++;
   }
   return cnt;
}

//==================================================================
void OnTimer()
{
   datetime now=TimeCurrent();
   if(DayStart(now)!=g_curDay) ResetDay(now);
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);

   // ---- ガード階層(規約準拠): 全停止フロア(equityベース・毎ティック) ----
   if(equity>g_peakEquity) g_peakEquity=equity;
   double floor=g_initBal*(1.0-InpAccountFloorDDPct/100.0);
   if(equity<=floor && !g_halted){ g_halted=true; CloseAllMine("EQUITY_FLOOR");
      PrintFormat("[HALT] equity %.2f <= floor %.2f",equity,floor); }
   if(g_halted){ CloseAllMine("HALTED"); return; }

   // ---- 日次ストップ(当日開始equity起点・規約-5%手前) ----
   if(InpDailyStopPct>0){
      double dpnl=equity-g_dayStartEq;
      if(dpnl<=-g_initBal*InpDailyStopPct/100.0 && !g_dayBlocked){
         g_dayBlocked=true; CloseAllMine("DAILY_STOP");
         PrintFormat("[DAILY STOP] %.2f",dpnl); }
   }

   MqlDateTime t; TimeToStruct(now,t);

   // ---- 各窓: 季節月を跨いだら全決済 / 季節月・未建て・建て営業日でエントリ ----
   for(int wi=0; wi<ArraySize(g_win); wi++){
      bool inSeason = (t.mon==g_win[wi].month);
      // 決済: 当該窓のポジが残り、かつ対象月を抜けたら翌月初寄付で全決済
      if(CountMagic(g_win[wi].magic)>0 && !inSeason){
         CloseMagic(g_win[wi].magic,"SEASON_END"); g_win[wi].lastEntryMon=0;
      }
   }
   if(g_dayBlocked) return;

   for(int wi=0; wi<ArraySize(g_win); wi++){
      if(t.mon!=g_win[wi].month) continue;
      MqlDateTime mk; TimeToStruct(now,mk); mk.day=1; mk.hour=0; mk.min=0; mk.sec=0;
      datetime thisMonth=StructToTime(mk);
      if(g_win[wi].lastEntryMon==thisMonth) continue;     // 当月建て済み
      if(CountMagic(g_win[wi].magic)>0) continue;
      if(ArraySize(g_win[wi].syms)==0) continue;
      int dom=DomFromStart(g_win[wi].syms[0],now);
      if(dom<InpEntryDom) continue;
      OpenWindow(wi);
      g_win[wi].lastEntryMon=thisMonth;
   }
}

void OpenWindow(int wi)
{
   int ns=ArraySize(g_win[wi].syms);
   if(ns==0) return;
   // この窓の総リスク = InpWindowRiskPct × 窓のsizeMult、銘柄等加重
   double winRisk=InpWindowRiskPct*g_win[wi].sizeMult;
   double perSym=winRisk/ns;
   trade.SetExpertMagicNumber(g_win[wi].magic);
   for(int i=0;i<ns;i++){
      if(g_win[wi].atrD1[i]==INVALID_HANDLE) continue;
      string sym=g_win[wi].syms[i]; double pt=PointOf(sym); if(pt<=0) continue;
      double atr=AtrAt(g_win[wi].atrD1[i]); if(atr<=0) continue;
      double sd=InpCatastropheATR*atr; double sp=sd/pt;
      double minStop = IsGold(sym)?InpMinStopPtsGold:InpMinStopPtsIndex;
      double maxSpr  = IsGold(sym)?InpMaxSpreadPtsXau:InpMaxSpreadPtsIdx;
      if(sp<minStop){ sp=minStop; sd=sp*pt; }
      double ask=SymbolInfoDouble(sym,SYMBOL_ASK), bid=SymbolInfoDouble(sym,SYMBOL_BID);
      if(ask<=0||bid<=0) continue;
      if((ask-bid)/pt>maxSpr) continue;
      double riskMoney=g_initBal*(perSym/100.0);
      double lots=LotsFor(sym,sd,riskMoney); if(lots<InpMinLot) continue;
      int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      double sl=NormalizeDouble(ask-sd,dg);
      if(trade.Buy(lots,sym,0.0,sl,0.0,StringFormat("SeasonPort_%d_%s",g_win[wi].month,sym)))
         { if(InpVerboseLog) PrintFormat("[SEASONAL-PORT ENTRY] %d月 LONG %s lots=%.2f SL=%.2f perSym=%.3f%%",
              g_win[wi].month,sym,lots,sl,perSym); }
   }
}
//+------------------------------------------------------------------+
//| 残存リスク(誠実な記録, docs/65):                                 |
//|  ・季節核=実サンプルは年数(10)のみ=薄い。Bonferroni未達(v7/E-Mon   |
//|    と同じ天井)。SEASONAL-LEAD であって ADOPT でない。本資金前デモ。|
//|  ・第2窓 XAU-Dec は弱い(OOS perm_p=0.26非有意/JK_max=0.123不合格/  |
//|    コスト3xで+2.4%)。既定で半分サイズ(0.5)。外す(InpCalendar から  |
//|    12月を削る)選択も妥当=核S-Jul単独でも口座は成立。              |
//|  ・遅い: 年1-2窓のみ=No-time-limit 2-Step 通過は中央~3年(小サイズ)。|
//|    本口座の価値は速さでなく口座2(E-Mon)との同時DD回避(corr -0.31)。 |
//|  ・口座1(v7)とは S-Jul co-active corr=+0.64(7月に共ロング)。稼働月  |
//|    が年1-2ヶ月ゆえ口座レベルの実害は限定だが、別口座/別業者推奨。   |
//|  ・1ヶ月保有=指数/金CFDのスワップ累積・配当・取引時間は業者差大。  |
//|    実スプレッド/スワップはデモで実測しサイズ確定。                |
//|  ・-10%枠厳守=核の実効リスクは概ね≤1.5%(1.7x超は単一窓で枠割れ)。  |
//|  ・建て/決済の営業日判定はD1足で概算。本番前デモで建て/決済時刻確認。|
//|  ・1チャートに本EAは1つだけ。同口座併存は Magic帯950740で分離。    |
//+------------------------------------------------------------------+
