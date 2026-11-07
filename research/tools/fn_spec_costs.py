# -*- coding: utf-8 -*-
"""docs/224: FNmarkets #511030 (RAW) の Chien_SpecDump.mq5 出力 → 銘柄別コスト表。
スプレッド(bps・スナップショット)/ RAW 手数料(往復 USD 7/lot・ECN 銘柄のみ)/ スワップ(bps/日・%/年)/ 3倍日 / 1lot 名目・証拠金。
通貨換算は使わず、価格比(bps)で統一する: spread_bps = (ask-bid)/mid×1e4, swap_bps = swap額/名目(同一通貨)×1e4。"""
import os, sys, csv, json
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data_ext", "fn511030_spec_20260914.csv")
OUT = os.path.join(ROOT, "results", "fn511030_costs.csv")
COMM_RT_USD = 7.0   # RAW: 往復 USD 7 / lot(docs/223 §1 #3)。ECN\ 配下(FX・金属)に適用
LEV = 500            # OrderCalcMargin は口座レバレッジ 1:500 で返る(margin_1lot×500 = USD 名目)
TARGET = ["EURUSD","GBPUSD","USDJPY","AUDUSD","NZDUSD","USDCAD","USDCHF","EURJPY","GBPJPY","AUDJPY","NZDJPY","CADJPY","CHFJPY","EURGBP","EURCHF",
          "XAUUSD","XAGUSD","USOUSD","UKOUSD","SPX500","NDX100","US30","US2000","GER40","JP225","UK100","FRA40","EUSTX50","AUS200","HK50","BTCUSD","ETHUSD"]


def rows():
    # description に "," を含む株式行があるため、行頭から固定 4 列 + 末尾から固定 22 列で切る
    with open(SRC, encoding="utf-8") as f:
        hdr = f.readline().strip().split(","); n = len(hdr)
        for line in f:
            p = line.rstrip("\n").split(",")
            if len(p) < n: continue
            p = p[:2] + [",".join(p[2:len(p) - (n - 3)])] + p[len(p) - (n - 3):]
            yield dict(zip(hdr, p))


def main():
    out = []
    for r in rows():
        s = r["symbol"]
        if s not in TARGET: continue
        bid, ask = float(r["bid"]), float(r["ask"]); mid = (bid + ask) / 2 or float("nan")
        point, contract = float(r["point"]), float(r["contract_size"]); mode = r["swap_mode"]
        sl, ss = float(r["swap_long"]), float(r["swap_short"]); notional_ccy = contract * mid
        if mode == "POINTS":              # 価格ポイント建て → 利益通貨額 = pts×point×contract
            bl, bs = sl * point / mid * 1e4, ss * point / mid * 1e4
        elif mode in ("CCY_MARGIN", "CCY_PROFIT", "CCY_DEPOSIT"):   # 通貨額/lot/日(指数・エネルギーは証拠金通貨=利益通貨)
            bl, bs = sl / notional_ccy * 1e4, ss / notional_ccy * 1e4
        elif mode.startswith("INT"):      # 年率 % → bps/日
            bl, bs = sl / 365 * 100, ss / 365 * 100
        else: bl = bs = float("nan")
        margin = float(r["margin_1lot"]); notional_usd = margin * LEV
        ecn = r["path"].startswith("ECN")
        comm_bps = COMM_RT_USD / notional_usd * 1e4 if ecn else 0.0
        spread_bps = (ask - bid) / mid * 1e4
        out.append(dict(symbol=s, path=r["path"].split("\\")[1] if "\\" in r["path"] else r["path"], digits=int(r["digits"]), contract=contract,
                        mid=round(mid, 5), notional_usd_1lot=round(notional_usd, 0), margin_1lot_usd=margin, vol_min=float(r["vol_min"]),
                        spread_pts=int(r["spread_points"]), spread_bps=round(spread_bps, 2), comm_rt_bps=round(comm_bps, 2),
                        rt_cost_bps_2x=round(2 * spread_bps + comm_bps, 2),      # docs/216 の慣例(建て+決済で 2 回スプレッド)+ 手数料
                        swap_mode=mode, swap_long_raw=sl, swap_short_raw=ss, swap_long_bps_d=round(bl, 3), swap_short_bps_d=round(bs, 3),
                        swap_long_pct_y=round(bl * 365 / 100, 2), swap_short_pct_y=round(bs * 365 / 100, 2), triple_day=r["swap3day"],
                        mon24h_long_cost_bps=round(2 * spread_bps + comm_bps - bl, 2)))   # Mon レッグ(月→火・ロール 1 回・LONG)
    out.sort(key=lambda d: TARGET.index(d["symbol"]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    print(f"{'sym':8s} {'grp':8s} {'notional$':>10s} {'sprd':>5s} {'sp_bps':>6s} {'comm':>5s} {'RT2x':>6s} {'swL/d':>7s} {'swS/d':>7s} {'swL%/y':>7s} {'swS%/y':>7s} 3x  Mon24h")
    for d in out:
        print(f"{d['symbol']:8s} {d['path']:8s} {d['notional_usd_1lot']:10,.0f} {d['spread_pts']:5d} {d['spread_bps']:6.2f} {d['comm_rt_bps']:5.2f} {d['rt_cost_bps_2x']:6.2f} "
              f"{d['swap_long_bps_d']:7.2f} {d['swap_short_bps_d']:7.2f} {d['swap_long_pct_y']:7.2f} {d['swap_short_pct_y']:7.2f} {d['triple_day']:3s} {d['mon24h_long_cost_bps']:6.2f}")
    print("->", OUT)


if __name__ == "__main__": main()
