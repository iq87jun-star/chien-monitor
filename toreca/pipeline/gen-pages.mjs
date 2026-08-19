// ビルド後処理: 記事ごとの静的ページと sitemap.xml を dist/ に生成する。
// SPAに埋め込まれた記事はGoogleが個別に認識できないため、
// 記事1本=1URL(/articles/{id}/)の静的HTMLを作って検索流入の受け皿にする。
import fs from "node:fs/promises";
import path from "node:path";
import { ROOT, CONTENT_DIR } from "./config.mjs";

export const SITE_URL = "https://pokeca-kaigai.com/";
const DIST = path.join(ROOT, "dist");

// GA4測定ID。当面はゲーム系サイトと共通プロパティ(ホスト名で区別可能)。
// ポケカ専用プロパティを作成したらここと index.html を差し替える
const GA_ID = "G-7LZS5DCBSG";
const GA_SNIPPET = `<script async src="https://www.googletagmanager.com/gtag/js?id=${GA_ID}"></script>
<script>
window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('js', new Date());
gtag('config', '${GA_ID}');
</script>`;

const esc = (s) =>
  String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

const fmtDate = (iso) =>
  new Date(iso).toLocaleDateString("ja-JP", { year: "numeric", month: "long", day: "numeric" });

function articleHtml(a) {
  const url = `${SITE_URL}articles/${a.id}/`;
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: a.title,
    description: a.summary,
    datePublished: a.createdAt,
    author: { "@type": "Organization", name: "ポケカ海外相場モニター" },
    mainEntityOfPage: url,
  };
  return `<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
${GA_SNIPPET}
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${esc(a.title)} | ポケカ海外相場モニター</title>
<meta name="description" content="${esc(a.summary)}">
<link rel="canonical" href="${url}">
<meta property="og:type" content="article">
<meta property="og:title" content="${esc(a.title)}">
<meta property="og:description" content="${esc(a.summary)}">
<meta property="og:url" content="${url}">
<meta property="og:image" content="${SITE_URL}og.png">
<meta property="og:site_name" content="ポケカ海外相場モニター">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">${JSON.stringify(jsonLd)}</script>
<style>
  body{margin:0;background:#0B0E17;color:#E8E6E0;font-family:'Hiragino Sans','Noto Sans JP','Yu Gothic',system-ui,sans-serif;line-height:1.85}
  .wrap{max-width:760px;margin:0 auto;padding:24px 18px 60px}
  a{color:#EBCB7A}
  .home{font-size:13px;color:#A9ACB8;text-decoration:none}
  .badge{display:inline-block;font-size:11px;font-weight:700;color:#0B0E17;background:#EBCB7A;border-radius:999px;padding:2px 10px;margin-right:8px}
  .date{font-size:12px;color:#6E7284}
  h1{font-size:24px;line-height:1.5;margin:14px 0 10px;color:#fff}
  .lead{color:#A9ACB8;font-size:15px;border-left:3px solid #D4A843;padding-left:12px;margin:16px 0 26px}
  h2{font-size:18px;color:#EBCB7A;margin:30px 0 8px;border-bottom:1px solid #2A3350;padding-bottom:6px}
  p{margin:10px 0;font-size:15px;white-space:pre-wrap}
  .tags{margin-top:26px}
  .tag{display:inline-block;font-size:12px;color:#A9ACB8;background:#1B2236;border:1px solid #2A3350;border-radius:999px;padding:3px 12px;margin:0 6px 6px 0}
  .cta{margin-top:30px;background:#131828;border:1px solid #2A3350;border-radius:14px;padding:16px 18px;font-size:14px}
  footer{margin-top:36px;border-top:1px solid #2A3350;padding-top:14px;font-size:11px;color:#6E7284;line-height:1.8}
</style>
</head>
<body>
<div class="wrap">
  <a class="home" href="../../">← ポケカ海外相場モニター トップ</a>
  <div style="margin-top:18px"><span class="badge">海外市場動向</span><span class="date">${fmtDate(a.createdAt)}</span></div>
  <h1>${esc(a.title)}</h1>
  <div class="lead">${esc(a.summary)}</div>
  ${a.sections
    .map((s) => `<h2>${esc(s.heading)}</h2>\n<p>${esc(s.body)}</p>`)
    .join("\n")}
  <div class="tags">${(a.tags ?? []).map((t) => `<span class="tag">#${esc(t)}</span>`).join("")}</div>
  <div class="cta">📊 最新の高騰・下落ランキングと全記事は
    <a href="../../">ポケカ海外相場モニター</a> で毎日自動更新中(Cardmarket価格×円換算)</div>
  <footer>本記事は集計データからAIが自動生成し、数値の照合チェックを通過したものです。
  価格はCardmarket(欧州)のユーロ建て平均価格と円換算の参考値であり、日本国内のショップ価格ではありません。
  売買・投資の助言ではありません。本サイトは株式会社ポケモン・Cardmarketと無関係の非公式ファンサイトです。</footer>
</div>
</body>
</html>`;
}

export async function generatePages() {
  const { articles } = JSON.parse(
    await fs.readFile(path.join(CONTENT_DIR, "articles.json"), "utf8"),
  );

  for (const a of articles) {
    const dir = path.join(DIST, "articles", a.id);
    await fs.mkdir(dir, { recursive: true });
    await fs.writeFile(path.join(dir, "index.html"), articleHtml(a));
  }

  // sitemap.xml(トップ+全記事)。public/の静的sitemapより優先される
  const urls = [
    { loc: SITE_URL, freq: "daily", pri: "1.0" },
    ...articles.map((a) => ({
      loc: `${SITE_URL}articles/${a.id}/`,
      freq: "monthly",
      pri: "0.7",
      lastmod: a.createdAt.slice(0, 10),
    })),
  ];
  const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls
  .map(
    (u) =>
      `  <url><loc>${u.loc}</loc>${u.lastmod ? `<lastmod>${u.lastmod}</lastmod>` : ""}<changefreq>${u.freq}</changefreq><priority>${u.pri}</priority></url>`,
  )
  .join("\n")}
</urlset>
`;
  await fs.writeFile(path.join(DIST, "sitemap.xml"), sitemap);
  console.log(`gen-pages: ${articles.length} article pages + sitemap generated`);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  generatePages().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
