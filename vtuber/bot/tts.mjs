// 音声合成(VOICEVOX)と再生。エンジン未起動でもテキストのみで配信を継続する。
import fs from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";
import { DATA_DIR, VOICEVOX_URL, VOICEVOX_SPEAKER } from "./config.mjs";

let warnedNoEngine = false;

export async function speak(text) {
  let wav;
  try {
    wav = await synthesize(text);
  } catch (err) {
    if (!warnedNoEngine) {
      console.warn(`tts: VOICEVOXに接続できないためテキストのみで継続します (${err.message})`);
      warnedNoEngine = true;
    }
    return;
  }
  await fs.mkdir(DATA_DIR, { recursive: true });
  const file = path.join(DATA_DIR, "voice.wav");
  await fs.writeFile(file, Buffer.from(wav));
  await play(file);
}

async function synthesize(text) {
  const q = new URLSearchParams({ text, speaker: String(VOICEVOX_SPEAKER) });
  const queryRes = await fetch(`${VOICEVOX_URL}/audio_query?${q}`, { method: "POST" });
  if (!queryRes.ok) throw new Error(`audio_query ${queryRes.status}`);
  const query = await queryRes.json();

  const synthRes = await fetch(`${VOICEVOX_URL}/synthesis?speaker=${VOICEVOX_SPEAKER}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(query),
  });
  if (!synthRes.ok) throw new Error(`synthesis ${synthRes.status}`);
  return synthRes.arrayBuffer();
}

// OS標準のプレイヤーを順に試して再生する。
// VTube Studio等のリップシンクへは仮想オーディオデバイス(VB-CABLE等)経由で渡す想定。
const PLAYERS = [
  ["aplay", []], // Linux (ALSA)
  ["afplay", []], // macOS
  ["ffplay", ["-nodisp", "-autoexit", "-loglevel", "quiet"]],
];

async function play(file) {
  for (const [cmd, args] of PLAYERS) {
    if (await tryPlay(cmd, [...args, file])) return;
  }
  console.warn(`tts: 再生コマンドが見つかりません(音声は ${file} に保存済み)`);
}

function tryPlay(cmd, args) {
  return new Promise((resolve) => {
    const p = spawn(cmd, args, { stdio: "ignore" });
    p.on("error", () => resolve(false)); // コマンド自体が存在しない
    p.on("exit", (code) => resolve(code === 0));
  });
}
