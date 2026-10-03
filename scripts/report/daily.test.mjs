// 毎朝の数字(daily.mjs)のテスト。外部のサービスは偽の fetch で置き換える
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  amoTargets,
  chrome,
  firefox,
  format,
  notify,
  parseChrome,
  post,
  stripe,
} from "./daily.mjs";

const json = (body, status = 200) => new Response(JSON.stringify(body), { status });

test("store/amo.json がある拡張をすべて対象にする", () => {
  const slugs = amoTargets().map((t) => t.slug);
  for (const s of ["toreca-kaigai-checker", "job-salary-checker", "realty-price-checker"])
    assert.ok(slugs.includes(s), s);
});

test("Firefox: 公開中は数字、審査中(認証が要る)は未公開と書く", async () => {
  const fetchImpl = async (url) =>
    url.includes("/a-pub/")
      ? json({
          status: "public",
          current_version: { version: "0.1.2" },
          average_daily_users: 12,
          weekly_downloads: 34,
          ratings: { average: 4.5, count: 2 },
        })
      : json({ detail: "Authentication credentials were not provided." }, 401);
  const [pub, wait] = await firefox(
    [
      { name: "A", slug: "a-pub" },
      { name: "B", slug: "b-wait" },
    ],
    fetchImpl,
  );
  assert.deepEqual(pub, {
    name: "A",
    status: "公開",
    version: "0.1.2",
    users: 12,
    downloads: 34,
    rating: "4.5(2件)",
  });
  assert.equal(wait.status, "審査中(未公開)");
});

test("Chrome: 公開ページから版と利用者数を読む(数が無ければ null)", async () => {
  assert.deepEqual(parseChrome('<x>"0.3.0"</x><div>1,234 users</div>'), {
    version: "0.3.0",
    users: 1234,
  });
  assert.deepEqual(parseChrome('<x>"0.1.0"</x>'), { version: "0.1.0", users: null });
  const [r] = await chrome(
    [{ name: "T", id: "x" }],
    async () => new Response("err", { status: 500 }),
  );
  assert.match(r.status, /取得できず/);
});

test("通知サービス: D1 から登録者・有料・カード数を数える", async () => {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push(url);
    if (url.includes("/d1/database?name="))
      return json({ success: true, result: [{ name: "toreca-notify", uuid: "db1" }] });
    const { sql } = JSON.parse(init.body);
    const row = sql.includes("FROM subscribers")
      ? { total: 5, active: 4, pro: 1, fresh: 2 }
      : { watches: 9 };
    return json({ success: true, result: [{ results: [row] }] });
  };
  assert.deepEqual(await notify({ accountId: "acc", token: "t", fetchImpl }), {
    total: 5,
    active: 4,
    pro: 1,
    fresh: 2,
    watches: 9,
  });
  assert.equal(await notify({ accountId: "", token: "" }), null, "Secrets が無ければ飛ばす");
});

test("Stripe: 契約中の数と、直近24時間の支払い済み(返金分を除く)の合計", async () => {
  const fetchImpl = async (url) =>
    url.includes("subscriptions")
      ? json({ data: [{}, {}], has_more: false })
      : json({
          data: [
            { paid: true, refunded: false, amount: 300, amount_refunded: 0 },
            { paid: true, refunded: true, amount: 300, amount_refunded: 300 },
            { paid: false, refunded: false, amount: 300 },
          ],
        });
  assert.deepEqual(await stripe({ key: "sk_live_x", fetchImpl }), {
    live: true,
    active: 2,
    more: false,
    sales: 300,
    count: 1,
  });
  assert.equal(await stripe({ key: "" }), null);
});

test("まとめの文章と、Issue が無ければ作ってからコメントする", async () => {
  const body = format({
    date: "2026/10/3",
    ff: [{ name: "A", status: "公開", version: "0.1.2", users: 12, downloads: 34, rating: "-" }],
    cr: [{ name: "T", status: "公開", version: "0.3.0", users: null }],
    nt: null,
    st: { live: false, active: 0, more: false, sales: 0, count: 0 },
    errors: { notify: "boom" },
  });
  assert.match(body, /\| A \| 公開 \| 0\.1\.2 \| 12 \| 34 \|/);
  assert.match(body, /少数のため非表示/);
  assert.match(body, /取得できず\(boom\)/);
  assert.match(body, /テストモード・契約中 0 件/);

  const seen = [];
  const fetchImpl = async (url, init = {}) => {
    seen.push(`${init.method ?? "GET"} ${url.replace("https://api.github.com/repos/o/r", "")}`);
    if (url.includes("labels=daily-report")) return json([]);
    if (url.endsWith("/issues")) return json({ number: 7 }, 201);
    return json({}, 201);
  };
  assert.equal(await post(body, { token: "t", repo: "o/r", fetchImpl }), 7);
  assert.deepEqual(seen, [
    "GET /issues?labels=daily-report&state=open&per_page=1",
    "POST /issues",
    "POST /issues/7/comments",
  ]);
});
