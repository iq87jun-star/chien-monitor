//+------------------------------------------------------------------+
//|                                Chien_Seasonal_R4G3_Prop.mq5      |
//|   R4+G3 ワンパターン版(プロップ中央3ヶ月・挿入するだけ):            |
//|   YEARROUND_R4(リスク調整比例・月別) + G3 FOMCオーバーレイ。        |
//|                                                                   |
//|   ★使い方: チャートにドロップ → OK(残高は自動記録・.set不要)。      |
//|     新フェーズ開始時のみ InpBaselineReset=true で基準残高を更新。   |
//|   ★校正(docs/111・日次MC 20000パス):                               |
//|     倍率1.5x = 中央3.0ヶ月 / 通過95.0% / 失格5.0〜7.8% /            |
//|     最悪単日-5.4%。M3速攻(失格10〜14%)の上位互換。                  |
//|   ★内蔵: 日次-4% / フロア-8% / +7%利益ロック(7.0/7.5) /            |
//|     リスクガードMONITOR / スワップログ / 手決済再建て /              |
//|     プッシュ通知(Even G2ミラー) / 利幅通知(過去分布p75/最大)。       |
//|                                                                   |
//|   ⚠ デモ必須: R4はLOYO合格(docs/105)だがデモ未了。                  |
//|     実口座投入はデモ1ヶ月採点(docs/103)で分布内を確認後。           |
//|   ⚠ 資金化後は InpMultOverride=0.68(ガード安全倍率, docs/110)へ。   |
//|   ⚠ 実装は Chien_Seasonal_Top_EA v1.50 の逐語コピー(既定値のみ変更・ |
//|     Magic基底940700=旧EAと同居しても衝突しない)。                   |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.41"   // = Seasonal_Top_EA v1.50 相当
#property strict
#property description "[FN100k #14074882 P1 R4G3 standard] R4+G3 ONE-CLICK (median-3, 1.5x, guards+notify+width built-in, v1.40 dual-path lot sizing sanity / v1.41 no-roll-on-restart fix, docs/153). Drop on chart & OK. Demo-first (docs/110-112)."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

enum ENUM_SEASONAL_SCN { SCN_JUNE_TOP5=0, SCN_JULY_TOP2=1, SCN_AUG_V4ONLY=2, SCN_YEARROUND_05=3, SCN_YEARROUND_M3=4, SCN_YEARROUND_R4=5 };

input group "=== シナリオ ==="
input ENUM_SEASONAL_SCN InpScenario = SCN_YEARROUND_R4; // R4(既定・変更不要)
input bool   InpAcknowledgeDemo = true;   // デモ専用を承認(本資金不可)
input double InpMultOverride    = 1.5;    // 中央3ヶ月校正(docs/111)。資金化後=0.68

input group "=== ガード(プロジェクト標準) ==="
input double InpDailyStopPct      = 4.0;  // 日次この%負けたら当日停止+全決済
input double InpAccountFloorDDPct = 8.0;  // 初期残高からこの%でEA恒久停止
input double InpInitialBalance    = 100000.0;  // 0=自動(初回アタッチ時の残高を端末に永続保存・再アタッチ耐性)
input bool   InpBaselineReset     = false;// 新フェーズ開始時のみtrue=基準残高を今の残高で取り直す

input group "=== +7%利益ロック(フェーズ通過の確定, docs/100) ==="
input bool   InpProfitLockEnable  = true; // 利益ロックを使う
input double InpLockArmPct        = 7.0;  // equity+この%で新規停止(水準判定・後退で自動再開)
input double InpLockClosePct      = 7.5;  // equity+この%で全決済し恒久ロック(PASS_LOCK)

input group "=== Max Risk 3%ガード(FN規約, docs/100 §2) ==="
enum ENUM_RISK_GUARD { RG_OFF=0, RG_MONITOR=1, RG_ENFORCE=2 };
input ENUM_RISK_GUARD InpRiskGuardMode = RG_MONITOR; // MONITOR=超過をログ記録のみ / ENFORCE=新規抑制
input double InpMaxOpenRiskPct    = 3.0;  // 同時保有の想定損失合算の上限%
input double InpNoSLRiskAssumePct = 10.0; // SLなし建玉(E5/月曜/SJul)の想定損失=建玉額×この%(保守側)

input group "=== 銘柄名(業者表記が違う場合のみ変更) ==="
input string InpV4Pairs  = "EURUSD,GBPUSD,USDJPY,AUDUSD,USDCHF,USDCAD,NZDUSD,EURJPY,GBPJPY";
input string InpE5Assets = "XAUUSD,US500,NAS100,GER40";
input string InpEMon     = "US500,NAS100,GER40";
input string InpEMonX    = "JP225,UK100,FR40";
input string InpV7X      = "AUDJPY,NZDJPY,CADJPY,CHFJPY";
input string InpV7       = "EURJPY,GBPJPY,USDJPY";   // 通年シナリオの5月のみ使用
input string InpSJul     = "US500,NAS100";

input group "=== スワップ実測ログ(docs/98転記用, docs/100 §4) ==="
input bool   InpSwapLogEnable = true;     // MQL5/Files/ChienSwapLog_<口座>.csv に記録

input group "=== 手決済後の再建て(docs/100 §5) ==="
input bool   InpReenterManualClose = true; // 月保有スリーブ(S-Jul/E5)を手決済したら同月内に自動で建て直す
                                           // ※ガード(日次/フロア/ロック/月ゲート)による決済後は再建てしない

input group "=== G3 FOMCオーバーレイ(ADOPT・docs/82, 重畳は docs/110) ==="
input bool   InpG3Enable        = true;   // G3 FOMCオーバーレイ(既定ON, docs/110)
input string InpG3Symbol        = "US500";
input string InpG3Dates         = "2026.01.28,2026.03.18,2026.04.29,2026.06.17,2026.07.29,2026.09.16,2026.10.28,2026.12.09"; // 声明日(毎年Fed公式から更新)
input double InpG3RiskPct       = 1.0;    // 1イベントのリスク%(ATR(D1)変動≒この%)
input double InpG3CatATR        = 2.5;    // 災害SL=2.5×ATR(D1)
input int    InpG3EntryHourET   = 14;     // エントリ=声明24h前(前日のこの時刻ET)
input int    InpG3ExitMinBefore = 5;      // 声明何分前に手仕舞うか(検証=0分・5分は保守側)

input group "=== プッシュ通知(MT5モバイル→スマホ→Even G2ミラー, docs/112) ==="
input bool   InpNotifyEnable      = true;   // SendNotificationを使う(要MetaQuotes ID設定)
input bool   InpNotifyEntries     = true;   // エントリー(G3含む)を通知
input double InpNotifyRefPct      = 6.0;    // 手決済の参考値: equity+この%で「検討ライン」通知
input double InpNotifyDayWarnPct  = 3.0;    // 日次−この%で警告(ガード−4%の手前)
input bool   InpNotifyWidth       = true;   // 利幅通知: スリーブ月内PnLが過去p75/最大(1x換算)超えで通知
                                            // ※上振れの認識用。行動は利益ロック任せ(docs/112 §5)

input group "=== 詳細 ==="
input int    InpHoldHoursMonday = 24;     // 月曜系の保有時間
input int    InpV4MaxHoldDays   = 8;      // v4の時間切れ(D1バー)
input int    InpV4MaxConcurrent = 4;      // v4同時保有上限(証拠金安全弁)
input double InpMaxSpreadBps    = 10.0;   // これ超のスプレッドは見送り
input long   InpMagicBase       = 940700; // 旧Seasonal(930700)と別基底=同居可
input bool   InpVerboseLog      = true;

//==================================================================
CTrade        trade;
CPositionInfo posinfo;

int      g_month   = 6;
double   g_mult    = 2.0;
double   g_initBal = 0.0;
bool     g_halted  = false;
bool     g_dayHalt = false;
int      g_dayKey  = -1;
double   g_dayStartEq = 0.0;
bool     g_lockDone = false;   // PASS_LOCK(恒久・+LockClose%で全決済済み)
bool     g_lockArmed = false;  // 新規停止中(+LockArm%以上・水準判定)
string   g_g3sym="";           // G3 FOMCオーバーレイ(v1.30)
int      g_g3atr=INVALID_HANDLE;
datetime g_g3WinStart[64], g_g3WinEnd[64];
int      g_g3n=0;
datetime g_g3Entered=0;
string   g_ntfBuf="";          // 通知バッファ(タイマー1回=1通に集約)
bool     g_ntfRef=false;       // 参考値ライン通知済み(水準を離れたら再武装)
bool     g_ntfArm=false;
int      g_ntfDayKey=-1;       // 日次警告は1日1回
string   g_gvName="";          // 基準残高の端末保存キー(4週失効対策で日次タッチ)
datetime g_lastD1  = 0;
int      g_e5MonthKey = -1, g_sjulMonthKey = -1, g_monWeekKey[64];

