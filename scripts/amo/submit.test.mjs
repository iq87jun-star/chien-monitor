// scripts/amo/submit.mjs のテスト。AMO の API をまねた手元のサーバーに向けて、
// 新規登録・新しい版の提出・提出済みの版・自動検証のエラーの流れを確かめる。
//   node --test scripts/amo/
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { submit, buildSubmission, AmoError } from "./submit.mjs";

process.env.AMO_POLL_MS = "10";
process.env.AMO_RETRY_SCALE = "0.01";
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const GUID = "sample@pokeca-kaigai.com";
const SECRET = "test-secret";

// 拡張のフォルダの最小限のひな形(manifest・listing.md・amo.json・スクリーンショット・Firefox 用 zip)
function fixture(version = "1.2.0") {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "amo-"));
  const manifest = {
    manifest_version: 3,
    name: "サンプル チェッカー",
    version,
    description: "サンプルの概要です。",
  };
  fs.writeFileSync(path.join(dir, "manifest.json"), JSON.stringify(manifest));
  fs.mkdirSync(path.join(dir, "store", "screenshots"), { recursive: true });
  fs.writeFileSync(
    path.join(dir, "store", "listing.md"),
    "# 掲載\n\n## 説明\n\n```\n1行目\n\n■ 2つ目の節\n```\n\n## 画像\n",
  );
  fs.writeFileSync(path.join(dir, "store", "screenshots", "1.png"), "png1");
  fs.writeFileSync(path.join(dir, "store", "screenshots", "2.png"), "png2");
  fs.writeFileSync(
    path.join(dir, "store", "amo.json"),
    JSON.stringify({
      slug: "sample-checker",
      categories: ["other"],
      homepage: "https://pokeca-kaigai.com/",
      privacy_policy: "何も収集しません。",
      approval_notes: "Test on example.com.",
      screenshots: ["store/screenshots/1.png", "store/screenshots/2.png"],
    }),
  );
  const src = path.join(dir, "ffsrc");
  fs.mkdirSync(src);
  fs.writeFileSync(
    path.join(src, "manifest.json"),
    JSON.stringify({ ...manifest, browser_specific_settings: { gecko: { id: GUID } } }),
  );
  fs.mkdirSync(path.join(dir, "dist", "firefox"), { recursive: true });
  execFileSync(
    "zip",
    ["-q", path.join(dir, "dist", "firefox", `sample-${version}-firefox.zip`), "manifest.json"],
    { cwd: src },
  );
  return dir;
}

// AMO をまねたサーバー。state を変えて「未登録/登録済み/検証エラー」を作る
const state = { addon: null, versions: [], previews: 0, uploadValid: true, throttle: 0, calls: [] };
let server;
let base;

function verifyJwt(header) {
  const [h, p, sig] = header.replace(/^JWT /, "").split(".");
  const ok = crypto.createHmac("sha256", SECRET).update(`${h}.${p}`).digest("base64url") === sig;
  const claims = JSON.parse(Buffer.from(p, "base64url").toString());
  return ok && claims.iss === "test-issuer" && claims.exp > claims.iat;
}

