// Firefox アドオン(AMO)への自動提出。3つの拡張で共通に使う。
//   node scripts/amo/submit.mjs <拡張のフォルダ> [--dry-run]
//
// 先に拡張のフォルダで `npm run pack` を実行し、dist/firefox/<名前>-<版>-firefox.zip を作っておく。
// 1) zip をアップロードして AMO の自動検証を待つ(エラーがあれば内容を出して止まる)
// 2) まだ AMO に無ければ新規登録、あれば新しい版として提出(同じ版が提出済みなら飛ばす)
// 3) 掲載情報(名前・概要・説明・カテゴリ・ホームページ・サポートメール)とプライバシーポリシーを同期
// 4) スクリーンショットが1枚も無ければ登録する
//
// 名前・概要は manifest.json、説明は store/listing.md の「## 説明」の ``` の中、
// それ以外は store/amo.json から取る(Chrome と同じ文章を1か所で管理する)。
//
// 環境変数:
//   AMO_JWT_ISSUER / AMO_JWT_SECRET … AMO の API キー(https://addons.mozilla.org/developers/addon/api/key/)
//   AMO_SUPPORT_EMAIL               … ストアに載せるサポートメール(任意。公開される)
//   AMO_API_BASE                    … 既定 https://addons.mozilla.org(テストでモックに向ける時だけ)
// --dry-run では通信せず、送る内容を確かめて表示するだけ(PR の CI で使う)。
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { pathToFileURL } from "node:url";

const SLUG_RE = /^(?!\d+$)[\p{L}\p{N}_~-]+$/u;
const CATEGORIES = new Set([
  "alerts-updates",
  "appearance",
  "bookmarks",
  "download-management",
  "feeds-news-blogging",
  "games-entertainment",
  "language-support",
  "photos-music-videos",
  "privacy-security",
  "search-tools",
  "shopping",
  "social-communication",
  "tabs",
  "web-development",
  "other",
]);
const LOCALE = "ja";
const POLL_LIMIT_MS = 15 * 60 * 1000;

export class AmoError extends Error {}
// 送りすぎの制限で中断した(後で再実行すれば続きから行える)。終了コード 75 で知らせる
export class AmoThrottled extends AmoError {}

// --- 提出内容を組み立てる(通信しない) ---

function listingDescription(dir) {
  const md = fs.readFileSync(path.join(dir, "store", "listing.md"), "utf8");
  const i = md.indexOf("## 説明");
  const m = i >= 0 && md.slice(i).match(/```[^\n]*\n([\s\S]*?)```/);
  if (!m) throw new AmoError("store/listing.md の「## 説明」に ``` で囲まれた本文が見つかりません");
  return m[1].trim();
}

function zipManifest(zipPath) {
  return JSON.parse(execFileSync("unzip", ["-p", zipPath, "manifest.json"], { encoding: "utf8" }));
}

