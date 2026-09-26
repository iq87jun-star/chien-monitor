//+------------------------------------------------------------------+
//| ★FN Stellar Instant 20k 口座11988011 G構成(docs/298・docs/299)      |
//|  2026-09-26 ユーザー決定「Instant G で作成」— Instant v1.02 を置換  |
//|  構成 G: Mon2(GBPJPY/AUDJPY)×4 + Mon NAS100/US500 ×1(E-Mon移設) |
//|  ⚠装着条件(規約): FN100k #14074882 を季節RG3 からギャンブル版へ     |
//|    切り替えた後にのみ装着(切替前は RG3 の E-Mon と同一取引=禁止)  |
//|  ⚠FN Instant のニュース規則(docs/182 の通知)は未確認。確認まで     |
//|    InpMonSkipDates に高インパクト日(FOMC/CPI/NFP の月曜)を入れる   |
//|  ⚠装着前に必須: 旧EA(Magic 761230系)を外し、旧建玉(v7/EMon/E5)を   |
//|    全て手動クローズしてフラット化を確認すること(E5は月間保有あり)   |
//|  ⚠InpHwmOverride: FNダッシュボードのMLLフロア/balance最高値を確認し |
//|    $20,000超の高値がPD稼働期にある場合はその値を入力(甘いガード防止)|
//|   Chien_RecentFit_2026H2_Instant — 直近特化トラック Instant版 v1.0 |
//|      (docs/174-175 設計 / docs/176 §7.8.2 Instant適応の決定)       |
//|                                                                   |
//|  ★FN Stellar Instant 20k 専用。Prop版(Chien_RecentFit_2026H2_Prop)|
//|    との差分:                                                      |
//|    1) Holdレッグ(JP225)を除外 — FN100kチャレンジの季節(指数)との   |
//|       Instant↔チャレンジ同一取引禁止(docs/161 §4③)に接触するため。|
//|       残り3レッグを再正規化(0.348/0.299/0.283 → 0.374/0.322/0.304)|
//|    2) 倍率 4.8x → 4.0x(安全側) — InstantのトレーリングMLL−6%に    |
//|       対し月中DD生−4.62%(4.8x)は余白1.4%のみ。4.0xで余白≈2.15%。  |
//|    3) ガード: 静的フロア(−10%系)を廃し、トレーリングDDガードへ     |
//|       (FNフロア=min(HWM−6%×初期, 建値)。docs/154/161で建値ロック  |
//|       公式確認済み。EAはequity-HWM追跡=FNのbalance-HWMより保守側)。|
//|    4) 利益ロック無効(Instantは目標なし)。+10%到達で通知のみ        |
//|       (スケールアップ=累計出金10%+出金1回, docs/154)。            |
//|                                                                   |
//|  構成(recentfit_screen.py 2026-07-30凍結値の再正規化):            |
//|    Mon  GBPJPY 37.4% / AUDJPY 32.2%  (月曜o2o LONG・24h)          |
//|    v4   USDJPY 30.4%                 (日足k≥4合議・SL/TP付き)     |
//|    倍率: 標準4.0x(グロス≈4.0x)                                    |
//|                                                                   |
//|  停止規則(docs/174事前登録+docs/176 §7.8.2):                      |
//|    ・有効期限2026-10-31: 期限後は新規停止=再スクリーニング必須     |
//|    ・トレーリングフロア+1%で全決済・恒久停止(口座保全)            |
//|  ⚠ 本EAは既存Instant 20kのPD_noV4(Magic 761230系)を置き換える。   |
//|    移行手順はdocs/177。旧EAの残存建玉は手動クローズしてから装着。  |
//|  ⚠ FN側の実フロアは口座開設来のbalance-HWM基準。PD稼働期に高値が   |
//|    ある場合は InpHwmOverride にFNダッシュボードのHWM値を入力する   |
//|    こと(EA初期化のHWMが実態より低いとガードが甘くなる)。          |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.13"
#property strict
//| v1.01(Prop版から移植): v4のデータ未同期/発注失敗のバー内再試行・  |
//|   合議不成立の可視化・Monショット枠の発注前消費修正               |
//| v1.02: 日次ガード基準の再起動復元(同日中の再アタッチで基準が      |
//|   現在残高に再アンカーされ緩むのを防ぐ)・Mon時刻数の範囲保護      |
//| v1.10(docs/299): G構成。指数 Mon レッグ対応(1pip=1pt・bps スプレッド|
//|   上限)・SPX500/NDX100 等の銘柄別名・Mon スキップ日(ニュース日)   |
//|   ・v4 レッグ既定空(旧 v4 建玉は Magic ベースで従来通り時間決済)  |
#property description "[RecentFit INSTANT G] FN Stellar Instant 20k. Mon GBPJPY+AUDJPY x4 + Mon NAS100/US500 x1 (docs/298 G). mult 4.0. Trailing -6pct guard (breakeven lock, equity-HWM), no profit target, +10pct notify. Expiry 2026-10-31."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

