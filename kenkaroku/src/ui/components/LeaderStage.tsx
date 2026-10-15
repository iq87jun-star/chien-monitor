import { useMemo, useState } from "react";
import { CHAR_BY_ID } from "../../data/characters";
import { homeLines, teamLeader, timeOfDay } from "../../core/dialogue";
import { useGame } from "../../state/store";
import { useNav } from "../nav";
import { TOKENS } from "../theme/tokens";
import { useNow } from "../hooks";
import { Portrait } from "./Portrait";

const TOD_LABEL = { morning: "朝", day: "昼", night: "夜" } as const;

/** ホーム上部：編成リーダーの立ち絵。タップで台詞、時間帯で背景と台詞が変わる */
export function LeaderStage() {
  const team = useGame((s) => s.save.team);
  const open = useNav((s) => s.open);
  const now = useNow(60_000);
  const tod = timeOfDay(new Date(now));
  const leader = teamLeader(team);
  const lines = useMemo(() => (leader ? homeLines(leader, tod) : []), [leader, tod]);
  // 最初は時間帯の台詞から
  const [n, setN] = useState(-1);
  const [tapKey, setTapKey] = useState(0);
  const t = TOKENS.time[tod];
  if (!leader) return null;
  const c = CHAR_BY_ID[leader];
  const line = n < 0 ? lines[lines.length - 1] : lines[n % lines.length];

  return (
    <section
      className={`leader leader--${tod}`}
      style={{ ["--top" as string]: t.top, ["--bottom" as string]: t.bottom, ["--glow" as string]: t.glow, ["--cc" as string]: c.color }}
    >
      <div className="leader__sky" aria-hidden>
        {tod === "night" && <span className="leader__moon" />}
        {tod === "morning" && <span className="leader__sun" />}
        <span className="leader__lanterns" />
      </div>
      <button
        className="leader__art"
        aria-label={`${c.given}に話しかける`}
        onClick={() => {
          setN((x) => (x < 0 ? 0 : x + 1));
          setTapKey((k) => k + 1);
        }}
      >
        <Portrait id={leader} crop="full" frame={false} background={false} className={tapKey ? "leader__bounce" : ""} key={tapKey} />
      </button>
      <div className="leader__bubble" key={`b${tapKey}`}>
        <b>{c.given}</b>
        {line}
      </div>
      <div className="leader__meta">
        <span className="leader__tod brush">{TOD_LABEL[tod]}</span>
        <button className="k-chip" onClick={() => open({ kind: "char", id: leader })}>
          {c.epithet}
        </button>
      </div>
    </section>
  );
}
