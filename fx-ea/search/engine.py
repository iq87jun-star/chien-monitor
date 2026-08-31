#!/usr/bin/env python3
"""戦略探索エンジン — 事前固定プロトコルによる仮説検定.

設計方針(この会話で実測した失敗から逆算):
  1. 探索空間を広げるほど偽陽性が増える。累積検定数を台帳に記録し、
     必要t値をその都度引き上げる(Bonferroni)。
  2. 「見つからなかった」が正常な結果。毎朝何かを見つける仕組みにしない。
  3. IS/OOS 双方プラスとウォークフォワードを必須にする。
  4. 一度検定した仮説は台帳に残す。条件を微調整して再検定すると
     累積カウントが増え、必要t値が上がる = こっそりチェリーピックできない。
"""
import math, statistics as st, datetime as dt, json, os
from collections import defaultdict
from fetch import fetch_daily

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- universe
UNIVERSE = [
    ("USDJPY=X","USDJPY","fx"), ("EURJPY=X","EURJPY","fx"), ("GBPJPY=X","GBPJPY","fx"),
    ("AUDJPY=X","AUDJPY","fx"), ("NZDJPY=X","NZDJPY","fx"), ("CADJPY=X","CADJPY","fx"),
    ("CHFJPY=X","CHFJPY","fx"),
    ("EURUSD=X","EURUSD","fx"), ("GBPUSD=X","GBPUSD","fx"), ("AUDUSD=X","AUDUSD","fx"),
    ("NZDUSD=X","NZDUSD","fx"), ("USDCAD=X","USDCAD","fx"), ("USDCHF=X","USDCHF","fx"),
    ("EURGBP=X","EURGBP","fx"), ("EURAUD=X","EURAUD","fx"), ("GBPAUD=X","GBPAUD","fx"),
    ("^N225","JP225","idx"), ("^GSPC","US500","idx"), ("^DJI","US30","idx"),
    ("^NDX","NAS100","idx"), ("^GDAXI","GER40","idx"), ("^FTSE","UK100","idx"),
    ("^HSI","HK50","idx"), ("^AXJO","AUS200","idx"),
    ("GC=F","XAUUSD","met"), ("SI=F","XAGUSD","met"), ("PL=F","XPTUSD","met"),
    ("CL=F","USOIL","eng"), ("BZ=F","UKOIL","eng"),
    # 暗号資産。週7日取引なので営業日の概念が他と違う。
    # エキゾチック通貨(TRY/ZAR/MXN)は入れない。損益のほとんどがスワップで、
    # このエンジンはスワップを測れない(7節)。測れないものを検定しない。
    ("BTC-USD","BTCUSD","cry"), ("ETH-USD","ETHUSD","cry"),
]
SYMS = {n: (y, c) for y, n, c in UNIVERSE}
# 参照専用シンボル(建玉は作らない。局面フィルタの条件としてのみ使う)
REFS = {"VIX": "^VIX", "US10Y": "^TNX",
        "US3M": "^IRX", "US5Y": "^FVX", "US30Y": "^TYX",   # 金利の期間構造
        "SKEW": "^SKEW", "VVIX": "^VVIX",                   # オプション市場
        "COPPER": "HG=F"}                                   # 景気の代理
# 往復コスト(名目比%)。スプレッド+スリッページ+1泊分の金利/スワップの保守値。
COST = {"fx": 0.020, "idx": 0.030, "met": 0.050, "eng": 0.060, "cry": 0.100}
# 1泊追加保有あたりの上乗せコスト
CARRY = {"fx": 0.004, "idx": 0.015, "met": 0.015, "eng": 0.018, "cry": 0.030}

_CACHE = {}
def rows_of(name):
    if name not in _CACHE:
        ysym = SYMS[name][0] if name in SYMS else REFS[name]
        _CACHE[name] = fetch_daily(ysym)
    return _CACHE[name]

# ---------------------------------------------------------------- protocol
MIN_TRADES = 100          # これ未満は「検証不能」として棄却
WF_START_YEAR = 2016      # ウォークフォワードの開始年

def tstat(xs):
    n = len(xs)
    if n < 5: return 0.0
    s = st.pstdev(xs)
    return 0.0 if s == 0 else st.mean(xs) / (s / math.sqrt(n))

