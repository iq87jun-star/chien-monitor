import { useMemo, useState } from "react";

// ---- テーマ(既存アプリと同系統のトーン) ----
const T = {
  primary:      "#1A56DB",
  primaryLight: "#EEF3FF",
  surface:      "#FFFFFF",
  surfaceVar:   "#F4F6FB",
  outline:      "#E2E8F0",
  onSurface:    "#0F172A",
  onSurfaceMed: "#475569",
  onSurfaceLow: "#94A3B8",
  green:  { bg:"#ECFDF5", text:"#059669", border:"#A7F3D0" },
  amber:  { bg:"#FFFBEB", text:"#D97706", border:"#FDE68A" },
  red:    { bg:"#FFF1F2", text:"#E11D48", border:"#FECDD3" },
  shadow:   "0 1px 3px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.05)",
  r: { sm:"8px", md:"14px", lg:"18px", full:"999px" },
};

// ---- METs定数 ----
const BIKE_OPTIONS = [
  { id:"slow",   label:"のんびり (~15 km/h)",  speed:15, met:5.8 },
  { id:"normal", label:"普通 (16〜19 km/h)",   speed:17.5, met:6.8 },
  { id:"fast",   label:"速め (19〜22 km/h)",   speed:20.5, met:8.0 },
];
const STAND_OPTIONS = [
  { id:"light",  label:"ほぼ立ちっぱなし(軽作業)", met:2.0 },
  { id:"mid",    label:"立ち仕事+ときどき歩く",     met:2.5 },
  { id:"active", label:"よく動き回る立ち仕事",       met:3.0 },
];
const SAUNA_MET = 1.5;      // 座位安静よりやや高い程度
const SLEEP_HOURS = 7;      // 睡眠
const MISC_MET = 1.5;       // その他の生活活動(家事・移動など)
const FAT_KCAL_PER_KG = 7200;

// Mifflin-St Jeor 基礎代謝
function bmrOf({ weight, height, age, sex }) {
  const base = 10 * weight + 6.25 * height - 5 * age;
  return sex === "male" ? base + 5 : base - 161;
}

// 運動の追加消費(安静分を除いた正味): (METs - 1) × 体重kg × 時間 × 1.05
const netKcal = (met, weight, hours) => Math.max(0, (met - 1) * weight * hours * 1.05);

const num = (v, fallback = 0) => {
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : fallback;
};
const fmt = (n) => Math.round(n).toLocaleString("ja-JP");

