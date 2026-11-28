# -*- coding: utf-8 -*-
"""docs/244 Q276(2026-11-24 登録「登録実行」・セル 6): FX の逆張り(v4・9 ペア)を月曜の枠に並べる形を、口座の到達・失格で確かめる。
口座モデルは Q253・Q271 と同じ(q253 の episode を文字列の置き換えで拡張・q253 のファイルは変更しない)。Q271 の 4 か所(開始時の最高値・開始月の発動回数・これからの暦・月内の停止は 3 回目)に、逆張りの経路を足す。
逆張りの入れ方: v4 の取引の台帳(Yahoo 日足・Q274 と同じデータ)から、日ごとの 値洗い損益 VC・その日の最悪 VL・前日から持ち越した含み損益 VF を作る。
  日次ガードの判定に「VW × (VF + その日の最悪)」を、その日の全時間に一定で足す(月曜の枠の最悪と同時と置く = 保守的)。終値側の判定は VC を使う。
  発動した日は逆張りも全決済(その日の損益は判定時点の値)・翌日からは前日の終値で建て直した扱い(持ち越しの含み損益を CF で数え直す)。月内の停止中は建てない。開始時は建玉なし。
口座(いまの状態から): FTMO 50k 531407058 / 宝くじ 531343523 / 1-Step 531466484。型: 1 取引あたりの名目 = 円クロスの倍率 × 0.125 / × 0.25。判定 = Q233 の ev_ok(基準 = 現状・逆張りなし)。
照合: 重み 0 で 1-Step が Q271(現状 92.9 / 7.1・30.6 / 55.1、金なし 61.2 / 15.x・29 / 53)と一致。台帳の合計 = v4_monthly の合計。
使い方: cd research && PYTHONPATH=queue python3 -W ignore queue/q276_v4_reversal_account_model.py <累積セル数>   出力: results/q276_v4_reversal_account.csv"""
import os, sys
_ARGV = list(sys.argv)
HERE = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(HERE, "q253_gold_hold_carry_vs_daily_guard.py"), encoding="utf-8").read().split("# ---------- 口座 ----------")[0]
def _rep(s, old, new): assert s.count(old) == 1, old; return s.replace(old, new)
_src = _rep(_src, "hwm = max(c, 0.0); e = None", "hwm = max(c, 0.0, HWM0); e = None")
_src = _rep(_src, "mkey = None; mf = 0; fresh = True", "mkey = MKEY(s, s, 0); mf = MF0; fresh = True; vres = 5 * s - 1")
_src = _rep(_src, "if MK[w, i] != mkey: mkey = MK[w, i]; mf = 0", "if MKEY(w, s, i) != mkey: mkey = MKEY(w, s, i); mf = 0")
_src = _rep(_src, "halted = mf >= 2; a = 24 * i", "halted = mf >= HALT_AT; a = 24 * i\n            did = 5 * w + i; vfc = 0.0; vday = 0.0; vclose = 0.0\n            if VW > 0 and halted: vres = did\n            if VW > 0 and not halted:\n                jj = did - vres; vfc = VW * (VF[did] - (CF[vres, jj] if (vres >= 0 and 1 <= jj < CFN) else 0.0)); vday = vfc + VW * (VL[did] if tag == \"lo\" else VC[did]); vclose = VW * VC[did]")
_src = _rep(_src, "real = 0.0; mon_closed = False;", "real = 0.0; vwk = 0.0; mon_closed = False;")
_src = _rep(_src, "metric = mm + ((fl + today) if integ else 0.0); hit", "metric = mm + ((fl + today) if integ else 0.0) + vday; hit")
_src = _rep(_src, "            if len(hit):\n                k = h0 + int(hit[0]); adj", "            vwk += (vday - vfc) if len(hit) else vclose\n            if len(hit) and VW > 0: vres = did; st[\"vfire\"] = st.get(\"vfire\", 0) + (1 if float((metric - vday)[h0 + int(hit[0])]) > -g else 0)\n            if len(hit):\n                k = h0 + int(hit[0]); adj")
_src = _rep(_src, "x = mon_val + (fend - f0 + real); st[\"weeks\"] += 1", "x = mon_val + (fend - f0 + real) + vwk; st[\"weeks\"] += 1")
_src = _rep(_src, "room75=float((rm >= 0.75).mean()) * 100, sl=st[\"sl\"])", "room75=float((rm >= 0.75).mean()) * 100, sl=st[\"sl\"], vfire=st.get(\"vfire\", 0) / n * 52)")
n5 = {"__name__": "q253_head", "__file__": os.path.join(HERE, "q253_gold_hold_carry_vs_daily_guard.py"), "HWM0": 0.0, "MF0": 0, "HALT_AT": 3, "VW": 0.0, "CFN": 16}
n5["MKEY"] = lambda w, s, i: n5["MK"][w, i]
exec(compile(_src, "q253_head", "exec"), n5)
np, pd = n5["np"], n5["pd"]; norm_items, account_items, acct, make_fac, MODE, PM, LV, TOP, MONS, W, mon_levels, run, GA = (n5[k] for k in ("norm_items", "account_items", "acct", "make_fac", "MODE", "PM", "LV", "TOP", "MONS", "W", "mon_levels", "run", "GA"))
T0 = pd.Timestamp("2026-11-23"); MKF = np.array([[(T0 + pd.Timedelta(days=7 * j + i)).year * 100 + (T0 + pd.Timedelta(days=7 * j + i)).month for i in range(5)] for j in range(53)])
def setup(hwm0, mf0):
    n5["HWM0"] = hwm0; n5["MF0"] = mf0; n5["HALT_AT"] = 3; n5["MKEY"] = lambda w, s, i: MKF[w - s, i]