export function buildSubmission(dir, env = process.env) {
  const manifest = JSON.parse(fs.readFileSync(path.join(dir, "manifest.json"), "utf8"));
  const amo = JSON.parse(fs.readFileSync(path.join(dir, "store", "amo.json"), "utf8"));
  const zipDir = path.join(dir, "dist", "firefox");
  const zipName = fs.existsSync(zipDir)
    ? fs.readdirSync(zipDir).find((f) => f.endsWith(`-${manifest.version}-firefox.zip`))
    : null;
  if (!zipName)
    throw new AmoError(
      `${zipDir} に版 ${manifest.version} の Firefox 用 zip がありません(先に npm run pack)`,
    );
  const zipPath = path.join(zipDir, zipName);
  const guid = zipManifest(zipPath).browser_specific_settings?.gecko?.id;
  if (!guid) throw new AmoError("Firefox 用 zip の manifest にアドオンID(gecko.id)がありません");

  const problems = [];
  if (!SLUG_RE.test(amo.slug ?? "")) problems.push(`slug が不正: ${amo.slug}`);
  for (const c of amo.categories ?? [])
    if (!CATEGORIES.has(c)) problems.push(`カテゴリが不正: ${c}`);
  if (!amo.categories?.length) problems.push("categories が空");
  if (!manifest.description || [...manifest.description].length > 250)
    problems.push("概要(manifest.description)は1〜250文字");
  if (!amo.privacy_policy?.trim()) problems.push("privacy_policy が空");
  const screenshots = (amo.screenshots ?? []).map((p) => path.join(dir, p));
  for (const p of screenshots)
    if (!fs.existsSync(p)) problems.push(`スクリーンショットがない: ${p}`);
  const description = listingDescription(dir);
  if (problems.length) throw new AmoError(problems.join("\n"));

  const supportEmail = env.AMO_SUPPORT_EMAIL?.trim();
  const t = (v) => ({ [LOCALE]: v });
  return {
    guid,
    version: manifest.version,
    zipPath,
    screenshots,
    privacyPolicy: amo.privacy_policy.trim(),
    // 掲載情報(新規登録と、登録済みの時の同期の両方で送る)
    metadata: {
      default_locale: LOCALE,
      name: t(manifest.name),
      summary: t(manifest.description),
      description: t(description),
      categories: { firefox: amo.categories },
      homepage: amo.homepage ? t(amo.homepage) : null,
      ...(supportEmail ? { support_email: t(supportEmail) } : {}),
      requires_payment: false,
      is_experimental: false,
    },
    slug: amo.slug,
    versionFields: {
      license: amo.license ?? "all-rights-reserved",
      approval_notes: amo.approval_notes ?? "",
      compatibility: ["firefox"],
    },
  };
}

// 翻訳付きの項目({ ja: "…" } または文字列)から、既定の言語の値を取り出す
function tr(v) {
  if (v == null) return null;
  if (typeof v === "string") return v;
  return v[LOCALE] ?? Object.values(v)[0] ?? null;
}

// AMO に登録済みの掲載情報と比べ、変わった項目だけを返す
export function changedMetadata(addon, metadata) {
  const current = {
    name: tr(addon.name),
    summary: tr(addon.summary),
    description: tr(addon.description),
    homepage: tr(addon.homepage?.url ?? addon.homepage),
    support_email: tr(addon.support_email),
    categories: [...(addon.categories?.firefox ?? addon.categories ?? [])].sort().join(","),
  };
  const out = {};
  for (const key of ["name", "summary", "description", "homepage", "support_email"]) {
    if (!(key in metadata)) continue;
    if ((tr(metadata[key]) ?? null) !== (current[key] ?? null)) out[key] = metadata[key];
  }
  if ([...metadata.categories.firefox].sort().join(",") !== current.categories) {
    out.categories = metadata.categories;
  }
  return out;
}

// --- AMO API ---

function jwt(issuer, secret) {
  const b64 = (o) => Buffer.from(JSON.stringify(o)).toString("base64url");
  const now = Math.floor(Date.now() / 1000);
  const body = `${b64({ alg: "HS256", typ: "JWT" })}.${b64({
    iss: issuer,
    jti: crypto.randomUUID(),
    iat: now,
    exp: now + 60,
  })}`;
  return `${body}.${crypto.createHmac("sha256", secret).update(body).digest("base64url")}`;
}

