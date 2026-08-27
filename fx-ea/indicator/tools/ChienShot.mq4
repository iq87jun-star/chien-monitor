//+------------------------------------------------------------------+
//|                                                   ChienShot.mq4  |
//|                                                                  |
//| チャートだけを画像として保存するスクリプト。                      |
//|                                                                  |
//| Windowsの画面キャプチャと違い、次のものが写りません:              |
//|   ・タイトルバー(口座番号・業者名)                              |
//|   ・タスクバー / 受信トレイ / 気配値表示                          |
//| チャート領域だけが、指定した大きさで保存されます。                |
//|                                                                  |
//| 使い方: チャートにドラッグするだけ。                              |
//| 保存先: MQL4\Files\(データフォルダは ファイル→データフォルダを開く)|
//+------------------------------------------------------------------+
#property copyright "iq87jun-star"
#property version   "1.00"
#property strict
#property script_show_inputs
#property description "チャートだけを画像として保存します。口座番号やタスクバーは写りません。"

//--- 出力する大きさ(商品ページ用は横1280〜1920が扱いやすい)
input int    InpWidth    = 1600;   // 横幅(px)
input int    InpHeight   = 1000;   // 高さ(px)
input string InpPrefix   = "chien"; // ファイル名の先頭
input bool   InpAddStamp = true;    // ファイル名に銘柄・時間足・日時を入れる

//+------------------------------------------------------------------+
void OnStart()
  {
   if(InpWidth < 200 || InpHeight < 200)
     {
      Alert("大きさが小さすぎます。横・縦とも200以上にしてください。");
      return;
     }

   string name = InpPrefix;
   if(InpAddStamp)
     {
      MqlDateTime dt;
      TimeToStruct(TimeLocal(), dt);
      name += StringFormat("_%s_%s_%04d%02d%02d_%02d%02d%02d",
                           _Symbol, PeriodName(),
                           dt.year, dt.mon, dt.day, dt.hour, dt.min, dt.sec);
     }
   name += ".png";

   if(!ChartScreenShot(0, name, InpWidth, InpHeight, ALIGN_RIGHT))
     {
      Alert("保存に失敗しました。エラー ", GetLastError());
      return;
     }

   PrintFormat("保存しました: MQL4\\Files\\%s  (%d x %d)", name, InpWidth, InpHeight);
   Alert("保存しました\n\nMQL4\\Files\\" + name +
         "\n\nファイル → データフォルダを開く → MQL4 → Files");
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
   return("TF");
  }
//+------------------------------------------------------------------+
