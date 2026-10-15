import { useNav, type Tab } from "./nav";
import { ResourceBar } from "./components/Resources";
import { Toast } from "./components/Toast";
import { Home } from "./screens/Home";
import { Team } from "./screens/Team";
import { Chars } from "./screens/Chars";
import { CharDetail } from "./screens/CharDetail";
import { Gacha } from "./screens/Gacha";
import { Quest } from "./screens/Quest";
import { Battle } from "./screens/Battle";
import { Settings } from "./screens/Settings";
import "./theme/components.css";
import "./theme/screens.css";

const TABS: { id: Tab; label: string; glyph: string }[] = [
  { id: "home", label: "出陣", glyph: "陣" },
  { id: "team", label: "編成", glyph: "編" },
  { id: "chars", label: "剣華", glyph: "華" },
  { id: "gacha", label: "花結び", glyph: "結" },
  { id: "quest", label: "任務", glyph: "務" },
];

export function App() {
  const { tab, overlay, go, open } = useNav();
  return (
    <div className="app-frame">
      <header className="app-head">
        <div className="app-logo brush">剣華録</div>
        <div className="app-head__right">
          <ResourceBar />
          <button className="k-icon-btn app-gear" onClick={() => open({ kind: "settings" })} aria-label="設定">
            ⚙
          </button>
        </div>
      </header>
      <main className="app-main">
        {tab === "home" && <Home />}
        {tab === "team" && <Team />}
        {tab === "chars" && <Chars />}
        {tab === "gacha" && <Gacha />}
        {tab === "quest" && <Quest />}
      </main>
      <nav className="app-nav">
        {TABS.map((t) => (
          <button key={t.id} className={`app-nav__btn ${tab === t.id ? "is-active" : ""}`} onClick={() => go(t.id)}>
            <span className="app-nav__glyph brush">{t.glyph}</span>
            <span className="app-nav__label">{t.label}</span>
          </button>
        ))}
      </nav>
      {overlay?.kind === "char" && <CharDetail id={overlay.id} />}
      {overlay?.kind === "battle" && <Battle view={overlay.view} />}
      {overlay?.kind === "settings" && <Settings />}
      <Toast />
    </div>
  );
}