#define SL_V4   1
#define SL_E5   2
#define SL_EMON 3
#define SL_EMONX 4
#define SL_V7X  5
#define SL_SJUL 6
#define SL_V7   7
#define SL_G3   8   // FOMCオーバーレイ(月ゲートの対象外・全ガードの対象)

string g_v4[16], g_e5[8], g_emon[8], g_emonx[8], g_v7x[8], g_sjul[8], g_v7[8];
int    g_nv4=0, g_ne5=0, g_nemon=0, g_nemonx=0, g_nv7x=0, g_nsjul=0, g_nv7=0;
int    g_curMonth=-1;   // 通年シナリオの月替わり検出
bool   g_rollPending=false; // 月替わり全決済の完了待ちフラグ(v1.30: 週末月替わりの迷子建玉対策)

// 通年(YEARROUND_05): 月利0.5%以上を平均比例配分(docs/87 §通年・2016-2025選抜)
// index=月(1-12)。合計1.0/月。
double WY_V4[13]   ={0, 0,   1.00,0.19,0,   0.46,0.38,0,   0.46,1.00,0,   0,   0.23};
double WY_E5[13]   ={0, 0,   0,   0.20,0,   0,   0.36,0.24,0.41,0,   0,   0,   0.42};
double WY_EMON[13] ={0, 1.00,0,   0.33,0,   0,   0.15,0,   0,   0,   0,   1.00,0.36};
double WY_EMONX[13]={0, 0,   0,   0.28,1.00,0,   0.12,0,   0.13,0,   1.00,0,   0};
double WY_V7X[13]  ={0, 0,   0,   0,   0,   0.31,0,   0,   0,   0,   0,   0,   0};
double WY_V7[13]   ={0, 0,   0,   0,   0,   0.23,0,   0,   0,   0,   0,   0,   0};
double WY_SJUL[13] ={0, 0,   0,   0,   0,   0,   0,   0.76,0,   0,   0,   0,   0};

// 通年(YEARROUND_R4): リスク調整比例(docs/105 R4・全期間訓練, docs/110)。index=月。
double WR4_V4[13]   ={0, 0,    1.00, 0.38, 0,    0.092,0.25, 0,    0.331,0.483,0,    0,    0.406};
double WR4_E5[13]   ={0, 0,    0,    0.217,0,    0,    0.332,0,    0.328,0,    0,    0,    0.594};
double WR4_EMON[13] ={0, 0.689,0,    0.403,0.773,0.084,0.173,0,    0.206,0.517,0.379,0,    0};
double WR4_EMONX[13]={0, 0,    0,    0,    0,    0.114,0,    0,    0,    0,    0.437,0.181,0};
double WR4_V7X[13]  ={0, 0,    0,    0,    0,    0.270,0,    0,    0,    0,    0,    0,    0};
double WR4_V7[13]   ={0, 0,    0,    0,    0,    0.279,0,    0,    0,    0,    0,    0,    0};
double WR4_SJUL[13] ={0, 0.311,0,    0,    0.227,0.162,0.245,1.00, 0.135,0,    0.184,0.819,0};

// 利幅通知用: 各スリーブの月次リターン過去分布(1x・2016-2025 Yahoo再構築, %)。
// p75=75%分位 / MAX=最大。research/seasonal_optimize_loyo の月次系列から生成(docs/112 §5)。
double WP75_V4[13]  ={0,1.81,2.89,3.53,1.39,3.58,2.87,1.14,3.72,2.12,2.40,0.71,1.76};
double WMAX_V4[13]  ={0,2.08,5.57,4.52,3.79,5.91,11.71,6.07,5.27,3.94,4.39,3.01,2.49};
double WP75_E5[13]  ={0,0.87,2.13,3.16,1.61,1.10,1.89,1.45,2.08,2.41,1.91,1.65,1.51};
double WMAX_E5[13]  ={0,4.35,3.89,4.42,2.12,4.00,7.54,5.40,5.44,7.05,2.61,2.91,3.56};
double WP75_EMON[13]={0,0.94,0.66,2.68,1.22,1.13,1.67,0.37,1.71,1.15,1.07,1.05,0.99};
double WMAX_EMON[13]={0,2.65,2.04,9.45,7.48,7.06,9.05,1.83,2.11,2.72,7.09,1.78,2.71};
double WP75_EMONX[13]={0,0.50,1.01,0.72,0.91,1.29,0.73,0.90,0.65,0.72,1.06,0.84,0.64};
double WMAX_EMONX[13]={0,2.09,4.00,1.23,4.16,5.02,3.38,1.42,3.36,2.20,4.64,6.58,1.70};
double WP75_V7X[13] ={0,0.51,0.48,0.43,0.78,1.36,0.59,0.83,0.28,0.28,1.46,0.51,0.54};
double WMAX_V7X[13] ={0,1.23,1.71,1.19,1.49,2.20,2.98,1.60,1.49,1.16,2.27,2.69,2.01};
double WP75_V7[13]  ={0,0.23,0.16,0.46,0.45,0.87,0.31,0.86,0.10,0.60,0.90,0.86,0.79};
double WMAX_V7[13]  ={0,1.34,1.67,2.03,1.17,1.39,0.93,2.15,1.64,1.43,2.15,2.33,2.47};
double WP75_SJUL[13]={0,5.58,2.80,3.18,3.60,5.12,5.45,4.65,2.97,1.34,3.29,5.64,2.98};
double WMAX_SJUL[13]={0,8.76,5.60,6.67,14.02,7.80,7.11,10.68,8.25,4.52,7.04,11.23,4.92};

//------------------------------------------------------------------
string ResolveSymbol(string want)
{
   string suf[]={"",".pi",".raw",".ecn",".stp",".pro",".cash",".r",".c",".m","m",".spot","-cash",".sd","+",".i","_SB","_raw",".a",".z"};
   string bases[]; ArrayResize(bases,40); int nb=0;
   bases[nb++]=want;
   string U=want; StringToUpper(U);
   if(StringFind(U,"XAU")>=0 || StringFind(U,"GOLD")>=0){
      bases[nb++]="XAUUSD"; bases[nb++]="GOLD"; bases[nb++]="GOLDUSD"; }
   else if(StringFind(U,"SPX")>=0 || StringFind(U,"US500")>=0 || StringFind(U,"500")==0){
      bases[nb++]="US500"; bases[nb++]="SPX500"; bases[nb++]="SP500"; bases[nb++]="USA500"; bases[nb++]="US500Cash"; bases[nb++]="SPX"; }
   else if(StringFind(U,"NAS")>=0 || StringFind(U,"USTEC")>=0 || StringFind(U,"NDX")>=0 || StringFind(U,"US100")>=0){
      bases[nb++]="NAS100"; bases[nb++]="USTEC"; bases[nb++]="US100"; bases[nb++]="NDX100"; bases[nb++]="USTECH"; bases[nb++]="NDX"; }
   else if(StringFind(U,"GER")>=0 || StringFind(U,"DAX")>=0 || StringFind(U,"DE40")>=0){
      bases[nb++]="GER40"; bases[nb++]="DE40"; bases[nb++]="DAX40"; bases[nb++]="GERMANY40"; bases[nb++]="DAX"; }
   else if(StringFind(U,"JP225")>=0 || StringFind(U,"JPN")>=0 || StringFind(U,"NIK")>=0){
      bases[nb++]="JP225"; bases[nb++]="JPN225"; bases[nb++]="NIKKEI225"; bases[nb++]="JP225Cash"; bases[nb++]="NI225"; bases[nb++]="JPN225.cash"; }
   else if(StringFind(U,"UK100")>=0 || StringFind(U,"FTSE")>=0){
      bases[nb++]="UK100"; bases[nb++]="FTSE100"; bases[nb++]="UK100Cash"; bases[nb++]="GB100"; }
   else if(StringFind(U,"FR40")>=0 || StringFind(U,"CAC")>=0 || StringFind(U,"FRA40")>=0){
      bases[nb++]="FR40"; bases[nb++]="FRA40"; bases[nb++]="CAC40"; bases[nb++]="F40"; bases[nb++]="FRA40.cash"; }
   ArrayResize(bases,nb);
   for(int b=0;b<nb;b++)
      for(int s=0;s<ArraySize(suf);s++){
         string cand=bases[b]+suf[s];
         if(SymbolSelect(cand,true)) return cand;
      }
   return "";
}

