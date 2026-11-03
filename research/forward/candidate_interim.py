# -*- coding: utf-8 -*-
"""docs/322 Q107(工学・セル 0): 紙上フォワード候補セル(paper_forward.CANDIDATES)の中間判定を毎月自動集計する。
判定規則は docs/229 §4 のまま変えない: 2026-10〜2027-03 の 6 か月で「+月 ≥ 4/6 かつ 累積 > 0 → LEAD、それ未満は棄却」。
  ・日足系候補: results/paper_forward_<YYYY-MM>.csv の「(候補)」行をそのまま読む(再計算しない = 月初の定例と同じ数字)。
  ・時間足系候補(MonIdxIntra / MonJpyIntra6J / MonIdxSession0 / MonJpySession6J / RollGateB2): 本体 H1(data_dukascopy・2026-08 末まで)に
    Dukascopy の月次 H1(forward/q20_monitor_data/<SYM>_<YYYY-MM>_bid.csv・無ければ取得)を継ぎ足し、paper_forward.candidate_series で再計算。
  ・HoldSL10 BTCUSD: q90 を import すると base.DATA が凍結フォルダ(data_202609)に固定される(docs/395 §2 の不具合)ため、ここで data_live に戻して再計算。
出力: results/candidate_interim_latest.csv(候補 × 月)と標準出力の表。paper_forward.py の末尾からも呼ばれる(毎月 1 日の定例)。
使い方: cd research && python3 forward/candidate_interim.py [--no-fetch]   (--no-fetch は Dukascopy へ行かず手元の月次ファイルだけ使う)"""
import os, sys, time, datetime as dt, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT)
for p in (ROOT, HERE, os.path.join(ROOT, "tools"), os.path.join(ROOT, "queue")):
    if p not in sys.path: sys.path.insert(0, p)
import recentfit_screen as base, paper_forward as pf, q_common
WINDOW = pd.period_range("2026-10", "2027-03", freq="M"); NEED_PLUS = 4
HOURLY = {"MonIdxIntra", "MonJpyIntra6J", "MonIdxSession0", "MonJpySession6J", "RollGateB2"}; RECOMPUTE_DAILY = {"HoldSL10"}
DK_CODE = {"UK100": "GBRIDXGBP", "WTI": "LIGHTCMDUSD", "GER40": "DEUIDXEUR", "JP225": "JPNIDXJPY", "NAS100": "USATECHIDXUSD", "US500": "USA500IDXUSD", "US30": "USA30IDXUSD"}
MDATA = os.path.join(ROOT, "forward", "q20_monitor_data"); os.makedirs(MDATA, exist_ok=True)
BASE_OF = {"MonExHol": "Mon", "MonExJpTue": "Mon", "MonExAUNZ": "Mon", "HoldSL10": "Hold", "MonIdxIntra": "Mon", "MonJpyIntra6J": "Mon", "MonIdxSession0": "Mon", "MonJpySession6J": "Mon"}
FETCH_BUDGET_S = 900


def last_completed_month(today=None):
    t = pd.Timestamp(today or pd.Timestamp.today()).to_period("M"); return t - 1


def month_file(sym, per):   # Dukascopy 月次 H1(bid)。q20_monitor.month_df と同じ置き場・同じ形式
    return os.path.join(MDATA, f"{sym}_{per.year}-{per.month:02d}_bid.csv")


def ensure_months(syms, periods, fetch=True, t0=None):
    import dukascopy_fetch as dk
    t0 = t0 or time.time(); missing = []
    for sym in syms:
        for per in periods:
            f = month_file(sym, per)
            if os.path.exists(f): continue
            if not fetch or time.time() - t0 > FETCH_BUDGET_S: missing.append((sym, str(per))); continue
            code = DK_CODE.get(sym, sym)
            st, data = dk.fetch(f"https://datafeed.dukascopy.com/datafeed/{code}/{per.year}/{per.month - 1:02d}/BID_candles_hour_1.bi5"); time.sleep(dk.GAP)
            if st != 200 or not data: missing.append((sym, str(per))); print(f"  [H1 取得不可] {sym} {per} (http {st})", flush=True); continue
            rows = dk.decode(data, code, per.year, per.month)
            pd.DataFrame(rows, columns=["t", "open", "high", "low", "close", "volume"]).set_index("t").to_csv(f); print(f"  [H1 取得] {sym} {per} {len(rows)} 本", flush=True)
    return missing


