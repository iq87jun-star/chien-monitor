//+------------------------------------------------------------------+
//| ★FN100k 口座14074882 焼き込み版 — RecentFit NonFX2 (DOW対応)      |
//|  v1.01 (2026-08-15): v1.00の設定検証で判明した執行側の乖離を是正   |
//|  選抜: research/nonfx_screen.py rev5 (クラウド再実行で再現確認済)  |
//|                                                                   |
//|  構成(Σw=0.999・rev5=FN取扱銘柄整合): DOW US500火L 0.309 /         |
//|    HK50月L 0.209 / HK50木S 0.209 / JP225水L 0.140 /               |
//|    XPT火L 0.072 / 銀火L 0.060 (v4なし)                            |
//|                                                                   |
//|  ■v1.00からの変更(research/nonfx_ea_review.md に検証根拠)         |
//|   ①レッグ別の建て時刻(CSV第5フィールド)。研究セルはo2o=各銘柄の    |
//|     現物寄り基準であり、v1.00の一律4,6,8,10UTCは以下だけずれていた:|
//|       US500 寄り13:30UTC → v1.00平均7:00 = 6.5h早い               |
//|       HK50  寄り01:30UTC → v1.00平均7:00 = 5.5h遅い               |
//|       JP225 寄り00:00UTC → v1.00平均7:00 = 7.0h遅い               |
//|     ※寄り時刻はYahoo日足と1時間足の完全一致照合で確定(不一致0-1日)|
//|     ずれの実測影響: 合成12M +20.7%(研究窓) → +8.6%(1セッション後  |
//|     送り) → -1.0%(丸1日ずれ)。HK50月Lは +22.0% → -5.2% と反転。   |
//|   ②InpCatastropheATR=2.5 と InpMult=1.0 は v1.00 のまま据え置き。 |
//|     検証初回は「2.5は発動率35-59%でエッジを半減させる」と判定した |
//|     が、これは建玉中の逆行に翌日の日中安値まで含めた誤りだった    |
//|     (建玉は翌日"寄り"で決済されるため逆行は当日日中のみ)。        |
//|     正しく再計算した結果(Σw=1.0・mult=1.0・研究窓パリティ前提):   |
//|       catATR  発動率   12M     全期間   maxDD   規則mult(×0.8)    |
//|         2.5   36.8%  +17.3%   +61.6%   -4.75%      1.32          |
//|         5.0   13.0%  +19.3%   +58.1%   -7.45%      0.84          |
//|        10.0    1.2%  +20.0%   +48.6%   -9.16%      0.68          |
//|        なし     0%   +20.8%   +47.0%   -9.32%      0.68          |
//|     2.5は12Mを17%削るが maxDDを半減させ全期間リターンはむしろ    |
//|     改善する(o2oの左裾を切るため)。この土俵で最良の作動点。      |
//|   ③同様に「mult1.0はフロア-8%を突破」も誤りだった。-9.32%は SL   |
//|     なし系列の値で、nonfx_screen.pyの校正がSLを織り込んでいない   |
//|     ことに由来する。実際の稼働系列(catATR2.5)のmaxDDは-4.75%で、  |
//|     規則(最悪日≥-4%かつDD≥-8%の最大倍率×0.8)を適用すると1.32。   |
//|     mult1.0は規則上限の内側=据え置きが妥当(引き上げは正式再校正  |
//|     後に。手で上げないこと)。                                     |
//|   ④InpInitialBalance 0 → 100000。0=自動は初回アタッチ時の残高を   |
//|     GVに凍結するため、残高<100000で装着するとフロアがFNの静的     |
//|     -10%線(90000)より下に来る(例: 97000装着→フロア89240)。        |
//|   ⑤SpreadCapFor を別名解決後の銘柄でも引けるよう双方向照合に。    |
//|     v1.00はキー"US500"に対しResolveSymbolが"SPX500"を返すため      |
//|     表を素通りし、FX用のInpMaxSpreadPips=3.0が最大レッグ(w0.309)  |
//|     に適用されていた(digits=2なら上限0.3指数pt=全弾き・ログなし)。|
//|   ⑥サイズ事前診断と見送りログ。v1.00は lots<MinLot を無言で       |
//|     スキップしていた。銀は1lot=5000oz×$65=$325k のため、          |
//|     4分割では mult 0.68/1.0 いずれでも0.01lot未満=レッグ消失。    |
//|     →小型レッグのショット数を削減(XPT 2本/銀 1本)して発注可能に。 |
//|                                                                   |
//|  校正(0.8×規則移植・コスト未計上の近似):                          |
//|    SLなし系列(nonfx_screen.pyの校正対象): 悲観0.68x / 12M窓2.92x  |
//|    実稼働系列(catATR2.5込み・全期間窓): 規則上限1.32x             |
//|    既定1.0x: 全期間 最悪日-0.97% / maxDD-4.75% / 12M+17.3%        |
//|      → フロア-8%まで3.25pt・失格線-10%まで5.25ptの余裕           |
//|    正攻法資金化口座のため、規則上限1.32xへの引き上げも正式再校正  |
//|    (p8p06z系・SLとコストを織り込んだMC)の後に限る。               |
//|                                                                   |
//|  土俵(FN想定・要フェーズ確認): 日次-5%(日開始max(bal,eq))/静的-10%|
//|    ガード: フロア-8%(ティック)/日次equity-4%停止+balance系-4%全決済|
//|    資金化(funded)想定=利益ロック既定無効。チャレンジ中なら:       |
//|      P1: Enable=true, 7.9/8.05/8.1  P2: 4.9/5.05/5.1(+BaselineReset)|
//|                                                                   |
//|  ⚠移行手順(置き換え): ①季節RG3のEA(Magic 940900)を全チャートから  |
//|    撤去・建玉クローズ確認 → ②本EA装着。RG3稼働中に起動しないこと  |
//|    (JP225/XAGUSD等が同一口座内で積み上がるため)。                 |
//|  ⚠装着チャートは24時間気配のある銘柄に(OnTickのフロア/BalGuard    |
//|    ティック評価が止まらないように。OnTimer 30秒でも代替評価あり)。|
//|                                                                   |
//|  停止規則(docs/174継承): 期限2026-10-15超過で新規停止=再スクリー   |
//|   ニング必須。失格でトラック終了(正攻法口座のため再購入なし)。    |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.01"
#property strict
#property description "[RecentFit NonFX2 FN100k 14074882 v1.01] DOW US500-Tue-L(14-17z)/HK50-Mon-L(2-3z)/HK50-Thu-S(2-3z)/JP225-Wed-L(0-3z)/XPT-Tue-L(4-5z)/XAG-Tue-L(4z). Per-leg entry hours matched to each cash open. mult 1.0 (rule cap 1.32). Cat SL 2.5xATR(H1). Floor -8 (tick), daily -4 stop / -4 close (server day, max(bal,eq)). Lock off (funded). Expiry 2026-10-15 UTC."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

