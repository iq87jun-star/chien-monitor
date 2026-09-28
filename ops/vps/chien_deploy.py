# -*- coding: utf-8 -*-
"""chien 配備モジュール(VPS 側)— docs/317 段階 2

役割(chien_ops_agent.py から端末ごとに呼ばれる):
  1) inventory: 端末のプロファイル(MQL5\\Profiles\\Charts\\<profile>\\chart*.chr)を読み、どのチャートにどの EA が付いているかを一覧にする
  2) compile : manifest の ensure にある .mq5 を GitHub(公開)から取得し、その端末の MetaEditor でコンパイル(.ex5 は MQL5\\Experts\\chien\\ に置く)
  3) apply   : manifest で apply=true の口座だけ、端末を止めて chart*.chr の <expert> ブロックを書き換え(remove を外し、ensure を付け)、端末を再起動する
     - .chr はバックアップ(chien_backup\\<時刻>\\)してから書き換える。チャートは削除しない。
     - expertmode(アルゴ取引許可などのフラグ)は同じ端末の既存 <expert> ブロックから学習して使う。無ければ manifest の expertmode か既定 5。
出力: <out>/<account>/deploy_status.json(棚卸し・コンパイル結果・適用結果)。
"""
import os, re, io, json, glob, time, shutil, datetime as dt, subprocess, urllib.request, urllib.parse

RAW_BASE = "https://raw.githubusercontent.com/iq87jun-star/chien-monitor/{branch}/"
MANIFEST_URL = RAW_BASE + "ops/config/deploy_manifest.json"
PERIOD_MIN = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440, "W1": 10080, "MN1": 43200}


def fetch(url, binary=False):
    req = urllib.request.Request(url + ("&" if "?" in url else "?") + "t=" + str(int(time.time())), headers={"User-Agent": "chien-deploy"})
    with urllib.request.urlopen(req, timeout=60) as r:
        b = r.read()
    return b if binary else b.decode("utf-8")


def load_manifest(branch="claude/prop-trading-new-methods-a8y3l1"):
    return json.loads(fetch(MANIFEST_URL.format(branch=branch)))


def read_text(p):
    b = open(p, "rb").read()
    for enc in ("utf-16", "utf-8-sig", "cp932"):
        try:
            return b.decode(enc), enc
        except Exception:
            continue
    return b.decode("latin-1"), "latin-1"


def write_text(p, s, enc):
    with open(p, "wb") as f:
        f.write(s.encode(enc))


EXPERT_RE = re.compile(r"<expert>\r?\n(.*?)</expert>\r?\n", re.S)


def parse_chart(p):
    s, enc = read_text(p)
    top = dict(re.findall(r"^(symbol|period_type|period_size|period|id|profile)=(.*?)\r?$", s, re.M))
    experts = []
    for m in EXPERT_RE.finditer(s):
        body = m.group(1)
        d = dict(re.findall(r"^(name|path|expertmode|flags)=(.*?)\r?$", body, re.M))
        inp = re.search(r"<inputs>\r?\n(.*?)</inputs>", body, re.S)
        d["inputs"] = dict(re.findall(r"^(\w+)=(.*?)\r?$", inp.group(1), re.M)) if inp else {}
        d["span"] = (m.start(), m.end())
        experts.append(d)
    return dict(file=os.path.basename(p), symbol=top.get("symbol", ""), period_type=top.get("period_type", ""), period_size=top.get("period_size", ""), experts=experts), s, enc


def profile_dir(data_path):
    root = os.path.join(data_path, "MQL5", "Profiles", "Charts")
    cur = None
    ini = os.path.join(data_path, "config", "terminal.ini")
    if os.path.exists(ini):
        t, _ = read_text(ini); m = re.search(r"^Profile=(.*?)\r?$", t, re.M)
        if m: cur = m.group(1).strip()
    if cur and os.path.isdir(os.path.join(root, cur)): return os.path.join(root, cur), cur
    if os.path.isdir(os.path.join(root, "Default")): return os.path.join(root, "Default"), "Default"
    ds = [d for d in glob.glob(os.path.join(root, "*")) if os.path.isdir(d)]
    return (ds[0], os.path.basename(ds[0])) if ds else (None, None)


