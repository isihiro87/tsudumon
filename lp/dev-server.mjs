// つづもんLP ローカル開発サーバー
//
// 使い方:
//   1. lp/.env を作成して GEMINI_API_KEY を書く（.env.example をコピー）
//   2. cd pdf-workbook/lp
//   3. node --env-file=.env dev-server.mjs
//   4. http://localhost:3300 を開く（チャットの /api/chat も同じポートで動く）
//
// 本番（Vercel）と同じ api/chat.js をそのまま読み込むので、ローカルで動けば本番も同じ挙動。

import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import chatHandler from './api/chat.js';

const root = fileURLToPath(new URL('.', import.meta.url));
const PORT = process.env.PORT || 3300;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
};

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);

  // Vercel Serverless Function のローカルアダプタ（末尾スラッシュあり/なし両対応）
  if (url.pathname === '/api/chat' || url.pathname === '/api/chat/') {
    // file:// で直接開いたLPからも使えるようCORSを許可（ローカル開発専用）
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    if (req.method === 'OPTIONS') { res.statusCode = 204; res.end(); return; }
    let body = '';
    for await (const chunk of req) body += chunk;
    try { req.body = body ? JSON.parse(body) : {}; } catch { req.body = {}; }
    res.status = (code) => { res.statusCode = code; return res; };
    res.json = (obj) => {
      res.setHeader('Content-Type', 'application/json; charset=utf-8');
      res.end(JSON.stringify(obj));
    };
    try {
      await chatHandler(req, res);
    } catch (e) {
      console.error('api/chat error:', e);
      if (!res.writableEnded) res.status(500).json({ error: 'internal error' });
    }
    return;
  }

  // 静的ファイル配信
  const pathname = url.pathname === '/' ? '/index.html' : url.pathname;
  const safePath = normalize(pathname).replace(/^([/\\.])+/, '');
  try {
    const file = await readFile(join(root, safePath));
    res.setHeader('Content-Type', MIME[extname(safePath).toLowerCase()] || 'application/octet-stream');
    res.end(file);
  } catch {
    res.statusCode = 404;
    res.end('not found');
  }
});

server.listen(PORT, () => {
  console.log(`つづもんLP dev server: http://localhost:${PORT}`);
  console.log(`GEMINI_API_KEY: ${process.env.GEMINI_API_KEY ? '設定済み' : '未設定（チャットはフォールバック応答になります）'}`);
});
