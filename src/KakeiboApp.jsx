import { useState, useEffect, useMemo, useRef } from "react";

const T = {
  primary:      "#1A56DB",
  primaryLight: "#EEF3FF",
  surface:      "#FFFFFF",
  surfaceVar:   "#F4F6FB",
  outline:      "#E2E8F0",
  onSurface:    "#0F172A",
  onSurfaceMed: "#475569",
  onSurfaceLow: "#94A3B8",
  income:  { bg:"#ECFDF5", text:"#059669", border:"#A7F3D0", badge:"#D1FAE5" },
  expense: { bg:"#FFF1F2", text:"#E11D48", border:"#FECDD3", badge:"#FFE4E6" },
  shadow:   "0 1px 3px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.05)",
  shadowMd: "0 2px 8px rgba(0,0,0,0.09), 0 8px 24px rgba(0,0,0,0.07)",
  r: { sm:"8px", md:"14px", lg:"18px", xl:"24px", full:"999px" },
};

const CATEGORIES = {
  income:  ["給料", "ボーナス", "副収入", "臨時収入", "その他"],
  expense: ["食費", "日用品", "住居", "水道光熱", "通信", "交通", "医療", "交際", "趣味", "教育", "その他"],
};

const STORAGE_KEY = "kakeibo-entries-v1";

function loadEntries() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const data = JSON.parse(raw);
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

const todayStr = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const yen = (n) => `¥${Math.abs(n).toLocaleString("ja-JP")}`;

const monthLabel = (ym) => {
  const [y, m] = ym.split("-");
  return `${y}年${Number(m)}月`;
};

const dateLabel = (dateStr) => {
  const [y, m, d] = dateStr.split("-").map(Number);
  const week = ["日", "月", "火", "水", "木", "金", "土"][new Date(y, m - 1, d).getDay()];
  return `${m}月${d}日 (${week})`;
};

