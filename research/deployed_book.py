# -*- coding: utf-8 -*-
"""
deployed_book.py — 稼働中口座の配備レッグの**単一情報源**(docs/197 §7の残タスク2)。

これまで配備構成は docs/177/178/181/182/183/196 に分散しており、
「現ブック合成」を再現するたびに各docから手で書き写していた
(recentfit_nonfx_screen.py の BOOK_CELLS / recentfit_portfolio_compare.py の main が別々に定義)。
docs/197 §3 の ρ_book は**この合成を基準に相関を測る**ため、定義が1箇所に無いと
再現性が担保できない。本モジュールがその1箇所である。

⚠ 構成を変更したら**必ず本ファイルを更新する**こと(配備カードのdocsと本ファイルの二重管理)。
⚠ 全て Yahoo日足による近似であり実口座成績ではない。近似の内容は APPROX を参照。
"""
import os, sys
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recentfit_screen as base
import recentfit_nonfx_screen as nfx          # v4_cell_nonfx とユニバース拡張(WTI/NATGAS)
import recentfit_portfolio_compare as pc      # mon_cell_dow / rsi2_cell(A案の構築式)

APPROX = [
    "S1/S2/Mon = 月曜o2o(実EAは12h保有・24hのものもある)",
    "S3 = 木曜o2o SHORT(実EAは16UTC+6h)",
    "S4/S5 = RSI(2)逆張りをD1で再現",
    "A案は各スリーブ等リスク(1.25%/回)を等ウェイト0.2で近似",
    "Fintokeiパール ¥500万≈$32k / 速攻プロ ¥2,000万≈$129k(155円換算)",
    "Yahoo日足近似・実口座成績ではない",
]

# 生成式のディスパッチ
CELL_FN = {
    "Mon":   base.mon_cell,
    "Hold":  base.hold_cell,
    "TSMOM": base.tsmom_cell,
    "v4":    base.v4_cell,
    "v4nfx": nfx.v4_cell_nonfx,                                  # 非FX銘柄のv4(相対コスト)
    "MonThuS": lambda s: pc.mon_cell_dow(s, 3, short=True),      # A案S3
    "RSI2a": lambda s: pc.rsi2_cell(s, 30, 70, 5),               # A案S4(GBPUSD)
    "RSI2b": lambda s: pc.rsi2_cell(s, 20, 80, 3),               # A案S5(GBPJPY)
}

# --- 稼働中の全口座(2026-09-01時点) ---
# legs = [(family, symbol, weight)] / capital_usd = 口座サイズ(USD換算) / mult = 配備倍率
BOOK = {
    "FN_Instant20k_11988011": dict(
        broker="FN", track="RecentFit Instant", doc="docs/177 §1",
        capital_usd=20.0, mult=4.0,
        legs=[("Mon", "GBPJPY", 0.374), ("Mon", "AUDJPY", 0.322), ("v4", "USDJPY", 0.304)]),

    "FTMO100k_531343523": dict(
        broker="FTMO", track="A案 RecentFit5", doc="docs/176 §1 / docs/178 §3",
        capital_usd=100.0, mult=4.8,          # 等ウェイト近似の校正値(portfolio_compare準拠)
        legs=[("Mon", "GBPUSD", 0.2), ("Mon", "GBPJPY", 0.2), ("MonThuS", "USDCHF", 0.2),
              ("RSI2a", "GBPUSD", 0.2), ("RSI2b", "GBPJPY", 0.2)]),

    "Fintokei_Pearl500": dict(
        broker="Fintokei", track="B案 RecentFit 2026H2", doc="docs/178 §2",
        capital_usd=32.0, mult=4.0,
        legs=[("Mon", "GBPJPY", 0.374), ("Mon", "AUDJPY", 0.322), ("v4", "USDJPY", 0.304)]),

    "FTMO50k_531407058": dict(
        broker="FTMO", track="C案 直近6ヶ月", doc="docs/181 §1",
        capital_usd=50.0, mult=6.0,
        legs=[("Mon", "GBPJPY", 0.323), ("Mon", "AUDJPY", 0.269),
              ("v4", "NZDUSD", 0.207), ("v4", "AUDUSD", 0.201)]),

    "FTMO50k_521100397": dict(
        broker="FTMO", track="D案 直近3ヶ月 2026-09規則適合版", doc="docs/196 §3",
        capital_usd=50.0, mult=5.24,
        legs=[("Mon", "USDJPY", 0.321), ("Mon", "EURJPY", 0.277),
              ("v4", "GBPJPY", 0.303), ("Hold", "GER40", 0.099)]),

    "FN100k_14166201": dict(
        broker="FN", track="非FX分散", doc="docs/182 §5",
        capital_usd=100.0, mult=1.48,
        legs=[("Mon", "ETHUSD", 0.145), ("v4nfx", "BTCUSD", 0.211),
              ("Hold", "UK100", 0.491), ("Hold", "WTI", 0.153)]),

    "Fintokei_Sokkou2000_6078225": dict(
        broker="Fintokei", track="速攻プロ C6m系", doc="docs/183 §2",
        capital_usd=129.0, mult=2.5,
        legs=[("Mon", "GBPJPY", 0.323), ("Mon", "AUDJPY", 0.269),
              ("v4", "NZDUSD", 0.207), ("v4", "AUDUSD", 0.201)]),
}

