import { useState, useEffect } from "react";

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
  normal:  { label:"快調",     emoji:"✅", color: T.normal,
    advice:"いい調子です!この生活リズムを続けましょう。" },
  delay:   { label:"便秘気味", emoji:"⚠️", color: T.delay,
    advice:"少し滞り気味。水分と食物繊維を意識して、体を動かしましょう。" },
  stop:    { label:"便秘",     emoji:"🚫", color: T.stop,
    advice:"4日以上出ていません。下のセルフケアを試し、つらい場合は受診も検討を。" },
  unknown: { label:"記録なし", emoji:"❓", color: T.unknown,
    advice:"まずは今日の状態を記録してみましょう。" },
};

// ブリストルスケール(便の形状の国際的な分類)
const BRISTOL = [
  { type:1, label:"コロコロ便", emoji:"🌰", note:"硬くて小さい塊。強い便秘のサイン", tone:"stop" },
  { type:2, label:"硬い便",     emoji:"🥜", note:"ソーセージ状だが硬い。便秘気味",   tone:"delay" },
  { type:3, label:"やや硬い便", emoji:"🌭", note:"表面にひび割れがある",             tone:"normal" },
  { type:4, label:"普通便",     emoji:"🍌", note:"なめらかなバナナ状。理想的!",      tone:"normal" },
  { type:5, label:"やや軟らかい便", emoji:"🥐", note:"半固形で境界がはっきり",       tone:"normal" },
  { type:6, label:"泥状便",     emoji:"🍮", note:"ふにゃふにゃで形が崩れる",         tone:"delay" },
  { type:7, label:"水様便",     emoji:"💧", note:"液体状。下痢",                     tone:"stop" },
];

// 便秘改善のための毎日の習慣
const HABITS = [
  { id:"water",     label:"水分をこまめに(1.5〜2L)", icon:"🚰" },
  { id:"fiber",     label:"食物繊維をとった(野菜・海藻・きのこ)", icon:"🥗" },
  { id:"fermented", label:"発酵食品をとった(ヨーグルト・納豆など)", icon:"🥣" },
  { id:"breakfast", label:"朝食を食べた", icon:"🍚" },
  { id:"exercise",  label:"体を動かした(散歩・ストレッチ)", icon:"🚶" },
  { id:"toilet",    label:"朝、トイレに座る時間をつくった", icon:"🚽" },
];

const TIPS = [
  { icon:"🌅", title:"朝のゴールデンタイムを逃さない",
    body:"起床後にコップ1杯の水を飲み、朝食をとると腸が大きく動きます(胃結腸反射)。便意がなくても毎朝トイレに座る習慣をつけましょう。" },
  { icon:"🥗", title:"食物繊維は2種類をバランスよく",
    body:"水溶性(海藻・オートミール・果物)は便を軟らかくし、不溶性(ごぼう・豆・きのこ)はかさを増やします。硬い便のときは水溶性を多めに。" },
  { icon:"🚶", title:"運動と「の」の字マッサージ",
    body:"1日20〜30分のウォーキングや、おへその周りを「の」の字にさするマッサージが腸のぜん動運動を助けます。" },
  { icon:"🧘", title:"がまんしない・いきみすぎない",
    body:"便意を我慢すると感覚が鈍り便秘が悪化します。トイレでは前かがみ(考える人のポーズ)+足台で膝を上げると出やすくなります。" },
  { icon:"😴", title:"睡眠とストレスケア",
    body:"腸は自律神経に大きく影響されます。睡眠不足やストレスが続くと腸の動きが乱れるため、休息も便秘改善の一部です。" },
];

const STORAGE_KEY = "benpi-monitor-v1";

