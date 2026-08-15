//+------------------------------------------------------------------+
//| ★FN100k 口座14074882 焼き込み版 — RecentFit NonFX2 (DOW対応)      |
//|  v1.02 (2026-08-15): 2系統のレビュー(vqtxyw / qxapaj)を統合し、    |
//|    両者の対立点を独立検証で裁定した版。これを配備する。            |
//|    統合レビュー: research/nonfx_config_merged_review.md            |
//|    裁定スクリプト: research/adjudicate_nonfx_sl.py (再現可能)      |
//|    入力: research/nonfx_config_verification.md (V: vqtxyw)         |
//|          research/nonfx_ea_review.md          (Q: qxapaj)         |
//|                                                                   |
//|  構成(5セル・Σw=1.000): US500火L 0.333 / HK50月L 0.225 /          |
//|    HK50木S 0.225 / JP225水L 0.152 / XAG火L 0.065                  |
//|    ※v1.00の XPTUSD火L(0.072)は除外。比例再正規化。                 |
//|                                                                   |
//|  校正(0.8×規則・窓外系列・SL込み・ギャップ実約定で再計算):         |
//|    窓外(選抜窓を除く約9年) maxDD-6.89% → 規則mult 0.92 → 0.90採用  |
//|    倍率後: 窓外maxDD-6.20%(フロア-8%に余裕) / 窓外年率+2.70% /     |
//|            選抜窓12M +12.9% / 窓外最悪日-1.29%                     |
//|                                                                   |
//|  ⚠2系統レビューの対立と裁定(詳細は統合レビュー §2):                |
//|   ・災害SL: V「接触率42-59%で研究と別物→5.0×ATR(D1)」              |
//|             Q「方法論誤り。36.8%でmaxDD半減→2.5×ATR(H1)据置」      |
//|     裁定=Q寄り。Vの判定は決済後(翌日日中)の安値まで数えた二重      |
//|     計上で、同一データでV法48.3%/Q法36.8%/正しい判定27.1%。        |
//|     ただしQの「ギャップも-sdで止まる」も楽観(窓外maxDD -4.65% と   |
//|     出るが、実約定で埋めると -6.71%)。SL水準はQを採り、倍率は      |
//|     悲観側で引き直す、が両者の正しい合成。                         |
//|   ・倍率: V=0.72 / Q=1.00 → 補正後の規則出力 0.92 に対し 0.90。     |
//|   ・XPT除外: V が正しい(§③)。Qはデータ品質を検査していない。      |
//|                                                                   |
//|  v1.00からの主な変更(すべて検証根拠つき):                          |
//|   ①XPTUSDレッグ除外 — t=1.66(最弱)/損益分岐スプレッド$0.70に対し   |
//|     実勢$1.5-3.0で恒常赤字/元データPL=Fの O=H=L=C 退化バーが       |
//|     全体66.7%・直近12M 66.1%(独立再測)で o2o を測れていない。      |
//|     除外により選抜窓は+16.6%→+14.4%と下がるが窓外年率は           |
//|     +3.04%→+3.00%とほぼ不変 = 落ちたのは見かけの成績だけ。         |
//|   ②mult 1.0 → 0.90 (補正後の窓外系列に0.8×規則を再適用=0.92)      |
//|   ③災害SL: 2.5×ATR(H1,24) → 0.5×ATR(D1,14) [水準は実質同じ]       |
//|     H1のATR24本と日次ATRの換算(÷5)は未検証の仮定であり、校正を     |
//|     行った単位(ATR_D1)で直接指定する形に改めた。値は等価。         |
//|     発動率は約31%で「災害用」ではなく戦略の一部。研究セル(SLなし)  |
//|     とのパリティは崩れるが、窓外maxDDを-9.04%→-6.89%に改善し、     |
//|     リスク調整後では広いSL(5×ATR_D1)より優れる(統合レビュー§2)。  |
//|   ④建玉時刻をレッグ毎に指定可能化(第5フィールド・'|'区切り)。      |
//|     研究セルは各銘柄の「寄り→翌寄り」。全レッグ共通の4/6/8/10UTC   |
//|     ではUS500の寄り13:30UTCと9.5hズレていた。窓を数時間ずらすと    |
//|     選抜窓成績は +20.8%→+8.8%(HK50月Lは+22.0%→-3.7%で符号反転)。  |
//|     各レッグを自分の寄り直後に合わせてパリティを回復する。         |
//|   ⑤スプレッド上限を bp(価格比)指定に変更。                        |
//|     旧 InpDowSpreadCaps は解決後シンボルとキーを照合するため、     |
//|     FN表記 SPX500 に "US500" が一致せず、最大重みレッグが既定      |
//|     3.0pip で判定されていた(digits次第で常時発注不能)。           |
//|     bp指定は桁数非依存。別名(解決前後の両方)で照合する。          |
//|   ⑥ロット粒度による無音のレッグ消滅を解消。                       |
//|     1ショットが最小ロットに届かない場合、そのレッグのショット数を  |
//|     自動的に減らして建玉サイズを確保する(従来は枠だけ消費して      |
//|     無警告で消えていた)。                                          |
//|   ⑦日次ガードを段階化: 新規停止-3% → 全決済-4% (旧は両方-4%)      |
//|   ⑧InpInitialBalance の既定を 100000 に(ヘッダー自身の推奨に整合) |
//|   ⑨スプレッド超過で見送った場合にログを出す(v1.02で追加)。        |
//|     従来は無言の continue で、レッグが建たない原因が追えなかった。 |
//|     同一銘柄1時間に1回まで。⑤の別名不一致はこれで即座に露見する。  |
//|                                                                   |
//|  ⚠XAGレッグの建玉時刻は「未確定」である(v1.02で判明):              |
//|    日足始値と完全一致する1時間足を2年分照合したところ、            |
//|    JP225=00:00UTC(486/486)・HK50=01:30UTC(489/489)・              |
//|    US500=13:30UTC(夏時間。冬は14:30) と確定できたのに対し、        |
//|    SI=F は一致33/503で特定の時刻に集まらない。つまり研究セルの     |
//|    「寄り」を時計時刻に写像できない。0|1|2|3 の4ショットは         |
//|    「正しい時刻」ではなく、タイミング不確実性を時間分散で          |
//|    平均化するための設定である。XAGは退化バー17%・最小ロット        |
//|    量子化も重なるため、実効的な信頼度は他4レッグより低い。         |
//|                                                                   |
//|  土俵(FN想定・要フェーズ確認): 日次-5%(日開始max(bal,eq))/静的-10%|
//|    ガード: フロア-8%(ティック)/日次equity-3%新規停止/             |
//|            balance系-4%全決済                                     |
//|    資金化(funded)想定=利益ロック既定無効。チャレンジ中なら:       |
//|      P1: Enable=true, 7.9/8.05/8.1  P2: 4.9/5.05/5.1(+BaselineReset)|
//|                                                                   |
//|  ⚠移行手順(置き換え): ①季節RG3のEA(Magic 940900)を全チャートから  |
//|    撤去・建玉クローズ確認 → ②本EA装着。RG3稼働中に起動しないこと  |
//|                                                                   |
//|  ⚠配備前の必須確認(デモ):                                         |
//|    ・5銘柄の契約サイズ/最小ロット/ステップ([INIT SIZE]ログで確認) |
//|    ・各レッグの建玉時刻でのスプレッド実測([INIT SPREAD]ログの      |
//|      損益分岐bpと突合。超えるレッグは期待値が負)                   |
//|    ・4本のショットが実際に約定するか(取引時間・昼休み)            |
//|    ・日次線がサーバー日と一致するか(FNダッシュボードと突合)       |
//|                                                                   |
//|  停止規則(docs/174継承): 期限2026-10-15超過で新規停止=再スクリー   |
//|   ニング必須。失格でトラック終了(正攻法口座のため再購入なし)。    |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.02"
#property strict
#property description "[RecentFit NonFX2 FN100k 14074882 v1.02] Merge of two reviews (vqtxyw/qxapaj) with independent adjudication."
#property description "5 legs: SPX500-Tue-L .333 / HK50-Mon-L .225 / HK50-Thu-S .225 / JP225-Wed-L .152 / XAG-Tue-L .065. XPTUSD dropped (66.7% degenerate bars)."
#property description "Per-leg entry hours (parity with each cash open). mult 0.90 (0.8x rule on out-of-window, SL-inclusive, gap-filled series)."
#property description "Stop 0.5*ATR(D1,14) ~= 2.5*ATR(H1,24); fires ~31% so it is part of the strategy, not a disaster stop."
#property description "Floor -8 (tick), daily -3 stop / -4 close (server day, max(bal,eq)). Lock off (funded). Expiry 2026-10-15 UTC."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

