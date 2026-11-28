//+------------------------------------------------------------------+
//| Chien_TsmomSignalDump.mq5 — docs/253 Q1 パリティ A 用スクリプト        |
//| 口座の月足(PERIOD_MN1)から TSMOM 符号(lb 1/3/6/12 の符号和)を月ごとに |
//| 計算し MQL5/Files/tsmom_signals_mt5.csv に書く。EA と同一ロジック。    |
//| 列: symbol, month(適用月 YYYY-MM), sign, sum, c_last                  |
//| 使い方: 任意チャートで実行(InpSymbols を口座の銘柄名に合わせる)。      |
//|   結果 CSV を research/queue/q01_tsmom_parity.py に渡す。              |
//+------------------------------------------------------------------+
#property script_show_inputs
input string InpSymbols = "XAUUSD,SPX500,NDX100,GER40,BTCUSD,ETHUSD";  // 口座の銘柄名(FN: SPX500/NDX100、他社: US500/NAS100)
input int    InpMonths  = 140;                                        // 遡る月数

void OnStart()
{
   string syms[]; int n=StringSplit(InpSymbols,',',syms);
   int h=FileOpen("tsmom_signals_mt5.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(h==INVALID_HANDLE){ Print("CSV open failed ",GetLastError()); return; }
   FileWrite(h,"symbol","month","sign","sum","c_last");
   for(int s=0;s<n;s++){
      string sym=syms[s]; StringTrimLeft(sym); StringTrimRight(sym);
      if(!SymbolSelect(sym,true)){ PrintFormat("⚠ %s 選択不可",sym); continue; }
      double c[]; datetime t[]; ArraySetAsSeries(c,false); ArraySetAsSeries(t,false);
      int nc=CopyClose(sym,PERIOD_MN1,0,InpMonths,c); int nt=CopyTime(sym,PERIOD_MN1,0,InpMonths,t);
      if(nc<14||nt<14){ PrintFormat("⚠ %s 月足 %d 本",sym,nc); continue; }
      int lbs[4]={1,3,6,12}; int rows=0;
      for(int i=12;i<nc-1;i++){                   // i = 確定月(最後の nc-1 は形成中なので除く)。適用月 = i+1
         int comp=0; for(int k=0;k<4;k++){ int j=i-lbs[k]; if(j<0) continue; double r=c[i]/c[j]-1.0; comp+=(r>0?1:(r<0?-1:0)); }
         int sign=(comp>0?1:(comp<0?-1:0));
         MqlDateTime d; TimeToStruct(t[i+1],d);
         FileWrite(h,sym,StringFormat("%04d-%02d",d.year,d.mon),IntegerToString(sign),IntegerToString(comp),DoubleToString(c[i],5)); rows++;
      }
      PrintFormat("[TSMOM DUMP] %s rows=%d (月足 %d 本)",sym,rows,nc);
   }
   FileClose(h); Print("→ MQL5/Files/tsmom_signals_mt5.csv");
}
