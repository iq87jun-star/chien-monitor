# -*- coding: utf-8 -*-
"""docs/244 Q253(2026-11-17 登録「登録して実行」・セル +11): 金の保有の含み損の持ち越しを、日次ガードの余地から引いた口座モデル。
きっかけ: 2026-11-16 の 1-Step のガード発動は、月曜のレグ −1.06% に金の含み損 −1.24%(先週からの持ち越し)が乗って −2.4% に届いた(docs/349 §9h)。
EA のガードは「現在の equity ≤ 当日開始時点の balance × (1 − g)」。balance に含み損益は入らないので、金の含み損はその日の余地を最初から削る(含み益は逆に余地を広げる)。
従来のモデル(Q188 系 run_guard)は月曜のレグだけを g と比べ、金の保有は入れていない(Q233 の評価中の表)か、日次系列として独立に足すだけ(Q190 / Q208)。
対象 = 金の保有を持つ評価中の 3 口座: 1-Step(金 0.36 倍・g 2.4%)/ 宝くじ(金 0.9 倍・g 4%・決済は採用済みの E1)/ FN 14074882(金 0.4 倍・g 4%)。
方法: 金の建値は経路に依存するので、週の無作為抽出ではなく「評価の開始週をずらして、実際の週の並びで 52 週まで進める」。開始週ごとに到達 / 失格 / 未決を数える。
  週 = 月曜のサーバー日の開始から 120 時間(5 日)。日ごとに「月曜レグの当日損益(既存の met)+ 金の含み損益(建値から・スワップ込み)」≤ −g を時間順に判定。
  発動 = 全決済(当日損益 −g × 1.1・従来と同じ約束)・その日は建てない・金は翌サーバー日の開始で建て直す(建値がリセット)。暦の月内 2 回の発動で月末まで新規停止(月曜も金も)。災害 SL(建値 −15%)。
  数量の段階(縮小の下限がある口座)は週の初めの累計から選ぶ。目標は週の途中の最高値(発動より前)でも判定(従来と同じ)。
  金の値動き: (A) 日足(data/XAUUSD_rf.csv・2016〜2026。日中は前日終値のまま・その日の最後に終値 / 安値を反映)= 全期間。(E) 1 時間足(2021-01〜2025-12)= 照合用。
型: 現状(いまの建玉と含み損から始め、建て直しは設計どおりの大きさ)/ 金なし / 建て直しを半分に / 建て直しをいまの大きさに / 参考: 金を独立に足す(従来の扱い)。
候補(セル 11): 1-Step 2・宝くじ いま 3 / 次 2・FN いま 2 / 次 2。判定は Q233 の ev_ok(基準 = 現状)。開始週は重なり合うので、割合は独立な試行の数ではない。
使い方: cd research && python3 -W ignore queue/q253_gold_hold_carry_vs_daily_guard.py   出力: results/q253_gold_carry_*.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(HERE, "q233_exit_switch_line_vs_vix_account_model.py"), encoding="utf-8").read().split("\n# ---------------- (A) 本口座後")[0]; n3 = {"__name__": "q233_head", "__file__": os.path.join(HERE, "q233_exit_switch_line_vs_vix_account_model.py")}; exec(compile(_src, "q233_head", "exec"), n3)
np, pd, q = n3["np"], n3["pd"], n3["q"]; norm_items, account_items, acct, make_fac, sim_eval, MODE, PM, LV, NP = (n3[k] for k in ("norm_items", "account_items", "acct", "make_fac", "sim_eval", "MODE", "PM", "LV", "NP"))
paths_fac, scaled, run_guard, P0, P1 = (n3[k] for k in ("paths_fac", "scaled", "run_guard", "P0", "P1")); us_dst = paths_fac.__globals__["us_dst"]; G = 37; COST = 5e-4; SLP = 0.15
# ---------- 金の価格 ----------
DG = pd.read_csv("data/XAUUSD_rf.csv"); DG["d"] = pd.to_datetime(DG["timestamp"]).dt.normalize(); DG = DG.drop_duplicates("d", keep="last").set_index("d").sort_index()
H1 = q.load("XAUUSD"); HR = pd.date_range(H1.index[0], H1.index[-1], freq="h"); HC = H1["close"].reindex(HR).ffill(); HL = H1["low"].reindex(HR).fillna(HC)
MONS = pd.date_range(P0 + pd.Timedelta(days=(7 - P0.dayofweek) % 7), P1, freq="7D"); W = len(MONS)
def gold_arrays(kind):
    """週ごとの金の時間別 終値 / 安値 [W, 120] と、週の直前の終値 [W]。kind = 'A'(日足)/ 'E'(1 時間足・範囲外の週は NaN)。"""
    pc = np.full((W, 120), np.nan); pl = np.full((W, 120), np.nan); pp = np.full(W, np.nan)
    for w, d in enumerate(MONS):
        if kind == "E":
            t0 = d - pd.Timedelta(days=1) + pd.Timedelta(hours=21 if us_dst(d) else 22); hrs = pd.date_range(t0, periods=120, freq="h")
            if t0 - pd.Timedelta(hours=1) < HR[0] or hrs[-1] > HR[-1]: continue
            pc[w] = HC.reindex(hrs).values; pl[w] = HL.reindex(hrs).values; pp[w] = float(HC[t0 - pd.Timedelta(hours=1)])
        else:
            prev = DG["close"][:d - pd.Timedelta(days=1)]
            if len(prev) == 0: continue
            last = float(prev.iloc[-1]); pp[w] = last
            for i in range(5):
                dd = d + pd.Timedelta(days=i); sl = slice(24 * i, 24 * i + 24); pc[w, sl] = last; pl[w, sl] = last
                if dd in DG.index: c = float(DG.close[dd]); pc[w, 24 * i + 23] = c; pl[w, 24 * i + 23] = min(float(DG.low[dd]), c); last = c
    return pc, pl, pp
GA = {k: gold_arrays(k) for k in ("A", "E")}
# ---------- 月曜レグ(段階別・暦の週にそろえる) ----------
def mon_levels(items, cap, fac, mult, levels):
    PA = paths_fac(items, None, fac, P0, P1) if cap is None else None; out = {}
    for li in levels:
        lv = LV[li]; P = scaled(PA, lv * mult) if PA is not None else paths_fac([(sy, ix, w * lv * mult) for sy, ix, w in items], cap, fac, P0, P1); D = {pd.Timestamp(p["d"]): p for p in P}
        met = {t: np.zeros((W, 120)) for t in ("lo", "cl")}; tot = {t: np.zeros((W, 120)) for t in ("lo", "cl")}; has = np.zeros(W, bool); off = np.zeros(W, int)
        for w, d in enumerate(MONS):
            o = 7 if us_dst(d) else 6; off[w] = o
            if d not in D: continue
            p = D[d]; has[w] = True
            for t in ("lo", "cl"):
                met[t][w, o:o + G] = p["met"][t]; met[t][w, o + G:48] = p["met"][t][-1]; tot[t][w, o:o + G] = p["tot"][t]; tot[t][w, o + G:] = p["fin"]
        out[li] = dict(met=met, tot=tot, has=has, off=off, P=P)
    return out
MK = np.array([[(d + pd.Timedelta(days=i)).year * 100 + (d + pd.Timedelta(days=i)).month for i in range(5)] for d in MONS]); TOP = len(LV) - 1; Z24 = np.zeros(24)
def episode(ML, tag, s, start, target, mdd, pad, smin, trail, g, swm, wg0, carry0, wg_re, integ, kind, st):
    """開始週 s から 52 週。戻り値: (1 到達 / 2 失格 / 0 未決, 週数)。st に月曜の開始時点の余地の使用率と発動の内訳をためる。"""
    pc, pl, pp = GA[kind]; px = pl if tag == "lo" else pc; c = float(start); hwm = max(c, 0.0); e = None; sw = 0.0; wg = 0.0; mkey = None; mf = 0; fresh = True
    for w in range(s, s + 52):
        if w >= W or np.isnan(pp[w]) or np.isnan(pc[w, -1]): return 0, 0
        floor = (min(hwm, 0.10) - mdd) if trail else -mdd; li = TOP if smin is None else int(np.abs(LV - min(max((c - floor) / mdd, smin), 1.0)).argmin()); M = ML[li]; has = bool(M["has"][w]); met, tot, totc = M["met"][tag][w], M["tot"][tag][w], M["tot"]["cl"][w]
        prev = pp[w]; f0 = (wg * (prev / e - 1) + sw) if e is not None else 0.0; real = 0.0; mon_closed = False; skip = not has; mon_val = float(totc[-1]) if has else 0.0; peakv = 0.0; fired_wk = False
        for i in range(5):
            if MK[w, i] != mkey: mkey = MK[w, i]; mf = 0
            halted = mf >= 2; a = 24 * i
            if i == 0 and halted: skip = True; mon_val = 0.0
            if e is None and not halted:
                wn = wg0 if fresh else wg_re
                if wn > 0:
                    wg = wn; sw = 0.0
                    if fresh and carry0: e = prev / (1 + carry0 / wg); f0 = carry0          # いまの建玉の含み損は開始時点の equity に入っている(二重に引かない)
                    else: e = prev * (1 + COST)
                fresh = False
            if e is not None: sw += wg * swm / 1e4 / 21.0; fl = wg * (px[w, a:a + 24] / e - 1) + sw; flc = wg * (pc[w, a:a + 24] / e - 1) + sw
            else: fl = Z24; flc = Z24
            mm = Z24 if (mon_closed or skip or i > 1) else met[a:a + 24]; today = 0.0; h0 = 0
            if i == 0 and e is not None and integ: st["room"].append(-(wg * (prev / e - 1) + sw) / g)
            while e is not None and integ:                                    # 災害 SL(建値 −15%): 確定して同じ時間に建て直す
                sl = np.flatnonzero(pl[w, a + h0:a + 24] <= e * (1 - SLP))
                if not len(sl): break
                hh = np.flatnonzero((mm + fl + today)[h0:] <= -g)
                if len(hh) and hh[0] <= sl[0]: break
                k = h0 + int(sl[0]); loss = -SLP * wg + sw; real += loss; today += loss; wg = wg_re if wg_re > 0 else wg; e = pc[w, a + k] * (1 + COST); sw = 0.0; h0 = k + 1; st["sl"] += 1
                fl = fl.copy(); flc = flc.copy(); fl[:k + 1] = 0.0; flc[:k + 1] = 0.0; fl[k + 1:] = wg * (px[w, a + k + 1:a + 24] / e - 1); flc[k + 1:] = wg * (pc[w, a + k + 1:a + 24] / e - 1)
                if h0 >= 24: break
            metric = mm + ((fl + today) if integ else 0.0); hit = np.flatnonzero(metric[h0:] <= -g) if h0 < 24 else []
            gcum = ((flc if e is not None else 0.0) - f0 + real) if True else 0.0; mpath = mon_val if (mon_closed or skip) else totc[a:a + 24]
            if len(hit):
                k = h0 + int(hit[0]); adj = -1.1 * g - float(metric[k]); mf += 1; mmk = float(mm[k]); glk = float(fl[k] + today) if integ else 0.0
                st["fires"].append((i, mmk <= -g, mmk < 0.0, glk)); 
                if not fired_wk and k > 0: peakv = max(peakv, float(np.max((mpath + gcum)[:k] if np.ndim(mpath + gcum) else mpath + gcum)))
                fired_wk = True
                if not mon_closed and not skip and i <= 1: mon_val = float(tot[a + k]); mon_closed = True
                if integ and e is not None: real += float(fl[k]) + adj; e = None; sw = 0.0
                else: mon_val += adj
            elif not fired_wk: peakv = max(peakv, float(np.max(mpath + gcum)))
            prev = pc[w, a + 23]
        fend = (wg * (prev / e - 1) + sw) if e is not None else 0.0; x = mon_val + (fend - f0 + real); st["weeks"] += 1
        if c + peakv >= target or c + x >= target: return 1, w - s + 1
        c += x
        if c <= floor + pad: return 2, w - s + 1
        hwm = max(hwm, c)
    return 0, 52
def run(ML, starts, kind, **kw):
    out = {}
    for tag in ("lo", "cl"):
        st = dict(room=[], fires=[], weeks=0, sl=0); res = [episode(ML, tag, s, kind=kind, st=st, **kw) for s in starts]; r = np.array([x[0] for x in res]); wk = np.array([x[1] for x in res])
        rm = np.array(st["room"]) if st["room"] else np.zeros(1); fr = st["fires"]; n = max(st["weeks"], 1)
        out[tag] = dict(reach=float((r == 1).mean()) * 100, fail=float((r == 2).mean()) * 100, weeks=(int(np.median(wk[r == 1])) if (r == 1).any() else 0), n=len(starts), fires_per52=len(fr) / n * 52, mon_alone=sum(1 for f in fr if f[0] <= 1 and f[1]) / n * 52,
                        mon_with_gold=sum(1 for f in fr if f[0] <= 1 and not f[1] and f[2]) / n * 52, gold_only=sum(1 for f in fr if not (f[0] <= 1 and f[2])) / n * 52, room25=float((rm >= 0.25).mean()) * 100, room50=float((rm >= 0.5).mean()) * 100, room75=float((rm >= 0.75).mean()) * 100, sl=st["sl"])
    return out
# ---------- 口座 ----------
# 表示名, 口座キー, 段階, 円クロス倍率, SKEW, 200 日線, 縮小の下限, 追随型, 開始(2026-11-16 21:22 UTC の equity), 目標, 停止線の手前幅, cap, 決済の型, 金(設計), 金(いまの建玉), いまの含み損(初期残高比), スワップ bps/月
B = [("1-Step", "531466484", "いま", None, True, False, None, True, 100225.64 / 1e5 - 1, 0.10, 0.01, "acct", None, 0.36, 0.36, 0.0, -52.0),
     ("宝くじ", "531343523", "いま", 8.0, True, False, 0.5, False, 94106.87 / 1e5 - 1, 0.10, 0.005, None, "E1", 0.9, 0.29, -(2102.1 + 235.14) / 1e5, -52.0), ("宝くじ", "531343523", "次", 8.0, True, True, 0.5, False, 0.0, 0.05, 0.005, None, "E1", 0.9, 0.9, 0.0, -52.0),
     ("FN 14074882", "14074882", "いま", 4.0, True, False, None, False, 92322.27 / 1e5 - 1, 0.08, 0.003, None, None, 0.4, 0.39, -(474.1 + 150.06) / 1e5, -76.0), ("FN 14074882", "14074882", "次", 4.0, True, False, None, False, 0.0, 0.05, 0.003, None, None, 0.4, 0.4, 0.0, -76.0)]
okA = ~np.isnan(GA["A"][2]); okE = ~np.isnan(GA["E"][2]); idx = np.arange(W)
STARTS = {"W1": [s for s in idx if MONS[s] >= PM and s + 52 <= W and okA[s]], "W2": [s for s in idx if MONS[s] < PM and s + 52 <= W and MONS[s + 51] < PM and okA[s]], "H1": [s for s in idx if okE[s] and s + 52 <= W and okE[s + 51]]}
print("開始週の数:", {k: len(v) for k, v in STARTS.items()}, flush=True); rows = []
for nm, key, stage, mm, skew, tilt, smin, trail, start, target, pad0, capm, mode, wgd, wgn, cr0, swm in B:
    items, cap, g = norm_items(key); cap = cap if capm == "acct" else None
    if mm is None: _, it0, _, _ = account_items(acct(key)); mm = sum(w for s, i, w in it0 if not i)
    fac = make_fac(items, skew, 0.5 if tilt else None); levels = list(range(len(LV))) if smin is not None else [TOP]
    MODE["k"] = mode; ML = mon_levels(items, cap, fac, mm, levels); MODE["k"] = None; ML = {li: ML[li if li in ML else TOP] for li in range(len(LV))}
    R0 = run_guard(ML[TOP]["P"], g); T0 = {tag: tuple(np.array([run_guard(ML[li]["P"], g)[tag][j] for li in range(len(LV))]) for j in range(3)) for tag in ("lo", "cl")}; d0 = np.array([pd.Timestamp(p["d"]) for p in ML[TOP]["P"]])
    r = dict(acct=nm, stage=stage, variant="参考: 金なし・従来の方法(週の無作為抽出)", cells=0)
    for wn, s_ in (("W1", d0 >= PM), ("W2", d0 < PM)):
        cols = np.arange(len(d0))[s_]; rr = [sim_eval(T0[tag], cols, start, target, 0.10, pad0, smin, trail) for tag in ("lo", "cl")]; r[f"reach_{wn}"] = round(min(x[0] for x in rr), 1); r[f"fail_{wn}"] = round(max(x[1] for x in rr), 1); r[f"weeks_{wn}"] = max((x[2] or 0) for x in rr)
    r["guard_mon_alone_pct"] = round(float(R0["lo"][1].mean()) * 100, 1); rows.append(r)
    V = [("現状(建て直しは設計どおり)", wgn, cr0, wgd, True, 0), ("金なし", 0.0, 0.0, 0.0, True, 1), ("建て直しを半分に", wgn, cr0, wgd / 2, True, 1)] + ([("建て直しをいまの大きさに", wgn, cr0, wgn, True, 1)] if abs(wgn - wgd) > 0.02 else []) + [("参考: 金を独立に足す(従来の扱い)", wgd, 0.0, wgd, False, 0)]
    for vn, w0, c0, wr, integ, cell in V:
        kw = dict(start=start, target=target, mdd=0.10, pad=pad0, smin=smin, trail=trail, g=g, swm=swm, wg0=w0, carry0=c0, wg_re=wr, integ=integ); r = dict(acct=nm, stage=stage, variant=vn, cells=cell, gold_now=w0, gold_re=wr)
        for wn in ("W1", "W2", "H1"):
            for kind in (("A", "E") if wn == "H1" else ("A",)):
                if wn == "H1" and not vn.startswith(("現状", "金なし")): continue
                o = run(ML, STARTS[wn], kind, **kw); sfx = wn if wn != "H1" else f"H1{kind}"
                r[f"reach_{sfx}"] = round(min(o[t]["reach"] for t in o), 1); r[f"fail_{sfx}"] = round(max(o[t]["fail"] for t in o), 1); r[f"weeks_{sfx}"] = max(o[t]["weeks"] for t in o)
                for k in ("fires_per52", "mon_alone", "mon_with_gold", "gold_only"): r[f"{k}_{sfx}"] = round(max(o[t][k] for t in o), 2)
                for k in ("room25", "room50", "room75"): r[f"{k}_{sfx}"] = round(o["cl"][k], 1)
                r[f"sl_{sfx}"] = o["lo"]["sl"]
        rows.append(r); print("  ", nm, stage, vn, flush=True)
pd.set_option("display.width", 340); pd.set_option("display.max_rows", 400); pd.set_option("display.max_columns", 60); pd.set_option("display.max_colwidth", 60)
D = pd.DataFrame(rows); D.to_csv("results/q253_gold_carry_eval.csv", index=False)
print("\n== (1) 評価の到達 % / 失格 % / 到達までの中央の週数(安値・終値の悪い方。W1 = 2021-08〜の開始週・W2 = 2016-11〜2020-07 の開始週) =="); print(D[["acct", "stage", "variant", "gold_now", "gold_re", "reach_W1", "fail_W1", "weeks_W1", "reach_W2", "fail_W2", "weeks_W2"]].to_string(index=False))
print("\n== (2) ガードの発動(52 週あたりの回数・評価が続いている週だけ)。mon_alone = 月曜レグだけで −g / mon_with_gold = 月曜レグは −g 未満で金の含み損が乗って届いた / gold_only = 月曜レグが損でない時の発動。room50 = 月曜の開始時点で金の含み損が余地の半分以上を使っている週 % =="); print(D[["acct", "stage", "variant", "fires_per52_W1", "mon_alone_W1", "mon_with_gold_W1", "gold_only_W1", "room25_W1", "room50_W1", "room75_W1", "fires_per52_W2", "mon_alone_W2", "mon_with_gold_W2", "gold_only_W2", "room50_W2", "sl_W1", "sl_W2", "guard_mon_alone_pct"]].to_string(index=False))
print("\n== (3) 照合: 金の 1 時間足(E)と日足の近似(A)。同じ開始週(2021-01〜2024-12) =="); print(D[D.variant.str.startswith(("現状", "金なし"))][["acct", "stage", "variant", "reach_H1A", "fail_H1A", "weeks_H1A", "fires_per52_H1A", "mon_with_gold_H1A", "gold_only_H1A", "reach_H1E", "fail_H1E", "weeks_H1E", "fires_per52_H1E", "mon_with_gold_H1E", "gold_only_H1E"]].to_string(index=False))
def ev_ok(b, v): return bool(all(v[f"reach_{w}"] >= b[f"reach_{w}"] - 1.0 and v[f"fail_{w}"] <= b[f"fail_{w}"] + 1.0 for w in ("W1", "W2")) and any(v[f"reach_{w}"] >= b[f"reach_{w}"] + 2.0 or v[f"fail_{w}"] <= b[f"fail_{w}"] - 2.0 for w in ("W1", "W2")))
print("\n== (4) 判定(基準 = 現状。Q233 の ev_ok: 両期間で到達 −1pt 以内・失格 +1pt 以内、かつどちらかの期間で到達 +2pt 以上か失格 −2pt 以下) ==")
for (nm, stage), x in D.groupby(["acct", "stage"], sort=False):
    b = x[x.variant.str.startswith("現状")].iloc[0]
    for _, v in x[x.cells == 1].iterrows(): print(f"  {nm} {stage}: {v.variant} → {'変更候補' if ev_ok(b, v) else '現行どおり'}(到達 {v.reach_W1:.0f} / {v.reach_W2:.0f}% vs {b.reach_W1:.0f} / {b.reach_W2:.0f}%・失格 {v.fail_W1:.0f} / {v.fail_W2:.0f}% vs {b.fail_W1:.0f} / {b.fail_W2:.0f}%・週 {v.weeks_W1} / {v.weeks_W2} vs {b.weeks_W1} / {b.weeks_W2})")
