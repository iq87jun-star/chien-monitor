#!/usr/bin/env python3
"""MQL ソースの静的検査。コンパイラがない環境で、出す前に潰せるものを潰す。

  python3 mqlcheck.py <file.mq4|file.mq5> [...]

見るもの:
  1. 括弧の対応
  2. StringFormat の書式指定子と引数の個数が合っているか
     — **コンパイラは通してしまうのに表示が壊れる**ため、ここが本命
  3. SetLine(i++) の最大呼び出し回数が LINES を超えていないか
  4. 定義されていない自作関数を呼んでいないか
  5. 宣言したのに一度も使っていないグローバル変数
  6. input のコメント(MetaTraderの設定画面に出る説明)の有無
"""
import re, sys, os

# MQL4/MQL5 の組み込み。ここに漏れがあると「定義が見つからない」の誤検出になる。
# 出品済みでコンパイル実績のあるソース(環境計・待ち伏せ)で誤検出0になるまで足した。
BUILTIN = {
    # 制御構文
    "if","for","while","switch","return","sizeof","case",
    # 入出力・通知
    "Print","PrintFormat","Alert","Comment","SendMail","SendNotification",
    "FileOpen","FileClose","FileWrite","FileReadNumber","FileIsExist","FileIsEnding",
    "FileReadString","FileWriteString","FileDelete","FileSeek",
    # 文字列
    "StringFormat","StringSubstr","StringLen","StringConcatenate","StringTrimRight",
    "StringTrimLeft","StringFind","StringReplace","StringToDouble","StringToInteger",
    "IntegerToString","DoubleToString","TimeToString","StringSplit","EnumToString",
    # 配列
    "ArrayResize","ArraySetAsSeries","ArraySort","ArraySize","ArrayCopy","ArrayInitialize",
    "ArrayFree","ArrayMaximum","ArrayMinimum","ArrayFill","ArrayRange",
    # 相場データ
    "CopyRates","CopyBuffer","CopyHigh","CopyLow","CopyClose","CopyOpen","CopyTime",
    "iTime","iOpen","iHigh","iLow","iClose","iVolume","iBars","iBarShift","Bars",
    "SeriesInfoInteger","SymbolInfoDouble","SymbolInfoInteger","SymbolInfoString",
    "MarketInfo","RefreshRates",
    # 指標
    "iATR","iRSI","iMA","iStdDev","iCCI","iMACD","iStochastic","iADX","iBands",
    "IndicatorRelease","IndicatorSetString","IndicatorSetInteger","IndicatorShortName",
    "IndicatorBuffers","IndicatorDigits","SetIndexBuffer","SetIndexStyle","SetIndexLabel",
    "SetIndexArrow","SetIndexEmptyValue","SetIndexShift","SetIndexDrawBegin",
    "PlotIndexSetDouble","PlotIndexSetInteger","PlotIndexSetString",
    # オブジェクト
    "ObjectCreate","ObjectDelete","ObjectFind","ObjectsDeleteAll","ObjectSetInteger",
    "ObjectSetString","ObjectSetDouble","ObjectGetInteger","ObjectGetString",
    "ObjectGetDouble","ObjectMove","ObjectsTotal","ObjectName",
    # チャート・時刻
    "ChartRedraw","ChartGetInteger","ChartSetInteger","ChartID","WindowRedraw",
    "TimeToStruct","TimeCurrent","TimeLocal","TimeGMT","StructToTime",
    # 数学
    "MathMin","MathMax","MathAbs","MathSqrt","MathRound","MathFloor","MathCeil",
    "MathPow","MathLog","MathExp","MathMod","MathRand","MathSrand","NormalizeDouble",
    # 口座・注文(将来EA側にも当てられるように)
    "AccountInfoDouble","AccountInfoInteger","OrderSend","OrderSelect","OrdersTotal",
    "PositionSelect","PositionsTotal","PositionGetDouble","PositionGetInteger",
    "GetLastError","ResetLastError","Sleep","EventSetTimer","EventKillTimer",
}
# 書式指定子。%% は文字としての % なので数えない
FMT = re.compile(r"%(?!%)[-+ #0]*[\d*]*(?:\.\d+)?[difFeEgGsSuxXocpn]")


def split_args(s):
    """トップレベルのカンマで分割する(入れ子の括弧・文字列は無視)。"""
    out, cur, depth, q = [], "", 0, None
    i = 0
    while i < len(s):
        ch = s[i]
        if q:
            cur += ch
            if ch == "\\": cur += s[i+1] if i+1 < len(s) else ""; i += 2; continue
            if ch == q: q = None
        elif ch in "\"'":
            q = ch; cur += ch
        elif ch in "([": depth += 1; cur += ch
        elif ch in ")]": depth -= 1; cur += ch
        elif ch == "," and depth == 0:
            out.append(cur); cur = ""
        else:
            cur += ch
        i += 1
    if cur.strip(): out.append(cur)
    return out