def pf(xs):
    g = sum(x for x in xs if x > 0); l = abs(sum(x for x in xs if x < 0))
    return g / l if l else 99.0

def required_t(cumulative_tests):
    """累積検定数に対する必要t値。片側 alpha=0.05 の Bonferroni 近似。"""
    if cumulative_tests < 1: cumulative_tests = 1
    p = 0.05 / cumulative_tests
    # 正規分布の上側 p 点(Acklam 近似で十分)
    import statistics
    return statistics.NormalDist().inv_cdf(1 - p)

def evaluate(series, cum_tests, hold=1, benchmark=None):
    """series を事前固定プロトコルで判定.

    hold      : 保有営業日数。日次シグナルで hold>1 だと建玉が重なり、
                取引が独立でなくなって t 値が過大になる。t/sqrt(hold) で補正する。
    benchmark : 同じ銘柄・同じ保有日数で「常に買い持ち」した場合のリターン列。
                これを上回らない戦略は、エッジではなく単なる方向性エクスポージャー。
    """
    if len(series) < MIN_TRADES:
        return {"verdict": "検証不能", "reason": f"取引数 {len(series)} < {MIN_TRADES}",
                "n": len(series)}
    s = sorted(series)
    xs = [r for _, r in s]
    cut = int(len(xs) * 0.6)
    is_m, oos_m = st.mean(xs[:cut]), st.mean(xs[cut:])
    t_raw = tstat(xs)
    t_adj = t_raw / math.sqrt(max(1, hold))

    by = defaultdict(list)
    for d, r in s: by[d[:4]].append(r)
    neg_years = sum(1 for y in by if st.mean(by[y]) < 0)

    wf = []
    years = sorted(by)
    for i, y in enumerate(years):
        if int(y) < WF_START_YEAR: continue
        hist = [r for yy in years[:i] for r in by[yy]]
        if len(hist) >= 30 and st.mean(hist) > 0:
            wf += by[y]

    # 診断値: 同じ日に相関の高い複数銘柄を建てても、独立な観測は1日につき1つ。
    # t/√hold は保有の重複しか補正しないため、多銘柄合成では t が過大に出る。
    # 判定基準ではない(5基準は変更していない)が、必ず記録して見えるようにする。
    per_date = defaultdict(list)
    for d, r in s: per_date[d].append(r)
    dvals = [st.mean(v) for _, v in sorted(per_date.items())]
    t_date = tstat(dvals) / math.sqrt(max(1, hold))

    bm = st.mean(benchmark) if benchmark else None
    mean = st.mean(xs)

    need_t = required_t(cum_tests)
    reasons = []
    if t_adj < need_t:
        reasons.append(f"補正t={t_adj:.2f}(生t={t_raw:.2f}/√{hold}) < 必要{need_t:.2f}"
                       f"(累積{cum_tests}検定)")
    if is_m <= 0:  reasons.append(f"IS平均 {is_m*100:.2f}bp <= 0")
    if oos_m <= 0: reasons.append(f"OOS平均 {oos_m*100:.2f}bp <= 0")
    if wf and st.mean(wf) <= 0: reasons.append(f"WF平均 {st.mean(wf)*100:.2f}bp <= 0")
    if bm is not None and mean <= bm:
        reasons.append(f"常時買い持ち {bm*100:.2f}bp を上回らない({mean*100:.2f}bp)")

    return {
        "verdict": "通過" if not reasons else "棄却",
        "reason": " / ".join(reasons) if reasons else "全基準を満たす",
        "n": len(xs), "t": round(t_raw, 3), "t_adj": round(t_adj, 3),
        "need_t": round(need_t, 3), "hold": hold,
        "n_dates": len(dvals), "t_date": round(t_date, 3),
        "mean_bp": round(mean * 100, 3),
        "bench_bp": round(bm * 100, 3) if bm is not None else None,
        "excess_bp": round((mean - bm) * 100, 3) if bm is not None else None,
        "is_bp": round(is_m * 100, 3), "oos_bp": round(oos_m * 100, 3),
        "wf_bp": round(st.mean(wf) * 100, 3) if wf else None,
        "wf_n": len(wf),
        "pf": round(pf(xs), 3),
        "wr": round(100 * sum(1 for x in xs if x > 0) / len(xs), 1),
        "neg_years": neg_years, "years": len(by),
        "first": s[0][0], "last": s[-1][0],
    }


