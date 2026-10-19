#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
withdrawal_fee_compare.py — 出金ルート別 手数料比較（銀行直接SWIFT / Wise経由 / 暗号通貨USDT経由）。

目的(ユーザー): 出金の手数料はどのくらい？暗号通貨と比較。
モデル: 分配後の受取額(USD)を、各ルートで日本の銀行(円)に着金させた時の【固定費＋変動費(率)】を控除し、
        手取り(円)と実効コスト%を出す。⚠手数料は業者/銀行/取引所/時期で変動＝下記は代表値。必ず実額確認。

ルートの代表的手数料(2026目安・要確認):
  ① 銀行直接SWIFT: 中継銀行¥2,000 + 受取¥2,500〜4,000(ネット銀行〜メガ) + 外貨→円スプレッド ~0.8%
                   (＋メガはリフティングチャージ等で更に増えうる)
  ② Wise経由     : 受取ほぼ無料 + USD→JPY 変換 ~0.5%(実勢に近い) + 円送金 ~¥300
  ③ 暗号USDT経由 : 業者→USDT出金 ~無料 + 送金網(TRC20) ~$1 + 取引所で売却 ~0.15%(取引所板) +
                   USDTペグ差 ~0.1% + 円出金 ~¥330  (※販売所スプレッドは1-3%と高い→板取引推奨)
"""
USDJPY = 157.0

ROUTES = {
 "①銀行直接SWIFT": dict(fixed_jpy=2000+3500, var_pct=0.008),   # 中継+受取(ネット〜メガ中間) + FXスプレッド0.8%
 "②Wise経由":      dict(fixed_jpy=300,        var_pct=0.005),   # 変換0.5% + 円送金¥300
 "③暗号USDT経由":  dict(fixed_jpy=157+330,    var_pct=0.0025),  # 網$1+円出金¥330 + (売却0.15%+ペグ0.1%)
}
AMOUNTS_USD = [1000, 2000, 4000, 10000]   # 分配後の受取額(例)

def net_jpy(usd, fixed_jpy, var_pct):
    gross=usd*USDJPY
    fee=gross*var_pct + fixed_jpy
    return gross-fee, fee

def main():
    print("="*78)
    print(f"出金ルート別 手数料比較（USDJPY={USDJPY}・分配後USD→日本の銀行(円)・代表値/要確認）")
    print("="*78)
    for usd in AMOUNTS_USD:
        gross=usd*USDJPY
        print(f"\n■ 受取(分配後) ${usd:,}  ≈ ¥{gross:,.0f}（額面）")
        print(f"   {'ルート':<14} | {'手数料計':>10} | {'手取り円':>12} | {'実効コスト':>8}")
        for name,p in ROUTES.items():
            net,fee=net_jpy(usd,p["fixed_jpy"],p["var_pct"])
            print(f"   {name:<14} | ¥{fee:>9,.0f} | ¥{net:>11,.0f} | {fee/gross*100:>6.2f}%")
    # 年間影響(攻めプラン合算の概算: 隔週出金=年26回, 1回平均額で換算)
    print("\n"+"="*78)
    print("年間影響の目安（攻め合算 ≈ 年¥3.7M を 隔週26回で出金=1回≈$900 と仮定）")
    print("="*78)
    per=3_727_795/USDJPY/26   # 1回あたりUSD
    print(f"   1回 ≈ ${per:,.0f} / 年26回")
    for name,p in ROUTES.items():
        _,fee=net_jpy(per,p["fixed_jpy"],p["var_pct"]); annual=fee*26
        print(f"   {name:<14}: 1回手数料¥{fee:>7,.0f} → 年間¥{annual:>9,.0f}（年収益比 {annual/3_727_795*100:.2f}%）")
    print("\n結論: 大口ほど『変動費(FXスプレッド)』が効く→ 暗号USDT(~0.25%)<Wise(~0.5%)<銀行直接(~0.8-1%+固定)。")
    print("      小口/高頻度は固定費が効く→ ここでも暗号・Wiseが有利。ただし暗号は『円転=課税イベント＋ペグ/送金リスク』、")
    print("      銀行直接はメガバンクの被仕向審査リスク。⚠全て代表値・要実額確認。")

    # 出金頻度別 年間手数料(攻め合算 年¥3.7M)。固定費はN回で増え、変動費(率)は頻度不変。
    REV=3_727_795
    print("\n"+"="*78)
    print(f"出金頻度別 年間手数料（攻め合算 年¥{REV:,}・固定費×回数＋変動費は総額の率）")
    print("="*78)
    freqs={"隔週(26回)":26, "月1(12回)":12, "四半期(4回)":4, "年1(1回)":1}
    print(f"   {'頻度':<12} | " + " | ".join(f"{n:>14}" for n in ROUTES))
    for fl,N in freqs.items():
        cells=[]
        for name,p in ROUTES.items():
            ann=p["var_pct"]*REV + p["fixed_jpy"]*N
            cells.append(f"¥{ann:>8,.0f}({ann/REV*100:.2f}%)")
        print(f"   {fl:<12} | " + " | ".join(f"{c:>14}" for c in cells))
    print("\n   → 月1にすると銀行直接は 4.6%→約2.6% に低下し『許容範囲』に入る(固定費の希薄化)。")
    print("     だが Wise/暗号(~0.4-0.6%)には及ばず、かつ出金頻度↓=口座残高が大きく滞留→業者破綻の被弾額↑。")
    print("     攻め(破綻リスク前提)なら『高頻度×低手数料(Wise/暗号)』が整合。簡便さ/税の単純さ重視なら『月1×銀行』も可。")

if __name__=="__main__":
    main()
