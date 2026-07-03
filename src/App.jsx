import { useState, useEffect, useRef } from "react";
import Anthropic from "@anthropic-ai/sdk";

const T = {
  primary:      "#1A56DB",
  primaryLight: "#EEF3FF",
  surface:      "#FFFFFF",
  surfaceVar:   "#F4F6FB",
  outline:      "#E2E8F0",
  onSurface:    "#0F172A",
  onSurfaceMed: "#475569",
  onSurfaceLow: "#94A3B8",
  normal:  { bg:"#ECFDF5", text:"#059669", border:"#A7F3D0", badge:"#D1FAE5" },
  delay:   { bg:"#FFFBEB", text:"#D97706", border:"#FDE68A", badge:"#FEF3C7" },
  stop:    { bg:"#FFF1F2", text:"#E11D48", border:"#FECDD3", badge:"#FFE4E6" },
  unknown: { bg:"#F8FAFC", text:"#64748B", border:"#E2E8F0", badge:"#F1F5F9" },
  shadow:   "0 1px 3px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.05)",
  shadowMd: "0 2px 8px rgba(0,0,0,0.09), 0 8px 24px rgba(0,0,0,0.07)",
  r: { sm:"8px", md:"14px", lg:"18px", xl:"24px", full:"999px" },
};

const STATUS = {
  normal:  { label:"平常運転",     emoji:"✅", color: T.normal  },
  delay:   { label:"遅　延",       emoji:"⚠️", color: T.delay   },
  stop:    { label:"運転見合わせ", emoji:"🚫", color: T.stop    },
  unknown: { label:"情報なし",     emoji:"❓", color: T.unknown },
};

const AGENTS = [
  { id:"official", label:"公式情報",    icon:"🏢", accent:"#1A56DB",
    prompt: l=>`「${l}」の現在の運行状況を公式サイトやYahoo!乗換案内で調べてください。` },
  { id:"news",     label:"ニュース",     icon:"📰", accent:"#7C3AED",
    prompt: l=>`「${l}」の遅延・運休に関する最新ニュースを調べてください。` },
  { id:"realtime", label:"リアルタイム", icon:"📡", accent:"#0891B2",
    prompt: l=>`「${l}」の今この瞬間の遅延状況を最新情報で調べてください。` },
  { id:"related",  label:"接続路線",     icon:"🔗", accent:"#DC2626",
    prompt: l=>`「${l}」と接続する路線への遅延波及影響を調べてください。` },
];

const SYSTEM_PROMPT = `あなたは日本の鉄道遅延情報を収集する専門エージェントです。
ウェブ検索で最新の運行情報を調べて、必ず以下のJSON形式だけで回答してください。余分なテキスト不要。
{
  "status": "normal"|"delay"|"stop"|"unknown",
  "delayMinutes": 数値またはnull,
  "affectedSection": "影響区間またはnull",
  "cause": "原因またはnull",
  "detail": "1〜3文の詳細説明",
  "sources": ["参照した情報源の名前"]
}
確実な情報が見つからない場合は status を "unknown" にしてください。`;

const MODEL = "claude-opus-4-8";

function parseAgentJson(text) {
  const start = text.indexOf("{");
  const end = text.lastIndexOf("}");
  if (start === -1 || end <= start) return null;
  try {
    const data = JSON.parse(text.slice(start, end + 1));
    if (!STATUS[data.status]) data.status = "unknown";
    return data;
  } catch {
    return null;
  }
}

async function queryAgent(apiKey, agent, line) {
  const client = new Anthropic({ apiKey, dangerouslyAllowBrowser: true });
  const response = await client.messages.create({
    model: MODEL,
    max_tokens: 4096,
    thinking: { type: "adaptive" },
    system: SYSTEM_PROMPT,
    tools: [{ type: "web_search_20260209", name: "web_search", max_uses: 3 }],
    messages: [{ role: "user", content: agent.prompt(line) }],
  });
  if (response.stop_reason === "refusal") {
    throw new Error("リクエストが拒否されました");
  }
  const text = response.content
    .filter(b => b.type === "text")
    .map(b => b.text)
    .join("\n");
  const data = parseAgentJson(text);
  if (!data) throw new Error("応答の解析に失敗しました");
  return data;
}

