//| ★v1.30(2026-09-26) EA8: EA2 の Mon 4 を全重み ×3.3 に戻し(Sess は docs/249 で無効)、GER40 ブレイク買い(H1 ドンチャン 120 本・2ATR トレイル・×2.0)を追加。docs/296 §7・docs/297。ユーザー判断の試験運用(改良基準は未達)。
//+------------------------------------------------------------------+
//| ★FTMO 50k 2-Step 口座521100397 EA2: A'(Mon円クロス4)+B(Sess上位5) 50/50・3.3倍|
//|   docs/237-239。Hold UK100 はスワップ有り口座のため除外(A'=Mon 4本・逆ボラ)           |
//|   Mon: GBPJPY .130/EURJPY .133/AUDJPY .108/USDJPY .129(=A' 加重×0.5)|
//|   Sess: 上位5 加重×0.5・月〜木 4h SHORT・スプレッド上限1.5pip・SL≥15pip            |
//|   紙上(Sess 3pip): 年率+12.5%・最大DD−3.3%・最悪月−1.1%・MC 57%/0.2%          |
//|   FTMO: 日次−4%(規約5%)・フロア−9%・P1 ロック 9.9/10.05                       |
//|   Magic 944100(既存 D案 943400 と別)。期限 2027-03-31                     |
//|   FOMC 決定日は Sess を建てない(InpSessSkipDates・2027年分は要更新)               |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.30"   // EA8: Mon4 ×3.3 + GER40 ブレイク ×2.0(docs/297)
#property strict
#property description "[RecentFit 2026H2] Recency-bet track (docs/174/175). Mon GBPJPY+AUDJPY / v4 USDJPY / Hold JP225. mult 4.8 std / 7.2 fast. Balance guard -4 tick, floor -9, FN P1 lock 8.05. Expiry-enforced re-screen."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

input bool   InpAcknowledgeBet  = true;   // 本トラック=直近過剰適合の明示ベット(docs/174)を承認

input group "=== 構成(銘柄:重み CSV。既定=2026-07-30スクリーニング凍結値) ==="
input string InpMonLegs  = "GBPJPY:0.260,EURJPY:0.266,AUDJPY:0.215,USDJPY:0.258"; // Mon 4(逆ボラ加重・合計 1.0)×InpMult = Mon4 ×3.3
input string InpV4Legs   = "";                          // v4: 未使用
input string InpHoldLegs = "";                          // Hold: 未使用(スワップ有り口座)
input double InpMult     = 3.3;   // Mon スリーブ倍率(docs/228: 5 年 MC 資金化 83% / 失格 7.9%)

input group "=== 有効期限(直近特化=賞味期限つき。docs/174停止規則) ==="
input datetime InpExpiry = D'2027.03.31 23:59';  // 6ヶ月判定(docs/233 §4)

input group "=== 口座/ガード ==="
input double InpInitialBalance   = 50000.0; // FTMO 50k の初期残高を固定(0=自動は端末変更で基準がずれる。docs/241 §1d)
input bool   InpBaselineReset    = false; // 新フェーズ開始時のみtrue=基準残高を取り直す
input double InpMaxLossLimitPct  = 10.0;  // 失格ライン%(FN Stellar=静的10%)
input double InpAccountFloorDDPct= 9.0;   // 全停止ライン%(-10%枠の手前)
input double InpDailyStopPct     = 4.0;   // 日次equity−この%で当日新規停止(規約−5%手前)

input group "=== v1.44 balance基準日次ガード(docs/170/171) ==="
input double InpBalGuardPct      = 4.0;   // equity≤日開始balance−この%で全決済+当日停止(0=無効)
input int    InpBalGuardMaxMonth = 2;     // 月内発動上限(超過は月末まで新規停止)

input group "=== 利益ロック(FN Stellar P1=+8%。P2は5.05/4.9に変更) ==="
input bool   InpProfitLockEnable = true;
input double InpLockArmPct    = 9.9;   // equity+この%で新規停止
input double InpLockClosePct  = 10.05;  // equity+この%で全決済し恒久ロック(PASS_LOCK)
input double InpProfitStopPct = 10.1;   // +この%で新規停止(保険)

input group "=== プッシュ通知(docs/112) ==="
input bool   InpNotifyEnable     = true;
input bool   InpNotifyEntries    = true;
input double InpNotifyDayWarnPct = 3.0;   // 日次−この%で警告

input group "=== Mon レッグ設定(月曜マルチショット・docs/09系パリティ) ==="
input string InpMonHoursUTC   = "4,6,8,10";
input int    InpMonHoldHours  = 24;
input int    InpAtrPeriodH1   = 24;
input double InpCatastropheATR= 2.5;    // 災害SL=2.5×ATR(H1)
input double InpMinStopPips   = 10.0;
input double InpMaxSpreadPips = 3.0;
input string InpMonSpreadCaps = "GBPJPY:2.9,EURJPY:2.5,AUDJPY:2.9,USDJPY:2.0";

input group "=== v4 レッグ設定(日足k≥4合議) ==="
input int    InpV4_RSI       = 14;
input double InpV4_RSIlo     = 35.0;
input double InpV4_RSIhi     = 65.0;
input int    InpV4_BBwin     = 20;
input double InpV4_BBz       = 1.5;
input int    InpV4_streak    = 3;
input double InpV4_dayMovePct= 0.5;
input int    InpV4_ATR       = 14;
input double InpV4_SLatr     = 1.5;
input double InpV4_RR        = 1.2;
input int    InpV4_MaxHoldDays= 8;
input bool   InpV4AllowShort = true;

input group "=== Hold レッグ設定(連続LONG) ==="
input bool   InpHoldEnable    = false;
input double InpHoldCatSLPct  = 15.0;   // 災害SL: 建値−この%(研究はSLなし・保険のみ)
input double InpHoldMaxSpreadPts = 3000.0;

input group "=== 時間帯セル Sess(docs/233-235・v1.10) ==="
input bool   InpSessEnable        = false;  // docs/249: Sess 族は無効。false 固定
input string InpSessLegs          = "EURGBP:S:20:4:0.1745,NZDUSD:S:20:4:0.0715,AUDUSD:S:20:4:0.0855,EURGBP:S:16:4:0.0865,USDCHF:S:0:4:0.0815"; // SYM:方向:建てUTC時:保有h:重み
input double InpSessMult          = 3.3;   // Sess 専用倍率(名目=基準残高×重み×倍率)
input double InpSessMaxSpreadPips = 1.5;   // 建て時スプレッド上限(pip)。超過は見送り
input double InpSessMinStopPips   = 15.0;  // 災害SL最小幅(21 UTC のスプレッド拡大を内側で受ける)
input string InpSessSkipDates     = "2026.09.16,2026.10.28,2026.12.09"; // Sess を建てない日(FOMC 決定日・UTC)。2027 年分は要更新

