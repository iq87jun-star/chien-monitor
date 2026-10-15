import { useState } from "react";
import { CHAPTERS, STAGES } from "../../data/stages";
import { FAST_IDLE_HOURS, IDLE_CAP_HOURS } from "../../core/economy";
import { fastIdleLeft, pendingIdle } from "../../core/game";
import { useGame } from "../../state/store";
import { useNav } from "../nav";
import { teamPower, useNow } from "../hooks";
import { Button } from "../components/Button";
import { Panel } from "../components/Panel";
import { Bar } from "../components/Bar";
import { GemIcon, GoldIcon } from "../components/Resources";
import { Sheet } from "../components/Modal";
import { EnemyPortrait } from "../components/Portrait";
import { BanterPanel } from "../components/BanterPanel";
import { LeaderStage } from "../components/LeaderStage";

export function Home() {
  const save = useGame((s) => s.save);
  const now = useNow();
  const idle = pendingIdle(save, now);
  const fastLeft = fastIdleLeft(save, now);
  const nextIndex = Math.min(save.cleared, STAGES.length - 1);
  const allClear = save.cleared >= STAGES.length;
  const [listOpen, setListOpen] = useState(false);

  return (
    <div className="home">
      <LeaderStage />
      <div className="screen">
      <IdlePanel hours={idle.hours} gold={idle.gold} gems={idle.gems} fastLeft={fastLeft} />
      <StagePanel index={nextIndex} allClear={allClear} power={teamPower(save)} onList={() => setListOpen(true)} />
      <BanterPanel />
      </div>
      {listOpen && <StageList onClose={() => setListOpen(false)} />}
    </div>
  );
}

function IdlePanel({ hours, gold, gems, fastLeft }: { hours: number; gold: number; gems: number; fastLeft: number }) {
  const claim = useGame((s) => s.claimIdle);
  const fast = useGame((s) => s.fastIdle);
  const notify = useGame((s) => s.notify);
  const h = Math.floor(hours);
  const m = Math.floor((hours - h) * 60);
  return (
    <Panel title="放置報酬" right={<span className="k-dim num">{h}時間{m}分 / {IDLE_CAP_HOURS}時間</span>}>
      <Bar value={hours} max={IDLE_CAP_HOURS} color="var(--k-kin)" height={6} />
      <div className="idle__row">
        <span className="idle__gain">
          <GoldIcon /> <span className="num">{gold.toLocaleString()}</span>
        </span>
        <span className="idle__gain">
          <GemIcon /> <span className="num">{gems}</span>
        </span>
        <div className="idle__btns">
          <Button
            size="sm"
            variant="ghost"
            disabled={fastLeft <= 0}
            onClick={() => {
              const r = fast();
              if (r.ok) notify(`高速放置：両 ${r.reward.gold.toLocaleString()}・花玉 ${r.reward.gems}`);
            }}
          >
            高速放置（{FAST_IDLE_HOURS}h）残{fastLeft}
          </Button>
          <Button
            size="sm"
            disabled={gold <= 0}
            onClick={() => {
              const r = claim();
              if (r.ok) notify(`両 ${r.reward.gold.toLocaleString()}・花玉 ${r.reward.gems} を受け取りました`);
            }}
          >
            受け取る
          </Button>
        </div>
      </div>
    </Panel>
  );
}

function StagePanel({ index, allClear, power, onList }: { index: number; allClear: boolean; power: number; onList: () => void }) {
  const st = STAGES[index];
  const ch = CHAPTERS[st.chapter - 1];
  const fight = useGame((s) => s.fightStage);
  const open = useNav((s) => s.open);
  return (
    <Panel title={`第${ch.no}章　${ch.title}`} right={<button className="k-link" onClick={onList}>ステージ一覧</button>}>
      <p className="k-dim stage__lead">{ch.lead}</p>
      <div className="stage__card">
        <div className="stage__id brush">{st.id}</div>
        <div className="stage__info">
          <div className="stage__name">
            {st.name}
            {st.boss && <span className="stage__boss">首領</span>}
          </div>
          <div className="k-dim num">
            推奨Lv {st.recommendedLevel}・編成戦力 {power.toLocaleString()}
          </div>
          <div className="stage__enemies">
            {st.enemies.map((e, i) => (e ? <EnemyPortrait key={i} id={e} className="stage__enemy" /> : null))}
          </div>
        </div>
      </div>
      <Button
        size="lg"
        variant="gold"
        className="stage__go"
        onClick={() => {
          const r = fight(index);
          if (r) open({ kind: "battle", view: { title: `${st.id} ${st.name}`, result: r.result, rewards: r.rewards } });
        }}
      >
        {allClear ? "再戦する" : "出陣"}
      </Button>
      {allClear && <p className="k-dim" style={{ textAlign: "center" }}>全ステージ踏破！ 続きは今後の更新で。</p>}
    </Panel>
  );
}

function StageList({ onClose }: { onClose: () => void }) {
  const save = useGame((s) => s.save);
  const fight = useGame((s) => s.fightStage);
  const open = useNav((s) => s.open);
  return (
    <Sheet title="ステージ一覧" onClose={onClose}>
      <ul className="stage-list">
        {STAGES.map((st) => {
          const locked = st.index > save.cleared;
          const cleared = st.index < save.cleared;
          return (
            <li key={st.id} className={`stage-list__item ${locked ? "is-locked" : ""}`}>
              <span className="brush stage-list__id">{st.id}</span>
              <span className="stage-list__name">
                {st.name}
                <span className="k-dim num"> 推奨Lv{st.recommendedLevel}</span>
              </span>
              {cleared && <span className="stage-list__done">済</span>}
              <Button
                size="sm"
                variant={cleared ? "ghost" : "primary"}
                disabled={locked}
                onClick={() => {
                  const r = fight(st.index);
                  if (r) open({ kind: "battle", view: { title: `${st.id} ${st.name}`, result: r.result, rewards: r.rewards } });
                }}
              >
                {locked ? "未解放" : cleared ? "再戦" : "出陣"}
              </Button>
            </li>
          );
        })}
      </ul>
    </Sheet>
  );
}
