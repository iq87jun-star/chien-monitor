# -*- coding: utf-8 -*-
"""オフライン検証(python3 ops/vps/test_chien_deploy.py): docs/328 §9m の 3 点 — 切り詰められた name でも装着済みと判定する・重複装着を 1 枚に減らす・restart_token で 1 回だけ再起動する。"""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chien_deploy as D

EA = "【FTMO100k_口座531343523_宝くじ】EA10L_Mon4_10.0倍+GER40ブレイク_6.0倍+HoldXAU0.9_v1.05"
def chart(symbol, experts):
    s = f"<chart>\r\nid=1\r\nsymbol={symbol}\r\nperiod_type=1\r\nperiod_size=1\r\n"
    for name, path in experts:
        s += f"<expert>\r\nname={name}\r\npath={path}\r\nexpertmode=5\r\n<inputs>\r\n</inputs>\r\n</expert>\r\n"
    return s + "<window>\r\nheight=100\r\n</window>\r\n</chart>\r\n"

def setup(tmp, charts):
    pdir = os.path.join(tmp, "MQL5", "Profiles", "Charts", "Default"); os.makedirs(pdir)
    for i, (sym, ex) in enumerate(charts, 1): D.write_text(os.path.join(pdir, f"chart{i:02d}.chr"), chart(sym, ex), "utf-16")
    return pdir

calls = []
D.stop_terminal = lambda t: calls.append("stop") or True
D.start_terminal = lambda t: calls.append("start")
D.time.sleep = lambda s: None
path = "Experts\\chien\\" + EA + ".ex5"
cfg = dict(apply=True, ensure=[dict(ea=EA + ".mq5", symbol="GBPJPY", period="H1")], remove=[])
compiled = {EA + ".mq5": dict(ok=True)}

# 1) 切り詰められた name(…+H)だけが付いている → 装着済みと判定し、何もしない
with tempfile.TemporaryDirectory() as tmp:
    pdir = setup(tmp, [("EURUSD", [(EA[:60], path)]), ("USDCHF", []), ("GBPUSD", [])]); inv = D.inventory(tmp)
    r = D.apply("t.exe", tmp, cfg, inv, compiled, os.path.join(tmp, "bk"))
    assert r["changed"] is False and not any(a.startswith("attach") for a in r["actions"]), r
    print("1 ok: 切り詰め name でも装着済み", r["actions"])

# 2) chart01(切り詰め name)+ chart02(完全 name)の二重装着 → chart02 側を除去し再起動
calls.clear()
with tempfile.TemporaryDirectory() as tmp:
    pdir = setup(tmp, [("EURUSD", [(EA[:60], path)]), ("USDCHF", [("chien\\" + EA, path)]), ("GBPUSD", [])]); inv = D.inventory(tmp)
    r = D.apply("t.exe", tmp, cfg, inv, compiled, os.path.join(tmp, "bk"))
    inv2 = D.inventory(tmp); att = [(a["chart"], a["path"]) for a in inv2["attached"]]
    assert r["changed"] is True and any(a.startswith("dedupe") for a in r["actions"]) and att == [("chart01.chr", path)], (r, att)
    assert calls == ["stop", "start"]
    print("2 ok: 重複を除去", r["actions"], att)

# 3) restart_token: 変更が無くても 1 回だけ再起動し、同じ token では再起動しない
calls.clear()
with tempfile.TemporaryDirectory() as tmp:
    pdir = setup(tmp, [("EURUSD", [(EA, path)]), ("USDCHF", [])]); inv = D.inventory(tmp)
    c2 = dict(cfg, restart_token="2026-10-21a")
    r1 = D.apply("t.exe", tmp, c2, inv, compiled, os.path.join(tmp, "bk")); r2 = D.apply("t.exe", tmp, c2, inv, compiled, os.path.join(tmp, "bk"))
    assert r1.get("restarted") and r1["changed"] is False and not r2.get("restarted") and calls == ["stop", "start"], (r1, r2, calls)
    print("3 ok: restart_token は 1 回だけ", r1["actions"])

# 4) 未装着(空チャートのみ)→ 従来どおり chart01 に装着
calls.clear()
with tempfile.TemporaryDirectory() as tmp:
    pdir = setup(tmp, [("EURUSD", []), ("USDCHF", [])]); inv = D.inventory(tmp)
    r = D.apply("t.exe", tmp, cfg, inv, compiled, os.path.join(tmp, "bk")); att = [(a["chart"], a["path"]) for a in D.inventory(tmp)["attached"]]
    assert r["changed"] and att == [("chart01.chr", path)], (r, att)
    print("4 ok: 未装着なら chart01 に装着", r["actions"])
print("all ok")
