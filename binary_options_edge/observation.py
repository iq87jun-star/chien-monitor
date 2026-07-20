"""気配観察実験の判定エンジン（THEORY.md §5-6 のキル条件を実装）。

使い方:
  1. OBSERVATION_GUIDE.md の手順でIG画面から気配を observations.csv に記録
  2. python -m binary_options_edge.observation observations.csv
  3. スナップショットごとに H2/H3 の判定（生存/棄却/判定不能）と根拠が出力される

判定はすべて「mid が拡散FVとジャンプ込みFV（または季節FV）のどちらに寄っているか」
と「乖離が半スプレッドを超えるか」で機械的に行う。恣意的な裁量は挟まない。
"""
from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from . import theory
from .pricing import prob_finish_above, prob_touch

# H3判定の閾値（THEORY.md §6 のキル条件）
H3_MAX_TRADABLE_SPREAD = 15.0   # これ超のスプレッドは「取れない」= 棄却
H3_MIN_GAP_POINTS = 5.0         # 拡散FVとジャンプFVの差がこれ未満なら銘柄選択不良
H2_CALENDAR_TOL_POINTS = 2.0    # midが季節FV±2pt以内なら「カレンダー実装済み」


@dataclass
class Snapshot:
    """IG画面から手動記録する1スナップショット。CSVの1行に対応。"""
    timestamp: datetime          # 記録時刻(JST)
    expiry: datetime             # 判定時刻(JST)
    pair: str
    spot: float
    option_type: str             # "ladder_above" | "touch"
    level: float                 # ストライク/バリア
    bid: Optional[float]         # 提示停止なら空欄
    ask: Optional[float]
    halted: bool
    hypothesis: str              # "H2" | "H3"
    sigma_ann: float             # 通常時の年率ボラ推定(例 0.10)
    jump_std_log: float          # H3: 想定ジャンプ標準偏差(対数, 例 0.002)
    sigma_trailing_ann: float    # H2: 直近トレーリング実現ボラ(年率)
    sigma_seasonal_ann: float    # H2: 季節カレンダー込みの窓ボラ(年率)
    note: str = ""

    @property
    def ttm_seconds(self) -> float:
        return max((self.expiry - self.timestamp).total_seconds(), 0.0)

    @property
    def spread(self) -> Optional[float]:
        if self.bid is None or self.ask is None:
            return None
        return self.ask - self.bid

    @property
    def mid_p(self) -> Optional[float]:
        if self.bid is None or self.ask is None:
            return None
        return 0.5 * (self.bid + self.ask) / 100.0


def _fair_prob(s: Snapshot, sigma_ann: float, jump_std_log: float = 0.0) -> float:
    """指定ボラ(+任意のジャンプ)でのフェア確率。"""
    if jump_std_log > 0:
        st_eff = theory.effective_horizon_sigma(sigma_ann, s.ttm_seconds, jump_std_log)
        sigma_ann = st_eff / theory.horizon_sigma(1.0, s.ttm_seconds)
    if s.option_type == "ladder_above":
        return prob_finish_above(s.spot, s.level, sigma_ann, s.ttm_seconds)
    if s.option_type == "touch":
        return prob_touch(s.spot, s.level, sigma_ann, s.ttm_seconds)
    raise ValueError(f"unknown option_type {s.option_type}")


@dataclass
class Verdict:
    snapshot: Snapshot
    status: str      # "生存" | "棄却" | "判定不能"
    reason: str
    detail: dict


def evaluate_h3(s: Snapshot) -> Verdict:
    """H3キル条件: 提示停止/スプレッド拡大→棄却、拡散寄りmid→生存、織り込み済み→棄却。"""
    if s.halted or s.mid_p is None:
        return Verdict(s, "棄却", "提示停止: イベント前に取引不能(README H3反証要因の実証)", {})
    p_diff = _fair_prob(s, s.sigma_ann)
    p_jump = _fair_prob(s, s.sigma_ann, s.jump_std_log)
    gap_pt = (p_jump - p_diff) * 100.0
    detail = {"p_diffusion": p_diff, "p_with_jump": p_jump,
              "mid_p": s.mid_p, "spread": s.spread, "gap_points": gap_pt}
    if s.spread > H3_MAX_TRADABLE_SPREAD:
        return Verdict(s, "棄却", f"スプレッド{s.spread:.0f}pt>{H3_MAX_TRADABLE_SPREAD:.0f}pt: "
                       "歪みがあっても半スプレッドが食う", detail)
    if abs(gap_pt) < H3_MIN_GAP_POINTS:
        return Verdict(s, "判定不能", f"拡散FVとジャンプFVの差{gap_pt:.1f}ptが小さすぎる: "
                       "よりOTMの銘柄で再記録を", detail)
    # midがジャンプ込みFVからどれだけ拡散側に離れているか(確率pt) vs 半スプレッド
    ev_edge_pt = (p_jump - s.mid_p) * 100.0
    if ev_edge_pt > (s.spread or 0.0) / 2.0:
        return Verdict(s, "生存", f"midがジャンプ込みFVより{ev_edge_pt:.1f}pt割安"
                       f"(>半スプレッド{(s.spread or 0)/2:.1f}pt): ジャンプ未織り込みの疑い", detail)
    return Verdict(s, "棄却", f"midはジャンプ込みFVと{abs(ev_edge_pt):.1f}pt差: 織り込み済み", detail)


