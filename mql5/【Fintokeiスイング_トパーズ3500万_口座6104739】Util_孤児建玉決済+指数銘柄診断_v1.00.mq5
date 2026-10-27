//+------------------------------------------------------------------+
//| ★Fintokei トパーズ 3,500万(口座 6104739)補助 EA Util v1.00(2026-10-28・docs/241 §1af)                                   |
//|   取引ロジック無し。2 つの一回限りの仕事を自動で行う(ユーザー 10/28「1 は自動で確認」「2 は設置 EA のエントリー外なら決済」)。|
//|   1) 指数銘柄の診断: 端末の全銘柄から Nasdaq / S&P 系の名称を列挙し、別名候補の解決可否・スプレッド(bps)・取引可否を    |
//|      [銘柄解決] 行でログに出す(毎時エージェントが拾う)。EA11 v1.18 の InpMonLegs / 別名表 / スプレッド上限の根拠にする。  |
//|   2) 孤児建玉の決済: 設置 EA(v1.17・Magic 943621)の管理外にある Magic(既定 943623 = v1.10 の Hold UK100p / USOILp)の     |
//|      建玉だけを成行で決済する。他の Magic・手動建玉には触れない。決済後は何もしない(付けたままで無害)。                   |
//|   本 EA は v1.17 と同じ端末の別チャートに付ける(manifest ensure の 2 本目)。                                                |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.00"
#property strict
#property description "[Util Topaz v1.00] no trading logic: (1) index symbol diagnostics to log, (2) close orphan positions by magic list (default 943623)"

#include <Trade/Trade.mqh>

input string InpCloseMagics   = "943623";   // 決済する建玉の Magic(カンマ区切り)。設置 EA の管理外のものだけ
input bool   InpCloseEnable   = true;       // true: 該当 Magic の建玉を成行で決済(一回限り・以後は監視のみ)
input string InpDiagKeys      = "NAS,NDX,TEC,100,US5,SPX,500,SP5";   // 全銘柄から名称にこれを含むものを列挙(大文字比較)
input string InpDiagCands     = "NAS100,USTEC,US100,NDX100,NDX,USATECH,US_TECH100,TECH100,NASDAQ,NAS,USTECH,NSDQ,US500,SPX500,SP500,US_500,SPX";  // 別名候補
input string InpDiagSuffixes  = ",p,.p,_p,.cash,Cash,.i,m,.m,.raw";  // 候補に付ける接尾辞
input int    InpDiagMaxLines  = 80;         // 列挙の上限行数
input int    InpTimerSec      = 60;         // 監視周期(秒)

CTrade  trade;
long    g_magics[];
bool    g_closedAll = false;
datetime g_lastHourly = 0;

void ULog(string s){ Print(s); }

int ParseMagics(string csv){
   string parts[]; int n = StringSplit(csv, ',', parts); int k = 0; ArrayResize(g_magics, 0);
   for(int i = 0; i < n; i++){ string t = parts[i]; StringTrimLeft(t); StringTrimRight(t); if(StringLen(t) == 0) continue; ArrayResize(g_magics, k + 1); g_magics[k++] = (long)StringToInteger(t); }
   return k;
}
bool IsTarget(long magic){ for(int i = 0; i < ArraySize(g_magics); i++) if(g_magics[i] == magic) return true; return false; }

