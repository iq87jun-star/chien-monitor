# -*- coding: utf-8 -*-
"""docs/218: 記録用デモ口座の実約定を「レグ別フォワード系列」に変換し、任意の重みでポートフォリオを合成する。

入力:
  1) MT5 取引履歴 xlsx(1 口座分)。コメント列が `RFMon_USDJPY_h4` / `RFv4_GBPJPY` / `RFHold_GER40` を持つ。
  2) 記録EAの CSV `<tag>_entries.csv`(任意)。建玉時のスプレッドが入っており、
     **任意のスプレッドキャップを後処理で当てられる**(docs/218 §8.3)。

使い方:
  python3 research/forward/leg_forward.py <history.xlsx> [--entries rec1_entries.csv ...]
      [--notional 100000] [--cap GBPJPY=2.9,AUDJPY=2.9] [--weights Mon/GBPJPY=0.374,...] [--out results/xxx.json]

出力: レグ別の日次リターン(名目に対する%)・月次・累積、およびキャップ適用で落ちた建玉の一覧。
"""
import os, sys, json, argparse, re, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import mt5_report as mr

LEG_RE = re.compile(r"^RF(Mon|v4|Hold)_([A-Za-z0-9._]+?)(?:_h(\d+))?$")


def parse_legs(pos):
    """コメント列からレグを復元。`RFMon_USDJPY_h4` → family=Mon, symbol=USDJPY, hour=4"""
    out = []
    for _, r in pos.iterrows():
        m = LEG_RE.match(str(r.get("comment", "") or "").strip())
        if not m:
            continue
        out.append(dict(family=m.group(1), symbol=m.group(2), hour=(int(m.group(3)) if m.group(3) else -1),
                        open_time=r["open_time"], close_time=r["close_time"], volume=r["volume"], net=r["net"]))
    return pd.DataFrame(out)


def load_entries(paths):
    """記録EAの CSV を読み、ENTRY 行だけ返す(スプレッド付き)。"""
    if not paths:
        return pd.DataFrame()
    fs = []
    for p in paths:
        d = pd.read_csv(p)
        d["utc"] = pd.to_datetime(d["utc"], errors="coerce")
        fs.append(d)
    d = pd.concat(fs, ignore_index=True).dropna(subset=["utc"])
    return d


def attach_spread(legs, entries, tol_sec=180):
    """建玉に、記録CSVの同一(family, symbol, hour)で時刻が最も近い ENTRY のスプレッドを付ける。"""
    legs = legs.copy(); legs["spread_pips"] = np.nan
    if entries.empty:
        return legs
    ent = entries[entries.event == "ENTRY"]
    for i, r in legs.iterrows():
        c = ent[(ent.family == r.family) & (ent.symbol == r.symbol) & (ent.hour == r.hour)]
        if c.empty:
            continue
        d = (c.utc - r.open_time).abs()
        j = d.idxmin()
        if d.loc[j] <= pd.Timedelta(seconds=tol_sec):
            legs.at[i, "spread_pips"] = float(c.loc[j, "spread_pips"])
    return legs


def apply_cap(legs, caps):
    """スプレッドキャップを後から当てる。記録が無い建玉は残す(保守側)。"""
    if not caps:
        return legs, pd.DataFrame()
    keep = pd.Series(True, index=legs.index)
    for sym, cap in caps.items():
        hit = (legs.symbol == sym) & legs.spread_pips.notna() & (legs.spread_pips > cap)
        keep &= ~hit
    return legs[keep].copy(), legs[~keep].copy()


def leg_series(legs, notional):
    """レグ別の日次リターン(決済日ベース・名目に対する%)。"""
    if legs.empty:
        return pd.DataFrame()
    legs = legs.copy()
    legs["key"] = legs.family + "/" + legs.symbol
    legs["day"] = pd.to_datetime(legs.close_time).dt.normalize()
    piv = legs.pivot_table(index="day", columns="key", values="net", aggfunc="sum") / notional * 100
    idx = pd.bdate_range(piv.index.min(), piv.index.max())
    return piv.reindex(idx).fillna(0.0)


def stats(s):
    c = (1 + s / 100).cumprod()
    return dict(n_days=int((s != 0).sum()), cum_pct=round(float(c.iloc[-1] - 1) * 100, 2),
                mean_bps=round(float(s[s != 0].mean()) * 100, 1) if (s != 0).any() else 0.0,
                maxdd_pct=round(float((c / c.cummax() - 1).min()) * 100, 2),
                worst_day_pct=round(float(s.min()), 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("--entries", nargs="*", default=[])
    ap.add_argument("--notional", type=float, default=100000.0, help="1レグの名目(記録プリセットの initBal×weight×mult)")
    ap.add_argument("--cap", default="", help="例 GBPJPY=2.9,AUDJPY=2.9(pip)")
    ap.add_argument("--weights", default="", help="例 Mon/GBPJPY=0.374,Mon/AUDJPY=0.322,v4/USDJPY=0.304")
    ap.add_argument("--mult", type=float, default=1.0)
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    _, pos, *_ = mr.parse(a.xlsx)
    pos = pos.dropna(subset=["close_time"])
    legs = parse_legs(pos)
    if legs.empty:
        print("コメント列から RecentFit 系のレグを復元できません。記録EAのレポートか確認してください。"); return
    print(f"建玉 {len(legs)} 件 / レグ {legs.family.str.cat(legs.symbol, sep='/').nunique()} 種 "
          f"{legs.open_time.min().date()}..{legs.close_time.max().date()}")

    entries = load_entries(a.entries)
    legs = attach_spread(legs, entries)
    have = int(legs.spread_pips.notna().sum())
    print(f"スプレッド記録の紐付け: {have}/{len(legs)} 件" + ("" if have else "(記録CSV未指定 → キャップ後処理は使えません)"))

    caps = {}
    if a.cap:
        for kv in a.cap.split(","):
            k, v = kv.split("="); caps[k.strip()] = float(v)
    kept, dropped = apply_cap(legs, caps)
    if caps:
        print(f"キャップ適用: {len(dropped)} 件を除外 " + str({k: int((dropped.symbol == k).sum()) for k in caps}))

    ser = leg_series(kept, a.notional)
    print("\n=== レグ別(名目 %s に対する%%) ===" % f"{a.notional:,.0f}")
    rows = {}
    for k in sorted(ser.columns):
        rows[k] = stats(ser[k])
        r = rows[k]
        print(f"  {k:16s} 建玉日{r['n_days']:4d} 累積{r['cum_pct']:+7.2f}% 平均{r['mean_bps']:+6.1f}bps "
              f"maxDD{r['maxdd_pct']:6.2f}% 最悪日{r['worst_day_pct']:+6.2f}%")

    out = dict(source=os.path.basename(a.xlsx), notional=a.notional, caps=caps,
               dropped=int(len(dropped)), legs=rows)
    if a.weights:
        w = {}
        for kv in a.weights.split(","):
            k, v = kv.split("="); w[k.strip()] = float(v)
        miss = [k for k in w if k not in ser.columns]
        if miss:
            print("\n⚠ 記録に無いレグ:", miss)
        comp = sum(ser[k] * v for k, v in w.items() if k in ser.columns) * a.mult
        out["portfolio"] = dict(weights=w, mult=a.mult, **stats(comp))
        print(f"\n=== 合成ポートフォリオ(倍率 {a.mult}) ===")
        print("  " + json.dumps(out["portfolio"], ensure_ascii=False))

    if a.out:
        json.dump(out, open(a.out, "w"), ensure_ascii=False, indent=1)
        print("\nsaved:", a.out)


if __name__ == "__main__":
    main()