def inventory(data_path):
    pdir, pname = profile_dir(data_path)
    charts = []
    if pdir:
        for p in sorted(glob.glob(os.path.join(pdir, "chart*.chr"))):
            try:
                c, _, enc = parse_chart(p); c["enc"] = enc
                for e in c["experts"]: e.pop("span", None)
                charts.append(c)
            except Exception as ex:
                charts.append(dict(file=os.path.basename(p), error=repr(ex)))
    learned = [e.get("expertmode") for c in charts for e in c.get("experts", []) if e.get("expertmode")]
    return dict(profile=pname, profile_dir=pdir, charts=charts, expertmode_seen=sorted(set(learned)),
                attached=[dict(chart=c["file"], symbol=c.get("symbol"), ea=e.get("name", "").replace("/", "\\").split("\\")[-1], path=e.get("path", ""), expertmode=e.get("expertmode"))
                          for c in charts for e in c.get("experts", [])])


def metaeditor_for(terminal_path):
    d = os.path.dirname(terminal_path)
    for n in ("metaeditor64.exe", "MetaEditor64.exe"):
        p = os.path.join(d, n)
        if os.path.exists(p): return p
    return None


def compile_ea(terminal_path, data_path, branch, ea_file):
    """GitHub から mq5 を取得 → MQL5\\Experts\\chien\\ に置く → MetaEditor でコンパイル。戻り値: dict(ok, ex5, log)"""
    me = metaeditor_for(terminal_path)
    dst_dir = os.path.join(data_path, "MQL5", "Experts", "chien"); os.makedirs(dst_dir, exist_ok=True)
    url = RAW_BASE.format(branch=branch) + "mql5/" + urllib.parse.quote(ea_file)
    src = fetch(url, binary=True)
    dst = os.path.join(dst_dir, ea_file)
    old = open(dst, "rb").read() if os.path.exists(dst) else None
    changed = (old != src)
    if changed: open(dst, "wb").write(src)
    ex5 = dst[:-4] + ".ex5"
    if not me: return dict(ok=False, ex5=ex5, log="metaeditor64.exe not found", changed=changed)
    if not changed and os.path.exists(ex5) and os.path.getmtime(ex5) >= os.path.getmtime(dst):
        return dict(ok=True, ex5=ex5, log="up to date", changed=False)
    logp = dst + ".log"
    inc = os.path.join(data_path, "MQL5")
    r = subprocess.run([me, f"/compile:{dst}", f"/inc:{inc}", f"/log:{logp}"], capture_output=True, timeout=300)
    log, _ = read_text(logp) if os.path.exists(logp) else ("", "")
    ok = os.path.exists(ex5) and os.path.getmtime(ex5) >= os.path.getmtime(dst) - 1 and "0 error" in log.replace("errors", "error")
    tail = "\n".join([l for l in log.splitlines() if "error" in l.lower() or "warning" in l.lower() or "Result" in l][-12:])
    return dict(ok=ok, ex5=ex5, log=tail[:2000], changed=changed, rc=r.returncode)


def terminal_pids(terminal_path):
    ps = ["powershell", "-NoProfile", "-Command", f"Get-CimInstance Win32_Process -Filter \"Name='terminal64.exe'\" | Where-Object {{ $_.ExecutablePath -eq '{terminal_path}' }} | Select-Object -ExpandProperty ProcessId"]
    r = subprocess.run(ps, capture_output=True, text=True, timeout=60)
    return [int(x) for x in r.stdout.split() if x.strip().isdigit()]


def stop_terminal(terminal_path):
    for pid in terminal_pids(terminal_path):
        subprocess.run(["taskkill", "/PID", str(pid), "/T"], capture_output=True, timeout=60)   # まず通常終了
    for _ in range(20):
        if not terminal_pids(terminal_path): return True
        time.sleep(1)
    for pid in terminal_pids(terminal_path):
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=60)
    time.sleep(2)
    return not terminal_pids(terminal_path)


def start_terminal(terminal_path):
    subprocess.Popen([terminal_path], cwd=os.path.dirname(terminal_path), creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))


def expert_block(name_noext, rel_path, expertmode, eol):
    return f"<expert>{eol}name={name_noext}{eol}path={rel_path}{eol}expertmode={expertmode}{eol}<inputs>{eol}</inputs>{eol}</expert>{eol}"