# ------------------------------------------------- 指標プロトコル v1(事前固定)
# 売買の族は「翌日の方向」を当てにいく。指標の族は当てにいかない。
# 商品が主張するのは「変動幅や局面を素朴な想定より正確に示す」ことなので、
# 素朴な基準に対する改善そのものを検定する。
#
#   1. 最低観測数 100
#   2. 補正t(改善のt / √hold)が累積検定数のBonferroni閾値以上
#   3. IS(前半60%)/OOS(後半40%)の双方で改善プラス
#   4. 改善が正の年が全年の 80% 以上(局面依存でないこと)
#   5. 実用水準 — 平均改善 ÷ 平均素朴基準が 5% 以上
#
# 「常時買い持ちを上回る」に相当する対照は、素朴基準として改善の定義に
# 織り込み済み。累積検定数は売買トラックと共有する(見た回数は同じ台帳で数える)。
MIN_YEAR_HIT = 0.80
MIN_GAIN_RATIO = 0.05


def evaluate_forecast(series, cum_tests, hold=1):
    """series: [(日付, 改善, 素朴基準の大きさ)] を指標プロトコル v1 で判定。"""
    if len(series) < MIN_TRADES:
        return {"verdict": "検証不能", "reason": f"観測数 {len(series)} < {MIN_TRADES}",
                "n": len(series)}
    s = sorted(series)
    gains = [g for _, g, _ in s]
    bases = [b for _, _, b in s]
    cut = int(len(gains) * 0.6)
    is_m, oos_m = st.mean(gains[:cut]), st.mean(gains[cut:])
    t_raw = tstat(gains)
    t_adj = t_raw / math.sqrt(max(1, hold))

    by = defaultdict(list)
    for d, g, _ in s: by[d[:4]].append(g)
    hit_years = sum(1 for y in by if st.mean(by[y]) > 0)
    hit_ratio = hit_years / len(by)

    per_date = defaultdict(list)
    for d, g, _ in s: per_date[d].append(g)
    dvals = [st.mean(v) for _, v in sorted(per_date.items())]
    t_date = tstat(dvals) / math.sqrt(max(1, hold))

    mean_g, mean_b = st.mean(gains), st.mean(bases)
    ratio = mean_g / mean_b if mean_b else 0.0
    need_t = required_t(cum_tests)

    reasons = []
    if t_adj < need_t:
        reasons.append(f"補正t={t_adj:.2f}(生t={t_raw:.2f}/√{hold}) < 必要{need_t:.2f}"
                       f"(累積{cum_tests}検定)")
    if is_m <= 0:  reasons.append(f"IS改善 {is_m:.3f} <= 0")
    if oos_m <= 0: reasons.append(f"OOS改善 {oos_m:.3f} <= 0")
    if hit_ratio < MIN_YEAR_HIT:
        reasons.append(f"改善年 {hit_years}/{len(by)} = {hit_ratio:.0%} < {MIN_YEAR_HIT:.0%}")
    if ratio < MIN_GAIN_RATIO:
        reasons.append(f"改善率 {ratio:.1%} < {MIN_GAIN_RATIO:.0%}(実用水準に届かない)")

    return {
        "verdict": "通過" if not reasons else "棄却",
        "reason": " / ".join(reasons) if reasons else "全基準を満たす",
        "n": len(gains), "t": round(t_raw, 3), "t_adj": round(t_adj, 3),
        "need_t": round(need_t, 3), "hold": hold,
        "n_dates": len(dvals), "t_date": round(t_date, 3),
        "gain": round(mean_g, 4), "base": round(mean_b, 4),
        "gain_ratio": round(ratio, 4),
        "is_gain": round(is_m, 4), "oos_gain": round(oos_m, 4),
        "hit_years": hit_years, "years": len(by),
        "first": s[0][0], "last": s[-1][0],
    }