int SplitResolve(string csv, string &arr[], int maxn, string label)
{
   string parts[]; int n=StringSplit(csv,',',parts); int k=0;
   for(int i=0;i<n && k<maxn;i++){
      string s=parts[i]; StringTrimLeft(s); StringTrimRight(s);
      if(StringLen(s)==0) continue;
      string r=ResolveSymbol(s);
      if(r==""){ PrintFormat("[WARN] %s: 銘柄'%s'を解決できず(スキップ)",label,s); continue; }
      arr[k++]=r;
   }
   return k;
}

//------------------------------------------------------------------
int OnInit()
{
   if(!InpAcknowledgeDemo){ Print("[STOP] デモ専用EA。InpAcknowledgeDemo=trueで承認してください。"); return INIT_FAILED; }
   if(InpScenario==SCN_JUNE_TOP5)      { g_month=6; g_mult=2.0; }
   else if(InpScenario==SCN_JULY_TOP2) { g_month=7; g_mult=1.3; }
   else if(InpScenario==SCN_AUG_V4ONLY){ g_month=8; g_mult=0.4; }   // 8月: v4単独。2024/8/5(円急騰)に同日複数SLで-8.9%/1x→日次ガード逆算0.5x×安全率(docs/87)
   else if(InpScenario==SCN_YEARROUND_05){ g_month=0; g_mult=0.7; } // 通年・運用版: 1xでmaxDD-9.0%=枠いっぱい→0.9x上限×安全率0.8(docs/87)
   else if(InpScenario==SCN_YEARROUND_R4){ g_month=0; g_mult=2.27; } // 通年・R4(リスク調整比例, docs/105/110)。2.27x=現行M3と同じ踏み込み係数。⚠ガード安全倍率は0.68(docs/110)=速攻値。デモ必須
   else                                { g_month=0; g_mult=2.0; }   // 通年・median-3チャレンジ版: 中央3.1ヶ月/失格MC1.5%(楽観値,docs/87)。⚠暴落日はガードが間に合わない可能性=デモ必須
   if(InpMultOverride>0.0) g_mult=InpMultOverride;
   // 基準残高(docs/112): 明示入力 > 端末保存値(初回アタッチ時に記録・再アタッチ/再起動で不変) > 現残高
   // フェーズが変わったら InpBaselineReset=true で取り直す(P1→P2、新チャレンジ等)。
   {
      string gv=StringFormat("ChienSeasonal_base_%I64d_%I64d",
                             (long)AccountInfoInteger(ACCOUNT_LOGIN),(long)InpMagicBase);
      g_gvName=gv;
      if(InpInitialBalance>0.0){
         g_initBal=InpInitialBalance; GlobalVariableSet(gv,g_initBal);
      }else if(!InpBaselineReset && GlobalVariableCheck(gv)){
         g_initBal=GlobalVariableGet(gv);
         PrintFormat("[基準残高] 端末保存値を復元: %.2f (取り直しは InpBaselineReset=true)",g_initBal);
      }else{
         g_initBal=AccountInfoDouble(ACCOUNT_BALANCE);
         if(g_initBal<=0.0) g_initBal=AccountInfoDouble(ACCOUNT_EQUITY);
         GlobalVariableSet(gv,g_initBal);
         PrintFormat("[基準残高] 新規記録: %.2f (口座%I64d/Magic%I64d)",
                     g_initBal,(long)AccountInfoInteger(ACCOUNT_LOGIN),(long)InpMagicBase);
      }
   }

   g_nv4   =SplitResolve(InpV4Pairs, g_v4, 16,"v4");
   g_ne5   =SplitResolve(InpE5Assets,g_e5,  8,"E5");
   g_nemon =SplitResolve(InpEMon,   g_emon, 8,"E-Mon");
   g_nemonx=SplitResolve(InpEMonX,  g_emonx,8,"E-Mon横");
   g_nv7x  =SplitResolve(InpV7X,    g_v7x,  8,"v7横");
   g_nv7   =SplitResolve(InpV7,     g_v7,   8,"v7");
   g_nsjul =SplitResolve(InpSJul,   g_sjul, 8,"S-Jul");
   ArrayInitialize(g_monWeekKey,-1);

   if(InpG3Enable){
      g_g3sym=ResolveSymbol(InpG3Symbol);
      if(g_g3sym==""){ Print("⚠ G3: 銘柄解決不可→G3無効"); }
      else{
         g_g3atr=iATR(g_g3sym,PERIOD_D1,14);
         if(!ParseG3Windows()) Print("⚠ G3: FOMC日程の解析失敗→G3無効");
         else PrintFormat("[G3] 有効: %s イベント%d件 risk=%.1f%%/event(ADOPT・要デモ, docs/82/110)",
                          g_g3sym,g_g3n,InpG3RiskPct);
      }
   }
   trade.SetDeviationInPoints(50);
   EventSetTimer(60);
   string scn=(InpScenario==SCN_JUNE_TOP5?"JUNE_TOP5":
              (InpScenario==SCN_JULY_TOP2?"JULY_TOP2":
              (InpScenario==SCN_AUG_V4ONLY?"AUG_V4ONLY":
              (InpScenario==SCN_YEARROUND_05?"YEARROUND_05":
              (InpScenario==SCN_YEARROUND_R4?"YEARROUND_R4":"YEARROUND_M3")))));
   PrintFormat("[INIT Seasonal %s] 稼働月=%s 倍率=%.1fx initBal=%.0f | v4:%d E5:%d EMon:%d EMonX:%d v7x:%d v7:%d SJul:%d",
      scn,(g_month==0?"通年(月替わり自動)":IntegerToString(g_month)+"月"),g_mult,g_initBal,
      g_nv4,g_ne5,g_nemon,g_nemonx,g_nv7x,g_nv7,g_nsjul);
   Print("[NOTE] デモ専用・対象月以外は自動で全決済して待機。横展開レッグはEA初実装(docs/86)。");
   // v1.41(docs/153追補): 再起動のたびにMONTH_ROLLが走るバグ修正。
   //   g_curMonth を現在月で初期化し、正規化(全決済→建て直し)は
   //   「EA停止中に月を跨いだ建玉が残っている場合」のみ実行する。
   //   これにより端末再起動/再接続/再アタッチでは既存建玉をそのまま引き継ぐ。
   {
      MqlDateTime ti; TimeToStruct(TimeCurrent(),ti);
      g_curMonth=ti.mon;
      g_rollPending=(MonthlyStaleCount(ti.mon,ti.year)>0);
      if(g_rollPending) Print("[v1.41] 停止中の月跨ぎを検出→MONTH_ROLL正規化を実行します");
      else PrintFormat("[v1.41] 既存建玉を当月(%d月)構成として引き継ぎ(再起動での全決済はしません)",ti.mon);
   }
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){ EventKillTimer(); if(g_g3atr!=INVALID_HANDLE) IndicatorRelease(g_g3atr); }

//------------------------------------------------------------------
double SpreadBps(string s)
{
   double a=SymbolInfoDouble(s,SYMBOL_ASK), b=SymbolInfoDouble(s,SYMBOL_BID);
   if(a<=0||b<=0) return 1e9;
   return (a-b)/((a+b)/2.0)*1e4;
}
//--- v1.40(docs/153): サイズ二重チェック。tick値申告と損益計算エンジンの2経路で見積り、
//    保守側(1ロット価値が大きい方=ロットが小さくなる側)を採用。FN GER30の10倍事故の恒久対策。
string g_sizeWarned="";
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
         PrintFormat("⚠[SIZE SANITY %s] tick値経路 $%.2f vs 損益経路 $%.2f (乖離%.1f倍) → 保守側を採用しロット縮小",
                     sym,a,b,r); } }
   return m;
}

