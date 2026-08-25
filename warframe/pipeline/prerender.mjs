// ビルド後に記事を1本ずつ静的HTMLページとして書き出す(SEO用)
// 出力: dist/articles/<id>/index.html と dist/articles/index.html(一覧)
import fs from "node:fs/promises";
import path from "node:path";
import { ROOT, CONTENT_DIR } from "./config.mjs";

const SITE = {
  name: "Warframe相場モニター",
  emoji: "🪐",
  baseUrl: "https://game-souba.com/warframe/",
  description:
    "Warframeのプライムセット・アルケイン相場(warframe.market)を自動集計して日本語で解説するサイト",
  gaId: "G-7LZS5DCBSG",
  colors: {
    bg: "#0D0B14",
    surface: "#16121F",
    outline: "#2C2440",
    accent: "#8FD8CE",
    text: "#E6E4EC",
    mid: "#A8A2B8",
  },
};

const esc = (s) =>
  String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

const fmtDate = (iso) => {
  const d = new Date(iso);
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`;
};

const C = SITE.colors;

const head = (title, desc, url) => `<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<meta name="description" content="${esc(desc)}" />
<title>${esc(title)}</title>
<link rel="canonical" href="${url}" />
<meta property="og:type" content="article" />
<meta property="og:site_name" content="${esc(SITE.name)}" />
<meta property="og:title" content="${esc(title)}" />
<meta property="og:description" content="${esc(desc)}" />
<meta property="og:url" content="${url}" />
<meta property="og:image" content="${SITE.baseUrl}ogp.png" />
<meta name="twitter:card" content="summary_large_image" />
<script async src="https://www.googletagmanager.com/gtag/js?id=${SITE.gaId}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', '${SITE.gaId}');
</script>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:${C.bg}; color:${C.text}; line-height:1.8;
    font-family:'Hiragino Sans','Noto Sans JP','Yu Gothic',system-ui,sans-serif; }
  .wrap { max-width:760px; margin:0 auto; padding:20px 16px 60px; }
  header { border-bottom:1px solid ${C.outline}; padding:14px 16px; background:${C.surface}; }
  header a { color:${C.accent}; text-decoration:none; font-weight:700; font-size:15px; }
  h1 { font-size:22px; line-height:1.5; margin:18px 0 8px; color:${C.text}; }
  .meta { font-size:12px; color:${C.mid}; margin-bottom:18px; }
  .summary { background:${C.surface}; border:1px solid ${C.outline}; border-radius:12px;
    padding:14px 16px; font-size:14px; color:${C.mid}; margin-bottom:22px; }
  h2 { font-size:16px; color:${C.accent}; margin:26px 0 8px; }
  p.body { font-size:14px; white-space:pre-wrap; }
  .nav { margin-top:36px; border-top:1px solid ${C.outline}; padding-top:18px; }
  .nav h3 { font-size:14px; color:${C.mid}; margin-bottom:10px; }
  .nav a { display:block; color:${C.accent}; font-size:13px; text-decoration:none; margin-bottom:8px; }
  .backlink { display:inline-block; margin-top:20px; color:${C.bg}; background:${C.accent};
    padding:8px 20px; border-radius:999px; font-size:13px; font-weight:700; text-decoration:none; }
  footer { font-size:11px; color:${C.mid}; margin-top:40px; }
  ul.list { list-style:none; }
  ul.list li { margin-bottom:14px; }
  ul.list a { color:${C.accent}; font-size:15px; text-decoration:none; font-weight:600; }
  ul.list .d { font-size:11px; color:${C.mid}; }
</style>`;

const headerNav = `<header><a href="../../">${SITE.emoji} ${esc(SITE.name)}</a></header>`;
const headerNavTop = `<header><a href="../">${SITE.emoji} ${esc(SITE.name)}</a></header>`;

function articleHtml(a, others) {
  const url = `${SITE.baseUrl}articles/${a.id}/`;
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    headline: a.title,
    datePublished: a.createdAt,
    description: a.summary,
    author: { "@type": "Organization", name: SITE.name },
    mainEntityOfPage: url,
  };
  const sections = a.sections
    .map((s) => `<h2>${esc(s.heading)}</h2>\n<p class="body">${esc(s.body)}</p>`)
    .join("\n");
  const otherLinks = others
    .slice(0, 8)
    .map((o) => `<a href="../${o.id}/">${esc(o.title)}</a>`)
    .join("\n");
  return `<!DOCTYPE html>
<html lang="ja">
<head>
${head(`${a.title} | ${SITE.name}`, a.summary.slice(0, 120), url)}
<script type="application/ld+json">${JSON.stringify(jsonLd)}</script>
</head>
<body>
${headerNav}
<div class="wrap">
<article>
<h1>${esc(a.title)}</h1>
<div class="meta">${fmtDate(a.createdAt)} ・ 市場動向 ・ 自動集計データからAIが生成(数値照合チェック済み)</div>
<div class="summary">${esc(a.summary)}</div>
${sections}
</article>
<a class="backlink" href="../../">最新の相場データを見る →</a>
<div class="nav">
<h3>過去の記事</h3>
${otherLinks}
<a href="../">記事一覧へ →</a>
</div>
<footer>${esc(SITE.name)} — ${esc(SITE.description)}</footer>
</div>
</body>
</html>`;
}

function indexHtml(articles) {
  const url = `${SITE.baseUrl}articles/`;
  const items = articles
    .map(
      (a) =>
        `<li><a href="${a.id}/">${esc(a.title)}</a><div class="d">${fmtDate(a.createdAt)} ・ ${esc(a.summary.slice(0, 80))}…</div></li>`,
    )
    .join("\n");
  return `<!DOCTYPE html>
<html lang="ja">
<head>
${head(`記事一覧 | ${SITE.name}`, SITE.description, url)}
</head>
<body>
${headerNavTop}
<div class="wrap">
<h1>記事一覧</h1>
<div class="meta">自動集計データからAIが生成した市況レポートのアーカイブです</div>
<ul class="list">
${items}
</ul>
<a class="backlink" href="../">最新の相場データを見る →</a>
<footer>${esc(SITE.name)} — ${esc(SITE.description)}</footer>
</div>
</body>
</html>`;
}

const distArticles = path.join(ROOT, "dist", "articles");
const data = JSON.parse(
  await fs.readFile(path.join(CONTENT_DIR, "articles.json"), "utf8").catch(() => '{"articles":[]}'),
);
const articles = data.articles ?? [];

await fs.mkdir(distArticles, { recursive: true });
for (const a of articles) {
  const others = articles.filter((o) => o.id !== a.id);
  const dir = path.join(distArticles, a.id);
  await fs.mkdir(dir, { recursive: true });
  await fs.writeFile(path.join(dir, "index.html"), articleHtml(a, others));
}
await fs.writeFile(path.join(distArticles, "index.html"), indexHtml(articles));
console.log(`prerender: ${articles.length} article pages written`);