input group "=== GER40 ブレイク Brk(docs/296 Q52 セル・v1.30) ==="
input bool   InpBrkEnable      = true;
input string InpBrkSymbol      = "GER40";   // 業者表記は自動解決(GER40.cash 等)
input int    InpBrkN           = 120;       // ドンチャン: 直前 N 本(確定バー)の高値更新で買い
input double InpBrkAtrTrail    = 2.0;       // 出口: 建て後の最高終値から この×ATR24(建て時) 戻った終値で次バー始値決済
input int    InpBrkMaxHours    = 240;       // 最長保有(H1 本数)
input double InpBrkWeight      = 1.0;       // 名目=基準残高×重み×倍率
input double InpBrkMult        = 2.0;       // 倍率(docs/296 §7: Mon4×3.3 + GER40×2 → 資金化 84% / 失格 10.5%)
input double InpBrkMaxSpreadPts= 5.0;       // 建て時スプレッド上限(ポイント)
input double InpBrkCatSLAtr    = 6.0;       // 災害SL = 建値 − この×ATR24(研究は SL 無し。保険のみ・0=無し)

input group "=== 防御フィルタ(docs/148) ==="
input bool   InpHolidayFilterEnable = true; // 12/20〜1/3は新規停止

input group "=== 共通 ==="
input double InpMinLot = 0.01;
input double InpMaxLot = 50.0;
input long   InpMagicBase = 944100;  // Mon=+1/v4=+2/Hold=+3/Sess=+5/Brk=+6(D案 943400 と別)
input int    InpSlippagePoints = 30;
input bool   InpVerboseLog = true;

//==================================================================
CTrade        trade;
CPositionInfo posinfo;

#define MAXLEG 8
string  g_monSym[MAXLEG];  double g_monW[MAXLEG];  int g_nMon=0;
string  g_v4Sym[MAXLEG];   double g_v4W[MAXLEG];   int g_nV4=0;
string  g_holdSym[MAXLEG]; double g_holdW[MAXLEG]; int g_nHold=0;
string  g_sesSym[MAXLEG]; bool g_sesShort[MAXLEG]; int g_sesH0[MAXLEG]; int g_sesSpan[MAXLEG]; double g_sesW[MAXLEG]; int g_nSes=0;   // v1.10
int      g_atrH1Ses[MAXLEG]; datetime g_lastSes[MAXLEG]; datetime g_sesSkip[MAXLEG];
int     g_monHours[]; int g_atrH1[MAXLEG]; int g_atrD1[MAXLEG]; int g_rsiD1[MAXLEG];
datetime g_lastShotMon[MAXLEG*8];
datetime g_lastV4Bar[MAXLEG];
datetime g_lastHoldTry[MAXLEG];
double   g_initBal=0.0;
double   g_dayStartEq=0.0, g_dayStartBal=0.0;
datetime g_curDay=0, g_balBlockDay=0;
int      g_balFireMonth=-1, g_balFires=0;
bool     g_balMonthHalt=false;
bool     g_halted=false, g_dayBlocked=false, g_passLocked=false, g_expired=false;
string   g_ntfBuf=""; bool g_ntfArm=false; datetime g_ntfWarnDay=0;
string   g_gvName="";
long     g_mMon=0, g_mV4=0, g_mHold=0, g_mSes=0, g_mBrk=0;
string   g_brkSym=""; datetime g_brkLastBar=0; double g_brkExt=0.0, g_brkAtr=0.0; datetime g_brkEntry=0;   // v1.30 Brk
string   g_sizeWarned="";

//==================================================================
string ResolveSymbol(string want)
{
   string suf[]={"",".pi",".raw",".ecn",".stp",".pro",".cash",".r",".c",".m","m",".spot","-cash",".sd","+",".i","_SB","_raw",".a",".z"};
   string bases[]; ArrayResize(bases,40); int nb=0;
   bases[nb++]=want;
   string U=want; StringToUpper(U);
   if(StringFind(U,"JP225")>=0 || StringFind(U,"JPN")>=0 || StringFind(U,"NIK")>=0){
      bases[nb++]="JP225"; bases[nb++]="JPN225"; bases[nb++]="NIKKEI225"; bases[nb++]="JP225Cash"; bases[nb++]="NI225"; bases[nb++]="JPN225.cash"; }
   if(StringFind(U,"UK100")>=0 || StringFind(U,"FTSE")>=0){                      // 本焼き込み: UK100別名
      bases[nb++]="UK100"; bases[nb++]="FTSE100"; bases[nb++]="UK100Cash"; bases[nb++]="UK100.cash"; }
   if(StringFind(U,"WTI")>=0 || StringFind(U,"USOIL")>=0 || StringFind(U,"XTI")>=0){  // 本焼き込み: WTI別名
      bases[nb++]="WTI"; bases[nb++]="USOIL"; bases[nb++]="XTIUSD"; bases[nb++]="USOUSD";
      bases[nb++]="USOil"; bases[nb++]="CrudeOIL"; bases[nb++]="OILUSD"; }
   ArrayResize(bases,nb);
   for(int b=0;b<nb;b++)
      for(int s=0;s<ArraySize(suf);s++){
         string cand=bases[b]+suf[s];
         if(SymbolSelect(cand,true)) return cand;
      }
   // v1.45(docs/173): 全銘柄走査フォールバック(接尾辞/接頭辞の自動吸収)
   {
      int total=SymbolsTotal(false);
      string bestName="";
      for(int i=0;i<total;i++){
         string nm=SymbolName(i,false);
         string UN=nm; StringToUpper(UN);
         for(int b=0;b<nb;b++){
            string UB=bases[b]; StringToUpper(UB);
            int pos=StringFind(UN,UB);
            if(pos<0) continue;
            if(pos>0){
               ushort c=StringGetCharacter(UN,pos-1);
               if(!(c=='.'||c=='_'||c=='-'||c=='#'||c=='@')) continue;
            }
            if(bestName=="" || StringLen(nm)<StringLen(bestName)) bestName=nm;
         }
      }
      if(bestName!="" && SymbolSelect(bestName,true)){
         PrintFormat("[SYM] '%s' → '%s' (全銘柄走査で解決)",want,bestName);
         return bestName;
      }
   }
   return "";
}