def ext_load(sym):
    """本体 H1 + 月次ファイル(ある分だけ)。q_common.load と同じ列・同じ休場フィルター。"""
    df = q_common.load(sym); parts = [df]
    for f in sorted(os.listdir(MDATA)):
        if f.startswith(sym + "_") and f.endswith("_bid.csv"):
            d = pd.read_csv(os.path.join(MDATA, f), parse_dates=["t"]).set_index("t"); d = d[(d.high > d.low) | (d.volume > 0)]; parts.append(d[d.index > df.index.max()])
    out = pd.concat(parts).sort_index(); return out[~out.index.duplicated(keep="last")]


def patch_hourly_loaders():
    import q_session, q114_mon_index_intraday, q147_roll_rate_diff_gate
    for mod in (q_common, q_session, q114_mon_index_intraday, q147_roll_rate_diff_gate): mod.load = ext_load
    q_common.END = pd.Timestamp("2099-12-31")


def monthly_pct(s, periods):
    out = {}
    for per in periods:
        q = s[s.index.to_period("M") == per]; out[str(per)] = (round(float((1 + q).prod() - 1) * 100, 3) if len(q) else np.nan, len(q))
    return out


def daily_rows_from_csv(periods):
    """paper_forward_<月>.csv の候補行と、その基準セル(Mon / Hold 同銘柄)の月次 % を読む。"""
    cand, basev = {}, {}
    for per in periods:
        f = os.path.join(ROOT, "results", f"paper_forward_{per}.csv")
        if not os.path.exists(f): continue
        d = pd.read_csv(f); col, ncol = f"{per}_pct", f"{per}_n"
        if col not in d.columns: continue
        for r in d.itertuples():
            fam = str(r.family); v = getattr(r, col.replace("-", "_")) if hasattr(r, col.replace("-", "_")) else None
            v = d.loc[r.Index, col]; n = int(d.loc[r.Index, ncol]) if not pd.isna(d.loc[r.Index, ncol]) else 0
            if fam.endswith("(候補)"): cand.setdefault((fam[:-4], r.symbol), {})[str(per)] = (None if pd.isna(v) else float(v), n)
            else: basev[(fam, r.symbol, str(per))] = None if pd.isna(v) else float(v)
    return cand, basev


def recompute(periods, fetch=True):
    """時間足系 5 族 + HoldSL10 を再計算して {(fam,sym): {月: (pct, n)}} を返す。"""
    t0 = time.time(); out = {}; hourly = [(f, s, d, sh) for f, s, d, sh in pf.CANDIDATES if f in HOURLY]
    syms = set()
    for f, s, _, _ in hourly:
        if f == "RollGateB2":
            from q147_roll_rate_diff_gate import PAIRS; syms |= set(PAIRS)
        else: syms.add(s)
    need = [p for p in pd.period_range("2026-09", periods[-1], freq="M")]   # 本体 H1 は 2026-08 末まで
    missing = ensure_months(sorted(syms), need, fetch=fetch, t0=t0)
    patch_hourly_loaders(); today = pd.Timestamp.today().normalize()
    for f, s, d, sh in hourly:
        try: ser = pf.candidate_series(f, s, d, sh); ser = ser[ser.index < today]; out[(f, s)] = monthly_pct(ser, periods); out[(f, s)]["data_end"] = str(ser.index.max().date())
        except Exception as e: out[(f, s)] = {"error": str(e)[:80]}
    # HoldSL10(日足): q90 の import が base.DATA を凍結フォルダに固定するので live に戻す
    pf.refresh_live(); live = base.DATA
    try:
        from q90_hold_disaster_sl import hold_sl; base.DATA = live
        ser = hold_sl("BTCUSD", 10.0)[0]; ser = ser[ser.index < today]; out[("HoldSL10", "BTCUSD")] = monthly_pct(ser, periods); out[("HoldSL10", "BTCUSD")]["data_end"] = str(ser.index.max().date())
    except Exception as e: out[("HoldSL10", "BTCUSD")] = {"error": str(e)[:80]}
    base.DATA = live
    return out, missing