def apply(terminal_path, data_path, acct_cfg, inv, compiled, backup_root):
    """manifest に従って chart*.chr を書き換える。戻り値: dict(changed, actions, error)"""
    pdir = inv.get("profile_dir")
    if not pdir: return dict(changed=False, actions=[], error="profile dir not found")
    actions = []; files = {}
    for p in sorted(glob.glob(os.path.join(pdir, "chart*.chr"))):
        c, s, enc = parse_chart(p); files[p] = [c, s, enc, False]
    eol = "\r\n"
    # 1) remove
    for pat in acct_cfg.get("remove", []):
        for p, rec in files.items():
            c, s, enc, ch = rec
            for e in sorted(c["experts"], key=lambda e: -e["span"][0]):
                if pat in e.get("name", "") or pat in e.get("path", ""):
                    s = s[:e["span"][0]] + s[e["span"][1]:]; rec[1] = s; rec[3] = True
                    actions.append(f"remove {e['name'].split(chr(92))[-1]} from {c['file']}")
            if rec[3]:
                c2, _, _ = parse_chart_text(rec[1]); rec[0] = c2
    # 2) ensure
    modes = inv.get("expertmode_seen") or []
    mode = str(acct_cfg.get("expertmode") or (modes[0] if modes else 5))
    for want in acct_cfg.get("ensure", []):
        ea = want["ea"]; base = ea[:-4] if ea.lower().endswith(".mq5") else ea
        comp = compiled.get(ea, {})
        if not comp.get("ok"):
            actions.append(f"skip ensure {base}: not compiled"); continue
        present = any(e.get("name", "").replace("/", "\\").split("\\")[-1] == base for rec in files.values() for e in rec[0]["experts"])
        if present:
            continue
        rel = "Experts\\chien\\" + base + ".ex5"; name = "chien\\" + base
        sym = want.get("symbol", ""); per = want.get("period", "H1")
        target = None
        for p, rec in files.items():
            c = rec[0]
            if c.get("symbol", "").upper().startswith(sym.upper()) and not c["experts"]: target = p; break
        if target is None:
            for p, rec in files.items():
                if not rec[0]["experts"]: target = p; break
        if target is None:
            # 新しいチャートファイルを作る(既存の最初のチャートを複製して symbol/period を差し替え)
            src = sorted(files.keys())[0] if files else None
            if not src: actions.append(f"skip ensure {base}: no chart to clone"); continue
            n = 1
            while os.path.exists(os.path.join(pdir, f"chart{n:02d}.chr")): n += 1
            target = os.path.join(pdir, f"chart{n:02d}.chr")
            c0, s0, enc0, _ = files[src]
            s0 = EXPERT_RE.sub("", s0)
            s0 = re.sub(r"^symbol=.*?$", f"symbol={sym}", s0, count=1, flags=re.M)
            s0 = re.sub(r"^period_type=.*?$", "period_type=1" if PERIOD_MIN.get(per, 60) >= 60 and PERIOD_MIN.get(per, 60) < 1440 else "period_type=0", s0, count=1, flags=re.M)
            s0 = re.sub(r"^period_size=.*?$", f"period_size={PERIOD_MIN.get(per, 60) // 60 if PERIOD_MIN.get(per, 60) >= 60 else PERIOD_MIN.get(per, 60)}", s0, count=1, flags=re.M)
            files[target] = [parse_chart_text(s0)[0], s0, enc0, True]
            actions.append(f"new chart {os.path.basename(target)} {sym} {per}")
        rec = files[target]; s = rec[1]
        m = re.search(r"^<window>", s, re.M)
        blk = expert_block(name, rel, mode, eol)
        s = (s[:m.start()] + blk + s[m.start():]) if m else s.replace("</chart>", blk + "</chart>", 1)
        rec[1] = s; rec[3] = True; rec[0] = parse_chart_text(s)[0]
        actions.append(f"attach {base} to {os.path.basename(target)} (expertmode={mode})")
    changed = [p for p, rec in files.items() if rec[3]]
    if not changed: return dict(changed=False, actions=actions, error=None)
    # 3) stop terminal → backup → write → start
    if not stop_terminal(terminal_path): return dict(changed=False, actions=actions, error="terminal did not stop")
    bdir = os.path.join(backup_root, dt.datetime.now().strftime("%Y%m%d_%H%M%S")); os.makedirs(bdir, exist_ok=True)
    for p in changed:
        if os.path.exists(p): shutil.copy2(p, bdir)
        write_text(p, files[p][1], files[p][2])
    start_terminal(terminal_path); time.sleep(15)
    return dict(changed=True, actions=actions, error=None, backup=bdir)


def parse_chart_text(s):
    top = dict(re.findall(r"^(symbol|period_type|period_size)=(.*?)\r?$", s, re.M))
    experts = []
    for m in EXPERT_RE.finditer(s):
        body = m.group(1); d = dict(re.findall(r"^(name|path|expertmode)=(.*?)\r?$", body, re.M)); d["span"] = (m.start(), m.end()); experts.append(d)
    return dict(symbol=top.get("symbol", ""), experts=experts), s, None