// "SYM:w,SYM:w" をパースし銘柄解決
// v1.10: "SYM:S|L:H0:SPAN:W"
int ParseSessLegs(string csv)
{
   string parts[]; int n=StringSplit(csv,',',parts); int k=0;
   for(int i=0;i<n && k<MAXLEG;i++){
      string kv[]; if(StringSplit(parts[i],':',kv)!=5) continue;
      string sym=kv[0]; StringTrimLeft(sym); StringTrimRight(sym);
      string d=kv[1]; StringTrimLeft(d); StringTrimRight(d); StringToUpper(d);
      int h0=(int)StringToInteger(kv[2]); int span=(int)StringToInteger(kv[3]); double w=StringToDouble(kv[4]);
      if(StringLen(sym)==0 || (d!="S" && d!="L") || h0<0 || h0>23 || span<1 || span>23 || w<=0){ PrintFormat("⚠ Sess: 書式不正 '%s'",parts[i]); continue; }
      string r=ResolveSymbol(sym);
      if(r==""){ PrintFormat("⚠ Sess: 銘柄'%s'を解決できず→スキップ",sym); continue; }
      if(r!=sym) PrintFormat("[銘柄解決] Sess %s → %s",sym,r);
      g_sesSym[k]=r; g_sesShort[k]=(d=="S"); g_sesH0[k]=h0; g_sesSpan[k]=span; g_sesW[k]=w; k++;
   }
   return k;
}
int ParseLegs(string csv, string &syms[], double &ws[], string label)
{
   string parts[]; int n=StringSplit(csv,',',parts); int k=0;
   for(int i=0;i<n && k<MAXLEG;i++){
      string kv[]; if(StringSplit(parts[i],':',kv)!=2) continue;
      string s=kv[0]; StringTrimLeft(s); StringTrimRight(s);
      double w=StringToDouble(kv[1]);
      if(StringLen(s)==0 || w<=0) continue;
      string r=ResolveSymbol(s);
      if(r==""){ PrintFormat("⚠ %s: 銘柄'%s'を解決できず→スキップ(重みは配分から欠落=サイズ縮小側)",label,s); continue; }
      if(r!=s) PrintFormat("[銘柄解決] %s %s → %s",label,s,r);
      syms[k]=r; ws[k]=w; k++;
   }
   return k;
}
int SplitHours(string csv, int &arr[])
{
   string p[]; int k=StringSplit(csv,',',p); int m=0; ArrayResize(arr,k);
   for(int i=0;i<k;i++){ string s=p[i]; StringTrimLeft(s); StringTrimRight(s);
      if(StringLen(s)==0) continue; int h=(int)StringToInteger(s);
      if(h>=0&&h<=23){ arr[m]=h; m++; } }
   ArrayResize(arr,m); return m;
}
double PipOf(string s){
   // 非FX(指数/暗号等)対応: pip=point×10。5桁/3桁FXでは従来値(0.0001/0.01)と一致。
   double pt=SymbolInfoDouble(s,SYMBOL_POINT);
   if(pt>0) return pt*10.0;
   return (StringFind(s,"JPY")>=0)? 0.01 : 0.0001; }

//--- v1.32(docs/153): サイズ二重チェック(tick値経路 vs 損益計算経路の保守側)
double MoneyPerUnit(string sym)
{
   double tv=SymbolInfoDouble(sym,SYMBOL_TRADE_TICK_VALUE);
   double ts=SymbolInfoDouble(sym,SYMBOL_TRADE_TICK_SIZE);
   double a=(tv>0&&ts>0)? tv/ts : 0.0;
   double p=SymbolInfoDouble(sym,SYMBOL_ASK);
   double b=0.0, prof=0.0, d=p*0.001;
   if(p>0 && d>0 && OrderCalcProfit(ORDER_TYPE_BUY,sym,1.0,p,p+d,prof) && prof>0) b=prof/d;
   double m=MathMax(a,b);
   if(a>0&&b>0){ double r=(a>b? a/b:b/a);
      if(r>1.5 && StringFind(g_sizeWarned,sym)<0){ g_sizeWarned+=sym+";";
         PrintFormat("⚠[SIZE SANITY %s] tick値経路 $%.2f vs 損益経路 $%.2f (乖離%.1f倍) → 保守側を採用しロット縮小",sym,a,b,r); } }
   return m;
}

// 想定元本ベースのロット(研究セルとのパリティ: 研究のリターン=価格変化率×重み×倍率)
// notionalMoney = 建玉の想定元本(口座通貨)。lots = notional / (1ロットの元本価値)
double LotsForNotional(string sym, double notionalMoney)
{
   if(notionalMoney<=0) return 0.0;
   double mpu=MoneyPerUnit(sym); if(mpu<=0) return 0.0;
   double px=SymbolInfoDouble(sym,SYMBOL_ASK); if(px<=0) return 0.0;
   double perLot=mpu*px; if(perLot<=0) return 0.0;
   double lots=notionalMoney/perLot;
   double step=SymbolInfoDouble(sym,SYMBOL_VOLUME_STEP);
   double vmin=SymbolInfoDouble(sym,SYMBOL_VOLUME_MIN);
   double vmax=SymbolInfoDouble(sym,SYMBOL_VOLUME_MAX);
   if(step>0) lots=MathFloor(lots/step)*step;
   lots=MathMin(lots,MathMin(InpMaxLot,vmax));
   if(lots<MathMax(InpMinLot,vmin)) return 0.0;
   return lots;
}

int CountPos(string sym, long magic){
   int n=0;
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Symbol()==sym && posinfo.Magic()==magic) n++; }
   return n;
}
bool IsMine(long m){ return (m==g_mMon||m==g_mV4||m==g_mHold||m==g_mSes||m==g_mBrk); }
void CloseAllMine(string why){
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(IsMine(posinfo.Magic())) trade.PositionClose(tk); }
   if(InpVerboseLog) PrintFormat("[CLOSE ALL %s]",why);
}

void Notify(string s){ if(!InpNotifyEnable) return; if(g_ntfBuf!="") g_ntfBuf+=" | "; g_ntfBuf+=s; }
void FlushNotify(){
   if(g_ntfBuf=="") return;
   string msg="[RF] "+g_ntfBuf;
   if(StringLen(msg)>250) msg=StringSubstr(msg,0,247)+"...";
   if(!MQLInfoInteger(MQL_TESTER)){
      if(!SendNotification(msg))
         PrintFormat("[NOTIFY失敗 err=%d] %s",GetLastError(),msg); }
   Print("[NOTIFY] ",msg); g_ntfBuf="";
}
bool HolidayBlocked(datetime utc){
   if(!InpHolidayFilterEnable) return false;
   MqlDateTime t; TimeToStruct(utc,t);
   return ((t.mon==12 && t.day>=20) || (t.mon==1 && t.day<=3));
}
double SpreadCapFor(string sym){
   if(StringLen(InpMonSpreadCaps)==0) return InpMaxSpreadPips;
   string S=sym; StringToUpper(S);
   string parts[]; int n=StringSplit(InpMonSpreadCaps,',',parts);
   for(int i=0;i<n;i++){
      string kv[]; if(StringSplit(parts[i],':',kv)!=2) continue;
      string k=kv[0]; StringTrimLeft(k); StringTrimRight(k); StringToUpper(k);
      if(StringLen(k)>0 && StringFind(S,k)>=0) return StringToDouble(kv[1]); }
   return InpMaxSpreadPips;
}

