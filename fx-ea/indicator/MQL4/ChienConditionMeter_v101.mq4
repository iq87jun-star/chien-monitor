//+------------------------------------------------------------------+
//|                                        ChienConditionMeter_v101.m  |
//|                                                                  |
//| 定石 零 ─ 環境計                                                  |
//|                                                                  |
//| 「いつ入るか」ではなく「いま入ってよいか」を示すパネルです。       |
//|                                                                  |
//| 表示するもの:                                                     |
//|   1. 現在のスプレッドが、その時間帯の過去中央値の何倍か           |
//|   2. ATRベースの想定変動幅と、それがスプレッドの何倍か           |
//|   3. スプレッドが最も開く時間帯(ロールオーバー)までの残り時間   |
//|   4. 上記から導いた 3 段階の判定                                  |
//|                                                                  |
//| スプレッドの履歴は MqlRates の spread フィールドから、            |
//| 表示中の口座・銘柄について実測で集計します。                      |
//| 外部データも DLL も使いません。                                   |
//|                                                                  |
//| 売買シグナルは出しません。判断は利用者が行うための道具です。      |
//+------------------------------------------------------------------+
#property copyright "iq87jun-star"
#property link      "https://www.gogojungle.co.jp/"
#property version   "1.01"
#property description "定石 零 ─ 環境計: スプレッド割高度・想定変動幅・時間帯コストを可視化します。売買シグナルは出しません。"
#property indicator_chart_window
#property strict

//--- 時間帯一覧の出し方
enum ENUM_HOUR_TABLE
  {
   HT_OFF = 0,   // 出さない
   HT_TOP,       // スプレッドが開く時間帯の上位のみ + 現在
   HT_ALL        // 24時間すべて
  };

//--- 表示位置
enum ENUM_PANEL_CORNER
  {
   PC_LEFT_UPPER  = 0,  // 左上
   PC_RIGHT_UPPER = 1,  // 右上
   PC_LEFT_LOWER  = 2,  // 左下
   PC_RIGHT_LOWER = 3   // 右下
  };

//=== 集計設定 =======================================================
input int    InpLookbackDays   = 60;    // スプレッド集計に使う日数
input int    InpAtrPeriod      = 14;    // 想定変動幅に使うATR期間

//=== 判定のしきい値 =================================================
input double InpRatioCaution   = 1.5;   // 割高度: これ以上で「警戒」
input double InpRatioAvoid     = 2.5;   // 割高度: これ以上で「回避」
input double InpMoveCostMin    = 8.0;   // 変動幅/スプレッド: これ未満で「回避」

//=== 表示設定 =======================================================
input ENUM_PANEL_CORNER InpCorner = PC_LEFT_UPPER; // パネルの位置
input int    InpX              = 12;    // 横のオフセット(px)
input int    InpY              = 22;    // 縦のオフセット(px)
input int    InpFontSize       = 9;     // 文字サイズ
input string InpFontName       = "Meiryo UI"; // フォント
input color  InpColText        = clrGainsboro; // 通常の文字色
input color  InpColHead        = clrWhite;     // 見出しの色
input color  InpColGood        = clrLimeGreen; // 良好
input color  InpColCaution     = clrGold;      // 警戒
input color  InpColAvoid       = clrTomato;    // 回避
input ENUM_HOUR_TABLE InpHourTable = HT_TOP; // 時間帯一覧の出し方
input int    InpHourTableTop    = 5;     // 「上位のみ」のときに出す本数
input bool   InpShowBackdrop    = true;  // 文字の背景に下地を敷く(推奨)
input color  InpColBackdrop     = C'12,12,16'; // 下地の色
input int    InpBackdropWidth   = 330;   // 下地の幅(px)

//--- 内部
#define PANEL_PREFIX "ChienCM101_"
#define MAX_PER_HOUR 512
#define MIN_SAMPLES  2      // 1時間帯あたり最低これだけの本数が要る
#define LINES        14