export default function CalorieCalculator() {
  // ---- プロフィール ----
  const [weight, setWeight] = useState("86");
  const [height, setHeight] = useState("176");
  const [age, setAge]       = useState("40");
  const [sex, setSex]       = useState("male");

  // ---- 通常の生活パターン(変化があれば調整) ----
  const [bikeKm, setBikeKm]     = useState("15");   // 自転車通勤 15km/日
  const [bikePace, setBikePace] = useState("normal");
  const [standH, setStandH]     = useState("10.5"); // 立ち仕事 10.5時間
  const [standType, setStandType] = useState("mid");
  const [workDays, setWorkDays] = useState("22");   // 勤務日数/月
  const [monthDays, setMonthDays] = useState("30");

  // ---- サウナ(趣味) ----
  const [saunaPerMonth, setSaunaPerMonth] = useState("4");
  const [saunaMin, setSaunaMin]           = useState("60");

  // ---- 摂取(食事2回: スクショから推定したkcalを入力) ----
  const [meal1, setMeal1] = useState("");
  const [meal2, setMeal2] = useState("");

  const calc = useMemo(() => {
    const w = num(weight, 70);
    const profile = { weight: w, height: num(height, 170), age: num(age, 40), sex };
    const bmr = bmrOf(profile);

    const bike = BIKE_OPTIONS.find(o => o.id === bikePace) ?? BIKE_OPTIONS[1];
    const stand = STAND_OPTIONS.find(o => o.id === standType) ?? STAND_OPTIONS[1];

    const bikeHours = num(bikeKm, 0) / bike.speed;
    const bikeKcal  = netKcal(bike.met, w, bikeHours);
    const standKcal = netKcal(stand.met, w, num(standH, 0));

    // 勤務日: 睡眠・仕事・通勤以外の残り時間は軽い生活活動として加算
    const miscHours = Math.max(0, 24 - SLEEP_HOURS - num(standH, 0) - bikeHours);
    const miscKcal  = netKcal(MISC_MET, w, miscHours);

    const workdayTotal = bmr + bikeKcal + standKcal + miscKcal;

    // 休日: 軽い活動レベル(BMR × 1.4)で概算
    const offdayTotal = bmr * 1.4;

    const saunaPerSession = netKcal(SAUNA_MET, w, num(saunaMin, 0) / 60);
    const saunaMonth = saunaPerSession * num(saunaPerMonth, 0);

    const wd = num(workDays, 22);
    const md = num(monthDays, 30);
    const offDays = Math.max(0, md - wd);
    const monthlyBurn = workdayTotal * wd + offdayTotal * offDays + saunaMonth;

    const dailyIntake = num(meal1, 0) + num(meal2, 0);
    const monthlyIntake = dailyIntake * md;
    const balance = monthlyIntake - monthlyBurn; // マイナス = 減量方向

    return {
      bmr, bike, stand, bikeHours, bikeKcal, standKcal, miscHours, miscKcal,
      workdayTotal, offdayTotal, saunaPerSession, saunaMonth,
      wd, offDays, md, monthlyBurn, dailyIntake, monthlyIntake, balance,
    };
  }, [weight, height, age, sex, bikeKm, bikePace, standH, standType,
      workDays, monthDays, saunaPerMonth, saunaMin, meal1, meal2]);

  const hasIntake = calc.dailyIntake > 0;
  const balanceColor = calc.balance <= 0 ? T.green : T.amber;

  return (
    <div style={{ minHeight:"100vh", background:T.surfaceVar, color:T.onSurface,
      fontFamily:'"Hiragino Sans","Yu Gothic UI",system-ui,sans-serif', padding:"24px 16px" }}>
      <div style={{ maxWidth:720, margin:"0 auto", display:"flex", flexDirection:"column", gap:16 }}>

        <header style={{ textAlign:"center", padding:"8px 0" }}>
          <h1 style={{ margin:0, fontSize:24 }}>🔥 月間消費カロリー計算</h1>
          <p style={{ margin:"6px 0 0", color:T.onSurfaceMed, fontSize:13 }}>
            自転車通勤15km・立ち仕事10.5hを通常パターンとして月間の消費カロリーを概算します
          </p>
        </header>

        {/* プロフィール */}
        <Card title="👤 プロフィール">
          <Row>
            <Field label="体重 (kg)"><Input value={weight} onChange={setWeight} /></Field>
            <Field label="身長 (cm)"><Input value={height} onChange={setHeight} /></Field>
            <Field label="年齢"><Input value={age} onChange={setAge} /></Field>
            <Field label="性別">
              <Select value={sex} onChange={setSex}
                options={[{value:"male",label:"男性"},{value:"female",label:"女性"}]} />
            </Field>
          </Row>
          <Note>基礎代謝(Mifflin-St Jeor式): <b>{fmt(calc.bmr)} kcal/日</b></Note>
        </Card>

        {/* 通常の運動 */}
        <Card title="🚴 通常の1日(勤務日)">
          <Row>
            <Field label="自転車通勤 (km/日)"><Input value={bikeKm} onChange={setBikeKm} /></Field>
            <Field label="ペース">
              <Select value={bikePace} onChange={setBikePace}
                options={BIKE_OPTIONS.map(o=>({value:o.id,label:o.label}))} />
            </Field>
          </Row>
          <Row>
            <Field label="立ち仕事 (時間/日)"><Input value={standH} onChange={setStandH} /></Field>
            <Field label="仕事の内容">
              <Select value={standType} onChange={setStandType}
                options={STAND_OPTIONS.map(o=>({value:o.id,label:o.label}))} />
            </Field>
          </Row>
          <Row>
            <Field label="勤務日数 (日/月)"><Input value={workDays} onChange={setWorkDays} /></Field>
            <Field label="月の日数"><Input value={monthDays} onChange={setMonthDays} /></Field>
          </Row>
        </Card>

        {/* サウナ */}
        <Card title="🧖 サウナ(趣味)">
          <Row>
            <Field label="回数 (回/月)"><Input value={saunaPerMonth} onChange={setSaunaPerMonth} /></Field>
            <Field label="1回あたり (分)"><Input value={saunaMin} onChange={setSaunaMin} /></Field>
          </Row>
          <Note>
            1回あたり約 <b>{fmt(calc.saunaPerSession)} kcal</b>。
            サウナ直後の体重減はほぼ水分です(脂肪燃焼は控えめに見積もっています)。
          </Note>
        </Card>

        {/* 食事 */}
        <Card title="🍽 食事(2回/日)">
          <Row>
            <Field label="食事1 (kcal)"><Input value={meal1} onChange={setMeal1} placeholder="スクショから推定した値" /></Field>
            <Field label="食事2 (kcal)"><Input value={meal2} onChange={setMeal2} placeholder="スクショから推定した値" /></Field>
          </Row>
          <Note>食事のスクショをチャットに送ってもらえれば、推定カロリーを算出してここに入力できます。</Note>
        </Card>

        {/* 結果 */}
        <Card title="📊 計算結果" accent>
          <table style={{ width:"100%", borderCollapse:"collapse", fontSize:14 }}>
            <tbody>
              <Tr label={`自転車 ${bikeLabel(calc)} (追加消費)`} value={`${fmt(calc.bikeKcal)} kcal/日`} />
              <Tr label={`立ち仕事 ${standH}h (追加消費)`} value={`${fmt(calc.standKcal)} kcal/日`} />
              <Tr label={`その他の生活活動 約${calc.miscHours.toFixed(1)}h`} value={`${fmt(calc.miscKcal)} kcal/日`} />
              <Tr label="基礎代謝" value={`${fmt(calc.bmr)} kcal/日`} />
              <Tr label="勤務日の合計" value={`${fmt(calc.workdayTotal)} kcal/日`} strong />
              <Tr label="休日の合計 (概算)" value={`${fmt(calc.offdayTotal)} kcal/日`} />
              <Tr label={`サウナ ${saunaPerMonth}回/月`} value={`${fmt(calc.saunaMonth)} kcal/月`} />
            </tbody>
          </table>

          <div style={{ marginTop:14, padding:"14px 16px", borderRadius:T.r.md,
            background:T.primaryLight, border:`1px solid ${T.outline}`, textAlign:"center" }}>
            <div style={{ fontSize:13, color:T.onSurfaceMed }}>
              月間消費カロリー(勤務{calc.wd}日+休み{calc.offDays}日+サウナ)
            </div>
            <div style={{ fontSize:30, fontWeight:700, color:T.primary, marginTop:4 }}>
              約 {fmt(calc.monthlyBurn)} kcal/月
            </div>
          </div>

          {hasIntake && (
            <div style={{ marginTop:12, padding:"14px 16px", borderRadius:T.r.md,
              background:balanceColor.bg, border:`1px solid ${balanceColor.border}` }}>
              <div style={{ fontSize:13, color:T.onSurfaceMed }}>
                摂取 {fmt(calc.dailyIntake)} kcal/日 × {calc.md}日 = {fmt(calc.monthlyIntake)} kcal/月
              </div>
              <div style={{ fontSize:18, fontWeight:700, color:balanceColor.text, marginTop:4 }}>
                月間収支: {calc.balance <= 0 ? "−" : "+"}{fmt(Math.abs(calc.balance))} kcal
                (体脂肪 約{(Math.abs(calc.balance)/FAT_KCAL_PER_KG).toFixed(1)}kg 相当の
                {calc.balance <= 0 ? "減少" : "増加"}ペース)
              </div>
            </div>
          )}
        </Card>

        <p style={{ fontSize:12, color:T.onSurfaceLow, textAlign:"center", margin:"4px 0 24px" }}>
          ※ METs法による概算です。個人差(体組成・気温・強度)により±10〜15%程度の誤差があります。
        </p>
      </div>
    </div>
  );
}