double LotsForNotional(string s, double notional)
{
   double price=SymbolInfoDouble(s,SYMBOL_ASK);
   double mpu=MoneyPerUnit(s);
   if(price<=0||mpu<=0) return 0.0;
   double valuePerLot=price*mpu;            // 1ロットの建玉評価額(口座通貨・v1.40二重チェック済)
   if(valuePerLot<=0) return 0.0;
   double lots=notional/valuePerLot;
   double step=SymbolInfoDouble(s,SYMBOL_VOLUME_STEP);
   double vmin=SymbolInfoDouble(s,SYMBOL_VOLUME_MIN);
   double vmax=SymbolInfoDouble(s,SYMBOL_VOLUME_MAX);
   if(step>0) lots=MathFloor(lots/step)*step;
   if(lots>vmax) lots=vmax;
   if(lots<vmin) return 0.0;
   return lots;
}
long MagicOf(int sleeve){ return InpMagicBase+sleeve; }

int CountSleeve(int sleeve, string sym="")
{
   int c=0;
   for(int i=PositionsTotal()-1;i>=0;i--){
      ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()!=MagicOf(sleeve)) continue;
      if(sym!="" && posinfo.Symbol()!=sym) continue;
      c++;
   }
   return c;
}
void CloseSleeve(int sleeve, string why, int olderThanSec=0, int maxBarsD1=0)
{
   for(int i=PositionsTotal()-1;i>=0;i--){
      ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(posinfo.Magic()!=MagicOf(sleeve)) continue;
      if(olderThanSec>0 && (TimeCurrent()-posinfo.Time())<olderThanSec) continue;
      if(maxBarsD1>0){
         int sh=iBarShift(posinfo.Symbol(),PERIOD_D1,posinfo.Time());
         if(sh<maxBarsD1) continue;
      }
      if(trade.PositionClose(tk) && InpVerboseLog)
         PrintFormat("[CLOSE %s] %s",why,posinfo.Symbol());
   }
}
void CloseAllMine(string why)      // ガード用: G3含む全スリーブ
{
   for(int sl=SL_V4; sl<=SL_G3; sl++) CloseSleeve(sl,why);
}
void CloseAllMonthly(string why)   // 月ゲート用: G3(イベント建玉)は対象外
{
   for(int sl=SL_V4; sl<=SL_V7; sl++) CloseSleeve(sl,why);
}

//--- v1.41(docs/153追補): 先月以前に建った月ゲート建玉の数(EA停止中に月を跨いだ場合のみ>0)
int MonthlyStaleCount(int curMon, int curYear)
{
   int n=0;
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      long m=posinfo.Magic();
      if(m<InpMagicBase+SL_V4 || m>InpMagicBase+SL_V7) continue;
      MqlDateTime pt; TimeToStruct((datetime)posinfo.Time(),pt);
      if(pt.mon!=curMon || pt.year!=curYear) n++; }
   return n;
}

int MonthlyOpenCount()   // 月ゲート対象(G3除く)の残建玉数: 休場中のMONTH_ROLL再試行判定に使う
{
   int n=0;
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      long m=posinfo.Magic();
      if(m>=InpMagicBase+SL_V4 && m<=InpMagicBase+SL_V7) n++; }
   return n;
}

// ===== Max Risk 3%ガード(docs/100 §2) =====
// 自スリーブ全建玉の「SL到達時の想定損失」合算を初期残高比%で返す。
// 本EAはE5/月曜系/S-JulがSLなし建玉→建玉額×InpNoSLRiskAssumePctで保守側に見積る。
bool IsMyMagic(long m){ return (m>=InpMagicBase+SL_V4 && m<=InpMagicBase+SL_G3); }
double OpenRiskPct()
{
   double total=0.0;
   for(int i=PositionsTotal()-1;i>=0;i--){
      ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(!IsMyMagic(posinfo.Magic())) continue;
      string sym=posinfo.Symbol();
      double vol=posinfo.Volume(), sl=posinfo.StopLoss(), op=posinfo.PriceOpen();
      double mpu=MoneyPerUnit(sym);
      double risk=0.0;
      if(sl>0.0 && mpu>0) risk=MathAbs(op-sl)*mpu*vol;
      else{
         double px=SymbolInfoDouble(sym,SYMBOL_BID);
         if(mpu>0 && px>0) risk=px*mpu*vol*InpNoSLRiskAssumePct/100.0;
      }
      total+=risk;
   }
   return (g_initBal>0? 100.0*total/g_initBal : 0.0);
}
// ===== スワップ実測ログ(docs/100 §4) =====
// 目的: E5/S-Jul等の持越しコスト実測→docs/98へ月次転記。CSV: MQL5/Files/ChienSwapLog_<口座>.csv
//  SNAPSHOT行: 日次・保有中建玉の累積スワップ / MONTHLY行: 決済履歴からスリーブ別の実現スワップ合算
string SleeveName(long magic)
{
   int s=(int)(magic-InpMagicBase);
   switch(s){ case SL_V4: return "v4"; case SL_E5: return "E5"; case SL_EMON: return "EMon";
              case SL_EMONX: return "EMonX"; case SL_V7X: return "v7x"; case SL_SJUL: return "SJul";
              case SL_V7: return "v7"; case SL_G3: return "G3"; }
   return "other";
}
void SwapLogWrite(string line)
{
   string fn=StringFormat("ChienSwapLog_%I64d.csv",(long)AccountInfoInteger(ACCOUNT_LOGIN));
   int h=FileOpen(fn,FILE_READ|FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_SHARE_READ);
   if(h==INVALID_HANDLE) return;
   if(FileSize(h)==0) FileWriteString(h,"type,date,ea,sleeve,symbol,ticket,lots,swap,commission,profit,note\n");
   FileSeek(h,0,SEEK_END); FileWriteString(h,line+"\n"); FileClose(h);
}
void SwapLogDailySnapshot()
{
   for(int i=PositionsTotal()-1;i>=0;i--){
      ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(!IsMyMagic(posinfo.Magic())) continue;
      SwapLogWrite(StringFormat("SNAPSHOT,%s,Seasonal,%s,%s,%I64u,%.2f,%.2f,,%.2f,accum-open",
         TimeToString(TimeCurrent(),TIME_DATE),SleeveName(posinfo.Magic()),
         posinfo.Symbol(),tk,posinfo.Volume(),posinfo.Swap(),posinfo.Profit()));
   }
}
datetime SwapMonthStart(int y,int m)
{
   MqlDateTime s; s.year=y; s.mon=m; s.day=1; s.hour=0; s.min=0; s.sec=0; s.day_of_week=0; s.day_of_year=0;
   return StructToTime(s);
}
void SwapLogMonthlySummary(int y,int m)   // 前月(y,m)の実現スワップをスリーブ別に合算
{
   int y2=(m==12? y+1:y), m2=(m==12? 1:m+1);
   datetime from=SwapMonthStart(y,m), to=SwapMonthStart(y2,m2);
   if(!HistorySelect(from,to)) return;
   double sw[9], cm[9], pf[9]; int cnt[9];
   ArrayInitialize(sw,0); ArrayInitialize(cm,0); ArrayInitialize(pf,0); ArrayInitialize(cnt,0);
   for(int i=HistoryDealsTotal()-1;i>=0;i--){
      ulong dt=HistoryDealGetTicket(i); if(dt==0) continue;
      long mg=(long)HistoryDealGetInteger(dt,DEAL_MAGIC);
      if(!IsMyMagic(mg)) continue;
      int s=(int)(mg-InpMagicBase); if(s<1||s>SL_G3) continue;
      sw[s]+=HistoryDealGetDouble(dt,DEAL_SWAP);
      cm[s]+=HistoryDealGetDouble(dt,DEAL_COMMISSION);
      pf[s]+=HistoryDealGetDouble(dt,DEAL_PROFIT); cnt[s]++;
   }
   for(int s=1;s<=SL_G3;s++){
      if(cnt[s]==0) continue;
      SwapLogWrite(StringFormat("MONTHLY,%04d-%02d,Seasonal,%s,,,,%.2f,%.2f,%.2f,deals=%d",
         y,m,SleeveName(InpMagicBase+s),sw[s],cm[s],pf[s],cnt[s]));
   }
}
int g_swapMonKey=-1;

