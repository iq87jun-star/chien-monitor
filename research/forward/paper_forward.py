# -*- coding: utf-8 -*-
"""docs/225: 全セルの「紙上フォワード」— 日足を当日まで再取得し、選抜凍結(2026-07-29)以後の月次リターンをセル別に出す。
実口座の記録ではなく生成式の延長(執行コスト=モデル定数)。フォワード記録(docs/218/224)との差 = 執行の実態。
使い方: python3 forward/paper_forward.py [YYYY-MM ...]   既定 = 2026-08 と当月"""
import os, sys, time, glob, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
import recentfit_screen as base, deployed_book as db
FREEZE = pd.Timestamp("2026-07-29")


def refresh_live():
    base.DATA = os.path.join(ROOT, "data_live"); os.makedirs(base.DATA, exist_ok=True)
    for f in glob.glob(os.path.join(base.DATA, "*_rf.csv")):           # 当日より古いキャッシュは捨てて再取得
        if time.time() - os.path.getmtime(f) > 6 * 3600: os.remove(f)
    base.P2_EPOCH = int(time.time()); base.W_ALL0, base.W_ALL1 = pd.Timestamp("2016-01-01"), pd.Timestamp.today().normalize()


def universe():
    cells = [("Mon", s) for s in base.MON_FX + base.MON_IDX] + [("Hold", s) for s in base.HOLD_SYMS] \
          + [("TSMOM", s) for s in base.TSMOM_SYMS] + [("v4", s) for s in base.V4_PAIRS]
    for acc in db.BOOK.values():
        for f, s, _ in acc["legs"]:
            if (f, s) not in cells: cells.append((f, s))
    return cells


# docs/229 §4 事前登録の候補セル(2026-10〜2027-03 の 6 ヶ月判定)。universe() には含めない(既知セル集合を変えないため)
CANDIDATES = [("Thu", "XAUUSD", 3, False)] + [("MonExHol", s, 0, False) for s in ("EURJPY", "GBPJPY", "USDJPY", "NZDJPY", "CHFJPY")] \
    + [("MonExAUNZ", s, 0, False) for s in ("AUDJPY", "NZDJPY")] + [("MonExJpTue", s, 0, False) for s in ("USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "NZDJPY", "CADJPY", "CHFJPY")] + [("MonExGotobi", "Mon7", 0, False)]   # 2026-09-26 docs/304 Q56   # 2026-09-26 docs/303 Q53: 祝日月曜スキップ(改良系通過・紙上のみ)   # 2026-09-18 docs/249: 曜日 SHORT 候補 4 本(MonS EURGBP / FriS NZDUSD / WedS CADCHF / TueS CADCHF)はコスト符号バグの産物のため削除


def candidate_series(fam, sym, dow, short):
    if fam == "MonExHol":   # docs/303 Q53: 月曜 o2o LONG から日本の祝日月曜を除く
        sys.path.insert(0, os.path.join(ROOT, "queue")); from q_jp import is_jp_holiday
        m = base.mon_cell(sym); return m[[not is_jp_holiday(t) for t in m.index]]
    if fam in ("MonExAUNZ", "MonExJpTue", "MonExGotobi"):   # docs/304 Q56: 参加者フィルター(改良系通過・紙上のみ)
        sys.path.insert(0, os.path.join(ROOT, "queue")); from q_jp import is_jp_holiday; from q_cal import CAL, gotobi, mon7
        m = mon7() if sym == "Mon7" else base.mon_cell(sym)
        if fam == "MonExAUNZ": keep = [not ((t in CAL["AU"]) or (t in CAL["NZ"])) for t in m.index]
        elif fam == "MonExJpTue": keep = [not is_jp_holiday(t + pd.Timedelta(days=1)) for t in m.index]
        else: keep = [not gotobi(t) for t in m.index]
        return m[keep]
    df = base.load_daily(sym); c = base.IDX_COST.get(sym) or (2 * base.pip_size(sym) / df["open"])
    s = df[df["weekday"] == dow]["o2o"]; s = ((-s if short else s) - c).dropna(); return base.clip(s)   # 2026-09-18 修正(docs/249)


def main():
    months = sys.argv[1:] or ["2026-08", pd.Timestamp.today().strftime("%Y-%m")]
    refresh_live(); today = pd.Timestamp.today().normalize(); rows = []
    base.YAHOO.setdefault("EURGBP", "EURGBP=X"); base.YAHOO.setdefault("CADCHF", "CADCHF=X")
    for fam, sym, *cand in list(universe()) + [(f, s, d, sh) for f, s, d, sh in CANDIDATES]:
        try: s = candidate_series(fam, sym, *cand) if cand else db.leg_series(fam, sym)
        except Exception as e: rows.append(dict(family=fam, symbol=sym, error=str(e)[:80])); continue
        s = s[s.index < today]
        r = dict(family=fam + ("(候補)" if cand else ""), symbol=sym, data_end=str(s.index.max().date()), n_post_freeze=int((s.index > FREEZE).sum()))
        for m in months:
            q = s[s.index.to_period("M") == pd.Period(m)]
            r[f"{m}_pct"] = round(float((1 + q).prod() - 1) * 100, 3) if len(q) else np.nan; r[f"{m}_n"] = len(q)
        y = s[s.index > today - pd.DateOffset(months=12)]
        r["12m_pct"] = round(float((1 + y).prod() - 1) * 100, 2); r["12m_mean_bps"] = round(float(y.mean()) * 1e4, 2)
        rows.append(r)
    df = pd.DataFrame(rows); out = os.path.join(ROOT, "results", f"paper_forward_{months[0]}.csv"); df.to_csv(out, index=False)
    pd.set_option("display.width", 200); print(df.to_string(index=False)); print("->", out)


if __name__ == "__main__": main()