input bool   InpAcknowledgeBet  = true;   // 本トラック=直近過剰適合の明示ベット(docs/174)を承認

input group "=== 構成(DOW: 銘柄:重み:曜日(1-5orMon..Fri):方向(L/S)[:時刻UTC('|'区切り)]) ==="
// 時刻は各銘柄の「寄り」直後に置く(研究セル=寄り→翌寄りのため)。
//   US500  寄り13:30UTC → 14|15|16|17
//   HK50   寄り01:30UTC → 2|3|6|7   (04:00-05:00UTCは香港の昼休みのため回避)
//   JP225  寄り00:00UTC → 0|1|2|4   (02:30-03:30UTCは東京の昼休みのため回避)
//   XAGUSD 寄り時刻を特定できず(日足始値と一致する1時間足が33/503で散在)。
//          0|1|2|3 は「正しい時刻」ではなく時間分散による不確実性の平均化。
input string InpDowLegs  = "US500:0.333:Tue:L:14|15|16|17,HK50:0.225:Mon:L:2|3|6|7,HK50:0.225:Thu:S:2|3|6|7,JP225:0.152:Wed:L:0|1|2|4,XAGUSD:0.065:Tue:L:0|1|2|3";
input string InpV4Legs   = "";                          // v4: 本構成では不使用
input string InpHoldLegs = "";                          // Hold: 本構成では不使用
input double InpMult     = 0.90;   // リスク倍率(補正後の窓外系列に0.8x規則=0.92 → 0.90採用)