def prepare_profile(data_path, account, cfg, inv, compiled):
    """MQL5 VPS 用: プロファイル MQL5\\Profiles\\Charts\\chien_<口座>\\chart01.chr を作る(正しい EA 1 本・既定入力)。Default には触らない。
    ユーザーはその口座でログイン → ファイル→プロファイル→chien_<口座> → VPS→移行、で反映する。"""
    pdir = inv.get("profile_dir")
    if not pdir: return dict(ok=False, error="profile dir not found")
    srcs = sorted(glob.glob(os.path.join(pdir, "chart*.chr")))
    if not srcs: return dict(ok=False, error="no template chart in current profile")
    modes = inv.get("expertmode_seen") or []; mode = str(cfg.get("expertmode") or (modes[0] if modes else 5))
    name = f"chien_{account}"; ndir = os.path.join(os.path.dirname(pdir), name); os.makedirs(ndir, exist_ok=True)
    eol = "\r\n"; made = []
    c0, s0, enc0 = parse_chart(srcs[0]); s0 = EXPERT_RE.sub("", s0)
    for i, want in enumerate(cfg.get("ensure", []), start=1):
        ea = want["ea"]; base = ea[:-4] if ea.lower().endswith(".mq5") else ea
        comp = compiled.get(ea, {})
        if not comp.get("ok"): made.append(f"skip {base}: not compiled"); continue
        sym = want.get("symbol", c0.get("symbol", "")); per = want.get("period", "H1"); pm = PERIOD_MIN.get(per, 60)
        s = re.sub(r"^symbol=.*?$", f"symbol={sym}", s0, count=1, flags=re.M)
        s = re.sub(r"^period_type=.*?$", ("period_type=1" if 60 <= pm < 1440 else "period_type=0"), s, count=1, flags=re.M)
        s = re.sub(r"^period_size=.*?$", f"period_size={pm // 60 if pm >= 60 else pm}", s, count=1, flags=re.M)
        blk = expert_block("chien\\" + base, "Experts\\chien\\" + base + ".ex5", mode, eol)
        m = re.search(r"^<window>", s, re.M)
        s = (s[:m.start()] + blk + s[m.start():]) if m else s.replace("</chart>", blk + "</chart>", 1)
        # 既存のプロファイル内チャートは消して作り直す(EA 1 本 = チャート 1 枚)
        for old in glob.glob(os.path.join(ndir, "chart*.chr")): os.remove(old)
        write_text(os.path.join(ndir, f"chart{i:02d}.chr"), s, enc0); made.append(f"{name}\\chart{i:02d}.chr = {base} @ {sym} {per} (expertmode={mode})")
    return dict(ok=True, profile=name, made=made)


def run(terminal_path, data_path, account, out_dir, manifest):
    """agent から呼ぶ入口。棚卸し → この端末で扱う全口座(manifest の terminal 一致)の EA をコンパイル → プロファイル生成。apply は MQL5 VPS では使わない。"""
    st = dict(time=dt.datetime.now().isoformat(), account=str(account), terminal=terminal_path)
    try:
        inv = inventory(data_path); st["inventory"] = inv
    except Exception as ex:
        st["inventory_error"] = repr(ex); inv = {}
    accounts = (manifest or {}).get("accounts", {})
    mine = {a: c for a, c in accounts.items() if (c.get("terminal") and c["terminal"].lower() in terminal_path.lower()) or a == str(account)}
    st["accounts_for_this_terminal"] = sorted(mine)
    branch = (manifest or {}).get("branch", "claude/prop-trading-new-methods-a8y3l1")
    st["compiled"] = {}; st["profiles"] = {}
    for a, cfg in mine.items():
        compiled = {}
        for want in cfg.get("ensure", []):
            try: compiled[want["ea"]] = compile_ea(terminal_path, data_path, branch, want["ea"])
            except Exception as ex: compiled[want["ea"]] = dict(ok=False, log=repr(ex))
        st["compiled"][a] = {k: {kk: vv for kk, vv in v.items() if kk != "ex5"} for k, v in compiled.items()}
        if cfg.get("prepare_profile", True):
            try: st["profiles"][a] = prepare_profile(data_path, a, cfg, inv, compiled)
            except Exception as ex: st["profiles"][a] = dict(ok=False, error=repr(ex))
        if cfg.get("apply") and a == str(account):
            try: st["apply"] = apply(terminal_path, data_path, cfg, inv, compiled, os.path.join(out_dir, "chien_backup"))
            except Exception as ex: st["apply"] = dict(changed=False, error=repr(ex))
    os.makedirs(out_dir, exist_ok=True)
    json.dump(st, open(os.path.join(out_dir, "deploy_status.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return st