input bool   InpAcknowledgeBet  = true;   // 本トラック=直近過剰適合の明示ベット(docs/174)を承認

input group "=== 構成(銘柄:重み CSV。既定=凍結値のJP225除外・再正規化) ==="
input string InpMonLegs  = "GBPJPY:0.537,AUDJPY:0.463,NAS100:0.125,US500:0.125"; // Mon: 月曜o2o LONG(FX=Mon2 ×4 / 指数=各×0.5)
input string InpV4Legs   = "";                          // v4: G構成では空(5年−0.7%・docs/290)
input string InpHoldLegs = "";                          // Hold: Instant版は空(JP225除外, docs/176 §7.8.2)
input double InpMult     = 4.0;    // リスク倍率(G: Σw=1.25 → グロス5.0x。docs/298 MLL接触30%/年)

input group "=== 有効期限(直近特化=賞味期限つき。docs/174停止規則) ==="
input datetime InpExpiry = D'2026.12.31 23:59';  // 期限後は新規停止(四半期レビューで更新・docs/299)

input group "=== 口座/基準残高 ==="
input double InpInitialBalance   = 20000.0; // 固定(docs/241 §1d: 自動取得は誤基準の事故あり)
input bool   InpBaselineReset    = false; // 基準残高とHWMを取り直す時のみtrue(1回だけ・戻すこと)

input group "=== トレーリングDDガード(FN Instant: フロア=min(HWM-6%x初期,建値)) ==="
input double InpTrailWidthPct    = 6.0;   // FN InstantトレーリングMLL幅%(docs/154/161)
input double InpTrailArmBufPct   = 2.0;   // FNフロア+この%で新規停止(回復で自動再開)
input double InpTrailHaltBufPct  = 1.0;   // FNフロア+この%で全決済+恒久停止
input double InpHwmOverride      = 0.0;   // 0=自動 / FNダッシュボードの実HWM(balance)を入力(PD稼働期の高値引継ぎ)

input group "=== v1.44 balance基準日次ガード(規則は無いが搭載=内部規律) ==="
input double InpBalGuardPct      = 4.0;   // equity≤日開始balance−この%で全決済+当日停止(0=無効)
input int    InpBalGuardMaxMonth = 2;     // 月内発動上限(超過は月末まで新規停止)
input double InpDailyStopPct     = 4.0;   // 日次equity−この%で当日新規停止(内部規律)

input group "=== 利益ロック(Instantは目標なし=既定OFF) ==="
input bool   InpProfitLockEnable = false; // Instantでは使わない(残す: 任意の利確ラインとして)
input double InpLockArmPct    = 9.9;
input double InpLockClosePct  = 10.05;
input double InpProfitStopPct = 0.0;      // 0=無効
input double InpNotifyStepPct = 10.0;     // +この%到達で通知(スケールアップ=累計出金10%+出金1回)

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
input string InpMonSpreadCaps = "GBPJPY:2.9,AUDJPY:2.9"; // FXペア別上限(edge20 §3)
input double InpIdxMaxSpreadBps = 3.0;   // 指数レッグのスプレッド上限(bps。NAS100≈1, US500≈1)
input int    InpIdxEntryOffsetMin = 5;    // 指数レッグ: 米国現物寄り(13:30夏/14:30冬 UTC)からの遅延分
input int    InpIdxEntryWindowMin = 60;   // 指数レッグ: 建て試行の窓(分)。窓内で30秒毎に再試行
input string InpMonSkipDates  = "";      // Mon を建てない日(UTC "2026.10.05,2026.11.02"。FN ニュース規則確認まで高インパクト日を入れる)
input bool   InpMonSkipIdxOnly = true;   // true=スキップ日は指数レッグのみ見送り / false=Mon 全レッグ見送り

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

