# -*- coding: utf-8 -*-
"""docs/322 Q94 / Q1 B 段: MT5 ストラテジーテスターのレポート(htm)を読み、Python 側の期待取引と比較する。
判定(docs/244 Q1): 取引数 ≥ 95%(テスター / Python)・累計損益差 ≤ 5%(名目比)・月次損益の符号一致率を併記。
使い方: cd research && python3 forward/tester_parity.py --report <report.htm> --expected <csv: month,pnl,trades> [--nominal 100000]
        python3 forward/tester_parity.py --selftest"""
import re, html, sys, argparse, io
import pandas as pd
def parse_report(path):
    """テスターレポートの『約定 / Deals』表 → DataFrame(time, symbol, type, direction, volume, price, profit)。lxml 無しで動く簡易パーサ。"""
    s = open(path, encoding="utf-16", errors="ignore").read() if open(path, "rb").read(2) in (b"\xff\xfe", b"\xfe\xff") else open(path, encoding="utf-8", errors="ignore").read()
    rows = [[html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S)] for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", s, flags=re.S)]
    hdr = None; out = []
    for r in rows:
        low = [c.lower() for c in r]
        if hdr is None and any(c in ("deal", "約定") for c in low) and any(c in ("profit", "損益") for c in low): hdr = low; continue
        if hdr is not None:
            if len(r) < len(hdr) - 2: 
                if out: break
                continue
            d = dict(zip(hdr, r)); out.append(d)
    if not out: return pd.DataFrame()
    df = pd.DataFrame(out); ren = {"time": "time", "時間": "time", "symbol": "symbol", "銘柄": "symbol", "type": "type", "タイプ": "type", "direction": "direction", "方向": "direction", "volume": "volume", "数量": "volume", "price": "price", "価格": "price", "profit": "profit", "損益": "profit", "comment": "comment", "コメント": "comment"}
    df = df.rename(columns={c: ren[c] for c in df.columns if c in ren})
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S", errors="coerce"); df["profit"] = pd.to_numeric(df["profit"].astype(str).str.replace(" ", "").str.replace(",", ""), errors="coerce").fillna(0.0)
    df = df[df["time"].notna()]
    return df
def monthly(df):
    """決済(direction=out/イン・アウト)の約定を月で集計: pnl・trades"""
    d = df.copy(); d = d[d.get("direction", pd.Series("out", index=d.index)).astype(str).str.lower().isin(("out", "out/in", "アウト", "決済"))] if "direction" in d else d
    d["month"] = d["time"].dt.to_period("M").astype(str); g = d.groupby("month").agg(pnl=("profit", "sum"), trades=("profit", "size")).reset_index(); return g
def compare(tester_m, expected, nominal):
    m = expected.merge(tester_m, on="month", how="outer", suffixes=("_py", "_mt5")).fillna(0.0).sort_values("month")
    n_py, n_mt = m.trades_py.sum(), m.trades_mt5.sum(); ratio = n_mt / n_py if n_py else float("nan")
    diff = (m.pnl_mt5.sum() - m.pnl_py.sum()) / nominal; sign = float(((m.pnl_py > 0) == (m.pnl_mt5 > 0))[(m.pnl_py != 0) | (m.pnl_mt5 != 0)].mean()) if len(m) else float("nan")
    ok = (ratio >= 0.95) and (abs(diff) <= 0.05)
    return dict(trades_py=int(n_py), trades_mt5=int(n_mt), trade_ratio=round(ratio, 3), pnl_py=round(float(m.pnl_py.sum()), 2), pnl_mt5=round(float(m.pnl_mt5.sum()), 2), pnl_diff_pct=round(diff * 100, 2), sign_agree=round(sign, 3), verdict=("通過" if ok else "不一致")), m
def selftest():
    h = """<html><table><tr><th>Time</th><th>Deal</th><th>Symbol</th><th>Type</th><th>Direction</th><th>Volume</th><th>Price</th><th>Order</th><th>Commission</th><th>Swap</th><th>Profit</th><th>Balance</th><th>Comment</th></tr>
<tr><td>2025.01.06 00:00:00</td><td>2</td><td>GBPJPY</td><td>buy</td><td>in</td><td>1.00</td><td>195.00</td><td>2</td><td>0.00</td><td>0.00</td><td>0.00</td><td>100 000.00</td><td>RFMon_GBPJPY</td></tr>
<tr><td>2025.01.07 00:00:00</td><td>3</td><td>GBPJPY</td><td>sell</td><td>out</td><td>1.00</td><td>196.00</td><td>3</td><td>0.00</td><td>0.00</td><td>640.00</td><td>100 640.00</td><td>RFMon_GBPJPY</td></tr>
<tr><td>2025.02.03 00:00:00</td><td>4</td><td>GBPJPY</td><td>buy</td><td>in</td><td>1.00</td><td>190.00</td><td>4</td><td>0.00</td><td>0.00</td><td>0.00</td><td>100 640.00</td><td>RFMon_GBPJPY</td></tr>
<tr><td>2025.02.04 00:00:00</td><td>5</td><td>GBPJPY</td><td>sell</td><td>out</td><td>1.00</td><td>189.50</td><td>5</td><td>0.00</td><td>0.00</td><td>-330.00</td><td>100 310.00</td><td>RFMon_GBPJPY</td></tr></table></html>"""
    p = "/tmp/_chien_selftest.htm"; open(p, "w", encoding="utf-8").write(h); df = parse_report(p); tm = monthly(df)
    exp = pd.DataFrame(dict(month=["2025-01", "2025-02"], pnl=[650.0, -320.0], trades=[1, 1]))
    r, m = compare(tm, exp, 100000); print(m.to_string(index=False)); print(r); assert r["verdict"] == "通過", r; print("selftest OK")
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--report"); ap.add_argument("--expected"); ap.add_argument("--nominal", type=float, default=100000); ap.add_argument("--selftest", action="store_true"); a = ap.parse_args()
    if a.selftest: return selftest()
    df = parse_report(a.report); tm = monthly(df); exp = pd.read_csv(a.expected); r, m = compare(tm, exp, a.nominal); print(m.to_string(index=False)); print(r)
if __name__ == "__main__": main()