def resample_weekly(rows):
    """日足を週足にまとめる。始値=週初の始値・高安=週内の高安・終値=週末の終値。

    日中足は取れないが、上位足なら日足から作れる。
    「日足でしか測っていない」という制約を、上側には少しだけ動かせる。
    """
    out, cur = [], None
    for r in rows:
        y, w, _ = dt.date.fromisoformat(r[0]).isocalendar()
        key = (y, w)
        if cur is None or cur[0] != key:
            if cur is not None: out.append(cur[1])
            cur = (key, [r[0], r[1], r[2], r[3], r[4], r[5] if len(r) > 5 else 0])
        else:
            b = cur[1]
            b[2] = max(b[2], r[2]); b[3] = min(b[3], r[3]); b[4] = r[4]
            if len(r) > 5: b[5] += r[5]
    if cur is not None: out.append(cur[1])
    # 最後の週は途中までしかない(今週分)。値幅が小さく出るので落とす。
    return out[:-1] if out else out


def build_forecast(family, params):
    """指標トラックの族を組み立てる。symbols を渡すと全銘柄で回して合成する。

    tf="W" を渡すと日足を週足にまとめてから検定する。
    """
    p = dict(params)
    tf = p.pop("tf", "D")
    fn = _F.FORECAST[family]
    syms = p.pop("symbols", None) or [p.pop("sym")]
    out = []
    for sym in syms:
        rows = rows_of(sym)
        if tf == "W": rows = resample_weekly(rows)
        out += fn(rows, **p)
    return out


def benchmark_series(symbols, hold):
    """同じ銘柄・同じ保有日数の「常に買い持ち」ベースライン。"""
    import families as _FF
    out = []
    for sym in symbols:
        rows = rows_of(sym)
        c = _cost(SYMS[sym][1], hold)
        sig = [(i, 1) for i in range(len(rows) - hold - 1)]
        out += [r for _, r in _FF.execute(rows, sig, hold, c)]
    return out


# ---------------------------------------------------------------- families
def _cost(cls, hold):
    return COST[cls] + CARRY[cls] * max(0, hold - 1)

def fam_dow(sym, dow, direction, hold=1):
    """曜日 open-to-open。dow=0..4、hold=保有営業日数。"""
    rows = rows_of(sym); cls = SYMS[sym][1]; c = _cost(cls, hold)
    out = []
    for i in range(len(rows) - hold):
        if dt.date.fromisoformat(rows[i][0]).weekday() != dow: continue
        o0, o1 = rows[i][1], rows[i + hold][1]
        out.append((rows[i][0], ((o1 / o0 - 1) * 100) * direction - c))
    return out

def fam_zrev(sym, win, thr, hold, direction):
    """z-score 逆張り: 終値が平均から thr SD 離れたら翌日始値で direction 方向。"""
    rows = rows_of(sym); cls = SYMS[sym][1]; c = _cost(cls, hold)
    cl = [r[4] for r in rows]; op = [r[1] for r in rows]
    out = []
    for i in range(win + 1, len(rows) - hold):
        w = cl[i - win:i]
        m = st.mean(w); sd = st.pstdev(w)
        if sd <= 0: continue
        z = (cl[i] - m) / sd
        hit = (z <= -thr) if direction > 0 else (z >= thr)
        if not hit: continue
        out.append((rows[i][0], ((op[i + hold] / op[i + 1] - 1) * 100) * direction - c))
    return out

def fam_mom(sym, look, hold, direction):
    """モメンタム: 直近 look 日の騰落が direction 方向なら翌日始値で追随。"""
    rows = rows_of(sym); cls = SYMS[sym][1]; c = _cost(cls, hold)
    cl = [r[4] for r in rows]; op = [r[1] for r in rows]
    out = []
    for i in range(look + 1, len(rows) - hold):
        chg = cl[i] / cl[i - look] - 1
        if (chg <= 0) if direction > 0 else (chg >= 0): continue
        out.append((rows[i][0], ((op[i + hold] / op[i + 1] - 1) * 100) * direction - c))
    return out

