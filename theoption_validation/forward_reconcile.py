#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""フォワード突合レポート v1.0 (2026-10-20)
VPSプローブの記録(probe_*.jsonl)と検証時のバックテスト期待値を突き合わせる。
使い方:
  python forward_reconcile.py out/probe_*.jsonl                        # 提供状況+ペイアウト+レート標本
  python forward_reconcile.py --duka <dir> out/probe_*.jsonl           # + Dukascopy乖離 (<dir>/{PAIR}_hourly.csv)
  python forward_reconcile.py --trades entry_history.csv out/*.jsonl   # + 実取引の戦略別突合
標準ライブラリのみ(VPS/Colab/どこでも動く)。全時刻はJST表記。
"""
import argparse, csv, json, math, os, sys, collections, datetime as dt

JST = dt.timezone(dt.timedelta(hours=9))
UTC = dt.timezone.utc

# ===== 検証済みメニュー (バックテスト期待値; 補正-2pp前の生WR%) =====
# (id, pair, 曜日(None=毎日), エントリーJST時, 商品dur, 判定JST時(当日/翌日は dur で判る), 方向, 想定payout, 検証WR%)
MENU = [
    ("EURGBP_1H",   "EURGBP", None, 7, "1H",  8,  "HIGH", 1.90, 68.02),
    ("CHFJPY_1H",   "CHFJPY", None, 7, "1H",  8,  "HIGH", 1.90, 65.83),
    ("EURJPY_1H",   "EURJPY", None, 7, "1H",  8,  "HIGH", 1.90, 63.32),
    ("USDCHF_7H",   "USDCHF", None, 7, "7H",  14, "HIGH", 1.95, 59.51),
    ("CADJPY_1H_M", "CADJPY", 0,    7, "1H",  8,  "HIGH", 1.90, 69.89),
    ("GBPJPY_1H_M", "GBPJPY", 0,    7, "1H",  8,  "HIGH", 1.90, 69.52),
    ("AUDJPY_1H_M", "AUDJPY", 0,    7, "1H",  8,  "HIGH", 1.90, 68.03),
    ("NZDJPY_1H_M", "NZDJPY", 0,    7, "1H",  8,  "HIGH", 1.90, 66.85),
    ("GBPUSD_1H_M", "GBPUSD", 0,    7, "1H",  8,  "HIGH", 1.90, 65.99),
    ("AUDJPY_23H_M","AUDJPY", 0,    11, "23H", 10, "HIGH", 1.95, 61.04),
    ("EURGBP_N",    "EURGBP", None, 23, "7H",  6,  "LOW",  1.95, 55.77),   # 月火水金・2/3/6/12月停止
    ("EURAUD_20H",  "EURAUD", None, 10, "20H", 6,  "LOW",  1.95, 55.27),
]
CORR_PP = 2.0

def wilson(w, n, z=1.96):
    if n == 0: return (0.0, 0.0)
    p = w / n; d = 1 + z*z/n; c = p + z*z/(2*n)
    m = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n))
    return ((c-m)/d*100, (c+m)/d*100)

def jx(s):
    """ISO文字列→JST datetime"""
    try: return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(JST)
    except Exception: return None

def cjson(s):
    try: return json.loads(s) if isinstance(s, str) else (s or None)
    except ValueError: return None

def load_probe(paths):
    """全フレームから 契約情報 / 判定価格標本 / エラー を抽出"""
    contracts = {}   # (date, name+stamp) -> dict(契約欄 + first_seen)
    rates = []       # dict(key, name, t_jst, rate, strike, payout, cutoff, expiry)
    errors = []
    for p in paths:
        for line in open(p, encoding="utf-8"):
            try: r = json.loads(line)
            except ValueError: continue
            fr = r.get("frame"); t = r.get("recv_utc", "")
            if not isinstance(fr, dict): continue
            if fr.get("type") in ("error", "fail", "rejected") or fr.get("errors"):
                errors.append((t, json.dumps(fr, ensure_ascii=False)[:200])); continue
            if fr.get("type") != "update": continue
            v = fr.get("values") or {}
            c = cjson(v.get("contract"))
            if fr.get("stream") == "contract_data" and c:
                a = cjson(v.get("asset")) or {}
                st = (cjson(v.get("barrier_strikes")) or [{}])[0].get("strike")
                rates.append(dict(key=fr.get("key", ""), name=c.get("name", ""),
                                  t=jx(a.get("timestamp") or v.get("timestamp")),
                                  rate=float(a["rate"]) if a.get("rate") else None,
                                  strike=float(st) if st else None,
                                  payout=float(c.get("payout_multiplier") or 0),
                                  cutoff=jx(c.get("cutoff_time")), expiry=jx(c.get("expiration_time")),
                                  status=c.get("status")))
                continue
            if c:   # contracts ストリーム
                exp_t = jx(c.get("expiration_time")); seen = jx(t)
                k = (fr.get("key", ""),)
                if k not in contracts:
                    contracts[k] = dict(name=c.get("name", ""), status=c.get("status"),
                                        payout=float(c.get("payout_multiplier") or 0),
                                        open=jx(c.get("open_time")), cutoff=jx(c.get("cutoff_time")),
                                        expiry=exp_t, exp_type=c.get("expiration_type"), first_seen=seen)
    return contracts, rates, errors

def parse_name(name):
    s = [x.strip() for x in str(name).split("|")]
    return dict(asset=s[0] if s else "", exp=s[1] if len(s) > 1 else "",
                dur=s[2] if len(s) > 2 else "", product=s[3] if len(s) > 3 else "",
                sel=s[4] if len(s) > 4 else "")

def sec1_availability(contracts):
    print("=" * 78)
    print("(1) 商品の提供状況 (契約ストリームより・初出JST)")
    rows = collections.defaultdict(list)
    for c in contracts.values():
        d = parse_name(c["name"])
        if d["product"] != "HIGHLOW": continue
        rows[(d["asset"], d["exp"], d["dur"])].append(c)
    for (asset, exp, dur), cs in sorted(rows.items()):
        pays = sorted({c["payout"] for c in cs})
        fs = min(c["first_seen"] for c in cs if c["first_seen"])
        exps = sorted({c["expiry"].strftime("%H:%M") for c in cs if c["expiry"]})[:6]
        print(f"  {asset:7} {exp}|{dur:4} 初出 {fs:%m/%d %H:%M} 倍率{pays} 判定時刻(JST){exps}")

def sec2_payout(contracts):
    print("=" * 78)
    print("(2) ペイアウト実測 vs メニュー想定")
    obs = collections.defaultdict(set)
    for c in contracts.values():
        d = parse_name(c["name"])
        obs[(d["asset"], d["dur"])].add(c["payout"])
    for mid, pair, wd, eh, dur, jh, sel, pay, bwr in MENU:
        got = obs.get((pair, dur))
        if not got:
            print(f"  {mid:13} {pair} {dur:4}: 記録なし(この時間帯のプローブ未実行)")
            continue
        mark = "OK" if pay in got else ("低倍率!" if max(got) < pay else "要確認")
        print(f"  {mid:13} {pair} {dur:4}: 想定{pay} 実測{sorted(got)} → {mark}")

def sec3_duka(rates, duka_dir):
    print("=" * 78)
    print("(3) 業者レート vs Dukascopy終値 (実効摩擦の推定)")
    if not duka_dir:
        print("  --duka 未指定のためスキップ (判定レート標本:", len([r for r in rates if r['rate']]), "件)")
        return
    cache = {}
    diffs = collections.defaultdict(list)
    for r in rates:
        if not (r["rate"] and r["t"]): continue
        pair = parse_name(r["name"])["asset"]
        f = os.path.join(duka_dir, f"{pair}_hourly.csv")
        if not os.path.exists(f): continue
        if pair not in cache:
            cache[pair] = {}
            with open(f, encoding="utf-8-sig") as fh:
                for row in csv.DictReader(fh):
                    k = dt.datetime.fromisoformat(row["datetime"].split("+")[0])
                    cache[pair][k.replace(tzinfo=UTC).astimezone(JST).strftime("%Y%m%d%H")] = float(row["Close"] if "Close" in row else row["close"])
        hb = (r["t"] - dt.timedelta(hours=1)).strftime("%Y%m%d%H")   # 直前に閉じた1時間足
        if hb in cache[pair]:
            diffs[pair].append((r["rate"] - cache[pair][hb]) / cache[pair][hb] * 1e4)  # bp
    if not diffs:
        print("  重複期間なし: Dukascopy CSVが記録期間をカバーしていない(要データ更新)。レート標本は保存済み")
        return
    for pair, d in sorted(diffs.items()):
        d.sort(); n = len(d)
        print(f"  {pair}: n={n} 乖離中央値 {d[n//2]:+.1f}bp 平均 {sum(d)/n:+.1f}bp (業者レート-Duka直前足終値)")

def sec4_pseudo_forward(contracts, rates):
    print("=" * 78)
    print("(4) 疑似フォワード: メニュー該当契約のエントリー時刻レート vs ストライク (記録範囲内)")
    # 各メニュー契約について、エントリーJST時の最初のレートとexpiry直前の最後のレートで勝敗を出す
    by_key = collections.defaultdict(list)
    for r in rates:
        if r["rate"] and r["t"]: by_key[r["key"]].append(r)
    results = collections.defaultdict(lambda: [0, 0])  # mid -> [win, n]
    for key, rs in by_key.items():
        d = parse_name(rs[0]["name"])
        exp_t = rs[0]["expiry"]
        if not exp_t: continue
        for mid, pair, wd, eh, dur, jh, sel, pay, bwr in MENU:
            if d["asset"] != pair or d["dur"] != dur or d["sel"] != sel: continue
            if exp_t.hour != jh: continue
            if wd is not None and exp_t.weekday() != (wd if jh > eh else (wd + 1) % 7): continue
            rs.sort(key=lambda x: x["t"])
            entry = next((x for x in rs if x["t"].hour == eh), None)
            final = rs[-1] if (exp_t - rs[-1]["t"]).total_seconds() < 300 else None
            if not (entry and final and entry["strike"]): continue
            win = (final["rate"] > entry["strike"]) if sel == "HIGH" else (final["rate"] < entry["strike"])
            results[mid][1] += 1; results[mid][0] += int(win)
    if not any(n for _, n in results.values()):
        print("  完結した契約の記録なし(チェック実行のみ/本番窓の記録待ち)。月曜フル実行後に有効化")
    for mid, (w, n) in sorted(results.items()):
        lo, hi = wilson(w, n)
        print(f"  {mid}: {w}勝{n-w}敗 (WR {w/n*100:.1f}%, 95%CI {lo:.1f}-{hi:.1f})")

def sec5_trades(trades_csv):
    print("=" * 78)
    print("(5) 実取引の突合 (entry_history.csv)")
    if not trades_csv or not os.path.exists(trades_csv):
        print("  取引ログ未指定。テンプレート: date,strategy_id,pair,direction,payout_actual,stake,result(WIN/LOSE/DRAW),pnl,note")
        return
    agg = collections.defaultdict(lambda: dict(w=0, n=0, pnl=0.0, pay=[]))
    with open(trades_csv, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            a = agg[row["strategy_id"]]
            if row["result"] == "DRAW": continue
            a["n"] += 1; a["w"] += int(row["result"] == "WIN")
            a["pnl"] += float(row.get("pnl") or 0)
            if row.get("payout_actual"): a["pay"].append(float(row["payout_actual"]))
    bmap = {m[0]: m for m in MENU}
    alerts = []
    for sid, a in sorted(agg.items()):
        wr = a["w"]/a["n"]*100 if a["n"] else 0
        lo, hi = wilson(a["w"], a["n"])
        line = f"  {sid:13} {a['w']}勝{a['n']-a['w']}敗 WR{wr:5.1f}% CI[{lo:.1f},{hi:.1f}] 損益{a['pnl']:+,.0f}円"
        if sid in bmap:
            bwr = bmap[sid][8]
            be = 100/ (sum(a["pay"])/len(a["pay"]) if a["pay"] else bmap[sid][7])
            line += f" | 検証WR{bwr:.1f}%"
            if hi < bwr - CORR_PP: line += " ⚠検証値を有意に下回る"; alerts.append(sid)
            if hi < be: line += " ⚠BE割れ"; alerts.append(sid)
        print(line)
    if alerts: print("  → 要注意:", ", ".join(sorted(set(alerts))), "(3ヶ月連続マイナスで停止ルールを適用)")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl", nargs="+")
    ap.add_argument("--duka", default=None, help="Dukascopy {PAIR}_hourly.csv のディレクトリ")
    ap.add_argument("--trades", default=None, help="実取引ログCSV")
    a = ap.parse_args()
    contracts, rates, errors = load_probe(a.jsonl)
    print(f"フォワード突合レポート  入力{len(a.jsonl)}ファイル  契約{len(contracts)}件  レート標本{len(rates)}件  エラー{len(errors)}件")
    sec1_availability(contracts)
    sec2_payout(contracts)
    sec3_duka(rates, a.duka)
    sec4_pseudo_forward(contracts, rates)
    sec5_trades(a.trades)
    if errors:
        print("=" * 78); print("(6) エラー先頭5件:")
        for t, e in errors[:5]: print("  ", t[:19], e)

if __name__ == "__main__":
    main()
