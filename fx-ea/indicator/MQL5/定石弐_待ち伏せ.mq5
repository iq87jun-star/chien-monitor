//+------------------------------------------------------------------+
//|                                          定石弐_待ち伏せ.mq5   |
//|                                                                  |
//| 定石 弐 ─ 待ち伏せ シグナル                                       |
//|                                                                  |
//| 日足の4条件が「すべて」揃った場面だけを検出します。               |
//|   1. RSI(14) が 35 未満(売り側は 65 超)                        |
//|   2. 終値が直前20本の平均から 1.5標準偏差 以上離れている          |
//|   3. 3本以上の連続陰線(売り側は連続陽線)                       |
//|   4. その日の変動が 0.5% を超えている                            |
//|                                                                  |
//| 4つすべてが揃うことが本質です。3つに緩めると優位性は失われます。  |
//| そのため、揃うのは1通貨ペアあたり年に数回しかありません。         |
//| このインジケーターの価値は「鳴らないこと」にあります。            |
//|                                                                  |
//| 表示するもの                                                      |
//|   ・4条件が揃った日足に矢印                                       |
//|   ・4条件それぞれの現在の成立状況(何が足りないか)               |
//|   ・損切り(日足ATR×1.5)と利確(損切り×1.2)の目安ライン       |
//|   ・揃った時のアラート / プッシュ通知                             |
//|                                                                  |
//| 発注は行いません。判断と執行は利用者が行います。                  |
//+------------------------------------------------------------------+
#property copyright "iq87jun-star"
#property link      "https://www.gogojungle.co.jp/"
#property version   "1.02"
#property description "定石 弐 ─ 待ち伏せ シグナル: 日足4条件がすべて揃った場面だけを検出します。年に数回しか鳴りません。発注は行いません。"
#property indicator_chart_window
#property indicator_buffers 2
#property indicator_plots   2

#property indicator_label1  "買いシグナル"
#property indicator_type1   DRAW_ARROW
#property indicator_color1  clrDeepSkyBlue
#property indicator_width1  3

#property indicator_label2  "売りシグナル"
#property indicator_type2   DRAW_ARROW
#property indicator_color2  clrOrangeRed
#property indicator_width2  3

//=== 条件の設定(既定値が検証で使った値です) ======================
input int    InpRsiPeriod   = 14;    // RSI期間
input double InpRsiBuy      = 35.0;  // 買い: RSIがこれ未満
input double InpRsiSell     = 65.0;  // 売り: RSIがこれ超
input int    InpZWindow     = 20;    // 標準偏差の計算本数
input double InpZThreshold  = 1.5;   // 何標準偏差離れたら成立か
input int    InpRunLength    = 3;    // 連続本数
input double InpMovePercent  = 0.5;  // その日の変動(%)
input int    InpNeedCount    = 4;    // 必要な条件数(4=すべて)

//=== 損切り・利確の目安 =============================================
input int    InpAtrPeriod   = 14;    // ATR期間
input double InpSlAtrMult   = 1.5;   // 損切り = 日足ATR × これ
input double InpRewardRatio = 1.2;   // 利確 = 損切り幅 × これ
input bool   InpShowLevels  = true;  // 目安ラインを描く

//=== 通知 ===========================================================
input bool   InpAlertPopup  = true;  // 画面にアラートを出す
input bool   InpAlertPush   = false; // スマホにプッシュ通知する
input bool   InpAlertMail   = false; // メールを送る

//=== パネル =========================================================
input int    InpMaxDays     = 1500;  // 矢印を描く過去日数の上限(0=無制限)

input bool   InpShowPanel   = true;  // 条件パネルを表示する
input bool   InpShowBackdrop = true; // 文字の背景に下地を敷く(推奨)
input color  InpColBackdrop  = C'12,12,16'; // 下地の色
input int    InpBackdropW    = 320;  // 下地の幅(px)
input int    InpPanelX      = 12;    // パネルの横位置(px)
input int    InpPanelY      = 22;    // パネルの縦位置(px)
input int    InpFontSize    = 9;     // 文字サイズ
input string InpFontName    = "Meiryo UI"; // フォント
input color  InpColHead     = clrWhite;      // 見出しの色
input color  InpColMet      = clrLimeGreen;  // 条件成立の色
input color  InpColUnmet    = clrGray;       // 条件不成立の色
input color  InpColBuy      = clrDeepSkyBlue;// 買いの色
input color  InpColSell     = clrOrangeRed;  // 売りの色

