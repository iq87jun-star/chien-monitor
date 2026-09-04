# -*- coding: utf-8 -*-
"""
event_calendar.py — マクロイベントの公式日程ローダー(docs/210)。到達性は 2026-09-04 に確認。
  FOMC : Fed 公式(年別 historical ページ 2003-2015 + ext_data.fomc_dates 2016-)
  BoJ  : 日銀 公式「Statement on Monetary Policy」年別ページ(mpr_YYYY, kYYMMDDa.*) 2003-
  ECB  : ECB 公式 Governing Council decisions 年別 include(isoDate + 'Monetary policy decisions') 2003-
  CPI/NFP : BLS ニュースリリース・アーカイブ(直接は 403 → r.jina.ai 経由の本文。cpi_MMDDYYYY / empsit_MMDDYYYY) 2008-02-
キャッシュ: research/data_ext/events_<name>.csv(gitignore 対象)。
"""
import os, re, datetime as dt, urllib.request
import pandas as pd
import ext_data as ext

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = ext.DATA
UA = {"User-Agent": "Mozilla/5.0"}


def _get(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 500:
        return open(path, encoding="utf-8", errors="ignore").read()
    b = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90).read()
    open(path, "wb").write(b)
    return b.decode("utf-8", "ignore")


def _cached(name, fn):
    p = os.path.join(DATA, f"events_{name}.csv")
    if os.path.exists(p):
        return sorted(pd.to_datetime(pd.read_csv(p)["date"]).dt.date)
    d = sorted(set(fn()))
    pd.DataFrame({"date": [x.isoformat() for x in d]}).to_csv(p, index=False)
    return d


def fomc():
    def f():
        out = set(ext.fomc_dates())
        MON = (r"(January|February|March|April|May|June|July|August|September|October|November|December"
               r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)")
        for y in range(2003, 2016):
            html = _get(f"https://www.federalreserve.gov/monetarypolicy/fomchistorical{y}.htm",
                        os.path.join(DATA, f"fomc_{y}.htm"))
            for m in re.finditer(MON + r"\s+(\d{1,2})(?:-(?:" + MON + r"\s+)?(\d{1,2}))?\s+(?:Meeting|Conference Call)", html):
                if "Conference Call" in m.group(0):
                    continue
                mon1, d1, mon2, d2 = m.group(1), int(m.group(2)), m.group(3), m.group(4)
                def _m(x): return ext.MONTHS[[k for k in ext.MONTHS if k.startswith(x[:3])][0]]
                out.add(dt.date(y, _m(mon2) if mon2 else _m(mon1), int(d2) if d2 else d1))
        return out
    return _cached("fomc", f)


def boj():
    def f():
        out = set()
        for y in range(2003, 2027):
            html = _get(f"https://www.boj.or.jp/en/mopo/mpmdeci/mpr_{y}/index.htm", os.path.join(DATA, f"boj_{y}.htm"))
            for m in re.finditer(r"k(\d{2})(\d{2})(\d{2})a?\.(?:htm|pdf)", html):
                out.add(dt.date(2000 + int(m.group(1)), int(m.group(2)), int(m.group(3))))
        return out
    return _cached("boj", f)


def ecb():
    def f():
        out = set()
        for y in range(2003, 2027):
            html = _get(f"https://www.ecb.europa.eu/press/govcdec/mopo/{y}/html/index_include.en.html",
                        os.path.join(DATA, f"ecb_{y}.htm"))
            for m in re.finditer(r'isoDate="(\d{4}-\d{2}-\d{2})"(.*?)</dd>', html, re.S):
                if re.search(r"Monetary policy decisions", m.group(2), re.I):
                    out.add(dt.date.fromisoformat(m.group(1)))
        return out
    return _cached("ecb", f)


def _bls(name):
    def f():
        txt = _get(f"https://r.jina.ai/https://www.bls.gov/bls/news-release/{name}.htm",
                   os.path.join(DATA, f"bls_{name}_archive.txt"))
        return {dt.date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
                for m in re.finditer(name + r"_(\d{2})(\d{2})(\d{4})\.htm", txt)}
    return _cached(name, f)


def cpi(): return _bls("cpi")
def nfp(): return _bls("empsit")


ALL = {"FOMC": fomc, "BOJ": boj, "ECB": ecb, "CPI": cpi, "NFP": nfp}

if __name__ == "__main__":
    for k, fn in ALL.items():
        d = fn()
        s = pd.Series(1, index=pd.to_datetime(d))
        print(f"{k:5s} n={len(d):4d} {d[0]}..{d[-1]}  年別:", s.groupby(s.index.year).sum().to_dict())