input group "=== Hold レッグ設定(Instant版は既定OFF) ==="
input bool   InpHoldEnable    = false;  // ⚠trueにする前にdocs/176 §7.8.2(FN100k季節との接触)を確認
input double InpHoldCatSLPct  = 15.0;
input double InpHoldMaxSpreadPts = 3000.0;

input group "=== 防御フィルタ(docs/148) ==="
input bool   InpHolidayFilterEnable = true; // 12/20〜1/3は新規停止
input string InpJpHolidayMondays = "2026.10.12,2026.11.02,2026.11.23,2027.01.11,2027.02.22,2027.03.22,2027.05.03,2027.07.19,2027.09.20,2027.10.11,2027.11.22"; // 日本の祝日月曜 + 翌火曜が祝日の月曜(UTC 日付)。JPY を含む Mon を建てない(docs/303 Q53・docs/304 Q56)。2028 年分は要追記
input bool   InpJpHolidayJpyOnly = true;   // true=JPY を含む Mon レッグのみ見送り / false=Mon 全レッグ
input string InpAuNzHolidayMondays = "2026.10.05,2026.10.26,2026.12.28,2027.01.04,2027.02.08,2027.03.29,2027.04.26,2027.06.07,2027.06.14,2027.10.04,2027.10.25,2027.12.27"; // 豪(NSW)・NZ の祝日月曜(UTC 日付)。AUD/NZD を含む Mon レッグを建てない(docs/304 Q56: 該当日は平均 −2.7 bps)。2028 年分は要追記

input group "=== 共通 ==="
input double InpMinLot = 0.01;
input double InpMaxLot = 50.0;
input long   InpMagicBase = 943200;  // Mon=+1/v4=+2/Hold=+3 (Prop版943100/旧PD 761230と区別)
input int    InpSlippagePoints = 30;
input bool   InpVerboseLog = true;

//==================================================================
CTrade        trade;
CPositionInfo posinfo;

#define MAXLEG 8
string  g_monSym[MAXLEG];  double g_monW[MAXLEG];  int g_nMon=0;
string  g_v4Sym[MAXLEG];   double g_v4W[MAXLEG];   int g_nV4=0;
string  g_holdSym[MAXLEG]; double g_holdW[MAXLEG]; int g_nHold=0;
int     g_monHours[]; int g_atrH1[MAXLEG]; int g_atrD1[MAXLEG]; int g_rsiD1[MAXLEG];
datetime g_lastShotMon[MAXLEG*8];
datetime g_lastV4Bar[MAXLEG];
datetime g_lastHoldTry[MAXLEG];
double   g_initBal=0.0;
double   g_hwm=0.0;            // equity最高値(トレーリングDD基準・端末保存・FNのbalance-HWMより保守側)
bool     g_trailArmed=false;   // トレーリングDD: 新規停止中
string   g_gvHwm="";
double   g_dayStartEq=0.0, g_dayStartBal=0.0;
datetime g_curDay=0, g_balBlockDay=0;
int      g_balFireMonth=-1, g_balFires=0;
bool     g_balMonthHalt=false;
bool     g_halted=false, g_dayBlocked=false, g_passLocked=false, g_expired=false;
bool     g_ntfStep=false;
string   g_ntfBuf=""; bool g_ntfArm=false; datetime g_ntfWarnDay=0;
string   g_gvName="";
long     g_mMon=0, g_mV4=0, g_mHold=0;
string   g_sizeWarned="";