// 手決済判定(docs/100 §5): 当月内の該当スリーブ×銘柄の直近クローズ約定が
// 手動(CLIENT/MOBILE/WEB)なら true。EA起点(EXPERT=ガード/月ゲート)や SL なら false。
bool ManualCloseThisMonth(int sleeve, string sym)
{
   MqlDateTime t; TimeToStruct(TimeCurrent(),t);
   if(!HistorySelect(SwapMonthStart(t.year,t.mon),TimeCurrent()+60)) return false;
   for(int i=HistoryDealsTotal()-1;i>=0;i--){
      ulong dt=HistoryDealGetTicket(i); if(dt==0) continue;
      if((long)HistoryDealGetInteger(dt,DEAL_MAGIC)!=MagicOf(sleeve)) continue;
      if(HistoryDealGetString(dt,DEAL_SYMBOL)!=sym) continue;
      if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(dt,DEAL_ENTRY)!=DEAL_ENTRY_OUT) continue;
      long r=(long)HistoryDealGetInteger(dt,DEAL_REASON);
      return (r==DEAL_REASON_CLIENT || r==DEAL_REASON_MOBILE || r==DEAL_REASON_WEB);
   }
   return false;
}

datetime g_rgLastLog=0;
bool RiskGuardBlocked(string ctx)
{
   if(InpRiskGuardMode==RG_OFF || InpMaxOpenRiskPct<=0) return false;
   double r=OpenRiskPct();
   if(r<=InpMaxOpenRiskPct) return false;
   if(TimeCurrent()-g_rgLastLog>=900){
      g_rgLastLog=TimeCurrent();
      PrintFormat("[RISK GUARD %s] open-risk %.2f%% > %.2f%% (%s) %s",
         (InpRiskGuardMode==RG_ENFORCE?"ENFORCE":"MONITOR"),r,InpMaxOpenRiskPct,ctx,
         (InpRiskGuardMode==RG_ENFORCE?"→ 新規抑制":"→ 記録のみ(docs/100 §2)"));
   }
   return (InpRiskGuardMode==RG_ENFORCE);
}
bool OpenNotional(string s, int sleeve, int dir, double notional, double slPrice=0.0, double tpPrice=0.0, string tag="")
{
   if(g_lockDone || g_lockArmed) return false;   // 利益ロック: 新規停止(決済系は各スリーブで継続)
   if(RiskGuardBlocked(tag)) return false;       // Max Riskガード(ENFORCE時のみ抑制)
   if(SpreadBps(s)>InpMaxSpreadBps){
      if(InpVerboseLog) PrintFormat("[SKIP] %s spread %.1fbps",s,SpreadBps(s));
      return false;
   }
   double lots=LotsForNotional(s,notional);
   if(lots<=0){ if(InpVerboseLog) PrintFormat("[SKIP] %s lots=0 (notional %.0f)",s,notional); return false; }
   trade.SetExpertMagicNumber(MagicOf(sleeve));
   bool ok=(dir>0)? trade.Buy(lots,s,0.0,slPrice,tpPrice,tag)
                  : trade.Sell(lots,s,0.0,slPrice,tpPrice,tag);
   if(ok && InpVerboseLog) PrintFormat("[ENTRY %s] %s %s lots=%.2f notional=%.0f",tag,s,(dir>0?"L":"S"),lots,notional);
   if(ok && InpNotifyEntries) Notify(StringFormat("IN %s %s %.2f",tag,s,lots));
   return ok;
}

//------------------------------------------------------------------ プッシュ通知(docs/112)
// MT5モバイルアプリへ送信→スマホ通知→Even Realitiesアプリのミラーリングで G2 に表示。
// タイマー1回分のイベントを1通に集約(SendNotificationのレート制限対策)。テスターでは無効。
void Notify(string s)
{
   if(!InpNotifyEnable) return;
   if(g_ntfBuf!="") g_ntfBuf+=" | ";
   g_ntfBuf+=s;
}
void FlushNotify()
{
   if(g_ntfBuf=="") return;
   string msg="[季節EA] "+g_ntfBuf;
   if(StringLen(msg)>250) msg=StringSubstr(msg,0,247)+"...";
   if(!MQLInfoInteger(MQL_TESTER)){
      if(!SendNotification(msg))
         PrintFormat("[NOTIFY失敗 err=%d] %s (ツール→オプション→通知のMetaQuotes ID設定を確認)",GetLastError(),msg);
   }
   Print("[NOTIFY] ",msg);
   g_ntfBuf="";
}

//------------------------------------------------------------------ 利幅通知(docs/112 §5)
// スリーブ別の月内PnL(実現+含み)を1x換算し、過去分布のp75/最大(上表)超えで通知。
// 上振れの「認識」用であり手決済の推奨ではない(処理は利益ロックが担う)。
double WidthRef(int sl, int m, bool wantMax)
{
   switch(sl){
      case SL_V4:    return wantMax? WMAX_V4[m]   : WP75_V4[m];
      case SL_E5:    return wantMax? WMAX_E5[m]   : WP75_E5[m];
      case SL_EMON:  return wantMax? WMAX_EMON[m] : WP75_EMON[m];
      case SL_EMONX: return wantMax? WMAX_EMONX[m]: WP75_EMONX[m];
      case SL_V7X:   return wantMax? WMAX_V7X[m]  : WP75_V7X[m];
      case SL_V7:    return wantMax? WMAX_V7[m]   : WP75_V7[m];
      case SL_SJUL:  return wantMax? WMAX_SJUL[m] : WP75_SJUL[m];
   }
   return 0.0;
}
double SleeveWeightNow(int sl, int m)
{
   if(InpScenario==SCN_JUNE_TOP5){
      if(m!=6) return 0;
      switch(sl){ case SL_V4: return .414; case SL_E5: return .219; case SL_EMON: return .160;
                  case SL_EMONX: return .133; case SL_V7X: return .074; } return 0;
   }
   if(InpScenario==SCN_JULY_TOP2){
      if(m!=7) return 0;
      switch(sl){ case SL_SJUL: return .685; case SL_E5: return .315; } return 0;
   }
   if(InpScenario==SCN_AUG_V4ONLY) return (m==8 && sl==SL_V4)? 1.0 : 0.0;
   if(InpScenario==SCN_YEARROUND_R4){
      switch(sl){ case SL_V4: return WR4_V4[m]; case SL_E5: return WR4_E5[m]; case SL_EMON: return WR4_EMON[m];
                  case SL_EMONX: return WR4_EMONX[m]; case SL_V7X: return WR4_V7X[m];
                  case SL_V7: return WR4_V7[m]; case SL_SJUL: return WR4_SJUL[m]; } return 0;
   }
   // YEARROUND_05 / M3
   switch(sl){ case SL_V4: return WY_V4[m]; case SL_E5: return WY_E5[m]; case SL_EMON: return WY_EMON[m];
               case SL_EMONX: return WY_EMONX[m]; case SL_V7X: return WY_V7X[m];
               case SL_V7: return WY_V7[m]; case SL_SJUL: return WY_SJUL[m]; }
   return 0;
}
int  g_widthMonKey=-1;
uint g_widthLatch=0;    // bit: sleeve*2(p75) / sleeve*2+1(max)。月替わりでリセット
void CheckWidthNotify()
{
   if(!InpNotifyEnable || !InpNotifyWidth || g_initBal<=0) return;
   MqlDateTime t; TimeToStruct(TimeCurrent(),t);
   int mk=t.year*100+t.mon;
   if(mk!=g_widthMonKey){ g_widthMonKey=mk; g_widthLatch=0; }
   // 月内PnL(実現)をスリーブ別に集計
   double pnl[9]; ArrayInitialize(pnl,0);
   if(HistorySelect(SwapMonthStart(t.year,t.mon),TimeCurrent()+60)){
      for(int i=HistoryDealsTotal()-1;i>=0;i--){
         ulong dt=HistoryDealGetTicket(i); if(dt==0) continue;
         long mg=(long)HistoryDealGetInteger(dt,DEAL_MAGIC);
         if(!IsMyMagic(mg)) continue;
         int s=(int)(mg-InpMagicBase); if(s<1||s>SL_G3) continue;
         pnl[s]+=HistoryDealGetDouble(dt,DEAL_PROFIT)+HistoryDealGetDouble(dt,DEAL_SWAP)
                +HistoryDealGetDouble(dt,DEAL_COMMISSION);
      }
   }
   for(int i=PositionsTotal()-1;i>=0;i--){       // +含み
      ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(!IsMyMagic(posinfo.Magic())) continue;
      int s=(int)(posinfo.Magic()-InpMagicBase); if(s<1||s>SL_G3) continue;
      pnl[s]+=posinfo.Profit()+posinfo.Swap();
   }
   for(int s=SL_V4;s<=SL_V7;s++){                // G3は対象外(イベント建玉)
      double w=SleeveWeightNow(s,t.mon)*g_mult;
      if(w<=0.01) continue;
      double acc=100.0*pnl[s]/g_initBal;         // 口座%
      double r1x=acc/w;                          // 素サイズ1x換算
      double p75=WidthRef(s,t.mon,false), wmax=WidthRef(s,t.mon,true);
      uint b75=(uint)1<<(uint)(s*2), bmx=(uint)1<<(uint)(s*2+1);
      if(wmax>0 && r1x>=wmax && (g_widthLatch&bmx)==0){
         g_widthLatch|=bmx|b75;
         Notify(StringFormat("利幅 %s 月内%+.2f%%(1x%+.2f%%)が過去最大%+.2f%%超え=⚪上振れ(docs/98)。処理はロック任せ",
                SleeveName(MagicOf(s)),acc,r1x,wmax));
      }else if(p75>0 && r1x>=p75 && (g_widthLatch&b75)==0){
         g_widthLatch|=b75;
         Notify(StringFormat("利幅 %s 月内%+.2f%%(1x%+.2f%% ≥ p75 %+.2f%%)。上振れ認識・行動不要",
                SleeveName(MagicOf(s)),acc,r1x,p75));
      }
   }
}

