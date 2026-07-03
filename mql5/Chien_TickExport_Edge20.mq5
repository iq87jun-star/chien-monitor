//+------------------------------------------------------------------+
//|                                  Chien_TickExport_Edge20.mq5     |
//|  edge20(docs/108改訂): ブローカー実ティックの1分集約エクスポート     |
//|                                                                   |
//|  用途: v7執行実測(スプレッド時刻構造・時刻セット頑健性・上限校正)。 |
//|  Dukascopy(Colab)不達のため、実際に取引するサーバーの実ティックを   |
//|  使う(執行最適化にはむしろこちらが正)。                            |
//|                                                                   |
//|  使い方: MetaEditorでコンパイル → ナビゲータ「スクリプト」から      |
//|    任意のチャートへドラッグ → OK。完了までターミナルを閉じない      |
//|    (履歴ダウンロードを含み数分〜十数分)。                          |
//|  出力: MQL5/Files/ChienTicksM1_<PAIR>.csv                          |
//|    列: time_server,bid_avg,ask_avg,spread_pips_avg,spread_pips_max,n_ticks |
//|  対象: 月曜・火曜(サーバー日付)× サーバー時刻 InpHourFrom-To、      |
//|    サーバーが保持する限り過去へ遡る(30日連続で無データなら終了)。   |
//|  ⚠ ティック履歴の深さはブローカー依存(FNは概ね数ヶ月〜1年超)。      |
//|    実際に取得できた期間はログに表示=docs/109に記録する。            |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.00"
#property script_show_inputs
#property strict

input string InpSymbols     = "EURJPY,GBPJPY,USDJPY";
input int    InpMaxDaysBack = 1200;   // 最大遡り日数(履歴が尽きれば自動終了)
input int    InpHourFrom    = 4;      // サーバー時刻 この時から(UTC+2/3なら03-12UTC≈05-15)
input int    InpHourTo      = 16;     // サーバー時刻 この時まで(この時間台を含む)
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

void OnStart()
{
   string syms[]; int ns=SplitCSV(InpSymbols,syms);
   PrintFormat("[TickExport] GMTオフセット(現在): サーバー%+d秒 (参考。解析側で週初ギャップから自動推定)",
               (int)(TimeCurrent()-TimeGMT()));
   for(int si=0; si<ns; si++){
      string sym=ResolveSymbol(syms[si]);
      if(sym==""){ PrintFormat("⚠ %s 解決不可→スキップ",syms[si]); continue; }
      double pip=(StringFind(sym,"JPY")>=0? 0.01: 0.0001);
      string fn=StringFormat("ChienTicksM1_%s.csv",syms[si]);
      int h=FileOpen(fn,FILE_WRITE|FILE_TXT|FILE_ANSI);
      if(h==INVALID_HANDLE){ PrintFormat("⚠ %s: ファイル作成失敗",fn); continue; }
      FileWriteString(h,"time_server,bid_avg,ask_avg,spread_pips_avg,spread_pips_max,n_ticks\n");

      datetime now=TimeCurrent();
      MqlDateTime t0; TimeToStruct(now,t0); t0.hour=0; t0.min=0; t0.sec=0;
      datetime today=StructToTime(t0);
      int emptyStreak=0, daysOut=0; datetime oldest=now;
      long rows=0;

      for(int d=0; d<InpMaxDaysBack && emptyStreak<InpEmptyStop && !IsStopped(); d++){
         datetime day0=today-(datetime)d*86400;
         MqlDateTime st; TimeToStruct(day0,st);
         if(st.day_of_week!=1 && st.day_of_week!=2) continue;   // 月・火(サーバー日付)
         bool any=false;
         for(int hh=InpHourFrom; hh<=InpHourTo; hh++){
            ulong fromMs=(ulong)(day0+hh*3600)*1000;
            ulong toMs  =fromMs+3600*1000-1;
            MqlTick ticks[];
            int n=CopyTicksRange(sym,ticks,COPY_TICKS_INFO,fromMs,toMs);
            if(n<=0) continue;
            any=true;
            // 1分集約
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
         if(any){ emptyStreak=0; daysOut++; if(day0<oldest) oldest=day0; }
         else emptyStreak++;
         if(daysOut>0 && daysOut%20==0 && any)
            PrintFormat("[%s] %s まで遡及済み(%d日・%d行)",syms[si],TimeToString(day0,TIME_DATE),daysOut,(int)rows);
      }
      FileClose(h);
      PrintFormat("[%s] 完了: %d日分・%d行 → MQL5/Files/%s(最古=%s)",
                  syms[si],daysOut,(int)rows,fn,TimeToString(oldest,TIME_DATE));
   }
   Print("[TickExport] 全完了。MQL5/Files の ChienTicksM1_*.csv(3本)をzipにしてチャットへアップロードしてください。");
}
//+------------------------------------------------------------------+