before(async () => {
  server = http.createServer((req, res) => {
    let body = "";
    req.setEncoding("latin1");
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      const send = (code, obj) => {
        res.writeHead(code, { "Content-Type": "application/json" });
        res.end(obj === undefined ? "" : JSON.stringify(obj));
      };
      if (!verifyJwt(req.headers.authorization ?? "")) return send(401, { detail: "bad jwt" });
      const url = new URL(req.url, "http://x");
      const json = req.headers["content-type"]?.startsWith("application/json")
        ? JSON.parse(Buffer.from(body, "latin1").toString())
        : null;
      state.calls.push({ method: req.method, path: url.pathname, json, raw: body });
      const addonPath = `/api/v5/addons/addon/${encodeURIComponent(GUID)}/`;
      const p = url.pathname;
      if (req.method === "POST" && p === "/api/v5/addons/upload/")
        return send(201, { uuid: "u1", processed: false });
      if (req.method === "GET" && p === "/api/v5/addons/upload/u1/") {
        return send(
          200,
          state.uploadValid
            ? { uuid: "u1", processed: true, valid: true, validation: { warnings: 0 } }
            : {
                uuid: "u1",
                processed: true,
                valid: false,
                validation: {
                  messages: [
                    { type: "error", message: "manifest が壊れています", file: "manifest.json" },
                  ],
                },
              },
        );
      }
      if (req.method === "POST" && p === "/api/v5/addons/addon/" && state.throttle > 0) {
        state.throttle--;
        return send(429, { detail: "Request was throttled. Expected available in 1 seconds." });
      }
      if (req.method === "POST" && p === "/api/v5/addons/addon/") {
        state.addon = {
          slug: json.slug,
          url: "https://addons.mozilla.org/ja/firefox/addon/sample-checker/",
          previews: [],
        };
        state.versions.push({ version: "1.2.0" });
        return send(201, state.addon);
      }
      if (p === addonPath && req.method === "GET")
        return state.addon
          ? send(200, { ...state.addon, previews: Array(state.previews).fill({}) })
          : send(404, { detail: "Not found." });
      if (p === addonPath && req.method === "PATCH")
        return send(200, { ...state.addon, previews: Array(state.previews).fill({}) });
      if (p === `${addonPath}versions/` && req.method === "GET")
        return send(200, { results: state.versions });
      if (p === `${addonPath}versions/` && req.method === "POST")
        return send(201, { version: "x" });
      if (p === `${addonPath}eula_policy/` && req.method === "PATCH") return send(200, {});
      if (p === `${addonPath}previews/` && req.method === "POST") {
        state.previews++;
        return send(201, {});
      }
      send(500, { detail: `unexpected ${req.method} ${p}` });
    });
  });
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  base = `http://127.0.0.1:${server.address().port}`;
});
after(() => server.close());

const env = () => ({
  AMO_JWT_ISSUER: "test-issuer",
  AMO_JWT_SECRET: SECRET,
  AMO_API_BASE: base,
  AMO_SUPPORT_EMAIL: "help@example.com",
});
const quiet = () => {};
const reset = (s) =>
  Object.assign(
    state,
    { addon: null, versions: [], previews: 0, uploadValid: true, throttle: 0, calls: [] },
    s,
  );

test("未登録なら新規登録し、掲載情報・プライバシーポリシー・スクリーンショットを送る", async () => {
  reset();
  const r = await submit(fixture(), { env: env(), log: quiet });
  assert.equal(r.action, "created");
  const create = state.calls.find((c) => c.method === "POST" && c.path === "/api/v5/addons/addon/");
  assert.equal(create.json.slug, "sample-checker");
  assert.deepEqual(create.json.name, { ja: "サンプル チェッカー" });
  assert.deepEqual(create.json.summary, { ja: "サンプルの概要です。" });
  assert.deepEqual(create.json.description, { ja: "1行目\n\n■ 2つ目の節" });
  assert.deepEqual(create.json.categories, { firefox: ["other"] });
  assert.deepEqual(create.json.support_email, { ja: "help@example.com" });
  assert.deepEqual(create.json.version, {
    upload: "u1",
    license: "all-rights-reserved",
    approval_notes: "Test on example.com.",
    compatibility: ["firefox"],
  });
  const upload = state.calls.find((c) => c.path === "/api/v5/addons/upload/");
  assert.match(upload.raw, /name="channel"\r\n\r\nlisted/);
  const policy = state.calls.find((c) => c.path.endsWith("/eula_policy/"));
  assert.deepEqual(policy.json, { privacy_policy: { ja: "何も収集しません。" } });
  assert.equal(state.previews, 2);
});