//==================================================================
string ResolveSymbol(string want)
{
   string suf[]={"",".pi",".raw",".ecn",".stp",".pro",".cash",".r",".c",".m","m",".spot","-cash",".sd","+",".i","_SB","_raw",".a",".z"};
   string bases[]; ArrayResize(bases,40); int nb=0;
   bases[nb++]=want;
   string U=want; StringToUpper(U);
   if(StringFind(U,"SPX")>=0 || StringFind(U,"US500")>=0 || StringFind(U,"500")==0){
      bases[nb++]="US500"; bases[nb++]="SPX500"; bases[nb++]="SP500"; bases[nb++]="USA500"; bases[nb++]="US500Cash"; bases[nb++]="SPX"; }
   else if(StringFind(U,"NAS")>=0 || StringFind(U,"USTEC")>=0 || StringFind(U,"NDX")>=0 || StringFind(U,"US100")>=0){
      bases[nb++]="NAS100"; bases[nb++]="USTEC"; bases[nb++]="US100"; bases[nb++]="NDX100"; bases[nb++]="USTECH"; bases[nb++]="NDX"; }
   else if(StringFind(U,"JP225")>=0 || StringFind(U,"JPN")>=0 || StringFind(U,"NIK")>=0){
      bases[nb++]="JP225"; bases[nb++]="JPN225"; bases[nb++]="NIKKEI225"; bases[nb++]="JP225Cash"; bases[nb++]="NI225"; bases[nb++]="JPN225.cash"; }
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
// v1.10: 指数CFD(桁数≤3・非JPY)は 1pip=1ポイント。FXは従来通り。
double PipOf(string s){
   if(StringFind(s,"JPY")>=0) return 0.01;
   int dg=(int)SymbolInfoInteger(s,SYMBOL_DIGITS);
   if(dg>=4) return 0.0001;
   return 1.0;
}
bool IsIdx(string s){ return (PipOf(s)>=1.0); }
double SpreadBps(string s){
   double a=SymbolInfoDouble(s,SYMBOL_ASK), b=SymbolInfoDouble(s,SYMBOL_BID);
   if(a<=0||b<=0) return 1e9;
   return (a-b)/((a+b)/2.0)*1e4;
}
bool MonSkipDate(datetime utc, bool idx){
   if(StringLen(InpMonSkipDates)==0) return false;
   if(InpMonSkipIdxOnly && !idx) return false;
   MqlDateTime u; TimeToStruct(utc,u);
   string today=StringFormat("%04d.%02d.%02d",u.year,u.mon,u.day);
   return (StringFind(InpMonSkipDates,today)>=0);
}
// v1.10: 米国夏時間(3月第2日曜〜11月第1日曜)。指数 Mon の研究定義(docs/298 mon_cell)は
//   米国現物の寄り(9:30 ET)→翌日寄り o2o のため、指数レッグは 13:30(夏)/14:30(冬) UTC から建てる。
bool UsDst(datetime utc){
   MqlDateTime u; TimeToStruct(utc,u);
   if(u.mon>=4 && u.mon<=10) return true;
   if(u.mon==3)  return (u.day-u.day_of_week>=8);   // 直近の日曜が 8 日以降=第2日曜を過ぎた
   if(u.mon==11) return (u.day-u.day_of_week<1);    // 11月の日曜をまだ跨いでいない
   return false;
}
bool IdxEntryWindow(datetime utc){
   int mod=(int)(utc%86400)/60;                     // UTC 分
   int openMin=(UsDst(utc)? 13*60+30 : 14*60+30)+InpIdxEntryOffsetMin;
   return (mod>=openMin && mod<openMin+InpIdxEntryWindowMin);
}

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
bool IsMine(long m){ return (m==g_mMon||m==g_mV4||m==g_mHold); }
void CloseAllMine(string why){
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(IsMine(posinfo.Magic())) trade.PositionClose(tk); }
   if(InpVerboseLog) PrintFormat("[CLOSE ALL %s]",why);
}