//------------------------------------------------------------------ G3 FOMCオーバーレイ(Chien_FOMC_Drift_EAから逐語移植, docs/82)
void ZeroMemoryStruct(MqlDateTime &t){ t.year=0;t.mon=0;t.day=0;t.hour=0;t.min=0;t.sec=0;t.day_of_week=0;t.day_of_year=0; }
datetime NthSundayUtc(int year,int month,int nth,int utcHour)
{
   MqlDateTime t; ZeroMemoryStruct(t);
   t.year=year; t.mon=month; t.day=1; t.hour=0;
   datetime d1=StructToTime(t);
   MqlDateTime w; TimeToStruct(d1,w);
   int firstSun = 1 + ((7 - w.day_of_week) % 7);
   t.day=firstSun + 7*(nth-1); t.hour=utcHour;
   return StructToTime(t);
}
bool IsDstUS(datetime utc)
{
   MqlDateTime t; TimeToStruct(utc,t);
   return (utc>=NthSundayUtc(t.year,3,2,7) && utc<NthSundayUtc(t.year,11,1,6));
}
datetime EtToUtc(int year,int mon,int day,int hourEt,int minEt)
{
   MqlDateTime t; ZeroMemoryStruct(t);
   t.year=year; t.mon=mon; t.day=day; t.hour=hourEt; t.min=minEt;
   datetime asUtc=StructToTime(t);
   int offset = IsDstUS(asUtc+5*3600) ? 4 : 5;    // EDT/EST(境界週の±1hはFOMC日に該当なし)
   return asUtc + offset*3600;
}
bool ParseG3Windows()
{
   g_g3n=0;
   string parts[]; int n=StringSplit(InpG3Dates,',',parts);
   for(int i=0;i<n && g_g3n<64;i++){
      string s=parts[i]; StringTrimLeft(s); StringTrimRight(s);
      string ymd[]; if(StringSplit(s,'.',ymd)!=3) continue;
      int y=(int)StringToInteger(ymd[0]), m=(int)StringToInteger(ymd[1]), d=(int)StringToInteger(ymd[2]);
      if(y<2020||m<1||m>12||d<1||d>31) continue;
      datetime ann=EtToUtc(y,m,d,InpG3EntryHourET,0);
      g_g3WinStart[g_g3n]=ann-24*3600;
      g_g3WinEnd[g_g3n]  =ann-InpG3ExitMinBefore*60;
      g_g3n++;
   }
   return (g_g3n>0);
}
void SleeveG3()
{
   if(!InpG3Enable || g_g3sym=="" || g_g3n==0) return;
   datetime utc=TimeGMT();
   int w=-1;
   for(int i=0;i<g_g3n;i++) if(utc>=g_g3WinStart[i] && utc<g_g3WinEnd[i]){ w=i; break; }
   if(w<0){ CloseSleeve(SL_G3,"G3_WINDOW_END"); return; }   // 窓外=手仕舞い(声明5分前の退出を含む)
   if(g_g3Entered==g_g3WinStart[w]) return;                 // この窓は処理済み
   if(CountSleeve(SL_G3)>0){ g_g3Entered=g_g3WinStart[w]; return; }
   if(g_lockDone || g_lockArmed) return;                    // 利益ロック
   if(RiskGuardBlocked("G3")) return;                       // Max Riskガード
   if(SpreadBps(g_g3sym)>InpMaxSpreadBps) return;           // 次のタイマーで再試行
   double a[1];
   if(g_g3atr==INVALID_HANDLE || CopyBuffer(g_g3atr,0,1,1,a)<1) return;
   double atr=a[0]; if(atr<=0) return;
   double mpu=MoneyPerUnit(g_g3sym);
   if(mpu<=0) return;
   double riskMoney=g_initBal*InpG3RiskPct/100.0;
   double lots=riskMoney/(atr*mpu);
   double step=SymbolInfoDouble(g_g3sym,SYMBOL_VOLUME_STEP);
   double vmin=SymbolInfoDouble(g_g3sym,SYMBOL_VOLUME_MIN);
   double vmax=SymbolInfoDouble(g_g3sym,SYMBOL_VOLUME_MAX);
   if(step>0) lots=MathFloor(lots/step)*step;
   lots=MathMin(lots,vmax);
   if(lots<vmin) return;
   double ask=SymbolInfoDouble(g_g3sym,SYMBOL_ASK); if(ask<=0) return;
   int dg=(int)SymbolInfoInteger(g_g3sym,SYMBOL_DIGITS);
   double sl=NormalizeDouble(ask-InpG3CatATR*atr,dg);
   trade.SetExpertMagicNumber(MagicOf(SL_G3));
   if(trade.Buy(lots,g_g3sym,0.0,sl,0.0,"G3_FOMC")){
      g_g3Entered=g_g3WinStart[w];
      if(InpVerboseLog) PrintFormat("[G3 ENTRY] LONG %s lots=%.2f SL=%.2f (窓終了=%s)",
         g_g3sym,lots,sl,TimeToString(g_g3WinEnd[w],TIME_DATE|TIME_MINUTES));
   }
}

//------------------------------------------------------------------ 指標(配列・直近確定基準)
double RsiW(const double &c[], int i, int n=14)
{
   if(i<n+2) return 50.0;
   double au=0,ad=0;
   for(int k=1;k<=i;k++){
      double d=c[k]-c[k-1]; double up=(d>0? d:0), dn=(d<0? -d:0);
      if(k==1){ au=up; ad=dn; }
      else    { au=(up+(n-1)*au)/n; ad=(dn+(n-1)*ad)/n; }
   }
   if(ad<=0) return 100.0;
   return 100.0-100.0/(1.0+au/ad);
}

