import { useState } from "react";
import economy from "../data/site/economy.json";
import articlesData from "../content/articles.json";

// クリスタルブルー×ゴールドの配色(FF14の雰囲気に合わせる)
const T = {
  bg: "#0A0E16",
  surface: "#131A28",
  surfaceVar: "#1B2436",
  outline: "#2A3650",
  accent: "#7FB4E6",
  accentLight: "#A8CDF0",
  gold: "#D9C27A",
  text: "#E6EBF2",
  textMed: "#9FB0C6",
  textLow: "#66788F",
  up: "#5DBB63",
  down: "#E05252",
  r: { sm: "8px", md: "12px", lg: "16px", full: "999px" },
  shadow: "0 2px 8px rgba(0,0,0,0.45)",
};

const fmtGil = (v) => (v == null ? "―" : `${Math.round(v).toLocaleString("ja-JP")}G`);

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
        <h2 style={{ margin: 0, fontSize: 16, color: T.accentLight, letterSpacing: "0.02em" }}>
          {title}
        </h2>
        {sub && <div style={{ fontSize: 12, color: T.textLow, marginTop: 2 }}>{sub}</div>}
      </div>
      {children}
    </section>
  );
}

function ItemRow({ it, showChange }) {
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
          {it.name}
        </div>
        <div style={{ fontSize: 11, color: T.textLow }}>
          最安 {fmtGil(it.minListing)} ・ 約{Math.round(it.velocity).toLocaleString("ja-JP")}個/日
        </div>
      </div>
      <div style={{ textAlign: "right" }}>
        <div style={{ fontSize: 13, color: T.gold, fontWeight: 700 }}>
          {fmtGil(it.price)}
        </div>
        {showChange && <Change pct={it.change7d} />}
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
            background: T.accent,
            borderRadius: T.r.full,
            padding: "2px 8px",
          }}
        >
          市場動向
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
            <h4 style={{ margin: "0 0 4px", fontSize: 13, color: T.accentLight }}>{s.heading}</h4>
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
      <a
        href={`articles/${a.id}/`}
        style={{
          marginTop: 10,
          marginLeft: 8,
          display: "inline-block",
          color: T.textMed,
          fontSize: 12,
          textDecoration: "none",
          border: `1px solid ${T.outline}`,
          borderRadius: T.r.full,
          padding: "4px 14px",
        }}
      >
        記事ページへ →
      </a>
    </article>
  );
}

export default function App() {
  const [openId, setOpenId] = useState(articlesData.articles[0]?.id ?? null);
  const articles = articlesData.articles;
  const hasHistory = economy.gainers.length > 0 || economy.losers.length > 0;

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
          <h1 style={{ margin: 0, fontSize: 20, color: T.accentLight, letterSpacing: "0.04em" }}>
            🔷 FF14マーケットモニター
          </h1>
          <div style={{ fontSize: 12, color: T.textMed, marginTop: 4 }}>
            対象: 日本リージョン統合 ・ 最終更新 {fmtDate(economy.generatedAt)} ・
            価格はギル(NQ平均売却価格)、変動率は直近7日間
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
            <a
              href="articles/"
              style={{ fontSize: 12, color: T.textMed, textDecoration: "underline" }}
            >
              過去記事の一覧を見る →
            </a>
          </Card>
        )}

        <div
          style={{
            display: "grid",
            gap: 16,
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          }}
        >
          <Card title="👑 高額アイテム TOP10" sub="NQ平均売却価格(日本リージョン集計)">
            {economy.expensive.map((it) => (
              <ItemRow key={it.id} it={it} showChange={hasHistory} />
            ))}
          </Card>
          <Card title="🔥 取引量ランキング TOP10" sub="1日あたりの推定取引数">
            {economy.topVolume.map((it) => (
              <ItemRow key={it.id} it={it} showChange={hasHistory} />
            ))}
          </Card>
        </div>

        <div
          style={{
            display: "grid",
            gap: 16,
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          }}
        >
          <Card title="📈 高騰アイテム TOP10(7日)" sub="観測窓内の最古値との比較">
            {economy.gainers.length > 0 ? (
              economy.gainers.map((it) => <ItemRow key={it.id} it={it} showChange />)
            ) : (
              <div style={{ fontSize: 12, color: T.textLow, lineHeight: 1.7 }}>
                変動率は観測開始から蓄積されます。次回以降の更新で表示されます。
              </div>
            )}
          </Card>
          <Card title="📉 下落アイテム TOP10(7日)" sub="観測窓内の最古値との比較">
            {economy.losers.length > 0 ? (
              economy.losers.map((it) => <ItemRow key={it.id} it={it} showChange />)
            ) : (
              <div style={{ fontSize: 12, color: T.textLow, lineHeight: 1.7 }}>
                変動率は観測開始から蓄積されます。次回以降の更新で表示されます。
              </div>
            )}
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
          <a href="https://universalis.app" style={{ color: T.textMed }}>
            Universalis
          </a>
          (クラウドソースのマーケットボード集計。実際の相場と遅延・誤差があり得ます)。
          本サイトは株式会社スクウェア・エニックスとは無関係の非公式ファンサイトです。
          FF14(ファイナルファンタジーXIV)の著作物は株式会社スクウェア・エニックスに帰属します。
          記事はAIによる自動生成のため、取引の判断は必ずご自身でデータを確認してください。
          {/* AdSense等の広告ユニットはこの位置に挿入する想定 */}
        </footer>
      </main>
    </div>
  );
}
