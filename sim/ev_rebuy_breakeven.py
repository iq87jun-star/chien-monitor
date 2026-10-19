#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ev_rebuy_breakeven.py — 「攻め vs 守り、再契約費用を勘案した期待値(EV)」判定。

問い(ユーザー): 業者破綻/失格で再契約費用がかかっても、攻め(高倍率)の方が収益とのEVで得策か？

モデル(定常状態EV):
  ・インスタント(Blueberry等): 口座は業者資金。失格しても損失は掛け金F(返金なし)に上限。
    年あたり失格確率 f で口座喪失→F払って再契約。利益は毎サイクル出金(攻めの前提)。
    → 年間ネットEV ≈ payout(倍率) − F × f(倍率)。
  ・プロップ(FN等): 掛け金は通過で返金。失格(審査中)時のみF損失→再挑戦。
    funded後はインスタント同様(口座=業者資金)。
  ・損益分岐の掛け金 F* : 倍率Aより攻めのBが得になる上限費用。
    F* = (payout_B − payout_A) / (f_B − f_A)。実費 F < F* なら『攻めBが得』。

数値は docs/46 の実10年確定値(推奨3種・各口座)を入力。payout=分配後 円/年, f=年失格確率。
⚠ 限界: payout は系列の幾何年率で『口座リセットの空白』を完全には織り込まない(高倍率でやや楽観)。
   よって損益分岐F*は『攻めに有利な上限』の上振れ目安。厳密には足内リセットMC(別途)で。
"""

# ---- docs/46 実10年確定値(推奨3種) ----
# INSTANT: Blueberry $50k, 分配80%。(payout円/年, 年失格f)
INSTANT = {
 "1.0x": dict(payout=610_931, f=0.001),   # 5年0.5%≈年0.1%
 "1.5x": dict(payout=928_223, f=0.018),   # 5年8.8%
 "2.0x": dict(payout=1_253_219, f=0.074), # 5年31.8%
 "2.5x": dict(payout=1_585_754, f=0.209), # 5年69.0%
 "3.0x": dict(payout=1_925_637, f=0.247), # 5年75.8%
}
# PROP funded: FN $100k, 分配80%。(payout円/年, 年失格f) ※資金化後を維持した場合
PROP = {
 "1.0x": dict(payout=1_221_863, f=0.0004),
 "1.5x": dict(payout=1_856_446, f=0.009),
 "2.0x": dict(payout=2_506_438, f=0.023),
 "2.5x": dict(payout=3_171_509, f=0.068),
 "3.0x": dict(payout=3_851_273, f=0.092),
}
# 掛け金(再契約費用)・円。クーポン有無で幅。
FEE_INSTANT = {"クーポン¥117k":117_086, "定価¥167k":167_265}
FEE_PROP    = {"FN$549≈¥87k(通過で返金)":87_000}

def net_ev(table, fee):
    return {k: v["payout"] - fee*v["f"] for k,v in table.items()}

def breakeven(table):
    """隣接倍率間で『攻めが得になる掛け金上限 F*』。"""
    ks=list(table.keys()); out={}
    for a,b in zip(ks,ks[1:]):
        dpay=table[b]["payout"]-table[a]["payout"]; dff=table[b]["f"]-table[a]["f"]
        out[f"{a}->{b}"]= (dpay/dff) if dff>0 else float("inf")
    return out

def show(name, table, fees):
    print("="*70); print(f"■ {name}"); print("="*70)
    print(f"  {'倍率':>5} | {'payout/年':>11} | {'年失格':>6} | " +
          " | ".join(f"netEV({fn})" for fn in fees))
    for k,v in table.items():
        evs=[net_ev(table,f)[k] for f in fees.values()]
        print(f"  {k:>5} | ¥{v['payout']:>10,} | {v['f']*100:>5.1f}% | " +
              " | ".join(f"¥{e:>10,.0f}" for e in evs))
    print("\n  [損益分岐] 攻めが得になる『再契約費用の上限 F*』(実費がこれ未満なら攻めが得):")
    for pair,fstar in breakeven(table).items():
        print(f"    {pair:>12}: F* = ¥{fstar:>12,.0f}")
    # 各掛け金で netEV 最大の倍率
    for fn,f in fees.items():
        ev=net_ev(table,f); best=max(ev,key=ev.get)
        print(f"  → 掛け金 {fn}: netEV最大 = {best} (¥{ev[best]:,.0f}/年)")

if __name__=="__main__":
    print("再契約費用を勘案した EV 判定（docs/46 実10年確定値・推奨3種）\n")
    show("インスタント Blueberry $50k(失格=掛け金F損失/口座は業者資金)", INSTANT, FEE_INSTANT)
    print()
    show("プロップ FN $100k 資金化後(維持時。掛け金は通過で返金)", PROP, FEE_PROP)
    print("\n総括: 失格1回の損失が『掛け金F』に上限される構造ゆえ、F≪収益差 である限り高倍率ほど netEV↑。")
    print("      実費(¥87k〜167k)は損益分岐F*(数百万円規模)を大きく下回る → 攻めがEVで得策(ユーザー判断は妥当)。")
    print("      ⚠ ただし payout は口座リセット空白を完全反映せず高倍率で楽観側。分散(破産確率)とエッジ持続")
    print("         (デモ要検証)は別軸。EV最大≠最適倍率。実務はインスタント~2.0x/プロップ~3.0xが現実的上限。")
