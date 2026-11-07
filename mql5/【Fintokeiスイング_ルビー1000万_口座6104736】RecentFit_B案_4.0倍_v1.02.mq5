//+------------------------------------------------------------------+
//| ★Fintokeiパール500万専用焼き込み版(docs/178・fintokei_4_0x.set反映) |
//|  Fintokei適合(docs/176 §7.5系): JP225 Hold除外(トレードグループ3%  |
//|  対策)・3レッグ再正規化(GBPJPY37.4/AUDJPY32.2/USDJPY30.4)・倍率4.0 |
//|  ステップ1: ロック7.9/8.05(目標8%)                                 |
//|  ステップ2移行時: InpLockArmPct=5.9 / InpLockClosePct=6.05 /       |
//|    InpProfitStopPct=6.1 / InpBaselineReset=true(1回だけ)★目標6%注意|
//|      Chien_RecentFit_2026H2_Prop — 直近特化トラック v1.0          |
//|            (docs/174 設計・事前登録 / docs/175 計測結果)           |
//|                                                                   |
//|  ★このEAは「正攻法」(10年検証・LOYO・docs/172の稼働体制)とは別の   |
//|    明示的なEVベット: 直近12/6ヶ月だけで伸びているセルを事前固定    |
//|    ルールで選抜した構成。耐久エッジの主張はしない。               |
//|    直近レジームが数ヶ月続けばチャレンジを高速通過できる、に張る。 |
//|                                                                   |
//|  構成(recentfit_screen.py 2026-07-30凍結・docs/175):              |
//|    Mon  GBPJPY 34.8% / AUDJPY 29.9%  (月曜o2o LONG・24h)          |
//|    v4   USDJPY 28.3%                 (日足k≥4合議・SL/TP付き)     |
//|    Hold JP225   7.0%                 (連続LONG・災害SLのみ)       |
//|    倍率: 標準4.8x / 速攻7.2x(.set) — 直近12ヶ月窓のガード逆算値   |
//|                                                                   |
//|  数字(docs/175・楽観/悲観の両バウンド併記が本トラックの規律):     |
//|    直近12ヶ月サンプル: 資金化到達99.9%・中央68日(標準4.8x)        |
//|    全期間サンプル:     資金化到達65.2%・失格24.8%(同)             |
//|    →真値はこの間のどこか。直近寄りに賭けるのが本トラックの本質。  |
//|                                                                   |
//|  停止規則(docs/174 事前登録・変更はdocsの追記で):                 |
//|    ・有効期限(既定2026-10-31)を過ぎたら新規停止=再スクリーニング  |
//|      必須(同じ固定ルールを再実行して構成を入れ替える)             |
//|    ・チャレンジ失格2回でトラック撤退(费用予算の上限)              |
//|  ⚠ 正攻法稼働口座とは別口座・できれば別業者で(重複取引規則)。     |
//|     GBPJPY月曜LONGはFTMO PD口座のv7と同一日・同方向になり得る。   |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.02"   // v1.02(2026-10-07・Q111 docs/327): VPS ログ送信(InpLogUrl・Apps Script)を追加。取引ロジックは v1.01 と同一   // ルビー版 v1.01(2026-10-05・Q93 docs/324): ロット計算の tick 値経路を口座通貨に換算し、損益経路を正とする。他は v1.00 と同一
//   // ルビー版 v1.00(2026-09-28): パール B案 v1.06 と同構成。Fintokei チャレンジプラン・スイング(swap-free)ルビー 1,000万(口座 6104736・2026-09-28 購入)用に基準残高固定・同時保有リスク 3% 警告の内側ガード(docs/318 §5・docs/276)
#property strict
#property description "[RecentFit 2026H2] Recency-bet track (docs/174/175). Mon GBPJPY+AUDJPY / v4 USDJPY / Hold JP225. mult 4.8 std / 7.2 fast. Balance guard -4 tick, floor -9, FN P1 lock 8.05. Expiry-enforced re-screen."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