//==================================================================
int OnInit()
{
   if(!InpAcknowledgeBet){ Print("[STOP] 本EAは直近過剰適合の明示ベット(docs/174)。InpAcknowledgeBet=trueで承認。"); return INIT_FAILED; }
   g_nMon =ParseLegs(InpMonLegs, g_monSym, g_monW, "Mon");
   g_nV4  =ParseLegs(InpV4Legs,  g_v4Sym,  g_v4W,  "v4");
   g_nHold=(InpHoldEnable? ParseLegs(InpHoldLegs,g_holdSym,g_holdW,"Hold") : 0);
   g_nSes =(InpSessEnable? ParseSessLegs(InpSessLegs) : 0);
   int nh=SplitHours(InpMonHoursUTC,g_monHours);
   if(nh>8){ ArrayResize(g_monHours,8); nh=8;                       // v1.02: g_lastShotMon[MAXLEG*8]の範囲保護
      Print("⚠ Mon時刻は最大8個まで→先頭8個のみ使用"); }
   if(g_nMon==0 && g_nV4==0 && g_nHold==0 && g_nSes==0){ Print("レッグが1つも解決できず"); return INIT_FAILED; }
   if(g_nMon>0 && nh==0){ Print("Mon時刻のパース失敗"); return INIT_FAILED; }
   g_mMon=InpMagicBase+1; g_mV4=InpMagicBase+2; g_mHold=InpMagicBase+3; g_mSes=InpMagicBase+5; g_mBrk=InpMagicBase+6;
   if(InpBrkEnable){ g_brkSym=ResolveSymbol(InpBrkSymbol); if(g_brkSym==""){ PrintFormat("⚠ Brk: 銘柄'%s'を解決できず→Brk 無効",InpBrkSymbol); }
      else { SymbolSelect(g_brkSym,true); if(g_brkSym!=InpBrkSymbol) PrintFormat("[銘柄解決] Brk %s → %s",InpBrkSymbol,g_brkSym); } }

   g_gvName=StringFormat("ChienRF_base_%I64d_%I64d",
                         (long)AccountInfoInteger(ACCOUNT_LOGIN),(long)InpMagicBase);
   if(InpInitialBalance>0.0){
      g_initBal=InpInitialBalance; GlobalVariableSet(g_gvName,g_initBal);
   }else if(!InpBaselineReset && GlobalVariableCheck(g_gvName)){
      g_initBal=GlobalVariableGet(g_gvName);
      PrintFormat("[基準残高] 端末保存値を復元: %.2f",g_initBal);
   }else{
      g_initBal=AccountInfoDouble(ACCOUNT_BALANCE);
      if(g_initBal<=0.0) g_initBal=AccountInfoDouble(ACCOUNT_EQUITY);
      GlobalVariableSet(g_gvName,g_initBal);
      PrintFormat("[基準残高] 新規記録: %.2f",g_initBal);
   }

   for(int i=0;i<g_nMon;i++) g_atrH1[i]=iATR(g_monSym[i],PERIOD_H1,InpAtrPeriodH1);
   for(int i=0;i<g_nV4;i++){
      g_atrD1[i]=iATR(g_v4Sym[i],PERIOD_D1,InpV4_ATR);
      g_rsiD1[i]=iRSI(g_v4Sym[i],PERIOD_D1,InpV4_RSI,PRICE_CLOSE); }
   ArrayInitialize(g_lastShotMon,0); ArrayInitialize(g_lastV4Bar,0); ArrayInitialize(g_lastHoldTry,0);
   for(int i=0;i<g_nSes;i++) g_atrH1Ses[i]=iATR(g_sesSym[i],PERIOD_H1,InpAtrPeriodH1);
   ArrayInitialize(g_lastSes,0); ArrayInitialize(g_sesSkip,0);
   trade.SetDeviationInPoints(InpSlippagePoints);
   RestoreOrResetDay();
   double wsum=0; for(int i=0;i<g_nMon;i++) wsum+=g_monW[i];
   for(int i=0;i<g_nV4;i++) wsum+=g_v4W[i];
   for(int i=0;i<g_nHold;i++) wsum+=g_holdW[i];
   PrintFormat("[INIT RecentFit] initBal=%.0f mult=%.1f Σw=%.3f (グロス想定≈%.1fx) expiry=%s Magic=%I64d/%I64d/%I64d",
      g_initBal,InpMult,wsum,wsum*InpMult,TimeToString(InpExpiry,TIME_DATE),g_mMon,g_mV4,g_mHold);
   { double ws2=0; for(int i=0;i<g_nSes;i++) ws2+=g_sesW[i];
     PrintFormat("[INIT Sess v1.10] legs=%d Σw=%.3f mult=%.1f (グロス想定≈%.1fx・同時最大=20-00UTC窓) spreadCap=%.1fpip minSL=%.0fpip Magic=%I64d",
        g_nSes,ws2,InpSessMult,ws2*InpSessMult,InpSessMaxSpreadPips,InpSessMinStopPips,g_mSes); }
   if(g_brkSym!=""){
      if(GlobalVariableCheck(g_gvName+"_brkext")) g_brkExt=GlobalVariableGet(g_gvName+"_brkext");
      if(GlobalVariableCheck(g_gvName+"_brkatr")) g_brkAtr=GlobalVariableGet(g_gvName+"_brkatr");
      if(GlobalVariableCheck(g_gvName+"_brkin"))  g_brkEntry=(datetime)(long)GlobalVariableGet(g_gvName+"_brkin");
      PrintFormat("[INIT Brk v1.30] %s N=%d trail=%.1fATR maxH=%d 名目=%.0f (重み %.2f × 倍率 %.1f) spreadCap=%.1fpt Magic=%I64d 建玉=%d",
         g_brkSym,InpBrkN,InpBrkAtrTrail,InpBrkMaxHours,g_initBal*InpBrkWeight*InpBrkMult,InpBrkWeight,InpBrkMult,InpBrkMaxSpreadPts,g_mBrk,CountPos(g_brkSym,g_mBrk)); }
   Print("[NOTE] 直近特化トラック(docs/174/175)。正攻法口座とは別口座・別業者推奨。期限後は新規停止=再スクリーニング必須。");
   EventSetTimer(30);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){
   EventKillTimer();
   for(int i=0;i<g_nMon;i++) if(g_atrH1[i]!=INVALID_HANDLE) IndicatorRelease(g_atrH1[i]);
   for(int i=0;i<g_nSes;i++) if(g_atrH1Ses[i]!=INVALID_HANDLE) IndicatorRelease(g_atrH1Ses[i]);
   for(int i=0;i<g_nV4;i++){ if(g_atrD1[i]!=INVALID_HANDLE) IndicatorRelease(g_atrD1[i]);
      if(g_rsiD1[i]!=INVALID_HANDLE) IndicatorRelease(g_rsiD1[i]); }
}

datetime DayStart(datetime t){ MqlDateTime s; TimeToStruct(t,s); s.hour=0;s.min=0;s.sec=0; return StructToTime(s); }
void ResetDay(datetime t){ g_curDay=DayStart(t); g_dayStartEq=AccountInfoDouble(ACCOUNT_EQUITY); g_dayBlocked=false;
   g_dayStartBal=AccountInfoDouble(ACCOUNT_BALANCE);
   if(g_gvName!=""){ GlobalVariableSet(g_gvName+"_dk",(double)(long)g_curDay);   // v1.02: 日次基準を永続化
      GlobalVariableSet(g_gvName+"_db",g_dayStartBal);
      GlobalVariableSet(g_gvName+"_de",g_dayStartEq); }
   if(g_gvName!="" && g_initBal>0) GlobalVariableSet(g_gvName,g_initBal); }
