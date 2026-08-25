import { useState } from "react";
import economy from "../data/site/economy.json";
import articlesData from "../content/articles.json";

// ダークチャコール×海賊レッド・ゴールド配色
const T = {
  bg: "#171114",
  surface: "#221820",
  surfaceVar: "#2C1E26",
  outline: "#463038",
  accent: "#C94A3B",
  accentLight: "#F0B94B",
  text: "#F0EAE6",
  textMed: "#B4A8A2",
  textLow: "#7C6E68",
  up: "#5DBB63",
  down: "#E05252",
  r: { sm: "8px", md: "12px", lg: "16px", full: "999px" },
  shadow: "0 2px 8px rgba(0,0,0,0.45)",
};

const fmtJpy = (v) => (v == null ? "—" : `${Math.round(v).toLocaleString("ja-JP")}円`);

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

function ItemRow({ item, badge }) {
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
          {item.url ? (
            // 最安出品への外部リンク(アフィリエイトリンクを含む場合あり)
            <a
              href={item.url}
              target="_blank"
              rel="sponsored nofollow noopener"
              style={{ color: T.text, textDecoration: "none" }}
              title={item.shop ? `最安出品: ${item.shop}` : "最安出品を見る"}
            >
              {item.name} <span style={{ color: T.textLow, fontSize: 11 }}>↗</span>
            </a>
          ) : (
            item.name
          )}
        </div>
        <div style={{ fontSize: 11, color: T.textLow }}>
          {item.brand} ・ {item.category} ・ 出品{item.count}件
          {item.premium != null && (
            <span
              style={{
                color: item.premium > 0 ? T.down : T.up,
                fontWeight: 700,
                marginLeft: 6,
              }}
            >
              定価{item.premium > 0 ? "+" : ""}
              {item.premium}%
            </span>
          )}
        </div>
      </div>
      <div style={{ textAlign: "right" }}>
        <div style={{ fontSize: 13, color: T.accentLight, fontWeight: 600 }}>
          {fmtJpy(item.low)}
          <span style={{ fontSize: 11, color: T.textLow, marginLeft: 5 }}>
            中央値 {fmtJpy(item.median)}
          </span>
        </div>
        {badge === "change" && <Change pct={item.change7d} />}
        {badge === "scarce" && (
          <span style={{ color: T.down, fontWeight: 700, fontSize: 12 }}>残り僅少</span>
        )}
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
          相場動向
        </span>
        <span style={{ fontSize: 11, color: T.textLow }}>{fmtDate(a.createdAt)}</span>
        <a
          href={`articles/${a.id}/`}
          style={{ fontSize: 11, color: T.textLow, marginLeft: "auto" }}
          title="この記事の単独ページ"
        >
          記事ページ🔗
        </a>
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
    </article>
  );
}

export default function App() {
  const [openId, setOpenId] = useState(articlesData.articles[0]?.id ?? null);
  const articles = articlesData.articles;
  const available = economy.available !== false;
  const hasChanges = available && economy.gainers.length > 0;
  const premium = economy.premium ?? [];
  const scarce = economy.scarce ?? [];

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
            🏴‍☠️ ワンピカ国内相場モニター
          </h1>
          <div style={{ fontSize: 12, color: T.textMed, marginTop: 4 }}>
            ワンピースカードの未開封BOX・高額パラレルの国内相場(楽天市場の出品を自動集計)
            {available && <> ・ 最終更新 {fmtDate(economy.generatedAt)}</>}
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
        {articles.length > 0 && (
          <Card
            title="📝 相場レポート(自動生成)"
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
                <Card title="📈 値上がり TOP10" sub="出品中央値の約7日前との比較">
                  {economy.gainers.map((c) => (
                    <ItemRow key={c.id} item={c} badge="change" />
                  ))}
                </Card>
                <Card title="📉 値下がり TOP10" sub="出品中央値の約7日前との比較">
                  {economy.losers.map((c) => (
                    <ItemRow key={c.id} item={c} badge="change" />
                  ))}
                </Card>
              </div>
            ) : (
              <Card title="📈 騰落ランキング(準備中)">
                <p style={{ margin: 0, fontSize: 13, color: T.textMed, lineHeight: 1.8 }}>
                  価格履歴を蓄積中です。数日分のデータが貯まると値上がり・値下がりランキングが表示されます
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
              {premium.length > 0 && (
                <Card title="👑 プレミア率 TOP10" sub="定価に対する最安出品価格の上乗せ率">
                  {premium.map((c) => (
                    <ItemRow key={c.id} item={c} />
                  ))}
                </Card>
              )}
              <Card title="💎 高額アイテム TOP10" sub="現在の最安出品価格">
                {economy.expensive.map((c) => (
                  <ItemRow key={c.id} item={c} />
                ))}
              </Card>
              {scarce.length > 0 && (
                <Card title="🕯 出品僅少" sub="集計対象の出品が3件以下のアイテム">
                  {scarce.map((c) => (
                    <ItemRow key={c.id} item={c} badge="scarce" />
                  ))}
                </Card>
              )}
            </div>
          </>
        ) : (
          <Card title="🔧 メンテナンス情報">
            <p style={{ margin: 0, fontSize: 13, color: T.textMed, lineHeight: 1.8 }}>
              価格データを準備中です。次回の自動更新をお待ちください
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
          価格データは
          <a href="https://developers.rakuten.com/" style={{ color: T.textMed }}>
            楽天ウェブサービス
          </a>
          (楽天市場商品検索API)による現在の出品価格(検索上位)からの自動集計で、参考値です。
          公式の希望小売価格・カードショップの買取価格ではありません。商品リンクにはアフィリエイトリンクを含みます。
          転売や投資の助言ではありません。
          本サイトは集英社・尾田栄一郎氏・バンダイ・楽天グループと無関係の非公式ファンサイトです。
          記事はAIによる自動生成であり、購入判断は必ずご自身で最新の価格をご確認ください。
          <div style={{ marginTop: 6 }}>Supported by Rakuten Developers</div>
          {/* AdSense等の広告ユニットはこの位置に挿入する想定 */}
        </footer>
      </main>
    </div>
  );
}