const todayKey = (d = new Date()) =>
  `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;

const fmtDate = (key) => {
  const [y,m,d] = key.split("-").map(Number);
  const day = ["日","月","火","水","木","金","土"][new Date(y, m-1, d).getDay()];
  return `${m}/${d}(${day})`;
};

const daysBetween = (fromKey, toKey) => {
  const [fy,fm,fd] = fromKey.split("-").map(Number);
  const [ty,tm,td] = toKey.split("-").map(Number);
  return Math.round((new Date(ty,tm-1,td) - new Date(fy,fm-1,fd)) / 86400000);
};

const load = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* 壊れたデータは初期化する */ }
  return { records: [], habits: {} };
};

function statusOf(records) {
  if (records.length === 0) return "unknown";
  const last = records[records.length - 1];
  const days = daysBetween(last.date, todayKey());
  if (days >= 4) return "stop";
  if (days >= 2) return "delay";
  const recent = records.slice(-3);
  if (recent.every(r => r.bristol <= 2)) return "delay";
  return "normal";
}

function Card({ children, style }) {
  return (
    <div style={{
      background: T.surface, borderRadius: T.r.lg, boxShadow: T.shadow,
      border: `1px solid ${T.outline}`, padding: "20px", ...style,
    }}>
      {children}
    </div>
  );
}

function SectionTitle({ icon, children }) {
  return (
    <div style={{ display:"flex", alignItems:"center", gap:"8px", marginBottom:"14px" }}>
      <span style={{ fontSize:"18px" }}>{icon}</span>
      <h2 style={{ margin:0, fontSize:"15px", fontWeight:700, color:T.onSurface }}>{children}</h2>
    </div>
  );
}

function StatusCard({ records }) {
  const key = statusOf(records);
  const s = STATUS[key];
  const last = records[records.length - 1];
  const days = last ? daysBetween(last.date, todayKey()) : null;
  return (
    <Card style={{ background:s.color.bg, border:`1px solid ${s.color.border}` }}>
      <div style={{ display:"flex", alignItems:"center", gap:"14px" }}>
        <div style={{ fontSize:"40px" }}>{s.emoji}</div>
        <div style={{ flex:1 }}>
          <div style={{ display:"flex", alignItems:"baseline", gap:"10px", flexWrap:"wrap" }}>
            <span style={{ fontSize:"22px", fontWeight:800, color:s.color.text }}>{s.label}</span>
            {days !== null && (
              <span style={{
                fontSize:"12px", fontWeight:600, color:s.color.text,
                background:s.color.badge, borderRadius:T.r.full, padding:"3px 10px",
              }}>
                {days === 0 ? "今日出ました" : `最後の排便から ${days} 日`}
              </span>
            )}
          </div>
          <p style={{ margin:"6px 0 0", fontSize:"13px", lineHeight:1.6, color:T.onSurfaceMed }}>
            {s.advice}
          </p>
        </div>
      </div>
    </Card>
  );
}

function WeekStrip({ records }) {
  const days = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    days.push(todayKey(d));
  }
  return (
    <Card>
      <SectionTitle icon="📅">この1週間</SectionTitle>
      <div style={{ display:"flex", gap:"6px" }}>
        {days.map(key => {
          const dayRecords = records.filter(r => r.date === key);
          const has = dayRecords.length > 0;
          const tone = has ? BRISTOL[dayRecords[dayRecords.length-1].bristol - 1].tone : "unknown";
          const c = T[tone];
          return (
            <div key={key} style={{ flex:1, textAlign:"center" }}>
              <div style={{ fontSize:"11px", color:T.onSurfaceLow, marginBottom:"6px" }}>
                {fmtDate(key)}
              </div>
              <div style={{
                height:"44px", borderRadius:T.r.sm, display:"flex", alignItems:"center",
                justifyContent:"center", fontSize:"18px",
                background: has ? c.bg : T.surfaceVar,
                border:`1px solid ${has ? c.border : T.outline}`,
              }}>
                {has ? "💩" : "–"}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function RecordForm({ onAdd }) {
  const [bristol, setBristol] = useState(4);
  const [memo, setMemo] = useState("");
  const selected = BRISTOL[bristol - 1];
  return (
    <Card>
      <SectionTitle icon="✏️">排便を記録する</SectionTitle>
      <div style={{ display:"flex", gap:"6px", marginBottom:"10px" }}>
        {BRISTOL.map(b => (
          <button key={b.type} onClick={() => setBristol(b.type)}
            title={`タイプ${b.type} ${b.label}`}
            style={{
              flex:1, padding:"10px 0", borderRadius:T.r.sm, cursor:"pointer",
              fontSize:"18px", lineHeight:1,
              background: bristol === b.type ? T.primaryLight : T.surfaceVar,
              border: `2px solid ${bristol === b.type ? T.primary : T.outline}`,
            }}>
            <div>{b.emoji}</div>
            <div style={{ fontSize:"10px", marginTop:"4px", color:T.onSurfaceMed }}>
              {b.type}
            </div>
          </button>
        ))}
      </div>
      <p style={{ margin:"0 0 12px", fontSize:"12px", color:T.onSurfaceMed }}>
        タイプ{selected.type}:{selected.label} — {selected.note}
      </p>
      <input value={memo} onChange={e => setMemo(e.target.value)}
        placeholder="メモ(任意):お腹の張り、残便感など"
        style={{
          width:"100%", boxSizing:"border-box", padding:"10px 12px", fontSize:"13px",
          borderRadius:T.r.sm, border:`1px solid ${T.outline}`, marginBottom:"12px",
          outline:"none", color:T.onSurface, background:T.surface,
        }} />
      <button onClick={() => { onAdd(bristol, memo.trim()); setMemo(""); setBristol(4); }}
        style={{
          width:"100%", padding:"12px", borderRadius:T.r.md, border:"none",
          background:T.primary, color:"#fff", fontSize:"15px", fontWeight:700,
          cursor:"pointer", boxShadow:T.shadowMd,
        }}>
        💩 今日の分を記録
      </button>
    </Card>
  );
}

function HabitList({ habits, onToggle }) {
  const done = HABITS.filter(h => habits[h.id]).length;
  return (
    <Card>
      <SectionTitle icon="🌱">今日の腸活チェック({done}/{HABITS.length})</SectionTitle>
      <div style={{ display:"flex", flexDirection:"column", gap:"8px" }}>
        {HABITS.map(h => {
          const on = !!habits[h.id];
          return (
            <button key={h.id} onClick={() => onToggle(h.id)}
              style={{
                display:"flex", alignItems:"center", gap:"10px", padding:"10px 12px",
                borderRadius:T.r.sm, cursor:"pointer", textAlign:"left", fontSize:"13px",
                background: on ? T.normal.bg : T.surfaceVar,
                border:`1px solid ${on ? T.normal.border : T.outline}`,
                color: on ? T.normal.text : T.onSurfaceMed,
                fontWeight: on ? 600 : 400,
              }}>
              <span style={{ fontSize:"16px" }}>{on ? "✅" : h.icon}</span>
              <span style={{ textDecoration: on ? "line-through" : "none" }}>{h.label}</span>
            </button>
          );
        })}
      </div>
    </Card>
  );
}

function History({ records, onDelete }) {
  if (records.length === 0) return null;
  return (
    <Card>
      <SectionTitle icon="📖">記録履歴</SectionTitle>
      <div style={{ display:"flex", flexDirection:"column", gap:"8px" }}>
        {[...records].reverse().slice(0, 14).map(r => {
          const b = BRISTOL[r.bristol - 1];
          const c = T[b.tone];
          return (
            <div key={r.id} style={{
              display:"flex", alignItems:"center", gap:"10px", padding:"10px 12px",
              borderRadius:T.r.sm, background:T.surfaceVar, border:`1px solid ${T.outline}`,
            }}>
              <span style={{ fontSize:"18px" }}>{b.emoji}</span>
              <div style={{ flex:1, minWidth:0 }}>
                <div style={{ fontSize:"13px", fontWeight:600, color:T.onSurface }}>
                  {fmtDate(r.date)}{" "}
                  <span style={{
                    fontSize:"11px", fontWeight:600, color:c.text, background:c.badge,
                    borderRadius:T.r.full, padding:"2px 8px", marginLeft:"4px",
                  }}>
                    タイプ{r.bristol} {b.label}
                  </span>
                </div>
                {r.memo && (
                  <div style={{ fontSize:"12px", color:T.onSurfaceMed, marginTop:"2px" }}>
                    {r.memo}
                  </div>
                )}
              </div>
              <button onClick={() => onDelete(r.id)} title="削除"
                style={{
                  border:"none", background:"none", cursor:"pointer",
                  color:T.onSurfaceLow, fontSize:"14px", padding:"4px",
                }}>
                ✕
              </button>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function Tips() {
  return (
    <Card>
      <SectionTitle icon="💡">便秘改善のヒント</SectionTitle>
      <div style={{ display:"flex", flexDirection:"column", gap:"14px" }}>
        {TIPS.map(t => (
          <div key={t.title} style={{ display:"flex", gap:"10px" }}>
            <span style={{ fontSize:"18px" }}>{t.icon}</span>
            <div>
              <div style={{ fontSize:"13px", fontWeight:700, color:T.onSurface }}>{t.title}</div>
              <p style={{ margin:"4px 0 0", fontSize:"12.5px", lineHeight:1.7, color:T.onSurfaceMed }}>
                {t.body}
              </p>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

export default function App() {
  const [data, setData] = useState(load);
  const today = todayKey();

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  }, [data]);

  const addRecord = (bristol, memo) =>
    setData(d => ({
      ...d,
      records: [...d.records, { id: `${Date.now()}`, date: today, bristol, memo }],
    }));

  const deleteRecord = (id) =>
    setData(d => ({ ...d, records: d.records.filter(r => r.id !== id) }));

  const toggleHabit = (habitId) =>
    setData(d => {
      const dayHabits = { ...(d.habits[today] || {}) };
      dayHabits[habitId] = !dayHabits[habitId];
      return { ...d, habits: { ...d.habits, [today]: dayHabits } };
    });

  return (
    <div style={{
      minHeight:"100vh", background:T.surfaceVar, color:T.onSurface,
      fontFamily:`"Hiragino Sans","Hiragino Kaku Gothic ProN","Noto Sans JP",Meiryo,sans-serif`,
      padding:"20px 16px 40px",
    }}>
      <div style={{ maxWidth:"560px", margin:"0 auto", display:"flex", flexDirection:"column", gap:"16px" }}>
        <header style={{ textAlign:"center", padding:"8px 0 4px" }}>
          <h1 style={{ margin:0, fontSize:"22px", fontWeight:800 }}>💩 べんぴモニター</h1>
          <p style={{ margin:"6px 0 0", fontSize:"12.5px", color:T.onSurfaceMed }}>
            毎日の記録と腸活習慣で、便秘をコツコツ改善
          </p>
        </header>

        <StatusCard records={data.records} />
        <WeekStrip records={data.records} />
        <RecordForm onAdd={addRecord} />
        <HabitList habits={data.habits[today] || {}} onToggle={toggleHabit} />
        <History records={data.records} onDelete={deleteRecord} />
        <Tips />

        <footer style={{
          fontSize:"11.5px", lineHeight:1.7, color:T.onSurfaceLow, textAlign:"center",
          padding:"8px 12px 0",
        }}>
          ⚠️ 本アプリは医療機器ではなく、セルフケアの記録を目的としています。
          血便・激しい腹痛・急な体重減少・便秘が長く続く場合は、医療機関を受診してください。
        </footer>
      </div>
    </div>
  );
}