// v1.02: 日次基準の復元(同日中の再起動で日次ガード基準が現在残高に
// 再アンカーされ、実質の日次許容損失が広がるのを防ぐ)。日付が変わって
// いれば通常のResetDayにフォールバック。
void RestoreOrResetDay()
{
   datetime today=DayStart(TimeCurrent());
   double dk=(g_gvName!="" && GlobalVariableCheck(g_gvName+"_dk"))? GlobalVariableGet(g_gvName+"_dk") : 0.0;
   double db=(g_gvName!="" && GlobalVariableCheck(g_gvName+"_db"))? GlobalVariableGet(g_gvName+"_db") : 0.0;
   if((datetime)(long)dk==today && db>0.0){
      g_curDay=today; g_dayStartBal=db;
      g_dayStartEq=(GlobalVariableCheck(g_gvName+"_de")? GlobalVariableGet(g_gvName+"_de") : 0.0);
      if(g_dayStartEq<=0.0) g_dayStartEq=AccountInfoDouble(ACCOUNT_EQUITY);
      if(GlobalVariableCheck(g_gvName+"_bd") && (datetime)(long)GlobalVariableGet(g_gvName+"_bd")==today) g_balBlockDay=today;
      if(GlobalVariableCheck(g_gvName+"_ds") && (datetime)(long)GlobalVariableGet(g_gvName+"_ds")==today) g_dayBlocked=true;
      PrintFormat("[日次基準復元] 日開始bal=%.2f eq=%.2f%s%s",g_dayStartBal,g_dayStartEq,
                  (g_balBlockDay==today?" BAL_GUARD継続":""),(g_dayBlocked?" DAILY_STOP継続":""));
   }else ResetDay(TimeCurrent());
}
double AtrAt(int handle){ double a[1]; if(handle==INVALID_HANDLE||CopyBuffer(handle,0,1,1,a)<1) return 0.0; return a[0]; }

//--- v1.44: balance基準日次ガード(ティック評価・翌日再開・月内上限)
bool BalGuardActive(){
   if(g_balMonthHalt) return true;
   return (g_balBlockDay!=0 && g_balBlockDay==g_curDay);
}
void BalGuardCheck()
{
   if(InpBalGuardPct<=0.0 || g_halted || g_passLocked) return;
   datetime now=TimeCurrent();
   if(DayStart(now)!=g_curDay) ResetDay(now);
   MqlDateTime bt; TimeToStruct(now,bt); int bmk=bt.year*100+bt.mon;
   if(bmk!=g_balFireMonth){
      g_balFireMonth=bmk; g_balFires=0; g_balMonthHalt=false;
      string bgv=g_gvName+"_bg";
      if(g_gvName!="" && GlobalVariableCheck(bgv)){
         long v=(long)GlobalVariableGet(bgv);
         if((int)(v/100)==bmk){ g_balFires=(int)(v%100); g_balMonthHalt=(g_balFires>InpBalGuardMaxMonth); }
      }
   }
   if(BalGuardActive() || g_dayStartBal<=0.0) return;
   double beq=AccountInfoDouble(ACCOUNT_EQUITY);
   if(beq>g_dayStartBal*(1.0-InpBalGuardPct/100.0)) return;
   g_balBlockDay=g_curDay; g_balFires++;
   if(g_balFires>InpBalGuardMaxMonth) g_balMonthHalt=true;
   if(g_gvName!=""){ GlobalVariableSet(g_gvName+"_bg",(double)((long)bmk*100+g_balFires));
                     GlobalVariableSet(g_gvName+"_bd",(double)(long)g_balBlockDay); }   // v1.02: 当日停止も永続化
   CloseAllMine("BAL_GUARD");
   PrintFormat("[BAL GUARD] eq %.2f <= 日開始bal %.2f -%.1f%% → 全決済・当日停止(月内%d回目%s)",
               beq,g_dayStartBal,InpBalGuardPct,g_balFires,(g_balMonthHalt?"・月末まで停止":""));
   Notify(StringFormat("BAL_GUARD -%.1f%% 全決済・当日停止(%d/月)",InpBalGuardPct,g_balFires));
   FlushNotify();
}
void OnTick(){ BalGuardCheck(); }

//==================================================================
void OnTimer()
{
   FlushNotify();
   datetime now=TimeCurrent(); datetime utc=TimeGMT();
   if(DayStart(now)!=g_curDay) ResetDay(now);
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);

   // 有効期限(docs/174停止規則): 期限後は新規停止。建玉は通常管理(時間切れ決済のみ)。
   if(!g_expired && now>=InpExpiry){
      g_expired=true;
      Print("[EXPIRY] 有効期限到達 → 新規停止。recentfit_screen.py を再実行し構成を更新すること(docs/174)。");
      Notify("EXPIRY 新規停止(再スクリーニング必須)"); FlushNotify();
   }

   // 静的フロア(初期残高基準)
   double floorEq=g_initBal*(1.0-InpMaxLossLimitPct/100.0);
   double guard=floorEq+g_initBal*(InpMaxLossLimitPct-InpAccountFloorDDPct)/100.0;
   if(equity<=guard && !g_halted){ g_halted=true; CloseAllMine("EQUITY_FLOOR");
      PrintFormat("[HALT] equity %.2f <= guard %.2f",equity,guard);
      Notify(StringFormat("FLOOR %.2f 全決済・恒久停止",equity)); FlushNotify(); }
   if(g_halted){ CloseAllMine("HALTED"); return; }

   // 利益ロック(通過確定)
   double gainPct=(g_initBal>0? (equity-g_initBal)/g_initBal*100.0 : 0.0);
   if(InpProfitLockEnable && !g_passLocked && gainPct>=InpLockClosePct){
      g_passLocked=true; CloseAllMine("PROFIT_LOCK");
      PrintFormat("[PROFIT LOCK] equity %+.2f%% >= +%.2f%% → 全決済・恒久ロック",gainPct,InpLockClosePct);
      Notify(StringFormat("PASS_LOCK %+.2f%% 全決済(通過確定)",gainPct)); FlushNotify();
   }
   if(InpProfitLockEnable && !g_passLocked){
      bool armNow=(gainPct>=InpLockArmPct);
      if(armNow && !g_ntfArm){ g_ntfArm=true;
         Notify(StringFormat("ARM %+.2f%% 新規停止(LOCK=+%.2f%%)",gainPct,InpLockClosePct)); }
      else if(!armNow) g_ntfArm=false;
   }
   Comment(StringFormat("Chien_RecentFit_2026H2 | gain %+.2f%% | mult %.1f | %s",gainPct,InpMult,
          (g_passLocked?"PASS_LOCK":
           (g_halted?"HALTED":
            (g_expired?"EXPIRED(新規停止)":
             (InpProfitLockEnable&&gainPct>=InpLockArmPct?"ARMED":
              (g_dayBlocked?"DAY_BLOCKED":
               (BalGuardActive()?"BAL_GUARD":"active"))))))));
   if(g_passLocked){ CloseAllMine("PROFIT_LOCK"); return; }

   BalGuardCheck();

   if(InpDailyStopPct>0){
      double dpnl=equity-g_dayStartEq;
      if(InpNotifyDayWarnPct>0 && g_ntfWarnDay!=g_curDay
         && dpnl<=-g_initBal*InpNotifyDayWarnPct/100.0){
         g_ntfWarnDay=g_curDay;
         Notify(StringFormat("日次-%.1f%%警告 eq=%.0f",InpNotifyDayWarnPct,equity)); FlushNotify(); }
      if(dpnl<=-g_initBal*InpDailyStopPct/100.0 && !g_dayBlocked){ g_dayBlocked=true;
         if(g_gvName!="") GlobalVariableSet(g_gvName+"_ds",(double)(long)g_curDay);   // v1.02: 当日停止も永続化
         PrintFormat("[DAILY STOP] %.2f",dpnl);
         Notify(StringFormat("DAILY_STOP -%.1f%% 当日新規停止",InpDailyStopPct)); FlushNotify(); }
   }

   ManageMonExit();
   ManageSessExit();
   ManageV4Exit();
   ManageBrk(false);   // v1.30: 出口は常に管理

   bool blockNew = (InpProfitStopPct>0 && equity>=g_initBal*(1.0+InpProfitStopPct/100.0))
                   || g_dayBlocked || g_expired
                   || (InpProfitLockEnable && gainPct>=InpLockArmPct)
                   || BalGuardActive();
   if(blockNew) return;

   EntriesMon(utc);
   EntriesSess(utc);
   EntriesV4();
   EntriesHold();
   ManageBrk(true);    // v1.30: 新規はガード通過時のみ
}

