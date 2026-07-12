//+------------------------------------------------------------------+
//|                                  Chien_TickExport_Edge20.mq5     |
//|  edge20/24: M1バー一括エクスポート v1.30                            |
//|                                                                   |
//|  v1.20: 位置ベースCopyRates(履歴DL競合で空振りしない方式)・環境診断  |
//|  v1.30(edge24 執行スタディ用, docs/149): high/low列を追加            |
//|    (指値約定シミュレーションにはM1の高安が必須)。出力名をv2に変更。   |
//|                                                                   |
//|  使い方: コンパイル → ナビゲータ「スクリプト」からチャートへドラッグ |
//|  出力: MQL5/Files/ChienRatesM1v2_<PAIR>.csv                        |
//|  → 3ペア分をzipしてチャットにアップロード                           |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.30"
#property script_show_inputs
#property strict

input string InpSymbols   = "EURJPY,GBPJPY,USDJPY";
input int    InpMaxBars   = 800000;  // 遡るM1本数の上限(≈3年。履歴が尽きれば自動終了)
input int    InpHourFrom  = 4;       // サーバー時刻 この時から
input int    InpHourTo    = 16;      // サーバー時刻 この時まで(含む)

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

      // ウォームアップ: 直近10本が取れるまで待つ(履歴ダウンロード誘発)
      MqlRates warm[]; int wn=-1;
      for(int a=0;a<10;a++){ ResetLastError(); wn=CopyRates(sym,PERIOD_M1,0,10,warm);
         if(wn>0) break; Sleep(1500); }
      long avail=Bars(sym,PERIOD_M1);
      PrintFormat("[%s 診断] warmup=%d本(err=%d) M1利用可能≈%d本",syms[si],wn,GetLastError(),(int)avail);
      if(wn<=0){ PrintFormat("⚠ %s: M1が1本も取れない→スキップ(ログを報告してください)",syms[si]); continue; }

      string fn=StringFormat("ChienRatesM1v2_%s.csv",syms[si]);
      int h=FileOpen(fn,FILE_WRITE|FILE_TXT|FILE_ANSI);
      if(h==INVALID_HANDLE){ PrintFormat("⚠ %s: ファイル作成失敗 err=%d",fn,GetLastError()); continue; }
      FileWriteString(h,"time_server,open_bid,high_bid,low_bid,close_bid,spread_pips_open\n");

      long pos=0, rows=0; datetime oldest=0,newest=0;
      int CHUNK=20000;
      while(pos<InpMaxBars && !IsStopped()){
         MqlRates r[]; int n=-1;
         for(int a=0;a<6;a++){ ResetLastError();
            n=CopyRates(sym,PERIOD_M1,(int)pos,CHUNK,r);
            if(n>0) break; Sleep(1500); }
         if(n<=0){ PrintFormat("[%s] pos=%d で履歴終端(err=%d)",syms[si],(int)pos,GetLastError()); break; }
         for(int i=0;i<n;i++){
            MqlDateTime st; TimeToStruct(r[i].time,st);
            if(st.day_of_week!=1 && st.day_of_week!=2) continue;
            if(st.hour<InpHourFrom || st.hour>InpHourTo) continue;
            FileWriteString(h,StringFormat("%s,%.5f,%.5f,%.5f,%.5f,%.3f\n",
               TimeToString(r[i].time,TIME_DATE|TIME_MINUTES),r[i].open,r[i].high,r[i].low,r[i].close,
               r[i].spread*point/pip));
            rows++;
            if(oldest==0 || r[i].time<oldest) oldest=r[i].time;
            if(r[i].time>newest) newest=r[i].time;
         }
         pos+=n;
         PrintFormat("[%s] %d本走査済み(採用%d行・最古=%s)",syms[si],(int)pos,(int)rows,
            (oldest>0?TimeToString(oldest,TIME_DATE):"-"));
         if(n<CHUNK) { PrintFormat("[%s] 履歴終端に到達",syms[si]); break; }
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
