import { useState } from "react";
import economy from "../data/site/economy.json";
import news from "../data/site/news.json";
import builds from "../data/site/builds.json";
import articlesData from "../content/articles.json";

// ダークファンタジー寄りの配色(PoE2の雰囲気に合わせる)
const T = {
  bg: "#0F0D0A",
  surface: "#1A1712",
  surfaceVar: "#241F17",
  outline: "#3A3225",
  gold: "#C9A227",
  goldLight: "#E8C95B",
  text: "#EAE3D2",
  textMed: "#B0A488",
  textLow: "#7A7060",
  up: "#5DBB63",
  down: "#E05252",
  r: { sm: "8px", md: "12px", lg: "16px", full: "999px" },
  shadow: "0 2px 8px rgba(0,0,0,0.45)",
};

const fmtRate = (v) =>
  v >= 100 ? Math.round(v).toLocaleString() : v >= 1 ? v.toFixed(1) : v.toFixed(3);

const fmtDate = (iso) =>
  new Date(iso).toLocaleString("ja-JP", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

function Change({ pct }) {
  const color = pct > 0 ? T.up : pct < 0 ? T.down : T.textLow;
  const sign = pct > 0 ? "▲" : pct < 0 ? "▼" : "―";
  return (
    <span style={{ color, fontWeight: 700, fontSize: 13, whiteSpace: "nowrap" }}>
      {sign} {Math.abs(pct).toFixed(1)}%
    </span>
  );
}


function Sparkline({ data, color }) {
  const pts = (data ?? []).filter((v) => typeof v === "number");
  if (pts.length < 2) return <span style={{ width: 56, flexShrink: 0 }} />;
  const min = Math.min(...pts);
  const max = Math.max(...pts);
  const range = max - min || 1;
  const w = 56;
  const h = 18;
  const points = pts
    .map(
      (v, i) =>
        `${((i / (pts.length - 1)) * w).toFixed(1)},${(h - 2 - ((v - min) / range) * (h - 4)).toFixed(1)}`,
    )
    .join(" ");
  return (
    <svg width={w} height={h} style={{ flexShrink: 0, opacity: 0.9 }} aria-hidden="true">
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  );
}

function Converter({ currencies, rateOf, unitLabel, defaultFrom, defaultTo }) {
  const find = (id) => currencies.find((c) => c.id === id);
  const [amount, setAmount] = useState("1");
  const [fromId, setFromId] = useState(find(defaultFrom) ? defaultFrom : currencies[0]?.id);
  const [toId, setToId] = useState(find(defaultTo) ? defaultTo : currencies[1]?.id);
  const opts = currencies.slice(0, 25);
  const num = parseFloat(String(amount).replace(/,/g, ""));
  const from = find(fromId);
  const to = find(toId);
  const result =
    Number.isFinite(num) && from && to ? (num * rateOf(from)) / rateOf(to) : null;
  const fmtResult = (v) =>
    v >= 1000
      ? Math.round(v).toLocaleString()
      : v >= 1
        ? v.toFixed(2)
        : v.toPrecision(3);
  const selStyle = {
    background: T.surfaceVar,
    color: T.text,
    border: `1px solid ${T.outline}`,
    borderRadius: T.r.sm,
    padding: "8px 6px",
    fontSize: 13,
    maxWidth: "100%",
  };
  return (
    <div style={{ display: "grid", gap: 10 }}>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <input
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          inputMode="decimal"
          style={{ ...selStyle, width: 90 }}
          aria-label="数量"
        />
        <select value={fromId} onChange={(e) => setFromId(e.target.value)} style={selStyle}>
          {opts.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <button
          onClick={() => {
            setFromId(toId);
            setToId(fromId);
          }}
          style={{
            background: "none",
            border: `1px solid ${T.outline}`,
            color: T.goldLight,
            borderRadius: T.r.full,
            padding: "6px 12px",
            cursor: "pointer",
            fontSize: 14,
          }}
          aria-label="入れ替え"
        >
          ⇄
        </button>
        <select value={toId} onChange={(e) => setToId(e.target.value)} style={selStyle}>
          {opts.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>
      <div style={{ fontSize: 15, color: T.text }}>
        {result !== null && from && to ? (
          <>
            <b style={{ color: T.goldLight }}>{fmtResult(result)}</b>{" "}
            <span style={{ fontSize: 12, color: T.textMed }}>{to.name}</span>
            <span style={{ fontSize: 11, color: T.textLow, marginLeft: 8 }}>
              (1 {from.name} ≈ {fmtResult(rateOf(from) / rateOf(to))} {to.name})
            </span>
          </>
        ) : (
          <span style={{ color: T.textLow, fontSize: 13 }}>数量を入力してください</span>
        )}
      </div>
    </div>
  );
}

function Card({ title, sub, children }) {
  return (
    <section
      style={{
        background: T.surface,
        border: `1px solid ${T.outline}`,
        borderRadius: T.r.lg,
        padding: "18px 20px",
        boxShadow: T.shadow,
      }}
    >
      <div style={{ marginBottom: 12 }}>
        <h2 style={{ margin: 0, fontSize: 16, color: T.goldLight, letterSpacing: "0.02em" }}>
          {title}
        </h2>
        {sub && <div style={{ fontSize: 12, color: T.textLow, marginTop: 2 }}>{sub}</div>}
      </div>
      {children}
    </section>
  );
}

function UniqueRow({ u }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "7px 4px",
        borderBottom: `1px solid ${T.outline}`,
      }}
    >
      {u.icon && (
        <img src={u.icon} alt="" width={28} height={28} style={{ flexShrink: 0 }} loading="lazy" />
      )}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: T.text,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {u.name}
        </div>
        <div style={{ fontSize: 11, color: T.textLow }}>
          {u.baseType} ・ 出品{u.listingCount}
        </div>
      </div>
      <Sparkline data={u.spark} color={u.change7d >= 0 ? T.up : T.down} />
      <div style={{ textAlign: "right" }}>
        <div style={{ fontSize: 13, color: T.text, fontWeight: 600 }}>
          {fmtRate(u.value)} <span style={{ fontSize: 10, color: T.textLow }}>ex</span>
        </div>
        <Change pct={u.change7d} />
      </div>
    </div>
  );
}