// 総合判定: 各エージェントの結果のうち最も深刻なものを採用
const SEVERITY = { stop: 3, delay: 2, normal: 1, unknown: 0 };
function overallStatus(results) {
  let worst = "unknown";
  for (const r of Object.values(results)) {
    if (r.data && SEVERITY[r.data.status] > SEVERITY[worst]) worst = r.data.status;
  }
  return worst;
}

function StatusBadge({ status, size = "md" }) {
  const s = STATUS[status] ?? STATUS.unknown;
  const pad = size === "lg" ? "10px 22px" : "4px 12px";
  const font = size === "lg" ? "20px" : "13px";
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: "6px",
      padding: pad, borderRadius: T.r.full, fontSize: font, fontWeight: 700,
      background: s.color.badge, color: s.color.text, border: `1px solid ${s.color.border}`,
    }}>
      <span>{s.emoji}</span>{s.label}
    </span>
  );
}

function AgentCard({ agent, result }) {
  const { loading, data, error } = result ?? {};
  return (
    <div style={{
      background: T.surface, borderRadius: T.r.lg, boxShadow: T.shadow,
      border: `1px solid ${T.outline}`, padding: "18px",
      borderTop: `3px solid ${agent.accent}`,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "10px" }}>
        <span style={{ fontSize: "18px" }}>{agent.icon}</span>
        <span style={{ fontWeight: 700, color: T.onSurface, fontSize: "15px" }}>{agent.label}</span>
        <span style={{ marginLeft: "auto" }}>
          {loading ? (
            <span style={{ fontSize: "12px", color: T.onSurfaceLow }}>調査中…</span>
          ) : data ? (
            <StatusBadge status={data.status} />
          ) : error ? (
            <span style={{ fontSize: "12px", color: T.stop.text }}>エラー</span>
          ) : null}
        </span>
      </div>
      {loading && (
        <div style={{ height: "8px", borderRadius: T.r.full, background: T.surfaceVar, overflow: "hidden" }}>
          <div className="chien-progress" style={{ height: "100%", width: "40%", background: agent.accent, borderRadius: T.r.full }} />
        </div>
      )}
      {error && <p style={{ fontSize: "13px", color: T.onSurfaceMed, margin: 0 }}>{error}</p>}
      {data && (
        <div style={{ fontSize: "13px", color: T.onSurfaceMed, lineHeight: 1.7 }}>
          {data.delayMinutes != null && <div>遅延時間: 約{data.delayMinutes}分</div>}
          {data.affectedSection && <div>影響区間: {data.affectedSection}</div>}
          {data.cause && <div>原因: {data.cause}</div>}
          <div style={{ marginTop: "4px" }}>{data.detail}</div>
          {Array.isArray(data.sources) && data.sources.length > 0 && (
            <div style={{ marginTop: "6px", fontSize: "11px", color: T.onSurfaceLow }}>
              情報源: {data.sources.join("、")}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [apiKey, setApiKey] = useState(() => localStorage.getItem("chien_api_key") ?? "");
  const [line, setLine] = useState("");
  const [results, setResults] = useState({});
  const [running, setRunning] = useState(false);
  const [checkedAt, setCheckedAt] = useState(null);
  const runIdRef = useRef(0);

  useEffect(() => {
    localStorage.setItem("chien_api_key", apiKey);
  }, [apiKey]);

  const check = async () => {
    const l = line.trim();
    if (!l || !apiKey.trim() || running) return;
    const runId = ++runIdRef.current;
    setRunning(true);
    setCheckedAt(null);
    setResults(Object.fromEntries(AGENTS.map(a => [a.id, { loading: true }])));
    await Promise.all(AGENTS.map(async agent => {
      let entry;
      try {
        entry = { data: await queryAgent(apiKey.trim(), agent, l) };
      } catch (e) {
        entry = { error: e?.message ?? "取得に失敗しました" };
      }
      if (runIdRef.current === runId) {
        setResults(prev => ({ ...prev, [agent.id]: entry }));
      }
    }));
    if (runIdRef.current === runId) {
      setRunning(false);
      setCheckedAt(new Date());
    }
  };

  const hasResults = Object.values(results).some(r => r.data || r.error);
  const overall = overallStatus(results);

  return (
    <div style={{
      minHeight: "100vh", background: T.surfaceVar, color: T.onSurface,
      fontFamily: "'Hiragino Sans', 'Noto Sans JP', system-ui, sans-serif",
      padding: "24px 16px",
    }}>
      <style>{`
        @keyframes chienSlide { 0% { margin-left: -40%; } 100% { margin-left: 100%; } }
        .chien-progress { animation: chienSlide 1.2s ease-in-out infinite; }
      `}</style>
      <div style={{ maxWidth: "680px", margin: "0 auto" }}>
        <header style={{ textAlign: "center", marginBottom: "24px" }}>
          <h1 style={{ fontSize: "24px", fontWeight: 800, margin: "0 0 4px" }}>🚃 遅延モニター</h1>
          <p style={{ fontSize: "13px", color: T.onSurfaceMed, margin: 0 }}>
            4つのエージェントが並行して路線の運行状況を調査します
          </p>
        </header>

        <div style={{
          background: T.surface, borderRadius: T.r.xl, boxShadow: T.shadowMd,
          border: `1px solid ${T.outline}`, padding: "20px", marginBottom: "20px",
        }}>
          <label style={{ display: "block", fontSize: "12px", fontWeight: 700, color: T.onSurfaceMed, marginBottom: "6px" }}>
            Anthropic APIキー(この端末にのみ保存されます)
          </label>
          <input
            type="password"
            value={apiKey}
            onChange={e => setApiKey(e.target.value)}
            placeholder="sk-ant-..."
            style={{
              width: "100%", boxSizing: "border-box", padding: "10px 14px",
              borderRadius: T.r.sm, border: `1px solid ${T.outline}`,
              fontSize: "14px", marginBottom: "14px", outline: "none",
            }}
          />
          <label style={{ display: "block", fontSize: "12px", fontWeight: 700, color: T.onSurfaceMed, marginBottom: "6px" }}>
            路線名
          </label>
          <div style={{ display: "flex", gap: "10px" }}>
            <input
              value={line}
              onChange={e => setLine(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") check(); }}
              placeholder="例: 山手線、東海道新幹線"
              style={{
                flex: 1, padding: "10px 14px", borderRadius: T.r.sm,
                border: `1px solid ${T.outline}`, fontSize: "14px", outline: "none",
              }}
            />
            <button
              onClick={check}
              disabled={running || !line.trim() || !apiKey.trim()}
              style={{
                padding: "10px 24px", borderRadius: T.r.sm, border: "none",
                background: running || !line.trim() || !apiKey.trim() ? T.onSurfaceLow : T.primary,
                color: "#fff", fontSize: "14px", fontWeight: 700,
                cursor: running || !line.trim() || !apiKey.trim() ? "default" : "pointer",
              }}
            >
              {running ? "調査中…" : "調べる"}
            </button>
          </div>
        </div>

        {hasResults && (
          <div style={{
            background: STATUS[overall].color.bg, border: `1px solid ${STATUS[overall].color.border}`,
            borderRadius: T.r.xl, padding: "20px", textAlign: "center", marginBottom: "20px",
          }}>
            <div style={{ fontSize: "12px", fontWeight: 700, color: T.onSurfaceMed, marginBottom: "8px" }}>
              総合判定{checkedAt && ` — ${checkedAt.toLocaleTimeString("ja-JP")} 時点`}
            </div>
            <StatusBadge status={overall} size="lg" />
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "14px" }}>
          {AGENTS.map(agent => (
            <AgentCard key={agent.id} agent={agent} result={results[agent.id]} />
          ))}
        </div>

        <footer style={{ textAlign: "center", marginTop: "28px", fontSize: "11px", color: T.onSurfaceLow }}>
          運行情報はAIによるウェブ検索結果です。正確な情報は各鉄道会社の公式発表をご確認ください。
        </footer>
      </div>
    </div>
  );
}