//===== Brk (v1.30: GER40 ドンチャン買い。研究セル docs/296: 直前 N 本の高値を確定バー終値が上抜け → 次バー始値で買い。
//        出口 = 建て後の最高終値 − trail×ATR24(建て時)を終値が割ったら次バー始値で決済、または最長保有。研究とのパリティ: 終値判定・次バー執行) =====
double BrkAtr24(string sym)   // トリガーバーの直前 24 本の高安レンジ平均 = 研究の atr24(shift 1)
{
   double h[], l[]; if(CopyHigh(sym,PERIOD_H1,2,24,h)<24 || CopyLow(sym,PERIOD_H1,2,24,l)<24) return 0.0;   // 確定バー 2..25(トリガーバーを含まない = 研究の atr24.shift(1))
   double s=0; for(int i=0;i<24;i++) s+=h[i]-l[i]; return s/24.0;
}
void BrkSave(){ if(g_gvName==""){ return; } GlobalVariableSet(g_gvName+"_brkext",g_brkExt); GlobalVariableSet(g_gvName+"_brkatr",g_brkAtr); GlobalVariableSet(g_gvName+"_brkin",(double)(long)g_brkEntry); }
void ManageBrk(bool allowEntry)
{
   if(g_brkSym=="" || !InpBrkEnable) return;
   datetime bar=iTime(g_brkSym,PERIOD_H1,0); if(bar==0 || bar==g_brkLastBar) return;   // 新しい H1 バーの始値時点で 1 回だけ
   string sym=g_brkSym; int have=CountPos(sym,g_mBrk);
   double c1=iClose(sym,PERIOD_H1,1); if(c1<=0) return;
   if(have>0){
      if(!allowEntry){                                         // 出口管理(毎バー・ガードに関係なく)
         g_brkLastBar=bar;
         if(c1>g_brkExt) g_brkExt=c1;
         int heldH=(g_brkEntry>0? (int)((bar-g_brkEntry)/3600) : 0);
         bool trailHit=(g_brkAtr>0 && c1<g_brkExt-InpBrkAtrTrail*g_brkAtr); bool timeHit=(heldH>=InpBrkMaxHours);
         if(trailHit || timeHit){
            for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue; if(!posinfo.SelectByTicket(tk)) continue;
               if(posinfo.Symbol()==sym && posinfo.Magic()==g_mBrk){ if(trade.PositionClose(tk) && InpVerboseLog) PrintFormat("[Brk EXIT %s] %s close=%.2f ext=%.2f atr=%.2f held=%dh",(trailHit?"TRAIL":"TIME"),sym,c1,g_brkExt,g_brkAtr,heldH); } }
            g_brkExt=0; g_brkAtr=0; g_brkEntry=0; BrkSave();
         } else BrkSave();
      }
      return;
   }
   if(!allowEntry) return;                                     // 新規はガード通過後の呼び出しでのみ
   if(HolidayBlocked(TimeGMT())) { g_brkLastBar=bar; return; }
   g_brkLastBar=bar;
   int ih=iHighest(sym,PERIOD_H1,MODE_HIGH,InpBrkN,2); if(ih<0) return;   // 確定バー 2..N+1 の最高値(バー 1 を含まない = 研究の shift(1))
   double hh=iHigh(sym,PERIOD_H1,ih); double atr=BrkAtr24(sym); if(hh<=0 || atr<=0) return;
   if(c1<=hh) return;
   double ask=SymbolInfoDouble(sym,SYMBOL_ASK), bid=SymbolInfoDouble(sym,SYMBOL_BID), pt=SymbolInfoDouble(sym,SYMBOL_POINT);
   if(ask<=0||bid<=0||pt<=0) return;
   if((ask-bid)/pt>InpBrkMaxSpreadPts){ PrintFormat("[Brk SKIP spread] %s %.1fpt > %.1f",sym,(ask-bid)/pt,InpBrkMaxSpreadPts); return; }
   double notional=g_initBal*InpBrkWeight*InpBrkMult; double lots=LotsForNotional(sym,notional); if(lots<InpMinLot) return;
   int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS); double sl=(InpBrkCatSLAtr>0? NormalizeDouble(ask-InpBrkCatSLAtr*atr,dg) : 0.0);
   trade.SetExpertMagicNumber(g_mBrk);
   if(trade.Buy(lots,sym,0.0,sl,0.0,"RFBrk_"+sym)){
      g_brkExt=c1; g_brkAtr=atr; g_brkEntry=bar; BrkSave();
      if(InpVerboseLog) PrintFormat("[Brk ENTRY] LONG %s lots=%.2f notional=%.0f close=%.2f > hh=%.2f atr=%.2f SL=%.2f",sym,lots,notional,c1,hh,atr,sl);
      if(InpNotifyEntries) Notify(StringFormat("IN Brk %s %.2f",sym,lots));
   } else PrintFormat("[Brk RETRY] %s 発注失敗ret=%d",sym,(int)trade.ResultRetcode());
}

//===== Mon (月曜o2oマルチショット・想定元本=重み×倍率×基準残高) =====
void ManageMonExit()
{
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()!=g_mMon) continue;
      int held=(int)(TimeCurrent()-(datetime)posinfo.Time());
      if(held>=InpMonHoldHours*3600){ if(trade.PositionClose(tk)&&InpVerboseLog)
         PrintFormat("[Mon TIME EXIT] %s",posinfo.Symbol()); }
   }
}
void EntriesMon(datetime utc)
{
   if(g_nMon==0) return;
   MqlDateTime u; TimeToStruct(utc,u);
   if(u.day_of_week!=1) return;
   if(HolidayBlocked(utc)) return;
   int slot=-1; for(int h=0;h<ArraySize(g_monHours);h++) if(u.hour==g_monHours[h]){ slot=h; break; }
   if(slot<0) return;
   datetime hourBar=utc-(utc%3600); int nh=ArraySize(g_monHours);
   trade.SetExpertMagicNumber(g_mMon);
   for(int s=0;s<g_nMon;s++){
      if(g_atrH1[s]==INVALID_HANDLE) continue;
      int key=s*nh+slot;
      if(g_lastShotMon[key]==hourBar) continue;
      string sym=g_monSym[s]; double pip=PipOf(sym);
      double atr=AtrAt(g_atrH1[s]); if(atr<=0) continue;
      double sd=InpCatastropheATR*atr; double sp=sd/pip;
      if(sp<InpMinStopPips){ sp=InpMinStopPips; sd=sp*pip; }
      double ask=SymbolInfoDouble(sym,SYMBOL_ASK), bid=SymbolInfoDouble(sym,SYMBOL_BID);
      if(ask<=0||bid<=0) continue;
      // v1.01修正: スプレッド超過・発注失敗ではショット枠を消費しない(同時間帯内で30秒毎に再試行)
      if((ask-bid)/pip>SpreadCapFor(sym)) continue;
      double notional=g_initBal*g_monW[s]*InpMult/nh;   // 1ショット=重み×倍率÷ショット数
      double lots=LotsForNotional(sym,notional); if(lots<InpMinLot){ g_lastShotMon[key]=hourBar; continue; }
      int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      double sl=NormalizeDouble(ask-sd,dg);
      if(trade.Buy(lots,sym,0.0,sl,0.0,StringFormat("RFMon_%s_h%d",sym,g_monHours[slot])))
         { g_lastShotMon[key]=hourBar;
           if(InpVerboseLog) PrintFormat("[Mon ENTRY] LONG %s h%dUTC lots=%.2f notional=%.0f SL=%.3f",sym,g_monHours[slot],lots,notional,sl);
           if(InpNotifyEntries) Notify(StringFormat("IN Mon %s %.2f",sym,lots)); }
      else PrintFormat("[Mon RETRY] %s h%d 発注失敗ret=%d(同時間帯内で再試行)",sym,g_monHours[slot],(int)trade.ResultRetcode());
   }
}