void Notify(string s){ if(!InpNotifyEnable) return; if(g_ntfBuf!="") g_ntfBuf+=" | "; g_ntfBuf+=s; }
void FlushNotify(){
   if(g_ntfBuf=="") return;
   string msg="[RFI] "+g_ntfBuf;
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
bool JpHolidayMonday(datetime utc, string sym){   // docs/303 Q53: 東京休場の月曜は建てない
   if(StringLen(InpJpHolidayMondays)==0) return false;
   MqlDateTime u; TimeToStruct(utc,u);
   string today=StringFormat("%04d.%02d.%02d",u.year,u.mon,u.day);
   if((StringFind(sym,"AUD")>=0||StringFind(sym,"NZD")>=0) && StringLen(InpAuNzHolidayMondays)>0 && StringFind(InpAuNzHolidayMondays,today)>=0) return true;   // docs/304 Q56
   if(InpJpHolidayJpyOnly && StringFind(sym,"JPY")<0) return false;
   return (StringFind(InpJpHolidayMondays,today)>=0);
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
   int nh=SplitHours(InpMonHoursUTC,g_monHours);
   if(nh>8){ ArrayResize(g_monHours,8); nh=8;                       // v1.02: g_lastShotMon[MAXLEG*8]の範囲保護
      Print("⚠ Mon時刻は最大8個まで→先頭8個のみ使用"); }
   if(g_nMon==0 && g_nV4==0 && g_nHold==0){ Print("レッグが1つも解決できず"); return INIT_FAILED; }
   if(g_nMon>0 && nh==0){ Print("Mon時刻のパース失敗"); return INIT_FAILED; }
   g_mMon=InpMagicBase+1; g_mV4=InpMagicBase+2; g_mHold=InpMagicBase+3;

   g_gvName=StringFormat("ChienRFI_base_%I64d_%I64d",
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

   // HWM(トレーリングDD基準)の永続化: 再起動/再アタッチで引き継ぐ。
   // ⚠FNの実フロアは口座開設来のbalance-HWM基準。PD稼働期の高値がある場合は
   //   InpHwmOverrideにダッシュボードの値を入れる(入れないとガードが実態より甘くなる)。
   g_gvHwm=StringFormat("ChienRFI_hwm_%I64d_%I64d",
                        (long)AccountInfoInteger(ACCOUNT_LOGIN),(long)InpMagicBase);
   {
      double eq0=AccountInfoDouble(ACCOUNT_EQUITY);
      if(InpHwmOverride>0.0)
           g_hwm=MathMax(InpHwmOverride,eq0);
      else if(!InpBaselineReset && GlobalVariableCheck(g_gvHwm))
           g_hwm=MathMax(GlobalVariableGet(g_gvHwm),eq0);
      else g_hwm=MathMax(g_initBal,eq0);
      GlobalVariableSet(g_gvHwm,g_hwm);
      PrintFormat("[HWM] %.2f (FNフロア=min(HWM-%.1f%%x初期, 建値)=%.2f)",
                  g_hwm,InpTrailWidthPct,MathMin(g_hwm-g_initBal*InpTrailWidthPct/100.0,g_initBal));
   }

   for(int i=0;i<g_nMon;i++) g_atrH1[i]=iATR(g_monSym[i],PERIOD_H1,InpAtrPeriodH1);
   for(int i=0;i<g_nV4;i++){
      g_atrD1[i]=iATR(g_v4Sym[i],PERIOD_D1,InpV4_ATR);
      g_rsiD1[i]=iRSI(g_v4Sym[i],PERIOD_D1,InpV4_RSI,PRICE_CLOSE); }
   ArrayInitialize(g_lastShotMon,0); ArrayInitialize(g_lastV4Bar,0); ArrayInitialize(g_lastHoldTry,0);
   trade.SetDeviationInPoints(InpSlippagePoints);
   RestoreOrResetDay();
   double wsum=0; for(int i=0;i<g_nMon;i++) wsum+=g_monW[i];
   for(int i=0;i<g_nV4;i++) wsum+=g_v4W[i];
   for(int i=0;i<g_nHold;i++) wsum+=g_holdW[i];
   PrintFormat("[INIT RecentFit INSTANT] initBal=%.0f mult=%.1f Σw=%.3f (グロス想定≈%.1fx) trail=%.1f%% expiry=%s Magic=%I64d/%I64d/%I64d",
      g_initBal,InpMult,wsum,wsum*InpMult,InpTrailWidthPct,TimeToString(InpExpiry,TIME_DATE),g_mMon,g_mV4,g_mHold);
   for(int i=0;i<g_nMon;i++){
      double nt=g_initBal*g_monW[i]*InpMult/(IsIdx(g_monSym[i])?1:MathMax(nh,1));
      PrintFormat("[INIT G v1.10] Mon %s w=%.3f %s 1ショット想定元本=%.0f → 推定lots=%.2f (min=%.2f step=%.2f)",
         g_monSym[i],g_monW[i],(IsIdx(g_monSym[i])?"指数(1pip=1pt,bps上限)":"FX"),nt,LotsForNotional(g_monSym[i],nt),
         SymbolInfoDouble(g_monSym[i],SYMBOL_VOLUME_MIN),SymbolInfoDouble(g_monSym[i],SYMBOL_VOLUME_STEP));
   }
   PrintFormat("[INIT G v1.10] 指数レッグ=米国現物寄り+%d分から%d分窓の単発(現在%s) 24h保有",InpIdxEntryOffsetMin,InpIdxEntryWindowMin,(UsDst(TimeGMT())?"夏時間13:30UTC":"冬時間14:30UTC"));
   PrintFormat("[INIT G v1.10] skipDates='%s' idxOnly=%s idxSpreadCap=%.1fbps",InpMonSkipDates,(InpMonSkipIdxOnly?"true":"false"),InpIdxMaxSpreadBps);
   Print("[NOTE] G構成(docs/298/299)。装着は FN100k #14074882 のギャンブル版切替後のみ(RG3 E-Mon と同一取引回避)。旧 Instant v1.02 の建玉は同 Magic のため引き継いで時間決済。");
   PrintFormat("[INIT JpHoliday v%s] 祝日月曜スキップ='%s' jpyOnly=%s 豪NZ='%s'(docs/303/304)","1.13",InpJpHolidayMondays,(InpJpHolidayJpyOnly?"true":"false"),InpAuNzHolidayMondays);
   EventSetTimer(30);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){
   EventKillTimer();
   for(int i=0;i<g_nMon;i++) if(g_atrH1[i]!=INVALID_HANDLE) IndicatorRelease(g_atrH1[i]);
   for(int i=0;i<g_nV4;i++){ if(g_atrD1[i]!=INVALID_HANDLE) IndicatorRelease(g_atrD1[i]);
      if(g_rsiD1[i]!=INVALID_HANDLE) IndicatorRelease(g_rsiD1[i]); }
}

datetime DayStart(datetime t){ MqlDateTime s; TimeToStruct(t,s); s.hour=0;s.min=0;s.sec=0; return StructToTime(s); }
void ResetDay(datetime t){ g_curDay=DayStart(t); g_dayStartEq=AccountInfoDouble(ACCOUNT_EQUITY); g_dayBlocked=false;
   g_dayStartBal=AccountInfoDouble(ACCOUNT_BALANCE);
   if(g_gvName!=""){ GlobalVariableSet(g_gvName+"_dk",(double)(long)g_curDay);   // v1.02: 日次基準を永続化
      GlobalVariableSet(g_gvName+"_db",g_dayStartBal);
      GlobalVariableSet(g_gvName+"_de",g_dayStartEq); }
   if(g_gvName!="" && g_initBal>0) GlobalVariableSet(g_gvName,g_initBal);
   if(g_gvHwm!="" && g_hwm>0) GlobalVariableSet(g_gvHwm,g_hwm); }
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

   // トレーリングDDガード(FN Instant: フロア=min(HWM−幅%×初期, 建値), docs/154/161)
   if(equity>g_hwm){ g_hwm=equity; if(g_gvHwm!="") GlobalVariableSet(g_gvHwm,g_hwm); }
   double fnFloor=MathMin(g_hwm-g_initBal*InpTrailWidthPct/100.0, g_initBal);
   double haltLvl=fnFloor+g_initBal*InpTrailHaltBufPct/100.0;
   double armLvl =fnFloor+g_initBal*InpTrailArmBufPct/100.0;
   if(equity<=haltLvl && !g_halted){ g_halted=true; CloseAllMine("TRAIL_FLOOR");
      PrintFormat("[HALT] equity %.2f <= trail停止線 %.2f (FNフロア %.2f)",equity,haltLvl,fnFloor);
      Notify(StringFormat("TRAIL_FLOOR %.2f 全決済・恒久停止 (FNフロア=%.0f)",equity,fnFloor)); FlushNotify(); }
   if(g_halted){ CloseAllMine("HALTED"); return; }
   bool tArm=(equity<=armLvl);
   if(tArm!=g_trailArmed){ g_trailArmed=tArm;
      PrintFormat("[TRAIL %s] eq=%.2f FNフロア=%.2f (+%.1f%%線)",(tArm?"ARMED=新規停止":"DISARM=新規再開"),equity,fnFloor,InpTrailArmBufPct);
      Notify(StringFormat("TRAIL %s eq=%.0f (FNフロア=%.0f)",(tArm?"新規停止":"新規再開"),equity,fnFloor)); FlushNotify(); }

   // 利益ロック(既定OFF・任意の利確ラインとして残置)
   double gainPct=(g_initBal>0? (equity-g_initBal)/g_initBal*100.0 : 0.0);
   if(InpProfitLockEnable && !g_passLocked && gainPct>=InpLockClosePct){
      g_passLocked=true; CloseAllMine("PROFIT_LOCK");
      PrintFormat("[PROFIT LOCK] equity %+.2f%% >= +%.2f%% → 全決済・恒久ロック",gainPct,InpLockClosePct);
      Notify(StringFormat("LOCK %+.2f%% 全決済",gainPct)); FlushNotify();
   }
   if(InpProfitLockEnable && !g_passLocked){
      bool armNow=(gainPct>=InpLockArmPct);
      if(armNow && !g_ntfArm){ g_ntfArm=true;
         Notify(StringFormat("ARM %+.2f%% 新規停止(LOCK=+%.2f%%)",gainPct,InpLockClosePct)); }
      else if(!armNow) g_ntfArm=false;
   }
   // スケールアップ通知(+10%目安: 累計出金10%+出金1回で規模加算, docs/154)
   if(InpNotifyStepPct>0){
      if(!g_ntfStep && gainPct>=InpNotifyStepPct){ g_ntfStep=true;
         Notify(StringFormat("STEP %+.2f%% 到達(出金でスケールアップ検討, docs/154)",gainPct)); FlushNotify(); }
      else if(g_ntfStep && gainPct<InpNotifyStepPct-1.0) g_ntfStep=false;
   }
   Comment(StringFormat("Chien_RecentFit_2026H2_INSTANT | gain %+.2f%% | HWM %+.2f%% | FNフロアまで%.2f%% | mult %.1f | %s",gainPct,
          (g_initBal>0?(g_hwm-g_initBal)/g_initBal*100.0:0.0),
          (g_initBal>0?(equity-fnFloor)/g_initBal*100.0:0.0),InpMult,
          (g_passLocked?"LOCKED":
           (g_halted?"HALTED":
            (g_expired?"EXPIRED(新規停止)":
             (g_trailArmed?"TRAIL_ARMED(新規停止)":
              (InpProfitLockEnable&&gainPct>=InpLockArmPct?"ARMED":
               (g_dayBlocked?"DAY_BLOCKED":
                (BalGuardActive()?"BAL_GUARD":"active")))))))));
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
   ManageV4Exit();

   bool blockNew = (InpProfitStopPct>0 && equity>=g_initBal*(1.0+InpProfitStopPct/100.0))
                   || g_dayBlocked || g_expired || g_trailArmed
                   || (InpProfitLockEnable && gainPct>=InpLockArmPct)
                   || BalGuardActive();
   if(blockNew) return;

   EntriesMon(utc);
   EntriesV4();
   EntriesHold();
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
   bool idxWin=IdxEntryWindow(utc);               // v1.10: 指数レッグは米国現物寄り(13:30/14:30 UTC)から60分の単発
   if(slot<0 && !idxWin) return;
   datetime hourBar=utc-(utc%3600); int nh=ArraySize(g_monHours);
   datetime dayBar=utc-(utc%86400);
   trade.SetExpertMagicNumber(g_mMon);
   for(int s=0;s<g_nMon;s++){
      if(g_atrH1[s]==INVALID_HANDLE) continue;
      string sym=g_monSym[s]; double pip=PipOf(sym);
      bool idx=IsIdx(sym);
      int key=0; datetime stamp=0; int shots=1; int hourTag=0;
      if(idx){ if(!idxWin) continue; key=s*nh+0; stamp=dayBar; shots=1; hourTag=u.hour; }
      else   { if(slot<0)  continue; key=s*nh+slot; stamp=hourBar; shots=nh; hourTag=g_monHours[slot]; }
      if(g_lastShotMon[key]==stamp) continue;
      if(JpHolidayMonday(utc,sym)){ g_lastShotMon[key]=stamp; if(InpVerboseLog) PrintFormat("[Mon SKIP] %s 祝日月曜(日本 docs/303 / 豪NZ docs/304)",sym); continue; }
      double atr=AtrAt(g_atrH1[s]); if(atr<=0) continue;
      double sd=InpCatastropheATR*atr; double sp=sd/pip;
      if(sp<InpMinStopPips){ sp=InpMinStopPips; sd=sp*pip; }
      double ask=SymbolInfoDouble(sym,SYMBOL_ASK), bid=SymbolInfoDouble(sym,SYMBOL_BID);
      if(ask<=0||bid<=0) continue;
      if(MonSkipDate(utc,idx)){ g_lastShotMon[key]=stamp;
         if(InpVerboseLog) PrintFormat("[Mon SKIP] %s h%d 指定スキップ日(InpMonSkipDates)",sym,hourTag); continue; }
      // v1.01修正: スプレッド超過・発注失敗ではショット枠を消費しない(同時間帯内で30秒毎に再試行)
      if(idx){ if(SpreadBps(sym)>InpIdxMaxSpreadBps) continue; }
      else if((ask-bid)/pip>SpreadCapFor(sym)) continue;
      double notional=g_initBal*g_monW[s]*InpMult/shots;   // 1ショット=重み×倍率÷ショット数(指数は単発)
      double lots=LotsForNotional(sym,notional); if(lots<InpMinLot){ g_lastShotMon[key]=stamp; continue; }
      int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      double sl=NormalizeDouble(ask-sd,dg);
      if(trade.Buy(lots,sym,0.0,sl,0.0,StringFormat("RFIMon_%s_h%d",sym,hourTag)))
         { g_lastShotMon[key]=stamp;
           if(InpVerboseLog) PrintFormat("[Mon ENTRY] LONG %s h%dUTC lots=%.2f notional=%.0f SL=%s%s",sym,hourTag,lots,notional,DoubleToString(sl,dg),(idx?" (指数・現物寄り単発)":""));
           if(InpNotifyEntries) Notify(StringFormat("IN Mon %s %.2f",sym,lots)); }
      else PrintFormat("[Mon RETRY] %s h%d 発注失敗ret=%d(同時間帯内で再試行)",sym,hourTag,(int)trade.ResultRetcode());
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
         ok=trade.Buy(lots,sym,0.0,sl,tp,"RFIv4_"+sym);
         if(ok){
            if(InpVerboseLog) PrintFormat("[v4 ENTRY] LONG %s lots=%.2f notional=%.0f",sym,lots,notional);
            if(InpNotifyEntries) Notify(StringFormat("IN v4 L %s %.2f",sym,lots)); } }
      else     { double e=SymbolInfoDouble(sym,SYMBOL_BID);
         double sl=NormalizeDouble(e+sd,dg), tp=NormalizeDouble(e-tpd,dg);
         ok=trade.Sell(lots,sym,0.0,sl,tp,"RFIv4_"+sym);
         if(ok){
            if(InpVerboseLog) PrintFormat("[v4 ENTRY] SHORT %s lots=%.2f notional=%.0f",sym,lots,notional);
            if(InpNotifyEntries) Notify(StringFormat("IN v4 S %s %.2f",sym,lots)); } }
      if(ok){ g_lastV4Bar[i]=db; g_v4Tries[i]=0; }
      else  V4Fail(i,db,StringFormat("発注失敗ret=%d",(int)trade.ResultRetcode()));
   }
}

