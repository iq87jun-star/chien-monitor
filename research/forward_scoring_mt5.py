# -*- coding: utf-8 -*-
"""
forward_scoring_mt5.py — C-7(docs/99): MT5レポートを読み込み、実測月利を docs/98 の
バックテスト月次分布と照合して分位を自動採点する。

使い方:
  1) MT5「履歴」タブ右クリック → レポート(HTML)保存 or 取引履歴エクスポート(CSV)
  2) python3 research/forward_scoring_mt5.py --file Report.html --month 2026-06 \
         --balance 100000 --dist seasonal:06 --mult 2.0 [--manual]
  3) レポートが無い月は --pl で直接指定も可(例: --pl 1211.75)

採点(docs/98 §3の判定基準をそのまま実装):
  25〜75%レンジ内 → ✅ エッジ生存 / 最小未満 → ⚠ 要注意(2ヶ月連続で倍率ダウン検討)
  最大超 → ⚪ 上振れ(次月の平均回帰に注意) / それ以外 → 分布内
  --manual 指定時は「参考(manual-adjusted)」ラベル(EA純粋でない月, docs/98)。

分布はdocs/98 §1の転記(素サイズ1x・2016-2025)。--mult で実測を1x換算してから照合。
⚠ 規律: 単月で一喜一憂しない。最低6ヶ月積んで「分布内に収まり続けるか」で判断(docs/40)。
"""
import argparse, json, os, re, sys, datetime as dt

# docs/98 §1: バックテスト基準分布(素サイズ1x・各月の月利%・2016-2025)
DISTS = {
    "seasonal:06": dict(
        label="6月(季節EA JUNE_TOP5, 1x)",
        samples=[-1.66, -0.46, 0.22, 0.67, 0.92, 1.42, 2.22, 2.34, 3.17, 6.38]),
    "portfolioD:06": dict(
        label="6月(PortfolioD, 1x) ⚠分布は min/中央/max のみ既知(docs/98)",
        samples=None, minimum=-1.16, median=1.21, maximum=4.78),
    # 7月以降はdocs/87 §2の月次実績が確定し次第ここに追記する(数字を盛らない=不明月は追加しない)
}


