//+------------------------------------------------------------------+
//|                                 Chien_SpecDump.mq5               |
//|   銘柄仕様の一括ダンプ(スクリプト・注文は一切出さない)            |
//|                                                                   |
//|   目的(docs/223 §5.2 / docs/218 §10):                            |
//|     FNmarkets サポートが数値を出さなかった以下を自分で実測する。   |
//|       ① スワップ実額(Long/Short・3倍日)                          |
//|       ② 現在スプレッド(point / pip 換算)                          |
//|       ③ 銘柄名の実際の表記(GER40 か DE40 か 等)                   |
//|       ④ 契約サイズ・ティック値(名目→ロット換算に必須)             |
//|       ⑤ 1ロットの必要証拠金(ティア制レバレッジの実効値)           |
//|                                                                   |
//|   使い方: チャートにドラッグ → OK。MQL5/Files に CSV が出る。      |
//|     InpAllSymbols=false → 気配値表示の銘柄のみ                     |
//|     InpAllSymbols=true  → 業者の全銘柄(数百件。銘柄名探しに使う)   |
//|     InpFilter="JPY"     → 名前に含む銘柄だけに絞る(空=絞らない)    |
//|                                                                   |
//|   ⚠ 注意: スワップも スプレッドも「今この瞬間の値」。              |
//|     スプレッドは時間帯で数倍変わる(docs/216)。平日の 4/6/8/10 UTC  |
//|     など、実際に建てる時刻に走らせて複数回取ること。               |
//+------------------------------------------------------------------+
#property copyright "chien-monitor research"
#property version   "1.00"
#property strict
#property script_show_inputs

input bool   InpAllSymbols = false;   // false=気配値表示のみ / true=全銘柄
input string InpFilter     = "";      // 名前フィルタ(部分一致・空=全件)
input string InpOutPrefix  = "spec";  // 出力= MQL5/Files/<prefix>_YYYYMMDD_HHMM.csv

string DayName(int d)
{
   switch(d){ case 0: return "Sun"; case 1: return "Mon"; case 2: return "Tue"; case 3: return "Wed";
              case 4: return "Thu"; case 5: return "Fri"; case 6: return "Sat"; }
   return "?";
}
string CalcModeName(int m)
{
   switch(m){ case SYMBOL_CALC_MODE_FOREX: return "FOREX"; case SYMBOL_CALC_MODE_CFD: return "CFD";
              case SYMBOL_CALC_MODE_CFDINDEX: return "CFDINDEX"; case SYMBOL_CALC_MODE_CFDLEVERAGE: return "CFDLEV";
              case SYMBOL_CALC_MODE_FOREX_NO_LEVERAGE: return "FOREX_NOLEV";
              case SYMBOL_CALC_MODE_FUTURES: return "FUTURES"; }
   return IntegerToString(m);
}
string TradeModeName(int m)
{
   switch(m){ case SYMBOL_TRADE_MODE_DISABLED: return "DISABLED"; case SYMBOL_TRADE_MODE_LONGONLY: return "LONGONLY";
              case SYMBOL_TRADE_MODE_SHORTONLY: return "SHORTONLY"; case SYMBOL_TRADE_MODE_CLOSEONLY: return "CLOSEONLY";
              case SYMBOL_TRADE_MODE_FULL: return "FULL"; }
   return IntegerToString(m);
}
string SwapModeName(int m)
{
   switch(m){ case SYMBOL_SWAP_MODE_DISABLED: return "DISABLED"; case SYMBOL_SWAP_MODE_POINTS: return "POINTS";
              case SYMBOL_SWAP_MODE_CURRENCY_SYMBOL: return "CCY_SYMBOL"; case SYMBOL_SWAP_MODE_CURRENCY_MARGIN: return "CCY_MARGIN";
              case SYMBOL_SWAP_MODE_CURRENCY_DEPOSIT: return "CCY_DEPOSIT";
              case SYMBOL_SWAP_MODE_INTEREST_CURRENT: return "INT_CURRENT"; case SYMBOL_SWAP_MODE_INTEREST_OPEN: return "INT_OPEN";
              case SYMBOL_SWAP_MODE_REOPEN_CURRENT: return "REOPEN_CUR"; case SYMBOL_SWAP_MODE_REOPEN_BID: return "REOPEN_BID"; }
   return IntegerToString(m);
}