def find_calls(src, name):
    """name(...) の呼び出しを (行番号, 引数文字列) で返す。"""
    res = []
    for m in re.finditer(r"\b" + name + r"\s*\(", src):
        i = m.end(); depth = 1; q = None; start = i
        while i < len(src) and depth:
            ch = src[i]
            if q:
                if ch == "\\": i += 2; continue
                if ch == q: q = None
            elif ch in "\"'": q = ch
            elif ch == "(": depth += 1
            elif ch == ")": depth -= 1
            i += 1
        res.append((src[:m.start()].count("\n") + 1, src[start:i-1]))
    return res


def strip_noise(src):
    """コメントと文字列リテラルを空白に潰す。中身を識別子として拾わないため。"""
    out, i, n = [], 0, len(src)
    while i < n:
        two = src[i:i+2]
        if two == "//":
            j = src.find("\n", i); j = n if j < 0 else j
            out.append(" " * (j - i)); i = j
        elif two == "/*":
            j = src.find("*/", i + 2); j = n if j < 0 else j + 2
            out.append(" " * (j - i)); i = j
        elif src[i] in "\"'":
            q = src[i]; j = i + 1
            while j < n and src[j] != q:
                j += 2 if src[j] == "\\" else 1
            j = min(j + 1, n)
            out.append(" " * (j - i)); i = j
        else:
            out.append(src[i]); i += 1
    return "".join(out)


def check(path):
    src = open(path, encoding="utf-8").read()
    code = strip_noise(src)
    bad = []
    say = lambda msg: bad.append(msg)

    # 1 括弧
    for a, b, nm in (("{", "}", "波括弧"), ("(", ")", "丸括弧"), ("[", "]", "角括弧")):
        d = src.count(a) - src.count(b)
        if d: say(f"{nm}の数が合わない({d:+d})")

    # 2 StringFormat の書式と引数
    for ln, args in find_calls(src, "StringFormat"):
        parts = split_args(args)
        if not parts: continue
        fmt = parts[0].strip()
        if not fmt.startswith('"'):
            continue                      # 変数を渡している場合は数えられない
        n_fmt = len(FMT.findall(fmt))
        n_arg = len(parts) - 1
        if n_fmt != n_arg:
            say(f"{ln}行: StringFormat の書式 {n_fmt} 個に対し引数 {n_arg} 個 → {fmt[:60]}")

    # 3 パネルの行数
    m = re.search(r"#define\s+LINES\s+(\d+)", code)
    if m:
        lines = int(m.group(1))
        # ラベルは "for(int i = 0; i < LINES + 24; i++)" のように余分に確保することがある。
        # 実際に確保している上限を見る。LINES そのものと比べると誤検出になる。
        a = re.search(r"i\s*<\s*LINES\s*\+\s*(\d+)", code)
        alloc = lines + (int(a.group(1)) if a else 0)
        draw = code[code.find("void Draw()"):] if "void Draw()" in code else ""
        used = draw.count("SetLine(i++")
        if used > alloc:
            say(f"SetLine(i++) が {used} 回あるのに、確保しているラベルは {alloc} 個")

    # 4 未定義の自作関数呼び出し
    defined = set(re.findall(r"^[A-Za-z_][\w ]*?\b(\w+)\s*\(", code, re.M))
    called = set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", code))
    # 大文字だけの名前は定数・マクロなので除く。
    # 接頭辞で広く除外すると、綴り間違いの呼び出しまで見逃す(C を除いていて
    # CreateLabelz() を取りこぼしていた)ので、除外は最小限にする。
    unknown = sorted(c for c in called - defined - BUILTIN
                     if not c.isupper() and not c.startswith("Inp"))
    if unknown:
        say(f"定義が見つからない呼び出し: {', '.join(unknown)}")

    # 5 使っていないグローバル変数
    for v in re.findall(r"^(?:double|int|bool|string|datetime|color)\s+(g_\w+)", code, re.M):
        if len(re.findall(r"\b" + v + r"\b", code)) < 2:
            say(f"宣言したのに使っていない: {v}")

    # 6 input のコメント
    for ln, line in enumerate(src.split("\n"), 1):
        if line.strip().startswith("input ") and "//" not in line:
            say(f"{ln}行: input に説明コメントがない → {line.strip()[:60]}")

    print(f"{'OK  ' if not bad else 'NG  '}{os.path.basename(path)}")
    for b in bad: print(f"      - {b}")
    return not bad


if __name__ == "__main__":
    ok = all([check(p) for p in sys.argv[1:]])
    sys.exit(0 if ok else 1)