# ⚠ 合成に含められない口座(生成式が本リポジトリのセル型に存在しないため)
NOT_RECONSTRUCTIBLE = {
    "FN100k_14074882": dict(
        broker="FN", track="季節RG3(正攻法・指数/金系)", doc="docs/172 / docs/179 §1",
        capital_usd=100.0,
        reason="季節RG3の生成式は本ブランチのresearch/に無い(recentfit系のセル型ではない)。"
               "recentfit_nonfx_screen.py の BOOK_CELLS も同じ理由で除外していた。"
               "ρ_bookの基準からは欠落する — この分だけ現ブックの実相関は過小評価され得る。"),
}


def leg_series(fam, sym):
    if fam not in CELL_FN:
        raise KeyError(f"未知のファミリー: {fam}")
    return CELL_FN[fam](sym)


def account_composite(key):
    """1口座の合成(倍率抜き・重み合計1.0)"""
    acc = BOOK[key]
    parts = [(leg_series(f, s), w) for f, s, w in acc["legs"]]
    idx = sorted(set().union(*[set(s.index) for s, _ in parts]))
    out = pd.Series(0.0, index=pd.DatetimeIndex(idx))
    for s, w in parts:
        out = out.add(s.reindex(out.index).fillna(0.0) * w, fill_value=0.0)
    return out


def book_composite(exclude=None, end=None):
    """現ブック合成(docs/197 §3の基準)。

    口座 i の日次$損益 ≈ capital_i × mult_i × legs_i。したがって
    ブック全体のリターン = Σ(capital_i × mult_i × legs_i) / Σ(capital_i × mult_i)。
    倍率も資金も**相対的な寄与**を決めるため両方を掛ける(倍率の高い小口座は寄与が大きい)。

    exclude: 除外する口座キー(または集合)。再スクリーニング対象口座は自分を除く。
    end:     この日付までに切る(既定は base.W_ALL1)。
    """
    ex = set() if exclude is None else ({exclude} if isinstance(exclude, str) else set(exclude))
    keys = [k for k in BOOK if k not in ex]
    if not keys:
        raise ValueError("合成対象の口座が無い")
    raw = {k: BOOK[k]["capital_usd"] * BOOK[k]["mult"] for k in keys}
    tot = sum(raw.values())
    comps = {k: account_composite(k) for k in keys}
    idx = sorted(set().union(*[set(s.index) for s in comps.values()]))
    out = pd.Series(0.0, index=pd.DatetimeIndex(idx))
    for k in keys:
        out = out.add(comps[k].reindex(out.index).fillna(0.0) * (raw[k] / tot), fill_value=0.0)
    e = base.W_ALL1 if end is None else end
    return out[(out.index >= base.W_ALL0) & (out.index <= e)]


def summary():
    tot_cap = sum(v["capital_usd"] for v in BOOK.values())
    lines = [f"稼働口座 {len(BOOK)}件(合成可)+{len(NOT_RECONSTRUCTIBLE)}件(合成不可)"
             f" / 合成可の資金合計 ${tot_cap:.0f}k"]
    for k, v in BOOK.items():
        w = v["capital_usd"] * v["mult"]
        legs = " ".join(f"{f}:{s}:{wt}" for f, s, wt in v["legs"])
        lines.append(f"  {k:28s} {v['broker']:9s} cap${v['capital_usd']:6.0f}k x{v['mult']:<5} "
                     f"寄与{w/sum(BOOK[x]['capital_usd']*BOOK[x]['mult'] for x in BOOK)*100:5.1f}%  {legs}")
    for k, v in NOT_RECONSTRUCTIBLE.items():
        lines.append(f"  {k:28s} {v['broker']:9s} cap${v['capital_usd']:6.0f}k  ⚠合成不可: {v['track']}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(summary())