//==================================================================
// Q111(docs/327・2026-10-07): VPS ログ送信。EA の Print/PrintFormat は ChienLog 経由(端末ログはそのまま)で
// 送信キューに積まれ、InpLogUrl(Google Apps Script の /exec)へ HTTPS POST される。送信失敗は取引に影響させない。
// 送る物: LOG(ログ行)・SNAP(毎時: 残高/有効証拠金/証拠金/建玉)・DEAL(約定: 理由 SL/TP/EXPERT 等)・INIT/DEINIT。
// 事前準備: ツール→オプション→エキスパート「WebRequest を許可する URL」に https://script.google.com と
//           https://script.googleusercontent.com を追加してから VPS へ移行(設定は移行時に写る)。InpLogUrl 空 = 送信しない。
//==================================================================
#define CHIEN_EA_VERSION "1.02"
#define CHIEN_LOG_MAXQ   200
input string InpLogUrl         = "";    // Q111 ログ送信先 URL(Apps Script /exec・空=送信しない)
input int    InpLogSnapshotMin = 60;    // Q111 スナップショット間隔(分)
input int    InpLogTimeoutMs   = 2000;  // Q111 WebRequest タイムアウト(ms)
string   g_clQ[];
int      g_clN=0, g_clFail=0;
datetime g_clLastSend=0, g_clLastSnap=0, g_clLastWarn=0;
ulong    g_clLastDealTk=0;
string   g_clTag="";

