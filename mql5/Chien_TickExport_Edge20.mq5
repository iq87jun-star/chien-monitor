//+------------------------------------------------------------------+
//|                                  Chien_TickExport_Edge20.mq5     |
//|  edge20(docs/108改訂): ブローカー実データのエクスポート v1.10       |
//|                                                                   |
//|  v1.10: ①CopyTicksRangeにリトライ+エラーコード診断を追加           |
//|         ②ティック不可なら自動でM1バー(スプレッド列付き)へフォール    |
//|           バック(履歴が深く、H20a/b/cの採点に十分)                  |
//|                                                                   |
//|  使い方: コンパイル → ナビゲータ「スクリプト」からチャートへドラッグ |
//|  出力: MQL5/Files/ChienTicksM1_<PAIR>.csv (ティック1分集約)         |
//|     or MQL5/Files/ChienRatesM1_<PAIR>.csv (M1バー・フォールバック)  |
//|  → できたCSV(3ペア分)をzipしてチャットにアップロード                |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.10"
#property script_show_inputs
#property strict

input string InpSymbols     = "EURJPY,GBPJPY,USDJPY";
input int    InpMaxDaysBack = 1200;   // 最大遡り日数(履歴が尽きれば自動終了)
input int    InpHourFrom    = 4;      // サーバー時刻 この時から
input int    InpHourTo      = 16;     // サーバー時刻 この時まで(含む)
input int    InpEmptyStop   = 30;     // 対象日がこれだけ連続無データなら終了

int SplitCSV(string csv, string &arr[])
{
   string p[]; int k=StringSplit(csv,',',p); int m=0; ArrayResize(arr,k);
   for(int i=0;i<k;i++){ string s=p[i]; StringTrimLeft(s); StringTrimRight(s);
      if(StringLen(s)>0){ arr[m]=s; m++; } }
   ArrayResize(arr,m); return m;
}
string ResolveSymbol(string want)
{
   string suf[]={"",".pi",".raw",".ecn",".stp",".pro",".r",".c",".m","m","+",".i",".a"};
   for(int s=0;s<ArraySize(suf);s++){ string c=want+suf[s]; if(SymbolSelect(c,true)) return c; }
   return "";
}

// ティック取得(リトライ付き)。戻り: >0=件数 / 0=本当に無し / -1=取得不能
int CopyTicksRetry(string sym, MqlTick &ticks[], ulong fromMs, ulong toMs, int tries=6)
{
   int lastErr=0;
   for(int a=0;a<tries;a++){
      ResetLastError();
      int n=CopyTicksRange(sym,ticks,COPY_TICKS_INFO,fromMs,toMs);
      if(n>0) return n;
      lastErr=GetLastError();
      if(n==0 && lastErr==0) return 0;      // データなし(正常)
      Sleep(1500);                          // 履歴ダウンロード待ち→再試行
   }
   PrintFormat("   (tick取得不能 err=%d)",lastErr);
   return -1;
}

