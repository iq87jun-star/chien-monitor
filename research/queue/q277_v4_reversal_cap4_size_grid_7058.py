# -*- coding: utf-8 -*-
"""docs/244 Q277(2026-11-24 登録「登録実行」・セル 5): FTMO 50k 7058 に FX の逆張りを小さく足す形 — 同時 4 本までの上限と、大きさの刻み。
口座モデルと逆張りの入れ方は Q276 と同じ(q276 のモジュールをそのまま使う)。今回足すのは「同時 4 本まで」の上限つきの台帳。
上限: EA(SleeveV4)と同じペアの順で日ごとに判定し、建てる日の始値の時点で持っている本数が 4 本以上なら、その日の残りのペアは建てない(見送ったペアは翌日また判定)。
型(セル 5): 上限ありで、1 取引あたりの名目 = 円クロスの倍率 × 0.0625 / 0.09375 / 0.125 / 0.15625 / 0.1875。基準 = 現状(逆張りなし)。判定 = Q233 の ev_ok。
提案に進める条件: 連続する 3 つ以上の刻みが変更候補。参照: 上限なしの同じ刻み / 次の段階(Verification)。
照合: 上限なしの日ごとの判定 = Q276 の台帳(612 取引・+70.97%)。上限なしの × 0.125 = Q276 の行(99.5 / 0.5・76.0 / 20.9)。
使い方: cd research && PYTHONPATH=queue python3 -W ignore queue/q277_v4_reversal_cap4_size_grid_7058.py <累積セル数>   出力: results/q277_v4_cap4_size_grid.csv"""
import os, sys
_ARGV = list(sys.argv)
import q276_v4_reversal_account_model as m
np, pd, pv, n5 = m.np, m.pd, m.pv, m.n5
ORDER = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD", "EURJPY", "GBPJPY"]; FS = (0.0625, 0.09375, 0.125, 0.15625, 0.1875)
def ledger_joint(cap):
    """日ごと・EA のペア順で判定する台帳。cap = 同時に持つ本数の上限(None = 上限なし)。規則は v4_monthly と同じ。"""
    P = {}
    for p in ORDER:
        df = pv.load_daily(p); idx = [pd.Timestamp(x).tz_localize(None) if getattr(x, "tzinfo", None) else pd.Timestamp(x) for x in df.index]
        o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
        P[p] = dict(o=o, h=h, l=l, c=c, idx=idx, n=len(c), rsi=pv.rsi_wilder(c, 14), atr=pv.atr_daily(h, l, c, 14), pos={d: k for k, d in enumerate(idx)}, nxt=22, cost=2 * pv.pip_size(p))
    days = sorted(set().union(*[set(x["idx"]) for x in P.values()])); T = []; open_iv = []; skipped = 0
    for D in days:
        for p in ORDER:
            x = P[p]; i = x["pos"].get(D)
            if i is None or i < x["nxt"] or i >= x["n"] - 1: continue
            c, o, h, l = x["c"], x["o"], x["h"], x["l"]; win = c[i - 20:i]; mean = win.mean(); sd = win.std(ddof=1); z = (c[i] - mean) / sd if sd > 0 else 0.0; down = 0
            for k in range(12):
                if i - k - 1 >= 0 and c[i - k] < c[i - k - 1]: down += 1
                else: break
            up = 0
            for k in range(12):
                if i - k - 1 >= 0 and c[i - k] > c[i - k - 1]: up += 1
                else: break
            ret = (c[i] - c[i - 1]) / c[i - 1] if c[i - 1] else 0.0
            buy = int(x["rsi"][i] < 35) + int(z < -1.5) + int(down >= 3) + int(ret < -0.005); sell = int(x["rsi"][i] > 65) + int(z > 1.5) + int(up >= 3) + int(ret > 0.005)
            sig = 1 if (buy >= 4 and buy > sell) else (-1 if (sell >= 4 and sell > buy) else 0)
            if sig == 0: continue
            entry = o[i + 1]; sld = 1.5 * x["atr"][i]; tpd = 1.2 * sld
            if sld <= 0: continue
            ed = x["idx"][i + 1]
            if cap is not None and sum(1 for a, b in open_iv if a <= ed <= b) >= cap: skipped += 1; continue      # EA は break(残りのペアも同じ本数を見るので同じ結果)
            sl = entry - sig * sld; tp = entry + sig * tpd; ex = None; j = i + 1; held = 0
            while j < x["n"] and held < 8:
                if sig > 0:
                    if l[j] <= sl: ex = sl; break
                    if h[j] >= tp: ex = tp; break
                else:
                    if h[j] >= sl: ex = sl; break
                    if l[j] <= tp: ex = tp; break
                j += 1; held += 1
            jx = min(j, x["n"] - 1)
            if ex is None: ex = c[jx]
            prev = entry; ds, pn, wo = [], [], []
            for t in range(i + 1, jx + 1):
                px = ex if t == jx else c[t]; r = sig * (px - prev) / entry; adv = max(l[t], sl) if sig > 0 else min(h[t], sl); wr = sig * (adv - prev) / entry
                if t == i + 1: r -= x["cost"] / entry; wr -= x["cost"] / entry
                ds.append(x["idx"][t]); pn.append(r); wo.append(min(r, wr)); prev = px
            T.append(dict(pair=p, dates=ds, pnl=pn, worst=wo, ret=sig * (ex / entry - 1.0) - x["cost"] / entry, exit=x["idx"][jx])); open_iv.append((ed, x["idx"][jx])); x["nxt"] = max(i + 1, j)
    return T, skipped
def use(T):
    VF, VC, VL, CF, used = m.v4_arrays(T); n5["VF"], n5["VC"], n5["VL"], n5["CF"] = VF, VC, VL, CF; return VF, VC, VL, used
