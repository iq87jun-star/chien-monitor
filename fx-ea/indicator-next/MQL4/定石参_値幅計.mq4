//+------------------------------------------------------------------+
//|                                              ChienRangeMeter.mq4  |
//|                                                                  |
//| 定石 参 ─ 値幅計                                                  |
//|                                                                  |
//| 「どちらに動くか」ではなく「どれだけ動くか」を示すパネルです。     |
//|                                                                  |
//| 表示するもの:                                                     |
//|   1. 次のバーの想定値幅(直近 N 本の高安幅の平均)                |
//|   2. その銘柄・その時間足の平年並みの値幅                         |
//|   3. 静穏度 = 想定 ÷ 平年並み(いまは平年の何倍か)              |
//|   4. 自己採点 ─ 直近の実績で、想定値幅が平年並みより              |
//|      どれだけ誤差を減らせていたか                                 |
//|   5. 想定値幅に対する幅の目安(0.5 / 1.0 / 1.5 倍)              |
//|                                                                  |
//| 売買シグナルは出しません。方向は示しません。                      |
//| 端末にある足だけで計算します。外部データも DLL も使いません。      |
//+------------------------------------------------------------------+
#property copyright "iq87jun-star"
#property link      "https://www.gogojungle.co.jp/"
#property version   "1.01"
#property description "定石 参 ─ 値幅計: 次のバーの想定値幅と、それが平年並みの何倍かを表示します。売買シグナルは出しません。"
#property indicator_chart_window
#property strict

//--- 表示位置
enum ENUM_PANEL_CORNER
  {
   PC_LEFT_UPPER  = 0,  // 左上
   PC_RIGHT_UPPER = 1,  // 右上
   PC_LEFT_LOWER  = 2,  // 左下
   PC_RIGHT_LOWER = 3   // 右下
  };

//=== 計算設定 =======================================================
input int    InpRangeBars   = 14;    // 想定値幅に使う本数
input int    InpBaseBars    = 1500;  // 平年並みの算出に使う本数
input int    InpScoreBars   = 250;   // 自己採点に使う本数
input int    InpBandBars    = 60;    // 想定の範囲に使う本数
input double InpBandLo      = 0.10;  // 範囲の下側(分位)
input double InpBandHi      = 0.90;  // 範囲の上側(分位)

//=== 判定のしきい値 =================================================
input double InpQuietBelow  = 0.85;  // 静穏度: これ未満で「静か」
input double InpBusyAbove   = 1.15;  // 静穏度: これ以上で「荒い」

//=== 表示設定 =======================================================
input ENUM_PANEL_CORNER InpCorner = PC_LEFT_UPPER; // パネルの位置
input int    InpX           = 12;    // 横のオフセット(px)
input int    InpY           = 22;    // 縦のオフセット(px)
input int    InpFontSize    = 9;     // 文字サイズ
input string InpFontName    = "Meiryo UI";     // フォント
input color  InpColText     = clrGainsboro;    // 通常の文字色
input color  InpColHead     = clrWhite;        // 見出しの文字色
input color  InpColGood     = clrMediumSeaGreen;  // 良い側の色
input color  InpColWarn     = clrGoldenrod;       // 中間の色
input color  InpColBad      = clrIndianRed;       // 悪い側の色
input bool   InpShowGuide   = true;  // 幅の目安を出す
input bool   InpShowScore   = true;  // 自己採点を出す
input bool   InpShowBackdrop   = true;          // 下地を敷く
input color  InpColBackdrop    = C'22,22,28';   // 下地の色
input int    InpBackdropWidth  = 300;           // 下地の幅(px)

#define PANEL_PREFIX "ChienRM100_"
#define LINES        20
#define MIN_BARS     120   // これ未満では判定しない

