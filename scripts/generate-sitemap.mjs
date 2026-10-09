// デプロイ時に、運用中のサイト(ff14 と原神・スタレ ツール)の記事を含むsitemap.xmlを site-dist/ に生成する
import fs from "node:fs/promises";

const BASE = "https://game-souba.com";
const SITES = ["ff14"];

const urls = [{ loc: `${BASE}/`, changefreq: "daily", priority: "1.0" }];

// 原神・スタレ ツール(hoyo/)
urls.push({ loc: `${BASE}/hoyo/`, changefreq: "weekly", priority: "0.9" });
for (const page of ["souba", "satei", "jisseki", "theater"]) urls.push({ loc: `${BASE}/hoyo/${page}/`, changefreq: "weekly", priority: "0.8" });

for (const site of SITES) {
  urls.push({ loc: `${BASE}/${site}/`, changefreq: "daily", priority: "0.9" });
  urls.push({ loc: `${BASE}/${site}/articles/`, changefreq: "daily", priority: "0.6" });
  let articles = [];
  try {
    articles = JSON.parse(await fs.readFile(`${site}/content/articles.json`, "utf8")).articles ?? [];
  } catch {
    // 記事なしのサイトはトップだけ載せる
  }
  for (const a of articles) {
    urls.push({
      loc: `${BASE}/${site}/articles/${a.id}/`,
      lastmod: a.createdAt?.slice(0, 10),
      changefreq: "monthly",
      priority: "0.7",
    });
  }
}

const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls
  .map(
    (u) =>
      ` <url>\n  <loc>${u.loc}</loc>\n` +
      (u.lastmod ? `  <lastmod>${u.lastmod}</lastmod>\n` : "") +
      `  <changefreq>${u.changefreq}</changefreq>\n  <priority>${u.priority}</priority>\n </url>`,
  )
  .join("\n")}
</urlset>
`;

await fs.writeFile("site-dist/sitemap.xml", xml);
console.log(`sitemap: ${urls.length} URLs written`);
