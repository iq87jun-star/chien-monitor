# -*- coding: utf-8 -*-
"""docs/212: 口座別 逸脱検知(n日分位 / 同窓バックテスト差 / CUSUM)。
使い方: python3 forward/deviation_monitor.py [xlsx のディレクトリ]  (既定: ~/.claude/uploads 配下を探索)"""
import os, sys, glob, json, time, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import recentfit_screen as base, deployed_book as db, mt5_report as mr

ACCT = {  # 口座番号 → (BOOK キー, 初期残高(口座通貨), 現構成開始日, 備考)
    "11988011": ("FN_Instant20k_11988011", 20_000, "2026-08-13", ""),
    "531343523": ("FTMO100k_531343523", 100_000, "2026-08-01", ""),
    "6071612": ("Fintokei_Pearl500", 5_000_000, "2026-07-29", ""),
    "531407058": ("FTMO50k_531407058", 50_000, "2026-08-01", ""),
    "521100397": ("FTMO50k_521100397", 50_000, "2026-08-01", "8月は旧5.52x構成(参考値)"),
    "14166201": ("FN100k_14166201", 100_000, "2026-08-10", ""),
    "6078225": ("Fintokei_Sokkou2000_6078225", 20_000_000, "2026-08-17", ""),
}
K, ARL0, SEED = 0.5, 250, 7


def latest_reports(d):
    out = {}
    for p in glob.glob(os.path.join(d, "**", "*ReportHistory*.xlsx"), recursive=True):
        a = "".join(ch for ch in os.path.basename(p).split("ReportHistory")[-1] if ch.isdigit())
        if a in ACCT and (a not in out or os.path.getmtime(p) > os.path.getmtime(out[a])): out[a] = p
    return out


def realized_daily(path, initial, start):
    _, pos, *_ = mr.parse(path)
    pos = pos.dropna(subset=["close_time"]); pos = pos[pos.close_time >= pd.Timestamp(start)]
    if pos.empty: return pd.Series(dtype=float)
    s = pos.groupby(pos.close_time.dt.normalize())["net"].sum() / initial * 100
    idx = pd.bdate_range(s.index.min(), s.index.max())
    return s.reindex(idx).fillna(0.0)


def backtest_live(key):
    base.DATA = os.path.join(ROOT, "data_live"); os.makedirs(base.DATA, exist_ok=True)
    base.P2_EPOCH = int(time.time()); base.W_ALL0, base.W_ALL1 = pd.Timestamp("2016-01-01"), pd.Timestamp.today().normalize()
    s = db.account_composite(key) * db.BOOK[key]["mult"] * 100
    return s[s.index < pd.Timestamp.today().normalize()]          # 当日の未完バーを除く


def rolling_pct(bt, n, R):
    c = (1 + bt / 100).rolling(n).apply(np.prod, raw=True).dropna() * 100 - 100
    return float((c <= R).mean()), len(c)


def calibrate_h(bt, rng, n_paths=400, T=2000):
    z = (bt / bt.std()).values; blocks = [z[i:i + 5] for i in range(0, len(z) - 5)]
    def arl(h):
        runs = []
        for _ in range(n_paths):
            path = np.concatenate([blocks[i] for i in rng.integers(0, len(blocks), T // 5 + 1)])[:T]
            S = 0.0; hit = T
            for t, zt in enumerate(path):
                S = max(0.0, S - zt - K)
                if S >= h: hit = t + 1; break
            runs.append(hit)
        return float(np.mean(runs))
    for h in (2, 3, 4, 5, 6, 7, 8):
        if arl(h) >= ARL0: return h
    return 8


def cusum(real, sigma):
    z = (real / sigma).values; Sd = Su = 0.0; md = mu = 0.0
    for zt in z:
        Sd = max(0.0, Sd - zt - K); Su = max(0.0, Su + zt - K); md, mu = max(md, Sd), max(mu, Su)
    return Sd, Su, md, mu


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/.claude/uploads")
    reps = latest_reports(d); rng = np.random.default_rng(SEED); out = {}
    print(f"レポート {len(reps)} 口座: {sorted(reps)}")
    for a, path in sorted(reps.items()):
        key, init, start, note = ACCT[a]
        real = realized_daily(path, init, start)
        if real.empty: print(f"{a}: 現構成開始以降の決済なし"); continue
        bt = backtest_live(key); sig = float(bt.std()); n = len(real); R = float(((1 + real / 100).prod() - 1) * 100)
        p_full, m_full = rolling_pct(bt, n, R); p_12, m_12 = rolling_pct(bt[bt.index >= bt.index[-1] - pd.Timedelta(days=365)], n, R)
        # 同窓バックテスト(0 / +1 営業日シフトの近い方)
        cands = []
        for sh in (0, 1):
            w = bt[(bt.index >= real.index[0] - pd.Timedelta(days=sh)) & (bt.index <= real.index[-1] - pd.Timedelta(days=sh))]
            cands.append(float(((1 + w / 100).prod() - 1) * 100))
        B = min(cands, key=lambda b: abs(b - R)); gap = R - B; gap_lim = 2 * sig * np.sqrt(n)
        h = calibrate_h(bt, rng); Sd, Su, md, mu = cusum(real, sig)
        flags = []
        if min(p_full, p_12) < 0.05: flags.append("警戒(n日分位<5%)")
        if abs(gap) > gap_lim: flags.append("実装乖離")
        if md >= h: flags.append("逸脱アラーム(CUSUM下方)")
        if mu >= h: flags.append("上方CUSUM(良すぎ)")
        out[a] = dict(key=key, note=note, start=start, first=str(real.index[0].date()), last=str(real.index[-1].date()), n=n,
                      R_pct=round(R, 2), B_same_window_pct=round(B, 2), gap_pct=round(gap, 2), gap_limit_pct=round(gap_lim, 2),
                      pct_full=round(p_full, 3), pct_12m=round(p_12, 3), sigma_bt_daily=round(sig, 3),
                      cusum_h=h, cusum_down=round(Sd, 2), cusum_up=round(Su, 2), cusum_down_max=round(md, 2), cusum_up_max=round(mu, 2),
                      flags=flags or ["なし"])
        print(f"{a} {key:28s} n={n:2d} R={R:+6.2f}% B同窓={B:+6.2f}% 差={gap:+5.2f}(限界±{gap_lim:.2f}) 分位 全={p_full:.2f} 12m={p_12:.2f} "
              f"CUSUM 下={Sd:.2f}/上={Su:.2f} (h={h}) → {' / '.join(flags) or 'なし'} {note}")
    json.dump(out, open(os.path.join(ROOT, "results", f"deviation_monitor_{pd.Timestamp.today():%Y%m%d}.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
