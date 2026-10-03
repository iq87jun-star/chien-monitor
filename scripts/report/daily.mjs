// 毎朝の数字(GitHub Actions の daily-report から実行)。
// 拡張(Firefox・Chrome)の利用者数、通知サービスの登録者数、Stripe の有料プランをまとめ、
// GitHub の Issue(ラベル daily-report)にコメントする。取れなかった項目は「取得できず」と書いて続ける。
//
// 環境変数(無いものは飛ばす):
//   GITHUB_TOKEN / GITHUB_REPOSITORY … Issue へのコメント(無ければ標準出力だけ)
//   CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID … 通知サービスの登録者数(D1)
//   STRIPE_SECRET_KEY … 有料プランの契約数・直近24時間の売上
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

// Chrome ウェブストアの ID(公開・審査に出したもの)。新しい拡張を出したらここに足す
export const CHROME = [
  { name: "トレカ海外相場チェッカー", id: "ldjebhejnobgblifnojjfhfaimjfoece" },
  { name: "求人 年収チェッカー", id: "ilamebemifljejhjgoeioedgfohclefe" },
];

const fmt = (n) => (n == null ? "-" : Number(n).toLocaleString("ja-JP"));

// store/amo.json がある拡張すべて(amo-publish と同じ探し方)
export function amoTargets(root = ROOT) {
  return fs
    .readdirSync(root, { withFileTypes: true })
    .filter((d) => d.isDirectory() && fs.existsSync(path.join(root, d.name, "store", "amo.json")))
    .map((d) => {
      const amo = JSON.parse(fs.readFileSync(path.join(root, d.name, "store", "amo.json"), "utf8"));
      const manifest = JSON.parse(
        fs.readFileSync(path.join(root, d.name, "manifest.json"), "utf8"),
      );
      return { name: manifest.short_name ?? manifest.name, slug: amo.slug };
    });
}

export async function firefox(targets, fetchImpl = fetch) {
  return Promise.all(
    targets.map(async ({ name, slug }) => {
      try {
        const res = await fetchImpl(`https://addons.mozilla.org/api/v5/addons/addon/${slug}/`);
        // 公開前(審査中)は認証なしでは見えない
        if (res.status === 401 || res.status === 403 || res.status === 404)
          return { name, status: "審査中(未公開)" };
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const j = await res.json();
        return {
          name,
          status: j.status === "public" ? "公開" : j.status,
          version: j.current_version?.version,
          users: j.average_daily_users,
          downloads: j.weekly_downloads,
          rating: j.ratings?.count ? `${j.ratings.average.toFixed(1)}(${j.ratings.count}件)` : "-",
        };
      } catch (err) {
        return { name, status: `取得できず(${err.message})` };
      }
    }),
  );
}

// Chrome は公開ページから版と利用者数を読む(利用者が少ないうちは数が出ない)
export function parseChrome(html) {
  const version = /"(\d+\.\d+\.\d+)"/.exec(html)?.[1] ?? null;
  const users = /([\d,]+)\s*(?:users|人のユーザー)/.exec(html)?.[1]?.replace(/,/g, "") ?? null;
  return { version, users: users == null ? null : Number(users) };
}

export async function chrome(items = CHROME, fetchImpl = fetch) {
  return Promise.all(
    items.map(async ({ name, id }) => {
      try {
        const res = await fetchImpl(`https://chromewebstore.google.com/detail/${id}?hl=en`, {
          headers: { "user-agent": "Mozilla/5.0" },
        });
        if (res.status === 404) return { name, status: "未公開" };
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return { name, status: "公開", ...parseChrome(await res.text()) };
      } catch (err) {
        return { name, status: `取得できず(${err.message})` };
      }
    }),
  );
}

export async function notify({ accountId, token, fetchImpl = fetch, now = new Date() }) {
  if (!accountId || !token) return null;
  const { findDatabase, fromRest } = await import("../../notify/src/db.js");
  const databaseId = await findDatabase({ accountId, token, name: "toreca-notify", fetchImpl });
  const db = fromRest({ accountId, databaseId, token, fetchImpl });
  const since = new Date(now.getTime() - 24 * 3600e3).toISOString();
  const [s] = await db.all(
    `SELECT COUNT(*) AS total,
            SUM(CASE WHEN active = 1 THEN 1 ELSE 0 END) AS active,
            SUM(CASE WHEN plan = 'pro' THEN 1 ELSE 0 END) AS pro,
            SUM(CASE WHEN created_at >= ? THEN 1 ELSE 0 END) AS fresh
       FROM subscribers`,
    [since],
  );
  const [w] = await db.all("SELECT COUNT(*) AS watches FROM watches");
  return {
    total: s.total ?? 0,
    active: s.active ?? 0,
    pro: s.pro ?? 0,
    fresh: s.fresh ?? 0,
    watches: w.watches ?? 0,
  };
}

