// YouTube Live Chat APIクライアント(APIキーのみで動作する読み取り専用。OAuth不要)
const API_BASE = "https://www.googleapis.com/youtube/v3";

function apiKey() {
  const key = process.env.YOUTUBE_API_KEY;
  if (!key) throw new Error("YOUTUBE_API_KEY is not set");
  return key;
}

async function getJson(url) {
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`YouTube API ${res.status}: ${body.slice(0, 300)}`);
  }
  return res.json();
}

// 配信(videoId)からアクティブなライブチャットIDを引く
export async function getLiveChatId(videoId) {
  const url = new URL(`${API_BASE}/videos`);
  url.searchParams.set("part", "liveStreamingDetails");
  url.searchParams.set("id", videoId);
  url.searchParams.set("key", apiKey());
  const data = await getJson(url);
  const chatId = data.items?.[0]?.liveStreamingDetails?.activeLiveChatId;
  if (!chatId) {
    throw new Error(`no active live chat for video ${videoId}(配信中か確認してください)`);
  }
  return chatId;
}

// チャットメッセージを1ページ取得。
// 次のポーリングまでの待機時間はAPIが返すpollingIntervalMillisに従う(クォータ節約)。
export async function fetchChatPage(liveChatId, pageToken) {
  const url = new URL(`${API_BASE}/liveChat/messages`);
  url.searchParams.set("liveChatId", liveChatId);
  url.searchParams.set("part", "snippet,authorDetails");
  url.searchParams.set("maxResults", "200");
  url.searchParams.set("key", apiKey());
  if (pageToken) url.searchParams.set("pageToken", pageToken);
  const data = await getJson(url);
  return {
    messages: (data.items || [])
      .filter((it) => it.snippet?.type === "textMessageEvent")
      .map((it) => ({
        id: it.id,
        text: it.snippet.displayMessage || "",
        author: it.authorDetails?.displayName || "名無し",
        authorChannelId: it.authorDetails?.channelId || "",
        publishedAt: it.snippet.publishedAt,
      })),
    nextPageToken: data.nextPageToken,
    pollingIntervalMillis: data.pollingIntervalMillis || 5000,
    offline: Boolean(data.offlineAt),
  };
}
