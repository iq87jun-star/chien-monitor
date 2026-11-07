# -*- coding: utf-8 -*-
"""docs/322 Q106(診断・セル 0): Fintokei「同時保有リスク 3%(トレードグループ)」警告線の実測と EA の警告線(InpBalGuardPct)との整合。
定義(docs/220 §2〜4・書面): 口座が建玉ゼロ(フラット)になってから次にフラットになるまでを 1 グループとし、その窓内の
  「確定損失 + 含み損」の合計が初期資金の 3% を超えた瞬間があれば警告。フラット化でリセット。
実測(外部価格を使わず口座データだけで閉じる):
  (a) グループ損益(h) = equity(h) − 窓開始時の残高 = floating(h) + 窓内に決済した net の合計 … equity_log(毎時)の分解能
  (b) SL 到達時の最悪(h) = 窓内の確定 net − Σ(建玉の SL までの損失) … 時間内の極値を上から抑える(ギャップ除く)
  (c) EA の警告線 = equity(h) − 日開始残高(サーバー日 00:00 = UTC 21:00)… InpBalGuardPct(2.8 / 4.0)で全決済+当日停止
出力: results/q106_fintokei_concurrent_risk.csv(口座 × 日: 最悪グループ損益 % ・ SL 最悪 % ・ EA 指標 % ・ 建玉数)、標準出力に要約。
使い方: cd research && python3 queue/q106_fintokei_concurrent_risk.py [--snapshot]   (--snapshot は最新行だけ 1 行/口座 … ダイジェスト用)
配備・manifest・EA は変更しない。"""
import os, sys, json, pandas as pd, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT); sys.path.insert(0, os.path.join(ROOT, "forward"))
import mt5_report as mr
INBOX = os.path.join(ROOT, "ops_inbox")
# 口座: (名称, 初期資金 = Fintokei 規則の分母, EA の InpBalGuardPct, 備考)
ACC = {"6104739": ("トパーズ 3500万", 35_000_000.0, 2.8, "P1・EA11 v1.18→v1.20"),
       "6104736": ("ルビー 1000万", 10_000_000.0, 2.8, "P1・B案 ×12"),
       "6071612": ("パール 500万(本口座)", 5_000_000.0, 4.0, "EA 基準残高は 5,175,220(自動取得)")}
SERVER_OFF = pd.Timedelta(hours=3)   # Fintokei(AXSE)サーバー時刻 = UTC+3(positions の h4 ショット 07:00 ⇔ ログ 13:00 JST)
WARN = 3.0

def load(acct):
    d = os.path.join(INBOX, acct)
    e = pd.read_csv(os.path.join(d, "equity_log.csv"), encoding="utf-8-sig"); e["t"] = pd.to_datetime(e.time_utc); e = e.sort_values("t").reset_index(drop=True)
    _, pos, *_ = mr.parse(os.path.join(d, "positions.csv")); pos = pos.dropna(subset=["close_time"]).copy()
    pos["ot"] = pos.open_time - SERVER_OFF; pos["ct"] = pos.close_time - SERVER_OFF
    op = os.path.join(d, "open_positions.csv"); o = pd.DataFrame()
    if os.path.exists(op) and os.path.getsize(op) > 5:
        o = pd.read_csv(op, encoding="utf-8-sig"); o["ot"] = pd.to_datetime(o.open_time, format="%Y.%m.%d %H:%M:%S") - SERVER_OFF; o["ct"] = pd.NaT
    return e, pos, o

def contract_value(pos):
    """銘柄ごとの 1 lot・価格 1.0 あたりの損益(口座通貨)。JPY クロスは 100,000、他は決済済み取引から中央値で推定。"""
    cv = {}
    for s, g in pos.groupby("symbol"):
        if "JPY" in s: cv[s] = 100_000.0; continue
        sign = np.where(g.type.str.lower() == "buy", 1.0, -1.0)
        d = (g.close_price - g.open_price) * sign * g.volume
        ok = d.abs() > 1e-9
        cv[s] = float(np.median((g.profit[ok] / d[ok]).abs())) if ok.any() else np.nan
    return cv

