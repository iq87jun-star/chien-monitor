import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { BattleEvent, HitResult, UnitState } from "../../core/battle/types";
import { STATUS_LABEL, type StatusType } from "../../core/types";
import { CHAR_BY_ID } from "../../data/characters";
import { VOICES } from "../../data/voices";
import { useGame } from "../../state/store";
import { useNav, type BattleView } from "../nav";
import { Bar } from "../components/Bar";
import { EnemyPortrait, Portrait } from "../components/Portrait";
import { Button } from "../components/Button";
import { GemIcon, GoldIcon, ShardIcon } from "../components/Resources";
import { elementColor } from "../theme/tokens";

interface View {
  hp: number;
  maxHp: number;
  shield: number;
  energy: number;
  statuses: StatusType[];
}

interface Popup {
  key: number;
  uid: string;
  text: string;
  kind: "dmg" | "crit" | "heal" | "shield" | "dot" | "miss";
}

/** 1イベントあたりの表示時間（×1速） */
const DURATION: Record<BattleEvent["t"], number> = {
  round: 380,
  action: 760,
  dot: 420,
  skip: 420,
  expire: 0,
  end: 0,
};

function initialView(units: UnitState[]): Record<string, View> {
  return Object.fromEntries(
    units.map((u) => [u.uid, { hp: u.hp, maxHp: u.maxHp, shield: u.shield, energy: u.energy, statuses: [] as StatusType[] }]),
  );
}

function applyHit(v: View, h: HitResult): View {
  let statuses = v.statuses;
  if (h.status && h.status !== "shield" && !statuses.includes(h.status)) statuses = [...statuses, h.status];
  if (h.killed) statuses = [];
  return { ...v, hp: h.hpAfter, shield: h.shieldAfter, energy: h.energyAfter, statuses };
}

/** イベントを1つ反映した表示状態を返す */
export function reduceView(view: Record<string, View>, e: BattleEvent): Record<string, View> {
  const next = { ...view };
  switch (e.t) {
    case "action": {
      next[e.actor] = { ...next[e.actor], energy: e.actorEnergy };
      for (const h of e.hits) next[h.target] = applyHit(next[h.target], h);
      break;
    }
    case "dot":
      next[e.unit] = { ...next[e.unit], hp: e.hpAfter, shield: e.shieldAfter, statuses: e.killed ? [] : next[e.unit].statuses };
      break;
    case "expire":
      next[e.unit] = {
        ...next[e.unit],
        statuses: next[e.unit].statuses.filter((s) => !e.statuses.includes(s)),
        shield: e.statuses.includes("shield") ? 0 : next[e.unit].shield,
      };
      break;
  }
  return next;
}

