# -*- coding: utf-8 -*-
"""
withdrawal_policy_mc.py — 【実験】出金・寿命ポリシー(docs/202の実装)。

問い: FN Instant 20k(目標なし・トレーリング−6%・建値ロック)で、いつ・いくら出金すると
口座の寿命と実現利益(E_value)はどう変わるか。出金後のフロア扱いはFN未回答のため
F_keep / F_reset の両仮定で走らせる。

フロア規則(docs/177 §1): floor = min(HWM − 6%×初期, 初期)。EA恒久停止 = equity ≤ floor + 1%。
⚠ docs/199/201のMCは建値ロックを実装していなかった(純粋トレーリング)。§5-1で差を記録する。
出力: results/withdrawal_policy_mc.json → docs/202 §10
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recentfit_screen as base
base.DATA = os.path.join(HERE, "data_202609")
import deployed_book as db

SEED = 7; N_MC = 10000; BLOCK = 5; HORIZON = 500
ACCT = "FN_Instant20k_11988011"; MULT = 4.0
TRAIL = 0.06; STOP_MARGIN = 0.01; GUARD = 0.04
W12_0 = pd.Timestamp("2025-09-01")
POLICIES = {"P0": None, "P1_10": (0.10, 0.00), "P2_10_5": (0.10, 0.05), "P3_5": (0.05, 0.00)}


def run(paths, policy, floor_mode, lock=True):
    """policy=(threshold, keep) or None. floor_mode: 'keep' | 'reset'. lock: 建値ロック(docs/177)"""
    n, T = paths.shape
    eq = np.ones(n); hwm = np.ones(n); ref = np.ones(n)     # ref=フロア計算の基準残高(F_resetで更新)
    alive = np.ones(n, bool); stop_day = np.full(n, HORIZON)
    withdrawn = np.zeros(n); n_wd = np.zeros(n, int)
    for t in range(T):
        if not alive.any(): break
        r = np.clip(paths[:, t] * MULT, -GUARD, None)
        eq = np.where(alive, eq * (1 + r), eq)
        hwm = np.maximum(hwm, eq)
        floor = hwm - TRAIL * ref
        if lock: floor = np.minimum(floor, ref)
        st = alive & (eq <= floor + STOP_MARGIN)
        alive &= ~st; stop_day[st] = t + 1
        if policy is not None:
            thr, keep = policy
            hit = alive & (eq >= ref * (1 + thr))
            amt = np.where(hit, eq - ref * (1 + keep), 0.0)
            withdrawn += amt; n_wd += hit
            eq = eq - amt
            if floor_mode == "reset":
                # 出金後は新残高を基準に再計算(HWM・フロアともリセット)
                ref = np.where(hit, eq, ref); hwm = np.where(hit, eq, hwm)
            # keep: HWM・ref不変=フロアそのまま。出金分だけ距離が縮む
    unreal = np.where(alive, np.maximum(eq - ref, 0.0), 0.0)
    value = withdrawn + unreal
    return dict(P_stop=round(float((~alive).mean()) * 100, 1),
                E_withdrawn=round(float(withdrawn.mean()) * 100, 2),
                E_unrealized=round(float(unreal.mean()) * 100, 2),
                E_value=round(float(value.mean()) * 100, 2),
                E_lifetime=round(float(stop_day.mean()), 0),
                E_n_withdrawals=round(float(n_wd.mean()), 2),
                P_value_positive=round(float((value > 0).mean()) * 100, 1))


def main():
    base.W_ALL1 = pd.Timestamp("2026-08-31")
    s = db.account_composite(ACCT)
    s = s[(s.index >= base.W_ALL0) & (s.index <= base.W_ALL1)]
    base.verify_window([s])
    # ⚠ Instant合成は活動日(月曜・v4シグナル日)のみを索引に持つ(12ヶ月で83本)。
    #   このまま500本を地平にすると暦で約6年になる。営業日カレンダーへ再索引し非活動日を0とする
    #   (docs/187 §6.1と同種の問題。docs/199/201のブックMCは全口座の和集合索引=ほぼ暦なので影響は限定的)。
    s = s.reindex(pd.date_range(s.index[0], s.index[-1], freq="B")).fillna(0.0)
    print(f"  営業日再索引: n={len(s)} (12ヶ月={int((s.index >= W12_0).sum())}営業日)")
    samples = {"recent_12m": s[s.index >= W12_0], "full_pessimistic": s}
    out = {"meta": dict(purpose="出金・寿命ポリシー docs/202", account=ACCT, mult=MULT, seed=SEED,
                        horizon=HORIZON, trail=TRAIL, stop_margin=STOP_MARGIN,
                        floor_rule="min(HWM-6%, 初期)・EA停止=floor+1%",
                        policies={k: v for k, v in POLICIES.items()}), "results": {}, "lock_sensitivity": {}}
    for sname, ser in samples.items():
        r = np.asarray(ser.values, float); nb = len(r) - BLOCK + 1
        rng = np.random.default_rng(SEED)
        st = rng.integers(0, nb, size=(N_MC, HORIZON // BLOCK + 1))
        paths = r[(st[:, :, None] + np.arange(BLOCK)[None, None, :])].reshape(N_MC, -1)[:, :HORIZON]
        out["results"][sname] = {}
        print(f"\n=== {sname} ===")
        print(f"{'policy':9s}{'floor':7s}{'P_stop':>8s}{'E_wd':>8s}{'E_unrl':>8s}{'E_value':>9s}{'life':>6s}{'n_wd':>6s}")
        for pname, pol in POLICIES.items():
            for fm in (("keep", "reset") if pol else ("keep",)):
                res = run(paths, pol, fm)
                out["results"][sname][f"{pname}/{fm}"] = res
                print(f"{pname:9s}{fm:7s}{res['P_stop']:8.1f}{res['E_withdrawn']:8.2f}{res['E_unrealized']:8.2f}"
                      f"{res['E_value']:9.2f}{res['E_lifetime']:6.0f}{res['E_n_withdrawals']:6.2f}")
        # §5-1: 建値ロックの有無(docs/199/201の実装との差)
        out["lock_sensitivity"][sname] = dict(with_lock=run(paths, None, "keep", lock=True),
                                              no_lock_as_docs199=run(paths, None, "keep", lock=False))
        a, b = out["lock_sensitivity"][sname]["with_lock"], out["lock_sensitivity"][sname]["no_lock_as_docs199"]
        print(f"  [§5-1] P0 停止率: 建値ロックあり={a['P_stop']}% / ロックなし(docs/199実装)={b['P_stop']}%")

    # 判定(docs/202 §7)
    verdict = {}
    for sname in samples:
        R = out["results"][sname]; p0 = R["P0/keep"]["E_value"]
        rows = {}
        for pname in POLICIES:
            if pname == "P0": continue
            k, rs = R[f"{pname}/keep"]["E_value"], R[f"{pname}/reset"]["E_value"]
            rows[pname] = dict(beats_P0_keep=bool(k > p0), beats_P0_reset=bool(rs > p0),
                               robust=bool(k > p0 and rs > p0), E_value_keep=k, E_value_reset=rs)
        rank_keep = sorted(rows, key=lambda p: -rows[p]["E_value_keep"])
        rank_reset = sorted(rows, key=lambda p: -rows[p]["E_value_reset"])
        verdict[sname] = dict(P0_E_value=p0, policies=rows, rank_keep=rank_keep, rank_reset=rank_reset,
                              ranking_depends_on_FN_answer=bool(rank_keep[0] != rank_reset[0]))
        print(f"\n[{sname}] P0 E_value={p0}  順位(keep)={rank_keep}  順位(reset)={rank_reset}  "
              f"FN回答で順位が変わる={verdict[sname]['ranking_depends_on_FN_answer']}")
    out["verdict"] = verdict
    fp = os.path.join(HERE, "results", "withdrawal_policy_mc.json")
    with open(fp, "w") as f: json.dump(out, f, ensure_ascii=False, indent=1)
    print("saved:", fp)


if __name__ == "__main__":
    main()