// ---- モードA: ティック1分集約 ----
bool ExportTicks(string sym, string base, double pip)
{
   string fn=StringFormat("ChienTicksM1_%s.csv",base);
   int h=FileOpen(fn,FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(h==INVALID_HANDLE) return false;
   FileWriteString(h,"time_server,bid_avg,ask_avg,spread_pips_avg,spread_pips_max,n_ticks\n");
   MqlDateTime t0; TimeToStruct(TimeCurrent(),t0); t0.hour=0;t0.min=0;t0.sec=0;
   datetime today=StructToTime(t0);
   int emptyStreak=0, daysOut=0; long rows=0; datetime oldest=TimeCurrent();
   for(int d=0; d<InpMaxDaysBack && emptyStreak<InpEmptyStop && !IsStopped(); d++){
      datetime day0=today-(datetime)d*86400;
      MqlDateTime st; TimeToStruct(day0,st);
      if(st.day_of_week!=1 && st.day_of_week!=2) continue;
      bool any=false;
      for(int hh=InpHourFrom; hh<=InpHourTo; hh++){
         ulong fromMs=(ulong)(day0+hh*3600)*1000, toMs=fromMs+3600*1000-1;
         MqlTick ticks[];
         int n=CopyTicksRetry(sym,ticks,fromMs,toMs);
         if(n<=0) continue;
         any=true;
         double sb=0,sa=0,sspr=0,mspr=0; int cnt=0; int curMin=-1; datetime curT=0;
         for(int i=0;i<n;i++){
            if(ticks[i].bid<=0 || ticks[i].ask<=0) continue;
            datetime tt=(datetime)(ticks[i].time_msc/1000);
            int mi=(int)((tt-day0)/60);
            if(mi!=curMin && cnt>0){
               FileWriteString(h,StringFormat("%s,%.5f,%.5f,%.3f,%.3f,%d\n",
                  TimeToString(curT,TIME_DATE|TIME_MINUTES),sb/cnt,sa/cnt,sspr/cnt/pip,mspr/pip,cnt));
               rows++; sb=0;sa=0;sspr=0;mspr=0;cnt=0;
            }
            if(mi!=curMin){ curMin=mi; curT=day0+(datetime)mi*60; }
            double spr=ticks[i].ask-ticks[i].bid;
            sb+=ticks[i].bid; sa+=ticks[i].ask; sspr+=spr; if(spr>mspr) mspr=spr; cnt++;
         }
         if(cnt>0){
            FileWriteString(h,StringFormat("%s,%.5f,%.5f,%.3f,%.3f,%d\n",
               TimeToString(curT,TIME_DATE|TIME_MINUTES),sb/cnt,sa/cnt,sspr/cnt/pip,mspr/pip,cnt));
            rows++;
         }
      }
      if(any){ emptyStreak=0; daysOut++; if(day0<oldest) oldest=day0;
         if(daysOut<=3 || daysOut%20==0)
            PrintFormat("[%s TICK] %s 取得済み(累計%d日・%d行)",base,TimeToString(day0,TIME_DATE),daysOut,(int)rows); }
      else emptyStreak++;
   }
   FileClose(h);
   PrintFormat("[%s TICK] 完了: %d日・%d行(最古=%s)→ %s",base,daysOut,(int)rows,TimeToString(oldest,TIME_DATE),fn);
   return (rows>0);
}

// ---- モードB: M1バー(スプレッド列)フォールバック ----
void ExportRates(string sym, string base, double pip)
{
   double point=SymbolInfoDouble(sym,SYMBOL_POINT);
   string fn=StringFormat("ChienRatesM1_%s.csv",base);
   int h=FileOpen(fn,FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(h==INVALID_HANDLE) return;
   FileWriteString(h,"time_server,open_bid,close_bid,spread_pips_open\n");
   MqlDateTime t0; TimeToStruct(TimeCurrent(),t0); t0.hour=0;t0.min=0;t0.sec=0;
   datetime today=StructToTime(t0);
   int emptyStreak=0, daysOut=0; long rows=0; datetime oldest=TimeCurrent();
   for(int d=0; d<InpMaxDaysBack && emptyStreak<InpEmptyStop && !IsStopped(); d++){
      datetime day0=today-(datetime)d*86400;
      MqlDateTime st; TimeToStruct(day0,st);
      if(st.day_of_week!=1 && st.day_of_week!=2) continue;
      datetime from=day0+InpHourFrom*3600, to=day0+(InpHourTo+1)*3600-60;
      MqlRates r[]; int n=-1;
      for(int a=0;a<6;a++){ ResetLastError();
         n=CopyRates(sym,PERIOD_M1,from,to,r);
         if(n>0) break; Sleep(1500); }
      if(n<=0){ emptyStreak++; continue; }
      for(int i=0;i<n;i++)
         { FileWriteString(h,StringFormat("%s,%.5f,%.5f,%.3f\n",
              TimeToString(r[i].time,TIME_DATE|TIME_MINUTES),r[i].open,r[i].close,
              r[i].spread*point/pip)); rows++; }
      emptyStreak=0; daysOut++; if(day0<oldest) oldest=day0;
      if(daysOut<=3 || daysOut%40==0)
         PrintFormat("[%s M1] %s 取得済み(累計%d日・%d行)",base,TimeToString(day0,TIME_DATE),daysOut,(int)rows);
   }
   FileClose(h);
   PrintFormat("[%s M1] 完了: %d日・%d行(最古=%s)→ %s",base,daysOut,(int)rows,TimeToString(oldest,TIME_DATE),fn);
}

void OnStart()
{
   string syms[]; int ns=SplitCSV(InpSymbols,syms);
   PrintFormat("[TickExport v1.10] GMTオフセット(現在): サーバー%+d秒",(int)(TimeCurrent()-TimeGMT()));

   for(int si=0; si<ns; si++){
      string sym=ResolveSymbol(syms[si]);
      if(sym==""){ PrintFormat("⚠ %s 解決不可→スキップ",syms[si]); continue; }
      double pip=(StringFind(sym,"JPY")>=0? 0.01: 0.0001);

      // 直近の火曜10時(サーバー)でティック取得を診断
      MqlDateTime t0; TimeToStruct(TimeCurrent(),t0); t0.hour=0;t0.min=0;t0.sec=0;
      datetime day=StructToTime(t0);
      while(true){ MqlDateTime st; TimeToStruct(day,st); if(st.day_of_week==2) break; day-=86400; }
      MqlTick probe[];
      int pn=CopyTicksRetry(sym,probe,(ulong)(day+10*3600)*1000,(ulong)(day+11*3600)*1000-1,8);
      PrintFormat("[%s 診断] 直近火曜(%s)10時台 tick=%d → %s",
         syms[si],TimeToString(day,TIME_DATE),pn,(pn>0?"ティックモード":"M1バーモードへフォールバック"));

      if(pn>0){ if(!ExportTicks(sym,syms[si],pip)) ExportRates(sym,syms[si],pip); }
      else      ExportRates(sym,syms[si],pip);
   }
   Print("[TickExport] 全完了。MQL5/Files の ChienTicksM1_*.csv または ChienRatesM1_*.csv をzipにしてチャットへアップロードしてください。");
}
//+------------------------------------------------------------------+