test("登録済みなら掲載情報を同期してから新しい版を提出し、スクリーンショットは重ねない", async () => {
  reset({
    addon: { slug: "sample-checker", previews: [] },
    versions: [{ version: "1.1.0" }],
    previews: 2,
  });
  const r = await submit(fixture("1.2.0"), { env: env(), log: quiet });
  assert.equal(r.action, "updated");
  const order = state.calls.map((c) => `${c.method} ${c.path.replace(/.*\/addon\/[^/]+\//, "")}`);
  assert.ok(order.indexOf("PATCH ") < order.indexOf("POST versions/"), `同期→提出の順: ${order}`);
  const version = state.calls.find((c) => c.method === "POST" && c.path.endsWith("/versions/"));
  assert.equal(version.json.upload, "u1");
  assert.ok(
    !state.calls.some((c) => c.path.endsWith("/previews/")),
    "スクリーンショットが既にあれば送らない",
  );
});

test("同じ版が提出済みなら、アップロードせず掲載情報の同期だけ", async () => {
  reset({ addon: { slug: "sample-checker" }, versions: [{ version: "1.2.0" }], previews: 2 });
  const r = await submit(fixture("1.2.0"), { env: env(), log: quiet });
  assert.equal(r.action, "unchanged");
  assert.ok(!state.calls.some((c) => c.path === "/api/v5/addons/upload/"));
  assert.ok(state.calls.some((c) => c.method === "PATCH" && c.path.endsWith("/eula_policy/")));
});

test("自動検証でエラーなら、その内容を出して止まり、登録しない", async () => {
  reset({ uploadValid: false });
  await assert.rejects(
    submit(fixture(), { env: env(), log: quiet }),
    (e) => e instanceof AmoError && /manifest が壊れています/.test(e.message),
  );
  assert.ok(!state.calls.some((c) => c.method === "POST" && c.path === "/api/v5/addons/addon/"));
});

test("API キーが無ければ通信せずに止まる。--dry-run は通信しない", async () => {
  reset();
  await assert.rejects(submit(fixture(), { env: {}, log: quiet }), /AMO_JWT_ISSUER/);
  const r = await submit(fixture(), { dryRun: true, env: {}, log: quiet });
  assert.equal(r.action, "dry-run");
  assert.equal(state.calls.length, 0);
});

test("3つの拡張の amo.json・listing.md・スクリーンショットが揃っている", () => {
  for (const d of ["extension", "job-extension", "realty-extension"]) {
    const dir = path.join(ROOT, d);
    if (!fs.existsSync(path.join(dir, "dist", "firefox")))
      execFileSync("node", ["scripts/pack.mjs"], { cwd: dir, stdio: "ignore" });
    const s = buildSubmission(dir);
    assert.match(s.guid, /@pokeca-kaigai\.com$/, d);
    assert.ok([...s.metadata.description.ja].length > 250, `${d} の説明が短すぎる`);
    assert.ok(s.screenshots.length >= 2, d);
  }
});

test("送りすぎの制限(429)なら、示された秒数だけ待って送り直す", async () => {
  reset({ throttle: 2 });
  const logs = [];
  const r = await submit(fixture(), { env: env(), log: (m) => logs.push(m) });
  assert.equal(r.action, "created");
  const creates = state.calls.filter(
    (c) => c.method === "POST" && c.path === "/api/v5/addons/addon/",
  );
  assert.equal(creates.length, 3, "429 が2回 → 3回目で登録");
  assert.equal(logs.filter((m) => /429/.test(m)).length, 2);
});

test("スクリーンショットが途中までなら、足りない分だけ登録する", async () => {
  reset({ addon: { slug: "sample-checker" }, versions: [{ version: "1.2.0" }], previews: 1 });
  await submit(fixture("1.2.0"), { env: env(), log: quiet });
  const posted = state.calls.filter((c) => c.path.endsWith("/previews/"));
  assert.equal(posted.length, 1);
  assert.match(posted[0].raw, /filename="2\.png"/);
  assert.match(posted[0].raw, /name="position"\r\n\r\n1/);
});

test("429 の待ち時間の合計が上限を超えたら、待たずに止める", async () => {
  reset({ throttle: 5 });
  process.env.AMO_RETRY_BUDGET_SEC = "2";
  try {
    await assert.rejects(submit(fixture(), { env: env(), log: quiet }), /中断しました/);
  } finally {
    delete process.env.AMO_RETRY_BUDGET_SEC;
  }
});