function bikeLabel(calc) {
  const min = Math.round(calc.bikeHours * 60);
  return `約${min}分`;
}

function Card({ title, accent, children }) {
  return (
    <section style={{ background:T.surface, borderRadius:T.r.lg, boxShadow:T.shadow,
      border: accent ? `2px solid ${T.primary}` : `1px solid ${T.outline}`, padding:"18px 20px" }}>
      <h2 style={{ margin:"0 0 12px", fontSize:16 }}>{title}</h2>
      {children}
    </section>
  );
}

function Row({ children }) {
  return <div style={{ display:"flex", flexWrap:"wrap", gap:12, marginBottom:10 }}>{children}</div>;
}

function Field({ label, children }) {
  return (
    <label style={{ display:"flex", flexDirection:"column", gap:4, flex:"1 1 140px", fontSize:12, color:T.onSurfaceMed }}>
      {label}
      {children}
    </label>
  );
}

const inputStyle = {
  padding:"9px 12px", borderRadius:T.r.sm, border:`1px solid ${T.outline}`,
  fontSize:15, color:T.onSurface, background:T.surface, width:"100%", boxSizing:"border-box",
};

function Input({ value, onChange, placeholder }) {
  return (
    <input type="number" inputMode="decimal" value={value} placeholder={placeholder}
      onChange={e=>onChange(e.target.value)} style={inputStyle} />
  );
}

function Select({ value, onChange, options }) {
  return (
    <select value={value} onChange={e=>onChange(e.target.value)} style={inputStyle}>
      {options.map(o=><option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

function Tr({ label, value, strong }) {
  return (
    <tr style={{ borderBottom:`1px solid ${T.outline}` }}>
      <td style={{ padding:"8px 4px", color: strong ? T.onSurface : T.onSurfaceMed,
        fontWeight: strong ? 700 : 400 }}>{label}</td>
      <td style={{ padding:"8px 4px", textAlign:"right", fontWeight: strong ? 700 : 500 }}>{value}</td>
    </tr>
  );
}