string ChienCsv(string s){ StringReplace(s,"\"","\"\""); StringReplace(s,"\r"," "); StringReplace(s,"\n"," "); return "\""+s+"\""; }
void ChienPush(string kind,string text){
   if(InpLogUrl=="") return;
   string line=IntegerToString((long)AccountInfoInteger(ACCOUNT_LOGIN))+","+TimeToString(TimeGMT(),TIME_DATE|TIME_SECONDS)+","+TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS)+","+kind+","+ChienCsv(g_clTag)+","+ChienCsv(text);
   if(g_clN>=CHIEN_LOG_MAXQ){ for(int i=1;i<g_clN;i++) g_clQ[i-1]=g_clQ[i]; g_clN--; }
   if(ArraySize(g_clQ)<g_clN+1) ArrayResize(g_clQ,g_clN+1,64);
   g_clQ[g_clN]=line; g_clN++;
}
void ChienLog(string s){ Print(s); ChienPush("LOG",StringSubstr(s,0,400)); }
void ChienLog(string a,string b){ ChienLog(a+b); }
bool ChienSend(string body){
   char data[]; char res[]; string rh;
   int n=StringToCharArray(body,data,0,WHOLE_ARRAY,CP_UTF8);
   if(n>0 && data[n-1]==0) ArrayResize(data,n-1);
   ResetLastError();
   int code=WebRequest("POST",InpLogUrl,"Content-Type: text/plain; charset=utf-8\r\n",InpLogTimeoutMs,data,res,rh);
   if(code==200 || code==201 || code==302) return true;
   int err=GetLastError();
   if(TimeCurrent()-g_clLastWarn>3600){ g_clLastWarn=TimeCurrent();
      if(err==4014) Print("[LOG SEND] WebRequest 不許可(err 4014): オプション→エキスパートの許可 URL に https://script.google.com と https://script.googleusercontent.com を追加して再移行");
      else PrintFormat("[LOG SEND] 失敗 code=%d err=%d(取引には影響しない)",code,err); }
   return false;
}
void ChienFlush(bool force){
   if(InpLogUrl=="" || g_clN==0) return;
   datetime now=TimeCurrent();
   if(!force && now-g_clLastSend<60 && g_clN<20) return;
   if(!force && g_clFail>=3 && now-g_clLastSend<600) return;
   string body=""; int k=0;
   for(;k<g_clN && k<100;k++) body+=g_clQ[k]+"\n";
   g_clLastSend=now;
   if(ChienSend(body)){ int rest=g_clN-k; for(int i=0;i<rest;i++) g_clQ[i]=g_clQ[i+k]; g_clN=rest; g_clFail=0; }
   else g_clFail++;
}
void ChienSnapshot(){
   if(InpLogUrl=="") return;
   datetime now=TimeCurrent();
   if(g_clLastSnap!=0 && now-g_clLastSnap<InpLogSnapshotMin*60) return;
   g_clLastSnap=now;
   string pos=""; int n=PositionsTotal();
   for(int i=0;i<n;i++){ ulong tk=PositionGetTicket(i); if(tk==0 || !PositionSelectByTicket(tk)) continue;
      pos+=StringFormat("%s|%s|%.2f|%.5f|%.2f|%I64d|%s;",PositionGetString(POSITION_SYMBOL),(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?"buy":"sell"),
           PositionGetDouble(POSITION_VOLUME),PositionGetDouble(POSITION_PRICE_OPEN),PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP),
           PositionGetInteger(POSITION_MAGIC),PositionGetString(POSITION_COMMENT)); }
   ChienPush("SNAP",StringFormat("balance=%.2f equity=%.2f margin=%.2f free=%.2f positions=%d %s",
      AccountInfoDouble(ACCOUNT_BALANCE),AccountInfoDouble(ACCOUNT_EQUITY),AccountInfoDouble(ACCOUNT_MARGIN),AccountInfoDouble(ACCOUNT_MARGIN_FREE),n,pos));
}
void ChienDeals(){
   if(InpLogUrl=="") return;
   datetime now=TimeCurrent();
   if(!HistorySelect(now-7*86400,now+3600)) return;
   int n=HistoryDealsTotal(); ulong mx=g_clLastDealTk;
   for(int i=0;i<n;i++){ ulong d=HistoryDealGetTicket(i); if(d==0) continue;
      if(g_clLastDealTk==0){ if(d>mx) mx=d; continue; }
      if(d<=g_clLastDealTk) continue;
      if(d>mx) mx=d;
      long type=HistoryDealGetInteger(d,DEAL_TYPE); if(type!=DEAL_TYPE_BUY && type!=DEAL_TYPE_SELL) continue;
      long entry=HistoryDealGetInteger(d,DEAL_ENTRY); long reason=HistoryDealGetInteger(d,DEAL_REASON);
      string rs=(reason==DEAL_REASON_SL?"SL":reason==DEAL_REASON_TP?"TP":reason==DEAL_REASON_SO?"STOPOUT":reason==DEAL_REASON_EXPERT?"EXPERT":
                 reason==DEAL_REASON_CLIENT?"CLIENT":reason==DEAL_REASON_MOBILE?"MOBILE":reason==DEAL_REASON_WEB?"WEB":"OTHER");
      string en=(entry==DEAL_ENTRY_IN?"IN":entry==DEAL_ENTRY_OUT?"OUT":entry==DEAL_ENTRY_INOUT?"INOUT":"OUTBY");
      ChienPush("DEAL",StringFormat("deal=%I64u pos=%I64d %s %s %s vol=%.2f price=%.5f profit=%.2f comm=%.2f swap=%.2f magic=%I64d reason=%s time=%s comment=%s",
         d,HistoryDealGetInteger(d,DEAL_POSITION_ID),en,HistoryDealGetString(d,DEAL_SYMBOL),(type==DEAL_TYPE_BUY?"buy":"sell"),
         HistoryDealGetDouble(d,DEAL_VOLUME),HistoryDealGetDouble(d,DEAL_PRICE),HistoryDealGetDouble(d,DEAL_PROFIT),HistoryDealGetDouble(d,DEAL_COMMISSION),
         HistoryDealGetDouble(d,DEAL_SWAP),HistoryDealGetInteger(d,DEAL_MAGIC),rs,TimeToString((datetime)HistoryDealGetInteger(d,DEAL_TIME),TIME_DATE|TIME_SECONDS),
         HistoryDealGetString(d,DEAL_COMMENT)));
   }
   if(g_clLastDealTk==0) g_clLastDealTk=(mx==0?1:mx); else g_clLastDealTk=mx;
}
void ChienLogTimer(){ if(InpLogUrl=="") return; ChienDeals(); ChienSnapshot(); ChienFlush(false); }
void ChienLogInit(){
   g_clTag=MQLInfoString(MQL_PROGRAM_NAME)+" v"+CHIEN_EA_VERSION;
   if(InpLogUrl==""){ Print("[LOG] InpLogUrl が空 → VPS ログ送信なし(Q111)"); return; }
   ChienDeals();
   ChienPush("INIT",StringFormat("server=%s currency=%s balance=%.2f equity=%.2f build=%d",AccountInfoString(ACCOUNT_SERVER),AccountInfoString(ACCOUNT_CURRENCY),
      AccountInfoDouble(ACCOUNT_BALANCE),AccountInfoDouble(ACCOUNT_EQUITY),(int)TerminalInfoInteger(TERMINAL_BUILD)));
   g_clLastSnap=0; ChienSnapshot(); ChienFlush(true);
   Print("[LOG] VPS ログ送信 有効(Q111) → ",InpLogUrl);
}
void ChienLogDeinit(){ if(InpLogUrl=="") return; ChienPush("DEINIT",StringFormat("reason=%d",UninitializeReason())); ChienFlush(true); }
//================================================================== Q111 ここまで