//===== Sess (v1.10: 時間帯セル。月〜木・建てUTC時に1本・保有h後に決済。docs/233-235) =====
void ManageSessExit()
{
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()!=g_mSes) continue;
      string c=posinfo.Comment(); int p=StringFind(c,"_h"); int h0=(p>=0? (int)StringToInteger(StringSubstr(c,p+2)) : -1);
      int span=4;
      for(int s=0;s<g_nSes;s++) if(g_sesSym[s]==posinfo.Symbol() && g_sesH0[s]==h0){ span=g_sesSpan[s]; break; }
      int held=(int)(TimeCurrent()-(datetime)posinfo.Time());
      if(held>=span*3600){ if(trade.PositionClose(tk)&&InpVerboseLog) PrintFormat("[Sess TIME EXIT] %s h%d",posinfo.Symbol(),h0); }
   }
}
void EntriesSess(datetime utc)
{
   if(g_nSes==0) return;
   MqlDateTime u; TimeToStruct(utc,u);
   if(u.day_of_week<1 || u.day_of_week>4) return;          // 月〜木(金は週末を跨ぐため除外)
   if(HolidayBlocked(utc)) return;
   { string today=StringFormat("%04d.%02d.%02d",u.year,u.mon,u.day);
     if(StringLen(InpSessSkipDates)>0 && StringFind(InpSessSkipDates,today)>=0) return; }   // v1.12: FOMC 等の指定日は建てない
   datetime hourBar=utc-(utc%3600);
   trade.SetExpertMagicNumber(g_mSes);
   for(int s=0;s<g_nSes;s++){
      if(u.hour!=g_sesH0[s]) continue;
      if(g_atrH1Ses[s]==INVALID_HANDLE) continue;
      if(g_lastSes[s]==hourBar) continue;
      string sym=g_sesSym[s]; double pip=PipOf(sym); bool sh=g_sesShort[s]; string side=(sh?"SHORT":"LONG");
      if(CountPos(sym,g_mSes)>0) continue;                 // 同一銘柄の Sess 建玉が残っていれば建てない
      double atr=AtrAt(g_atrH1Ses[s]); if(atr<=0) continue;
      double sd=InpCatastropheATR*atr; double sp=sd/pip;
      if(sp<InpSessMinStopPips){ sp=InpSessMinStopPips; sd=sp*pip; }
      double ask=SymbolInfoDouble(sym,SYMBOL_ASK), bid=SymbolInfoDouble(sym,SYMBOL_BID);
      if(ask<=0||bid<=0) continue;
      double spr=(ask-bid)/pip;
      if(spr>InpSessMaxSpreadPips){
         if(g_sesSkip[s]!=hourBar){ g_sesSkip[s]=hourBar;
            PrintFormat("[Sess SKIP spread] %s h%dUTC spread=%.2fpip > cap=%.2f",sym,g_sesH0[s],spr,InpSessMaxSpreadPips); }
         continue;                                          // 同時間帯内で 30 秒毎に再試行
      }
      double notional=g_initBal*g_sesW[s]*InpSessMult;
      double lots=LotsForNotional(sym,notional); if(lots<InpMinLot){ g_lastSes[s]=hourBar; continue; }
      int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      string cmt=StringFormat("RFSess_%s_h%d",sym,g_sesH0[s]);
      bool ok; double sl;
      if(sh){ sl=NormalizeDouble(bid+sd,dg); ok=trade.Sell(lots,sym,0.0,sl,0.0,cmt); }
      else  { sl=NormalizeDouble(ask-sd,dg); ok=trade.Buy (lots,sym,0.0,sl,0.0,cmt); }
      if(ok){ g_lastSes[s]=hourBar;
              if(InpVerboseLog) PrintFormat("[Sess ENTRY] %s %s h%dUTC +%dh lots=%.2f notional=%.0f spread=%.2fpip SL=%.5f",side,sym,g_sesH0[s],g_sesSpan[s],lots,notional,spr,sl);
              if(InpNotifyEntries) Notify(StringFormat("IN Sess %s %s %.2f",side,sym,lots)); }
      else PrintFormat("[Sess RETRY] %s h%d 発注失敗ret=%d",sym,g_sesH0[s],(int)trade.ResultRetcode());
   }
}

//===== v4 (日足k≥4合議・想定元本ベース) =====
int V4Signal(string sym, int rsiHandle)
{
   double c[]; ArraySetAsSeries(c,true);
   int need=MathMax(InpV4_BBwin+2, InpV4_streak+3);
   if(CopyClose(sym,PERIOD_D1,1,need+2,c)<need+1) return -99;   // v1.01: データ未同期(0=合議不成立と区別)
   double rb[1];
   if(rsiHandle==INVALID_HANDLE || CopyBuffer(rsiHandle,0,1,1,rb)<1) return -99;
   double rsi=rb[0];
   double mean=0; for(int k=1;k<=InpV4_BBwin;k++) mean+=c[k]; mean/=InpV4_BBwin;
   double var=0; for(int k=1;k<=InpV4_BBwin;k++) var+=(c[k]-mean)*(c[k]-mean); var/=(InpV4_BBwin-1);
   double sd=MathSqrt(var); double z=(sd>0)?(c[0]-mean)/sd:0.0;
   int down=0; for(int k=0;k<12;k++){ if(c[k]<c[k+1]) down++; else break; }
   int up=0;   for(int k=0;k<12;k++){ if(c[k]>c[k+1]) up++;   else break; }
   double ret=(c[1]!=0)?(c[0]-c[1])/c[1]:0.0; double mv=InpV4_dayMovePct/100.0;
   int buy = (rsi<InpV4_RSIlo?1:0)+(z<-InpV4_BBz?1:0)+(down>=InpV4_streak?1:0)+(ret<-mv?1:0);
   int sell= (rsi>InpV4_RSIhi?1:0)+(z> InpV4_BBz?1:0)+(up  >=InpV4_streak?1:0)+(ret> mv?1:0);
   if(buy>=4 && buy>sell) return 1;
   if(sell>=4 && sell>buy && InpV4AllowShort) return -1;
   return 0;
}
void ManageV4Exit()
{
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()!=g_mV4) continue;
      int heldDays=(int)((TimeCurrent()-(datetime)posinfo.Time())/86400);
      if(heldDays>=InpV4_MaxHoldDays){ if(trade.PositionClose(tk)&&InpVerboseLog)
         PrintFormat("[v4 TIME EXIT %dd] %s",heldDays,posinfo.Symbol()); }
   }
}
int g_v4Tries[MAXLEG];   // v1.01: v4のバー内再試行カウンタ