void OnStart()
{
   MqlDateTime t; TimeToStruct(TimeGMT(),t);
   string fn=StringFormat("%s_%04d%02d%02d_%02d%02d.csv",InpOutPrefix,t.year,t.mon,t.day,t.hour,t.min);
   int h=FileOpen(fn,FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(h==INVALID_HANDLE){ PrintFormat("⚠ CSVを開けません: %s err=%d",fn,GetLastError()); return; }

   FileWrite(h,"utc","symbol","description","path","calc_mode","trade_mode",
               "digits","point","pip","contract_size","tick_value","tick_size",
               "vol_min","vol_max","vol_step","spread_points","spread_pips",
               "swap_mode","swap_long","swap_short","swap3day",
               "margin_1lot","ccy_margin","ccy_profit","bid","ask");

   int total = InpAllSymbols ? SymbolsTotal(false) : SymbolsTotal(true);
   int n=0, skipped=0;
   string stamp=TimeToString(TimeGMT(),TIME_DATE|TIME_MINUTES);

   for(int i=0;i<total;i++)
   {
      string s=SymbolName(i,!InpAllSymbols);
      if(s=="") continue;
      if(StringLen(InpFilter)>0 && StringFind(s,InpFilter)<0){ skipped++; continue; }
      if(InpAllSymbols && !SymbolSelect(s,true)){ skipped++; continue; }

      double pt   =SymbolInfoDouble(s,SYMBOL_POINT);
      int    dg   =(int)SymbolInfoInteger(s,SYMBOL_DIGITS);
      double pip  =(pt>0? pt*10.0 : 0.0);           // 記録EAの PipOf() と同一定義
      double cs   =SymbolInfoDouble(s,SYMBOL_TRADE_CONTRACT_SIZE);
      double tv   =SymbolInfoDouble(s,SYMBOL_TRADE_TICK_VALUE);
      double ts   =SymbolInfoDouble(s,SYMBOL_TRADE_TICK_SIZE);
      double bid  =SymbolInfoDouble(s,SYMBOL_BID), ask=SymbolInfoDouble(s,SYMBOL_ASK);
      long   spr  =SymbolInfoInteger(s,SYMBOL_SPREAD);
      double sprp =(pip>0? (double)spr*pt/pip : 0.0);
      double swl  =SymbolInfoDouble(s,SYMBOL_SWAP_LONG);
      double sws  =SymbolInfoDouble(s,SYMBOL_SWAP_SHORT);

      double marg=0.0;
      if(ask>0 && !OrderCalcMargin(ORDER_TYPE_BUY,s,1.0,ask,marg)) marg=-1.0;

      FileWrite(h,stamp,s,
         SymbolInfoString(s,SYMBOL_DESCRIPTION), SymbolInfoString(s,SYMBOL_PATH),
         CalcModeName((int)SymbolInfoInteger(s,SYMBOL_TRADE_CALC_MODE)),
         TradeModeName((int)SymbolInfoInteger(s,SYMBOL_TRADE_MODE)),
         IntegerToString(dg), DoubleToString(pt,8), DoubleToString(pip,8),
         DoubleToString(cs,2), DoubleToString(tv,5), DoubleToString(ts,8),
         DoubleToString(SymbolInfoDouble(s,SYMBOL_VOLUME_MIN),2),
         DoubleToString(SymbolInfoDouble(s,SYMBOL_VOLUME_MAX),2),
         DoubleToString(SymbolInfoDouble(s,SYMBOL_VOLUME_STEP),2),
         IntegerToString(spr), DoubleToString(sprp,2),
         SwapModeName((int)SymbolInfoInteger(s,SYMBOL_SWAP_MODE)),
         DoubleToString(swl,3), DoubleToString(sws,3),
         DayName((int)SymbolInfoInteger(s,SYMBOL_SWAP_ROLLOVER3DAYS)),
         DoubleToString(marg,2),
         SymbolInfoString(s,SYMBOL_CURRENCY_MARGIN), SymbolInfoString(s,SYMBOL_CURRENCY_PROFIT),
         DoubleToString(bid,dg), DoubleToString(ask,dg));
      n++;
   }
   FileClose(h);
   PrintFormat("[SPEC DUMP] %d 銘柄を書き出しました(除外 %d)。ファイル: MQL5/Files/%s",n,skipped,fn);
   PrintFormat("[SPEC DUMP] 口座: レバレッジ 1:%d / 残高 %.2f %s / ストップアウト %.0f%% / 会社 %s",
      (int)AccountInfoInteger(ACCOUNT_LEVERAGE), AccountInfoDouble(ACCOUNT_BALANCE),
      AccountInfoString(ACCOUNT_CURRENCY), AccountInfoDouble(ACCOUNT_MARGIN_SO_SO),
      AccountInfoString(ACCOUNT_COMPANY));
}