//--- 直近の計算結果
double   g_pip      = 0.0001;
double   g_fc       = 0.0;   // 想定値幅(価格)
double   g_base     = 0.0;   // 平年並みの値幅(価格)
double   g_gain     = 0.0;   // 自己採点の改善率(0〜1)
int      g_scoreN   = 0;     // 自己採点に使えた本数
int      g_barsUsed = 0;     // 平年並みに使えた本数
int      g_scoreBase = 0;    // 自己採点で使った平年並みの本数
double   g_lo       = 0.0;   // 想定の範囲(下)
double   g_hi       = 0.0;   // 想定の範囲(上)
double   g_cover    = 0.0;   // その範囲に実際に入った割合
int      g_coverN   = 0;     // 被覆率の集計に使えた本数
bool     g_valid    = false;
datetime g_lastBar  = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   int    digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double point  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   g_pip = (digits == 3 || digits == 5) ? point * 10.0 : point;
   if(g_pip <= 0.0) g_pip = 0.0001;

   if(InpRangeBars < 2 || InpBaseBars <= InpRangeBars)
     {
      Print("値幅計: 本数の設定が不正です(平年並みの本数は想定値幅の本数より大きく)");
      return(INIT_PARAMETERS_INCORRECT);
     }
   IndicatorShortName("定石 参 ─ 値幅計");
   CreateLabels();
   g_lastBar = 0;
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, PANEL_PREFIX);
   ChartRedraw();
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated,
                const datetime &time[], const double &open[],
                const double &high[], const double &low[], const double &close[],
                const long &tick_volume[], const long &volume[], const int &spread[])
  {
   // バーが変わったときだけ集計し直す(毎ティックは回さない)
   datetime cur = iTime(_Symbol, _Period, 0);
   if(cur != g_lastBar)
     {
      g_lastBar = cur;
      Recalc();
     }
   Draw();
   return(rates_total);
  }

//+------------------------------------------------------------------+
//| 高安幅の系列を作り、想定値幅・平年並み・自己採点を出す            |
//|                                                                  |
//| 自己採点は、過去の各時点で「そのとき手に入る情報だけ」で          |
//| 想定値幅と平年並みを作り、実際の値幅とどちらが近かったかを見る。  |
//| 先読みが入らないよう、判定バー自身は必ず除いて計算する。          |
//+------------------------------------------------------------------+
void Recalc()
  {
   g_valid = false;
   int need = InpBaseBars + InpScoreBars + InpRangeBars + 2;

   MqlRates r[];
   ArraySetAsSeries(r, true);
   int got = CopyRates(_Symbol, _Period, 0, need, r);
   if(got < MIN_BARS + InpRangeBars + 2) return;

   // rng[k] = k 本前の確定足の高安幅。k=0 は形成中の足なので使わない
   int n = got;
   double rng[];
   ArrayResize(rng, n);
   for(int k = 0; k < n; k++) rng[k] = r[k].high - r[k].low;

   // pre[k] = rng[1] + ... + rng[k] の累積和(確定足だけ)
   double pre[];
   ArrayResize(pre, n + 1);
   pre[0] = 0.0; pre[1] = 0.0;
   for(int k = 1; k < n; k++) pre[k + 1] = pre[k] + rng[k];

   // --- 想定値幅: 直近 InpRangeBars 本の平均
   if(n <= InpRangeBars + 1) return;
   g_fc = (pre[InpRangeBars + 1] - pre[1]) / InpRangeBars;

   // --- 平年並み: 取得できた確定足すべて(上限 InpBaseBars)の平均
   int baseN = (int)MathMin(InpBaseBars, n - 1);
   if(baseN < MIN_BARS) return;
   g_base = (pre[baseN + 1] - pre[1]) / baseN;
   g_barsUsed = baseN;
   if(g_base <= 0.0 || g_fc <= 0.0) return;

   // --- 想定の範囲: 直近 InpBandBars 本の高安幅の分位
   int bandN = (int)MathMin(InpBandBars, n - 1);
   g_lo = (bandN >= 20) ? Quantile(rng, 1, bandN, InpBandLo) : 0.0;
   g_hi = (bandN >= 20) ? Quantile(rng, 1, bandN, InpBandHi) : 0.0;

   // --- 自己採点
   // 採点する各時点でも平年並みの窓が必要なので、足が少ないチャートでは
   // 表示用より短い窓を使う。短くしないと足りずに一度も採点できなくなる。
   int scoreN = (int)MathMin(InpScoreBars, n - MIN_BARS - 2);
   int sBase  = (int)MathMin(baseN, n - 2 - scoreN);
   double errFc = 0.0, errBase = 0.0;
   int cnt = 0, coverHit = 0, coverN = 0;
   if(scoreN > 0 && sBase >= MIN_BARS)
     {
      for(int k = 1; k <= scoreN; k++)
        {
         // k 本前の足の値幅を、その直前までの情報だけで当てにいく
         int fcFrom = k + 1;
         int fcTo   = k + InpRangeBars;
         int bsTo   = k + sBase;
         if(fcTo + 1 > n || bsTo + 1 > n) break;
         double fc = (pre[fcTo + 1] - pre[fcFrom]) / InpRangeBars;
         double bs = (pre[bsTo + 1] - pre[fcFrom]) / sBase;
         double act = rng[k];
         errFc   += MathAbs(act - fc);
         errBase += MathAbs(act - bs);
         cnt++;
         // その時点の範囲に、実際の値幅が入っていたかを数える
         if(bandN >= 20 && k + bandN < n)
           {
            double a = Quantile(rng, k + 1, bandN, InpBandLo);
            double b = Quantile(rng, k + 1, bandN, InpBandHi);
            if(act >= a && act <= b) coverHit++;
            coverN++;
           }
        }
     }
   g_coverN = coverN;
   g_cover  = (coverN >= 30) ? (double)coverHit / coverN : 0.0;
   g_scoreN    = cnt;
   g_scoreBase = sBase;
   g_gain      = (cnt >= 30 && errBase > 0.0) ? (errBase - errFc) / errBase : 0.0;
   g_valid     = true;
  }