function client({ base, issuer, secret, log = console.log }) {
  // 1つの拡張の提出で 429 を待つ時間の合計の上限。AMO は1時間単位の制限もあり、
  // 待ち続けると実行が何十分も止まるため、上限を超えたら止めて後で再実行してもらう
  const budgetSec = Number(process.env.AMO_RETRY_BUDGET_SEC ?? 900);
  let waitedSec = 0;
  return async function api(method, p, body, { allow404 = false } = {}) {
    // 429(短時間に送りすぎ)は、AMO が示す秒数だけ待って同じ内容を送り直す
    for (let attempt = 1; ; attempt++) {
      const headers = { Authorization: `JWT ${jwt(issuer, secret)}` };
      let payload;
      if (body instanceof FormData) payload = body;
      else if (body !== undefined) {
        headers["Content-Type"] = "application/json";
        payload = JSON.stringify(body);
      }
      const res = await fetch(new URL(`/api/v5${p}`, base), { method, headers, body: payload });
      if (allow404 && res.status === 404) return null;
      const text = await res.text();
      if (res.status === 429 && attempt <= MAX_RETRIES) {
        const wait = retryAfterSeconds(res, text);
        if (waitedSec + wait > budgetSec) {
          throw new AmoThrottled(
            `${method} ${p}: 送りすぎの制限(429)が続いているため中断しました(待ち時間の合計が ${budgetSec} 秒を超える)。` +
              "1時間ほど後にもう一度実行すると、終わっていない所から続きを行います",
          );
        }
        waitedSec += wait;
        log(
          `${method} ${p}: 送りすぎの制限(429)。${wait} 秒待って送り直します(${attempt}/${MAX_RETRIES})`,
        );
        await new Promise((r) => setTimeout(r, wait * 1000 * RETRY_SCALE()));
        continue;
      }
      if (!res.ok) throw new AmoError(`${method} ${p} → ${res.status}: ${text.slice(0, 2000)}`);
      return text ? JSON.parse(text) : {};
    }
  };
}

const MAX_RETRIES = 8;
// テストで待ち時間を縮めるための倍率(通常は 1)
const RETRY_SCALE = () => Number(process.env.AMO_RETRY_SCALE ?? 1);

// Retry-After ヘッダーか、本文の「Expected available in 57 seconds.」から待つ秒数を取る(最大10分)
function retryAfterSeconds(res, text) {
  const header = Number(res.headers.get("retry-after"));
  const body = Number(text.match(/available in (\d+) second/)?.[1]);
  const sec = [header, body].find((v) => Number.isFinite(v) && v > 0) ?? 60;
  return Math.min(sec + 2, 600);
}

async function uploadAndValidate(api, zipPath, log) {
  const form = new FormData();
  form.append("upload", new Blob([fs.readFileSync(zipPath)]), path.basename(zipPath));
  form.append("channel", "listed");
  let up = await api("POST", "/addons/upload/", form);
  log(`アップロード ${up.uuid}: 自動検証を待っています`);
  const start = Date.now();
  while (!up.processed) {
    if (Date.now() - start > POLL_LIMIT_MS)
      throw new AmoError("自動検証が15分で終わりませんでした");
    await new Promise((r) => setTimeout(r, Number(process.env.AMO_POLL_MS ?? 5000)));
    up = await api("GET", `/addons/upload/${up.uuid}/`);
  }
  if (!up.valid) {
    const msgs = (up.validation?.messages ?? [])
      .filter((m) => m.type === "error")
      .map((m) => `- ${m.message}${m.file ? ` (${m.file})` : ""}`);
    throw new AmoError(
      `AMO の自動検証でエラー:\n${msgs.join("\n") || JSON.stringify(up.validation).slice(0, 2000)}`,
    );
  }
  const warnings = up.validation?.warnings ?? 0;
  log(`自動検証: 合格(警告 ${warnings} 件)`);
  return up.uuid;
}