input bool   InpAcknowledgeBet  = true;   // 本トラック=直近過剰適合の明示ベット(docs/174)を承認

input group "=== 構成(DOW: 銘柄:重み:曜日(1-5orMon..Fri):方向(L/S)[:建て時刻UTC ';'区切り]) ==="
// v1.01: 第5フィールド=そのレッグ専用の建て時刻(省略時はInpDowHoursUTCを使用)。
//   時刻は各銘柄の現物寄り(研究o2oの起点)直後に配置:
//     US500 13:30UTC → 14,15,16,17 / HK50 01:30UTC → 2,3(HK前場01:30-04:00内)
//     JP225 00:00UTC → 0,1,2,3     / XPT・XAG 日足バー04:00UTCスタンプ → 4,5 / 4
//   ショット数は最小ロットを満たす範囲で決定(XPT=2本・銀=1本。⑥参照)。
input string InpDowLegs  = "US500:0.309:Tue:L:14;15;16;17,HK50:0.209:Mon:L:2;3,HK50:0.209:Thu:S:2;3,JP225:0.140:Wed:L:0;1;2;3,XPTUSD:0.072:Tue:L:4;5,XAGUSD:0.060:Tue:L:4";
input string InpV4Legs   = "";                          // v4: rev5では不使用(銅がFN非取扱で脱落)
input string InpHoldLegs = "";                          // Hold: 本構成では不使用
input double InpMult     = 1.0;    // リスク倍率(実稼働系列の規則上限1.32。SLなし系列基準なら悲観0.68/12M窓2.92)

input group "=== 有効期限(直近特化=賞味期限つき。docs/174停止規則) ==="
input datetime InpExpiry = D'2026.10.15 23:59';  // 選抜2026-08-15の2ヶ月枠(UTC解釈)

input group "=== 口座/ガード(FN: 日次-5%/静的-10%想定) ==="
input double InpInitialBalance   = 100000.0; // v1.01: 規約基準残高を明示(0=自動は静的-10%とズレる)
input bool   InpBaselineReset    = false; // 新フェーズ開始時のみtrue=基準残高を取り直す
input double InpMaxLossLimitPct  = 10.0;  // 失格ライン%(FN=初期残高静的-10%。記録用・コード未使用)
input double InpAccountFloorDDPct= 8.0;   // 全停止ライン%(-10%枠の2%手前。ティック評価)
input double InpDailyStopPct     = 4.0;   // 日次equity−この%で当日新規停止(規約−5%手前)
input double InpDayProfitCapPct  = 0.0;   // FNに日次利益上限規則なし=既定無効
input double InpDayProfitCloseAllPct = 0.0; // 同上(コードは温存)

input group "=== 日次決済ガード(max(日開始bal,eq)アンカー・サーバー日) ==="
input double InpBalGuardPct      = 4.0;   // equity≤日開始max(bal,eq)−この%で全決済+当日停止(0=無効)
input int    InpBalGuardMaxMonth = 2;     // 月内発動上限(超過は月末まで新規停止)

input group "=== 利益ロック(funded想定=既定無効。P1: 7.9/8.05/8.1 P2: 4.9/5.05/5.1) ==="
input bool   InpProfitLockEnable = false;
input double InpLockArmPct    = 7.9;   // equity+この%で新規停止
input double InpLockClosePct  = 8.05;  // equity+この%で全決済し恒久ロック(PASS_LOCK)
input double InpProfitStopPct = 8.1;   // +この%で新規停止(保険)

input group "=== プッシュ通知(docs/112) ==="
input bool   InpNotifyEnable     = true;
input bool   InpNotifyEntries    = true;
input double InpNotifyDayWarnPct = 3.0;   // 日次−この%で警告

input group "=== DOW レッグ設定(曜日マルチショット・docs/09系パリティ) ==="
input string InpDowHoursUTC   = "4,6,8,10";  // レッグ側で時刻未指定のときの既定(v1.01構成では全レッグ指定済=未使用)
input int    InpDowHoldHours  = 24;
input int    InpAtrPeriodH1   = 24;
input double InpCatastropheATR= 2.5;    // 災害SL=2.5×ATR(H1,24)。発動率36.8%だがmaxDDを半減させる(②の表)
input double InpMinStopPips   = 10.0;
input double InpMaxSpreadPips = 3.0;    // キャップ表に無い銘柄の既定(FX尺度。指数は必ず表に載せること)
// v1.01: 指定名と解決後名の双方を載せる(US500→SPX500 等の別名解決に対応)。
//   単位は pip=point×10。digitsがブローカー依存のため、[SPEC]起動ログの実測pip値で最終化のこと。
input string InpDowSpreadCaps = "SPX500:4.0,US500:4.0,HK50:25.0,JP225:30.0,XPTUSD:45.0,XAGUSD:6.0";

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