//------------------------------------------------------------------ v4 スリーブ(D1新バーで判定)
void SleeveV4(double W)
{
   datetime d1=(datetime)iTime(_Symbol,PERIOD_D1,0);
   if(d1==g_lastD1) { CloseSleeve(SL_V4,"V4_TIMEOUT",0,InpV4MaxHoldDays); return; }
   g_lastD1=d1;
   CloseSleeve(SL_V4,"V4_TIMEOUT",0,InpV4MaxHoldDays);
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   for(int p=0;p<g_nv4;p++){
      string s=g_v4[p];
      if(CountSleeve(SL_V4,s)>0) continue;
      if(CountSleeve(SL_V4)>=InpV4MaxConcurrent) break;
      double c[],h[],l[];
      if(CopyClose(s,PERIOD_D1,1,40,c)<40) continue;   // [0]=最古..[39]=直近確定
      if(CopyHigh (s,PERIOD_D1,1,40,h)<40) continue;
      if(CopyLow  (s,PERIOD_D1,1,40,l)<40) continue;
      int i=39;
      double mean=0,sd=0;
      for(int k=i-20;k<i;k++) mean+=c[k]; mean/=20.0;
      for(int k=i-20;k<i;k++) sd+=(c[k]-mean)*(c[k]-mean);
      sd=MathSqrt(sd/19.0);
      double z=(sd>0? (c[i]-mean)/sd : 0.0);
      int down=0; for(int k=0;k<12 && i-k-1>=0;k++){ if(c[i-k]<c[i-k-1]) down++; else break; }
      int up=0;   for(int k=0;k<12 && i-k-1>=0;k++){ if(c[i-k]>c[i-k-1]) up++;   else break; }
      double ret=(c[i-1]>0? c[i]/c[i-1]-1.0 : 0.0);
      double rsi=RsiW(c,i,14);
      int buy =(rsi<35?1:0)+(z<-1.5?1:0)+(down>=3?1:0)+(ret<-0.005?1:0);
      int sell=(rsi>65?1:0)+(z>1.5?1:0)+(up>=3?1:0)+(ret>0.005?1:0);
      int sig=(buy>=4 && buy>sell)? 1 : ((sell>=4 && sell>buy)? -1 : 0);
      if(sig==0) continue;
      double atr=0;
      for(int k=i-13;k<=i;k++){
         double tr=MathMax(h[k]-l[k],MathMax(MathAbs(h[k]-c[k-1]),MathAbs(l[k]-c[k-1])));
         atr=(k==i-13? tr : (tr+13.0*atr)/14.0);
      }
      if(atr<=0) continue;
      double px=(sig>0? SymbolInfoDouble(s,SYMBOL_ASK):SymbolInfoDouble(s,SYMBOL_BID));
      int dg=(int)SymbolInfoInteger(s,SYMBOL_DIGITS);
      double sl=NormalizeDouble(px-sig*1.5*atr,dg);
      double tp=NormalizeDouble(px+sig*1.8*atr,dg);   // 1.2×(1.5ATR)
      OpenNotional(s,SL_V4,sig,eq*W*g_mult,sl,tp,"V4_K4");
   }
}

//------------------------------------------------------------------ 月曜スリーブ(E-Mon/E-Mon横/v7横)
void SleeveMonday(int sleeve, string &syms[], int nsym, double W, int slot)
{
   CloseSleeve(sleeve,"MON_24H",InpHoldHoursMonday*3600);
   MqlDateTime t; TimeToStruct(TimeCurrent(),t);
   if(t.day_of_week!=1) return;
   int wk=t.year*100+(t.day_of_year/7);
   if(g_monWeekKey[slot]==wk) return;
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   int done=0;
   for(int i=0;i<nsym;i++){
      if(CountSleeve(sleeve,syms[i])>0){ done++; continue; }
      if(OpenNotional(syms[i],sleeve,+1,eq*W*g_mult/nsym,0,0,
         (sleeve==SL_V7X?"V7X_MON":(sleeve==SL_EMONX?"EMONX_MON":"EMON_MON")))) done++;
   }
   if(done>=nsym) g_monWeekKey[slot]=wk;   // 全建て完了で当週終了(未約定銘柄は再試行)
}

//------------------------------------------------------------------ E5 スリーブ(月初)
void SleeveE5(double W)
{
   MqlDateTime t; TimeToStruct(TimeCurrent(),t);
   int mk=t.year*100+t.mon;
   bool firstBuild=(g_e5MonthKey!=mk);
   if(!firstBuild && !InpReenterManualClose) return;
   double sgn[8], invv[8], sumInv=0;
   for(int i=0;i<g_ne5;i++){
      sgn[i]=0; invv[i]=0;
      double c[];
      if(CopyClose(g_e5[i],PERIOD_MN1,0,16,c)<16) continue;  // [0]=最古..[15]=当月(形成中)
      int i1=14;                                             // 直近確定月
      double comp=0;
      int lbs[4]={1,3,6,12};
      for(int k=0;k<4;k++){
         int j=i1-lbs[k]; if(j<0) continue;
         double r=c[i1]/c[j]-1.0;
         comp+=(r>0?1:(r<0?-1:0));
      }
      if(comp==0) continue;
      double m=0,v=0, rets[12];
      for(int k=0;k<12;k++){ rets[k]=c[i1-k]/c[i1-k-1]-1.0; m+=rets[k]; }
      m/=12.0;
      for(int k=0;k<12;k++) v+=(rets[k]-m)*(rets[k]-m);
      double sd2=MathSqrt(v/12.0);
      if(sd2<=0) continue;
      sgn[i]=(comp>0?1:-1); invv[i]=1.0/sd2; sumInv+=invv[i];
   }
   if(sumInv<=0){ if(firstBuild) g_e5MonthKey=mk; return; }
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   int done=0, want=0;
   for(int i=0;i<g_ne5;i++){
      if(sgn[i]==0) continue;
      want++;
      if(CountSleeve(SL_E5,g_e5[i])>0){ done++; continue; }
      if(!firstBuild && !ManualCloseThisMonth(SL_E5,g_e5[i])) continue;    // 再建ては手決済後のみ
      if(OpenNotional(g_e5[i],SL_E5,(int)sgn[i],eq*W*g_mult*invv[i]/sumInv,0,0,(firstBuild?"E5_TSMOM":"E5_REENTER"))) done++;
   }
   if(firstBuild && done>=want) g_e5MonthKey=mk;
}

//------------------------------------------------------------------ S-Jul スリーブ(月初買い持ち)
void SleeveSJul(double W)
{
   MqlDateTime t; TimeToStruct(TimeCurrent(),t);
   int mk=t.year*100+t.mon;
   bool firstBuild=(g_sjulMonthKey!=mk);
   if(!firstBuild && !InpReenterManualClose) return;
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   int done=0;
   for(int i=0;i<g_nsjul;i++){
      if(CountSleeve(SL_SJUL,g_sjul[i])>0){ done++; continue; }
      if(!firstBuild && !ManualCloseThisMonth(SL_SJUL,g_sjul[i])) continue;  // 再建ては手決済後のみ
      if(OpenNotional(g_sjul[i],SL_SJUL,+1,eq*W*g_mult/g_nsjul,0,0,(firstBuild?"SJUL":"SJUL_REENTER"))) done++;
   }
   if(firstBuild && done>=g_nsjul) g_sjulMonthKey=mk;
}