double   g_medSpread[24];      // 時間帯別のスプレッド中央値(pips)
bool     g_medValid  = false;
int      g_worstHour = -1;
double   g_pip       = 0.0001;
int      g_hoursReady  = 0;    // 中央値を出せた時間帯の数
int      g_barsGot     = 0;    // 取得できたH1バー数
datetime g_lastRebuild = 0;
datetime g_lastDraw    = 0;
int      g_buf[24][MAX_PER_HOUR];   // 時間帯別スプレッド(集計用)

//+------------------------------------------------------------------+
int OnInit()
  {
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   g_pip = (digits == 3 || digits == 5) ? point * 10.0 : point;
   if(g_pip <= 0.0) g_pip = 0.0001;

   for(int i = 0; i < 24; i++) g_medSpread[i] = 0.0;

   IndicatorShortName("定石 零 ─ 環境計");
   CreateLabels();
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
                const double &high[], const double &low[],
                const double &close[], const long &tick_volume[],
                const long &volume[], const int &spread[])
  {
   // スプレッド分布は1時間に一度だけ組み直す(毎ティックでは重い)
   datetime now = TimeCurrent();
   if(!g_medValid ? (now - g_lastRebuild >= 60) : (now - g_lastRebuild >= 3600))
     {
      BuildSpreadProfile();
      g_lastRebuild = now;
     }

   // 描画は1秒に一度で十分
   if(now != g_lastDraw)
     {
      Draw();
      g_lastDraw = now;
     }
   return(rates_total);
  }