export function Battle({ view }: { view: BattleView }) {
  const { result } = view;
  const settings = useGame((s) => s.save.settings);
  const updateSettings = useGame((s) => s.updateSettings);
  const close = useNav((s) => s.close);
  const units = useMemo(() => Object.fromEntries(result.initial.map((u) => [u.uid, u])), [result]);

  const [idx, setIdx] = useState(0);
  const [state, setState] = useState(() => initialView(result.initial));
  const [popups, setPopups] = useState<Popup[]>([]);
  const [actor, setActor] = useState<string | null>(null);
  const [hitTargets, setHitTargets] = useState<string[]>([]);
  const [round, setRound] = useState(0);
  const [log, setLog] = useState<string>("戦闘開始");
  const [done, setDone] = useState(false);
  const popKey = useRef(0);
  const speed = settings.speed;

  const nameOf = useCallback((uid: string) => units[uid]?.setup.name ?? uid, [units]);

  const finish = useCallback(() => {
    let v = initialView(result.initial);
    for (const e of result.events) v = reduceView(v, e);
    setState(v);
    setIdx(result.events.length);
    setActor(null);
    setPopups([]);
    setDone(true);
  }, [result]);

  useEffect(() => {
    if (done) return;
    if (idx >= result.events.length) {
      setDone(true);
      return;
    }
    const e = result.events[idx];
    setState((s) => reduceView(s, e));
    const pops: Popup[] = [];
    if (e.t === "round") {
      setRound(e.round);
      setActor(null);
      setHitTargets([]);
    } else if (e.t === "action") {
      setActor(e.actor);
      setHitTargets(e.hits.filter((h) => h.kind === "damage").map((h) => h.target));
      for (const h of e.hits) {
        pops.push({
          key: ++popKey.current,
          uid: h.target,
          text: h.kind === "heal" ? `+${h.amount}` : h.kind === "shield" ? `盾+${h.amount}` : `${h.amount}`,
          kind: h.kind === "heal" ? "heal" : h.kind === "shield" ? "shield" : h.crit ? "crit" : "dmg",
        });
      }
      setLog(e.kind === "skill" ? `${nameOf(e.actor)}「${e.skillName}」！` : `${nameOf(e.actor)}の攻撃`);
    } else if (e.t === "dot") {
      pops.push({ key: ++popKey.current, uid: e.unit, text: `${e.dmg}`, kind: "dot" });
      setLog(`${nameOf(e.unit)}は${STATUS_LABEL[e.status]}で${e.dmg}のダメージ`);
    } else if (e.t === "skip") {
      pops.push({ key: ++popKey.current, uid: e.unit, text: STATUS_LABEL[e.reason], kind: "miss" });
      setLog(`${nameOf(e.unit)}は${STATUS_LABEL[e.reason]}で動けない`);
    }
    if (pops.length) setPopups(pops);
    const t = setTimeout(() => setIdx((i) => i + 1), DURATION[e.t] / speed);
    return () => clearTimeout(t);
  }, [idx, done, result, speed, nameOf]);

  const row = (side: "ally" | "enemy", slots: number[]) => (
    <div className={`bt-row bt-row--${slots.length}`}>
      {slots.map((slot) => {
        const uid = `${side}-${slot}`;
        const u = units[uid];
        if (!u) return <div key={uid} className="bt-unit bt-unit--empty" />;
        const v = state[uid];
        const dead = v.hp <= 0;
        return (
          <div
            key={uid}
            className={`bt-unit ${dead ? "is-dead" : ""} ${actor === uid ? "is-acting" : ""} ${hitTargets.includes(uid) ? "is-hit" : ""} bt-unit--${side}`}
            style={{ ["--ec" as string]: elementColor(u.setup.element) }}
          >
            <div className="bt-unit__art">
              {side === "ally" ? <Portrait id={u.setup.refId} crop="bust" /> : <EnemyPortrait id={u.setup.refId} />}
              {v.statuses.length > 0 && (
                <div className="bt-unit__status">
                  {v.statuses.map((s) => (
                    <span key={s} className={`bt-st bt-st--${s}`}>
                      {STATUS_LABEL[s][0]}
                    </span>
                  ))}
                </div>
              )}
              {popups
                .filter((p) => p.uid === uid)
                .map((p) => (
                  <span key={p.key} className={`bt-pop bt-pop--${p.kind} num`}>
                    {p.text}
                  </span>
                ))}
            </div>
            <div className="bt-unit__name">{u.setup.name}</div>
            <Bar value={v.hp} max={v.maxHp} color={side === "ally" ? "var(--k-hp)" : "var(--k-hpEnemy)"} extra={v.shield} extraColor="var(--k-shield)" height={5} />
            <Bar value={v.energy} max={100} color={v.energy >= 100 ? "var(--k-kinLight)" : "var(--k-energy)"} height={3} />
          </div>
        );
      })}
    </div>
  );

  return (
    <div className="overlay battle">
      <header className="overlay__bar">
        <span className="brush">{view.title}</span>
        <span className="bt-round num">
          第{round}合 / 20
        </span>
        <div className="bt-ctrl">
          <button
            className="k-chip num"
            onClick={() => updateSettings({ speed: speed === 1 ? 2 : speed === 2 ? 4 : 1 })}
            aria-label="速度切り替え"
          >
            ×{speed}
          </button>
          {!done && (
            <button className="k-chip" onClick={finish}>
              飛ばす
            </button>
          )}
        </div>
      </header>
      <div className="bt-field">
        <div className="bt-side bt-side--enemy">
          {row("enemy", [2, 3, 4])}
          {row("enemy", [0, 1])}
        </div>
        <div className="bt-mid">
          <div className="k-divider" />
        </div>
        <div className="bt-side bt-side--ally">
          {row("ally", [0, 1])}
          {row("ally", [2, 3, 4])}
        </div>
      </div>
      <div className="bt-log">{log}</div>
      {done && <BattleEnd view={view} onClose={close} />}
    </div>
  );
}

function BattleEnd({ view, onClose }: { view: BattleView; onClose: () => void }) {
  const { result } = view;
  // 勝敗セリフは生き残った（敗北時は先頭の）剣華が話す
  const allies = result.final.filter((u) => u.side === "ally");
  const speaker = (result.win ? allies.find((u) => u.hp > 0) : allies[0])?.setup.refId;
  const c = speaker ? CHAR_BY_ID[speaker] : null;
  const line = speaker ? (result.win ? VOICES[speaker].victory : VOICES[speaker].defeat) : "";
  const reasonText = result.reason === "timeout" ? "時間切れ" : result.win ? "敵を殲滅" : "全滅";
  return (
    <div className={`bt-end ${result.win ? "is-win" : "is-lose"}`}>
      <div className="bt-end__box kintsugi">
        <div className="bt-end__title brush">{result.win ? "勝利" : "敗北"}</div>
        <div className="k-dim num">
          {reasonText}・{result.rounds}合
        </div>
        {c && (
          <div className="bt-end__voice">
            <div className="bt-end__face">
              <Portrait id={c.id} crop="face" />
            </div>
            <p>
              <b>{c.given}</b>「{line}」
            </p>
          </div>
        )}
        {view.rewards && (
          <div className="bt-end__rewards num">
            <span>
              <GoldIcon /> {view.rewards.gold.toLocaleString()}
            </span>
            {view.rewards.gems > 0 && (
              <span>
                <GemIcon /> {view.rewards.gems}（初回）
              </span>
            )}
          </div>
        )}
        {view.shards && (
          <div className="bt-end__rewards num">
            <span>
              <ShardIcon /> {CHAR_BY_ID[view.shards.charId].given}の花片 +{view.shards.amount}
            </span>
          </div>
        )}
        {!result.win && <p className="k-dim">剣華を育てるか、編成や属性相性を見直してみましょう。</p>}
        <Button onClick={onClose} style={{ width: "100%" }}>
          戻る
        </Button>
      </div>
    </div>
  );
}