input group "=== Hold レッグ設定(本構成では不使用) ==="
input bool   InpHoldEnable    = false;
input double InpHoldCatSLPct  = 15.0;
input double InpHoldMaxSpreadPts = 3000.0;

input group "=== 防御フィルタ(docs/148) ==="
input bool   InpHolidayFilterEnable = true; // 12/20〜1/3は新規停止

input group "=== 共通 ==="
input double InpMinLot = 0.01;
input double InpMaxLot = 50.0;
input long   InpMagicBase = 944000;  // DOW=+1/v4=+2/Hold=+3 (⚠RG3=940900と別系)
input int    InpSlippagePoints = 30;
input bool   InpVerboseLog = true;

//==================================================================
CTrade        trade;
CPositionInfo posinfo;

#define MAXLEG 8
#define MAXSHOT 8
string  g_dowSym[MAXLEG];  double g_dowW[MAXLEG];  int g_dowDay[MAXLEG]; int g_dowDir[MAXLEG]; int g_nDow=0;
string  g_dowReq[MAXLEG];                       // v1.01: 解決前の指定名(スプレッドキャップ照合用)
int     g_dowLegH[MAXLEG][MAXSHOT];             // v1.01: レッグ別の建て時刻(UTC)
int     g_dowLegNH[MAXLEG];                     // v1.01: レッグ別のショット数(0=未指定→既定を流用)
string  g_v4Sym[MAXLEG];   double g_v4W[MAXLEG];   int g_nV4=0;
string  g_holdSym[MAXLEG]; double g_holdW[MAXLEG]; int g_nHold=0;
int     g_dowHours[]; int g_atrH1[MAXLEG]; int g_atrD1[MAXLEG]; int g_rsiD1[MAXLEG];
datetime g_lastShotDow[MAXLEG*MAXSHOT];
datetime g_lastSpreadWarn[MAXLEG];              // v1.01: スプレッド見送りログのレート制限
datetime g_lastV4Bar[MAXLEG];
datetime g_lastHoldTry[MAXLEG];
double   g_initBal=0.0;
double   g_dayStartEq=0.0, g_dayStartBal=0.0;
datetime g_curDay=0, g_balBlockDay=0;
int      g_balFireMonth=-1, g_balFires=0;
bool     g_balMonthHalt=false;
bool     g_halted=false, g_dayBlocked=false, g_passLocked=false, g_expired=false;
datetime g_profitCloseDay=0;
string   g_ntfBuf=""; bool g_ntfArm=false; datetime g_ntfWarnDay=0;
string   g_gvName="";
long     g_mDow=0, g_mV4=0, g_mHold=0;
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
   if(StringFind(U,"HK50")>=0 || StringFind(U,"HSI")>=0 || StringFind(U,"HONGKONG")>=0){
      bases[nb++]="HK50"; bases[nb++]="HSI"; bases[nb++]="HSI50"; bases[nb++]="HK50Cash"; bases[nb++]="HKG33"; bases[nb++]="HongKong50"; }
   if(StringFind(U,"US500")>=0 || StringFind(U,"SPX")>=0 || StringFind(U,"SP500")>=0){
      bases[nb++]="US500"; bases[nb++]="SPX500"; bases[nb++]="SP500"; bases[nb++]="US500Cash"; bases[nb++]="USA500"; }
   if(StringFind(U,"XAG")>=0 || StringFind(U,"SILVER")>=0){
      bases[nb++]="XAGUSD"; bases[nb++]="SILVER"; bases[nb++]="Silver"; }
   if(StringFind(U,"XPT")>=0 || StringFind(U,"PLATINUM")>=0){
      bases[nb++]="XPTUSD"; bases[nb++]="PLATINUM"; bases[nb++]="Platinum"; }
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