function Article({ a, expanded, onToggle }) {
  return (
    <article
      style={{
        border: `1px solid ${T.outline}`,
        borderRadius: T.r.md,
        padding: "14px 16px",
        background: T.surfaceVar,
      }}
    >
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
        <span
          style={{
            fontSize: 10,
            fontWeight: 700,
            color: T.bg,
            background: a.type === "patch" ? T.goldLight : T.textMed,
            borderRadius: T.r.full,
            padding: "2px 8px",
          }}
        >
          {a.type === "patch" ? "パッチ解説" : "市場動向"}
        </span>
        <span style={{ fontSize: 11, color: T.textLow }}>{fmtDate(a.createdAt)}</span>
      </div>
      <h3
        style={{ margin: "0 0 6px", fontSize: 15, color: T.text, cursor: "pointer" }}
        onClick={onToggle}
      >
        {a.title}
      </h3>
      <p style={{ margin: 0, fontSize: 13, color: T.textMed, lineHeight: 1.7 }}>{a.summary}</p>
      {expanded &&
        a.sections.map((s, i) => (
          <div key={i} style={{ marginTop: 12 }}>
            <h4 style={{ margin: "0 0 4px", fontSize: 13, color: T.goldLight }}>{s.heading}</h4>
            <p
              style={{
                margin: 0,
                fontSize: 13,
                color: T.text,
                lineHeight: 1.8,
                whiteSpace: "pre-wrap",
              }}
            >
              {s.body}
            </p>
          </div>
        ))}
      <button
        onClick={onToggle}
        style={{
          marginTop: 10,
          background: "none",
          border: `1px solid ${T.outline}`,
          color: T.textMed,
          borderRadius: T.r.full,
          padding: "4px 14px",
          fontSize: 12,
          cursor: "pointer",
        }}
      >
        {expanded ? "閉じる" : "続きを読む"}
      </button>
    </article>
  );
}