export default function KakeiboApp() {
  const [entries, setEntries] = useState(loadEntries);
  const [viewMonth, setViewMonth] = useState(() => todayStr().slice(0, 7));
  const [form, setForm] = useState({
    date: todayStr(), type: "expense", category: CATEGORIES.expense[0], amount: "", memo: "",
  });
  const fileRef = useRef(null);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  }, [entries]);

  // リポジトリに置かれた記録 (public/entries.json) を取り込む。
  // チャット経由で追記された記録もアプリに反映される。
  useEffect(() => {
    fetch("/entries.json")
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => {
        if (!Array.isArray(data)) return;
        const valid = data.filter(
          (x) => x && x.id && x.date && (x.type === "income" || x.type === "expense") &&
                 Number.isFinite(Number(x.amount))
        );
        setEntries((prev) => {
          const ids = new Set(prev.map((p) => p.id));
          const fresh = valid.filter((v) => !ids.has(v.id));
          if (fresh.length === 0) return prev;
          return [...prev, ...fresh].sort((a, b) => (a.date < b.date ? -1 : 1));
        });
      })
      .catch(() => {});
  }, []);

  const setType = (type) =>
    setForm((f) => ({ ...f, type, category: CATEGORIES[type][0] }));

  const addEntry = (e) => {
    e.preventDefault();
    const amount = Number(form.amount);
    if (!form.date || !Number.isFinite(amount) || amount <= 0) return;
    const entry = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      date: form.date,
      type: form.type,
      category: form.category,
      amount: Math.floor(amount),
      memo: form.memo.trim(),
    };
    setEntries((prev) =>
      [...prev, entry].sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0))
    );
    setForm((f) => ({ ...f, amount: "", memo: "" }));
    setViewMonth(entry.date.slice(0, 7));
  };

  const removeEntry = (id) => {
    if (!window.confirm("この記録を削除しますか?")) return;
    setEntries((prev) => prev.filter((e) => e.id !== id));
  };

  const shiftMonth = (delta) => {
    const [y, m] = viewMonth.split("-").map(Number);
    const d = new Date(y, m - 1 + delta, 1);
    setViewMonth(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`);
  };

  const monthEntries = useMemo(
    () => entries.filter((e) => e.date.startsWith(viewMonth)),
    [entries, viewMonth]
  );

  const sum = (list, type) =>
    list.filter((e) => e.type === type).reduce((acc, e) => acc + e.amount, 0);

  const monthIncome  = sum(monthEntries, "income");
  const monthExpense = sum(monthEntries, "expense");
  const totalSavings = sum(entries, "income") - sum(entries, "expense");

  const byDate = useMemo(() => {
    const map = new Map();
    for (const e of monthEntries) {
      if (!map.has(e.date)) map.set(e.date, []);
      map.get(e.date).push(e);
    }
    return [...map.entries()].sort((a, b) => (a[0] < b[0] ? 1 : -1));
  }, [monthEntries]);

  const exportCsv = () => {
    const header = "日付,種別,カテゴリ,金額,メモ";
    const rows = entries.map((e) =>
      [e.date, e.type === "income" ? "収入" : "支出", e.category, e.amount,
       `"${(e.memo || "").replace(/"/g, '""')}"`].join(",")
    );
    const blob = new Blob(["﻿" + [header, ...rows].join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `kakeibo-${todayStr()}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(entries, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `kakeibo-${todayStr()}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const importJson = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const data = JSON.parse(reader.result);
        if (!Array.isArray(data)) throw new Error();
        const valid = data.filter(
          (x) => x && x.date && (x.type === "income" || x.type === "expense") &&
                 Number.isFinite(Number(x.amount))
        );
        if (!window.confirm(`${valid.length}件の記録を読み込みます。既存の記録と統合しますか?`)) return;
        setEntries((prev) => {
          const ids = new Set(prev.map((p) => p.id));
          const merged = [...prev, ...valid.filter((v) => !ids.has(v.id))];
          return merged.sort((a, b) => (a.date < b.date ? -1 : 1));
        });
      } catch {
        window.alert("ファイルを読み込めませんでした。JSON形式のバックアップを選択してください。");
      }
    };
    reader.readAsText(file);
    e.target.value = "";
  };

  const balance = monthIncome - monthExpense;

  const inputStyle = {
    padding: "10px 12px", borderRadius: T.r.sm, border: `1px solid ${T.outline}`,
    fontSize: "15px", color: T.onSurface, background: T.surface, outline: "none",
    width: "100%", boxSizing: "border-box",
  };
  const labelStyle = {
    fontSize: "12px", fontWeight: 600, color: T.onSurfaceMed, marginBottom: "4px", display: "block",
  };

  return (
    <div style={{
      minHeight: "100vh", background: T.surfaceVar, color: T.onSurface,
      fontFamily: '"Hiragino Sans", "Yu Gothic UI", "Noto Sans JP", sans-serif',
      padding: "16px",
    }}>
      <div style={{ maxWidth: "640px", margin: "0 auto" }}>

        <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 4px 16px" }}>
          <h1 style={{ fontSize: "20px", fontWeight: 700, margin: 0 }}>💰 収支きろく</h1>
          <div style={{ display: "flex", gap: "8px" }}>
            <button onClick={exportCsv} style={{
              padding: "6px 12px", borderRadius: T.r.full, border: `1px solid ${T.outline}`,
              background: T.surface, fontSize: "12px", fontWeight: 600, color: T.onSurfaceMed, cursor: "pointer",
            }}>CSV出力</button>
            <button onClick={exportJson} style={{
              padding: "6px 12px", borderRadius: T.r.full, border: `1px solid ${T.outline}`,
              background: T.surface, fontSize: "12px", fontWeight: 600, color: T.onSurfaceMed, cursor: "pointer",
            }}>バックアップ</button>
            <button onClick={() => fileRef.current?.click()} style={{
              padding: "6px 12px", borderRadius: T.r.full, border: `1px solid ${T.outline}`,
              background: T.surface, fontSize: "12px", fontWeight: 600, color: T.onSurfaceMed, cursor: "pointer",
            }}>復元</button>
            <input ref={fileRef} type="file" accept=".json,application/json" onChange={importJson} style={{ display: "none" }} />
          </div>
        </header>

        <section style={{
          background: T.primary, borderRadius: T.r.lg, padding: "20px", color: "#fff",
          boxShadow: T.shadowMd, marginBottom: "16px",
        }}>
          <div style={{ fontSize: "12px", opacity: 0.85, fontWeight: 600 }}>これまでの貯蓄合計</div>
          <div style={{ fontSize: "32px", fontWeight: 700, margin: "4px 0 0" }}>
            {totalSavings < 0 ? "-" : ""}{yen(totalSavings)}
          </div>
          <div style={{ fontSize: "12px", opacity: 0.8, marginTop: "4px" }}>
            全期間の収入 − 支出({entries.length}件の記録)
          </div>
        </section>

        <section style={{
          background: T.surface, borderRadius: T.r.lg, padding: "16px",
          boxShadow: T.shadow, marginBottom: "16px",
        }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
            <button onClick={() => shiftMonth(-1)} aria-label="前の月" style={{
              width: "32px", height: "32px", borderRadius: T.r.full, border: `1px solid ${T.outline}`,
              background: T.surface, cursor: "pointer", fontSize: "14px",
            }}>‹</button>
            <div style={{ fontWeight: 700, fontSize: "16px" }}>{monthLabel(viewMonth)}</div>
            <button onClick={() => shiftMonth(1)} aria-label="次の月" style={{
              width: "32px", height: "32px", borderRadius: T.r.full, border: `1px solid ${T.outline}`,
              background: T.surface, cursor: "pointer", fontSize: "14px",
            }}>›</button>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "8px" }}>
            <div style={{ background: T.income.bg, border: `1px solid ${T.income.border}`, borderRadius: T.r.md, padding: "10px" }}>
              <div style={{ fontSize: "11px", fontWeight: 600, color: T.income.text }}>収入</div>
              <div style={{ fontSize: "16px", fontWeight: 700, color: T.income.text }}>{yen(monthIncome)}</div>
            </div>
            <div style={{ background: T.expense.bg, border: `1px solid ${T.expense.border}`, borderRadius: T.r.md, padding: "10px" }}>
              <div style={{ fontSize: "11px", fontWeight: 600, color: T.expense.text }}>支出</div>
              <div style={{ fontSize: "16px", fontWeight: 700, color: T.expense.text }}>{yen(monthExpense)}</div>
            </div>
            <div style={{ background: T.primaryLight, border: `1px solid ${T.outline}`, borderRadius: T.r.md, padding: "10px" }}>
              <div style={{ fontSize: "11px", fontWeight: 600, color: T.primary }}>収支</div>
              <div style={{ fontSize: "16px", fontWeight: 700, color: balance < 0 ? T.expense.text : T.primary }}>
                {balance < 0 ? "-" : "+"}{yen(balance)}
              </div>
            </div>
          </div>
        </section>

        <section style={{
          background: T.surface, borderRadius: T.r.lg, padding: "16px",
          boxShadow: T.shadow, marginBottom: "16px",
        }}>
          <form onSubmit={addEntry}>
            <div style={{ display: "flex", gap: "8px", marginBottom: "12px" }}>
              {[["expense", "支出"], ["income", "収入"]].map(([type, label]) => {
                const active = form.type === type;
                const c = T[type];
                return (
                  <button key={type} type="button" onClick={() => setType(type)} style={{
                    flex: 1, padding: "10px", borderRadius: T.r.md, cursor: "pointer",
                    border: `2px solid ${active ? c.text : T.outline}`,
                    background: active ? c.bg : T.surface,
                    color: active ? c.text : T.onSurfaceMed,
                    fontWeight: 700, fontSize: "14px",
                  }}>{label}</button>
                );
              })}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginBottom: "10px" }}>
              <div>
                <label style={labelStyle}>日付</label>
                <input type="date" value={form.date} required
                  onChange={(e) => setForm((f) => ({ ...f, date: e.target.value }))} style={inputStyle} />
              </div>
              <div>
                <label style={labelStyle}>カテゴリ</label>
                <select value={form.category}
                  onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))} style={inputStyle}>
                  {CATEGORIES[form.type].map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label style={labelStyle}>金額(円)</label>
                <input type="number" inputMode="numeric" min="1" step="1" placeholder="1000" required
                  value={form.amount}
                  onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))} style={inputStyle} />
              </div>
              <div>
                <label style={labelStyle}>メモ(任意)</label>
                <input type="text" placeholder="スーパーで買い物 など" value={form.memo}
                  onChange={(e) => setForm((f) => ({ ...f, memo: e.target.value }))} style={inputStyle} />
              </div>
            </div>
            <button type="submit" style={{
              width: "100%", padding: "12px", borderRadius: T.r.md, border: "none",
              background: T.primary, color: "#fff", fontWeight: 700, fontSize: "15px", cursor: "pointer",
            }}>記録する</button>
          </form>
        </section>

        <section>
          {byDate.length === 0 && (
            <div style={{
              textAlign: "center", color: T.onSurfaceLow, padding: "32px 0", fontSize: "14px",
            }}>
              {monthLabel(viewMonth)}の記録はまだありません
            </div>
          )}
          {byDate.map(([date, list]) => (
            <div key={date} style={{ marginBottom: "12px" }}>
              <div style={{ fontSize: "12px", fontWeight: 700, color: T.onSurfaceMed, padding: "0 4px 6px" }}>
                {dateLabel(date)}
              </div>
              <div style={{ background: T.surface, borderRadius: T.r.md, boxShadow: T.shadow, overflow: "hidden" }}>
                {list.map((e, i) => {
                  const c = T[e.type];
                  return (
                    <div key={e.id} style={{
                      display: "flex", alignItems: "center", gap: "10px", padding: "12px 14px",
                      borderTop: i === 0 ? "none" : `1px solid ${T.outline}`,
                    }}>
                      <span style={{
                        fontSize: "11px", fontWeight: 700, color: c.text, background: c.badge,
                        borderRadius: T.r.full, padding: "3px 10px", whiteSpace: "nowrap",
                      }}>{e.category}</span>
                      <span style={{ flex: 1, fontSize: "13px", color: T.onSurfaceMed, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {e.memo}
                      </span>
                      <span style={{ fontWeight: 700, fontSize: "15px", color: c.text, whiteSpace: "nowrap" }}>
                        {e.type === "income" ? "+" : "-"}{yen(e.amount)}
                      </span>
                      <button onClick={() => removeEntry(e.id)} aria-label="削除" style={{
                        border: "none", background: "transparent", color: T.onSurfaceLow,
                        cursor: "pointer", fontSize: "14px", padding: "4px",
                      }}>✕</button>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </section>

        <footer style={{ textAlign: "center", fontSize: "11px", color: T.onSurfaceLow, padding: "16px 0 8px" }}>
          データはこの端末のブラウザ(localStorage)に保存されます。機種変更時は「バックアップ」→「復元」で引き継げます。
        </footer>
      </div>
    </div>
  );
}
