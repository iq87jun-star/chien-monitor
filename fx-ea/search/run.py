#!/usr/bin/env python3
"""毎朝の探索実行。pending の仮説を事前固定プロトコルで検定し、台帳に記録する。

  python3 run.py            # pending をすべて実行
  python3 run.py --report   # 実行せず、台帳の要約だけ出す
"""
import json, os, sys, datetime as dt
import engine

HERE = os.path.dirname(os.path.abspath(__file__))
HYP = os.path.join(HERE, "hypotheses.json")
REPORT = os.path.join(HERE, "REPORT.md")


def summarize(led, lines):
    lines.append(f"**累積検定数: {led['cumulative_tests']:,}** "
                 f"→ 現在の必要t値 **{engine.required_t(led['cumulative_tests']):.2f}**\n")
    passed = [e for e in led["entries"] if e["result"].get("verdict") == "通過"]
    lines.append(f"検定済み仮説 {len(led['entries'])} 件 / うち通過 **{len(passed)} 件**\n")
    if passed:
        lines.append("## 通過した仮説\n")
        lines.append("| id | n | t | 必要t | 平均bp | OOS bp | PF | 負け年 |")
        lines.append("|---|--:|--:|--:|--:|--:|--:|--:|")
        for e in passed:
            r = e["result"]
            lines.append(f"| {e['id']} | {r['n']} | {r['t']} | {r['need_t']} | "
                         f"{r['mean_bp']} | {r['oos_bp']} | {r['pf']} | "
                         f"{r['neg_years']}/{r['years']} |")
        lines.append("")


def main():
    led = engine.load_ledger()
    report_only = "--report" in sys.argv

    lines = [f"# 探索レポート — {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"]

    if report_only:
        summarize(led, lines)
        open(REPORT, "w").write("\n".join(lines))
        print("\n".join(lines))
        return

    hyp = json.load(open(HYP))
    pending = [h for h in hyp["queue"] if h.get("status") == "pending"]

    if not pending:
        lines.append("本日の新規仮説なし。台帳の状態のみ報告します。\n")
        summarize(led, lines)
        open(REPORT, "w").write("\n".join(lines))
        print("\n".join(lines))
        return

    lines.append(f"本日の検定: **{len(pending)} 件**\n")
    results = []
    for h in pending:
        # 探索空間の大きさを累積検定数に加算する。
        # 「1つの仮説」でも裏で何通り試したかを申告させる = 自己申告の規律。
        led["cumulative_tests"] += int(h.get("space_size", 1))
        try:
            series = engine.build(h["family"], h["params"])
            res = engine.evaluate(series, led["cumulative_tests"])
        except Exception as ex:
            res = {"verdict": "エラー", "reason": f"{type(ex).__name__}: {ex}"}
        entry = {"id": h["id"], "note": h.get("note", ""), "family": h["family"],
                 "params": h["params"], "space_size": h.get("space_size", 1),
                 "tested_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
                 "cum_tests_at_time": led["cumulative_tests"], "result": res}
        led["entries"].append(entry)
        results.append(entry)
        h["status"] = "done"

    lines.append("## 本日の結果\n")
    for e in results:
        r = e["result"]
        mark = {"通過": "○", "棄却": "×", "検証不能": "－"}.get(r["verdict"], "!")
        lines.append(f"### {mark} `{e['id']}` — {r['verdict']}\n")
        lines.append(f"{e['note']}\n")
        if "n" in r and r.get("t") is not None:
            lines.append(f"| n | t | 必要t | 平均bp | IS bp | OOS bp | WF bp | PF | 勝率 | 負け年 |")
            lines.append(f"|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
            lines.append(f"| {r['n']} | {r['t']} | {r['need_t']} | {r['mean_bp']} | "
                         f"{r['is_bp']} | {r['oos_bp']} | {r.get('wf_bp')} | {r['pf']} | "
                         f"{r['wr']}% | {r['neg_years']}/{r['years']} |")
        lines.append(f"\n**判定理由**: {r['reason']}\n")

    summarize(led, lines)
    engine.save_ledger(led)
    json.dump(hyp, open(HYP, "w"), ensure_ascii=False, indent=1)
    open(REPORT, "w").write("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