//+------------------------------------------------------------------+
//| 時間帯別スプレッド中央値を、実際のバー履歴から集計する            |
//+------------------------------------------------------------------+
void BuildSpreadProfile()
  {
   g_medValid = false;
   g_worstHour = -1;

   int bars = InpLookbackDays * 24;
   if(bars < 24) bars = 24;

   MqlRates r[];
   ArraySetAsSeries(r, false);
   int got = CopyRates(_Symbol, PERIOD_H1, 0, bars, r);
   if(got <= 0)
      return;

   int cnt[24];
   for(int h = 0; h < 24; h++) cnt[h] = 0;

   MqlDateTime dt;
   for(int i = 0; i < got; i++)
     {
      if(r[i].spread <= 0) continue;
      TimeToStruct(r[i].time, dt);
      int h = dt.hour;
      if(h < 0 || h > 23) continue;
      if(cnt[h] >= MAX_PER_HOUR) continue;
      g_buf[h][cnt[h]] = (int)r[i].spread;
      cnt[h]++;
     }

   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double worst = -1.0;
   int filled = 0;

   for(int h = 0; h < 24; h++)
     {
      if(cnt[h] < MIN_SAMPLES) { g_medSpread[h] = 0.0; continue; }

      // 挿入ソート(1時間あたり最大512件なので十分)
      for(int a = 1; a < cnt[h]; a++)
        {
         int key = g_buf[h][a];
         int b = a - 1;
         while(b >= 0 && g_buf[h][b] > key) { g_buf[h][b + 1] = g_buf[h][b]; b--; }
         g_buf[h][b + 1] = key;
        }

      double medPoints;
      if(cnt[h] % 2 == 1)
         medPoints = (double)g_buf[h][cnt[h] / 2];
      else
         medPoints = (g_buf[h][cnt[h] / 2 - 1] + g_buf[h][cnt[h] / 2]) / 2.0;

      g_medSpread[h] = medPoints * point / g_pip;
      filled++;
      if(g_medSpread[h] > worst) { worst = g_medSpread[h]; g_worstHour = h; }
     }

   g_hoursReady = filled;
   g_barsGot    = got;
   g_medValid   = (filled >= 8);
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

   for(int i = 0; i < LINES + 24; i++)
     {
      string n = PANEL_PREFIX + IntegerToString(i);
      if(!ObjectCreate(0, n, OBJ_LABEL, 0, 0, 0)) continue;
      ObjectSetInteger(0, n, OBJPROP_CORNER, CornerOf());
      ObjectSetInteger(0, n, OBJPROP_XDISTANCE, InpX);
      ObjectSetInteger(0, n, OBJPROP_YDISTANCE, InpY + i * (InpFontSize + 6));
      ObjectSetInteger(0, n, OBJPROP_FONTSIZE, InpFontSize);
      ObjectSetString(0, n, OBJPROP_FONT, InpFontName);
      ObjectSetInteger(0, n, OBJPROP_COLOR, InpColText);
      ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, n, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, n, OBJPROP_BACK, false);
      ObjectSetInteger(0, n, OBJPROP_TIMEFRAMES, OBJ_NO_PERIODS);
      ObjectSetInteger(0, n, OBJPROP_ANCHOR,
                       (InpCorner == PC_RIGHT_UPPER || InpCorner == PC_RIGHT_LOWER)
                       ? ANCHOR_RIGHT_UPPER : ANCHOR_LEFT_UPPER);
      ObjectSetString(0, n, OBJPROP_TEXT, "");
     }
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
   string n = PANEL_PREFIX + IntegerToString(idx);
   if(ObjectFind(0, n) < 0) return;
   // 空文字のラベルは既定文字 "Label" で描画されてしまうため、
   // 使わない行は時間足フィルタで非表示にする
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
void Draw()
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   int hour = dt.hour;

   double point   = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double curSpr  = (double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) * point / g_pip;
   double medNow  = (g_medValid && g_medSpread[hour] > 0.0) ? g_medSpread[hour] : 0.0;
   double ratio   = (medNow > 0.0) ? curSpr / medNow : 0.0;

   double atrVal  = iATR(_Symbol, _Period, InpAtrPeriod, 0);
   double atrPips = (atrVal > 0.0) ? atrVal / g_pip : 0.0;
   double moveCost = (curSpr > 0.0) ? atrPips / curSpr : 0.0;

   int i = 0;
   SetLine(i++, "定石 零 ─ 環境計  v1.01", InpColHead);
   SetLine(i++, StringFormat("%s  %s   %02d:%02d サーバー時刻",
                _Symbol, PeriodName(), dt.hour, dt.min), InpColText);
   SetLine(i++, " ", InpColText);

   // --- スプレッド
   SetLine(i++, StringFormat("スプレッド        %.1f pips", curSpr), InpColHead);
   if(!g_medValid)
     {
      SetLine(i++, StringFormat("  履歴が不足(H1 %d本 / %d時間帯が集計済)",
              g_barsGot, g_hoursReady), InpColCaution);
      SetLine(i++, "  H1チャートで Home キーを押し履歴を読み込んでください", InpColCaution);
     }
   else
     {
      SetLine(i++, StringFormat("  この時間帯の中央値  %.1f pips", medNow), InpColText);
      color rc = InpColGood;
      string rt = "適正";
      if(ratio >= InpRatioAvoid)        { rc = InpColAvoid;   rt = "回避推奨"; }
      else if(ratio >= InpRatioCaution) { rc = InpColCaution; rt = "割高"; }
      SetLine(i++, StringFormat("  割高度  %.2f 倍   %s", ratio, rt), rc);
     }

   // --- 想定変動幅
   SetLine(i++, StringFormat("想定変動幅 ATR(%d)  %.1f pips", InpAtrPeriod, atrPips),
           InpColHead);
   color mc = InpColGood;
   string mt = "十分";
   if(moveCost > 0.0 && moveCost < InpMoveCostMin) { mc = InpColAvoid; mt = "不足"; }
   else if(moveCost > 0.0 && moveCost < InpMoveCostMin * 1.5) { mc = InpColCaution; mt = "やや不足"; }
   SetLine(i++, StringFormat("  変動幅 / スプレッド  %.1f 倍   %s", moveCost, mt), mc);

   // --- ロールオーバー
   if(g_medValid && g_worstHour >= 0)
     {
      int togo = (g_worstHour - hour + 24) % 24;
      SetLine(i++, StringFormat("最もスプレッドが開く時間帯  %02d:00", g_worstHour),
              InpColHead);
      SetLine(i++, StringFormat("  中央値 %.1f pips / あと %d 時間",
              g_medSpread[g_worstHour], togo),
              (togo <= 1) ? InpColAvoid : InpColText);
     }
   else
     {
      SetLine(i++, " ", InpColText);
      SetLine(i++, " ", InpColText);
     }

   // --- 総合判定
   SetLine(i++, " ", InpColText);
   int score = 0;   // 0=良好 1=警戒 2=回避
   if(g_medValid)
     {
      if(ratio >= InpRatioAvoid) score = 2;
      else if(ratio >= InpRatioCaution) score = 1;
     }
   if(moveCost > 0.0 && moveCost < InpMoveCostMin) score = 2;
   else if(moveCost > 0.0 && moveCost < InpMoveCostMin * 1.5 && score < 1) score = 1;

   string vtext = "○  コスト条件は良好";
   color  vcol  = InpColGood;
   if(score == 1)      { vtext = "△  コスト警戒";   vcol = InpColCaution; }
   else if(score == 2) { vtext = "×  コストが割高"; vcol = InpColAvoid; }
   // スプレッド分布が未集計のうちは、判定の半分が欠けている。良好と言い切らない
   if(!g_medValid)     { vtext = "─  判定できません(履歴の集計待ち)"; vcol = InpColCaution; }
   SetLine(i++, StringFormat("判定   %s", vtext), vcol);

   // --- 時間帯一覧
   if(InpHourTable != HT_OFF && g_medValid)
     {
      SetLine(i++, " ", InpColText);
      SetLine(i++, (InpHourTable == HT_ALL)
                   ? StringFormat("時間帯別スプレッド中央値 (pips) ─ 直近%d日分",
                                  (int)MathRound(g_barsGot / 24.0))
                   : StringFormat("スプレッドが開く時間帯 上位%d ─ 直近%d日分",
                                  InpHourTableTop, (int)MathRound(g_barsGot / 24.0)),
              InpColHead);

      // 表示する時間を決める
      bool show[24];
      for(int h = 0; h < 24; h++) show[h] = (InpHourTable == HT_ALL);

      if(InpHourTable == HT_TOP)
        {
         // 中央値の大きい順に InpHourTableTop 個を選ぶ
         int n = MathMax(1, MathMin(24, InpHourTableTop));
         for(int k = 0; k < n; k++)
           {
            int best = -1; double bv = -1.0;
            for(int h = 0; h < 24; h++)
              {
               if(show[h] || g_medSpread[h] <= 0.0) continue;
               if(g_medSpread[h] > bv) { bv = g_medSpread[h]; best = h; }
              }
            if(best < 0) break;
            show[best] = true;
           }
         if(g_medSpread[hour] > 0.0) show[hour] = true;   // 現在の時間帯は必ず出す
        }

      for(int h = 0; h < 24; h++)
        {
         if(!show[h] || g_medSpread[h] <= 0.0) continue;
         string bar = "";
         int len = (int)MathRound(g_medSpread[h]
                   / MathMax(g_medSpread[g_worstHour], 0.01) * 18.0);
         for(int k = 0; k < len; k++) bar += "|";
         color hc = (h == hour) ? InpColHead
                  : (h == g_worstHour ? InpColAvoid : InpColText);
         string tag = (h == hour) ? " ←今" : "";
         SetLine(i++, StringFormat("  %02d  %5.1f  %s%s", h, g_medSpread[h], bar, tag), hc);
        }
     }

   // 下地の高さに使うため、実際に使った行数をここで控える
   int used = i;

   // 余った行を消す
   for(; i < LINES + 24; i++) SetLine(i, "", InpColText);

   // 下地を実際に使った行数に合わせる
   if(InpShowBackdrop)
     {
      string bg = PANEL_PREFIX + "BG";
      if(ObjectFind(0, bg) >= 0)
         ObjectSetInteger(0, bg, OBJPROP_YSIZE, used * (InpFontSize + 6) + 14);
     }

   ChartRedraw();
  }

//+------------------------------------------------------------------+
string PeriodName()
  {
   switch(_Period)
     {
      case PERIOD_M1:  return("M1");   case PERIOD_M5:  return("M5");
      case PERIOD_M15: return("M15");  case PERIOD_M30: return("M30");
      case PERIOD_H1:  return("H1");   case PERIOD_H4:  return("H4");
      case PERIOD_D1:  return("D1");   case PERIOD_W1:  return("W1");
      case PERIOD_MN1: return("MN1");
     }
   return("TF" + IntegerToString(_Period));
  }
//+------------------------------------------------------------------+