input bool   InpAcknowledgeBet  = true;   // 本トラック=直近過剰適合の明示ベット(docs/174)を承認

input group "=== 構成(銘柄:重み CSV。既定=2026-07-30スクリーニング凍結値) ==="
input string InpMonLegs  = "GBPJPY:0.374,AUDJPY:0.322"; // Mon: 月曜o2o LONG
input string InpV4Legs   = "USDJPY:0.304";              // v4: 日足k≥4合議
input string InpHoldLegs = "";                        // Hold: 連続LONG
input double InpMult     = 4.0;    // リスク倍率(標準4.8 / 速攻7.2=.set)

input group "=== 有効期限(直近特化=賞味期限つき。docs/174停止規則) ==="
input datetime InpExpiry = D'2026.10.31 23:59';  // 期限後は新規停止(再スクリーニングで更新)

input group "=== 口座/ガード ==="
input double InpInitialBalance   = 10000000.0; // ルビー 1,000万を固定(docs/241 §1d: 自動取得は誤基準の事故あり)
input bool   InpBaselineReset    = false; // 新フェーズ開始時のみtrue=基準残高を取り直す
input double InpMaxLossLimitPct  = 10.0;  // 失格ライン%(Fintokei スイング=静的10%)
input double InpAccountFloorDDPct= 9.0;   // 全停止ライン%(-10%枠の手前)
input double InpDailyStopPct     = 4.0;   // 日次equity−この%で当日新規停止(スイング規約 −5% 有効証拠金の手前)

input group "=== v1.44 balance基準日次ガード(docs/170/171) ==="
input double InpBalGuardPct      = 2.8;   // equity≤日開始balance−この%で全決済+当日停止(Fintokei 同時保有リスク 3% 警告の内側・docs/276)
input int    InpBalGuardMaxMonth = 2;     // 月内発動上限(超過は月末まで新規停止)

input group "=== 利益ロック(FN Stellar P1=+8%。P2は5.05/4.9に変更) ==="
input bool   InpProfitLockEnable = true;
input double InpLockArmPct    = 7.9;   // equity+この%で新規停止
input double InpLockClosePct  = 8.05;  // equity+この%で全決済し恒久ロック(PASS_LOCK)
input double InpProfitStopPct = 8.1;   // +この%で新規停止(保険)

input group "=== プッシュ通知(docs/112) ==="
input bool   InpNotifyEnable     = true;
input bool   InpNotifyEntries    = true;
input double InpNotifyDayWarnPct = 3.0;   // 日次−この%で警告

