import { useState } from "react";
import { BEGINNER_MISSIONS } from "../../data/missions";
import { TRIALS, TRIAL_DAILY_LIMIT, TRIAL_LEVELS } from "../../data/stages";
import { CHAR_BY_ID, CHARACTERS } from "../../data/characters";
import { condValue, isMissionDone } from "../../core/missions";
import { progressOf, trialsLeft } from "../../core/game";
import { ELEMENT_LABEL, type Element } from "../../core/types";
import { useGame } from "../../state/store";
import { useNav } from "../nav";
import { useNow } from "../hooks";
import { Panel } from "../components/Panel";
import { Button } from "../components/Button";
import { Bar } from "../components/Bar";
import { GemIcon, GoldIcon, ShardIcon } from "../components/Resources";
import { CharCard } from "../components/CharCard";
import { elementColor } from "../theme/tokens";

export function Quest() {
  const [tab, setTab] = useState<"bloom" | "beginner">("bloom");
  return (
    <div className="screen quest">
      <div className="k-tabs k-tabs--wide">
        <button className={`k-tab ${tab === "bloom" ? "is-active" : ""}`} onClick={() => setTab("bloom")}>
          開花任務
        </button>
        <button className={`k-tab ${tab === "beginner" ? "is-active" : ""}`} onClick={() => setTab("beginner")}>
          初心者任務
        </button>
      </div>
      {tab === "bloom" ? <BloomTrials /> : <Beginner />}
    </div>
  );
}

function Beginner() {
  const save = useGame((s) => s.save);
  const claim = useGame((s) => s.claimMission);
  const p = progressOf(save);
  const list = [...BEGINNER_MISSIONS].sort(
    (a, b) => Number(save.missionsClaimed.includes(a.id)) - Number(save.missionsClaimed.includes(b.id)),
  );
  return (
    <Panel title="初心者任務">
      <ul className="missions">
        {list.map((m) => {
          const done = isMissionDone(m, p);
          const claimed = save.missionsClaimed.includes(m.id);
          const v = Math.min(condValue(m.cond, p), m.cond.n);
          return (
            <li key={m.id} className={`mission ${claimed ? "is-claimed" : ""}`}>
              <div className="mission__body">
                <div className="mission__title">{m.title}</div>
                <Bar value={v} max={m.cond.n} color={done ? "var(--k-kin)" : "var(--k-washiFaint)"} height={4} />
                <div className="mission__reward num">
                  <span className="k-dim">{v}/{m.cond.n}</span>
                  {m.reward.gems && (
                    <span>
                      <GemIcon size={12} /> {m.reward.gems}
                    </span>
                  )}
                  {m.reward.gold && (
                    <span>
                      <GoldIcon size={12} /> {m.reward.gold.toLocaleString()}
                    </span>
                  )}
                </div>
              </div>
              <Button size="sm" variant={done && !claimed ? "gold" : "ghost"} disabled={!done || claimed} onClick={() => claim(m.id)}>
                {claimed ? "受取済" : done ? "受け取る" : "未達成"}
              </Button>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}

function BloomTrials() {
  const save = useGame((s) => s.save);
  const fight = useGame((s) => s.fightTrial);
  const open = useNav((s) => s.open);
  const now = useNow(10_000);
  const [element, setElement] = useState<Element>("fire");
  const [level, setLevel] = useState(1);
  const candidates = CHARACTERS.filter((c) => c.element === element && save.roster[c.id]);
  const [targetByEl, setTargetByEl] = useState<Partial<Record<Element, string>>>({});
  const target = targetByEl[element] && save.roster[targetByEl[element]!] ? targetByEl[element]! : candidates[0]?.id;
  const left = trialsLeft(save, now);
  const trial = TRIALS.find((t) => t.element === element)!;
  const lv = TRIAL_LEVELS.find((l) => l.level === level)!;
  const locked = save.cleared < lv.requireStage;

  return (
    <>
      <Panel title="開花任務" right={<span className="k-dim num">本日 残り {left}/{TRIAL_DAILY_LIMIT}</span>}>
        <p className="k-dim">育てたい剣華を選んで挑む、花片集めの試練です。勝利したときだけ回数を使います。</p>
        <div className="trial__els">
          {TRIALS.map((t) => (
            <button
              key={t.element}
              className={`trial__el ${element === t.element ? "is-active" : ""}`}
              style={{ ["--ec" as string]: elementColor(t.element) }}
              onClick={() => setElement(t.element)}
            >
              <span className="brush">{ELEMENT_LABEL[t.element]}</span>
              <small>{t.name}</small>
            </button>
          ))}
        </div>
        <div className="trial__levels">
          {TRIAL_LEVELS.map((l) => (
            <button
              key={l.level}
              className={`k-tab ${level === l.level ? "is-active" : ""}`}
              disabled={save.cleared < l.requireStage}
              onClick={() => setLevel(l.level)}
            >
              {"壱弐参肆伍"[l.level - 1]}
            </button>
          ))}
        </div>
        <div className="trial__info num">
          <span>敵Lv {lv.enemyLevel}</span>
          <span>
            報酬 <ShardIcon size={12} /> {lv.shards}
          </span>
          {locked && <span className="k-warn">ステージを{lv.requireStage}つ突破で解放</span>}
        </div>
      </Panel>
      <Panel title="花片を受け取る剣華">
        {candidates.length === 0 ? (
          <p className="k-dim">{ELEMENT_LABEL[element]}属性の剣華がいません。</p>
        ) : (
          <div className="pick-grid">
            {candidates.map((c) => (
              <CharCard
                key={c.id}
                id={c.id}
                owned={save.roster[c.id]}
                selected={c.id === target}
                note={`片${save.roster[c.id].shards}`}
                onClick={() => setTargetByEl({ ...targetByEl, [element]: c.id })}
              />
            ))}
          </div>
        )}
        <Button
          variant="gold"
          size="lg"
          style={{ width: "100%", marginTop: 12 }}
          disabled={locked || left <= 0 || !target}
          onClick={() => {
            if (!target) return;
            const r = fight(element, level, target);
            if (r)
              open({
                kind: "battle",
                view: {
                  title: `${trial.name}・${"壱弐参肆伍"[level - 1]}`,
                  result: r.result,
                  shards: r.shards ? { charId: target, amount: r.shards } : undefined,
                },
              });
          }}
        >
          {target ? `${CHAR_BY_ID[target].given}のために挑む` : "挑む"}
        </Button>
      </Panel>
    </>
  );
}