// v1.00: DOWレッグ "SYM:w:曜日:方向" をパース(曜日=1-5 or Mon..Fri, 方向=L/S)
int ParseDowDay(string s)
{
   StringTrimLeft(s); StringTrimRight(s);
   string U=s; StringToUpper(U);
   if(U=="MON") return 1; if(U=="TUE") return 2; if(U=="WED") return 3;
   if(U=="THU") return 4; if(U=="FRI") return 5;
   int d=(int)StringToInteger(s);
   return (d>=1&&d<=5)? d : 0;
}
// v1.01: レッグ別建て時刻 "14;15;16;17" をパースし g_dowLegH[idx] に格納
int ParseLegHours(string csv, int idx)
{
   string p[]; int k=StringSplit(csv,';',p); int m=0;
   for(int i=0;i<k && m<MAXSHOT;i++){
      string s=p[i]; StringTrimLeft(s); StringTrimRight(s);
      if(StringLen(s)==0) continue;
      int h=(int)StringToInteger(s);
      if(h>=0 && h<=23){ g_dowLegH[idx][m]=h; m++; }
      else PrintFormat("⚠ DOW: 建て時刻'%s'は0-23の範囲外→無視",s);
   }
   return m;
}
int ParseDowLegs(string csv)
{
   string parts[]; int n=StringSplit(csv,',',parts); int k=0;
   for(int i=0;i<n && k<MAXLEG;i++){
      string kv[]; int nf=StringSplit(parts[i],':',kv);
      if(nf!=4 && nf!=5){
         if(StringLen(parts[i])>0) PrintFormat("⚠ DOW: '%s'は SYM:w:曜日:L/S[:時刻;時刻] 形式でない→スキップ",parts[i]);
         continue; }
      string s=kv[0]; StringTrimLeft(s); StringTrimRight(s);
      double w=StringToDouble(kv[1]);
      int day=ParseDowDay(kv[2]);
      string dir=kv[3]; StringTrimLeft(dir); StringTrimRight(dir); StringToUpper(dir);
      int sgn=(dir=="L"?+1:(dir=="S"?-1:0));
      if(StringLen(s)==0 || w<=0 || day==0 || sgn==0){
         PrintFormat("⚠ DOW: '%s'のパース失敗(曜日/方向/重み)→スキップ",parts[i]); continue; }
      string r=ResolveSymbol(s);
      if(r==""){ PrintFormat("⚠ DOW: 銘柄'%s'を解決できず→スキップ(重みは配分から欠落=サイズ縮小側)",s); continue; }
      if(r!=s) PrintFormat("[銘柄解決] DOW %s → %s",s,r);
      g_dowSym[k]=r; g_dowReq[k]=s; g_dowW[k]=w; g_dowDay[k]=day; g_dowDir[k]=sgn;
      g_dowLegNH[k]=(nf==5 ? ParseLegHours(kv[4],k) : 0);   // 0=既定(InpDowHoursUTC)を後で流用
      k++;
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
   // 非FX(指数/金属等)対応: pip=point×10(#14166201焼き込みと同方式)。
   // 5桁/3桁FXでは従来値(0.0001/0.01)と一致。
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
// v1.01: 1ロットあたりの想定元本(診断用。気配なしなら0)
double NotionalPerLot(string sym)
{
   double mpu=MoneyPerUnit(sym); if(mpu<=0) return 0.0;
   double px=SymbolInfoDouble(sym,SYMBOL_ASK); if(px<=0) return 0.0;
   return mpu*px;
}

int CountPos(string sym, long magic){
   int n=0;
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Symbol()==sym && posinfo.Magic()==magic) n++; }
   return n;
}
bool IsMine(long m){ return (m==g_mDow||m==g_mV4||m==g_mHold); }
void CloseAllMine(string why){
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(IsMine(posinfo.Magic())) trade.PositionClose(tk); }
   if(InpVerboseLog) PrintFormat("[CLOSE ALL %s]",why);
}