input group "=== Mon レッグ設定(月曜マルチショット・docs/09系パリティ) ==="
input string InpMonHoursUTC   = "4,6,8,10";
input int    InpMonHoldHours  = 24;
input int    InpAtrPeriodH1   = 24;
input double InpCatastropheATR= 3.0;    // 災害SL=3.0×ATR(H1)。2026-09-27 ユーザー決定 docs/313 §5 B 案(2.5 → 3.0: 発動 34→27%・5 年 +0.5pt・最悪日 −0.3pt)
input double InpMinStopPips   = 10.0;
input double InpMaxSpreadPips = 3.0;
input string InpMonSpreadCaps = "GBPJPY:2.9,AUDJPY:2.9"; // ペア別上限(edge20 §3)

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
input bool   InpHoldEnable    = false;   // false=Holdレッグ停止(手決済を維持したい時もfalseに)
input double InpHoldCatSLPct  = 15.0;   // 災害SL: 建値−この%(研究はSLなし・保険のみ)
input double InpHoldMaxSpreadPts = 3000.0;

input group "=== 防御フィルタ(docs/148) ==="
input bool   InpHolidayFilterEnable = true; // 12/20〜1/3は新規停止
input string InpJpHolidayMondays = "2026.10.12,2026.11.02,2026.11.23,2027.01.11,2027.02.22,2027.03.22,2027.05.03,2027.07.19,2027.09.20,2027.10.11,2027.11.22"; // 日本の祝日月曜 + 翌火曜が祝日の月曜(UTC 日付)。JPY を含む Mon を建てない(docs/303 Q53・docs/304 Q56)。2028 年分は要追記
input bool   InpJpHolidayJpyOnly = true;   // true=JPY を含む Mon レッグのみ見送り / false=Mon 全レッグ
input string InpAuNzHolidayMondays = "2026.10.05,2026.10.26,2026.12.28,2027.01.04,2027.02.08,2027.03.29,2027.04.26,2027.06.07,2027.06.14,2027.10.04,2027.10.25,2027.12.27"; // 豪(NSW)・NZ の祝日月曜(UTC 日付)。AUD/NZD を含む Mon レッグを建てない(docs/304 Q56: 該当日は平均 −2.7 bps)。2028 年分は要追記

