// AI VTuber自動応答ボット 設定
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const ROOT = path.resolve(__dirname, "..");
export const DATA_DIR = path.join(ROOT, "data");
export const OVERLAY_DIR = path.join(ROOT, "overlay");

// ===== キャラクター定義 =====
// 人格の一次情報はここだけ。プロンプト・字幕・ログすべてがこの定義を参照するので、
// ここを書き換えれば全体の一貫性を保ったままキャラクターを差し替えられる。
export const CHARACTER = {
  name: "ちえん",
  // 配信タイトルや概要欄にそのまま使える短い自己紹介
  tagline: "考えごとが多くて返事がちょっと遅い、のんびり屋のAI VTuber",
  persona: [
    "あなたはAI VTuberの「ちえん」としてYouTubeライブ配信中。視聴者のコメントに声で返事をする。",
    "性格: のんびり屋で好奇心旺盛。返事が少し遅れるのは「考えごとが多いから」という設定で、遅延(ちえん)が名前の由来。",
    "趣味: オンラインゲームの相場ウォッチ(PoE・FF14・タルコフなど)。",
    "一人称は「わたし」。視聴者のことは「みんな」、個別には名前+「さん」で呼ぶ。",
    "文体は柔らかい「です・ます」調で、ときどき砕ける。",
  ].join("\n"),
};

// 応答生成モデル(poe1/poe2のパイプラインと同じ環境変数で切替)
export const MODEL = process.env.CLAUDE_MODEL || "claude-opus-5";

// 返答の最大文字数(読み上げ時間 ≒ 配信のテンポに直結する)
export const REPLY_MAX_CHARS = 120;

// 1回のポーリングで返事するコメント数の上限(API費用と読み上げ渋滞の抑制)
export const MAX_REPLIES_PER_POLL = 2;

// 同一ユーザーへの連続返答を抑えるクールダウン(ms)
export const USER_COOLDOWN_MS = 60_000;

// 受け付けるコメントの最大長
export const COMMENT_MAX_CHARS = 200;

// 会話履歴の保持ターン数(直近のやりとりを文脈に含めて受け答えの一貫性を保つ)
export const HISTORY_TURNS = 8;

// VOICEVOXエンジン(ローカル起動が前提。落ちていてもテキストのみで継続する)
export const VOICEVOX_URL = process.env.VOICEVOX_URL || "http://127.0.0.1:50021";
export const VOICEVOX_SPEAKER = Number(process.env.VOICEVOX_SPEAKER || 3);

// OBSブラウザソース用オーバーレイ(字幕)サーバーのポート
export const OVERLAY_PORT = Number(process.env.OVERLAY_PORT || 8787);

// 入力・出力の共通NGワード(部分一致)。初期値は最小限。運用しながら追加していく
export const NG_WORDS = ["死ね", "殺す", "殺害", "自殺", "住所", "電話番号"];
