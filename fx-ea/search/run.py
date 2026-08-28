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
    for track, title, head, cols in (
        ("ea", "通過した仮説(売買トラック)",
         "| id | n | 補正t | 必要t | 日次t | 平均bp | 超過bp | OOS bp | PF | 負け年 |",
         lambda r: f"{r.get('t_adj')} | {r['need_t']} | {r.get('t_date')} | "
                   f"{r['mean_bp']} | {r.get('excess_bp')} | {r['oos_bp']} | "
                   f"{r['pf']} | {r['neg_years']}/{r['years']}"),
        ("indicator", "通過した仮説(指標トラック)",
         "| id | n | 補正t | 必要t | 日次t | 平均改善 | 改善率 | OOS改善 | 改善年 |",
         lambda r: f"{r.get('t_adj')} | {r['need_t']} | {r.get('t_date')} | "
                   f"{r['gain']} | {r['gain_ratio']:.1%} | {r['oos_gain']} | "
                   f"{r['hit_years']}/{r['years']}"),
    ):
        rows = [e for e in passed if e.get("track", "ea") == track]
        if not rows: continue
        lines.append(f"## {title}\n")
        lines.append(head)
        lines.append("|" + "---|" * (head.count("|") - 1))
        for e in rows:
            lines.append(f"| {e['id']} | {e['result']['n']} | {cols(e['result'])} |")
        lines.append("")
        if track == "indicator":
            lines.append("> 指標トラックの通過は「方向を当てられる」という意味ではない。"
                         "素朴な想定より変動幅・局面を正確に示せる、という意味しかない。\n")


def render_day(led, lines, day):
    """指定日に検定した全エントリを描画する(1日に複数回走らせても当日分が残る)。"""
    todays = [e for e in led["entries"] if e.get("tested_at") == day]
    if not todays:
        return
    lines.append(f"## 本日({day})の結果 — {len(todays)} 件\n")
    for e in todays:
        r = e["result"]
        mark = {"通過": "○", "棄却": "×", "検証不能": "－"}.get(r["verdict"], "!")
        lines.append(f"### {mark} `{e['id']}` — {r['verdict']}\n")
        lines.append(f"{e['note']}\n")
        if e.get("track") == "indicator" and r.get("t") is not None:
            lines.append("| n | 生t | 補正t | 必要t | 日数 | 日次t | 平均改善 | 素朴基準 | 改善率 | OOS改善 | 改善年 |")
            lines.append("|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
            lines.append(f"| {r['n']} | {r['t']} | {r['t_adj']} | {r['need_t']} | "
                         f"{r['n_dates']} | {r['t_date']} | {r['gain']} | {r['base']} | "
                         f"{r['gain_ratio']:.1%} | {r['oos_gain']} | "
                         f"{r['hit_years']}/{r['years']} |")
        elif "n" in r and r.get("t") is not None:
            lines.append("| n | 生t | 補正t | 必要t | 日数 | 日次t | 平均bp | 常時買持bp | 超過bp | OOS bp | WF bp | PF | 負け年 |")
            lines.append("|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
            lines.append(f"| {r['n']} | {r['t']} | {r.get('t_adj')} | {r['need_t']} | "
                         f"{r.get('n_dates')} | {r.get('t_date')} | "
                         f"{r['mean_bp']} | {r.get('bench_bp')} | {r.get('excess_bp')} | "
                         f"{r['oos_bp']} | {r.get('wf_bp')} | {r['pf']} | "
                         f"{r['neg_years']}/{r['years']} |")
        lines.append(f"\n**判定理由**: {r['reason']}\n")


def main():
    led = engine.load_ledger()
    report_only = "--report" in sys.argv

    lines = [f"# 探索レポート — {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"]

    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")

    if report_only:
        render_day(led, lines, today)
        summarize(led, lines)
        open(REPORT, "w").write("\n".join(lines))
        print("\n".join(lines))
        return

    hyp = json.load(open(HYP))
    pending = [h for h in hyp["queue"] if h.get("status") == "pending"]

    if not pending:
        lines.append("本日の新規仮説なし。台帳の状態のみ報告します。\n")
        render_day(led, lines, today)
        summarize(led, lines)
        open(REPORT, "w").write("\n".join(lines))
        print("\n".join(lines))
        return

    lines.append(f"今回の検定: **{len(pending)} 件**\n")
    results = []
    for h in pending:
        # 探索空間の大きさを累積検定数に加算する。
        # 「1つの仮説」でも裏で何通り試したかを申告させる = 自己申告の規律。
        led["cumulative_tests"] += int(h.get("space_size", 1))
        track = h.get("track", "ea")
        hold = int(h["params"].get("hold", 1))
        try:
            if track == "indicator":
                # 指標トラック: 方向ではなく「素朴基準に対する改善」を検定する
                series = engine.build_forecast(h["family"], h["params"])
                res = engine.evaluate_forecast(series, led["cumulative_tests"],
                                               hold=hold)
            else:
                series = engine.build(h["family"], h["params"])
                syms = h["params"].get("symbols")
                if syms is None and h["family"] == "pairs":
                    syms = [h["params"]["a"], h["params"]["b"]]
                if syms is None and "sym" in h["params"]:
                    syms = [h["params"]["sym"]]
                bench = engine.benchmark_series(syms, hold) if syms else None
                res = engine.evaluate(series, led["cumulative_tests"], hold=hold,
                                      benchmark=bench)
        except Exception as ex:
            res = {"verdict": "エラー", "reason": f"{type(ex).__name__}: {ex}"}
        entry = {"id": h["id"], "note": h.get("note", ""), "family": h["family"],
                 "track": track,
                 "params": h["params"], "space_size": h.get("space_size", 1),
                 "protocol": ("指標v1 (素朴基準に対する改善)" if track == "indicator"
                              else "v2 (重複補正 + 常時買い持ちベンチマーク)"),
                 "tested_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
                 "cum_tests_at_time": led["cumulative_tests"], "result": res}
        led["entries"].append(entry)
        results.append(entry)
        h["status"] = "done"

    render_day(led, lines, today)

    summarize(led, lines)
    engine.save_ledger(led)
    json.dump(hyp, open(HYP, "w"), ensure_ascii=False, indent=1)
    open(REPORT, "w").write("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