#define PFX "ChienQS102_"
#define PANEL_LINES 12

double   g_buyBuf[];
double   g_sellBuf[];
int      g_hRsi = INVALID_HANDLE;
int      g_hAtr = INVALID_HANDLE;
datetime g_lastAlert = 0;
// 直近確定日足の判定キャッシュ(毎ティックの再計算を避ける)
datetime g_cacheDay  = 0;
int      g_cacheSig  = 0;
bool     g_cacheBuy[4], g_cacheSell[4];

//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0, g_buyBuf,  INDICATOR_DATA);
   SetIndexBuffer(1, g_sellBuf, INDICATOR_DATA);
   PlotIndexSetInteger(0, PLOT_ARROW, 233);   // 上向き
   PlotIndexSetInteger(1, PLOT_ARROW, 234);   // 下向き
   PlotIndexSetInteger(0, PLOT_ARROW_SHIFT, -12);
   PlotIndexSetInteger(1, PLOT_ARROW_SHIFT,  12);
   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetDouble(1, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   ArraySetAsSeries(g_buyBuf,  false);
   ArraySetAsSeries(g_sellBuf, false);

   g_hRsi = iRSI(_Symbol, PERIOD_D1, InpRsiPeriod, PRICE_CLOSE);
   g_hAtr = iATR(_Symbol, PERIOD_D1, InpAtrPeriod);
   if(g_hRsi == INVALID_HANDLE || g_hAtr == INVALID_HANDLE)
     {
      Print("待ち伏せ: 日足インジケーターの作成に失敗しました");
      return(INIT_FAILED);
     }

   IndicatorSetString(INDICATOR_SHORTNAME, "定石 弐 ─ 待ち伏せ");
   if(InpShowPanel) CreatePanel();
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(g_hRsi != INVALID_HANDLE) IndicatorRelease(g_hRsi);
   if(g_hAtr != INVALID_HANDLE) IndicatorRelease(g_hAtr);
   ObjectsDeleteAll(0, PFX);
   ChartRedraw();
  }