//+------------------------------------------------------------------+
void CreateLabels()
  {
   ObjectsDeleteAll(0, PANEL_PREFIX);

   // 下地を先に作る(作成順が描画順になるため、必ずラベルより前に置く)
   if(InpShowBackdrop)
     {
      string bg = PANEL_PREFIX + "BG";
      if(ObjectCreate(0, bg, OBJ_RECTANGLE_LABEL, 0, 0, 0))
        {
         ObjectSetInteger(0, bg, OBJPROP_CORNER, CornerOf());
         ObjectSetInteger(0, bg, OBJPROP_XDISTANCE, InpX - 8);
         ObjectSetInteger(0, bg, OBJPROP_YDISTANCE, InpY - 8);
         ObjectSetInteger(0, bg, OBJPROP_XSIZE, InpBackdropWidth);
         ObjectSetInteger(0, bg, OBJPROP_YSIZE, 16);
         ObjectSetInteger(0, bg, OBJPROP_BGCOLOR, InpColBackdrop);
         ObjectSetInteger(0, bg, OBJPROP_BORDER_TYPE, BORDER_FLAT);
         ObjectSetInteger(0, bg, OBJPROP_COLOR, C'48,48,56');
         ObjectSetInteger(0, bg, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, bg, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, bg, OBJPROP_BACK, false);
        }
     }

   for(int i = 0; i < LINES; i++)
     {
      string nm = PANEL_PREFIX + IntegerToString(i);
      if(!ObjectCreate(0, nm, OBJ_LABEL, 0, 0, 0)) continue;
      ObjectSetInteger(0, nm, OBJPROP_CORNER, CornerOf());
      ObjectSetInteger(0, nm, OBJPROP_XDISTANCE, InpX);
      ObjectSetInteger(0, nm, OBJPROP_YDISTANCE, InpY + i * (InpFontSize + 6));
      ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, InpFontSize);
      ObjectSetString(0, nm, OBJPROP_FONT, InpFontName);
      ObjectSetInteger(0, nm, OBJPROP_COLOR, InpColText);
      ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, nm, OBJPROP_BACK, false);
      ObjectSetInteger(0, nm, OBJPROP_TIMEFRAMES, OBJ_NO_PERIODS);
      ObjectSetInteger(0, nm, OBJPROP_ANCHOR,
                       (InpCorner == PC_RIGHT_UPPER || InpCorner == PC_RIGHT_LOWER)
                       ? ANCHOR_RIGHT_UPPER : ANCHOR_LEFT_UPPER);
      ObjectSetString(0, nm, OBJPROP_TEXT, "");
     }
  }


//+------------------------------------------------------------------+
//| rng[from..to] の p 分位(0〜1)。Python 側の検証と同じ取り方。     |
//+------------------------------------------------------------------+
double Quantile(const double &rng[], const int from, const int cnt, const double p)
  {
   if(cnt <= 0) return(0.0);
   double w[];
   ArrayResize(w, cnt);
   for(int j = 0; j < cnt; j++) w[j] = rng[from + j];
   ArraySort(w);
   int idx = (int)(cnt * p);
   if(idx > cnt - 1) idx = cnt - 1;
   if(idx < 0) idx = 0;
   return(w[idx]);
  }

//+------------------------------------------------------------------+
int CornerOf()
  {
   switch(InpCorner)
     {
      case PC_RIGHT_UPPER: return(CORNER_RIGHT_UPPER);
      case PC_LEFT_LOWER:  return(CORNER_LEFT_LOWER);
      case PC_RIGHT_LOWER: return(CORNER_RIGHT_LOWER);
     }
   return(CORNER_LEFT_UPPER);
  }

