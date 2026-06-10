# -*- coding: utf-8 -*-
"""検証結果と入力データのハッシュを research/results/ に保存(再現性の証跡)。

docs/71 §4 の残課題対応。Dukascopy 実データで検証ノートを回す際、看板数値を docs に
"手転記"する代わりに、本ヘルパーで metrics + 入力SHA-256 + 実行環境バージョンを JSON 化する。
これにより「どの入力・どの環境で出た数字か」がリポジトリ内で追跡可能になる。

使い方(Colab/ローカル共通):
    from capture_results import save_result
    save_result(
        "v7_10year_validation",
        metrics={"net_pct": 80.3, "maxDD_pct": 14.8, "phase1_pass_pct": 79.2},
        inputs=[f"{H1_DIR}/EURJPY_h1.csv", f"{H1_DIR}/GBPJPY_h1.csv"],
        params=P, seed=MC_SEED,
    )
    # -> research/results/v7_10year_validation.json
"""
import os, sys, json, hashlib, platform, datetime

try:
    _BASE = os.path.dirname(os.path.abspath(__file__))
except NameError:            # ノート/Colab では __file__ が無い
    _BASE = os.getcwd()
RESULTS_DIR = os.path.join(_BASE, "results")


def sha256_file(path, _buf=1 << 20):
    """ファイルの SHA-256(同一入力であることの証跡)。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_buf), b""):
            h.update(chunk)
    return h.hexdigest()


def _env():
    out = {"python": sys.version.split()[0], "platform": platform.platform()}
    for mod in ("numpy", "pandas", "matplotlib"):
        try:
            out[mod] = getattr(__import__(mod), "__version__", "?")
        except Exception:
            out[mod] = None
    return out


def save_result(name, metrics, inputs=None, params=None, seed=None):
    """検証結果を research/results/<name>.json に保存して返す。

    name    : 出力ファイル名(拡張子不要)
    metrics : 看板数値の dict(例 {"net_pct":80.3,"maxDD_pct":14.8})
    inputs  : 入力データファイルのパス list(各 SHA-256 を記録)
    params  : EA入力など(再現に必要な設定)
    seed    : 乱数シード
    """
    inputs = inputs or []
    rec = {
        "name": name,
        "saved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "env": _env(),
        "seed": seed,
        "params": params,
        "inputs": [
            {
                "file": os.path.basename(p),
                "exists": os.path.exists(p),
                "bytes": os.path.getsize(p) if os.path.exists(p) else None,
                "sha256": sha256_file(p) if os.path.exists(p) else None,
            }
            for p in inputs
        ],
        "metrics": metrics,
    }
    os.makedirs(RESULTS_DIR, exist_ok=True)
    out = os.path.join(RESULTS_DIR, f"{name}.json")
    with open(out, "w") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2, default=str)
    missing = [i["file"] for i in rec["inputs"] if not i["exists"]]
    print(f"[capture] {out}  inputs={len(inputs)}" + (f"  ★未検出={missing}" if missing else ""))
    return out


if __name__ == "__main__":
    # 自己テスト(本ファイル自身を入力に見立ててハッシュ取得)
    p = save_result("_selftest", {"net_pct": 80.3, "maxDD_pct": 14.8},
                    inputs=[__file__], params={"demo": True}, seed=7)
    print(json.dumps(json.load(open(p)), ensure_ascii=False, indent=2)[:600])
