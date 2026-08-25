import { useState } from "react";
import economy from "../data/site/economy.json";
import articlesData from "../content/articles.json";

// ダークレザー×ブロンズ配色。MTGの重厚な雰囲気に合わせる
const T = {
  bg: "#12100C",
  surface: "#1B1812",
  surfaceVar: "#241F15",
  outline: "#3A3322",
  accent: "#D08A3E",
  accentLight: "#E8B06A",
  text: "#EAE7DE",
  textMed: "#ADA795",
  textLow: "#736C58",
  up: "#5DBB63",
  down: "#E05252",
  r: { sm: "8px", md: "12px", lg: "16px", full: "999px" },
  shadow: "0 2px 8px rgba(0,0,0,0.45)",
};

const fmtJpy = (v) => (v == null ? "—" : `約${Math.round(v).toLocaleString("ja-JP")}円`);
const fmtUsd = (v) => `$${v.toFixed(2)}`;

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

const RARITY_JA = { mythic: "神話レア", rare: "レア", uncommon: "アンコモン", common: "コモン" };

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
        <div style={{ fontSize: 11, color: T.textLow }}>
          {item.set}
          {item.rarity && <> ・ {RARITY_JA[item.rarity] ?? item.rarity}</>}
          {item.foilOnly && (
            <span style={{ color: T.accent, fontWeight: 700, marginLeft: 6 }}>Foil</span>
          )}
        </div>
      </div>
      <div style={{ textAlign: "right" }}>
        <div style={{ fontSize: 13, color: T.accentLight, fontWeight: 600 }}>
          {fmtJpy(item.jpy)}
          <span style={{ fontSize: 11, color: T.textLow, marginLeft: 5 }}>
            {fmtUsd(item.usd)}
          </span>
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
          海外市場動向
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
            🔮 MTG海外相場モニター
          </h1>
          <div style={{ fontSize: 12, color: T.textMed, marginTop: 4 }}>
            直近セットの海外市場価格(TCGplayer $) ・ 最終更新 {fmtDate(economy.generatedAt)}
            {economy.fx && (
              <>
                {" "}
                ・ 円換算レート $1 = {economy.fx.usdJpy}円({economy.fx.date} ECB)
              </>
            )}
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
            title="📝 海外市場レポート(自動生成)"
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
                <Card title="📈 高騰カード TOP10" sub="約7日前の価格との比較($2以上のカード)">
                  {economy.gainers.map((c) => (
                    <ItemRow key={c.id} item={c} />
                  ))}
                </Card>
                <Card title="📉 下落カード TOP10" sub="約7日前の価格との比較($2以上のカード)">
                  {economy.losers.map((c) => (
                    <ItemRow key={c.id} item={c} />
                  ))}
                </Card>
              </div>
            ) : (
              <Card title="📈 騰落ランキング(準備中)">
                <p style={{ margin: 0, fontSize: 13, color: T.textMed, lineHeight: 1.8 }}>
                  価格履歴を蓄積中です。数日分のデータが貯まると高騰・下落ランキングが表示されます
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
              <Card title="👑 高額カード TOP10" sub="現在のTCGplayer価格">
                {economy.expensive.map((c) => (
                  <ItemRow key={c.id} item={c} showChange={false} />
                ))}
              </Card>
              <Card title="🗂️ 監視セット概況" sub="直近発売セットと最高額カード(当たり枠)">
                {economy.sets.map((s) => (
                  <div
                    key={s.code}
                    style={{ padding: "8px 4px", borderBottom: `1px solid ${T.outline}` }}
                  >
                    <div style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{s.name}</div>
                    <div style={{ fontSize: 11, color: T.textLow, marginTop: 2 }}>
                      発売 {s.releaseDate} ・ 価格付き {s.pricedCards}枚
                    </div>
                    {s.topCard && (
                      <div style={{ fontSize: 12, color: T.textMed, marginTop: 2 }}>
                        最高額: {s.topCard.name}{" "}
                        <span style={{ color: T.accentLight, fontWeight: 600 }}>
                          {fmtJpy(s.topCard.jpy)}({fmtUsd(s.topCard.usd)})
                        </span>
                        {s.topCard.foilOnly && (
                          <span style={{ color: T.accent, fontWeight: 700, marginLeft: 4 }}>
                            Foil
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </Card>
            </div>
          </>
        ) : (
          <Card title="🔧 メンテナンス情報">
            <p style={{ margin: 0, fontSize: 13, color: T.textMed, lineHeight: 1.8 }}>
              データ取得元(Scryfall)が一時的に利用できません。次回の自動更新で復旧します
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
          <a href="https://scryfall.com" style={{ color: T.textMed }}>
            Scryfall
          </a>
          (公開API・TCGplayer/Cardmarket価格)、為替は
          <a href="https://frankfurter.dev" style={{ color: T.textMed }}>
            Frankfurter
          </a>
          (ECB公表レート)。円換算はあくまで参考値です。カード名は英語表記で、
          eBay等の海外取引で実際に使われる名称です。監視対象は直近発売のセット群です。
          本サイトはWizards of the Coast・TCGplayer・Cardmarket・Scryfallとは無関係の非公式ファンサイトです。
          記事はAIによる自動生成であり、売買や投資の助言ではありません。取引の判断は必ずご自身でデータをご確認ください。
          {/* AdSense等の広告ユニットはこの位置に挿入する想定 */}
        </footer>
      </main>
    </div>
  );
}