def verdict(vals, elapsed):
    """vals: 月 → pct(None=データなし)。elapsed: 判定窓のうち経過した完了月数。docs/229 §4 の規則で中間状態を返す。"""
    done = [v for v in vals if v is not None]; plus = sum(1 for v in done if v > 0); cum = float(np.prod([1 + v / 100 for v in done]) - 1) * 100 if done else np.nan
    remaining = len(WINDOW) - elapsed
    if elapsed >= len(WINDOW): state = "LEAD" if (plus >= NEED_PLUS and cum > 0) else "棄却"
    elif plus + remaining < NEED_PLUS: state = "棄却確定"
    else: state = f"継続(あと {max(0, NEED_PLUS - plus)} 勝・残 {remaining} 月)"
    return plus, len(done), cum, state


def main(fetch=True, today=None, quiet=False):
    lcm = last_completed_month(today); periods = [p for p in WINDOW if p <= lcm]; elapsed = len(periods)
    cand, basev = daily_rows_from_csv(periods)
    rec, missing = recompute(periods, fetch=fetch) if periods else ({}, [])
    rows = []
    for fam, sym, d, sh in pf.CANDIDATES:
        key = (fam, sym); src = "再計算" if key in rec else "CSV"
        vals = {}; ns = {}; note = ""
        if key in rec:
            if "error" in rec[key]: note = "error: " + rec[key]["error"]
            for per in periods: v, n = rec[key].get(str(per), (np.nan, 0)); vals[str(per)] = None if pd.isna(v) else v; ns[str(per)] = n
        else:
            for per in periods: v, n = cand.get(key, {}).get(str(per), (None, 0)); vals[str(per)] = v; ns[str(per)] = n
        plus, done, cum, state = verdict(list(vals.values()), elapsed)
        bf = BASE_OF.get(fam); diffs = []
        for per in periods:
            b = basev.get((bf, sym, str(per))) if bf else None
            diffs.append(None if (b is None or vals[str(per)] is None) else round(vals[str(per)] - b, 3))
        r = dict(family=fam, symbol=sym, source=src, months_elapsed=elapsed, months_with_data=done, plus_months=plus, cum_pct=None if pd.isna(cum) else round(cum, 3), state=state,
                 base=(f"{bf} {sym}" if bf else ""), note=note)
        for per in periods: r[f"{per}_pct"] = vals[str(per)]; r[f"{per}_n"] = ns[str(per)]; r[f"{per}_vs_base"] = diffs[periods.index(per)]
        rows.append(r)
    df = pd.DataFrame(rows); out = os.path.join(ROOT, "results", "candidate_interim_latest.csv"); df.to_csv(out, index=False)
    if not quiet:
        print(f"\n== 候補セルの中間判定(docs/229 §4: 2026-10〜2027-03・+月 ≥ {NEED_PLUS}/6 かつ 累積 > 0 → LEAD)・経過 {elapsed}/6 か月(〜{lcm})")
        cols = ["family", "symbol", "source"] + [f"{p}_pct" for p in periods] + ["plus_months", "cum_pct", "state", "base"] + [f"{p}_vs_base" for p in periods]
        pd.set_option("display.width", 250); print(df[cols].to_string(index=False))
        if missing: print("  未取得の月次 H1:", missing)
        print("->", out)
    return df


if __name__ == "__main__":
    main(fetch="--no-fetch" not in sys.argv)