void Notify(string s){ if(!InpNotifyEnable) return; if(g_ntfBuf!="") g_ntfBuf+=" | "; g_ntfBuf+=s; }
void FlushNotify(){
   if(g_ntfBuf=="") return;
   string msg="[RF-NX2] "+g_ntfBuf;
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
//--- v1.01(⑤): 指定名(別名解決前)と解決後名の双方で照合。
//    v1.00は解決後名のみで引いていたため "US500"→"SPX500" のとき表を素通りし、
//    FX尺度のInpMaxSpreadPipsが最大レッグに適用されていた。
double SpreadCapFor(string reqName, string sym)
{
   if(StringLen(InpDowSpreadCaps)==0) return InpMaxSpreadPips;
   string S=sym;     StringToUpper(S);
   string R=reqName; StringToUpper(R);
   string parts[]; int n=StringSplit(InpDowSpreadCaps,',',parts);
   for(int i=0;i<n;i++){
      string kv[]; if(StringSplit(parts[i],':',kv)!=2) continue;
      string k=kv[0]; StringTrimLeft(k); StringTrimRight(k); StringToUpper(k);
      if(StringLen(k)==0) continue;
      if(StringFind(S,k)>=0 || StringFind(k,S)>=0 ||
         StringFind(R,k)>=0 || StringFind(k,R)>=0) return StringToDouble(kv[1]); }
   return InpMaxSpreadPips;
}
bool HasSpreadCap(string reqName, string sym)
{
   if(StringLen(InpDowSpreadCaps)==0) return false;
   string S=sym;     StringToUpper(S);
   string R=reqName; StringToUpper(R);
   string parts[]; int n=StringSplit(InpDowSpreadCaps,',',parts);
   for(int i=0;i<n;i++){
      string kv[]; if(StringSplit(parts[i],':',kv)!=2) continue;
      string k=kv[0]; StringTrimLeft(k); StringTrimRight(k); StringToUpper(k);
      if(StringLen(k)==0) continue;
      if(StringFind(S,k)>=0 || StringFind(k,S)>=0 ||
         StringFind(R,k)>=0 || StringFind(k,R)>=0) return true; }
   return false;
}

//--- v1.01(⑥): 起動時のサイズ/スプレッド事前診断。
//    最小ロット未満でレッグが消える・キャップが尺度違いで全弾きになる、を装着時に可視化する。
void PreflightDow()
{
   Print("[PREFLIGHT] レッグ別の建て時刻・想定元本・ロット・スプレッド尺度の事前診断");
   for(int i=0;i<g_nDow;i++){
      string sym=g_dowSym[i]; int nh=g_dowLegNH[i];
      string hrs=""; for(int h=0;h<nh;h++){ if(h>0) hrs+=","; hrs+=IntegerToString(g_dowLegH[i][h]); }
      double notional=g_initBal*g_dowW[i]*InpMult/MathMax(nh,1);
      double perLot=NotionalPerLot(sym);
      double pip=PipOf(sym);
      double ask=SymbolInfoDouble(sym,SYMBOL_ASK), bid=SymbolInfoDouble(sym,SYMBOL_BID);
      int    dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      double cap=SpreadCapFor(g_dowReq[i],sym);
      PrintFormat("[SPEC %s] digits=%d point=%.6g pip=%.6g 建て%sUTC×%d本 曜日%d %s",
                  sym,dg,SymbolInfoDouble(sym,SYMBOL_POINT),pip,hrs,nh,g_dowDay[i],(g_dowDir[i]>0?"L":"S"));
      if(perLot<=0.0 || ask<=0.0 || bid<=0.0){
         PrintFormat("  └ ⚠気配なし(市場休止中?) → サイズ/スプレッド診断は取引時間中に再確認のこと"); continue; }
      double lots=LotsForNotional(sym,notional);
      double got =lots*perLot;
      double spr =(ask-bid)/pip;
      PrintFormat("  └ 1ショット想定元本 $%.0f / 1lot $%.0f → %.2f lot (実効 $%.0f = 目標の%.0f%%)",
                  notional,perLot,lots,got,(notional>0? got/notional*100.0:0.0));
      if(lots<InpMinLot)
         PrintFormat("  └ ★致命: 最小ロット未満 → このレッグは1本も発注されない(重み%.3fが完全に欠落)。"
                     "ショット数を減らすかInpMultを上げること",g_dowW[i]);
      else if(got<notional*0.75 || got>notional*1.25)
         PrintFormat("  └ ▲サイズ丸め誤差が大きい(目標の%.0f%%)。研究の重み配分と乖離する",got/notional*100.0);
      if(!HasSpreadCap(g_dowReq[i],sym))
         PrintFormat("  └ ★InpDowSpreadCapsに該当キーなし → FX尺度の既定%.1f pipが適用される。表に追加すること",InpMaxSpreadPips);
      PrintFormat("  └ 現在スプレッド %.2f pip / 上限 %.2f pip %s",spr,cap,
                  (spr>cap? "★超過=この状態では発注されない":(cap>spr*20.0? "▲上限が緩すぎ(実質無効)":"OK")));
   }
}

//==================================================================
int OnInit()
{
   if(!InpAcknowledgeBet){ Print("[STOP] 本EAは直近過剰適合の明示ベット(docs/174)。InpAcknowledgeBet=trueで承認。"); return INIT_FAILED; }
   int nh=SplitHours(InpDowHoursUTC,g_dowHours);
   if(nh>MAXSHOT){ ArrayResize(g_dowHours,MAXSHOT); nh=MAXSHOT;
      Print("⚠ DOW既定時刻は最大8個まで→先頭8個のみ使用"); }
   for(int i=0;i<MAXLEG;i++){ g_dowLegNH[i]=0; for(int h=0;h<MAXSHOT;h++) g_dowLegH[i][h]=-1; }
   g_nDow =ParseDowLegs(InpDowLegs);
   g_nV4  =ParseLegs(InpV4Legs,  g_v4Sym,  g_v4W,  "v4");
   g_nHold=(InpHoldEnable? ParseLegs(InpHoldLegs,g_holdSym,g_holdW,"Hold") : 0);
   // v1.01: 時刻未指定のレッグには既定(InpDowHoursUTC)を流用
   for(int i=0;i<g_nDow;i++){
      if(g_dowLegNH[i]>0) continue;
      for(int h=0;h<nh;h++) g_dowLegH[i][h]=g_dowHours[h];
      g_dowLegNH[i]=nh;
   }
   if(g_nDow==0 && g_nV4==0 && g_nHold==0){ Print("レッグが1つも解決できず"); return INIT_FAILED; }
   for(int i=0;i<g_nDow;i++)
      if(g_dowLegNH[i]==0){
         PrintFormat("DOW leg %d (%s): 建て時刻が0個(レッグ指定もInpDowHoursUTCも空)",i,g_dowSym[i]);
         return INIT_FAILED; }
   g_mDow=InpMagicBase+1; g_mV4=InpMagicBase+2; g_mHold=InpMagicBase+3;

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
      PrintFormat("[基準残高] 新規記録: %.2f ⚠規約基準(通常100000)と一致するか確認のこと",g_initBal);
   }
   // v1.01(④): 自動基準がFNの静的-10%線より低いフロアを生む場合に警告
   if(InpInitialBalance<=0.0){
      double floorLv=g_initBal*(1.0-InpAccountFloorDDPct/100.0);
      PrintFormat("⚠[基準残高] InpInitialBalance=0(自動)。フロア=%.2f。口座の規約基準残高×(1-%.1f%%)より"
                  "低い場合、失格線より下でしか停止せず守れない。規約基準残高の明示指定を強く推奨",
                  floorLv,InpMaxLossLimitPct);
   }

   for(int i=0;i<g_nDow;i++) g_atrH1[i]=iATR(g_dowSym[i],PERIOD_H1,InpAtrPeriodH1);
   for(int i=0;i<g_nV4;i++){
      g_atrD1[i]=iATR(g_v4Sym[i],PERIOD_D1,InpV4_ATR);
      g_rsiD1[i]=iRSI(g_v4Sym[i],PERIOD_D1,InpV4_RSI,PRICE_CLOSE); }
   ArrayInitialize(g_lastShotDow,0); ArrayInitialize(g_lastV4Bar,0); ArrayInitialize(g_lastHoldTry,0);
   ArrayInitialize(g_lastSpreadWarn,0);
   trade.SetDeviationInPoints(InpSlippagePoints);
   RestoreOrResetDay();
   double wsum=0; for(int i=0;i<g_nDow;i++) wsum+=g_dowW[i];
   for(int i=0;i<g_nV4;i++) wsum+=g_v4W[i];
   for(int i=0;i<g_nHold;i++) wsum+=g_holdW[i];
   PrintFormat("[INIT RF-NonFX2 v1.01] initBal=%.0f mult=%.2f Σw=%.3f (グロス想定≈%.2fx) catSL=%.1f×ATR(H1) floor=-%.1f%% daily=-%.1f/-%.1f%% lock=%s expiry=%s Magic=%I64d/%I64d/%I64d",
      g_initBal,InpMult,wsum,wsum*InpMult,InpCatastropheATR,InpAccountFloorDDPct,InpDailyStopPct,InpBalGuardPct,
      (InpProfitLockEnable?StringFormat("%.2f/%.2f",InpLockArmPct,InpLockClosePct):"off"),
      TimeToString(InpExpiry,TIME_DATE),g_mDow,g_mV4,g_mHold);
   for(int i=0;i<g_nDow;i++){
      string hrs=""; for(int h=0;h<g_dowLegNH[i];h++){ if(h>0) hrs+=","; hrs+=IntegerToString(g_dowLegH[i][h]); }
      PrintFormat("[DOW leg %d] %s w=%.3f day=%d dir=%s hours=%sUTC(%d本)",
                  i,g_dowSym[i],g_dowW[i],g_dowDay[i],(g_dowDir[i]>0?"L":"S"),hrs,g_dowLegNH[i]);
   }
   PreflightDow();
   Print("[NOTE] 直近特化トラック(docs/174)。⚠季節RG3(Magic940900)の停止・建玉クローズを確認してから稼働のこと(置き換え運用)。");
   EventSetTimer(30);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){
   EventKillTimer();
   for(int i=0;i<g_nDow;i++) if(g_atrH1[i]!=INVALID_HANDLE) IndicatorRelease(g_atrH1[i]);
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
// 再アンカーされ、実質の日次許容損失が広がるのを防ぐ)。
// v1.00(本焼き込み④): FN=サーバー日アンカー(TimeCurrent)。FNダッシュボード
// の日次線とデモで突合すること。
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
                  (g_balBlockDay==today?" BAL_GUARD継続":""),(g_dayBlocked?" DAY_BLOCK継続":""));
   }else ResetDay(TimeCurrent());
}
double AtrAt(int handle){ double a[1]; if(handle==INVALID_HANDLE||CopyBuffer(handle,0,1,1,a)<1) return 0.0; return a[0]; }

