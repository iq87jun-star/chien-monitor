# -*- coding: utf-8 -*-
"""docs/322 Q104(診断・セル 0): 祝日スキップの実口座パリティ。
(1) EA の除外日リスト(InpJpHolidayMondays = 日本の祝日月曜 + 翌火曜が祝日の月曜、InpAuNzHolidayMondays = 豪 NSW・NZ の祝日月曜)を
    jpholiday / holidays パッケージから作った期待集合(2026-09-28〜2027-12-31 の月曜)と突き合わせる(欠け・余り)。
(2) 配備以降の各月曜について exec_schedule の予定(除外日は予定 0)と実口座 positions/open_positions の建て本数を照合し、
    「除外日に建てた」「除外日でないのに建てなかった」を列挙する。当日分は ea_log_extract の [Mon SKIP] 行数も添える。
使い方: cd research && python3 queue/q104_holiday_skip_parity.py [開始月曜 2026-09-28] [終了月曜 今日]
出力: results/q104_holiday_skip_parity.csv(月曜 × 口座 × 銘柄)。配備・manifest は変更しない。毎月 1 日のダイジェスト後にも同じコマンドで再確認できる。"""
import os, sys, re, glob, datetime as dt, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT); sys.path.insert(0, os.path.join(ROOT, "forward"))
import exec_schedule as es
import jpholiday, holidays
start = pd.Timestamp(sys.argv[1]) if len(sys.argv) > 1 else pd.Timestamp("2026-09-28")
end = pd.Timestamp(sys.argv[2]) if len(sys.argv) > 2 else pd.Timestamp(dt.datetime.utcnow().date())
end = end - pd.Timedelta(days=end.dayofweek)   # 直近の月曜
rules = es.account_rules()
# ---- (1) カレンダー照合 ----
def jp(x): x = x.date() if hasattr(x, "date") else x; return bool(jpholiday.is_holiday(x)) or (x.month == 1 and x.day <= 3) or (x.month == 12 and x.day == 31)
mons = pd.date_range("2026-09-28", "2027-12-31", freq="7D")
exp_jp = {m for m in mons if jp(m) or jp(m + pd.Timedelta(days=1))}
au = holidays.country_holidays("AU", subdiv="NSW", years=[2026, 2027]); nz = holidays.country_holidays("NZ", years=[2026, 2027])
exp_aunz = {m for m in mons if m.date() in au or m.date() in nz}
print("== (1) 除外日リスト vs カレンダー(2026-09-28〜2027-12-31 の月曜)")
cal_ok = True
for acct, r in sorted(rules.items()):
    if not r["mon_fx"]: continue
    mj, ej = sorted(exp_jp - r["jp"]), sorted(r["jp"] - exp_jp); ma, ea = sorted(exp_aunz - r["aunz"]), sorted(r["aunz"] - exp_aunz)
    has_aud = any(s.startswith(("AUD", "NZD")) for s in r["mon_fx"])
    status = "一致" if not (mj or ej or (has_aud and (ma or ea))) else "不一致"
    if status != "一致": cal_ok = False
    print(f"  {acct}: JP {len(r['jp'])} 日 (欠け {[d.date().isoformat() for d in mj]} 余り {[d.date().isoformat() for d in ej]}) | 豪NZ {len(r['aunz'])} 日 {'(AUD/NZD レッグあり)' if has_aud else '(AUD/NZD なし)'} (欠け {[d.date().isoformat() for d in ma]} 余り {[d.date().isoformat() for d in ea]}) → {status}")
print("  期待 JP:", [d.date().isoformat() for d in sorted(exp_jp)]); print("  期待 豪NZ:", [d.date().isoformat() for d in sorted(exp_aunz)])
# ---- (2) 実口座パリティ ----
skip_log = {}
for p in glob.glob("ops_inbox/*/ea_log_extract.csv"):
    acct = os.path.basename(os.path.dirname(p))
    for line in open(p, encoding="utf-8-sig", errors="replace"):
        m = re.search(r"Logs/(\d{8})\.log.*\[Mon SKIP\] ([A-Za-z0-9.]+)", line)
        if m: d = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}"; k = (acct, es.norm_sym(m.group(2)), d); skip_log[k] = skip_log.get(k, 0) + 1
rows = []
for mon in pd.date_range(start, end, freq="7D"):
    res = es.check_week(mon)
    for r in res["rows"]:
        if r["fam"] != "Mon" or r["sym"] in es.IDX or pd.Timestamp(r["date"]) != mon: continue
        ru = rules[r["account"]]; is_jp = mon in ru["jp"] and "JPY" in r["sym"]; is_aunz = mon in ru["aunz"] and r["sym"].startswith(("AUD", "NZD"))
        kind = "JP祝日" if is_jp else ("豪NZ祝日" if is_aunz else "")
        if is_jp and not jp(mon): kind = "翌火曜JP祝日"
        sk = skip_log.get((r["account"], r["sym"], mon.date().isoformat()), 0)
        if r["n_expected"] == 0: verdict = "OK(建てず)" if r["n_actual"] == 0 else "違反(除外日に建てた)"
        else: verdict = "OK" if r["n_actual"] >= r["n_expected"] else ("照合時点で建玉中/未決済" if mon == end else "建て損ね")
        rows.append(dict(monday=mon.date().isoformat(), account=r["account"], sym=r["sym"], holiday=kind, n_expected=r["n_expected"], n_actual=r["n_actual"], skip_log=sk, recorded=r["recorded"], verdict=verdict))
df = pd.DataFrame(rows); os.makedirs("results", exist_ok=True); df.to_csv("results/q104_holiday_skip_parity.csv", index=False)
print("\n== (2) 除外日の実口座パリティ")
hol = df[df.holiday != ""]
for (mon, kind), g in hol.groupby(["monday", "holiday"]):
    bad = g[g.verdict.str.startswith("違反")]
    print(f"  {mon} {kind}: 口座×銘柄 {len(g)} 件 建て 0 = {int((g.n_actual == 0).sum())} 件 / SKIP ログ {int(g.skip_log.sum())} 行 → {'パリティ OK' if not len(bad) else '違反 ' + ', '.join(f'{b.account} {b.sym} {b.n_actual} 本' for b in bad.itertuples())}")
non = df[(df.holiday == "") & df.recorded]
miss = non[non.verdict == "建て損ね"]
print(f"\n== 参考: 除外日以外の月曜 {non.monday.nunique()} 週 × {len(non)} 件: 建て損ね {len(miss)} 件" + ("" if not len(miss) else " → " + "; ".join(f"{m.monday} {m.account} {m.sym} 予定 {m.n_expected} 実 {m.n_actual}" for m in miss.itertuples())))
print("\n判定:", "カレンダー一致・除外日の違反なし" if cal_ok and not len(hol[hol.verdict.str.startswith('違反')]) else "要確認")