//+------------------------------------------------------------------+
//| 日足バー shift の4条件を判定する                                  |
//|  戻り値: +1=買い / -1=売り / 0=なし                              |
//|  met[] には 4条件それぞれの成立状況が入る(買い側基準)          |
//+------------------------------------------------------------------+
int EvalDay(const int shift, bool &metBuy[], bool &metSell[])
  {
   ArrayResize(metBuy, 4);  ArrayResize(metSell, 4);
   for(int k = 0; k < 4; k++) { metBuy[k] = false; metSell[k] = false; }

   double rsiArr[1];
   if(CopyBuffer(g_hRsi, 0, shift, 1, rsiArr) != 1) return(0);
   double rsi = rsiArr[0];

   // 直前 InpZWindow 本の平均と標本標準偏差(判定バー自身は含めない)
   double sum = 0.0, sum2 = 0.0;
   for(int k = shift + 1; k <= shift + InpZWindow; k++)
     {
      double c = iClose(_Symbol, PERIOD_D1, k);
      if(c <= 0.0) return(0);
      sum += c; sum2 += c * c;
     }
   double mean = sum / InpZWindow;
   double var  = (sum2 - InpZWindow * mean * mean) / (InpZWindow - 1);
   if(var <= 0.0) return(0);
   double sd = MathSqrt(var);

   double c1 = iClose(_Symbol, PERIOD_D1, shift);
   double c2 = iClose(_Symbol, PERIOD_D1, shift + 1);
   if(c1 <= 0.0 || c2 <= 0.0) return(0);
   double z = (c1 - mean) / sd;

   int down = 0, up = 0;
   for(int k = 0; k < 12; k++)
     {
      double a = iClose(_Symbol, PERIOD_D1, shift + k);
      double b = iClose(_Symbol, PERIOD_D1, shift + k + 1);
      if(a <= 0.0 || b <= 0.0) break;
      if(a < b) down++; else break;
     }
   for(int k = 0; k < 12; k++)
     {
      double a = iClose(_Symbol, PERIOD_D1, shift + k);
      double b = iClose(_Symbol, PERIOD_D1, shift + k + 1);
      if(a <= 0.0 || b <= 0.0) break;
      if(a > b) up++; else break;
     }

   double ret = (c1 - c2) / c2 * 100.0;

   metBuy[0]  = (rsi < InpRsiBuy);
   metBuy[1]  = (z < -InpZThreshold);
   metBuy[2]  = (down >= InpRunLength);
   metBuy[3]  = (ret < -InpMovePercent);

   metSell[0] = (rsi > InpRsiSell);
   metSell[1] = (z >  InpZThreshold);
   metSell[2] = (up >= InpRunLength);
   metSell[3] = (ret >  InpMovePercent);

   int nb = 0, ns = 0;
   for(int k = 0; k < 4; k++) { if(metBuy[k]) nb++; if(metSell[k]) ns++; }

   if(nb >= InpNeedCount && nb > ns) return(1);
   if(ns >= InpNeedCount && ns > nb) return(-1);
   return(0);
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated,
                const datetime &time[], const double &open[],
                const double &high[], const double &low[],
                const double &close[], const long &tick_volume[],
                const long &volume[], const int &spread[])
  {
   if(rates_total < 60) return(0);

   int need = MathMax(InpZWindow, MathMax(InpRsiPeriod, InpAtrPeriod)) + 5;
   if(Bars(_Symbol, PERIOD_D1) < need + 5) return(0);

   int start = (prev_calculated > 1) ? prev_calculated - 1 : 1;

   // 履歴が長いチャートで初回計算が重くならないよう、描画範囲を絞る
   if(InpMaxDays > 0 && prev_calculated == 0)
     {
      datetime cutoff = iTime(_Symbol, PERIOD_D1, MathMin(InpMaxDays,
                              Bars(_Symbol, PERIOD_D1) - 1));
      if(cutoff > 0)
         for(int j = 1; j < rates_total; j++)
            if(time[j] >= cutoff) { start = MathMax(start, j); break; }
      for(int j = 0; j < start; j++)
        { g_buyBuf[j] = EMPTY_VALUE; g_sellBuf[j] = EMPTY_VALUE; }
     }

   bool mb[], ms[];

   for(int i = start; i < rates_total; i++)
     {
      g_buyBuf[i]  = EMPTY_VALUE;
      g_sellBuf[i] = EMPTY_VALUE;

      // このチャート足で「日付が変わった」最初の足かどうか
      int dNow  = iBarShift(_Symbol, PERIOD_D1, time[i], false);
      int dPrev = iBarShift(_Symbol, PERIOD_D1, time[i - 1], false);
      if(dNow < 0 || dPrev < 0 || dNow == dPrev) continue;

      // 直前に確定した日足(= dNow + 1)を判定する
      int sig = EvalDay(dNow + 1, mb, ms);
      if(sig == 0) continue;

      if(sig > 0) g_buyBuf[i]  = low[i];
      else        g_sellBuf[i] = high[i];
     }

   // 最新足での通知(確定した日足に対して1回だけ)
   if(rates_total > 2)
     {
      int dLast = iBarShift(_Symbol, PERIOD_D1, time[rates_total - 1], false);
      if(dLast >= 0)
        {
         datetime dTime = iTime(_Symbol, PERIOD_D1, dLast + 1);
         if(dTime > 0 && dTime != g_lastAlert)
           {
            int sig = (dLast + 1 == 1) ? CurrentEval(mb, ms) : EvalDay(dLast + 1, mb, ms);
            if(sig != 0)
              {
               g_lastAlert = dTime;
               string msg = StringFormat("定石 弐: %s %s シグナル(4条件すべて成立)",
                                         _Symbol, (sig > 0 ? "買い" : "売り"));
               if(InpAlertPopup) Alert(msg);
               if(InpAlertPush)  SendNotification(msg);
               if(InpAlertMail)  SendMail("定石 弐 シグナル", msg);
              }
           }
        }
     }

   if(InpShowPanel)  DrawPanel();
   if(InpShowLevels) DrawLevels();
   ChartRedraw();

   return(rates_total);
  }

