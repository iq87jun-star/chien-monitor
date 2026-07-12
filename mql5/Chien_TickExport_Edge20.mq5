//+------------------------------------------------------------------+
//|                                  Chien_TickExport_Edge20.mq5     |
//|  edge20/24: 執行データエクスポート v1.40(ティック→M1再構築)          |
//|                                                                   |
//|  v1.20: 位置ベースCopyRates・環境診断                               |
//|  v1.30: high/low列を追加(指値約定シミュレーションに必須)             |
//|  v1.40(docs/149 §6): M1保持が約3ヶ月しかない問題への対策として、     |
//|    CopyTicksRangeで【ティック履歴】から月・火曜のM1を再構築          |
//|    (edge20実績: EURJPYはティックで2.5年遡れた)。週単位で遡行し        |
//|    8週連続空振りで履歴終端と判断。                                   |
//|                                                                   |
//|  使い方: コンパイル → ナビゲータ「スクリプト」からチャートへドラッグ |
//|  出力: MQL5/Files/ChienRatesM1v2_<PAIR>.csv                        |
//|  → 3ペア分をzipしてチャットにアップロード(数分〜十数分かかります)    |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.40"
#property script_show_inputs
#property strict

input string InpSymbols   = "EURJPY,GBPJPY,USDJPY";
input int    InpMaxBars   = 800000;  // (v1.40では未使用・互換のため残置)
input int    InpHourFrom  = 4;       // サーバー時刻 この時から
input int    InpHourTo    = 16;      // サーバー時刻 この時まで(含む)
input int    InpMaxWeeks  = 160;     // 遡る週数の上限(≈3年。ティック履歴が尽きれば自動終了)

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

void OnStart()
{
   PrintFormat("[Export v1.20 診断] TimeCurrent=%s TimeGMT=%s (サーバーGMTオフセット%+d秒) 端末MaxBars=%d",
      TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS),TimeToString(TimeGMT(),TIME_DATE|TIME_SECONDS),
      (int)(TimeCurrent()-TimeGMT()),(int)TerminalInfoInteger(TERMINAL_MAXBARS));

   string syms[]; int ns=SplitCSV(InpSymbols,syms);
   for(int si=0; si<ns && !IsStopped(); si++){
      string sym=ResolveSymbol(syms[si]);
      if(sym==""){ PrintFormat("⚠ %s 解決不可→スキップ",syms[si]); continue; }
      double pip=(StringFind(sym,"JPY")>=0? 0.01: 0.0001);
      double point=SymbolInfoDouble(sym,SYMBOL_POINT);

      string fn=StringFormat("ChienRatesM1v2_%s.csv",syms[si]);
      int h=FileOpen(fn,FILE_WRITE|FILE_TXT|FILE_ANSI);
      if(h==INVALID_HANDLE){ PrintFormat("⚠ %s: ファイル作成失敗 err=%d",fn,GetLastError()); continue; }
      FileWriteString(h,"time_server,open_bid,high_bid,low_bid,close_bid,spread_pips_open\n");

      // v1.40: ティック履歴から月・火曜のM1を再構築(週単位で遡行・8週連続空で終端判定)
      datetime nowSrv=TimeCurrent();
      datetime day0=nowSrv-(nowSrv%86400);
      MqlDateTime nt; TimeToStruct(day0,nt);
      datetime lastMon=day0-((nt.day_of_week+6)%7)*86400;   // 直近の月曜00:00(サーバー)
      long rows=0; datetime oldest=0,newest=0; int emptyWeeks=0;
      for(int w=0; w<InpMaxWeeks && !IsStopped(); w++){
         bool weekHas=false;
         for(int d=0; d<2; d++){                            // 月曜(d=0)・火曜(d=1)
            datetime dayS=lastMon-(datetime)w*604800+(datetime)d*86400;
            ulong fromMs=(ulong)(dayS+(datetime)InpHourFrom*3600)*1000;
            ulong toMs  =(ulong)(dayS+(datetime)(InpHourTo+1)*3600)*1000;
            MqlTick tk[]; int n=-1;
            for(int a=0;a<4;a++){ ResetLastError();
               n=CopyTicksRange(sym,tk,COPY_TICKS_INFO,fromMs,toMs);
               if(n>=0) break; Sleep(1200); }
            if(n<=0) continue;
            weekHas=true;
            // 分単位に集約(bid OHLC+先頭スプレッド)
            datetime curMin=0; double o=0,hi=0,lo=0,cl=0,sp0=0;
            for(int i=0;i<n;i++){
               if(tk[i].bid<=0||tk[i].ask<=0) continue;
               datetime m=tk[i].time-(tk[i].time%60);
               if(m!=curMin){
                  if(curMin>0){
                     FileWriteString(h,StringFormat("%s,%.5f,%.5f,%.5f,%.5f,%.3f\n",
                        TimeToString(curMin,TIME_DATE|TIME_MINUTES),o,hi,lo,cl,sp0));
                     rows++;
                     if(oldest==0||curMin<oldest) oldest=curMin;
                     if(curMin>newest) newest=curMin;
                  }
                  curMin=m; o=tk[i].bid; hi=tk[i].bid; lo=tk[i].bid; sp0=(tk[i].ask-tk[i].bid)/pip;
               }
               cl=tk[i].bid;
               if(tk[i].bid>hi) hi=tk[i].bid;
               if(tk[i].bid<lo) lo=tk[i].bid;
            }
            if(curMin>0){
               FileWriteString(h,StringFormat("%s,%.5f,%.5f,%.5f,%.5f,%.3f\n",
                  TimeToString(curMin,TIME_DATE|TIME_MINUTES),o,hi,lo,cl,sp0));
               rows++;
               if(oldest==0||curMin<oldest) oldest=curMin;
               if(curMin>newest) newest=curMin;
            }
         }
         if(weekHas) emptyWeeks=0; else emptyWeeks++;
         if(emptyWeeks>=8){ PrintFormat("[%s] %d週目で8週連続空=ティック履歴終端",syms[si],w); break; }
         if(w%26==0) PrintFormat("[%s] %d週遡行済み(採用%d行・最古=%s)",syms[si],w,(int)rows,
            (oldest>0?TimeToString(oldest,TIME_DATE):"-"));
      }
      FileClose(h);
      PrintFormat("[%s] 完了: %d行(期間 %s 〜 %s)→ MQL5/Files/%s",
         syms[si],(int)rows,(oldest>0?TimeToString(oldest,TIME_DATE):"-"),
         (newest>0?TimeToString(newest,TIME_DATE):"-"),fn);
   }
   Print("[Export] 全完了。MQL5/Files の ChienRatesM1v2_*.csv(3本)をzipにしてチャットへアップロードしてください。");
   Print("[Export] もし行数0のペアがあれば、このエキスパートタブのログを丸ごと貼り付けてください。");
}
//+------------------------------------------------------------------+