def read_text(path):
    raw = open(path, "rb").read()
    for enc in ("utf-16", "utf-8-sig", "utf-8", "cp932"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return raw.decode("utf-8", errors="replace")


def strip_tags(cell):
    return re.sub(r"<[^>]+>", "", cell).replace("&nbsp;", " ").strip()


def parse_num(s):
    s = s.replace(" ", "").replace(" ", "").replace(",", "")
    m = re.match(r"^-?\d+(\.\d+)?$", s)
    return float(s) if m else None


BALANCE_TYPES = {"balance", "credit", "deposit", "withdrawal", "入金", "出金", "残高", "クレジット"}


def parse_mt5_html(text, year, month):
    """MT5レポートHTMLの行から、指定月の 損益+スワップ+手数料 を合算する。
       ヘッダに Time/時間 と Profit/損益 を含むテーブルを対象。Balance系の行は除外。"""
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", text, flags=re.S | re.I)
    header_idx = {}
    total = dict(profit=0.0, swap=0.0, commission=0.0, deals=0)
    for tr in rows:
        cells = [strip_tags(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S | re.I)]
        if not cells:
            continue
        low = [c.lower() for c in cells]
        if any(("profit" in c or "損益" in c) for c in low) and any(("time" in c or "時間" in c or "約定" in c) for c in low):
            header_idx = {}
            for i, c in enumerate(low):
                if "time" in c or "時間" in c:
                    header_idx.setdefault("time", i)
                elif "profit" in c or "損益" in c:
                    header_idx["profit"] = i
                elif "swap" in c or "スワップ" in c:
                    header_idx["swap"] = i
                elif "commission" in c or "手数料" in c:
                    header_idx["commission"] = i
                elif "type" in c or "タイプ" in c or "種別" in c:
                    header_idx["type"] = i
            continue
        if "profit" not in header_idx or "time" not in header_idx:
            continue
        ti = header_idx["time"]
        if ti >= len(cells):
            continue
        m = re.match(r"(\d{4})[./-](\d{2})[./-](\d{2})", cells[ti])
        if not m:
            continue
        if int(m.group(1)) != year or int(m.group(2)) != month:
            continue
        if "type" in header_idx and header_idx["type"] < len(cells):
            if cells[header_idx["type"]].strip().lower() in BALANCE_TYPES:
                continue
        pi = header_idx["profit"]
        p = parse_num(cells[pi]) if pi < len(cells) else None
        if p is None:
            continue
        total["profit"] += p
        total["deals"] += 1
        for k in ("swap", "commission"):
            if k in header_idx and header_idx[k] < len(cells):
                v = parse_num(cells[header_idx[k]])
                if v is not None:
                    total[k] += v
    return total


def parse_csv(text, year, month):
    """MT5エクスポートCSV/TSV(列名に time/profit 系を含む)から同様に合算。"""
    import csv, io
    delim = "\t" if text.count("\t") > text.count(",") else ","
    rd = csv.reader(io.StringIO(text), delimiter=delim)
    rows = list(rd)
    if not rows:
        return dict(profit=0.0, swap=0.0, commission=0.0, deals=0)
    head = [c.strip().lower() for c in rows[0]]
    def col(*keys):
        for i, c in enumerate(head):
            if any(k in c for k in keys):
                return i
        return None
    ti, pi = col("time", "時間", "約定"), col("profit", "損益")
    si, ci, tyi = col("swap", "スワップ"), col("commission", "手数料"), col("type", "タイプ", "種別")
    total = dict(profit=0.0, swap=0.0, commission=0.0, deals=0)
    if ti is None or pi is None:
        return total
    for r in rows[1:]:
        if len(r) <= max(ti, pi):
            continue
        m = re.match(r"(\d{4})[./-](\d{2})[./-](\d{2})", r[ti].strip())
        if not m or int(m.group(1)) != year or int(m.group(2)) != month:
            continue
        if tyi is not None and tyi < len(r) and r[tyi].strip().lower() in BALANCE_TYPES:
            continue
        p = parse_num(r[pi].strip())
        if p is None:
            continue
        total["profit"] += p; total["deals"] += 1
        for k, idx in (("swap", si), ("commission", ci)):
            if idx is not None and idx < len(r):
                v = parse_num(r[idx].strip())
                if v is not None:
                    total[k] += v
    return total


def percentile_of(x, samples):
    n = len(samples)
    below = sum(1 for s in samples if s < x)
    eq = sum(1 for s in samples if s == x)
    return 100.0 * (below + 0.5 * eq) / n


def quantile(samples, q):
    s = sorted(samples); idx = q * (len(s) - 1)
    lo = int(idx); fr = idx - lo
    return s[-1] if lo >= len(s) - 1 else s[lo] + (s[lo + 1] - s[lo]) * fr


def score(monthly_pct_1x, dist_key, manual):
    d = DISTS[dist_key]
    res = dict(dist=d["label"], value_1x_pct=round(monthly_pct_1x, 3))
    if d.get("samples"):
        s = d["samples"]
        q25, q50, q75 = quantile(s, .25), quantile(s, .50), quantile(s, .75)
        res.update(pctile=round(percentile_of(monthly_pct_1x, s), 1),
                   q25=q25, median=q50, q75=q75, minimum=min(s), maximum=max(s))
        if monthly_pct_1x < min(s):
            res["verdict"] = "⚠ 最小未満=要注意(2ヶ月連続なら倍率ダウン検討)"
        elif monthly_pct_1x > max(s):
            res["verdict"] = "⚪ 最大超=上振れ(次月の平均回帰に注意)"
        elif q25 <= monthly_pct_1x <= q75:
            res["verdict"] = "✅ 25-75%レンジ内=エッジ生存(モデル通り)"
        else:
            res["verdict"] = "○ 分布内(25-75%レンジ外)"
    else:
        res.update(minimum=d["minimum"], median=d["median"], maximum=d["maximum"])
        if monthly_pct_1x < d["minimum"]:
            res["verdict"] = "⚠ 最小未満=要注意"
        elif monthly_pct_1x > d["maximum"]:
            res["verdict"] = "⚪ 最大超=上振れ"
        else:
            res["verdict"] = "○ 分布内(min/中央/maxのみ既知=分位は概算不可)"
    if manual:
        res["verdict"] += "【参考: manual-adjusted=EA純粋でない月(docs/98)】"
    return res


def selftest():
    ok = True
    def chk(name, c):
        nonlocal ok; ok &= bool(c); print(f"  [{'PASS' if c else 'FAIL'}] {name}")
    html = """<html><table>
    <tr><th>Time</th><th>Type</th><th>Commission</th><th>Swap</th><th>Profit</th></tr>
    <tr><td>2026.06.09 05:00:00</td><td>buy</td><td>-2.00</td><td>0.00</td><td>500.25</td></tr>
    <tr><td>2026.06.10 05:00:00</td><td>sell</td><td>-2.00</td><td>-1.50</td><td>711.50</td></tr>
    <tr><td>2026.07.01 05:00:00</td><td>buy</td><td>0.00</td><td>0.00</td><td>999.00</td></tr>
    <tr><td>2026.06.01 00:00:00</td><td>balance</td><td>0.00</td><td>0.00</td><td>100000.00</td></tr>
    </table></html>"""
    t = parse_mt5_html(html, 2026, 6)
    chk("HTML: 対象月のみ合算(1211.75)", abs(t["profit"] - 1211.75) < 1e-9 and t["deals"] == 2)
    chk("HTML: balance行を除外", t["profit"] < 10000)
    chk("HTML: swap/commission合算", abs(t["swap"] + 1.5) < 1e-9 and abs(t["commission"] + 4.0) < 1e-9)
    csvtxt = "Time,Type,Commission,Swap,Profit\n2026.06.09 05:00,buy,-2.0,0.0,500.25\n2026.06.30 05:00,sell,0,0,711.5\n2026.05.01 00:00,buy,0,0,50\n"
    t2 = parse_csv(csvtxt, 2026, 6)
    chk("CSV: 対象月のみ合算", abs(t2["profit"] - 1211.75) < 1e-9)
    r = score(1.21, "seasonal:06", False)
    chk("採点: +1.21%(1x)は6月分布の25-75内", "✅" in r["verdict"])
    r2 = score(-2.0, "seasonal:06", False)
    chk("採点: -2.0%は最小未満=⚠", "⚠" in r2["verdict"])
    r3 = score(7.0, "seasonal:06", True)
    chk("採点: +7.0%は最大超=⚪+参考ラベル", "⚪" in r3["verdict"] and "参考" in r3["verdict"])
    print("SELFTEST:", "ALL PASS" if ok else "FAILURES")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="MT5レポート(HTML)またはエクスポートCSV")
    ap.add_argument("--pl", type=float, help="確定損益$を直接指定(レポートなしの月)")
    ap.add_argument("--month", help="対象月 YYYY-MM")
    ap.add_argument("--balance", type=float, help="口座サイズ$(初期残高)")
    ap.add_argument("--mult", type=float, default=1.0, help="運用倍率(実測を1x換算して照合)")
    ap.add_argument("--dist", default="seasonal:06", choices=sorted(DISTS.keys()))
    ap.add_argument("--manual", action="store_true", help="手決済が混じる月(参考扱い)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.month or not a.balance or (not a.file and a.pl is None):
        ap.error("--month/--balance と --file または --pl が必要(または --selftest)")
    y, m = map(int, a.month.split("-"))
    if a.file:
        text = read_text(a.file)
        tot = parse_csv(text, y, m) if a.file.lower().endswith((".csv", ".tsv", ".txt")) \
            else parse_mt5_html(text, y, m)
        pl = tot["profit"] + tot["swap"] + tot["commission"]
        print(f"[抽出] {a.month}: deals={tot['deals']} profit={tot['profit']:.2f} "
              f"swap={tot['swap']:.2f} comm={tot['commission']:.2f} → 合計 {pl:.2f}$")
        if tot["deals"] == 0:
            print("⚠ 対象月の約定が見つからない(ファイル形式/月指定を確認)"); return 1
    else:
        pl = a.pl
    pct = 100.0 * pl / a.balance
    pct1x = pct / a.mult if a.mult > 0 else pct
    res = score(pct1x, a.dist, a.manual)
    res.update(month=a.month, measured_pl=round(pl, 2), balance=a.balance,
               measured_pct=round(pct, 3), mult=a.mult)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results",
                       f"forward_score_{a.month}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print("保存:", out, "→ docs/98 §2 へ転記")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
