import { useState } from "react";
import economy from "../data/site/economy.json";
import articlesData from "../content/articles.json";

// ヴォイド(ダーク紫)×オロキンティール配色。Warframeの雰囲気に合わせる
const T = {
  bg: "#0D0B14",
  surface: "#16121F",
  surfaceVar: "#1E1929",
  outline: "#2C2440",
  accent: "#5FB8AC",
  accentLight: "#8FD8CE",
  text: "#E6E4EC",
  textMed: "#A8A2B8",
  textLow: "#6E687F",
  up: "#5DBB63",
  down: "#E05252",
  r: { sm: "8px", md: "12px", lg: "16px", full: "999px" },
  shadow: "0 2px 8px rgba(0,0,0,0.45)",
};

const fmtPlat = (v) => `${Math.round(v).toLocaleString("ja-JP")} p`;

const fmtDate = (iso) =>
  new Date(iso).toLocaleString("ja-JP", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

function Change({ pct }) {
  if (pct == null) return <span style={{ color: T.textLow, fontSize: 13 }}>—</span>;
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

function ItemRow({ item, showChange = true }) {
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
      {item.icon && (
        <img
          src={item.icon}
          alt=""
          width={28}
          height={28}
          style={{ flexShrink: 0, borderRadius: 4 }}
          loading="lazy"
        />
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
          {item.name}
        </div>
        <div style={{ fontSize: 11, color: T.textLow }}>7日間 {item.vol7d}件成立</div>
      </div>
      <div style={{ textAlign: "right" }}>
        <div style={{ fontSize: 13, color: T.accentLight, fontWeight: 600 }}>
          {fmtPlat(item.price)}
        </div>
        {showChange && <Change pct={item.change7d} />}
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
            background: T.accentLight,
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
  const available = economy.available !== false;
  const hasChanges = available && economy.gainers.length > 0;

  return (
    <div
      style={{
        minHeight: "100vh",
        background: T.bg,
        color: T.text,
        fontFamily: "'Hiragino Sans', 'Noto Sans JP', 'Yu Gothic', system-ui, sans-serif",
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
            🪐 Warframe相場モニター
          </h1>
          <div style={{ fontSize: 12, color: T.textMed, marginTop: 4 }}>
            プライムセット・アルケイン相場(warframe.market) ・ 最終更新{" "}
            {fmtDate(economy.generatedAt)} ・ 価格は取引成立の中央値(プラチナ)、変動率は約7日比
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
            title="📝 市場レポート(自動生成)"
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

        {available ? (
          <>
            {hasChanges ? (
              <div
                style={{
                  display: "grid",
                  gap: 16,
                  gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
                }}
              >
                <Card
                  title="📈 高騰アイテム TOP10"
                  sub="約7日前の中央値との比較(10p以上・週15件以上成立)"
                >
                  {economy.gainers.map((i) => (
                    <ItemRow key={i.slug} item={i} />
                  ))}
                </Card>
                <Card
                  title="📉 下落アイテム TOP10"
                  sub="約7日前の中央値との比較(10p以上・週15件以上成立)"
                >
                  {economy.losers.map((i) => (
                    <ItemRow key={i.slug} item={i} />
                  ))}
                </Card>
              </div>
            ) : (
              <Card title="📈 騰落ランキング(準備中)">
                <p style={{ margin: 0, fontSize: 13, color: T.textMed, lineHeight: 1.8 }}>
                  取引統計を集計中です。次回の自動更新で高騰・下落ランキングが表示されます
                </p>
              </Card>
            )}
            <div
              style={{
                display: "grid",
                gap: 16,
                gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              }}
            >
              <Card title="👑 高額アイテム TOP10" sub="現在の取引成立中央値">
                {economy.expensive.map((i) => (
                  <ItemRow key={i.slug} item={i} showChange={false} />
                ))}
              </Card>
              <Card title="🔥 取引量 TOP10" sub="直近7日の取引成立数">
                {economy.mostTraded.map((i) => (
                  <ItemRow key={i.slug} item={i} showChange={false} />
                ))}
              </Card>
            </div>
          </>
        ) : (
          <Card title="🔧 メンテナンス情報">
            <p style={{ margin: 0, fontSize: 13, color: T.textMed, lineHeight: 1.8 }}>
              データ取得元(warframe.market)が一時的に利用できません。次回の自動更新で復旧します
            </p>
          </Card>
        )}

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
          <a href="https://warframe.market" style={{ color: T.textMed }}>
            warframe.market
          </a>
          (公開API・取引成立統計)。監視対象は全プライムセットと定番のアルケイン・Primed MOD。
          プラチナはゲーム内通貨であり、リアルマネー取引(RMT)を推奨するものではありません。
          本サイトはDigital Extremes・warframe.marketとは無関係の非公式ファンサイトです。
          記事はAIによる自動生成のため、ゲーム内取引の判断はご自身でデータをご確認ください。
          {/* AdSense等の広告ユニットはこの位置に挿入する想定 */}
        </footer>
      </main>
    </div>
  );
}