// v1.03: 当日新規停止(_ds)の永続化を共通化
void PersistDayBlock(){ if(g_gvName!="") GlobalVariableSet(g_gvName+"_ds",(double)(long)g_curDay); }

//--- v1.03(⑦)継承: 静的フロアのティック評価
double FloorGuardLevel(){ return g_initBal*(1.0-InpAccountFloorDDPct/100.0); }
void FloorCheck()
{
   if(g_halted || g_initBal<=0.0) return;
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq>FloorGuardLevel()) return;
   g_halted=true; CloseAllMine("EQUITY_FLOOR");
   PrintFormat("[HALT] equity %.2f <= guard %.2f",eq,FloorGuardLevel());
   Notify(StringFormat("FLOOR %.2f 全決済・恒久停止",eq)); FlushNotify();
}

//--- 日次決済ガード(ティック評価・翌日再開・月内上限)
//    v1.03(④)継承: アンカー=max(日開始bal, 日開始eq)(常に保守側)。
//    v1.00(④): 日回りはFNサーバー日(TimeCurrent)。
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
   double anchor=MathMax(g_dayStartBal,g_dayStartEq);
   if(BalGuardActive() || anchor<=0.0) return;
   double beq=AccountInfoDouble(ACCOUNT_EQUITY);
   if(beq>anchor*(1.0-InpBalGuardPct/100.0)) return;
   g_balBlockDay=g_curDay; g_balFires++;
   if(g_balFires>InpBalGuardMaxMonth) g_balMonthHalt=true;
   if(g_gvName!=""){ GlobalVariableSet(g_gvName+"_bg",(double)((long)bmk*100+g_balFires));
                     GlobalVariableSet(g_gvName+"_bd",(double)(long)g_balBlockDay); }
   CloseAllMine("BAL_GUARD");
   PrintFormat("[BAL GUARD] eq %.2f <= 日開始max(bal,eq) %.2f -%.1f%% → 全決済・当日停止(月内%d回目%s)",
               beq,anchor,InpBalGuardPct,g_balFires,(g_balMonthHalt?"・月末まで停止":""));
   Notify(StringFormat("BAL_GUARD -%.1f%% 全決済・当日停止(%d/月)",InpBalGuardPct,g_balFires));
   FlushNotify();
}
void OnTick(){ FloorCheck(); BalGuardCheck(); }

