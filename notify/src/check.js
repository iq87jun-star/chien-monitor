// 値下がりチェック(GitHub Actions から1日数回)。
// 相場データが前回のチェック以降に更新されていれば、登録されたカードを目標額と比べて Discord に通知する。
// 同じカードで何度も通知しないよう、通知したら armed=0 にし、相場が目標の5%超まで戻ったら armed=1 に戻す。
import { loadPrices } from "../public/prices.js";
import { postWebhook, priceDropMessages } from "./discord.js";

export const REARM_RATIO = 1.05;

// 1件の判定: "notify"(通知する)/ "rearm"(次の値下がりに備える)/ null(何もしない)
export function evaluate(watch, jpy) {
  if (jpy == null) return null;
  if (watch.armed && jpy <= watch.target_jpy) return "notify";
  if (!watch.armed && jpy > watch.target_jpy * REARM_RATIO) return "rearm";
  return null;
}

// deps: { db, fetchImpl, discordOrigin, now, force, log }
export async function runCheck(deps) {
  const { db, fetchImpl = fetch, discordOrigin, now = () => new Date(), force = false } = deps;
  const log = deps.log ?? (() => {});
  const { cards, sources, errors } = await loadPrices(fetchImpl);
  for (const [game, msg] of Object.entries(errors)) log(`相場データ取得失敗 ${game}: ${msg}`);

  const metaRows = await db.all("SELECT value FROM meta WHERE key = 'fetchedAt'");
  const prev = metaRows[0] ? JSON.parse(metaRows[0].value) : {};
  const stamps = { ...prev };
  for (const [game, s] of Object.entries(sources)) stamps[game] = s.fetchedAt;
  const updated = Object.keys(sources).filter((g) => sources[g].fetchedAt !== prev[g]);
  const stats = { updated, notified: 0, rearmed: 0, failed: 0, gone: 0, skipped: false };
  if (!force && updated.length === 0) {
    stats.skipped = true;
    log("相場データに更新がないためスキップ");
    return stats;
  }

  const rows = await db.all(
    `SELECT w.*, s.webhook_url FROM watches w JOIN subscribers s ON s.id = w.subscriber_id
     WHERE s.active = 1 ORDER BY w.id`,
  );
  const bySub = new Map();
  for (const w of rows) {
    const card = cards.get(w.card_key);
    const action = evaluate(w, card?.jpy);
    if (action === "rearm") {
      await db.run("UPDATE watches SET armed = 1 WHERE id = ?", [w.id]);
      stats.rearmed++;
    } else if (action === "notify") {
      if (!bySub.has(w.subscriber_id))
        bySub.set(w.subscriber_id, { url: w.webhook_url, items: [] });
      bySub.get(w.subscriber_id).items.push({ watch: w, card, source: sources[card.game] });
    }
  }

  for (const [subId, { url, items }] of bySub) {
    const messages = priceDropMessages(items);
    let sent = 0;
    for (const msg of messages) {
      const r = await postWebhook(fetchImpl, url, msg, discordOrigin);
      if (r.gone) {
        await db.run("UPDATE subscribers SET active = 0 WHERE id = ?", [subId]);
        stats.gone++;
        log(`ウェブフック削除済みのため停止: ${subId}`);
        break;
      }
      if (!r.ok) {
        log(`送信失敗 ${subId}: HTTP ${r.status}${r.error ? ` ${r.error}` : ""}`);
        break;
      }
      // 送れたメッセージに含まれるカードだけ通知済みにする(失敗分は次回また送る)
      for (const { watch } of items.slice(sent * 10, sent * 10 + msg.embeds.length)) {
        await db.run("UPDATE watches SET armed = 0, notified_at = ? WHERE id = ?", [
          now().toISOString(),
          watch.id,
        ]);
        stats.notified++;
      }
      sent++;
    }
    stats.failed += items.length - Math.min(items.length, sent * 10);
  }

  await db.run(
    `INSERT INTO meta (key, value) VALUES ('fetchedAt', ?)
     ON CONFLICT(key) DO UPDATE SET value = excluded.value`,
    [JSON.stringify(stamps)],
  );
  log(
    `更新: ${updated.join(",") || "なし"} / 通知 ${stats.notified}件・再設定 ${stats.rearmed}件・失敗 ${stats.failed}件`,
  );
  return stats;
}