input group "=== 有効期限(直近特化=賞味期限つき。docs/174停止規則) ==="
input datetime InpExpiry = D'2026.10.15 23:59';  // 選抜2026-08-15の2ヶ月枠(UTC解釈)

input group "=== 口座/ガード(FN: 日次-5%/静的-10%想定) ==="
input double InpInitialBalance   = 100000.0; // 規約基準残高。0=自動(非推奨: 静的-10%とズレる)
input bool   InpBaselineReset    = false; // 新フェーズ開始時のみtrue=基準残高を取り直す
input double InpMaxLossLimitPct  = 10.0;  // 失格ライン%(FN=初期残高静的-10%。記録用・未使用)
input double InpAccountFloorDDPct= 8.0;   // 全停止ライン%(-10%枠の2%手前。ティック評価)
input double InpDailyStopPct     = 3.0;   // 日次equity−この%で当日新規停止(全決済-4%の1段手前)
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
input double InpNotifyDayWarnPct = 2.5;   // 日次−この%で警告(新規停止-3%の手前)

input group "=== DOW レッグ設定(曜日マルチショット・docs/09系パリティ) ==="
input string InpDowHoursUTC   = "4,6,8,10";  // レッグが時刻を指定しない場合のフォールバック
input int    InpDowHoldHours  = 24;
input int    InpAtrPeriodD1   = 14;     // 災害SL用 ATR(D1)期間
// SL距離=InpCatastropheATR×ATR(D1,14)。0.5 は旧 2.5×ATR(H1,24) と実質同水準。
// 発動率≒31%で「災害用」ではなく戦略の一部(校正もこの系列で行っている)。
// 参考: 1.0→発動7.7%/窓外maxDD-8.92%、2.0→0.8%/-8.98%、5.0→0.0%/-9.04%。
// 広げるほど窓外maxDDは悪化する(=SLは実際にDDを抑えている)。変更時は要再校正。
input double InpCatastropheATR= 0.5;    // 戦略SL=0.5×ATR(D1,14)
input double InpMinStopPips   = 10.0;
input double InpMaxSpreadBp   = 8.0;    // 既定スプレッド上限(bp=価格の1/10000)
// 各レッグの上限bp。窓外の損益分岐bpの約2倍=「異常スプレッド弾き」として設定。
// (損益分岐: US500 3.0bp / HK50 6.4-9.0bp / JP225 2.4bp / XAG 12.3bp)
input string InpDowSpreadCapsBp = "SPX500:6.0,US500:6.0,HK50:13.0,JP225:5.0,XAGUSD:24.0";

input group "=== v4 レッグ設定(日足k≥4合議・本構成では不使用) ==="
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