def evaluate_h2(s: Snapshot) -> Verdict:
    """H2キル条件: mid≈季節FV→カレンダー実装済みで棄却、トレーリングFV寄り→生存。"""
    if s.halted or s.mid_p is None:
        return Verdict(s, "判定不能", "提示なし(H2は平常時間帯の検証なので記録時刻を見直す)", {})
    p_trail = _fair_prob(s, s.sigma_trailing_ann)
    p_seas = _fair_prob(s, s.sigma_seasonal_ann)
    mid_pt = s.mid_p * 100.0
    detail = {"p_trailing": p_trail, "p_seasonal": p_seas,
              "mid_p": s.mid_p, "spread": s.spread}
    dist_seas = abs(mid_pt - p_seas * 100.0)
    dist_trail = abs(mid_pt - p_trail * 100.0)
    if dist_seas <= H2_CALENDAR_TOL_POINTS:
        return Verdict(s, "棄却", f"midは季節FVと{dist_seas:.1f}pt差(±{H2_CALENDAR_TOL_POINTS:.0f}pt内): "
                       "IGは季節カレンダー実装済み", detail)
    edge_pt = abs(p_seas - s.mid_p) * 100.0
    if dist_trail < dist_seas and edge_pt > (s.spread or 0.0) / 2.0:
        return Verdict(s, "生存", f"midはトレーリングFV寄りで季節FVと{edge_pt:.1f}pt乖離"
                       f"(>半スプレッド): 境界効果が残存", detail)
    return Verdict(s, "判定不能", "どちらのFVにも決定的に寄っていない: 記録を追加", detail)


def evaluate(s: Snapshot) -> Verdict:
    return evaluate_h3(s) if s.hypothesis.upper() == "H3" else evaluate_h2(s)


# --------------------------------------------------------------------------- #
# CSV入出力
# --------------------------------------------------------------------------- #
_FIELDS = ("timestamp", "expiry", "pair", "spot", "option_type", "level",
           "bid", "ask", "halted", "hypothesis", "sigma_ann", "jump_std_log",
           "sigma_trailing_ann", "sigma_seasonal_ann", "note")


def _opt_float(v: str) -> Optional[float]:
    v = (v or "").strip()
    return float(v) if v else None


def load_csv(path: str) -> list[Snapshot]:
    out: list[Snapshot] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not (row.get("timestamp") or "").strip():
                continue
            out.append(Snapshot(
                timestamp=datetime.fromisoformat(row["timestamp"].strip()),
                expiry=datetime.fromisoformat(row["expiry"].strip()),
                pair=row["pair"].strip(),
                spot=float(row["spot"]),
                option_type=row["option_type"].strip(),
                level=float(row["level"]),
                bid=_opt_float(row.get("bid", "")),
                ask=_opt_float(row.get("ask", "")),
                halted=(row.get("halted", "").strip() in ("1", "true", "True", "yes")),
                hypothesis=row["hypothesis"].strip(),
                sigma_ann=float(row.get("sigma_ann") or 0.10),
                jump_std_log=float(row.get("jump_std_log") or 0.002),
                sigma_trailing_ann=float(row.get("sigma_trailing_ann") or 0.10),
                sigma_seasonal_ann=float(row.get("sigma_seasonal_ann") or 0.10),
                note=(row.get("note") or "").strip(),
            ))
    return out


def report(snapshots: list[Snapshot]) -> None:
    print(f"# 気配観察 判定レポート（{len(snapshots)}件）\n")
    counts: dict[tuple[str, str], int] = {}
    for s in snapshots:
        v = evaluate(s)
        counts[(s.hypothesis.upper(), v.status)] = counts.get((s.hypothesis.upper(), v.status), 0) + 1
        mid = f"mid={s.mid_p*100:.1f}" if s.mid_p is not None else "mid=--"
        spd = f"s={s.spread:.0f}pt" if s.spread is not None else "s=--"
        print(f"[{s.hypothesis}] {s.timestamp:%m-%d %H:%M} {s.pair} {s.option_type}"
              f"@{s.level} {mid} {spd}")
        print(f"  -> {v.status}: {v.reason}")
        if v.detail:
            d = v.detail
            fv = (f"拡散FV={d['p_diffusion']*100:.1f} ジャンプFV={d['p_with_jump']*100:.1f}"
                  if "p_diffusion" in d else
                  f"トレーリングFV={d['p_trailing']*100:.1f} 季節FV={d['p_seasonal']*100:.1f}")
            print(f"     {fv}")
    print("\n## 集計")
    for (hyp, status), n in sorted(counts.items()):
        print(f"  {hyp} {status}: {n}件")
    print("\n判定原則: 「生存」が複数の独立した記録で再現しない限りエッジとは結論しない。")
    print("1件の生存はデータ入力誤差・ボラ推定誤差でも出る。棄却はそのまま棄却。")


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python -m binary_options_edge.observation <observations.csv>")
        raise SystemExit(1)
    report(load_csv(sys.argv[1]))


if __name__ == "__main__":
    main()
