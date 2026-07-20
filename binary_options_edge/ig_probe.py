"""IG公式API(labs.ig.com)でバイナリーオプション銘柄が取得可能かを探索するプローブ。

背景:
  - IGグループには公式REST API(認証: APIキー+口座ログイン)が存在する。
  - ただしIG証券(日本)のヘルプは「APIアクセスは提供していません」と案内しており、
    日本口座でAPIキーが発行できるか・バイナリー銘柄(EPIC)が市場ツリーに
    公開されているかは口座で実際に試すまで不明。
  - 本スクリプトはその判定を自動化する。バイナリーEPICが見つかれば、
    そのまま気配スナップショット収集(observation.py互換CSV)まで行える。

⚠️ 必ずデモ口座のAPIキーで試すこと。公式APIのみを使用し、
   Web取引画面の内部通信を直接叩くこと(非公式スクレイピング)はしない。

使い方:
  export IG_API_KEY=...      # My IG > 設定 > APIキー で発行(デモ)
  export IG_USERNAME=...
  export IG_PASSWORD=...
  export IG_ACCOUNT_TYPE=demo   # demo | live

  python -m binary_options_edge.ig_probe probe            # バイナリー銘柄の探索
  python -m binary_options_edge.ig_probe collect EPIC1 EPIC2 --interval 60
                                                          # 気配収集(CSV出力)
"""
from __future__ import annotations

import csv
import os
import sys
import time
from datetime import datetime, timezone

import requests

BASE = {"demo": "https://demo-api.ig.com/gateway/deal",
        "live": "https://api.ig.com/gateway/deal"}

# バイナリーを示唆する語(日英)。市場ツリー探索と銘柄名判定の両方に使う
BINARY_HINTS = ("バイナリー", "ラダー", "ワンタッチ", "レンジ",
                "binar", "ladder", "touch", "digital", "sprint")


class IGSession:
    def __init__(self) -> None:
        self.api_key = os.environ.get("IG_API_KEY", "")
        self.username = os.environ.get("IG_USERNAME", "")
        self.password = os.environ.get("IG_PASSWORD", "")
        self.base = BASE.get(os.environ.get("IG_ACCOUNT_TYPE", "demo"), BASE["demo"])
        if not (self.api_key and self.username and self.password):
            raise SystemExit(
                "環境変数 IG_API_KEY / IG_USERNAME / IG_PASSWORD を設定してください"
                "(デモ口座のAPIキー推奨)。キーが発行できない場合、それ自体が"
                "「日本口座にAPI提供なし」の確定情報になります。")
        self.s = requests.Session()
        self.s.headers.update({"X-IG-API-KEY": self.api_key,
                               "Content-Type": "application/json; charset=UTF-8",
                               "Accept": "application/json; charset=UTF-8"})

    def login(self) -> dict:
        r = self.s.post(f"{self.base}/session", json={
            "identifier": self.username, "password": self.password},
            headers={"Version": "2"}, timeout=30)
        if r.status_code != 200:
            raise SystemExit(f"ログイン失敗 HTTP {r.status_code}: {r.text[:300]}\n"
                             "→ APIキー/認証情報を確認。日本口座でキー自体が無効なら"
                             "『API提供なし』が確定。")
        self.s.headers.update({"CST": r.headers.get("CST", ""),
                               "X-SECURITY-TOKEN": r.headers.get("X-SECURITY-TOKEN", "")})
        return r.json()

    def get(self, path: str, version: str = "1", **params) -> dict:
        r = self.s.get(f"{self.base}{path}", params=params or None,
                       headers={"Version": version}, timeout=30)
        r.raise_for_status()
        return r.json()


def _is_binary_like(text: str) -> bool:
    t = (text or "").lower()
    return any(h.lower() in t for h in BINARY_HINTS)