//+------------------------------------------------------------------+
//| 直近の確定日足(shift=1)の判定。日足が変わるまで結果を使い回す  |
//+------------------------------------------------------------------+
int CurrentEval(bool &mb[], bool &ms[])
  {
   datetime d1 = iTime(_Symbol, PERIOD_D1, 1);
   if(d1 > 0 && d1 == g_cacheDay)
     {
      ArrayResize(mb, 4); ArrayResize(ms, 4);
      for(int k = 0; k < 4; k++) { mb[k] = g_cacheBuy[k]; ms[k] = g_cacheSell[k]; }
      return(g_cacheSig);
     }
   int sig = EvalDay(1, mb, ms);
   if(d1 > 0 && ArraySize(mb) >= 4)
     {
      g_cacheDay = d1; g_cacheSig = sig;
      for(int k = 0; k < 4; k++) { g_cacheBuy[k] = mb[k]; g_cacheSell[k] = ms[k]; }
     }
   return(sig);
  }

//+------------------------------------------------------------------+
ENUM_BASE_CORNER QsCorner()
  {
   switch(InpPanelCorner)
     {
      case QC_RIGHT_UPPER: return(CORNER_RIGHT_UPPER);
      case QC_LEFT_LOWER:  return(CORNER_LEFT_LOWER);
      case QC_RIGHT_LOWER: return(CORNER_RIGHT_LOWER);
     }
   return(CORNER_LEFT_UPPER);
  }

//+------------------------------------------------------------------+
void CreatePanel()
  {
   if(InpShowBackdrop)
     {
      string bg = PFX + "BG";
      if(ObjectCreate(0, bg, OBJ_RECTANGLE_LABEL, 0, 0, 0))
        {
         ObjectSetInteger(0, bg, OBJPROP_CORNER, QsCorner());
         ObjectSetInteger(0, bg, OBJPROP_XDISTANCE, InpPanelX - 8);
         ObjectSetInteger(0, bg, OBJPROP_YDISTANCE, InpPanelY - 8);
         ObjectSetInteger(0, bg, OBJPROP_XSIZE, InpBackdropW);
         ObjectSetInteger(0, bg, OBJPROP_YSIZE, PANEL_LINES * (InpFontSize + 6) + 14);
         ObjectSetInteger(0, bg, OBJPROP_BGCOLOR, InpColBackdrop);
         ObjectSetInteger(0, bg, OBJPROP_BORDER_TYPE, BORDER_FLAT);
         ObjectSetInteger(0, bg, OBJPROP_COLOR, C'48,48,56');
         ObjectSetInteger(0, bg, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, bg, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, bg, OBJPROP_BACK, false);
        }
     }

   for(int i = 0; i < PANEL_LINES; i++)
     {
      string n = PFX + "L" + IntegerToString(i);
      if(!ObjectCreate(0, n, OBJ_LABEL, 0, 0, 0)) continue;
      ObjectSetInteger(0, n, OBJPROP_CORNER, QsCorner());
      ObjectSetInteger(0, n, OBJPROP_ANCHOR,
                       (InpPanelCorner == QC_RIGHT_UPPER || InpPanelCorner == QC_RIGHT_LOWER)
                       ? ANCHOR_RIGHT_UPPER : ANCHOR_LEFT_UPPER);
      ObjectSetInteger(0, n, OBJPROP_XDISTANCE, InpPanelX);
      ObjectSetInteger(0, n, OBJPROP_YDISTANCE, InpPanelY + i * (InpFontSize + 6));
      ObjectSetInteger(0, n, OBJPROP_FONTSIZE, InpFontSize);
      ObjectSetString(0, n, OBJPROP_FONT, InpFontName);
      ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, n, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, n, OBJPROP_TIMEFRAMES, OBJ_NO_PERIODS);
      ObjectSetString(0, n, OBJPROP_TEXT, "");
     }
  }

//+------------------------------------------------------------------+
void SetLine(const int idx, const string text, const color col)
  {
   string n = PFX + "L" + IntegerToString(idx);
   if(ObjectFind(0, n) < 0) return;
   // 空文字のラベルは既定文字 "Label" で描画されるため、使わない行は非表示にする
   if(StringLen(text) == 0)
     {
      ObjectSetInteger(0, n, OBJPROP_TIMEFRAMES, OBJ_NO_PERIODS);
      return;
     }
   ObjectSetInteger(0, n, OBJPROP_TIMEFRAMES, OBJ_ALL_PERIODS);
   ObjectSetString(0, n, OBJPROP_TEXT, text);
   ObjectSetInteger(0, n, OBJPROP_COLOR, col);
  }

