"""
build_policy_rates.py — BIS から G10 政策金利（月次）を自動取得し policy_rates_monthly.csv を生成。

出典: BIS WS_CBPOL（Central bank policy rates, monthly, end of period）。
  SDMX v1 CSV: https://stats.bis.org/api/v1/data/WS_CBPOL/M.<REF_AREA>?format=csv
  これで E3C（横断キャリー）の金利差ランクが完全自動になる（手作業ゼロ）。

出力: EDGE_DATA_DIR/policy_rates_monthly.csv  (date, ccy, rate)
"""
from __future__ import annotations

import io
import os
import time
import urllib.request

import pandas as pd

from data_io import DATA_DIR

# 通貨 → BIS REF_AREA。XM = ユーロ圏。
CCY_AREA = {
    "USD": "US", "EUR": "XM", "GBP": "GB", "JPY": "JP", "AUD": "AU",
    "NZD": "NZ", "CAD": "CA", "CHF": "CH", "SEK": "SE", "NOK": "NO",
}
START, END = "2016-01", "2025-12"
BASE = "https://stats.bis.org/api/v1/data/WS_CBPOL/M.{area}?format=csv&startPeriod={s}&endPeriod={e}"


def fetch_area(area: str) -> pd.DataFrame:
    url = BASE.format(area=area, s=START, e=END)
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "edge-research/1.0"})
            with urllib.request.urlopen(req, timeout=40) as resp:
                raw = resp.read().decode("utf-8")
            df = pd.read_csv(io.StringIO(raw))
            return df[["TIME_PERIOD", "OBS_VALUE"]].copy()
        except Exception as ex:
            if attempt == 3:
                raise
            print(f"    {area} retry {attempt+1}: {str(ex)[:60]}")
            time.sleep(2 ** (attempt + 1))


def main():
    months = pd.date_range(f"{START}-01", f"{END}-01", freq="MS")
    frames = []
    for ccy, area in CCY_AREA.items():
        d = fetch_area(area)
        s = pd.Series(d["OBS_VALUE"].values,
                      index=pd.to_datetime(d["TIME_PERIOD"] + "-01")).sort_index()
        # 月次に揃え、欠損は直近値で前方補完（政策金利は据置期間が続くため）
        s = s.reindex(months).ffill().bfill()
        frames.append(pd.DataFrame({"date": months.date, "ccy": ccy, "rate": s.values}))
        print(f"  {ccy} ({area}): {s.notna().sum()} months, "
              f"{START}={s.iloc[0]:.3f} {END}={s.iloc[-1]:.3f}")
    out = pd.concat(frames, ignore_index=True)
    path = os.path.join(DATA_DIR, "policy_rates_monthly.csv")
    out.to_csv(path, index=False)
    print(f"[WROTE] {path}  rows={len(out)}  ccys={out['ccy'].nunique()}")


if __name__ == "__main__":
    main()
