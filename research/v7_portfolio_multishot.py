"""
v7_portfolio_multishot.py — 「数を打って成績を上げる」の工学的実装と実測。

設計思想(過剰最適化ではない):
  v6エッジ=「04-10 UTC帯 × 3円クロス(EUR/GBP/USDJPY)の月曜ドリフト」は実在。
  docs/13で判明した失格原因は【エッジ不足ではなくリスク配分】: 3ペア×各0.40%同時 →
  合算DD 11.81% > 10% で Phase1 FAIL。
  そこで「本物の1エッジを細かくサンプリング」して器(FundedNext)に収める:
    (1) ショット数を増やす: 月曜 04/06/08/10 UTC の4時刻 × 3ペア = 週12ショット
        (週1→週12)。タイミング運(どの1時刻か)とペア集中を平準化し分散を下げる。
    (2) 合算リスクを予算化: 「週あたり総リスク予算」を固定し、ショット数で割って
        各ショットを小さくする。多ショットでも合算は器に収まる。
    (3) FundedNextは時間無制限 → 低リスク多ショットは「+8%到達 vs -10%失格」競争に
        単調有利。到達は遅れるが失格確率が下がる ⇒ 合格率(EV)が上がる。

本スクリプトの実測:
  A. 各(ペア×時刻)月曜ショットの実リターンを committed H1(2.8年)から構築
  B. ショット間相関を測る(多ショットの分散低減が本物か確認)
  C. 週次ポートフォリオ・リターンを「総リスク予算」配分で合成
  D. ブロック・ブートストラップでチャレンジをモンテカルロ:
       Phase1(+8%/-10%総DD/-5%日次)、Phase1→Phase2 連続、合格率・時間・DD分布
  E. 総リスク予算を sweep → 合格率を最大化する配分を提示
       併せて「週1・3ペア・各0.40%(=旧v6)」を対照に同じMCで比較

⚠ committed = 2.8年のみ。MCは限られた標本のブロック・ブートストラップで、将来を保証
   しない。10年H1での追認は colab 版(後続)で行う。数値は全て JSON 直読/marker検証。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
PAIRS = ["EURJPY", "GBPJPY", "USDJPY"]   # 主力 EUR/GBP, 補助 USD(単体は弱いが分散用)
HOURS = [4, 6, 8, 10]                    # 検証で安定の朝帯(13UTCで消滅)
PIP = 0.01
COST_PIP = 2.0
HOLD = 24
WEEKDAY = 0                              # Monday

def load(p):
    d = pd.read_csv(os.path.join(DATA, f"{p}_h1.csv"))
    d["t"] = pd.to_datetime(d["timestamp"], utc=True, errors="coerce")
    return d.dropna(subset=["t"]).sort_values("t").set_index("t")

CACHE = {p: load(p) for p in PAIRS}

def shot_returns(pair, hour):
    """その(ペア×時刻)の月曜LONG・24h・コスト後リターンを週indexで返す。"""
    df = CACHE[pair]; cv = df["close"].values; idx = df.index
    a = np.where((idx.dayofweek == WEEKDAY) & (idx.hour == hour))[0]
    a = a[a + HOLD < len(cv)]
    r = (cv[a + HOLD] - cv[a]) / cv[a] - COST_PIP * PIP / cv[a]
    s = pd.Series(r, index=idx[a])
    s.index = s.index.to_period("W")          # 週キーで揃える
    return s[~s.index.duplicated()]

def build_matrix(pairs, hours):
    """週 × (pair,hour) のリターン行列。各列=1ショット系列。"""
    cols = {}
    for p in pairs:
        for h in hours:
            cols[f"{p}_{h:02d}"] = shot_returns(p, h)
    M = pd.DataFrame(cols).sort_index()
    return M

def weekly_portfolio(M, total_weekly_lev):
    """各週、『週あたり総レバレッジ予算 total_weekly_lev』をその週のアクティブ・ショットに
       等分して建て、合算週次・口座リターンを返す。
       1ショットの口座リターン = レバレッジ L_i × そのショットの価格リターン r_i。
       (実EAでは L_i = RiskPerTrade% / 災害SL距離%。SLは広く通常未到達なので、実現損益は
        ほぼ価格リターン×レバレッジ。よって『建玉ノーション/口座 = レバレッジ』でモデル化。)
       週次口座リターン = Σ_active (total_weekly_lev / n_active) × r_i。
       ⇒ 総建玉エクスポージャを固定し、ショット数で割る = 純粋な分散効果のテスト。"""
    out = {}
    for wk, row in M.iterrows():
        rs = row.dropna()
        if len(rs) == 0: continue
        L = total_weekly_lev / len(rs)          # アクティブ・ショットで総予算を等分
        out[wk] = float((L * rs).sum())
    return pd.Series(out).sort_index()

def realized_net_pct(weekly):
    """標本期間の実現・複利ネット%(設計の妥当性アンカー)。"""
    return round(float(((1 + weekly).prod() - 1) * 100), 1)

def block_bootstrap_paths(weekly, n_paths=4000, max_weeks=520, block=4, seed=11):
    """週次ポートフォリオ・リターンを block 単位でブートストラップし equity パスを作る。
       FundedNextは時間無制限 → max_weeks(=10年)まで延ばし、+8%到達 or -10%失格を判定。"""
    rng = np.random.default_rng(seed)
    w = weekly.values
    n = len(w)
    paths = np.empty((n_paths, max_weeks), dtype=float)
    for p in range(n_paths):
        seq = []
        while len(seq) < max_weeks:
            start = rng.integers(0, n)               # 循環ブロック
            seq.extend(w[(start + k) % n] for k in range(block))
        paths[p] = seq[:max_weeks]
    return paths

def eval_challenge(paths, target=0.08, total_dd=0.10, daily_dd=0.05):
    """各パスで Phase1 を評価。週次リターンを日次に割らず『週次が最小粒度の総DD/到達』で判定。
       (週次保有・週内クローズ前提なので daily_dd は週次DDで近似的にチェック)
       戻り: pass率, 失格率, 未達率, 到達までの中央値(週), maxDD分布。"""
    n_paths, T = paths.shape
    res_pass = np.zeros(n_paths, bool)
    res_fail = np.zeros(n_paths, bool)
    weeks_to_target = np.full(n_paths, np.nan)
    maxdd = np.zeros(n_paths)
    for i in range(n_paths):
        eq = 1.0; peak = 1.0; mdd = 0.0
        for t in range(T):
            eq *= (1.0 + paths[i, t])
            # 週次DD(日次-5%は週次が-5%以内なら満たす近似。保守的に週次でチェック)
            if paths[i, t] <= -daily_dd:            # 単週で-5%超 = 日次規則抵触とみなす
                res_fail[i] = True; break
            peak = max(peak, eq)
            dd = (eq - peak) / peak
            mdd = min(mdd, dd)
            if dd <= -total_dd:                      # 総DD-10%抵触
                res_fail[i] = True; break
            if eq >= 1.0 + target:                   # +8%到達
                res_pass[i] = True; weeks_to_target[i] = t + 1; break
        maxdd[i] = mdd
    return dict(
        pass_rate=round(float(res_pass.mean()) * 100, 1),
        fail_rate=round(float(res_fail.mean()) * 100, 1),
        timeout_rate=round(float((~res_pass & ~res_fail).mean()) * 100, 1),
        median_weeks_to_target=(None if np.all(np.isnan(weeks_to_target))
                                else round(float(np.nanmedian(weeks_to_target)), 0)),
        p95_maxDD_pct=round(float(np.percentile(maxdd, 5)) * 100, 1),   # 5%tile(最悪側)
        median_maxDD_pct=round(float(np.percentile(maxdd, 50)) * 100, 1),
    )

def two_phase(weekly, n_paths=4000):
    """Phase1(+8%)通過後、続けてPhase2(+5%)を同じ過程で評価した連続合格率。"""
    paths = block_bootstrap_paths(weekly, n_paths=n_paths)
    p1 = eval_challenge(paths, target=0.08)
    # Phase2はtarget+5%、同じDD制限。p1合格者のみが進む前提で独立近似(連続=積)
    paths2 = block_bootstrap_paths(weekly, n_paths=n_paths, seed=99)
    p2 = eval_challenge(paths2, target=0.05)
    combined = round(p1["pass_rate"] * p2["pass_rate"] / 100, 1)
    return p1, p2, combined

def run():
    out = {}
    # --- A. ショット行列 & 相関 ---
    M = build_matrix(PAIRS, HOURS)
    out["matrix_shape"] = dict(weeks=int(M.shape[0]), shots=int(M.shape[1]),
                               span=f"{M.index.min()}..{M.index.max()}")
    cc = M.corr()
    iu = np.triu_indices(cc.shape[0], 1)
    out["shot_corr_mean"] = round(float(np.nanmean(cc.values[iu])), 2)
    # 時刻内(同ペア隣接時刻)vs ペア間 の相関分解
    same_pair, cross_pair = [], []
    cols = list(M.columns)
    for i in range(len(cols)):
        for j in range(i+1, len(cols)):
            v = cc.values[i, j]
            if np.isnan(v): continue
            (same_pair if cols[i][:6] == cols[j][:6] else cross_pair).append(v)
    out["corr_same_pair_diff_hour"] = round(float(np.mean(same_pair)), 2)
    out["corr_cross_pair"] = round(float(np.mean(cross_pair)), 2)

    # --- B. 単一ショット(週1・1ペア・1時刻)の生の質: 平均週次/標準偏差/シャープ ---
    def sharpe(s):
        s = s.dropna(); return round(float(s.mean()/s.std()*np.sqrt(52)), 2) if s.std()>0 else 0.0
    out["per_shot_weekly_sharpe"] = {c: sharpe(M[c]) for c in M.columns}

    # --- C. ポートフォリオ週次系列 & 年率シャープ(スケール不変=予算1.0で形を見る) ---
    # 「数を打つ」効果の核: 12ショット平均の週次シャープ vs 単一ショット平均シャープ
    port = weekly_portfolio(M, total_weekly_lev=1.0)
    out["portfolio_weekly_sharpe_12shot"] = sharpe(port)
    out["mean_single_shot_sharpe"] = round(float(np.mean(list(out["per_shot_weekly_sharpe"].values()))), 2)

    # --- D. 総レバレッジ予算 sweep でチャレンジMC(実現net%もアンカー表示) ---
    # 予算は『週あたり総建玉/口座』。実EAの各0.40%×3≒総レバ約0.7前後が出発点。広く探る。
    sweep = {}
    for lev in [0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0]:
        weekly = weekly_portfolio(M, total_weekly_lev=lev)
        paths = block_bootstrap_paths(weekly, n_paths=4000)
        sweep[f"{lev:.2f}"] = dict(**eval_challenge(paths, target=0.08),
                                   realized_net_pct=realized_net_pct(weekly))
    out["risk_sweep_phase1"] = sweep

    # 選択基準: FundedNextは時間無制限ゆえ pass率は低DDなら飽和する。よって束縛条件は
    # 『失格(DD)』。最悪側DD(p95)を -7.5% 以内(=-10%の十分内側に2.5%マージン)に
    # 保ちつつ、合格率×リターン速度が最大の予算を選ぶ = 安全な範囲で最も良い成績。
    def safe_best(sw):
        cand = [(k, v) for k, v in sw.items() if v["p95_maxDD_pct"] >= -7.5 and v["fail_rate"] <= 2.0]
        if not cand: cand = list(sw.items())
        # 合格率優先 → 同率は到達速度(短い週数)優先
        return max(cand, key=lambda kv: (kv[1]["pass_rate"], -(kv[1]["median_weeks_to_target"] or 9e9)))
    best_lev, best_stats = safe_best(sweep)
    out["chosen_total_weekly_lev"] = best_lev
    out["chosen_phase1"] = best_stats

    # --- E. 対照: 旧v6(週1相当=3ペア×08UTCのみ=3ショット)。同じ総レバ予算で公平比較。 ---
    M3 = build_matrix(PAIRS, [8])
    old_weekly = weekly_portfolio(M3, total_weekly_lev=float(best_lev))
    old_paths = block_bootstrap_paths(old_weekly, n_paths=4000)
    out["baseline_oldv6_3shot_08only"] = dict(
        **eval_challenge(old_paths, target=0.08),
        sharpe=sharpe(old_weekly), realized_net_pct=realized_net_pct(old_weekly))

    # --- 2フェーズ連続(採用予算で) ---
    weekly_best = weekly_portfolio(M, total_weekly_lev=float(best_lev))
    p1, p2, comb = two_phase(weekly_best)
    out["two_phase"] = dict(phase1=p1, phase2=p2, combined_pass_pct=comb)

    return out, M, weekly_best

if __name__ == "__main__":
    out, M, weekly_best = run()
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "v7_portfolio_multishot.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    # 単一スカラ marker で検証印字(表示破損対策)
    print("MK_weeks", out["matrix_shape"]["weeks"], "shots", out["matrix_shape"]["shots"])
    print("MK_corr_mean", out["shot_corr_mean"], "same_pair", out["corr_same_pair_diff_hour"], "cross", out["corr_cross_pair"])
    print("MK_sharpe_single", out["mean_single_shot_sharpe"], "sharpe_12shot", out["portfolio_weekly_sharpe_12shot"])
    print("MK_chosen_lev", out["chosen_total_weekly_lev"])
    c = out["chosen_phase1"]
    print("MK_chosen_pass", c["pass_rate"], "fail", c["fail_rate"], "timeout", c["timeout_rate"],
          "medwk", c["median_weeks_to_target"], "p95DD", c["p95_maxDD_pct"], "medDD", c["median_maxDD_pct"],
          "net", c["realized_net_pct"])
    print("MK_sweep:", {k: (v["pass_rate"], v["fail_rate"], v["p95_maxDD_pct"], v["realized_net_pct"])
                         for k, v in out["risk_sweep_phase1"].items()})
    b = out["baseline_oldv6_3shot_08only"]
    print("MK_baseline_pass", b["pass_rate"], "fail", b["fail_rate"], "p95DD", b["p95_maxDD_pct"],
          "sharpe", b["sharpe"], "net", b["realized_net_pct"])
    print("MK_twophase_combined", out["two_phase"]["combined_pass_pct"])
    print("saved research/results/v7_portfolio_multishot.json")
