// デプロイ時に全サイトの記事を含むsitemap.xmlを site-dist/ に生成する
import fs from "node:fs/promises";

const BASE = "https://game-souba.com";
const SITES = ["poe2", "poe1", "tarkov", "ff14"];

const urls = [{ loc: `${BASE}/`, changefreq: "daily", priority: "1.0" }];

for (const site of SITES) {
  urls.push({ loc: `${BASE}/${site}/`, changefreq: "hourly", priority: "0.9" });
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
