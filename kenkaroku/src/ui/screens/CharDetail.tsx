import { CHAR_BY_ID, fullName } from "../../data/characters";
import { allyUnit } from "../../core/battle/setup";
import { bloomCost, bloomStageName, levelCap, levelUpCost, MAX_STAR } from "../../core/economy";
import { power } from "../../core/stats";
import { useGame } from "../../state/store";
import { useNav } from "../nav";
import { VOICES } from "../../data/voices";
import { Portrait } from "../components/Portrait";
import { BloomPips, ElementBadge, RarityBadge, RoleBadge } from "../components/Badges";
import { Button } from "../components/Button";
import { Panel } from "../components/Panel";
import { Bar } from "../components/Bar";
import { GoldIcon, ShardIcon } from "../components/Resources";

export function CharDetail({ id }: { id: string }) {
  const c = CHAR_BY_ID[id];
  const owned = useGame((s) => s.save.roster[id]);
  const gold = useGame((s) => s.save.gold);
  const levelUp = useGame((s) => s.levelUp);
  const bloom = useGame((s) => s.bloom);
  const close = useNav((s) => s.close);
  const open = useNav((s) => s.open);
  const roster = useGame((s) => s.save.roster);
  const v = VOICES[id];
  const voiceLines: [string, string][] = [
    ["編成", v.formation],
    ["スキル", v.skill],
    ["勝利", v.victory],
    ["敗北", v.defeat],
    ["開花", v.bloom],
    ...v.home.map((t, i): [string, string] => [`ホーム${i + 1}`, t]),
    ["朝", v.homeTime.morning],
    ["昼", v.homeTime.day],
    ["夜", v.homeTime.night],
  ];
  const stats = owned ? allyUnit(id, owned, 0).stats : null;
  const cap = owned ? levelCap(owned.star) : 40;
  const cost = owned ? levelUpCost(owned.level) : 0;
  const bCost = owned ? bloomCost(owned.star) : null;

  return (
    <div className="overlay char-detail" key={id} style={{ ["--cc" as string]: c.color }} ref={(el) => el?.scrollTo(0, 0)}>
      <header className="overlay__bar">
        <button className="k-icon-btn" onClick={close} aria-label="戻る">
          ‹
        </button>
        <span className="brush">{c.epithet}</span>
        <span />
      </header>
      <div className="char-detail__hero">
        <Portrait id={id} crop="full" dim={!owned} className="char-detail__art" />
        <div className="char-detail__name">
          <div className="char-detail__epithet">{c.epithet}</div>
          <h1 className="brush">{fullName(c)}</h1>
          <div className="char-detail__kana k-dim">{c.kana}</div>
          <div className="char-detail__badges">
            <RarityBadge rarity={c.rarity} />
            <ElementBadge element={c.element} />
            <RoleBadge role={c.role} />
          </div>
        </div>
      </div>

      <div className="screen">
        {owned && stats ? (
          <Panel title="育成" right={<span className="k-dim num">戦力 {power(stats).toLocaleString()}</span>}>
            <div className="grow__row">
              <span className="num grow__lv">
                Lv <b>{owned.level}</b> / {cap}
              </span>
              <span className="grow__cost num">
                <GoldIcon /> {cost.toLocaleString()}
              </span>
            </div>
            <div className="grow__btns">
              <Button disabled={owned.level >= cap || gold < cost} onClick={() => levelUp(id, 1)}>
                Lv+1
              </Button>
              <Button variant="ghost" disabled={owned.level >= cap || gold < cost} onClick={() => levelUp(id, 10)}>
                Lv+10
              </Button>
            </div>
            <div className="k-divider" />
            <div className="grow__row">
              <span>
                開花：<b>{bloomStageName(owned.star)}</b>
              </span>
              <BloomPips star={owned.star} />
            </div>
            <div className="grow__row">
              <span className="num grow__cost">
                <ShardIcon /> 花片 {owned.shards} / {bCost ?? "—"}
              </span>
              <Button
                variant="gold"
                size="sm"
                disabled={bCost === null || owned.shards < bCost || owned.star >= MAX_STAR}
                onClick={() => bloom(id)}
              >
                {owned.star >= MAX_STAR ? "満開" : "開花する"}
              </Button>
            </div>
            {bCost !== null && <Bar value={owned.shards} max={bCost} color="var(--k-shu)" height={4} />}
            <p className="k-dim grow__hint">開花するとレベル上限が20上がり、能力も伸びます。花片は被りや開花任務で手に入ります。</p>
            <div className="k-divider" />
            <dl className="stats">
              <div><dt>体力</dt><dd className="num">{stats.hp.toLocaleString()}</dd></div>
              <div><dt>攻撃</dt><dd className="num">{stats.atk.toLocaleString()}</dd></div>
              <div><dt>防御</dt><dd className="num">{stats.def.toLocaleString()}</dd></div>
              <div><dt>素早さ</dt><dd className="num">{stats.spd}</dd></div>
            </dl>
          </Panel>
        ) : (
          <Panel title="未加入">
            <p className="k-dim">花結びで出会うと仲間になります。</p>
          </Panel>
        )}

        <Panel title="人物">
          <p className="profile__text">{c.profile}</p>
          <dl className="profile">
            <div><dt>流派</dt><dd>{c.school}</dd></div>
            <div><dt>年頃</dt><dd>{c.age}</dd></div>
            <div><dt>性格</dt><dd>{c.personality}</dd></div>
            <div><dt>一人称</dt><dd>{c.firstPerson}</dd></div>
            <div><dt>好きなもの</dt><dd>{c.likes}</dd></div>
            <div><dt>苦手なもの</dt><dd>{c.dislikes}</dd></div>
            <div><dt>得物</dt><dd>{c.weapon}</dd></div>
            <div><dt>紋</dt><dd>{c.motifText}</dd></div>
          </dl>
          <p className="profile__quote">「{c.toneSample}」</p>
        </Panel>

        <Panel title="縁（えにし）">
          <ul className="relations">
            {c.relations.map((r) => {
              const rc = CHAR_BY_ID[r.id];
              return (
                <li key={r.id}>
                  <button className="relation" onClick={() => open({ kind: "char", id: r.id })}>
                    <span className="relation__face">
                      <Portrait id={r.id} crop="face" dim={!roster[r.id]} />
                    </span>
                    <span className="relation__text">
                      <b>{fullName(rc)}</b>
                      <span className="k-dim">{r.label}</span>
                    </span>
                    <span className="relation__go">›</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </Panel>

        <Panel title="台詞">
          <ul className="voices">
            {voiceLines.map(([label, text], i) => (
              <li key={i} className="voice">
                <button className="voice__play" disabled aria-label="ボイス再生（準備中）" title="ボイスは準備中です">
                  ▶
                </button>
                <span className="voice__label">{label}</span>
                <span className="voice__text">{owned || label === "編成" ? text : "？？？"}</span>
              </li>
            ))}
          </ul>
          {!owned && <p className="k-dim">仲間になると全ての台詞を読めます。</p>}
        </Panel>

        <Panel title="奥義">
          <div className="skill">
            <div className="skill__name brush">{c.skill.name}</div>
            <p>{c.skill.desc}</p>
            <p className="k-dim">気力が100たまると自動で発動します（通常攻撃+40・被弾+10）。</p>
          </div>
        </Panel>
      </div>
    </div>
  );
}