#define MAXLEG   8
#define MAXSHOT  8
string  g_dowSym[MAXLEG];  string g_dowReq[MAXLEG];       // 解決後 / 解決前(別名照合用)
double  g_dowW[MAXLEG];    int g_dowDay[MAXLEG]; int g_dowDir[MAXLEG]; int g_nDow=0;
int     g_dowHrs[MAXLEG][MAXSHOT];                        // v1.01: レッグ毎の建玉時刻
int     g_dowNH[MAXLEG];                                  // 指定された時刻の数
int     g_dowShots[MAXLEG];                               // 実際に使うショット数(ロット粒度で縮む)
string  g_v4Sym[MAXLEG];   double g_v4W[MAXLEG];   int g_nV4=0;
string  g_holdSym[MAXLEG]; double g_holdW[MAXLEG]; int g_nHold=0;
int     g_dowHoursDef[]; int g_atrDowD1[MAXLEG]; int g_atrD1[MAXLEG]; int g_rsiD1[MAXLEG];
datetime g_lastShotDow[MAXLEG*MAXSHOT];
datetime g_lastV4Bar[MAXLEG];
datetime g_lastHoldTry[MAXLEG];
datetime g_shotsDay=0;
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
string   g_shotWarned="";
datetime g_spLogged[MAXLEG];    // v1.02⑨: スプレッド超過ログの間引き(レッグ毎1時間に1回)

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