# ---------- 逆張りの台帳(元の v4_monthly と同じ規則) ----------
import q274_seasonal_r4_rebuild as q4
pv = q4.pv
def v4_ledger():
    T = []
    for p in pv.V4_PAIRS:
        df = pv.load_daily(p); o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values; idx = [pd.Timestamp(x).tz_localize(None) if getattr(x, "tzinfo", None) else pd.Timestamp(x) for x in df.index]; n = len(c)
        rsi = pv.rsi_wilder(c, 14); atr = pv.atr_daily(h, l, c, 14); bb = 20; cost = 2 * pv.pip_size(p); i = bb + 2
        while i < n - 1:
            win = c[i - bb:i]; mean = win.mean(); sd = win.std(ddof=1); z = (c[i] - mean) / sd if sd > 0 else 0.0; down = 0
            for k in range(12):
                if i - k - 1 >= 0 and c[i - k] < c[i - k - 1]: down += 1
                else: break
            up = 0
            for k in range(12):
                if i - k - 1 >= 0 and c[i - k] > c[i - k - 1]: up += 1
                else: break
            ret = (c[i] - c[i - 1]) / c[i - 1] if c[i - 1] else 0.0
            buy = int(rsi[i] < 35) + int(z < -1.5) + int(down >= 3) + int(ret < -0.005); sell = int(rsi[i] > 65) + int(z > 1.5) + int(up >= 3) + int(ret > 0.005)
            sig = 1 if (buy >= 4 and buy > sell) else (-1 if (sell >= 4 and sell > buy) else 0)
            if sig == 0: i += 1; continue
            entry = o[i + 1]; sld = 1.5 * atr[i]; tpd = 1.2 * sld
            if sld <= 0: i += 1; continue
            sl = entry - sig * sld; tp = entry + sig * tpd; ex = None; j = i + 1; held = 0
            while j < n and held < 8:
                if sig > 0:
                    if l[j] <= sl: ex = sl; break
                    if h[j] >= tp: ex = tp; break
                else:
                    if h[j] >= sl: ex = sl; break
                    if l[j] <= tp: ex = tp; break
                j += 1; held += 1
            jx = min(j, n - 1)
            if ex is None: ex = c[jx]
            prev = entry; ds, pn, wo = [], [], []
            for t in range(i + 1, jx + 1):
                px = ex if t == jx else c[t]; r = sig * (px - prev) / entry; adv = max(l[t], sl) if sig > 0 else min(h[t], sl); wr = sig * (adv - prev) / entry
                if t == i + 1: r -= cost / entry; wr -= cost / entry
                ds.append(idx[t]); pn.append(r); wo.append(min(r, wr)); prev = px
            T.append(dict(pair=p, dates=ds, pnl=pn, worst=wo, ret=sig * (ex / entry - 1.0) - cost / entry, exit=idx[jx])); i = max(i + 1, j)
    return T