//------------------------------------------------------------------
void OnTimer()
{
   FlushNotify();   // 前タイマー分の未送信(早期return経路)を送出
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);

   // スワップ実測ログ(docs/100 §4): ガードとは独立に日次1回+月替わりで集計
   if(InpSwapLogEnable){
      MqlDateTime ts0; TimeToStruct(TimeCurrent(),ts0);
      int swDk=ts0.year*1000+ts0.day_of_year;
      static int s_swapDayKey=-1;
      if(swDk!=s_swapDayKey){
         s_swapDayKey=swDk;
         if(g_gvName!="") GlobalVariableSet(g_gvName,g_initBal);  // 4週失効対策の日次タッチ
         SwapLogDailySnapshot();
         int mk=ts0.year*100+ts0.mon;
         if(g_swapMonKey!=-1 && mk!=g_swapMonKey) SwapLogMonthlySummary(g_swapMonKey/100,g_swapMonKey%100);
         g_swapMonKey=mk;
      }
   }

   // フロア(恒久停止)
   if(eq<=g_initBal*(1.0-InpAccountFloorDDPct/100.0) && !g_halted){
      g_halted=true; CloseAllMine("FLOOR");
      PrintFormat("[HALT] equity %.2f <= floor",eq);
      Notify(StringFormat("FLOOR -%.1f%% 全決済・恒久停止",InpAccountFloorDDPct)); FlushNotify();
   }
   if(g_halted){ CloseAllMine("HALTED"); return; }

   // +7%利益ロック(docs/100): Arm=新規停止(水準判定) / Close=全決済し恒久ロック。
   // ⚠正直な注記: +LockClose%での全決済が確定するのは実現≈+LockClose%(スリッページ下振れあり)。
   //   フェーズ目標(+8%等)より低く設定した場合、残差は縮小サイズ再稼働か手動で確定する(docs/100)。
   if(InpProfitLockEnable && g_initBal>0){
      double gainPct=(eq-g_initBal)/g_initBal*100.0;
      if(!g_lockDone && gainPct>=InpLockClosePct){
         g_lockDone=true; CloseAllMine("PROFIT_LOCK");
         PrintFormat("[PROFIT LOCK] equity %+.2f%% >= +%.2f%% → 全決済・恒久ロック(再開はEA再アタッチ)",gainPct,InpLockClosePct);
         Notify(StringFormat("PASS_LOCK %+.2f%% 全決済(通過確定処理)",gainPct));
      }
      bool armNow=(!g_lockDone && gainPct>=InpLockArmPct);
      if(armNow!=g_lockArmed){
         g_lockArmed=armNow;
         PrintFormat("[PROFIT LOCK %s] equity %+.2f%% (arm=+%.1f%%)",(armNow?"ARMED=新規停止":"DISARM=新規再開"),gainPct,InpLockArmPct);
         if(armNow && !g_ntfArm){ g_ntfArm=true; Notify(StringFormat("ARM %+.2f%% 新規停止(手決済参考: +%.1f%%で全決済)",gainPct,InpLockClosePct)); }
         if(!armNow) g_ntfArm=false;
      }
      // 手決済の参考値ライン(既定+6%): 到達で1回通知、-0.5%離れたら再武装
      if(!g_ntfRef && gainPct>=InpNotifyRefPct && InpNotifyRefPct>0){
         g_ntfRef=true;
         Notify(StringFormat("参考値到達 %+.2f%% (ARM=+%.1f%%/LOCK=+%.1f%%が自動処理)",gainPct,InpLockArmPct,InpLockClosePct));
      }else if(g_ntfRef && gainPct<InpNotifyRefPct-0.5) g_ntfRef=false;
      Comment(StringFormat("Chien_Seasonal | gain %+.2f%% | open-risk %.2f%%(cap %.1f%% %s) | %s",gainPct,
             OpenRiskPct(),InpMaxOpenRiskPct,
             (InpRiskGuardMode==RG_ENFORCE?"ENF":(InpRiskGuardMode==RG_MONITOR?"MON":"OFF")),
             (g_lockDone?"PASS_LOCK(全決済済)":(g_lockArmed?"ARMED(新規停止)":"active"))));
   }
   if(g_lockDone){ CloseAllMine("PROFIT_LOCK"); return; }

   // 日次ガード
   MqlDateTime t; TimeToStruct(TimeCurrent(),t);
   int dk=t.year*1000+t.day_of_year;
   if(dk!=g_dayKey){ g_dayKey=dk; g_dayStartEq=eq; g_dayHalt=false; }
   // 日次の警告ライン(既定-3%・ガード-4%の手前で1日1回)
   if(InpNotifyDayWarnPct>0 && g_ntfDayKey!=dk && g_dayStartEq>0
      && eq<=g_dayStartEq*(1.0-InpNotifyDayWarnPct/100.0)){
      g_ntfDayKey=dk;
      Notify(StringFormat("日次-%.1f%%警告(ガード-%.1f%%手前) eq=%.0f",InpNotifyDayWarnPct,InpDailyStopPct,eq)); FlushNotify();
   }
   if(!g_dayHalt && eq<=g_dayStartEq*(1.0-InpDailyStopPct/100.0)){
      g_dayHalt=true; CloseAllMine("DAILY_STOP");
      PrintFormat("[DAILY HALT] %.2f%%",InpDailyStopPct);
      Notify(StringFormat("DAILY_STOP -%.1f%% 当日停止・全決済",InpDailyStopPct)); FlushNotify();
   }
   if(g_dayHalt) return;

   // G3 FOMCオーバーレイ(イベント建玉・月ゲートと独立。ガードの対象)
   SleeveG3();
   // 利幅通知(スリーブ別・過去分布比較, docs/112 §5)
   CheckWidthNotify();

   // 通年シナリオ: 月替わりで全決済→当月の構成へ自動切替(挿しっぱなしで12ヶ月回る)
   if(InpScenario==SCN_YEARROUND_05 || InpScenario==SCN_YEARROUND_M3){
      if(t.mon!=g_curMonth){ g_rollPending=true; g_curMonth=t.mon; }
      if(g_rollPending){                       // 休場中(土曜の月替わり等)は決済失敗→完了まで毎タイマー再試行
         CloseAllMonthly("MONTH_ROLL");
         if(MonthlyOpenCount()>0) return;      // 全決済が終わるまで新しい月の構成へ進まない
         g_rollPending=false;
      }
      int m=t.mon;
      if(WY_V4[m]>0.0)    SleeveV4(WY_V4[m]);
      if(WY_E5[m]>0.0)    SleeveE5(WY_E5[m]);
      if(WY_EMON[m]>0.0)  SleeveMonday(SL_EMON, g_emon, g_nemon, WY_EMON[m], 0);
      if(WY_EMONX[m]>0.0) SleeveMonday(SL_EMONX,g_emonx,g_nemonx,WY_EMONX[m],1);
      if(WY_V7X[m]>0.0)   SleeveMonday(SL_V7X,  g_v7x,  g_nv7x,  WY_V7X[m],  2);
      if(WY_V7[m]>0.0)    SleeveMonday(SL_V7,   g_v7,   g_nv7,   WY_V7[m],   3);
      if(WY_SJUL[m]>0.0)  SleeveSJul(WY_SJUL[m]);
      return;
   }
   // 通年シナリオ(R4: リスク調整比例, docs/110)
   if(InpScenario==SCN_YEARROUND_R4){
      if(t.mon!=g_curMonth){ g_rollPending=true; g_curMonth=t.mon; }
      if(g_rollPending){                       // 休場中(土曜の月替わり等)は決済失敗→完了まで毎タイマー再試行
         CloseAllMonthly("MONTH_ROLL");
         if(MonthlyOpenCount()>0) return;      // 全決済が終わるまで新しい月の構成へ進まない
         g_rollPending=false;
      }
      int m=t.mon;
      if(WR4_V4[m]>0.0)    SleeveV4(WR4_V4[m]);
      if(WR4_E5[m]>0.0)    SleeveE5(WR4_E5[m]);
      if(WR4_EMON[m]>0.0)  SleeveMonday(SL_EMON, g_emon, g_nemon, WR4_EMON[m], 0);
      if(WR4_EMONX[m]>0.0) SleeveMonday(SL_EMONX,g_emonx,g_nemonx,WR4_EMONX[m],1);
      if(WR4_V7X[m]>0.0)   SleeveMonday(SL_V7X,  g_v7x,  g_nv7x,  WR4_V7X[m],  2);
      if(WR4_V7[m]>0.0)    SleeveMonday(SL_V7,   g_v7,   g_nv7,   WR4_V7[m],   3);
      if(WR4_SJUL[m]>0.0)  SleeveSJul(WR4_SJUL[m]);
      return;
   }

   // 単月シナリオの月ゲート: 対象月以外は全決済して待機
   if(t.mon!=g_month){ CloseAllMonthly("MONTH_GATE"); return; }

   if(InpScenario==SCN_JUNE_TOP5){
      SleeveV4(0.414);
      SleeveE5(0.219);
      SleeveMonday(SL_EMON, g_emon, g_nemon, 0.160, 0);
      SleeveMonday(SL_EMONX,g_emonx,g_nemonx,0.133, 1);
      SleeveMonday(SL_V7X,  g_v7x,  g_nv7x,  0.074, 2);
   }else if(InpScenario==SCN_JULY_TOP2){
      SleeveSJul(0.685);
      SleeveE5(0.315);
   }else{ // SCN_AUG_V4ONLY: 8月ランキング1位のv4を100%(倍率0.4x)
      SleeveV4(1.0);
   }
}
void OnTick(){ /* 主処理はOnTimer(60s) */ }
//+------------------------------------------------------------------+
//| 残存リスク(誠実な記録):                                          |
//|  ・月別配分は10年の記述統計(in-sample重み)。フォワードの目的は     |
//|    「分布内か」の確認でありこの月利の保証ではない(docs/87)。       |
//|  ・横展開4クロス/3指数はEA実装・約定実績ゼロ→デモで要確認。        |
//|  ・v4はSL/TP到達を足内で判定する実装(バックテストはD1高安)。       |
//|    月末跨ぎのv4建玉は月ゲートで強制決済(検証との小差・保守側)。    |
//|  ・サーバ時刻基準で月曜/月初を判定(UTCとのズレは数時間・影響小)。  |
//|  ・指数の取引時間外は約定失敗→次のタイマーで再試行する設計。       |
//|  ・gross露出は6月版で最大≈200%+v4重複分。証拠金率の低い業者では    |
//|    InpV4MaxConcurrentを下げる。                                    |
//+------------------------------------------------------------------+
