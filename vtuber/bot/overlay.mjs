// OBSブラウザソース用オーバーレイ(字幕)サーバー。依存なしのnode:httpで完結する。
import http from "node:http";
import fs from "node:fs/promises";
import path from "node:path";
import { CHARACTER, OVERLAY_DIR, OVERLAY_PORT } from "./config.mjs";

const state = {
  name: CHARACTER.name,
  comment: null, // {author, text}
  reply: null,
  updatedAt: null,
};

export function setSubtitle(comment, reply) {
  state.comment = comment;
  state.reply = reply;
  state.updatedAt = new Date().toISOString();
}

export function startOverlayServer() {
  const server = http.createServer(async (req, res) => {
    if (req.url === "/state") {
      res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
      res.end(JSON.stringify(state));
      return;
    }
    try {
      const html = await fs.readFile(path.join(OVERLAY_DIR, "index.html"));
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end(html);
    } catch {
      res.writeHead(404);
      res.end("not found");
    }
  });
  server.listen(OVERLAY_PORT, "127.0.0.1", () => {
    console.log(`overlay: http://127.0.0.1:${OVERLAY_PORT} をOBSのブラウザソースに設定してください`);
  });
  return server;
}