def v4_arrays(T):
    N = 5 * W; DID = {}
    for w, d in enumerate(MONS):
        for i in range(5): DID[pd.Timestamp(d) + pd.Timedelta(days=i)] = 5 * w + i
    VF = np.zeros(N); VC = np.zeros(N); VL = np.zeros(N); CF = np.zeros((N, n5["CFN"])); used = 0
    for t in T:
        ids = [DID.get(pd.Timestamp(x).normalize()) for x in t["dates"]]; cum = np.cumsum(t["pnl"])
        if any(x is not None for x in ids): used += 1
        for m, did in enumerate(ids):
            if did is None: continue
            VC[did] += t["pnl"][m]; VL[did] += t["worst"][m]
            if m >= 1: VF[did] += cum[m - 1]
            for k in range(m):
                if ids[k] is None: continue
                jj = did - ids[k]
                if 1 <= jj < n5["CFN"]: CF[ids[k], jj] += cum[k]
    return VF, VC, VL, CF, used
def one(ML, starts, kw, vw):
    n5["VW"] = float(vw); r = {}
    for wn in ("W1", "W2"):
        o = run(ML, starts[wn], "A", **kw); r[f"reach_{wn}"] = round(min(o[t]["reach"] for t in o), 1); r[f"fail_{wn}"] = round(max(o[t]["fail"] for t in o), 1); r[f"weeks_{wn}"] = max(o[t]["weeks"] for t in o); r[f"fires_{wn}"] = round(max(o[t]["fires_per52"] for t in o), 2); r[f"v4fires_{wn}"] = round(max(o[t]["vfire"] for t in o), 2)
    n5["VW"] = 0.0; return r