def probe(sess: IGSession) -> list[dict]:
    """市場ツリーBFS+検索語で、バイナリーらしき銘柄(EPIC)を列挙する。"""
    info = sess.login()
    print(f"ログイン成功: accountType={info.get('accountType')} "
          f"currency={info.get('currencyIsoCode')}")

    found: dict[str, dict] = {}

    # 1) 市場ナビゲーションツリーをBFS(バイナリーらしきノードを優先展開)
    print("\n[1/2] 市場ツリー探索中...")
    queue: list[tuple[str, str, int]] = [("", "(root)", 0)]
    visited = 0
    while queue and visited < 200:      # 探索上限(デモのレート制限に配慮)
        node_id, node_name, depth = queue.pop(0)
        visited += 1
        try:
            path = f"/marketnavigation/{node_id}" if node_id else "/marketnavigation"
            data = sess.get(path)
        except requests.HTTPError as e:
            print(f"  ノード{node_id or 'root'} 取得失敗: {e}")
            continue
        for n in data.get("nodes") or []:
            name = n.get("name", "")
            # バイナリーらしき枝は必ず展開、それ以外は浅い階層のみ展開
            if _is_binary_like(name) or depth < 2:
                queue.append((n["id"], name, depth + 1))
            if _is_binary_like(name):
                print(f"  候補ノード: {name} (id={n['id']})")
        for m in data.get("markets") or []:
            label = f"{m.get('instrumentName','')} {m.get('instrumentType','')}"
            if _is_binary_like(label) or _is_binary_like(node_name):
                found[m["epic"]] = m
        time.sleep(0.3)

    # 2) 検索APIでも補完
    print("[2/2] 銘柄検索中...")
    for term in ("バイナリー", "ラダー", "binary", "ladder", "one touch"):
        try:
            data = sess.get("/markets", searchTerm=term)
            for m in data.get("markets") or []:
                if _is_binary_like(f"{m.get('instrumentName','')} {m.get('instrumentType','')}"):
                    found[m["epic"]] = m
        except requests.HTTPError as e:
            print(f"  検索'{term}'失敗: {e}")
        time.sleep(0.3)

    print(f"\n=== 結果: バイナリーらしき銘柄 {len(found)}件 ===")
    for epic, m in list(found.items())[:50]:
        print(f"  {epic}: {m.get('instrumentName')} [{m.get('instrumentType')}] "
              f"bid={m.get('bid')} offer={m.get('offer')} 状態={m.get('marketStatus')}")
    if not found:
        print("  見つからず。日本口座のAPIにはバイナリーが公開されていない可能性が高い。")
        print("  (CFD/FXのEPICは見えているのにバイナリーが無い場合、ほぼ確定)")
    else:
        print("\n→ collect モードで気配収集が可能:")
        print(f"  python -m binary_options_edge.ig_probe collect {' '.join(list(found)[:3])}")
    return list(found.values())


def collect(sess: IGSession, epics: list[str], interval: float = 60.0,
            out_path: str = "ig_binary_quotes.csv") -> None:
    """指定EPICの気配スナップショットを定期収集(README §2 方法Aの実装)。"""
    sess.login()
    new_file = not os.path.exists(out_path)
    print(f"収集開始: {len(epics)}銘柄, {interval}s間隔 -> {out_path} (Ctrl-Cで停止)")
    with open(out_path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["ts_utc", "epic", "instrument_name", "market_status",
                        "bid", "offer", "spread", "expiry", "update_time"])
        while True:
            for epic in epics:
                try:
                    d = sess.get(f"/markets/{epic}", version="3")
                    snap = d.get("snapshot", {})
                    inst = d.get("instrument", {})
                    bid, offer = snap.get("bid"), snap.get("offer")
                    spread = (offer - bid) if (bid is not None and offer is not None) else ""
                    w.writerow([datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                epic, inst.get("name"), snap.get("marketStatus"),
                                bid, offer, spread, inst.get("expiry"),
                                snap.get("updateTime")])
                except requests.HTTPError as e:
                    w.writerow([datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                epic, "", f"ERROR {e.response.status_code}",
                                "", "", "", "", ""])
                time.sleep(0.5)
            f.flush()
            time.sleep(max(interval - 0.5 * len(epics), 1.0))


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args or args[0] not in ("probe", "collect"):
        print(__doc__)
        raise SystemExit(1)
    sess = IGSession()
    if args[0] == "probe":
        probe(sess)
    else:
        interval = 60.0
        if "--interval" in sys.argv:
            interval = float(sys.argv[sys.argv.index("--interval") + 1])
        epics = [a for a in args[1:] if not a.replace(".", "").isdigit()]
        if not epics:
            raise SystemExit("collect には EPIC を1つ以上指定")
        collect(sess, epics, interval)


if __name__ == "__main__":
    main()
