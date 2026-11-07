# -*- coding: utf-8 -*-
"""docs/322 Q111(2026-10-07 ユーザー「EA を変更したいので、記録版を作成してください」): 配備中 EA の「記録版」を別ファイル(版 +0.01)として生成する。
やること(各 EA に同じ加工・手で書かない):
  1. Print(...) / PrintFormat(...) を ChienLog(...) / ChienLog(StringFormat(...)) に置換(端末ログはそのまま出る + 送信キューに積む)
  2. #include の直後に Q111 ブロック(InpLogUrl・キュー・WebRequest 送信・毎時スナップショット・決済取引の送信)を挿入
  3. OnInit 末尾(EventSetTimer の直後)に ChienLogInit()、OnDeinit に ChienLogDeinit()、OnTimer 先頭に ChienLogTimer()
  4. #property version を +0.01 し、ファイル名に _vX.YY を付ける。manifest・docs/241 は変えない(切替はユーザーの「切替」後)。
実行: cd research && python3 queue/q111_make_log_versions.py   → mql5/ に 10 本生成。再実行は冪等(同名を上書き)。"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE)); MQL = os.path.join(ROOT, "mql5")
DATE = "2026-10-07"
BASES = [   # (元ファイル, 新版番号)
    ("【Fintokeiスイング_トパーズ3500万_口座6104739】EA11_Mon4x2.0+Roll5x1.0+NonFX0.5_v1.11.mq5", "1.12"),
    ("【Fintokeiスイング_ルビー1000万_口座6104736】RecentFit_B案_4.0倍_v1.01.mq5", "1.02"),
    ("【Fintokeiパール500万】RecentFit_4.0倍_v1.07.mq5", "1.08"),
    ("【FTMO50k_口座521100397】EA8_Mon4_3.3倍+GER40ブレイク_2.0倍.mq5", "1.35"),
    ("【FTMO50k_口座531407058】EA3_Mon4_3.3倍.mq5", "1.17"),
    ("【FN_Instant20k_口座11988011】RecentFit_G_Mon2x4+MonNAS100_US500x1.mq5", "1.16"),
    ("【FN100k_口座14074882】RecentFit_Mon3x4+HoldXAU0.4_ギャンブル.mq5", "1.10"),
    ("【FN100k_口座14166201】RecentFit_NonFX_1.48倍+Roll5_3.0倍.mq5", "1.32"),
    ("【FTMO100k_口座531343523_宝くじ】EA10L_Mon4_3.3倍+GER40ブレイク_2.0倍+HoldXAU0.3.mq5", "1.02"),
    ("【FTMO100k_1Step_口座531466484】EA9_A案_HoldXAU+MonGBPJPY+MonNAS100_1.5倍.mq5", "1.01"),
]

BLOCK = r'''
//==================================================================
// Q111(docs/327・{date}): VPS ログ送信。EA の Print/PrintFormat は ChienLog 経由(端末ログはそのまま)で
// 送信キューに積まれ、InpLogUrl(Google Apps Script の /exec)へ HTTPS POST される。送信失敗は取引に影響させない。
// 送る物: LOG(ログ行)・SNAP(毎時: 残高/有効証拠金/証拠金/建玉)・DEAL(約定: 理由 SL/TP/EXPERT 等)・INIT/DEINIT。
// 事前準備: ツール→オプション→エキスパート「WebRequest を許可する URL」に https://script.google.com と
//           https://script.googleusercontent.com を追加してから VPS へ移行(設定は移行時に写る)。InpLogUrl 空 = 送信しない。
//==================================================================
#define CHIEN_EA_VERSION "{ver}"
#define CHIEN_LOG_MAXQ   200
input string InpLogUrl         = "";    // Q111 ログ送信先 URL(Apps Script /exec・空=送信しない)
input int    InpLogSnapshotMin = 60;    // Q111 スナップショット間隔(分)
input int    InpLogTimeoutMs   = 2000;  // Q111 WebRequest タイムアウト(ms)
string   g_clQ[];
int      g_clN=0, g_clFail=0;
datetime g_clLastSend=0, g_clLastSnap=0, g_clLastWarn=0;
ulong    g_clLastDealTk=0;
string   g_clTag="";

string ChienCsv(string s){ StringReplace(s,"\"","\"\""); StringReplace(s,"\r"," "); StringReplace(s,"\n"," "); return "\""+s+"\""; }
void ChienPush(string kind,string text){
   if(InpLogUrl=="") return;
   string line=IntegerToString((long)AccountInfoInteger(ACCOUNT_LOGIN))+","+TimeToString(TimeGMT(),TIME_DATE|TIME_SECONDS)+","+TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS)+","+kind+","+ChienCsv(g_clTag)+","+ChienCsv(text);
   if(g_clN>=CHIEN_LOG_MAXQ){ for(int i=1;i<g_clN;i++) g_clQ[i-1]=g_clQ[i]; g_clN--; }
   if(ArraySize(g_clQ)<g_clN+1) ArrayResize(g_clQ,g_clN+1,64);
   g_clQ[g_clN]=line; g_clN++;
}
void ChienLog(string s){ Print(s); ChienPush("LOG",StringSubstr(s,0,400)); }
void ChienLog(string a,string b){ ChienLog(a+b); }
bool ChienSend(string body){
   char data[]; char res[]; string rh;
   int n=StringToCharArray(body,data,0,WHOLE_ARRAY,CP_UTF8);
   if(n>0 && data[n-1]==0) ArrayResize(data,n-1);
   ResetLastError();
   int code=WebRequest("POST",InpLogUrl,"Content-Type: text/plain; charset=utf-8\r\n",InpLogTimeoutMs,data,res,rh);
   if(code==200 || code==201 || code==302) return true;
   int err=GetLastError();
   if(TimeCurrent()-g_clLastWarn>3600){ g_clLastWarn=TimeCurrent();
      if(err==4014) Print("[LOG SEND] WebRequest 不許可(err 4014): オプション→エキスパートの許可 URL に https://script.google.com と https://script.googleusercontent.com を追加して再移行");
      else PrintFormat("[LOG SEND] 失敗 code=%d err=%d(取引には影響しない)",code,err); }
   return false;
}
void ChienFlush(bool force){
   if(InpLogUrl=="" || g_clN==0) return;
   datetime now=TimeCurrent();
   if(!force && now-g_clLastSend<60 && g_clN<20) return;
   if(!force && g_clFail>=3 && now-g_clLastSend<600) return;
   string body=""; int k=0;
   for(;k<g_clN && k<100;k++) body+=g_clQ[k]+"\n";
   g_clLastSend=now;
   if(ChienSend(body)){ int rest=g_clN-k; for(int i=0;i<rest;i++) g_clQ[i]=g_clQ[i+k]; g_clN=rest; g_clFail=0; }
   else g_clFail++;
}
void ChienSnapshot(){
   if(InpLogUrl=="") return;
   datetime now=TimeCurrent();
   if(g_clLastSnap!=0 && now-g_clLastSnap<InpLogSnapshotMin*60) return;
   g_clLastSnap=now;
   string pos=""; int n=PositionsTotal();
   for(int i=0;i<n;i++){ ulong tk=PositionGetTicket(i); if(tk==0 || !PositionSelectByTicket(tk)) continue;
      pos+=StringFormat("%s|%s|%.2f|%.5f|%.2f|%I64d|%s;",PositionGetString(POSITION_SYMBOL),(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?"buy":"sell"),
           PositionGetDouble(POSITION_VOLUME),PositionGetDouble(POSITION_PRICE_OPEN),PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP),
           PositionGetInteger(POSITION_MAGIC),PositionGetString(POSITION_COMMENT)); }
   ChienPush("SNAP",StringFormat("balance=%.2f equity=%.2f margin=%.2f free=%.2f positions=%d %s",
      AccountInfoDouble(ACCOUNT_BALANCE),AccountInfoDouble(ACCOUNT_EQUITY),AccountInfoDouble(ACCOUNT_MARGIN),AccountInfoDouble(ACCOUNT_MARGIN_FREE),n,pos));
}
void ChienDeals(){
   if(InpLogUrl=="") return;
   datetime now=TimeCurrent();
   if(!HistorySelect(now-7*86400,now+3600)) return;
   int n=HistoryDealsTotal(); ulong mx=g_clLastDealTk;
   for(int i=0;i<n;i++){ ulong d=HistoryDealGetTicket(i); if(d==0) continue;
      if(g_clLastDealTk==0){ if(d>mx) mx=d; continue; }
      if(d<=g_clLastDealTk) continue;
      if(d>mx) mx=d;
      long type=HistoryDealGetInteger(d,DEAL_TYPE); if(type!=DEAL_TYPE_BUY && type!=DEAL_TYPE_SELL) continue;
      long entry=HistoryDealGetInteger(d,DEAL_ENTRY); long reason=HistoryDealGetInteger(d,DEAL_REASON);
      string rs=(reason==DEAL_REASON_SL?"SL":reason==DEAL_REASON_TP?"TP":reason==DEAL_REASON_SO?"STOPOUT":reason==DEAL_REASON_EXPERT?"EXPERT":
                 reason==DEAL_REASON_CLIENT?"CLIENT":reason==DEAL_REASON_MOBILE?"MOBILE":reason==DEAL_REASON_WEB?"WEB":"OTHER");
      string en=(entry==DEAL_ENTRY_IN?"IN":entry==DEAL_ENTRY_OUT?"OUT":entry==DEAL_ENTRY_INOUT?"INOUT":"OUTBY");
      ChienPush("DEAL",StringFormat("deal=%I64u pos=%I64d %s %s %s vol=%.2f price=%.5f profit=%.2f comm=%.2f swap=%.2f magic=%I64d reason=%s time=%s comment=%s",
         d,HistoryDealGetInteger(d,DEAL_POSITION_ID),en,HistoryDealGetString(d,DEAL_SYMBOL),(type==DEAL_TYPE_BUY?"buy":"sell"),
         HistoryDealGetDouble(d,DEAL_VOLUME),HistoryDealGetDouble(d,DEAL_PRICE),HistoryDealGetDouble(d,DEAL_PROFIT),HistoryDealGetDouble(d,DEAL_COMMISSION),
         HistoryDealGetDouble(d,DEAL_SWAP),HistoryDealGetInteger(d,DEAL_MAGIC),rs,TimeToString((datetime)HistoryDealGetInteger(d,DEAL_TIME),TIME_DATE|TIME_SECONDS),
         HistoryDealGetString(d,DEAL_COMMENT)));
   }
   if(g_clLastDealTk==0) g_clLastDealTk=(mx==0?1:mx); else g_clLastDealTk=mx;
}
void ChienLogTimer(){ if(InpLogUrl=="") return; ChienDeals(); ChienSnapshot(); ChienFlush(false); }
void ChienLogInit(){
   g_clTag=MQLInfoString(MQL_PROGRAM_NAME)+" v"+CHIEN_EA_VERSION;
   if(InpLogUrl==""){ Print("[LOG] InpLogUrl が空 → VPS ログ送信なし(Q111)"); return; }
   ChienDeals();
   ChienPush("INIT",StringFormat("server=%s currency=%s balance=%.2f equity=%.2f build=%d",AccountInfoString(ACCOUNT_SERVER),AccountInfoString(ACCOUNT_CURRENCY),
      AccountInfoDouble(ACCOUNT_BALANCE),AccountInfoDouble(ACCOUNT_EQUITY),(int)TerminalInfoInteger(TERMINAL_BUILD)));
   g_clLastSnap=0; ChienSnapshot(); ChienFlush(true);
   Print("[LOG] VPS ログ送信 有効(Q111) → ",InpLogUrl);
}
void ChienLogDeinit(){ if(InpLogUrl=="") return; ChienPush("DEINIT",StringFormat("reason=%d",UninitializeReason())); ChienFlush(true); }
//================================================================== Q111 ここまで
'''


def replace_calls(src, name, repl_open, add_close):
    """name( ... ) を repl_open ... ) [+ ')'] に置換(括弧対応・文字列リテラル考慮)。識別子の一部(PrintFormat の Print)は触らない。"""
    out = []; i = 0; n = len(src); cnt = 0
    while i < n:
        j = src.find(name + "(", i)
        if j < 0: out.append(src[i:]); break
        prev = src[j - 1] if j > 0 else " "
        if prev.isalnum() or prev == "_":   # 識別子の一部
            out.append(src[i:j + len(name)]); i = j + len(name); continue
        # 行コメント内は無視
        ls = src.rfind("\n", 0, j) + 1
        if "//" in src[ls:j] and not ('"' in src[ls:j]):
            out.append(src[i:j + len(name) + 1]); i = j + len(name) + 1; continue
        k = j + len(name) + 1; depth = 1; instr = False
        while k < n and depth > 0:
            c = src[k]
            if instr:
                if c == "\\": k += 1
                elif c == '"': instr = False
            else:
                if c == '"': instr = True
                elif c == "(": depth += 1
                elif c == ")": depth -= 1
            k += 1
        out.append(src[i:j]); out.append(repl_open); out.append(src[j + len(name) + 1:k - 1]); out.append(")" + (")" if add_close else ""))
        i = k; cnt += 1
    return "".join(out), cnt


def make(base, ver):
    p = os.path.join(MQL, base); s = open(p, encoding="utf-8").read()
    m = re.search(r'#property version\s+"(\d+\.\d+)"', s); old = m.group(1)
    assert old != ver and "ChienLog" not in s, base
    s, n1 = replace_calls(s, "PrintFormat", "ChienLog(StringFormat(", True)
    s, n2 = replace_calls(s, "Print", "ChienLog(", False)
    s = s.replace(m.group(0), f'#property version   "{ver}"   // v{ver}({DATE}・Q111 docs/327): VPS ログ送信(InpLogUrl・Apps Script)を追加。取引ロジックは v{old} と同一', 1)
    inc = "#include <Trade/PositionInfo.mqh>"; assert s.count(inc) == 1, base
    s = s.replace(inc, inc + "\n" + BLOCK.replace("{date}", DATE).replace("{ver}", ver), 1)
    assert s.count("EventSetTimer(30);") == 1 and s.count("EventKillTimer();") == 1 and s.count("void OnTimer()\n{") == 1, base
    s = s.replace("EventSetTimer(30);", "EventSetTimer(30);\n   ChienLogInit();   // Q111", 1)
    s = s.replace("EventKillTimer();", "ChienLogDeinit();   // Q111\n   EventKillTimer();", 1)
    s = s.replace("void OnTimer()\n{", "void OnTimer()\n{\n   ChienLogTimer();   // Q111: 約定・スナップショット・送信(30 秒ごと・失敗は無視)", 1)
    name = re.sub(r"_v\d+\.\d+\.mq5$", "", base)[:-4] if not re.search(r"_v\d+\.\d+\.mq5$", base) else re.sub(r"_v\d+\.\d+\.mq5$", "", base)
    out = f"{name}_v{ver}.mq5"; open(os.path.join(MQL, out), "w", encoding="utf-8", newline="").write(s)
    # 静的検査: 括弧の数(文字列外・コメント内の括弧は元ファイルと同数なので差分 0 を要求)
    def pdepth(t):
        depth = 0; instr = False; k = 0
        while k < len(t):
            c = t[k]
            if instr:
                if c == "\\": k += 1
                elif c == '"': instr = False
            else:
                if c == '"': instr = True
                elif c == "(": depth += 1
                elif c == ")": depth -= 1
            k += 1
        return depth
    base_depth = pdepth(open(p, encoding="utf-8").read()); blk_depth = pdepth(BLOCK)
    assert pdepth(s) == base_depth + blk_depth, f"paren {out} {pdepth(s)} vs {base_depth}+{blk_depth}"
    print(f"{out}  (v{old}→v{ver}  PrintFormat {n1} / Print {n2} 置換)")
    return out


if __name__ == "__main__":
    for b, v in BASES: make(b, v)