// DOWレッグ "SYM:w:曜日:方向[:時刻|時刻|...]" をパース(曜日=1-5 or Mon..Fri, 方向=L/S)
int ParseDowDay(string s)
{
   StringTrimLeft(s); StringTrimRight(s);
   string U=s; StringToUpper(U);
   if(U=="MON") return 1; if(U=="TUE") return 2; if(U=="WED") return 3;
   if(U=="THU") return 4; if(U=="FRI") return 5;
   int d=(int)StringToInteger(s);
   return (d>=1&&d<=5)? d : 0;
}
int SplitHours(string csv, ushort sep, int &arr[])
{
   string p[]; int k=StringSplit(csv,sep,p); int m=0; ArrayResize(arr,k>0?k:0);
   for(int i=0;i<k;i++){ string s=p[i]; StringTrimLeft(s); StringTrimRight(s);
      if(StringLen(s)==0) continue; int h=(int)StringToInteger(s);
      if(h>=0&&h<=23){ arr[m]=h; m++; } }
   ArrayResize(arr,m); return m;
}
int ParseDowLegs(string csv)
{
   string parts[]; int n=StringSplit(csv,',',parts); int k=0;
   for(int i=0;i<n && k<MAXLEG;i++){
      string kv[]; int nf=StringSplit(parts[i],':',kv);
      if(nf!=4 && nf!=5){
         if(StringLen(parts[i])>0) PrintFormat("⚠ DOW: '%s'は SYM:w:曜日:L/S[:時刻] 形式でない→スキップ",parts[i]);
         continue; }
      string s=kv[0]; StringTrimLeft(s); StringTrimRight(s);
      double w=StringToDouble(kv[1]);
      int day=ParseDowDay(kv[2]);
      string dir=kv[3]; StringTrimLeft(dir); StringTrimRight(dir); StringToUpper(dir);
      int sgn=(dir=="L"?+1:(dir=="S"?-1:0));
      if(StringLen(s)==0 || w<=0 || day==0 || sgn==0){
         PrintFormat("⚠ DOW: '%s'のパース失敗(曜日/方向/重み)→スキップ",parts[i]); continue; }
      // v1.01④: 第5フィールドがあればレッグ固有の建玉時刻。無ければ共通既定。
      int hrs[]; int nh=0;
      if(nf==5) nh=SplitHours(kv[4],'|',hrs);
      if(nh==0){ nh=ArraySize(g_dowHoursDef); ArrayResize(hrs,nh);
                 for(int h=0;h<nh;h++) hrs[h]=g_dowHoursDef[h]; }
      if(nh==0){ PrintFormat("⚠ DOW: '%s'の建玉時刻が空→スキップ",parts[i]); continue; }
      if(nh>MAXSHOT){ nh=MAXSHOT; PrintFormat("⚠ DOW: %s の時刻は最大%d個→先頭のみ使用",s,MAXSHOT); }
      string r=ResolveSymbol(s);
      if(r==""){ PrintFormat("⚠ DOW: 銘柄'%s'を解決できず→スキップ(重みは配分から欠落=サイズ縮小側)",s); continue; }
      if(r!=s) PrintFormat("[銘柄解決] DOW %s → %s",s,r);
      g_dowSym[k]=r; g_dowReq[k]=s; g_dowW[k]=w; g_dowDay[k]=day; g_dowDir[k]=sgn;
      g_dowNH[k]=nh; g_dowShots[k]=nh;
      for(int h=0;h<nh;h++) g_dowHrs[k][h]=hrs[h];
      k++;
   }
   return k;
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

datetime DayStart(datetime t){ MqlDateTime s; TimeToStruct(t,s); s.hour=0;s.min=0;s.sec=0; return StructToTime(s); }

//--- v1.01⑥: 1ショットが最小ロットに届かない場合、ショット数を減らして建玉を確保する。
//    (v1.00は枠だけ消費して無警告でレッグが消えていた)
void RefreshShots()
{
   datetime today=DayStart(TimeCurrent());
   if(g_shotsDay==today) return;
   bool allPriced=true;                                            // 全銘柄の気配が揃うまで確定させない
   for(int s=0;s<g_nDow;s++){
      double full=g_initBal*g_dowW[s]*InpMult;
      if(SymbolInfoDouble(g_dowSym[s],SYMBOL_ASK)<=0.0){ allPriced=false; continue; }
      int n=g_dowNH[s];
      while(n>1 && LotsForNotional(g_dowSym[s],full/n)<=0.0) n--;
      if(LotsForNotional(g_dowSym[s],full/n)<=0.0) n=0;
      if(n!=g_dowShots[s]){
         if(n==0)
            PrintFormat("⚠[SHOT %s] 想定元本 %.0f では最小ロットに届かない → このレッグは建てられない。"
                        "重みか倍率、あるいは銘柄の契約サイズを確認のこと",g_dowSym[s],full);
         else
            PrintFormat("[SHOT %s] 1ショットが最小ロット未満 → ショット数 %d → %d に縮小(1ショット想定元本 %.0f)",
                        g_dowSym[s],g_dowShots[s],n,full/n);
         g_dowShots[s]=n;
      }
   }
   if(allPriced) g_shotsDay=today;   // 揃わなければ次のタイマーで再試行
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

//--- v1.01⑤: スプレッド上限を bp(価格比)で指定。桁数(digits/point)に依存しない。
//    キーは解決前・解決後の両方の銘柄名と照合する(FN表記 SPX500 対策)。
double SpreadCapBpFor(int s)
{
   if(StringLen(InpDowSpreadCapsBp)==0) return InpMaxSpreadBp;
   string A=g_dowSym[s]; StringToUpper(A);
   string B=g_dowReq[s]; StringToUpper(B);
   string parts[]; int n=StringSplit(InpDowSpreadCapsBp,',',parts);
   for(int i=0;i<n;i++){
      string kv[]; if(StringSplit(parts[i],':',kv)!=2) continue;
      string k=kv[0]; StringTrimLeft(k); StringTrimRight(k); StringToUpper(k);
      if(StringLen(k)==0) continue;
      if(StringFind(A,k)>=0 || StringFind(B,k)>=0) return StringToDouble(kv[1]); }
   return InpMaxSpreadBp;
}

//==================================================================
int OnInit()
{
   if(!InpAcknowledgeBet){ Print("[STOP] 本EAは直近過剰適合の明示ベット(docs/174)。InpAcknowledgeBet=trueで承認。"); return INIT_FAILED; }
   SplitHours(InpDowHoursUTC,',',g_dowHoursDef);        // レッグ側で時刻未指定の場合のフォールバック
   g_nDow =ParseDowLegs(InpDowLegs);
   g_nV4  =ParseLegs(InpV4Legs,  g_v4Sym,  g_v4W,  "v4");
   g_nHold=(InpHoldEnable? ParseLegs(InpHoldLegs,g_holdSym,g_holdW,"Hold") : 0);
   if(g_nDow==0 && g_nV4==0 && g_nHold==0){ Print("レッグが1つも解決できず"); return INIT_FAILED; }
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

   // v1.02③: SLは日足ATRベース。校正を行った単位(ATR_D1)で直接指定する。
   for(int i=0;i<g_nDow;i++) g_atrDowD1[i]=iATR(g_dowSym[i],PERIOD_D1,InpAtrPeriodD1);
   for(int i=0;i<g_nV4;i++){
      g_atrD1[i]=iATR(g_v4Sym[i],PERIOD_D1,InpV4_ATR);
      g_rsiD1[i]=iRSI(g_v4Sym[i],PERIOD_D1,InpV4_RSI,PRICE_CLOSE); }
   ArrayInitialize(g_lastShotDow,0); ArrayInitialize(g_lastV4Bar,0); ArrayInitialize(g_lastHoldTry,0);
   trade.SetDeviationInPoints(InpSlippagePoints);
   RestoreOrResetDay();
   RefreshShots();

   double wsum=0; for(int i=0;i<g_nDow;i++) wsum+=g_dowW[i];
   for(int i=0;i<g_nV4;i++) wsum+=g_v4W[i];
   for(int i=0;i<g_nHold;i++) wsum+=g_holdW[i];
   PrintFormat("[INIT RF-NonFX2 v1.02] initBal=%.0f mult=%.2f Σw=%.3f (グロス想定≈%.2fx) floor=-%.1f%% daily=-%.1f/-%.1f%% lock=%s expiry=%s Magic=%I64d/%I64d/%I64d",
      g_initBal,InpMult,wsum,wsum*InpMult,InpAccountFloorDDPct,InpDailyStopPct,InpBalGuardPct,
      (InpProfitLockEnable?StringFormat("%.2f/%.2f",InpLockArmPct,InpLockClosePct):"off"),
      TimeToString(InpExpiry,TIME_DATE),g_mDow,g_mV4,g_mHold);

   // v1.01: 配備前チェックをログ一発で出す(契約仕様・スプレッド・ロット)
   for(int i=0;i<g_nDow;i++){
      string sym=g_dowSym[i];
      string hs=""; for(int h=0;h<g_dowNH[i];h++) hs+=(h?"|":"")+IntegerToString(g_dowHrs[i][h]);
      double ask=SymbolInfoDouble(sym,SYMBOL_ASK), bid=SymbolInfoDouble(sym,SYMBOL_BID);
      double mid=(ask+bid)*0.5;
      double spbp=(mid>0? (ask-bid)/mid*10000.0 : -1.0);
      double full=g_initBal*g_dowW[i]*InpMult;
      int ns=(g_dowShots[i]>0? g_dowShots[i]:1);
      PrintFormat("[DOW leg %d] %s (要求'%s') w=%.3f day=%d dir=%s 時刻=%sUTC ショット=%d",
                  i,sym,g_dowReq[i],g_dowW[i],g_dowDay[i],(g_dowDir[i]>0?"L":"S"),hs,g_dowShots[i]);
      PrintFormat("   [INIT SIZE] 1ショット想定元本=%.0f → lots=%.2f (最小%.2f/step%.2f/契約%.0f)",
                  full/ns, LotsForNotional(sym,full/ns),
                  SymbolInfoDouble(sym,SYMBOL_VOLUME_MIN), SymbolInfoDouble(sym,SYMBOL_VOLUME_STEP),
                  SymbolInfoDouble(sym,SYMBOL_TRADE_CONTRACT_SIZE));
      PrintFormat("   [INIT SPREAD] 現在=%.2fbp / 上限=%.2fbp (digits=%d point=%g pip=%g)",
                  spbp, SpreadCapBpFor(i), (int)SymbolInfoInteger(sym,SYMBOL_DIGITS),
                  SymbolInfoDouble(sym,SYMBOL_POINT), PipOf(sym));
   }
   Print("[NOTE] 直近特化トラック(docs/174)。窓外期待値は年率+2.70%(mult0.90・コスト未計上)。");
   Print("[NOTE] 窓外tは US500 0.34 / JP225 0.26 と最大重み2本がほぼ無相関。重みは逆ボラ由来で"
         "エッジの持続性を反映していない — 期待値の主張は HK50木S と XAG に依存している。");
   Print("[NOTE] ⚠季節RG3(Magic940900)の停止・建玉クローズを確認してから稼働のこと(置き換え運用)。");
   Print("[NOTE] ⚠[INIT SPREAD]の実測値が損益分岐(US500 3.0bp/HK50 6.4-9.0bp/JP225 2.4bp/XAG 12.3bp)を"
         "超えるレッグは期待値が負。デモで各建玉時刻の実測を取ること。");
   EventSetTimer(30);
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){
   EventKillTimer();
   for(int i=0;i<g_nDow;i++) if(g_atrDowD1[i]!=INVALID_HANDLE) IndicatorRelease(g_atrDowD1[i]);
   for(int i=0;i<g_nV4;i++){ if(g_atrD1[i]!=INVALID_HANDLE) IndicatorRelease(g_atrD1[i]);
      if(g_rsiD1[i]!=INVALID_HANDLE) IndicatorRelease(g_rsiD1[i]); }
}

void ResetDay(datetime t){ g_curDay=DayStart(t); g_dayStartEq=AccountInfoDouble(ACCOUNT_EQUITY); g_dayBlocked=false;
   g_dayStartBal=AccountInfoDouble(ACCOUNT_BALANCE);
   if(g_gvName!=""){ GlobalVariableSet(g_gvName+"_dk",(double)(long)g_curDay);   // v1.02: 日次基準を永続化
      GlobalVariableSet(g_gvName+"_db",g_dayStartBal);
      GlobalVariableSet(g_gvName+"_de",g_dayStartEq); }
   if(g_gvName!="" && g_initBal>0) GlobalVariableSet(g_gvName,g_initBal); }
// v1.02: 日次基準の復元(同日中の再起動で日次ガード基準が現在残高に
// 再アンカーされ、実質の日次許容損失が広がるのを防ぐ)。
// v1.00(④): FN=サーバー日アンカー(TimeCurrent)。FNダッシュボード
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
   if(!g_expired && utc>=InpExpiry){
      g_expired=true;
      Print("[EXPIRY] 有効期限到達 → 新規停止。再スクリーニングし構成を更新すること(docs/174)。");
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
   Comment(StringFormat("FN14074882_RF_NonFX2 v1.02 | gain %+.2f%% | mult %.2f | %s",gainPct,InpMult,
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
   RefreshShots();                                    // v1.01⑥: 日毎にショット数を見直す
   datetime hourBar=utc-(utc%3600);
   trade.SetExpertMagicNumber(g_mDow);
   for(int s=0;s<g_nDow;s++){
      if(g_dowDay[s]!=u.day_of_week) continue;         // レッグ毎の曜日判定
      int ns=g_dowShots[s]; if(ns<=0) continue;        // ロット粒度で建てられないレッグ
      if(g_atrDowD1[s]==INVALID_HANDLE) continue;
      int slot=-1;                                     // v1.01④: レッグ毎の建玉時刻
      for(int h=0;h<ns;h++) if(u.hour==g_dowHrs[s][h]){ slot=h; break; }
      if(slot<0) continue;
      int key=s*MAXSHOT+slot;
      if(g_lastShotDow[key]==hourBar) continue;
      string sym=g_dowSym[s]; double pip=PipOf(sym);
      double atr=AtrAt(g_atrDowD1[s]); if(atr<=0) continue;
      double sd=InpCatastropheATR*atr; double sp=sd/pip;   // v1.02③: SL=0.5×ATR(D1,14)
      if(sp<InpMinStopPips){ sp=InpMinStopPips; sd=sp*pip; }
      double ask=SymbolInfoDouble(sym,SYMBOL_ASK), bid=SymbolInfoDouble(sym,SYMBOL_BID);
      if(ask<=0||bid<=0) continue;
      // v1.01継承: スプレッド超過・発注失敗ではショット枠を消費しない(同時間帯内で30秒毎に再試行)
      double mid=(ask+bid)*0.5;
      double spbp=(mid>0? (ask-bid)/mid*10000.0 : 1e9);
      if(spbp>SpreadCapBpFor(s)){
         // v1.02⑨: 無言で見送らない。別名不一致・実勢スプレッド過大をここで検知する。
         if(g_spLogged[s]!=hourBar){ g_spLogged[s]=hourBar;
            PrintFormat("⚠[DOW SPREAD] %s(要求名%s) %.2fbp > 上限%.2fbp → 見送り h%dUTC",
               sym,g_dowReq[s],spbp,SpreadCapBpFor(s),u.hour); }
         continue; }
      double notional=g_initBal*g_dowW[s]*InpMult/ns;   // 1ショット=重み×倍率÷ショット数
      double lots=LotsForNotional(sym,notional);
      if(lots<InpMinLot){                               // v1.01⑥: 無音で消さず一度だけ警告
         if(StringFind(g_shotWarned,sym)<0){ g_shotWarned+=sym+";";
            PrintFormat("⚠[DOW SKIP] %s 想定元本%.0fが最小ロット未満 → このショットは見送り",sym,notional); }
         g_lastShotDow[key]=hourBar; continue; }
      int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      bool ok=false;
      if(g_dowDir[s]>0){
         double sl=NormalizeDouble(ask-sd,dg);
         ok=trade.Buy(lots,sym,0.0,sl,0.0,StringFormat("RFDow_%s_d%dh%d",sym,g_dowDay[s],g_dowHrs[s][slot]));
      }else{
         double sl=NormalizeDouble(bid+sd,dg);
         ok=trade.Sell(lots,sym,0.0,sl,0.0,StringFormat("RFDow_%s_d%dh%d",sym,g_dowDay[s],g_dowHrs[s][slot]));
      }
      if(ok){ g_lastShotDow[key]=hourBar;
           if(InpVerboseLog) PrintFormat("[DOW ENTRY] %s %s day%d h%dUTC lots=%.2f notional=%.0f spread=%.2fbp SL距離=%.2f%%",
              (g_dowDir[s]>0?"LONG":"SHORT"),sym,g_dowDay[s],g_dowHrs[s][slot],lots,notional,spbp,sd/mid*100.0);
           if(InpNotifyEntries) Notify(StringFormat("IN DOW %s %s %.2f",(g_dowDir[s]>0?"L":"S"),sym,lots)); }
      else PrintFormat("[DOW RETRY] %s day%d h%d 発注失敗ret=%d(同時間帯内で再試行)",sym,g_dowDay[s],g_dowHrs[s][slot],(int)trade.ResultRetcode());
   }
}

//===== v4 (日足k≥4合議・想定元本ベース・本構成では不使用) =====
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
      if(lots<InpMinLot) continue;
      int dg=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      double sl=NormalizeDouble(ask*(1.0-InpHoldCatSLPct/100.0),dg);
      if(trade.Buy(lots,sym,0.0,sl,0.0,"RFHold_"+sym)){
         if(InpVerboseLog) PrintFormat("[Hold ENTRY] LONG %s lots=%.2f notional=%.0f SL=%.1f",sym,lots,notional,sl);
         if(InpNotifyEntries) Notify(StringFormat("IN Hold %s %.2f",sym,lots)); }
   }
}
//+------------------------------------------------------------------+
//| 残存リスク(誠実な記録・v1.02時点):                                 |
//|  ・選抜は490セルからの直近12ヶ月窓=構造的に楽観(docs/165/174)。   |
//|    多重検定(DOW族140検定)を通すと補正後に残るのは HK50月L のみ。   |
//|    窓外(選抜窓を除く約9年)の実力は年率+2.70%(mult0.90・コスト前)。 |
//|    エッジの大半は「選抜した1年が続くこと」に賭けている。           |
//|  ・【v1.02追記】窓外のレッグ別tは US500 0.34 / JP225 0.26 /        |
//|    HK50月L 1.03 / HK50木S 2.08 / XAG 3.09。重み最大の2本(合計     |
//|    w=0.485)が窓外でほぼ無相関である一方、窓外寄与の主力は         |
//|    HK50木S と XAG。逆ボラ重みは「低ボラ」を選んだのであって       |
//|    「持続するエッジ」を選んでいない。重み配分と根拠の強さが       |
//|    逆向きである点は、この構成の最大の構造的弱点。                 |
//|  ・コストが薄利を食い切り得る。窓外の損益分岐スプレッドは          |
//|    US500 3.0bp / HK50 6.4-9.0bp / JP225 2.4bp / XAG 12.3bp。      |
//|    [INIT SPREAD]の実測がこれを超えるレッグは期待値が負。           |
//|    o2oは毎回1泊するためオーバーナイト金利も年0.6-0.8%相当かかる。  |
//|  ・建玉時刻は各銘柄の寄り直後に合わせたが、CFDの取引時間・         |
//|    ファンディング・配当調整は研究に未計上。デモ実測必須。          |
//|  ・エッジは時刻に強く依存する(窓を数時間ずらすと選抜窓成績は       |
//|    +20.8%→+8.8%)。時刻設定を安易に変えないこと。                  |
//|  ・相関フィルタは曜日をまたぐDOWセル同士には効いていない           |
//|    (欠損0埋めにより構造的にρ≈0)。「分散」の主張は弱い。実質は     |
//|    ネットロング≈0.44(×mult)の指数ロングブック。                   |
//|  ・SLは発動率約31%=「災害用」ではなく戦略の一部。研究セル         |
//|    (SLなし)とのパリティはこの点で崩れており、選抜時のtスタットや   |
//|    合成DDをそのまま適用できない。倍率はSL込みの系列で引き直した。  |
//|  ・SLは窓ギャップを跳び越える。日中で止まらずギャップで抜けた分は  |
//|    翌寄りの実約定になる。この効果を織り込むと窓外maxDDは          |
//|    -4.65%(楽観モデル)ではなく -6.89% である。フロア-8%までの      |
//|    余裕はmult0.90で約1.8pt しかない。                             |
//|  ・週末エクスポージャはゼロ(金曜に建てるレッグが無く、木S建玉も    |
//|    金曜午前に決済される)。効くのは日次の窓ギャップ。               |
//|  ・日次アンカー=サーバー日(TimeCurrent)。FNダッシュボードの       |
//|    日次線とデモで突合してから本番稼働のこと。                     |
//|  ・置き換え運用: 季節RG3の停止を確認してから起動(ヘッダー⚠参照)。 |
//+------------------------------------------------------------------+