//+------------------------------------------------------------------+
void SetLine(const int idx, const string text, const color col)
  {
   if(idx < 0 || idx >= LINES) return;
   string nm = PANEL_PREFIX + IntegerToString(idx);
   if(ObjectFind(0, nm) < 0) return;
   // 空文字のラベルは既定文字 "Label" で描画されてしまうため、
   // 使わない行は時間足フィルタで非表示にする
   if(StringLen(text) == 0)
     {
      ObjectSetInteger(0, nm, OBJPROP_TIMEFRAMES, OBJ_NO_PERIODS);
      return;
     }
   ObjectSetInteger(0, nm, OBJPROP_TIMEFRAMES, OBJ_ALL_PERIODS);
   ObjectSetString(0, nm, OBJPROP_TEXT, text);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, col);
  }

//+------------------------------------------------------------------+
string TfName()
  {
   switch(_Period)
     {
      case PERIOD_M1:  return("M1");
      case PERIOD_M5:  return("M5");
      case PERIOD_M15: return("M15");
      case PERIOD_M30: return("M30");
      case PERIOD_H1:  return("H1");
      case PERIOD_H4:  return("H4");
      case PERIOD_D1:  return("D1");
      case PERIOD_W1:  return("W1");
      case PERIOD_MN1: return("MN1");
     }
   return("TF" + IntegerToString(_Period));
  }

//+------------------------------------------------------------------+
void Draw()
  {
   int i = 0;
   SetLine(i++, "定石 参 ─ 値幅計  v1.01", InpColHead);
   SetLine(i++, StringFormat("%s  %s", _Symbol, TfName()), InpColText);
   SetLine(i++, " ", InpColText);

   if(!g_valid)
     {
      SetLine(i++, "判定できません(足の本数が足りません)", InpColWarn);
      SetLine(i++, StringFormat("必要 %d 本以上。チャートを遡って", MIN_BARS), InpColText);
      SetLine(i++, "読み込ませてください。", InpColText);
      for(; i < LINES; i++) SetLine(i, "", InpColText);
      ChartRedraw();
      return;
     }

   double fcPips   = g_fc   / g_pip;
   double basePips = g_base / g_pip;
   double quiet    = g_fc / g_base;

   color  qc  = InpColWarn;
   string qs  = "平年並み";
   if(quiet < InpQuietBelow) { qc = InpColGood; qs = "静か"; }
   if(quiet > InpBusyAbove)  { qc = InpColBad;  qs = "荒い"; }

   SetLine(i++, StringFormat("次のバーの想定値幅   %.1f pips", fcPips), InpColHead);
   SetLine(i++, StringFormat("平年並み             %.1f pips  (%d本)",
                             basePips, g_barsUsed), InpColText);
   SetLine(i++, StringFormat("静穏度  %.2f 倍  ─  %s", quiet, qs), qc);
   SetLine(i++, " ", InpColText);

   if(g_hi > g_lo)
     {
      SetLine(i++, StringFormat("想定の範囲   %.1f 〜 %.1f pips",
                                g_lo / g_pip, g_hi / g_pip), InpColHead);
      if(g_coverN >= 30)
         SetLine(i++, StringFormat("  この範囲に入った割合  %.0f%%(直近 %d 本)",
                                   g_cover * 100.0, g_coverN), InpColText);
      SetLine(i++, " ", InpColText);
     }

   if(InpShowGuide)
     {
      SetLine(i++, "想定値幅に対する幅の目安", InpColHead);
      SetLine(i++, StringFormat("  0.5倍 %.1f  /  1.0倍 %.1f  /  1.5倍 %.1f",
                                fcPips * 0.5, fcPips, fcPips * 1.5), InpColText);
      SetLine(i++, " ", InpColText);
     }

   if(InpShowScore)
     {
      if(g_scoreN >= 30)
        {
         color sc = (g_gain > 0.0) ? InpColGood : InpColBad;
         SetLine(i++, StringFormat("自己採点(直近 %d 本 / 平年並み %d 本)",
                                   g_scoreN, g_scoreBase), InpColHead);
         SetLine(i++, StringFormat("  平年並みより誤差 %+.1f%%", g_gain * 100.0), sc);
        }
      else
        {
         SetLine(i++, "自己採点: 集計待ち(30本以上必要)", InpColWarn);
        }
     }

   for(; i < LINES; i++) SetLine(i, "", InpColText);
   ChartRedraw();
  }
//+------------------------------------------------------------------+