//+------------------------------------------------------------------+
void DrawPanel()
  {
   bool mb[], ms[];
   int sig = CurrentEval(mb, ms);
   if(ArraySize(mb) < 4) return;

   int nb = 0, ns = 0;
   for(int k = 0; k < 4; k++) { if(mb[k]) nb++; if(ms[k]) ns++; }
   bool buySide = (nb >= ns);
   int  cnt     = buySide ? nb : ns;

   string names[4] = {"RSI", "標準偏差", "連続本数", "当日変動"};
   string cond[4];
   cond[0] = buySide ? StringFormat("RSI(%d) < %.0f", InpRsiPeriod, InpRsiBuy)
                     : StringFormat("RSI(%d) > %.0f", InpRsiPeriod, InpRsiSell);
   cond[1] = StringFormat("平均から %.1f SD 以上", InpZThreshold);
   cond[2] = StringFormat("%d本以上の連続%s", InpRunLength, buySide ? "陰線" : "陽線");
   cond[3] = StringFormat("当日 %.1f%% 超の下落", InpMovePercent);
   if(!buySide) cond[3] = StringFormat("当日 %.1f%% 超の上昇", InpMovePercent);

   int i = 0;
   SetLine(i++, "定石 弐 ─ 待ち伏せ  v1.02", InpColHead);
   SetLine(i++, StringFormat("%s  日足で判定中", _Symbol), InpColHead);
   SetLine(i++, " ", InpColHead);
   SetLine(i++, buySide ? "買い方向の条件" : "売り方向の条件",
           buySide ? InpColBuy : InpColSell);

   for(int k = 0; k < 4; k++)
     {
      bool met = buySide ? mb[k] : ms[k];
      SetLine(i++, StringFormat("  %s %-8s %s", met ? "●" : "○", names[k], cond[k]),
              met ? InpColMet : InpColUnmet);
     }

   SetLine(i++, " ", InpColHead);
   if(sig != 0)
     {
      SetLine(i++, StringFormat("★ %d / 4 すべて成立 — %s シグナル",
                   cnt, sig > 0 ? "買い" : "売り"),
              sig > 0 ? InpColBuy : InpColSell);
      SetLine(i++, "  翌営業日の寄り付き前後での執行を想定しています", InpColHead);
     }
   else
     {
      SetLine(i++, StringFormat("%d / 4 成立 — 待機中", cnt), InpColUnmet);
      SetLine(i++, "  4つすべてが揃うまで動きません", InpColUnmet);
     }
   for(; i < PANEL_LINES; i++) SetLine(i, "", InpColUnmet);
  }

//+------------------------------------------------------------------+
void DrawLevels()
  {
   string nSL = PFX + "SL", nTP = PFX + "TP", nEN = PFX + "EN";
   bool mb[], ms[];
   int sig = CurrentEval(mb, ms);

   if(sig == 0)
     {
      ObjectDelete(0, nSL); ObjectDelete(0, nTP); ObjectDelete(0, nEN);
      return;
     }

   double atrArr[1];
   if(CopyBuffer(g_hAtr, 0, 1, 1, atrArr) != 1 || atrArr[0] <= 0.0) return;

   double entry  = iClose(_Symbol, PERIOD_D1, 1);
   double slDist = atrArr[0] * InpSlAtrMult;
   double sl = (sig > 0) ? entry - slDist : entry + slDist;
   double tp = (sig > 0) ? entry + slDist * InpRewardRatio
                         : entry - slDist * InpRewardRatio;

   DrawHLine(nEN, entry, (sig > 0) ? InpColBuy : InpColSell, STYLE_SOLID,  "目安 建値");
   DrawHLine(nSL, sl,    clrTomato,                          STYLE_DASH,   "目安 損切り");
   DrawHLine(nTP, tp,    clrLimeGreen,                       STYLE_DASH,   "目安 利確");
  }

//+------------------------------------------------------------------+
void DrawHLine(const string name, const double price, const color col,
               const ENUM_LINE_STYLE style, const string text)
  {
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_HLINE, 0, 0, price);
   ObjectSetDouble(0, name, OBJPROP_PRICE, price);
   ObjectSetInteger(0, name, OBJPROP_COLOR, col);
   ObjectSetInteger(0, name, OBJPROP_STYLE, style);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetString(0, name, OBJPROP_TOOLTIP, StringFormat("%s  %.5f", text, price));
  }
//+------------------------------------------------------------------+
