import { useState } from "react";
import { CHAR_BY_ID } from "../../data/characters";
import { CURRENT_BANNER } from "../../data/banners";
import { PITY, RATE_SSR, RATE_UR, PICKUP_SHARE, type ResolvedPull } from "../../core/gacha";
import { PULL_COST_SINGLE, PULL_COST_TEN } from "../../core/economy";
import { useGame } from "../../state/store";
import { Panel } from "../components/Panel";
import { Button } from "../components/Button";
import { Portrait } from "../components/Portrait";
import { GemIcon, ShardIcon } from "../components/Resources";
import { Modal } from "../components/Modal";
import { rarityColor } from "../theme/tokens";

export function Gacha() {
  const save = useGame((s) => s.save);
  const pull = useGame((s) => s.pull);
  const [results, setResults] = useState<ResolvedPull[] | null>(null);
  const pickup = CHAR_BY_ID[CURRENT_BANNER.pickup];

  const doPull = (n: 1 | 10) => {
    const r = pull(n);
    if (r) setResults(r);
  };

  return (
    <div className="screen gacha">
      <Panel className="banner" style={{ ["--cc" as string]: pickup.color }}>
        <div className="banner__art">
          <Portrait id={pickup.id} crop="full" />
        </div>
        <div className="banner__text">
          <div className="banner__kind">花結び・ピックアップ</div>
          <h2 className="brush banner__title">{CURRENT_BANNER.title}</h2>
          <p>{CURRENT_BANNER.lead}</p>
          <p className="k-dim num">天井まで あと {PITY - save.pity} 回</p>
        </div>
      </Panel>
      <div className="gacha__btns">
        <Button variant="ghost" size="lg" disabled={save.gems < PULL_COST_SINGLE} onClick={() => doPull(1)}>
          一回結ぶ
          <small className="num">
            <GemIcon size={12} /> {PULL_COST_SINGLE}
          </small>
        </Button>
        <Button variant="gold" size="lg" disabled={save.gems < PULL_COST_TEN} onClick={() => doPull(10)}>
          十回結ぶ
          <small className="num">
            <GemIcon size={12} /> {PULL_COST_TEN}
          </small>
        </Button>
      </div>
      <Panel title="提供割合">
        <ul className="rates num">
          <li>
            <span style={{ color: rarityColor("UR") }}>UR</span> {(RATE_UR * 100).toFixed(0)}%（うちピックアップ {(PICKUP_SHARE * 100).toFixed(0)}%）
          </li>
          <li>
            <span style={{ color: rarityColor("SSR") }}>SSR</span> {(RATE_SSR * 100).toFixed(0)}%
          </li>
          <li>
            <span style={{ color: rarityColor("SR") }}>SR</span> {((1 - RATE_UR - RATE_SSR) * 100).toFixed(0)}%
          </li>
          <li>十回結ぶと SSR 以上が1人以上確定</li>
          <li>{PITY}回目までにURが出なければピックアップURが確定</li>
          <li>すでにいる剣華は花片10枚になります</li>
        </ul>
        <p className="k-dim">※ 課金は未実装です（花玉は遊んで貯まります）。</p>
      </Panel>
      {results && <PullResults results={results} onClose={() => setResults(null)} />}
    </div>
  );
}

export function PullResults({ results, onClose }: { results: ResolvedPull[]; onClose: () => void }) {
  return (
    <Modal title="花結びの結果" onClose={onClose}>
      <div className={`pull-grid pull-grid--${results.length === 1 ? 1 : 10}`}>
        {results.map((r, i) => {
          const c = CHAR_BY_ID[r.charId];
          return (
            <div key={i} className={`pull-item rarity-${r.rarity}`} style={{ ["--rc" as string]: rarityColor(r.rarity) }}>
              <Portrait id={r.charId} crop="bust" />
              <span className="pull-item__r">{r.rarity}</span>
              {r.isNew ? <span className="pull-item__new">NEW</span> : (
                <span className="pull-item__shard num">
                  <ShardIcon size={10} />+{r.shards}
                </span>
              )}
              <span className="pull-item__name">{c.given}</span>
            </div>
          );
        })}
      </div>
      <Button onClick={onClose} style={{ width: "100%", marginTop: 12 }}>
        閉じる
      </Button>
    </Modal>
  );
}