input group "=== 共通 ==="
input double InpMinLot = 0.01;
input double InpMaxLot = 50.0;
input long   InpMagicBase = 943110;  // Mon=+1/v4=+2/Hold=+3(パール 943100 と別・同一端末で区別)
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
double   g_dayStartEq=0.0, g_dayStartBal=0.0;
datetime g_curDay=0, g_balBlockDay=0;
int      g_balFireMonth=-1, g_balFires=0;
bool     g_balMonthHalt=false;
bool     g_halted=false, g_dayBlocked=false, g_passLocked=false, g_expired=false;
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
   if(StringFind(U,"JP225")>=0 || StringFind(U,"JPN")>=0 || StringFind(U,"NIK")>=0){
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
         ChienLog(StringFormat("[SYM] '%s' → '%s' (全銘柄走査で解決)",want,bestName));
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
      if(r==""){ ChienLog(StringFormat("⚠ %s: 銘柄'%s'を解決できず→スキップ(重みは配分から欠落=サイズ縮小側)",label,s)); continue; }
      if(r!=s) ChienLog(StringFormat("[銘柄解決] %s %s → %s",label,s,r));
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
double PipOf(string s){ return (StringFind(s,"JPY")>=0)? 0.01 : 0.0001; }

//--- v1.32(docs/153): サイズ二重チェック(tick値経路 vs 損益計算経路の保守側)
//--- Q93(docs/324・2026-10-05): 損益経路(OrderCalcProfit = 口座通貨換算済み)を正とする。tick 値経路は損益通貨建てで返す業者
//    (AXSE/Fintokei: UK100p=1.00 GBP・USOILp=1000 USD)があり、円口座では換算しないと 150〜200 倍の偽 SIZE SANITY が毎回出ていた。
//    tick 値は SYMBOL_CURRENCY_PROFIT → 口座通貨に換算してから比較し、損益経路が使えない時だけ予備として使う。
double ProfitCcyToAccount(string sym)
{
   string pc=SymbolInfoString(sym,SYMBOL_CURRENCY_PROFIT);
   string ac=AccountInfoString(ACCOUNT_CURRENCY);
   if(pc=="" || ac=="" || pc==ac) return 1.0;
   string r1=ResolveSymbol(pc+ac);
   if(r1!=""){ double b=SymbolInfoDouble(r1,SYMBOL_BID); if(b>0) return b; }
   string r2=ResolveSymbol(ac+pc);
   if(r2!=""){ double b=SymbolInfoDouble(r2,SYMBOL_BID); if(b>0) return 1.0/b; }
   return 0.0;   // 換算不能(損益経路のみ使う)
}
double MoneyPerUnit(string sym)
{
   double p=SymbolInfoDouble(sym,SYMBOL_ASK);
   double b=0.0, prof=0.0, d=p*0.001;
   if(p>0 && d>0 && OrderCalcProfit(ORDER_TYPE_BUY,sym,1.0,p,p+d,prof) && prof>0) b=prof/d;
   double tv=SymbolInfoDouble(sym,SYMBOL_TRADE_TICK_VALUE);
   double ts=SymbolInfoDouble(sym,SYMBOL_TRADE_TICK_SIZE);
   double a=(tv>0&&ts>0)? tv/ts : 0.0;
   double fx=ProfitCcyToAccount(sym);
   if(a>0 && fx>0) a*=fx; else a=0.0;
   if(b>0){
      if(a>0){ double r=(a>b? a/b:b/a);
         if(r>1.5 && StringFind(g_sizeWarned,sym)<0){ g_sizeWarned+=sym+";";
            ChienLog(StringFormat("⚠[SIZE SANITY %s] tick値経路(換算後) %.2f vs 損益経路 %.2f (乖離%.1f倍) → 損益経路を採用",sym,a,b,r)); } }
      return b;
   }
   if(a>0){ if(StringFind(g_sizeWarned,sym)<0){ g_sizeWarned+=sym+";"; ChienLog(StringFormat("⚠[SIZE %s] 損益経路が使えず tick値経路(換算後 %.2f)を採用",sym,a)); } return a; }
   return 0.0;
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
bool IsMine(long m){ return (m==g_mMon||m==g_mV4||m==g_mHold); }
void CloseAllMine(string why){
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(IsMine(posinfo.Magic())) trade.PositionClose(tk); }
   if(InpVerboseLog) ChienLog(StringFormat("[CLOSE ALL %s]",why));
}

void Notify(string s){ if(!InpNotifyEnable) return; if(g_ntfBuf!="") g_ntfBuf+=" | "; g_ntfBuf+=s; }
void FlushNotify(){
   if(g_ntfBuf=="") return;
   string msg="[RF] "+g_ntfBuf;
   if(StringLen(msg)>250) msg=StringSubstr(msg,0,247)+"...";
   if(!MQLInfoInteger(MQL_TESTER)){
      if(!SendNotification(msg))
         ChienLog(StringFormat("[NOTIFY失敗 err=%d] %s",GetLastError(),msg)); }
   ChienLog("[NOTIFY] ",msg); g_ntfBuf="";
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
   if(!InpAcknowledgeBet){ ChienLog("[STOP] 本EAは直近過剰適合の明示ベット(docs/174)。InpAcknowledgeBet=trueで承認。"); return INIT_FAILED; }
   g_nMon =ParseLegs(InpMonLegs, g_monSym, g_monW, "Mon");
   g_nV4  =ParseLegs(InpV4Legs,  g_v4Sym,  g_v4W,  "v4");
   g_nHold=(InpHoldEnable? ParseLegs(InpHoldLegs,g_holdSym,g_holdW,"Hold") : 0);
   int nh=SplitHours(InpMonHoursUTC,g_monHours);
   if(nh>8){ ArrayResize(g_monHours,8); nh=8;                       // v1.02: g_lastShotMon[MAXLEG*8]の範囲保護
      ChienLog("⚠ Mon時刻は最大8個まで→先頭8個のみ使用"); }
   if(g_nMon==0 && g_nV4==0 && g_nHold==0){ ChienLog("レッグが1つも解決できず"); return INIT_FAILED; }
   if(g_nMon>0 && nh==0){ ChienLog("Mon時刻のパース失敗"); return INIT_FAILED; }
   g_mMon=InpMagicBase+1; g_mV4=InpMagicBase+2; g_mHold=InpMagicBase+3;

   g_gvName=StringFormat("ChienRF_base_%I64d_%I64d",
                         (long)AccountInfoInteger(ACCOUNT_LOGIN),(long)InpMagicBase);
   if(InpInitialBalance>0.0){
      g_initBal=InpInitialBalance; GlobalVariableSet(g_gvName,g_initBal);
   }else if(!InpBaselineReset && GlobalVariableCheck(g_gvName)){
      g_initBal=GlobalVariableGet(g_gvName);
      ChienLog(StringFormat("[基準残高] 端末保存値を復元: %.2f",g_initBal));
   }else{
      g_initBal=AccountInfoDouble(ACCOUNT_BALANCE);
      if(g_initBal<=0.0) g_initBal=AccountInfoDouble(ACCOUNT_EQUITY);
      GlobalVariableSet(g_gvName,g_initBal);
      ChienLog(StringFormat("[基準残高] 新規記録: %.2f",g_initBal));
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
   ChienLog(StringFormat("[INIT RecentFit] initBal=%.0f mult=%.1f Σw=%.3f (グロス想定≈%.1fx) expiry=%s Magic=%I64d/%I64d/%I64d",
      g_initBal,InpMult,wsum,wsum*InpMult,TimeToString(InpExpiry,TIME_DATE),g_mMon,g_mV4,g_mHold));
   ChienLog("[NOTE] 直近特化トラック(docs/174/175)。正攻法口座とは別口座・別業者推奨。期限後は新規停止=再スクリーニング必須。");
   ChienLog(StringFormat("[INIT JpHoliday v%s] 祝日月曜スキップ='%s' jpyOnly=%s 豪NZ='%s'(docs/303/304)","1.06",InpJpHolidayMondays,(InpJpHolidayJpyOnly?"true":"false"),InpAuNzHolidayMondays));
   EventSetTimer(30);
   ChienLogInit();   // Q111
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){
   ChienLogDeinit();   // Q111
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
      ChienLog(StringFormat("[日次基準復元] 日開始bal=%.2f eq=%.2f%s%s",g_dayStartBal,g_dayStartEq,
                  (g_balBlockDay==today?" BAL_GUARD継続":""),(g_dayBlocked?" DAILY_STOP継続":"")));
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
   ChienLog(StringFormat("[BAL GUARD] eq %.2f <= 日開始bal %.2f -%.1f%% → 全決済・当日停止(月内%d回目%s)",
               beq,g_dayStartBal,InpBalGuardPct,g_balFires,(g_balMonthHalt?"・月末まで停止":"")));
   Notify(StringFormat("BAL_GUARD -%.1f%% 全決済・当日停止(%d/月)",InpBalGuardPct,g_balFires));
   FlushNotify();
}
void OnTick(){ BalGuardCheck(); }

//==================================================================
void OnTimer()
{
   ChienLogTimer();   // Q111: 約定・スナップショット・送信(30 秒ごと・失敗は無視)
   FlushNotify();
   datetime now=TimeCurrent(); datetime utc=TimeGMT();
   if(DayStart(now)!=g_curDay) ResetDay(now);
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);

   // 有効期限(docs/174停止規則): 期限後は新規停止。建玉は通常管理(時間切れ決済のみ)。
   if(!g_expired && now>=InpExpiry){
      g_expired=true;
      ChienLog("[EXPIRY] 有効期限到達 → 新規停止。recentfit_screen.py を再実行し構成を更新すること(docs/174)。");
      Notify("EXPIRY 新規停止(再スクリーニング必須)"); FlushNotify();
   }

   // 静的フロア(初期残高基準)
   double floorEq=g_initBal*(1.0-InpMaxLossLimitPct/100.0);
   double guard=floorEq+g_initBal*(InpMaxLossLimitPct-InpAccountFloorDDPct)/100.0;
   if(equity<=guard && !g_halted){ g_halted=true; CloseAllMine("EQUITY_FLOOR");
      ChienLog(StringFormat("[HALT] equity %.2f <= guard %.2f",equity,guard));
      Notify(StringFormat("FLOOR %.2f 全決済・恒久停止",equity)); FlushNotify(); }
   if(g_halted){ CloseAllMine("HALTED"); return; }

   // 利益ロック(通過確定)
   double gainPct=(g_initBal>0? (equity-g_initBal)/g_initBal*100.0 : 0.0);
   if(InpProfitLockEnable && !g_passLocked && gainPct>=InpLockClosePct){
      g_passLocked=true; CloseAllMine("PROFIT_LOCK");
      ChienLog(StringFormat("[PROFIT LOCK] equity %+.2f%% >= +%.2f%% → 全決済・恒久ロック",gainPct,InpLockClosePct));
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
         ChienLog(StringFormat("[DAILY STOP] %.2f",dpnl));
         Notify(StringFormat("DAILY_STOP -%.1f%% 当日新規停止",InpDailyStopPct)); FlushNotify(); }
   }

   ManageMonExit();
   ManageV4Exit();

   bool blockNew = (InpProfitStopPct>0 && equity>=g_initBal*(1.0+InpProfitStopPct/100.0))
                   || g_dayBlocked || g_expired
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
         ChienLog(StringFormat("[Mon TIME EXIT] %s",posinfo.Symbol())); }
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
      if(JpHolidayMonday(utc,sym)){ g_lastShotMon[key]=hourBar; if(InpVerboseLog) ChienLog(StringFormat("[Mon SKIP] %s 祝日月曜(日本 docs/303 / 豪NZ docs/304)",sym)); continue; }
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
           if(InpVerboseLog) ChienLog(StringFormat("[Mon ENTRY] LONG %s h%dUTC lots=%.2f notional=%.0f SL=%.3f",sym,g_monHours[slot],lots,notional,sl));
           if(InpNotifyEntries) Notify(StringFormat("IN Mon %s %.2f",sym,lots)); }
      else ChienLog(StringFormat("[Mon RETRY] %s h%d 発注失敗ret=%d(同時間帯内で再試行)",sym,g_monHours[slot],(int)trade.ResultRetcode()));
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
         ChienLog(StringFormat("[v4 TIME EXIT %dd] %s",heldDays,posinfo.Symbol())); }
   }
}
int g_v4Tries[MAXLEG];   // v1.01: v4のバー内再試行カウンタ