//==================================================================
void OnTimer()
{
   FlushNotify();
   datetime now=TimeCurrent(); datetime utc=TimeGMT();
   if(DayStart(now)!=g_curDay) ResetDay(now);     // FN: サーバー日アンカー
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);

   // 有効期限(docs/174停止規則): 期限後は新規停止。建玉は通常管理(時間切れ決済のみ)。
   // InpExpiryはUTC解釈(v1.03⑧継承)。
   if(!g_expired && utc>=InpExpiry){
      g_expired=true;
      Print("[EXPIRY] 有効期限到達 → 新規停止。nonfx_screen.py(正式にはrecentfit_nonfx_screen.py系)を再実行し構成を更新すること(docs/174)。");
      Notify("EXPIRY 新規停止(再スクリーニング必須)"); FlushNotify();
   }

   // 静的フロア(初期残高基準・ティック評価と併用)
   FloorCheck();
   if(g_halted){ CloseAllMine("HALTED"); return; }

   // 利益ロック(funded想定=既定無効。チャレンジ中のみ有効化)
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
   Comment(StringFormat("FN14074882_RF_NonFX2 v1.01 | gain %+.2f%% | mult %.2f | %s",gainPct,InpMult,
          (g_passLocked?"PASS_LOCK":
           (g_halted?"HALTED":
            (g_expired?"EXPIRED(新規停止)":
             (InpProfitLockEnable&&gainPct>=InpLockArmPct?"ARMED":
              (g_dayBlocked?"DAY_BLOCKED":
               (BalGuardActive()?"BAL_GUARD":"active"))))))));
   if(g_passLocked){ CloseAllMine("PROFIT_LOCK"); return; }

   BalGuardCheck();

   double dpnl=equity-g_dayStartEq;
   if(InpDailyStopPct>0){
      if(InpNotifyDayWarnPct>0 && g_ntfWarnDay!=g_curDay
         && dpnl<=-g_initBal*InpNotifyDayWarnPct/100.0){
         g_ntfWarnDay=g_curDay;
         Notify(StringFormat("日次-%.1f%%警告 eq=%.0f",InpNotifyDayWarnPct,equity)); FlushNotify(); }
      if(dpnl<=-g_initBal*InpDailyStopPct/100.0 && !g_dayBlocked){ g_dayBlocked=true;
         PersistDayBlock();
         PrintFormat("[DAILY STOP] %.2f",dpnl);
         Notify(StringFormat("DAILY_STOP -%.1f%% 当日新規停止",InpDailyStopPct)); FlushNotify(); }
   }
   // 日次利益cap系(FNに該当規則なし=既定無効。コードはv1.03統合版から温存)
   if(InpDayProfitCapPct>0 && dpnl>=g_initBal*InpDayProfitCapPct/100.0 && !g_dayBlocked){ g_dayBlocked=true;
      PersistDayBlock();
      PrintFormat("[DAY PROFIT CAP] %+.2f → 当日新規停止",dpnl);
      Notify("DAY_PROFIT_CAP 当日新規停止"); FlushNotify(); }
   if(InpDayProfitCloseAllPct>0 && g_profitCloseDay!=g_curDay
      && dpnl>=g_initBal*InpDayProfitCloseAllPct/100.0){
      g_profitCloseDay=g_curDay;
      if(!g_dayBlocked){ g_dayBlocked=true; PersistDayBlock(); }
      CloseAllMine("DAY_PROFIT_CLOSE");
      PrintFormat("[DAY PROFIT CLOSE] %+.2f >= +%.1f%% → 全決済・当日新規停止",dpnl,InpDayProfitCloseAllPct);
      Notify(StringFormat("DAY_PROFIT_CLOSE %+.1f%% 全決済",InpDayProfitCloseAllPct)); FlushNotify();
   }

   ManageDowExit();
   ManageV4Exit();

   bool blockNew = (InpProfitStopPct>0 && InpProfitLockEnable && equity>=g_initBal*(1.0+InpProfitStopPct/100.0))
                   || g_dayBlocked || g_expired
                   || (InpProfitLockEnable && gainPct>=InpLockArmPct)
                   || BalGuardActive();
   if(blockNew) return;

   EntriesDow(utc);
   EntriesV4();
   EntriesHold();
}