//===== Hold (Instant版は既定OFF。ONにする前にdocs/176 §7.8.2を確認) =====
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
      if(trade.Buy(lots,sym,0.0,sl,0.0,"RFIHold_"+sym)){
         if(InpVerboseLog) PrintFormat("[Hold ENTRY] LONG %s lots=%.2f notional=%.0f SL=%.1f",sym,lots,notional,sl);
         if(InpNotifyEntries) Notify(StringFormat("IN Hold %s %.2f",sym,lots)); }
   }
}
//+------------------------------------------------------------------+
//| 残存リスク(誠実な記録・docs/175/176 §7.8.2):                      |
//|  ・本構成は直近12ヶ月窓で選び直近窓で校正=構造的に楽観。          |
//|    全期間参考では2018年型(−7.7%)にトレーリング−6%へ接触し得る=    |
//|    口座喪失シナリオ(掛金$599+将来収益)。4.0xでも消えない。        |
//|  ・トレーリングMLLはbalance-HWM基準(FN)、EAはequity-HWM追跡=      |
//|    保守側。ただしPD稼働期のHWMはInpHwmOverrideで手動引継ぎが必要。|
//|  ・数値(docs/176 §7.8.2)は4.8x系列×5/6+JP225除外の近似。         |
//|    recentfit_screen.pyのInstant構成(JP225なし・4.0x)再実行が正式値|
//|    =残タスク。                                                    |
//|  ・Mon GBPJPY/AUDJPYはFTMO PDのv7と同一日・同方向(別業者=可)。    |
//|    FN内ではチャレンジ側にA案/B案を並行配備するとInstant↔チャレンジ|
//|    接触が発生(docs/176 §7.8.2)。配備前に§7.6.1回答を確認。        |
//|  ・想定元本サイジング: 研究セル(価格変化率×重み)と直接パリティ。  |
//|  ・日次ガードはティック評価だが週末ギャップ/急変時のスリップは    |
//|    防げない(docs/169クラッシュ監査参照)。                         |
//+------------------------------------------------------------------+
