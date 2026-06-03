"""
fetch_cot.py — CFTC TFF（Leveraged Money）の FX 建玉を取得し cot_fx.csv を生成。

dataset: gpe5-46if（Traders in Financial Futures, Futures-Only）。
出力: EDGE_DATA_DIR/cot_fx.csv  (date, ccy, spec_net_pct)
  spec_net_pct = (lev_money_long - lev_money_short) / open_interest_all
公表ラグは runner 側で織り込む（火曜建玉→翌週建てる）。
"""
from __future__ import annotations

import io
import os
import urllib.parse
import urllib.request

import pandas as pd

from data_io import DATA_DIR

ENDPOINT = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
# 通貨 → CME 先物の market_and_exchange_names（GBPは新旧2名称）
CCY_MARKETS = {
    "EUR": ["EURO FX - CHICAGO MERCANTILE EXCHANGE"],
    "GBP": ["BRITISH POUND - CHICAGO MERCANTILE EXCHANGE",
            "BRITISH POUND STERLING - CHICAGO MERCANTILE EXCHANGE"],
    "JPY": ["JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE"],
    "AUD": ["AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE"],
    "CAD": ["CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE"],
    "CHF": ["SWISS FRANC - CHICAGO MERCANTILE EXCHANGE"],
    "NZD": ["NEW ZEALAND DOLLAR - CHICAGO MERCANTILE EXCHANGE"],
}


def _query(market: str) -> pd.DataFrame:
    where = (f"market_and_exchange_names='{market}' "
             f"AND report_date_as_yyyy_mm_dd between '2016-01-01T00:00:00' "
             f"and '2025-12-31T00:00:00'")
    params = {
        "$select": ("report_date_as_yyyy_mm_dd, lev_money_positions_long, "
                    "lev_money_positions_short, open_interest_all"),
        "$where": where, "$order": "report_date_as_yyyy_mm_dd", "$limit": "5000",
    }
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return pd.read_json(io.StringIO(r.read().decode()))
        except Exception as e:
            if attempt == 3:
                raise
            print(f"  retry {attempt+1}: {str(e)[:60]}")
            import time; time.sleep(2 ** (attempt + 1))


def main():
    rows = []
    for ccy, markets in CCY_MARKETS.items():
        frames = [_query(m) for m in markets]
        df = pd.concat([f for f in frames if f is not None and len(f)], ignore_index=True)
        if df.empty:
            print(f"[WARN] {ccy}: no data"); continue
        df["date"] = pd.to_datetime(df["report_date_as_yyyy_mm_dd"]).dt.tz_localize("UTC")
        oi = df["open_interest_all"].replace(0, pd.NA)
        df["spec_net_pct"] = (df["lev_money_positions_long"] -
                              df["lev_money_positions_short"]) / oi
        sub = df[["date", "spec_net_pct"]].dropna().sort_values("date")
        sub["ccy"] = ccy
        rows.append(sub)
        print(f"[OK] {ccy}: {len(sub)} weeks  {sub['date'].min().date()}..{sub['date'].max().date()}")
    out = pd.concat(rows, ignore_index=True)[["date", "ccy", "spec_net_pct"]]
    path = os.path.join(DATA_DIR, "cot_fx.csv")
    out.to_csv(path, index=False)
    print(f"[WROTE] {path}  rows={len(out)}  ccys={out['ccy'].nunique()}")


if __name__ == "__main__":
    main()
