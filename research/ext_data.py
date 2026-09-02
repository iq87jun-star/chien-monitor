# -*- coding: utf-8 -*-
"""
ext_data.py — 価格以外の外部状態データのローダー(docs/203)。
この環境から到達可能と確認済みのソースのみ(2026-09-02疎通確認):
  - CFTC COT 金融先物(年次zip)   : 投機筋(Leveraged Funds)のネットポジション・週次
  - Fed FOMC カレンダー(公式HTML)  : 会合決定日(2日会合の2日目)
  - Yahoo ^VIX / ^VIX3M(日次)     : ボラ期間構造
キャッシュ: research/data_ext/(gitignore対象・無ければ取得)
"""
import os, re, io, csv, json, zipfile, datetime as dt, urllib.request
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data_ext")
os.makedirs(DATA, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0"}
YEARS = range(2016, 2027)


def _get(url, path, binary=True):
    if os.path.exists(path):
        return path
    b = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
    with open(path, "wb" if binary else "w") as f:
        f.write(b if binary else b.decode())
    return path


# ---------------- FOMC ----------------
MONTHS = {m: i + 1 for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July",
                                           "August", "September", "October", "November", "December"])}


def fomc_dates():
    """会合の決定日(2日会合なら2日目)の集合。2016-2020は年別ページ、2021以降は現行カレンダー。"""
    out = set()
    pages = [(y, _get(f"https://www.federalreserve.gov/monetarypolicy/fomchistorical{y}.htm",
                      os.path.join(DATA, f"fomc_{y}.htm"))) for y in range(2016, 2021)]
    pages.append((None, _get("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
                             os.path.join(DATA, "fomc_current.htm"))))
    for y, p in pages:
        html = open(p, encoding="utf-8", errors="ignore").read()
        if y is not None:
            # 例: <h5 class="panel-heading">January 26-27 Meeting - 2016</h5> / "March 15-16 Meeting"
            MON = r"(January|February|March|April|May|June|July|August|September|October|November|December)"
            # 単月: "March 15-16 Meeting" / 月跨ぎ: "January 31-February 1 Meeting" / 単日・臨時も拾う
            for m in re.finditer(MON + r"\s+(\d{1,2})(?:-(?:" + MON + r"\s+)?(\d{1,2}))?\s+Meeting", html):
                mon1, d1, mon2, d2 = m.group(1), int(m.group(2)), m.group(3), m.group(4)
                end_mon = MONTHS[mon2] if mon2 else MONTHS[mon1]
                out.add(dt.date(y, end_mon, int(d2) if d2 else d1))
        else:
            # 年ブロック: <h4 ...>2026 FOMC Meetings</h4> の後に月/日の div が並ぶ
            for yb in re.finditer(r"(\d{4}) FOMC Meetings(.*?)(?=\d{4} FOMC Meetings|$)", html, re.S):
                yy = int(yb.group(1)); block = yb.group(2)
                months = re.findall(r'fomc-meeting__month[^>]*>\s*<strong>([A-Za-z/]+)</strong>', block)
                days = re.findall(r'fomc-meeting__date[^>]*>\s*([0-9]{1,2})(?:-([0-9]{1,2}))?', block)
                for mon, (d1, d2) in zip(months, days):
                    mon2 = mon.split("/")[-1]           # "Jan/Feb" のような跨ぎは後半の月
                    key = [k for k in MONTHS if k.startswith(mon2[:3])]
                    if key:
                        out.add(dt.date(yy, MONTHS[key[0]], int(d2) if d2 else int(d1)))
    return sorted(out)


# ---------------- COT ----------------
COT_MARKETS = {
    "JPY": "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE",
    "GBP": "BRITISH POUND - CHICAGO MERCANTILE EXCHANGE",
    "AUD": "AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE",
    "EUR": "EURO FX - CHICAGO MERCANTILE EXCHANGE",
    "NZD": "NZ DOLLAR - CHICAGO MERCANTILE EXCHANGE",
    "CAD": "CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE",
    "CHF": "SWISS FRANC - CHICAGO MERCANTILE EXCHANGE",
}


def cot_lev_net():
    """通貨別: 投機筋(Leveraged Funds)ネット(ロング−ショート)/建玉 の週次系列。
    index=報告基準日(火曜)。列 release = 公表日(通常 金曜=+3日)。利用時は release 以降にのみ既知とする。"""
    frames = []
    for y in YEARS:
        p = _get(f"https://www.cftc.gov/files/dea/history/fut_fin_txt_{y}.zip", os.path.join(DATA, f"cot_{y}.zip"))
        z = zipfile.ZipFile(p); name = z.namelist()[0]
        df = pd.read_csv(io.BytesIO(z.read(name)), encoding="latin1", low_memory=False)
        df.columns = [c.strip() for c in df.columns]
        frames.append(df)
    all_ = pd.concat(frames, ignore_index=True)
    all_["Market_and_Exchange_Names"] = all_["Market_and_Exchange_Names"].str.strip()
    out = {}
    for cur, mk in COT_MARKETS.items():
        d = all_[all_["Market_and_Exchange_Names"] == mk].copy()
        d["date"] = pd.to_datetime(d["Report_Date_as_YYYY-MM-DD"])
        d = d.sort_values("date").drop_duplicates("date")
        net = (d["Lev_Money_Positions_Long_All"] - d["Lev_Money_Positions_Short_All"]) / d["Open_Interest_All"]
        s = pd.Series(net.values, index=d["date"].values, name=cur)
        out[cur] = pd.DataFrame({"net_pct_oi": s, "release": s.index + pd.Timedelta(days=3)})
    return out


# ---------------- VIX ----------------
def vix_series():
    res = {}
    for sym, fn in (("^VIX", "vix.csv"), ("^VIX3M", "vix3m.csv")):
        p = os.path.join(DATA, fn)
        if not os.path.exists(p):
            u = (f"https://query2.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(sym)}"
                 f"?interval=1d&period1=1451606400&period2=1788220799")
            d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read())
            r = d["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]
            rows = [(dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d"), q["close"][i])
                    for i, t in enumerate(ts) if q["close"][i] is not None]
            with open(p, "w", newline="") as f:
                w = csv.writer(f); w.writerow(["date", "close"]); w.writerows(rows)
        df = pd.read_csv(p, parse_dates=["date"]).set_index("date")["close"]
        res[sym.strip("^")] = df
    return res["VIX"], res["VIX3M"]


if __name__ == "__main__":
    f = fomc_dates()
    print(f"FOMC決定日: {len(f)}件 {f[0]}..{f[-1]}")
    per_year = {}
    for d in f: per_year[d.year] = per_year.get(d.year, 0) + 1
    print("  年別:", per_year)
    c = cot_lev_net()
    for k, v in c.items():
        print(f"COT {k}: n={len(v)} {v.index[0].date()}..{v.index[-1].date()} net%OI 最新={v['net_pct_oi'].iloc[-1]:+.3f} 最小={v['net_pct_oi'].min():+.3f} 最大={v['net_pct_oi'].max():+.3f}")
    vix, vix3m = vix_series()
    j = pd.concat([vix.rename("vix"), vix3m.rename("vix3m")], axis=1).dropna()
    print(f"VIX: n={len(vix)} / VIX3M: n={len(vix3m)} ..{vix3m.index[-1].date()} / 共通={len(j)} / VIX>VIX3M(逆転)日の比率={(j.vix>j.vix3m).mean()*100:.1f}%")