def run(acct, snapshot=False):
    name, init, guard, note = ACC[acct]
    e, pos, o = load(acct); cv = contract_value(pos)
    allp = pd.concat([pos[["symbol", "type", "volume", "open_price", "sl", "ot", "ct", "net"]], o.rename(columns={})[["symbol", "type", "volume", "open_price", "sl", "ot", "ct"]].assign(net=np.nan)] if len(o) else [pos[["symbol", "type", "volume", "open_price", "sl", "ot", "ct", "net"]]], ignore_index=True)
    allp["loss_sl"] = [abs(r.open_price - r.sl) * r.volume * cv.get(r.symbol, np.nan) if r.sl > 0 else np.nan for r in allp.itertuples()]
    # フラット時刻: 建玉数が 0 になる時刻の列(イベント走査)
    ev = sorted([(t, +1) for t in allp.ot] + [(t, -1) for t in allp.ct.dropna()])
    flats = []; n = 0; prev = None
    for t, d in ev:
        n += d
        if n == 0: flats.append(t)
    flats = pd.Series(sorted(set(flats)))
    rows = []
    for r in e.itertuples():
        h = r.t
        ws = flats[flats <= h]; ws = ws.iloc[-1] if len(ws) else allp.ot.min()
        inwin = allp[(allp.ct > ws) & (allp.ct <= h)]; realized = float(inwin.net.sum()) if len(inwin) else 0.0
        openp = allp[(allp.ot <= h) & ((allp.ct.isna()) | (allp.ct > h))]
        floating = float(r.equity - r.balance)
        group = floating + realized                                   # (a)
        slsum = float(openp.loss_sl.sum()); worst = realized - slsum  # (b)
        day0 = (h - pd.Timedelta(hours=21)).normalize() + pd.Timedelta(hours=21)   # サーバー日 00:00 = UTC 21:00(前日)
        d0 = e[(e.t >= day0) & (e.t <= h)]; dsb = float(d0.balance.iloc[0]) if len(d0) else float(r.balance)
        ea = float(r.equity) - dsb                                     # (c)
        rows.append(dict(acct=acct, t=h, equity=r.equity, balance=r.balance, n_open=len(openp), n_open_log=r.open_positions, win_start=ws,
                         realized_w=realized, floating=floating, group=group, group_pct=100 * group / init, slsum=slsum, worst_pct=100 * worst / init,
                         ea_pct=100 * ea / dsb, syms=",".join(sorted(set(openp.symbol)))))
    df = pd.DataFrame(rows)
    if snapshot:
        last = df.iloc[-1]
        print(f"  同時保有リスク {name}: 建玉 {int(last.n_open)} ({last.syms or '-'}) | グループ損益 {last.group_pct:+.2f}% | SL 到達時 {last.worst_pct:+.2f}%(警告 −{WARN}% まで {WARN + last.worst_pct:.2f}pt) | EA 日次指標 {last.ea_pct:+.2f}%(ガード −{guard}%)")
        return df
    # 要約
    w = df.loc[df.group_pct.idxmin()]; s = df.loc[df.worst_pct.idxmin()]; g = df.loc[df.ea_pct.idxmin()]
    gap = df[(df.group_pct <= -WARN) & (df.ea_pct > -guard)]
    print(f"== {acct} {name}(初期資金 {init:,.0f}・EA ガード −{guard}%・{note})")
    print(f"  期間 {df.t.min()} 〜 {df.t.max()} / 毎時 {len(df)} 行 / 建玉のあった時間 {int((df.n_open > 0).sum())} / フラット化 {len(flats)} 回 / 契約値 {json.dumps({k: round(v, 1) for k, v in cv.items()}, ensure_ascii=False)}")
    print(f"  (a) グループ損益の最悪 {w.group_pct:+.2f}% @ {w.t}(建玉 {int(w.n_open)}: {w.syms}・窓開始 {w.win_start}・確定 {w.realized_w:,.0f}・含み {w.floating:,.0f}) | ≤−3%: {int((df.group_pct <= -3).sum())} 時間 / ≤−2.5%: {int((df.group_pct <= -2.5).sum())} / ≤−2%: {int((df.group_pct <= -2).sum())}")
    print(f"  (b) SL 到達時の最悪 {s.worst_pct:+.2f}% @ {s.t}(建玉 {int(s.n_open)}: {s.syms}・SL 合計 {s.slsum:,.0f}) | ≤−3%: {int((df.worst_pct <= -3).sum())} 時間 / ≤−2.5%: {int((df.worst_pct <= -2.5).sum())}")
    print(f"  (c) EA 日次指標の最悪 {g.ea_pct:+.2f}% @ {g.t} | ガード −{guard}% 到達: {int((df.ea_pct <= -guard).sum())} 時間 | 3% 警告なのに EA 未発動(隙間): {len(gap)} 時間")
    # 日次集計
    df["date"] = df.t.dt.date
    day = df.groupby("date").agg(group_min=("group_pct", "min"), worst_min=("worst_pct", "min"), ea_min=("ea_pct", "min"), n_open_max=("n_open", "max"), hours=("t", "size")).reset_index()
    day.insert(0, "acct", acct)
    return day

if __name__ == "__main__":
    snap = "--snapshot" in sys.argv
    out = []
    for a in ACC:
        if not os.path.exists(os.path.join(INBOX, a, "equity_log.csv")): print(f"  {a}: equity_log なし"); continue
        out.append(run(a, snapshot=snap))
    if not snap:
        res = pd.concat(out, ignore_index=True); res.to_csv("results/q106_fintokei_concurrent_risk.csv", index=False)
        print(f"\n書き出し results/q106_fintokei_concurrent_risk.csv({len(res)} 行)")