def ev_ok(b, v): return bool(all(v[f"reach_{w}"] >= b[f"reach_{w}"] - 1.0 and v[f"fail_{w}"] <= b[f"fail_{w}"] + 1.0 for w in ("W1", "W2")) and any(v[f"reach_{w}"] >= b[f"reach_{w}"] + 2.0 or v[f"fail_{w}"] <= b[f"fail_{w}"] - 2.0 for w in ("W1", "W2")))
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 6; rows = []
    T = v4_ledger(); tot = sum(t["ret"] for t in T); vm = pv.v4_monthly(); print(f"台帳: {len(T)} 取引・合計 {tot * 100:.2f}%・v4_monthly の合計 {float(vm.sum()) * 100:.2f}%(一致 {abs(tot - float(vm.sum())) < 1e-9})・日次の合計との差 {abs(sum(sum(t['pnl']) for t in T) - tot):.2e}", flush=True)
    VF, VC, VL, CF, used = v4_arrays(T); n5["VF"], n5["VC"], n5["VL"], n5["CF"] = VF, VC, VL, CF
    act = VC != 0; print(f"口座モデルの期間に入る取引 {used}・1 取引あたり名目 1 倍での日次: 平均 {VC.mean() * 1e4:.2f} bps・標準偏差 {VC.std() * 100:.3f}%・最悪日 {VC.min() * 100:.2f}%・最悪(日中)  {VL.min() * 100:.2f}%・持ち越しの含み損の最悪 {VF.min() * 100:.2f}%・建玉のある日 {act.mean() * 100:.0f}%", flush=True)
    okA = ~np.isnan(GA["A"][2]); idx = np.arange(W); STARTS = {"W1": [s for s in idx if MONS[s] >= PM and s + 52 <= W and okA[s]], "W2": [s for s in idx if MONS[s] < PM and s + 52 <= W and MONS[s + 51] < PM and okA[s]]}; print("開始週の数:", {k: len(v) for k, v in STARTS.items()}, flush=True)
    # 表示名, 口座キー, 円クロス倍率(None = 口座の設定から), SKEW, 200 日線, 縮小の下限, 追随型, 開始, 目標, 停止線の手前幅, cap, 決済の型, 金, スワップ, 開始時の最高, 今月の発動回数
    B = [("1-Step", "531466484", None, True, False, None, True, 97826.72 / 1e5 - 1, 0.10, 0.01, "acct", None, 0.36, -52.0, 102813.25 / 1e5 - 1, 2),
         ("FTMO 50k 7058", "531407058", 6.0, False, False, None, False, 52697.16 / 5e4 - 1, 0.10, 0.01, None, None, 0.0, 0.0, 0.0, 0),
         ("宝くじ", "531343523", 8.0, True, True, 0.5, False, 93147.34 / 1e5 - 1, 0.10, 0.005, None, "E1", 0.0, 0.0, 0.0, 0)]
    for nm, key, mm, skew, tilt, smin, trail, start, target, pad0, capm, mode, wg, swm, hwm0, mf0 in B:
        items, cap, g = norm_items(key); cap = cap if capm == "acct" else None
        if mm is None: _, it0, _, _ = account_items(acct(key)); mm = sum(w for s, i, w in it0 if not i)
        fac = make_fac(items, skew, 0.5 if tilt else None); levels = list(range(len(LV))) if smin is not None else [TOP]
        MODE["k"] = mode; ML = mon_levels(items, cap, fac, mm, levels); MODE["k"] = None; ML = {li: ML[li if li in ML else TOP] for li in range(len(LV))}; setup(hwm0, mf0)
        kw = dict(start=start, target=target, mdd=0.10, pad=pad0, smin=smin, trail=trail, g=g, swm=swm, wg0=wg, carry0=0.0, wg_re=wg, integ=True)
        b = one(ML, STARTS, kw, 0.0); rows.append(dict(acct=nm, variant="現状(逆張りなし)", v4_notional=0.0, cells=0, verdict="基準", mon_mult=round(mm, 2), g=g, start_pct=round(start * 100, 2), **b)); print(f"  {nm}: 円クロス {mm:.2f} 倍・g {g}・現状 {b}", flush=True)
        if nm == "1-Step":
            kz = dict(kw, wg0=0.0, wg_re=0.0); z = one(ML, STARTS, kz, 0.0); rows.append(dict(acct=nm, variant="照合: 金なし(逆張りなし)", v4_notional=0.0, cells=0, verdict="—", mon_mult=round(mm, 2), g=g, start_pct=round(start * 100, 2), **z)); print("  照合(Q271: 現状 92.9 / 7.1・30.6 / 55.1、金なし 61 / 15・29 / 53):", (b["reach_W1"], b["fail_W1"], b["reach_W2"], b["fail_W2"]), (z["reach_W1"], z["fail_W1"], z["reach_W2"], z["fail_W2"]), flush=True)
        for f in (0.125, 0.25):
            v = one(ML, STARTS, kw, mm * f); rows.append(dict(acct=nm, variant=f"逆張りを足す(円クロスの倍率 × {f})", v4_notional=round(mm * f, 3), cells=1, verdict="変更候補" if ev_ok(b, v) else "現行どおり", mon_mult=round(mm, 2), g=g, start_pct=round(start * 100, 2), **v)); print(f"  {nm} × {f}: {v}", flush=True)
    D = pd.DataFrame(rows); D.to_csv("results/q276_v4_reversal_account.csv", index=False); assert int(D.cells.sum()) == N
    pd.set_option("display.width", 320); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 44)
    print(f"\n== Q276(累積セル {cum} + {N} = {cum + N}・到達 % / 失格 %・W1 = 2021-08 以降の開始・W2 = 2016-11〜2020-07 の開始・fires = 52 週あたりのガード発動・v4fires = うち逆張りを足して初めて届いた発動) =="); print(D.to_string(index=False))
    j = D[D.cells == 1]; print(f"\n判定: 変更候補 {int((j.verdict == '変更候補').sum())} / {len(j)} 件")