double SpreadBps(string sym){
   double bid = SymbolInfoDouble(sym, SYMBOL_BID), ask = SymbolInfoDouble(sym, SYMBOL_ASK);
   if(bid <= 0) return -1.0; return (ask - bid) / bid * 10000.0;
}
string SymLine(string sym){
   int dg = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS); double pt = SymbolInfoDouble(sym, SYMBOL_POINT);
   long spr = SymbolInfoInteger(sym, SYMBOL_SPREAD); long tm = SymbolInfoInteger(sym, SYMBOL_TRADE_MODE);
   double bid = SymbolInfoDouble(sym, SYMBOL_BID);
   return StringFormat("%s digits=%d point=%g spread=%dpt(%.2fbps・pip換算%.1f) bid=%g trade_mode=%d desc='%s'", sym, dg, pt, (int)spr, SpreadBps(sym),
          (dg == 3 || dg == 5) ? spr / 10.0 : (double)spr, bid, (int)tm, SymbolInfoString(sym, SYMBOL_DESCRIPTION));
}
bool HasKey(string U, string keysCsv){
   string ks[]; int n = StringSplit(keysCsv, ',', ks);
   for(int i = 0; i < n; i++){ string k = ks[i]; StringTrimLeft(k); StringTrimRight(k); StringToUpper(k); if(StringLen(k) > 0 && StringFind(U, k) >= 0) return true; }
   return false;
}
void Diagnose(){
   int total = SymbolsTotal(false), lines = 0;
   ULog(StringFormat("[INIT Util v1.00] 銘柄診断開始: 全銘柄 %d・気配値表示 %d・キー='%s'", total, SymbolsTotal(true), InpDiagKeys));
   for(int i = 0; i < total && lines < InpDiagMaxLines; i++){
      string nm = SymbolName(i, false); string U = nm; StringToUpper(U);
      if(!HasKey(U, InpDiagKeys)) continue;
      SymbolSelect(nm, true); lines++;
      ULog("[銘柄解決] Util 列挙: " + SymLine(nm));
   }
   string cands[]; int nc = StringSplit(InpDiagCands, ',', cands); string sufs[]; int ns = StringSplit(InpDiagSuffixes, ',', sufs);
   for(int c = 0; c < nc; c++){
      string base = cands[c]; StringTrimLeft(base); StringTrimRight(base); if(StringLen(base) == 0) continue;
      string found = "";
      for(int s = 0; s < ns; s++){ string cand = base + sufs[s]; if(SymbolSelect(cand, true)){ found = cand; break; } }
      if(found != "") ULog(StringFormat("[銘柄解決] Util 候補 %s → '%s' あり: %s", base, found, SymLine(found)));
      else ULog(StringFormat("[銘柄解決] Util 候補 %s → 解決できず(接尾辞 %s)", base, InpDiagSuffixes));
   }
   ULog(StringFormat("[INIT Util v1.00] 銘柄診断終了(列挙 %d 行)", lines));
}
void HourlySpread(){
   string s = "[銘柄解決] Util 毎時スプレッド:";
   string cands[]; int nc = StringSplit(InpDiagCands, ',', cands); string sufs[]; int ns = StringSplit(InpDiagSuffixes, ',', sufs); int k = 0;
   for(int c = 0; c < nc && k < 6; c++){
      string base = cands[c]; StringTrimLeft(base); StringTrimRight(base);
      for(int sx = 0; sx < ns; sx++){ string cand = base + sufs[sx]; if(SymbolSelect(cand, true)){ s += StringFormat(" %s %.2fbps", cand, SpreadBps(cand)); k++; break; } }
   }
   ULog(s);
}
int CloseOrphans(){
   int closed = 0, remain = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--){
      ulong tk = PositionGetTicket(i); if(tk == 0 || !PositionSelectByTicket(tk)) continue;
      long mg = PositionGetInteger(POSITION_MAGIC); if(!IsTarget(mg)) continue;
      string sym = PositionGetString(POSITION_SYMBOL); double vol = PositionGetDouble(POSITION_VOLUME), pf = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      if(!InpCloseEnable){ remain++; ULog(StringFormat("[CLOSE ALL Util] 対象あり(決済無効): #%I64u %s %.2f magic=%I64d 損益=%.0f", tk, sym, vol, mg, pf)); continue; }
      if(trade.PositionClose(tk)){ closed++; ULog(StringFormat("[CLOSE ALL Util] 孤児建玉を決済: #%I64u %s %.2f magic=%I64d 損益=%.0f ret=%d", tk, sym, vol, mg, pf, (int)trade.ResultRetcode())); }
      else { remain++; ULog(StringFormat("[CLOSE ALL Util] 決済失敗(次回再試行): #%I64u %s %.2f magic=%I64d ret=%d %s", tk, sym, vol, mg, (int)trade.ResultRetcode(), trade.ResultRetcodeDescription())); }
   }
   if(closed > 0 || remain > 0) ULog(StringFormat("[CLOSE ALL Util] 決済 %d 本・残 %d 本", closed, remain));
   return remain;
}
int OnInit(){
   int n = ParseMagics(InpCloseMagics);
   trade.SetAsyncMode(false); trade.SetDeviationInPoints(50);
   ULog(StringFormat("[INIT Util v1.00] 取引ロジック無し。孤児 Magic=%s(%d 個)決済=%s 周期=%ds 口座=%I64d equity=%.0f", InpCloseMagics, n, InpCloseEnable ? "有効" : "無効", InpTimerSec, AccountInfoInteger(ACCOUNT_LOGIN), AccountInfoDouble(ACCOUNT_EQUITY)));
   Diagnose();
   EventSetTimer(MathMax(10, InpTimerSec));
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){ EventKillTimer(); }
void OnTimer(){
   if(!TerminalInfoInteger(TERMINAL_CONNECTED)) return;
   if(!g_closedAll){
      if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED)){ if(TimeCurrent() - g_lastHourly > 3600){ ULog("[CLOSE ALL Util] 自動売買が許可されていないため待機"); g_lastHourly = TimeCurrent(); } return; }
      int remain = CloseOrphans();
      if(remain == 0){ g_closedAll = true; ULog("[CLOSE ALL Util] 対象の孤児建玉なし(完了)。以後は毎時のスプレッド記録のみ"); }
   }
   datetime now = TimeCurrent(); MqlDateTime dt; TimeToStruct(now, dt);
   if(dt.min >= 5 && now - g_lastHourly >= 3500){ g_lastHourly = now; HourlySpread(); }
}
void OnTick(){}
