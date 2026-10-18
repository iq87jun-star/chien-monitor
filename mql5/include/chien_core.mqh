//+------------------------------------------------------------------+
//| chien_core.mqh 1.0 — docs/322 Q95(docs/363): RecentFit 系 EA の共通コア       |
//| 10 本の配備 EA(EA3 v1.19・EA8 v1.37・EA9 v1.04・EA10L v1.05・EA11 v1.15・パール v1.10・B 案 v1.04・FN v1.35・14074882 v1.11・Instant G v1.16)で本体が完全一致する 28 関数(ChienLog は 2 つの多重定義)を EA3 v1.19 の原文のまま収めた。 |
//| 使い方: EA の input・グローバル(Inp*・g_*)の宣言の後に  #include "chien_core.mqh"  を置く(同じフォルダ MQL5\Experts\chien\ に置く)。 |
//| 依存: EA 側に ResolveSymbol / MoneyPerUnit / PipOf / IsMine / ResetDay / FlushNotify(EA ごとに異なる 13 関数)が必要。 |
//| 規則: ここを変えるときは Q94 のテスター(tester_parity.py)で「現行版と取引一致」を確認してから配備候補にする。 |
//+------------------------------------------------------------------+
#ifndef CHIEN_CORE_MQH
#define CHIEN_CORE_MQH
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

void CloseAllMine(string why){
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(!posinfo.SelectByTicket(tk)) continue;
      if(IsMine(posinfo.Magic())) trade.PositionClose(tk); }
   if(InpVerboseLog) ChienLog(StringFormat("[CLOSE ALL %s]",why));
}

void Notify(string s){ if(!InpNotifyEnable) return; if(g_ntfBuf!="") g_ntfBuf+=" | "; g_ntfBuf+=s; }

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

datetime DayStart(datetime t){ MqlDateTime s; TimeToStruct(t,s); s.hour=0;s.min=0;s.sec=0; return StructToTime(s); }

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

void V4Fail(int i, datetime db, string why)
{
   g_v4Tries[i]++;                                   // 30秒タイマーで再試行(最大120回≈1時間)
   if(g_v4Tries[i]>=120){
      ChienLog(StringFormat("[v4 GIVEUP] %s %s %d回失敗→当バー断念",g_v4Sym[i],why,g_v4Tries[i]));
      g_lastV4Bar[i]=db; g_v4Tries[i]=0;
   }
}
#endif // CHIEN_CORE_MQH
