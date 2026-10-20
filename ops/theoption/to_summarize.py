# -*- coding: utf-8 -*-
"""to_probe.py の記録(JSONL)の要約。python to_summarize.py out\\probe_demo_YYYYMMDD_HHMM.jsonl [...]
出すもの: (1) 期間・商品の組み合わせごとの初出時刻(JST)、(2) FD|1H|HIGHLOW の通貨ペア別初出と払い戻し関連の欄、
(3) 契約 JSON に含まれる欄名の一覧(払い戻し倍率がどの欄か探すため)、(4) contract_data への応答の例、(5) エラー。"""
import json, sys, datetime as dt, collections
from to_probe import parse_name, contract_json, is_target
JST = dt.timezone(dt.timedelta(hours=9))
PAYKEYS = ("payout", "return", "profit", "multiplier", "rate", "percent", "odds")

def jst(s):
    try: return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(JST).strftime("%m/%d %H:%M:%S")
    except Exception: return s

def report(*paths):
    combo, target, fields, paysamp, data_resp, errors, subs = {}, {}, collections.Counter(), {}, [], [], {}
    for p in paths:
        for line in open(p, encoding="utf-8"):
            try: r = json.loads(line)
            except ValueError: continue
            k, fr, t = r.get("kind"), r.get("frame"), r.get("recv_utc", "")
            if k in ("health", "balance"): print(f"[{k}] {jst(t)} {json.dumps(fr, ensure_ascii=False)[:200]}"); continue
            if k in ("error", "raw"): errors.append((t, str(fr)[:200])); continue
            if not isinstance(fr, dict): continue
            ty = fr.get("type")
            if ty == "subscribed": subs[fr.get("reqId")] = fr.get("sid")
            if ty in ("error", "fail", "rejected") or fr.get("errors"): errors.append((t, json.dumps(fr, ensure_ascii=False)[:300]))
            if ty != "update": continue
            c = contract_json(fr.get("values"))
            if c is None:   # contracts 以外(contract_data など)
                if len(data_resp) < 5: data_resp.append((t, json.dumps(fr, ensure_ascii=False)[:400]))
                continue
            fields.update(c.keys()); name = c.get("name") or fr.get("key", ""); d = parse_name(name)
            if c.get("status", "Opened") != "Opened": continue
            ck = (d["exp"], d["dur"], d["product"]); combo.setdefault(ck, t)
            if is_target(name):
                target.setdefault(name, t)
                pv = {kk: vv for kk, vv in c.items() if any(w in kk.lower() for w in PAYKEYS)}
                if pv and name not in paysamp: paysamp[name] = (t, pv)
    print("\n(1) 組み合わせ(満期種別・期間・商品)の初出 JST")
    for ck, t in sorted(combo.items(), key=lambda x: x[1]): print(f"  {jst(t)}  {'|'.join(ck)}")
    print("\n(2) FD|1H|HIGHLOW の初出 JST(月曜の開場は 夏 06:00 / 冬 07:00。開場 +20 分以内に出るかが要点)")
    if not target: print("  (無し)")
    for n, t in sorted(target.items(), key=lambda x: x[1]): print(f"  {jst(t)}  {n}  払い戻し関連: {paysamp.get(n, ('', '-'))[1]}")
    print("\n(3) 契約 JSON の欄名:", ", ".join(f"{k}({v})" for k, v in fields.most_common()))
    print("\n(4) contract_data 等の応答例:"); [print(" ", jst(t), s) for t, s in data_resp] or print("  (無し)")
    print("\n(5) エラー・切断:"); [print(" ", jst(t), s) for t, s in errors[:20]] or print("  (無し)")
    return dict(combo=combo, target=target, fields=fields, paysamp=paysamp, errors=errors)

if __name__ == "__main__":
    if len(sys.argv) < 2: print(__doc__); sys.exit(2)
    report(*sys.argv[1:])