def desc(T, tag):
    VF, VC, VL, used = use(T); N = len(VC); cnt = np.zeros(N, int); DID = {}
    for w, d in enumerate(m.MONS):
        for i in range(5): DID[pd.Timestamp(d) + pd.Timedelta(days=i)] = 5 * w + i
    for t in T:
        for xx in t["dates"]:
            k = DID.get(pd.Timestamp(xx).normalize())
            if k is not None: cnt[k] += 1
    tot = VF + VL; yrs = {}
    for t in T: yrs.setdefault(t["exit"].year, []).append(t["ret"])
    print(f"[{tag}] {len(T)} 取引・合計 {sum(t['ret'] for t in T) * 100:.2f}%・期間内 {used}・日次の標準偏差 {VC.std() * 100:.3f}%・最悪日 {VC.min() * 100:.2f}%・持ち越し + 当日の最悪の最小 {tot.min() * 100:.2f}%・同時保有の最大 {cnt.max()} 本・名目 0.75 倍で逆張りだけでガード 4% に届く日 年 {(0.75 * tot <= -0.04).sum() / N * 260:.2f} 回", flush=True)
    print("   年別 %:", {y: round(sum(v) * 100, 1) for y, v in sorted(yrs.items())}, flush=True)
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 5; rows = []
    T0 = m.v4_ledger(); TU, _ = ledger_joint(None); TC, skc = ledger_joint(4)
    print(f"照合: 上限なしの日ごとの判定 {len(TU)} 取引・合計 {sum(t['ret'] for t in TU) * 100:.2f}% / Q276 の台帳 {len(T0)} 取引・{sum(t['ret'] for t in T0) * 100:.2f}%(一致 {len(TU) == len(T0) and abs(sum(t['ret'] for t in TU) - sum(t['ret'] for t in T0)) < 1e-9})・上限 4 本で見送った判定 {skc} 回", flush=True)
    desc(TU, "上限なし"); desc(TC, "上限 4 本")
    okA = ~np.isnan(m.GA["A"][2]); idx = np.arange(m.W); STARTS = {"W1": [s for s in idx if m.MONS[s] >= m.PM and s + 52 <= m.W and okA[s]], "W2": [s for s in idx if m.MONS[s] < m.PM and s + 52 <= m.W and m.MONS[s + 51] < m.PM and okA[s]]}
    key = "531407058"; mm = 6.0; items, cap, g = m.norm_items(key)
    # 段階, SKEW, 200 日線, 縮小の下限, 開始, 目標
    for stage, skew, tilt, smin, start, target, judged in (("いま(第 1 段階・開始 +5.39%)", False, False, None, 52697.16 / 5e4 - 1, 0.10, True), ("参照: 次の段階(Verification・開始 0・目標 +5%)", True, True, 0.5, 0.0, 0.05, False)):
        fac = m.make_fac(items, skew, 0.5 if tilt else None); levels = list(range(len(m.LV))) if smin is not None else [m.TOP]
        ML = m.mon_levels(items, None, fac, mm, levels); ML = {li: ML[li if li in ML else m.TOP] for li in range(len(m.LV))}; m.setup(0.0, 0)
        kw = dict(start=start, target=target, mdd=0.10, pad=0.01, smin=smin, trail=False, g=g, swm=0.0, wg0=0.0, carry0=0.0, wg_re=0.0, integ=True)
        use(TC); b = m.one(ML, STARTS, kw, 0.0); rows.append(dict(stage=stage, ledger="—", variant="現状(逆張りなし)", f=0.0, v4_notional=0.0, cells=0, verdict="基準", **b)); print(f"  {stage}: 現状 {b}", flush=True)
        for tag, T, cell in (("上限 4 本", TC, 1 if judged else 0), ("参照: 上限なし", TU, 0)):
            if not judged and tag.startswith("参照"): continue
            use(T)
            for f in FS:
                v = m.one(ML, STARTS, kw, mm * f); ok = m.ev_ok(b, v); rows.append(dict(stage=stage, ledger=tag, variant=f"逆張り × {f}", f=f, v4_notional=round(mm * f, 4), cells=cell, verdict=("変更候補" if ok else "現行どおり") if cell else ("(変更候補に相当)" if ok else "(現行どおりに相当)"), **v)); print(f"  {stage} {tag} × {f}: {v} → {'○' if ok else '×'}", flush=True)
    D = pd.DataFrame(rows); D.to_csv("results/q277_v4_cap4_size_grid.csv", index=False); assert int(D.cells.sum()) == N
    pd.set_option("display.width", 320); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 50)
    print(f"\n== Q277(累積セル {cum} + {N} = {cum + N}・FTMO 50k 7058・到達 % / 失格 %・W1 = 2021-08 以降の開始・W2 = 2016-11〜2020-07 の開始) =="); print(D.to_string(index=False))
    j = D[D.cells == 1].sort_values("f"); flags = (j.verdict == "変更候補").tolist(); run_len = best = 0
    for x in flags:
        run_len = run_len + 1 if x else 0; best = max(best, run_len)
    print(f"\n判定: 変更候補 {sum(flags)} / {len(flags)} 件(刻みの順 {['○' if x else '×' for x in flags]})・連続する変更候補の最大 {best} → 提案に進める条件(連続 3 つ以上)を{'満たす' if best >= 3 else '満たさない'}")
    u = D[(D.ledger == "参照: 上限なし") & (D.f == 0.125)].iloc[0]; print("照合(Q276 の × 0.125: 99.5 / 0.5・76.0 / 20.9):", (u.reach_W1, u.fail_W1, u.reach_W2, u.fail_W2))