//===== DOW (曜日o2oマルチショット・方向指定・想定元本=重み×倍率×基準残高) =====
void ManageDowExit()
{
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()!=g_mDow) continue;
      int held=(int)(TimeCurrent()-(datetime)posinfo.Time());
      if(held>=InpDowHoldHours*3600){ if(trade.PositionClose(tk)&&InpVerboseLog)
         PrintFormat("[DOW TIME EXIT] %s",posinfo.Symbol()); }
   }
}
void EntriesDow(datetime utc)
{
   if(g_nDow==0) return;
   MqlDateTime u; TimeToStruct(utc,u);
   if(u.day_of_week<1 || u.day_of_week>5) return;
   if(HolidayBlocked(utc)) return;
   datetime hourBar=utc-(utc%3600);
   trade.SetExpertMagicNumber(g_mDow);
   for(int s=0;s<g_nDow;s++){
      if(g_dowDay[s]!=u.day_of_week) continue;    // レッグ毎の曜日判定
      if(g_atrH1[s]==INVALID_HANDLE) continue;
      // v1.01: 建て時刻はレッグ毎(研究o2oの起点=各銘柄の現物寄りに合わせる)
      int nh=g_dowLegNH[s]; int slot=-1;
      for(int h=0;h<nh;h++) if(u.hour==g_dowLegH[s][h]){ slot=h; break; }
      if(slot<0) continue;
      int key=s*MAXSHOT+slot;                     // v1.01: ストライドはnhでなく固定MAXSHOT
      if(g_lastShotDow[key]==hourBar) continue;
      string sym=g_dowSym[s]; double pip=PipOf(sym);
      double atr=AtrAt(g_atrH1[s]); if(atr<=0) continue;
      double sd=InpCatastropheATR*atr; double sp=sd/pip;
      if(sp<InpMinStopPips){ sp=InpMinStopPips; sd=sp*pip; }
      double ask=SymbolInfoDouble(sym,SYMBOL_ASK), bid=SymbolInfoDouble(sym,SYMBOL_BID);
      if(ask<=0||bid<=0) continue;
      // v1.01継承: スプレッド超過・発注失敗ではショット枠を消費しない(同時間帯内で30秒毎に再試行)
      double spr=(ask-bid)/pip, cap=SpreadCapFor(g_dowReq[s],sym);
      if(spr>cap){
         if(g_lastSpreadWarn[s]!=hourBar){        // v1.01(⑤): 無言スキップをやめ1時間に1回記録
            g_lastSpreadWarn[s]=hourBar;
            PrintFormat("[DOW SPREAD] %s スプレッド%.2f pip > 上限%.2f pip → 見送り(同時間帯内で再試行)",sym,spr,cap); }
         continue; }
      double notional=g_initBal*g_dowW[s]*InpMult/nh;   // 1ショット=重み×倍率÷そのレッグのショット数
      double lots=LotsForNotional(sym,notional);
      if(lots<InpMinLot){                          // v1.01(⑥): 無言スキップをやめ理由を記録
         g_lastShotDow[key]=hourBar;
         PrintFormat("⚠[DOW SIZE] %s 想定元本$%.0f が最小ロット未満 → 見送り(重み%.3f分が配分から欠落)",
                     sym,notional,g_dowW[s]);
         continue; }
      int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      bool ok=false;
      if(g_dowDir[s]>0){
         double sl=NormalizeDouble(ask-sd,dg);
         ok=trade.Buy(lots,sym,0.0,sl,0.0,StringFormat("RFDow_%s_d%dh%d",sym,g_dowDay[s],g_dowLegH[s][slot]));
      }else{
         double sl=NormalizeDouble(bid+sd,dg);
         ok=trade.Sell(lots,sym,0.0,sl,0.0,StringFormat("RFDow_%s_d%dh%d",sym,g_dowDay[s],g_dowLegH[s][slot]));
      }
      if(ok){ g_lastShotDow[key]=hourBar;
           if(InpVerboseLog) PrintFormat("[DOW ENTRY] %s %s day%d h%dUTC lots=%.2f notional=%.0f SL=%.1fpip",
              (g_dowDir[s]>0?"LONG":"SHORT"),sym,g_dowDay[s],g_dowLegH[s][slot],lots,notional,sp);
           if(InpNotifyEntries) Notify(StringFormat("IN DOW %s %s %.2f",(g_dowDir[s]>0?"L":"S"),sym,lots)); }
      else PrintFormat("[DOW RETRY] %s day%d h%d 発注失敗ret=%d(同時間帯内で再試行)",sym,g_dowDay[s],g_dowLegH[s][slot],(int)trade.ResultRetcode());
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
      // v1.01継承: バー消費は「成立/合議不成立の確定/既保有」時のみ。
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
      if(lots<InpMinLot){ g_lastV4Bar[i]=db; g_v4Tries[i]=0;
         PrintFormat("⚠[v4 SIZE] %s 想定元本$%.0f が最小ロット未満 → 見送り",sym,notional); continue; }
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

//===== Hold (連続LONG・災害SLのみ。本構成では不使用・コード温存) =====
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
      if(lots<InpMinLot){ PrintFormat("⚠[Hold SIZE] %s 想定元本$%.0f が最小ロット未満 → 見送り",sym,notional); continue; }
      int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      double sl=NormalizeDouble(ask*(1.0-InpHoldCatSLPct/100.0),dg);
      if(trade.Buy(lots,sym,0.0,sl,0.0,"RFHold_"+sym)){
         if(InpVerboseLog) PrintFormat("[Hold ENTRY] LONG %s lots=%.2f notional=%.0f SL=%.1f",sym,lots,notional,sl);
         if(InpNotifyEntries) Notify(StringFormat("IN Hold %s %.2f",sym,lots)); }
   }
}
//+------------------------------------------------------------------+
//| 残存リスク(誠実な記録):                                           |
//|  ・選抜は490セルからの直近12ヶ月窓=構造的に楽観(docs/165/174)。   |
//|    全期間の悲観バウンド(Σw=1.0・mult1.0・catATR2.5込み):          |
//|    最悪日-0.97% / maxDD-4.75% → フロア-8%の内側。ただしこの       |
//|    maxDD縮小は災害SLに依存しており、SLはギャップを跳び越え得る    |
//|    (SLなし系列のmaxDDは-9.32%=フロア突破水準)。窓ギャップが       |
//|    続く局面では-9%側の挙動になり得ると理解して運用すること。      |
//|  ・研究は現物指数/先物の寄り引け。CFDの取引時間・スプレッド・     |
//|    ファンディング・配当調整は未計上。v1.01で建て時刻を各銘柄の    |
//|    寄り(US500 13:30/HK50 01:30/JP225 00:00 UTC。Yahoo日足と       |
//|    1時間足の完全一致照合で確定)直後に合わせたが、寄り"価格"では   |
//|    なく寄り直後の成行である点、CFDと現物指数の乖離は残る。        |
//|  ・XPT/XAGは日足バーが04:00UTC(=00:00 NY)スタンプで、1時間足との  |
//|    完全一致が取れない(先物の集計規約が異なる)。この2レッグ       |
//|    (w計0.132)の執行パリティは他4本より不確実。                    |
//|  ・XPT/XAGは最小ロット制約が厳しい(銀1lot=5000oz×$65=$325k)。    |
//|    v1.00は4分割のため銀が0.01lot未満=1本も発注されなかった。      |
//|    v1.01はショット数を絞って発注可能にしたが(XPT2本/銀1本)、      |
//|    丸め後の実効サイズは mult1.0 で XPT≈97% / 銀≈54% になる       |
//|    (銀は0.01lot=$3.25kに対し目標$6k)。[PREFLIGHT]ログで実測し、  |
//|    銀の実効重みが0.06→0.032相当に下がる点を織り込むこと。        |
//|  ・日次アンカー=サーバー日(TimeCurrent)。FNダッシュボードの       |
//|    日次線とデモで突合してから本番稼働のこと。                     |
//|  ・InpDowSpreadCapsはpip=point×10単位でdigits依存。[SPEC]ログの   |
//|    実測pip値・現在スプレッドを見て最終化すること。                |
//|  ・火曜集中(US500+XPT+XAG=w0.441)。ただしv1.01では建て時刻が      |
//|    分離した(XPT/XAG 4-5UTC・US500 14-17UTC)ため同時建ては減る。   |
//|  ・週末・窓ギャップは指数・商品でFXより大(docs/169)。災害SLは     |
//|    ギャップを跳び越え得る。上のmaxDD-4.75%はSLが指定値で約定する  |
//|    前提の値で、ギャップ時の実約定はそれより不利になる。           |
//|  ・置き換え運用: 季節RG3の停止を確認してから起動(ヘッダー⚠参照)。 |
//+------------------------------------------------------------------+
