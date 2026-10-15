import { useState } from "react";
import { SAVE_VERSION } from "../../core/game";
import { useGame } from "../../state/store";
import { useNav } from "../nav";
import { Panel } from "../components/Panel";
import { Button } from "../components/Button";
import { Modal } from "../components/Modal";
import { usePrefersReducedMotion } from "../hooks";

function Toggle({ label, desc, value, onChange }: { label: string; desc?: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="setting">
      <span className="setting__text">
        <span>{label}</span>
        {desc && <span className="k-dim">{desc}</span>}
      </span>
      <button role="switch" aria-checked={value} className={`k-switch ${value ? "is-on" : ""}`} onClick={() => onChange(!value)}>
        <span />
      </button>
    </div>
  );
}

export function Settings() {
  const settings = useGame((s) => s.save.settings);
  const update = useGame((s) => s.updateSettings);
  const reset = useGame((s) => s.reset);
  const notify = useGame((s) => s.notify);
  const close = useNav((s) => s.close);
  const go = useNav((s) => s.go);
  const reduced = usePrefersReducedMotion();
  const [confirm, setConfirm] = useState(false);

  return (
    <div className="overlay settings">
      <header className="overlay__bar">
        <button className="k-icon-btn" onClick={close} aria-label="戻る">
          ‹
        </button>
        <span className="brush">設定</span>
        <span />
      </header>
      <div className="screen">
        <Panel title="演出">
          <Toggle label="スキルカットイン" desc="奥義のときに帯と台詞を出します" value={settings.cutin} onChange={(v) => update({ cutin: v })} />
          <Toggle label="花結びの演出" desc="オフにすると結果をすぐ表示します" value={settings.gachaAnim} onChange={(v) => update({ gachaAnim: v })} />
          <div className="setting">
            <span className="setting__text">
              <span>戦闘速度</span>
              <span className="k-dim">×2以上ではカットインが短くなります</span>
            </span>
            <div className="k-tabs" style={{ margin: 0 }}>
              {([1, 2, 4] as const).map((s) => (
                <button key={s} className={`k-tab num ${settings.speed === s ? "is-active" : ""}`} onClick={() => update({ speed: s })}>
                  ×{s}
                </button>
              ))}
            </div>
          </div>
          {reduced && <p className="k-dim">端末の「視差効果を減らす」設定が有効なため、演出は簡略化されています。</p>}
        </Panel>
        <Panel title="データ">
          <p className="k-dim">セーブデータはこの端末のブラウザに保存されています（形式 v{SAVE_VERSION}）。</p>
          <Button variant="ghost" onClick={() => setConfirm(true)} style={{ width: "100%", borderColor: "var(--k-danger)", color: "var(--k-danger)" }}>
            データを初期化する
          </Button>
        </Panel>
        <Panel title="この作品について">
          <p className="k-dim" style={{ lineHeight: 1.7 }}>
            剣華録は架空の戦国「八洲」を舞台にした放置RPGの試作です。登場する人物・流派・地名はすべて架空のものです。課金機能はありません。
          </p>
        </Panel>
      </div>
      {confirm && (
        <Modal title="本当に初期化しますか？" onClose={() => setConfirm(false)}>
          <p style={{ textAlign: "center", lineHeight: 1.7 }}>剣華・花玉・進行状況がすべて消え、最初からになります。元には戻せません。</p>
          <div className="grow__btns">
            <Button variant="ghost" onClick={() => setConfirm(false)}>
              やめる
            </Button>
            <Button
              onClick={() => {
                reset();
                setConfirm(false);
                go("home");
                notify("データを初期化しました");
              }}
            >
              初期化する
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}