void V4Fail(int i, datetime db, string why)
{
   g_v4Tries[i]++;                                   // 30秒タイマーで再試行(最大120回≈1時間)
   if(g_v4Tries[i]>=120){
      ChienLog(StringFormat("[v4 GIVEUP] %s %s %d回失敗→当バー断念",g_v4Sym[i],why,g_v4Tries[i]));
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
         if(InpVerboseLog && g_v4Tries[i]==0) ChienLog(StringFormat("[v4 EVAL] %s 合議不成立(バー%s)",sym,TimeToString(db,TIME_DATE)));
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
            if(InpVerboseLog) ChienLog(StringFormat("[v4 ENTRY] LONG %s lots=%.2f notional=%.0f",sym,lots,notional));
            if(InpNotifyEntries) Notify(StringFormat("IN v4 L %s %.2f",sym,lots)); } }
      else     { double e=SymbolInfoDouble(sym,SYMBOL_BID);
         double sl=NormalizeDouble(e+sd,dg), tp=NormalizeDouble(e-tpd,dg);
         ok=trade.Sell(lots,sym,0.0,sl,tp,"RFv4_"+sym);
         if(ok){
            if(InpVerboseLog) ChienLog(StringFormat("[v4 ENTRY] SHORT %s lots=%.2f notional=%.0f",sym,lots,notional));
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
         if(InpVerboseLog) ChienLog(StringFormat("[Hold ENTRY] LONG %s lots=%.2f notional=%.0f SL=%.1f",sym,lots,notional,sl));
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