export async function stripe({ key, fetchImpl = fetch, now = new Date() }) {
  if (!key) return null;
  const get = async (p) => {
    const res = await fetchImpl(`https://api.stripe.com/v1/${p}`, {
      headers: { authorization: `Bearer ${key}` },
    });
    const j = await res.json();
    if (!res.ok) throw new Error(j.error?.message ?? `HTTP ${res.status}`);
    return j;
  };
  const subs = await get("subscriptions?status=active&limit=100");
  const since = Math.floor(now.getTime() / 1000) - 24 * 3600;
  const charges = await get(`charges?limit=100&created[gte]=${since}`);
  const paid = charges.data.filter((c) => c.paid && !c.refunded);
  return {
    live: key.startsWith("sk_live_") || key.startsWith("rk_live_"),
    active: subs.data.length,
    more: Boolean(subs.has_more), // 100件を超える時
    sales: paid.reduce((sum, c) => sum + c.amount - (c.amount_refunded ?? 0), 0),
    count: paid.length,
  };
}

export function format({ date, ff, cr, nt, st, errors = {} }) {
  const lines = [`## ${date} の数字`, ""];
  lines.push(
    "### Firefox",
    "",
    "| 拡張 | 状態 | 版 | 1日の利用者 | 週のDL | 評価 |",
    "|---|---|---|---|---|---|",
  );
  for (const a of ff)
    lines.push(
      `| ${a.name} | ${a.status} | ${a.version ?? "-"} | ${fmt(a.users)} | ${fmt(a.downloads)} | ${a.rating ?? "-"} |`,
    );
  lines.push("", "### Chrome", "", "| 拡張 | 状態 | 公開中の版 | 利用者 |", "|---|---|---|---|");
  for (const c of cr)
    lines.push(
      `| ${c.name} | ${c.status} | ${c.version ?? "-"} | ${c.users == null ? "少数のため非表示" : fmt(c.users)} |`,
    );
  lines.push("", "### トレカ値下がり通知");
  if (nt)
    lines.push(
      "",
      `- 登録者 ${fmt(nt.total)} 人(通知が届く状態 ${fmt(nt.active)} 人・直近24時間の新規 ${fmt(nt.fresh)} 人)`,
      `- 有料プラン ${fmt(nt.pro)} 人・見張っているカード ${fmt(nt.watches)} 枚`,
    );
  else
    lines.push(
      "",
      `- 取得できず${errors.notify ? `(${errors.notify})` : "(Cloudflare の Secrets が未設定)"}`,
    );
  lines.push("", "### Stripe(有料プラン)");
  if (st)
    lines.push(
      "",
      `- ${st.live ? "本番" : "テストモード"}・契約中 ${fmt(st.active)}${st.more ? " 件以上" : " 件"}`,
      `- 直近24時間の売上 ${fmt(st.sales)} 円(${st.count} 件)`,
    );
  else
    lines.push(
      "",
      `- 取得できず${errors.stripe ? `(${errors.stripe})` : "(STRIPE_SECRET_KEY が未設定)"}`,
    );
  lines.push(
    "",
    "計算API(RapidAPI)の購読者・呼び出し数は https://rapidapi.com/workspace で見られます(API で取れないため)。",
  );
  return lines.join("\n");
}

// ラベル daily-report の開いた Issue にコメントする(無ければ作る)
export async function post(body, { token, repo, fetchImpl = fetch }) {
  const gh = async (p, init = {}) => {
    const res = await fetchImpl(`https://api.github.com/repos/${repo}${p}`, {
      ...init,
      headers: {
        authorization: `Bearer ${token}`,
        accept: "application/vnd.github+json",
        "content-type": "application/json",
      },
    });
    if (!res.ok) throw new Error(`GitHub ${p}: HTTP ${res.status}`);
    return res.json();
  };
  const open = await gh("/issues?labels=daily-report&state=open&per_page=1");
  let number = open[0]?.number;
  if (!number) {
    const made = await gh("/issues", {
      method: "POST",
      body: JSON.stringify({
        title: "毎朝の数字(自動)",
        labels: ["daily-report"],
        body: "拡張の利用者数・通知サービスの登録者数・有料プランの売上を、毎朝ここにコメントします(.github/workflows/daily-report.yml)。",
      }),
    });
    number = made.number;
  }
  await gh(`/issues/${number}/comments`, { method: "POST", body: JSON.stringify({ body }) });
  return number;
}

export async function main(env = process.env, fetchImpl = fetch) {
  const now = new Date();
  const date = now.toLocaleDateString("ja-JP", { timeZone: "Asia/Tokyo" });
  const errors = {};
  const [ff, cr, nt, st] = await Promise.all([
    firefox(amoTargets(), fetchImpl),
    chrome(CHROME, fetchImpl),
    notify({
      accountId: env.CLOUDFLARE_ACCOUNT_ID,
      token: env.CLOUDFLARE_API_TOKEN,
      fetchImpl,
      now,
    }).catch((e) => ((errors.notify = e.message), null)),
    stripe({ key: env.STRIPE_SECRET_KEY, fetchImpl, now }).catch(
      (e) => ((errors.stripe = e.message), null),
    ),
  ]);
  const body = format({ date, ff, cr, nt, st, errors });
  console.log(body);
  if (env.GITHUB_STEP_SUMMARY) fs.appendFileSync(env.GITHUB_STEP_SUMMARY, body + "\n");
  if (env.GITHUB_TOKEN && env.GITHUB_REPOSITORY) {
    const n = await post(body, { token: env.GITHUB_TOKEN, repo: env.GITHUB_REPOSITORY, fetchImpl });
    console.log(`Issue #${n} にコメントしました`);
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) await main();