void V4Fail(int i, datetime db, string why)
{
   g_v4Tries[i]++;                                   // 30秒タイマーで再試行(最大120回≈1時間)
   if(g_v4Tries[i]>=120){
      PrintFormat("[v4 GIVEUP] %s %s %d回失敗→当バー断念",g_v4Sym[i],why,g_v4Tries[i]);
      g_lastV4Bar[i]=db; g_v4Tries[i]=0;
   }
}

void EntriesV4()
{
   if(g_nV4==0) return;
   if(HolidayBlocked(TimeGMT())) return;
   trade.SetExpertMagicNumber(g_mV4);
   for(int i=0;i<g_nV4;i++){
      if(g_atrD1[i]==INVALID_HANDLE) continue;
      string sym=g_v4Sym[i];
      datetime db=(datetime)iTime(sym,PERIOD_D1,0);
      if(db==0 || db==g_lastV4Bar[i]) continue;
      // v1.01修正: バー消費は「成立/合議不成立の確定/既保有」時のみ。
      // 旧実装は判定前に消費していたため、データ未同期・発注失敗が当日空振りに恒久化した。
      if(CountPos(sym,g_mV4)>0){ g_lastV4Bar[i]=db; g_v4Tries[i]=0; continue; }
      int sig=V4Signal(sym,g_rsiD1[i]);
      if(sig==-99){ V4Fail(i,db,"データ未同期"); continue; }
      if(sig==0){
         if(InpVerboseLog && g_v4Tries[i]==0) PrintFormat("[v4 EVAL] %s 合議不成立(バー%s)",sym,TimeToString(db,TIME_DATE));
         g_lastV4Bar[i]=db; g_v4Tries[i]=0; continue; }
      double atr=AtrAt(g_atrD1[i]);
      if(atr<=0){ V4Fail(i,db,"ATR未取得"); continue; }
      double sd=InpV4_SLatr*atr; double tpd=InpV4_RR*sd;
      double notional=g_initBal*g_v4W[i]*InpMult;
      double lots=LotsForNotional(sym,notional);
      if(lots<InpMinLot){ g_lastV4Bar[i]=db; g_v4Tries[i]=0; continue; }   // 恒久条件=消費
      int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      bool ok=false;
      if(sig>0){ double e=SymbolInfoDouble(sym,SYMBOL_ASK);
         double sl=NormalizeDouble(e-sd,dg), tp=NormalizeDouble(e+tpd,dg);
         ok=trade.Buy(lots,sym,0.0,sl,tp,"RFv4_"+sym);
         if(ok){
            if(InpVerboseLog) PrintFormat("[v4 ENTRY] LONG %s lots=%.2f notional=%.0f",sym,lots,notional);
            if(InpNotifyEntries) Notify(StringFormat("IN v4 L %s %.2f",sym,lots)); } }
      else     { double e=SymbolInfoDouble(sym,SYMBOL_BID);
         double sl=NormalizeDouble(e+sd,dg), tp=NormalizeDouble(e-tpd,dg);
         ok=trade.Sell(lots,sym,0.0,sl,tp,"RFv4_"+sym);
         if(ok){
            if(InpVerboseLog) PrintFormat("[v4 ENTRY] SHORT %s lots=%.2f notional=%.0f",sym,lots,notional);
            if(InpNotifyEntries) Notify(StringFormat("IN v4 S %s %.2f",sym,lots)); } }
      if(ok){ g_lastV4Bar[i]=db; g_v4Tries[i]=0; }
      else  V4Fail(i,db,StringFormat("発注失敗ret=%d",(int)trade.ResultRetcode()));
   }
}

//===== Hold (連続LONG・災害SLのみ。研究セル=単純保有とのパリティ) =====
// フラットなら建て直す(ガード当日・期限後・ロック中を除く)。
// ⚠手決済しても翌タイマーで再建てされる。恒久停止したい時は InpHoldEnable=false で再アタッチ。
void EntriesHold()
{
   if(g_nHold==0) return;
   if(HolidayBlocked(TimeGMT())) return;
   trade.SetExpertMagicNumber(g_mHold);
   for(int i=0;i<g_nHold;i++){
      string sym=g_holdSym[i];
      if(CountPos(sym,g_mHold)>0) continue;
      datetime now=TimeCurrent();
      if(g_lastHoldTry[i]!=0 && now-g_lastHoldTry[i]<3600) continue;   // 再試行は1時間毎
      double ask=SymbolInfoDouble(sym,SYMBOL_ASK), bid=SymbolInfoDouble(sym,SYMBOL_BID);
      double pt=SymbolInfoDouble(sym,SYMBOL_POINT);
      if(ask<=0||bid<=0||pt<=0) continue;
      if((ask-bid)/pt>InpHoldMaxSpreadPts){ g_lastHoldTry[i]=now; continue; }
      double notional=g_initBal*g_holdW[i]*InpMult;
      double lots=LotsForNotional(sym,notional);
      g_lastHoldTry[i]=now;
      if(lots<InpMinLot) continue;
      int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      double sl=NormalizeDouble(ask*(1.0-InpHoldCatSLPct/100.0),dg);
      if(trade.Buy(lots,sym,0.0,sl,0.0,"RFHold_"+sym)){
         if(InpVerboseLog) PrintFormat("[Hold ENTRY] LONG %s lots=%.2f notional=%.0f SL=%.1f",sym,lots,notional,sl);
         if(InpNotifyEntries) Notify(StringFormat("IN Hold %s %.2f",sym,lots)); }
   }
}
//+------------------------------------------------------------------+
//| 残存リスク(誠実な記録・docs/175):                                 |
//|  ・本構成は直近12ヶ月窓で選び直近12ヶ月窓で校正=構造的に楽観。    |
//|    全期間サンプルでは失格24.8%(標準4.8x)/32.2%(速攻7.2x)。        |
//|  ・選抜セルはノイズで入れ替わる(docs/165で実証済み)。本トラックは |
//|    それを承知の上のEVベット=チャレンジ費用2回分が損失上限。       |
//|  ・Mon GBPJPY/AUDJPYは正攻法口座のv7/v7x(5月等)・FTMO PDのv7と    |
//|    同一日・同方向になり得る=別業者での運用を推奨(重複取引規則)。  |
//|  ・想定元本サイジング: 研究セル(価格変化率×重み)と直接パリティ。  |
//|    ガード類はリスクベースEA(v1.44)と同一。                        |
//|  ・日次ガードはティック評価だが週末ギャップ/急変時のスリップは    |
//|    防げない(docs/169クラッシュ監査参照)。                         |
//|  ・JP225 Holdは配当調整・スワップが業者差大=デモで実測すること。  |
//+------------------------------------------------------------------+
