// Discord のウェブフック(チャンネルの「連携サービス → ウェブフック」で発行するURL)への送信。
// URL を知っていればそのチャンネルに投稿できる=URL がそのまま通知先の証明になる。

const WEBHOOK_RE =
  /^https:\/\/(?:ptb\.|canary\.)?discord(?:app)?\.com\/api(?:\/v\d+)?\/webhooks\/(\d{15,25})\/([\w-]{20,100})\/?$/;

export const USERNAME = "トレカ値下がり通知";
const COLOR = 0x16a34a;

// 形式が正しければ { id, url(discord.com の正規形) }、違えば null
export function parseWebhook(input) {
  const m = WEBHOOK_RE.exec(String(input ?? "").trim());
  return m ? { id: m[1], url: `https://discord.com/api/webhooks/${m[1]}/${m[2]}` } : null;
}

// テストでは origin を差し替えてローカルの偽 Discord に送る
const target = (url, origin) => (origin ? url.replace("https://discord.com", origin) : url);

// ウェブフックが実在するか(投稿せずに確認できる)
export async function webhookExists(fetchImpl, url, origin) {
  const res = await fetchImpl(target(url, origin), { method: "GET" });
  return res.ok;
}

// 投稿。gone = ウェブフックが削除された(以後送っても届かない)
export async function postWebhook(fetchImpl, url, payload, origin) {
  let res;
  try {
    res = await fetchImpl(target(url, origin), {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ username: USERNAME, allowed_mentions: { parse: [] }, ...payload }),
    });
  } catch (err) {
    return { ok: false, status: 0, gone: false, error: err.message };
  }
  return { ok: res.ok, status: res.status, gone: res.status === 404 || res.status === 401 };
}

const yen = (n) => `${Math.round(n).toLocaleString("ja-JP")}円`;

// 値下がり通知(1メッセージに埋め込みは10件まで)
export function priceDropMessages(items) {
  const embeds = items.map(({ watch, card, source }) => ({
    title: watch.label.slice(0, 250),
    url: source.siteUrl ?? undefined,
    color: COLOR,
    description: [
      `海外相場が目標の **${yen(watch.target_jpy)}** 以下になりました`,
      `現在: **${yen(card.jpy)}**`,
      card.sub ? `(${card.sub})` : "",
    ]
      .filter(Boolean)
      .join("\n"),
    footer: { text: `${source.name}・${source.disclaimer}` },
  }));
  const out = [];
  for (let i = 0; i < embeds.length; i += 10) out.push({ embeds: embeds.slice(i, i + 10) });
  return out;
}

export function welcomeMessage(manageUrl) {
  return {
    content: [
      "✅ このチャンネルにトレカの値下がり通知を送るよう登録しました。",
      `通知するカードの追加・削除はこちらから(このリンクを知っている人は設定を変更できます): ${manageUrl}`,
    ].join("\n"),
  };
}

export function testMessage() {
  return {
    content: "🔔 テスト通知です。値下がりしたカードがあると、このチャンネルにお知らせします。",
  };
}