export default function App() {
  const [openId, setOpenId] = useState(articlesData.articles[0]?.id ?? null);
  const articles = articlesData.articles;
  const patchNews = news.items.filter((n) => n.isPatch).slice(0, 5);

  return (
    <div
      style={{
        minHeight: "100vh",
        background: T.bg,
        color: T.text,
        fontFamily:
          "'Hiragino Sans', 'Noto Sans JP', 'Yu Gothic', system-ui, sans-serif",
      }}
    >
      <header
        style={{
          borderBottom: `1px solid ${T.outline}`,
          padding: "18px 20px",
          background: T.surface,
        }}
      >
        <div style={{ maxWidth: 960, margin: "0 auto" }}>
          <h1 style={{ margin: 0, fontSize: 20, color: T.goldLight, letterSpacing: "0.04em" }}>
            ⚔️ PoE2相場モニター
          </h1>
          <div style={{ fontSize: 12, color: T.textMed, marginTop: 4 }}>
            リーグ「{economy.league}」 ・ 最終更新 {fmtDate(economy.generatedAt)} ・
            通貨レートはExalted Orb基準、変動率は直近7日間
          </div>
        </div>
      </header>

      <main
        style={{
          maxWidth: 960,
          margin: "0 auto",
          padding: "20px 16px 60px",
          display: "grid",
          gap: 16,
        }}
      >
        <Card title="🔁 通貨換算ツール" sub="現在レートで換算(6時間ごと自動更新)">
          <Converter
            currencies={economy.currencies}
            rateOf={(c) => c.rateInExalted}
            unitLabel=""
            defaultFrom="divine"
            defaultTo="exalted"
          />
        </Card>

        {/* AI生成記事 */}
        {articles.length > 0 && (
          <Card
            title="📝 週間市場レポート(自動生成)"
            sub="集計データからAIが生成し、数値の照合チェックを通過した記事のみ掲載しています"
          >
            <div style={{ display: "grid", gap: 10 }}>
              {articles.slice(0, 5).map((a) => (
                <Article
                  key={a.id}
                  a={a}
                  expanded={openId === a.id}
                  onToggle={() => setOpenId(openId === a.id ? null : a.id)}
                />
              ))}
            </div>
          </Card>
        )}

        <div
          style={{
            display: "grid",
            gap: 16,
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          }}
        >
          {/* 通貨相場 */}
          <Card title="💰 通貨相場" sub="1 Exalted Orbに対するレート">
            <div>
              {economy.currencies.slice(0, 14).map((c) => (
                <div
                  key={c.id}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "6px 4px",
                    borderBottom: `1px solid ${T.outline}`,
                    gap: 8,
                  }}
                >
                  <span
                    style={{
                      fontSize: 13,
                      color: T.text,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {c.name}
                  </span>
                  <span style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    <Sparkline data={c.spark} color={c.change7d >= 0 ? T.up : T.down} />
                    <span style={{ fontSize: 13, fontWeight: 700, color: T.goldLight }}>
                      {fmtRate(c.rateInExalted)}
                    </span>
                    <Change pct={c.change7d} />
                  </span>
                </div>
              ))}
            </div>
          </Card>

          {/* 公式ニュース */}
          <Card title="📰 公式ニュース" sub="Steamニュースから自動取得">
            <div style={{ display: "grid", gap: 8 }}>
              {(patchNews.length > 0 ? patchNews : news.items.slice(0, 5)).map((n) => (
                <a
                  key={n.gid}
                  href={n.url}
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    color: T.text,
                    textDecoration: "none",
                    fontSize: 13,
                    lineHeight: 1.5,
                    padding: "6px 8px",
                    borderRadius: T.r.sm,
                    background: T.surfaceVar,
                    border: `1px solid ${T.outline}`,
                  }}
                >
                  <div style={{ fontWeight: 600 }}>{n.title}</div>
                  <div style={{ fontSize: 11, color: T.textLow, marginTop: 2 }}>
                    {new Date(n.date * 1000).toLocaleDateString("ja-JP")}
                    {n.isPatch && (
                      <span style={{ color: T.goldLight, marginLeft: 6 }}>● パッチ関連</span>
                    )}
                  </div>
                </a>
              ))}
            </div>
          </Card>
        </div>

        {/* ビルドメタ統計(公式ラダーAPI設定後に表示される) */}
        {builds.available && (
          <Card
            title="🏆 人気クラス分布"
            sub={`公式ラダー上位${builds.totalEntries}キャラの集計(アセンダンシー別)`}
          >
            <div style={{ display: "grid", gap: 6 }}>
              {builds.classes.slice(0, 12).map((c) => (
                <div key={c.name} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontSize: 12, color: T.text, width: 140, flexShrink: 0 }}>
                    {c.name}
                  </span>
                  <div
                    style={{
                      flex: 1,
                      height: 14,
                      background: T.surfaceVar,
                      borderRadius: T.r.full,
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${Math.max(c.pct, 1)}%`,
                        height: "100%",
                        background: T.gold,
                      }}
                    />
                  </div>
                  <span style={{ fontSize: 12, color: T.goldLight, width: 52, textAlign: "right" }}>
                    {c.pct}%
                  </span>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 14 }}>
              <div style={{ fontSize: 12, color: T.textLow, marginBottom: 6 }}>
                ラダー上位キャラ
              </div>
              {builds.top.slice(0, 10).map((t) => (
                <div
                  key={t.rank}
                  style={{
                    display: "flex",
                    gap: 10,
                    fontSize: 12,
                    padding: "4px 2px",
                    borderBottom: `1px solid ${T.outline}`,
                    color: T.textMed,
                  }}
                >
                  <span style={{ width: 28, color: T.goldLight }}>#{t.rank}</span>
                  <span style={{ flex: 1, color: T.text }}>{t.name}</span>
                  <span>{t.class}</span>
                  <span style={{ width: 46, textAlign: "right" }}>Lv{t.level}</span>
                </div>
              ))}
            </div>
          </Card>
        )}

        <div
          style={{
            display: "grid",
            gap: 16,
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          }}
        >
          <Card title="📈 高騰ユニーク TOP10" sub="直近7日の上昇率(出品5件以上)">
            {economy.gainers.map((u) => (
              <UniqueRow key={`${u.name}-${u.baseType}`} u={u} />
            ))}
          </Card>
          <Card title="📉 下落ユニーク TOP10" sub="直近7日の下落率(出品5件以上)">
            {economy.losers.map((u) => (
              <UniqueRow key={`${u.name}-${u.baseType}`} u={u} />
            ))}
          </Card>
          <Card title="👑 高額ユニーク TOP10" sub="現在の取引価格">
            {economy.expensive.map((u) => (
              <UniqueRow key={`${u.name}-${u.baseType}`} u={u} />
            ))}
          </Card>
        </div>

        <footer
          style={{
            fontSize: 11,
            color: T.textLow,
            lineHeight: 1.8,
            borderTop: `1px solid ${T.outline}`,
            paddingTop: 14,
          }}
        >
          データ出典:{" "}
          <a href="https://poe.ninja" style={{ color: T.textMed }}>
            poe.ninja
          </a>{" "}
          /{" "}
          <a href="https://store.steampowered.com/app/2694490/" style={{ color: T.textMed }}>
            Steam公式ニュース
          </a>
          。本サイトはGrinding Gear Gamesとは無関係の非公式ファンサイトです。
          記事はAIによる自動生成のため、取引の判断は必ずご自身でデータを確認してください。
          {/* AdSense等の広告ユニットはこの位置に挿入する想定 */}
        </footer>
      </main>
    </div>
  );
}