export async function submit(dir, { dryRun = false, env = process.env, log = console.log } = {}) {
  const s = buildSubmission(dir, env);
  log(`${s.metadata.name[LOCALE]} v${s.version}(${s.guid})`);
  if (dryRun) {
    log(
      `[dry-run] zip: ${path.relative(dir, s.zipPath)} / slug: ${s.slug} / カテゴリ: ${s.metadata.categories.firefox.join(",")}`,
    );
    log(
      `[dry-run] 説明 ${[...s.metadata.description[LOCALE]].length} 文字・スクリーンショット ${s.screenshots.length} 枚・プライバシーポリシー ${[...s.privacyPolicy].length} 文字`,
    );
    return { action: "dry-run", guid: s.guid, version: s.version };
  }
  if (!env.AMO_JWT_ISSUER || !env.AMO_JWT_SECRET)
    throw new AmoError("AMO_JWT_ISSUER / AMO_JWT_SECRET が未設定です");
  const api = client({
    base: env.AMO_API_BASE || "https://addons.mozilla.org",
    issuer: env.AMO_JWT_ISSUER,
    secret: env.AMO_JWT_SECRET,
    log,
  });
  const g = encodeURIComponent(s.guid);

  let addon = await api("GET", `/addons/addon/${g}/`, undefined, { allow404: true });
  let action;
  if (!addon) {
    const upload = await uploadAndValidate(api, s.zipPath, log);
    addon = await api("POST", "/addons/addon/", {
      ...s.metadata,
      slug: s.slug,
      version: { upload, ...s.versionFields },
    });
    action = "created";
    log(`新規登録して審査に提出しました: ${addon.url ?? addon.slug}`);
  } else {
    // 掲載情報は版の提出より先に同期する(版の作成では掲載情報を変えられないため)
    // AMO は編集の回数の制限が厳しいので、変わった項目だけ送る(何も変わっていなければ送らない)
    const changed = changedMetadata(addon, s.metadata);
    if (Object.keys(changed).length) {
      addon = await api("PATCH", `/addons/addon/${g}/`, changed);
      log(`掲載情報を更新しました: ${Object.keys(changed).join(", ")}`);
    }
    const versions = await api(
      "GET",
      `/addons/addon/${g}/versions/?filter=all_with_unlisted&page_size=50`,
    );
    if ((versions.results ?? []).some((v) => v.version === s.version)) {
      action = "unchanged";
      log(`v${s.version} は提出済みのため、版の提出は飛ばしました`);
    } else {
      const upload = await uploadAndValidate(api, s.zipPath, log);
      await api("POST", `/addons/addon/${g}/versions/`, { upload, ...s.versionFields });
      action = "updated";
      log(`v${s.version} を審査に提出しました`);
    }
  }

  const policy = await api("GET", `/addons/addon/${g}/eula_policy/`);
  if (tr(policy.privacy_policy) !== s.privacyPolicy) {
    await api("PATCH", `/addons/addon/${g}/eula_policy/`, {
      privacy_policy: { [LOCALE]: s.privacyPolicy },
    });
    log("プライバシーポリシーを更新しました");
  }

  // スクリーンショットは足りない分だけ登録する(途中で止まった時も、再実行で続きから)
  const have = (addon.previews ?? []).length;
  const missing = s.screenshots.slice(have);
  if (missing.length) {
    for (const [j, p] of missing.entries()) {
      const i = have + j;
      const form = new FormData();
      form.append("image", new Blob([fs.readFileSync(p)], { type: "image/png" }), path.basename(p));
      form.append("position", String(i));
      await api("POST", `/addons/addon/${g}/previews/`, form);
    }
    log(`スクリーンショット ${missing.length} 枚を登録しました(計 ${s.screenshots.length} 枚)`);
  }
  return { action, guid: s.guid, version: s.version, url: addon.url };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const args = process.argv.slice(2);
  const dir = path.resolve(args.find((a) => !a.startsWith("--")) ?? ".");
  try {
    const r = await submit(dir, { dryRun: args.includes("--dry-run") });
    if (process.env.GITHUB_STEP_SUMMARY) {
      fs.appendFileSync(
        process.env.GITHUB_STEP_SUMMARY,
        `- Firefox(AMO) ${path.basename(dir)} v${r.version}: ${r.action}${r.url ? ` ${r.url}` : ""}\n`,
      );
    }
  } catch (e) {
    console.error(e instanceof AmoError ? e.message : e);
    process.exit(e instanceof AmoThrottled ? 75 : 1);
  }
}
