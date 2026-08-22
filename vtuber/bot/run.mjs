// AI VTuber自動応答ボット 本体
// コメント取得 → 選別 → 返答生成 → 字幕更新 → 読み上げ、を配信終了まで繰り返す。
import readline from "node:readline";
import { CHARACTER, MAX_REPLIES_PER_POLL } from "./config.mjs";
import { getLiveChatId, fetchChatPage } from "./chat.mjs";
import { skipReason, markReplied } from "./filter.mjs";
import { generateReply } from "./reply.mjs";
import { speak } from "./tts.mjs";
import { startOverlayServer, setSubtitle } from "./overlay.mjs";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function respondTo(msg) {
  let reply;
  try {
    reply = await generateReply(msg.author, msg.text);
  } catch (err) {
    // 生成失敗・検品落ちは配信に載せず読み飛ばす(配信自体は止めない)
    console.warn(`reply: skipped (${err.message})`);
    return;
  }
  markReplied(msg.authorChannelId);
  console.log(`> ${msg.author}: ${msg.text}`);
  console.log(`${CHARACTER.name}: ${reply}`);
  setSubtitle({ author: msg.author, text: msg.text }, reply);
  await speak(reply); // 読み上げが終わるまで次の返答を作らない(音声の渋滞防止)
}

async function runLive(videoId) {
  const ownChannelId = process.env.OWN_CHANNEL_ID || "";
  const liveChatId = await getLiveChatId(videoId);
  console.log(`chat: connected (${liveChatId})`);

  let pageToken;
  let first = true;
  for (;;) {
    let page;
    try {
      page = await fetchChatPage(liveChatId, pageToken);
    } catch (err) {
      console.warn(`chat: fetch failed — 15秒後に再試行します (${err.message})`);
      await sleep(15_000);
      continue;
    }
    pageToken = page.nextPageToken;
    if (page.offline) {
      console.log("chat: 配信が終了しました");
      return;
    }

    // 初回ページは接続前の過去ログなので読み飛ばす(今さら返事をしない)
    if (!first) {
      const targets = [];
      for (const msg of page.messages) {
        const reason = skipReason(msg, ownChannelId);
        if (reason) {
          console.log(`skip (${reason}): ${msg.author}: ${msg.text.slice(0, 40)}`);
        } else {
          targets.push(msg);
        }
      }
      for (const msg of targets.slice(-MAX_REPLIES_PER_POLL)) {
        await respondTo(msg);
      }
    }
    first = false;
    await sleep(Math.max(page.pollingIntervalMillis, 5000));
  }
}

// ドライラン: 配信・YouTube APIなしで動作確認する。標準入力の1行を1コメントとして扱う。
async function runDry() {
  console.log("dry-run: 1行=1コメントとして入力してください(Ctrl+Cで終了)");
  const rl = readline.createInterface({ input: process.stdin });
  let n = 0;
  for await (const line of rl) {
    const text = line.trim();
    if (!text) continue;
    const msg = {
      id: `dry-${n}`,
      text,
      author: "テスト視聴者",
      authorChannelId: `dry-user-${n}`, // クールダウンに掛からないよう毎回別ユーザー扱い
      publishedAt: new Date().toISOString(),
    };
    n += 1;
    const reason = skipReason(msg, "");
    if (reason) {
      console.log(`skip (${reason})`);
      continue;
    }
    await respondTo(msg);
  }
}

if (!process.env.ANTHROPIC_API_KEY) {
  console.error("run: ANTHROPIC_API_KEY を設定してください(返答生成に必須)");
  process.exit(1);
}

startOverlayServer();

if (process.argv.includes("--dry")) {
  await runDry();
} else {
  const videoId = process.env.VIDEO_ID || process.argv[2];
  if (!videoId) {
    console.error("run: 配信のVIDEO_IDを指定してください(環境変数 VIDEO_ID または第1引数)");
    process.exit(1);
  }
  await runLive(videoId);
}
process.exit(0);