def fam_tom(sym, before, after, direction):
    """月末効果: 月末 before 営業日前の寄り → 翌月 after 営業日目の寄り。"""
    rows = rows_of(sym); cls = SYMS[sym][1]
    idx = defaultdict(list)
    for i, r in enumerate(rows): idx[r[0][:7]].append(i)
    keys = sorted(idx); out = []
    for k in range(len(keys) - 1):
        cur, nxt = idx[keys[k]], idx[keys[k + 1]]
        if len(cur) < before or len(nxt) < after: continue
        i0, i1 = cur[-before], nxt[after - 1]
        c = _cost(cls, i1 - i0)
        out.append((rows[i0][0], ((rows[i1][1] / rows[i0][1] - 1) * 100) * direction - c))
    return out

FAMILIES = {"dow": fam_dow, "zrev": fam_zrev, "mom": fam_mom, "tom": fam_tom}

import families as _F


def build(family, params):
    """3系統に振り分ける。
      - 旧族(dow/zrev/mom/tom): sym を直接受ける
      - 指標・構造族: rows と cost を受ける(families.SINGLE)
      - 複数銘柄族(xsect/pairs): 専用シグネチャ
    params に symbols(リスト)があれば全銘柄で回して合成する。
    """
    p = dict(params)

    if family == "xsect":
        syms = p.pop("symbols")
        data = {s: rows_of(s) for s in syms}
        return _F.f_xsect(data, lambda n, h: _cost(SYMS[n][1], h), **p)

    if family == "pairs":
        a, b = p.pop("a"), p.pop("b")
        hold = p.get("hold", 5)
        # 2脚それぞれのクラスで、保有日数分のキャリーを含めた往復コストを引く。
        return _F.f_pairs(rows_of(a), rows_of(b),
                          _cost(SYMS[a][1], hold), _cost(SYMS[b][1], hold), **p)

    if family == "ccystr":
        syms = p.pop("symbols")
        data = {s: rows_of(s) for s in syms}
        return _F.f_ccystr(data, lambda n, h: _cost(SYMS[n][1], h), **p)

    if family == "breadth":
        basket = {s: rows_of(s) for s in p.pop("basket")}
        syms = p.pop("symbols")
        hold = p.get("hold", 1)
        out = []
        for t in syms:
            out += _F.f_breadth(rows_of(t), basket, _cost(SYMS[t][1], hold), **p)
        return out

    if family == "lead":
        src = p.pop("src")
        syms = p.pop("symbols")
        hold = p.get("hold", 1)
        out = []
        for t in syms:
            out += _F.f_lead(rows_of(src), rows_of(t), _cost(SYMS[t][1], hold), **p)
        return out

    if family == "xspread":
        # 2つの参照系列の関係(比または差)で局面を判定する。
        # xfilter が単一系列の水準を見るのに対し、こちらは系列間の関係を見る。
        a, b = p.pop("a"), p.pop("b")
        syms = p.pop("symbols")
        hold = p.get("hold", 1)
        out = []
        for t in syms:
            out += _F.f_xspread(rows_of(t), rows_of(a), rows_of(b),
                                _cost(SYMS[t][1], hold), **p)
        return out

    if family == "xfilter":
        ref = p.pop("ref")
        syms = p.pop("symbols")
        hold = p.get("hold", 1)
        out = []
        for t in syms:
            out += _F.f_xfilter(rows_of(t), rows_of(ref), _cost(SYMS[t][1], hold), **p)
        return out

    if family in FAMILIES:
        fn = FAMILIES[family]
        syms = p.pop("symbols", None)
        if syms is None:
            return fn(**p)
        out = []
        for s in syms:
            out += fn(sym=s, **p)
        return out

    if family in _F.SINGLE:
        fn = _F.SINGLE[family]
        syms = p.pop("symbols", None)
        if syms is None:
            syms = [p.pop("sym")]
        hold = p.get("hold", 1)
        out = []
        for s in syms:
            out += fn(rows_of(s), _cost(SYMS[s][1], hold), **p)
        return out

    raise KeyError(f"unknown family: {family}")

# ---------------------------------------------------------------- ledger
LEDGER = os.path.join(HERE, "ledger.json")

def load_ledger():
    if os.path.exists(LEDGER):
        return json.load(open(LEDGER))
    return {"cumulative_tests": 0, "entries": []}

def save_ledger(led):
    json.dump(led, open(LEDGER, "w"), ensure_ascii=False, indent=1)
