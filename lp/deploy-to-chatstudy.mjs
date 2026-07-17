// つづもんLPを chatstudy.jp（marutto-study）へ同期するスクリプト
//
// 使い方:  node deploy-to-chatstudy.mjs
//
// やること:
//   1. LP本体（index.html / tokushoho.html / privacy.html / 参照している画像）を
//      marutto-study/public/tsudumon/ へコピー → https://www.chatstudy.jp/tsudumon/ で配信
//   2. チャットAPI（api/chat.js）を marutto-study/api/chat.js へコピー
//      → 同一ドメインの /api/chat で動く（Vercelがルート /api を関数として認識）
//
// ※ LPの正本はこのフォルダ（pdf-workbook/lp）。編集したらこのスクリプトを再実行して同期する。
// ※ chatstudy.jp の Vercel プロジェクトに環境変数 GEMINI_API_KEY（必要なら CHAT_DAILY_LIMIT /
//    CHAT_USER_DAILY_LIMIT）を設定しないとチャットはフォールバック応答になる。

import { cp, mkdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const lp = fileURLToPath(new URL('.', import.meta.url));
const marutto = join(lp, '..', '..', 'marutto-study');
const dest = join(marutto, 'public', 'tsudumon');

// LPが実際に参照している画像だけを index.html から拾ってコピーする
const html = await readFile(join(lp, 'index.html'), 'utf-8');
const imgs = [...new Set(html.match(/img\/[a-zA-Z0-9._-]+/g) || [])];

await mkdir(join(dest, 'img'), { recursive: true });
for (const page of ['index.html', 'tokushoho.html', 'privacy.html']) {
  await cp(join(lp, page), join(dest, page));
}
for (const img of imgs) {
  await cp(join(lp, img), join(dest, img));
}
await mkdir(join(marutto, 'api'), { recursive: true });
await cp(join(lp, 'api', 'chat.js'), join(marutto, 'api', 'chat.js'));

console.log(`LP → ${dest}`);
console.log(`  ページ3枚 + 画像${imgs.length}枚`);
console.log(`API → ${join(marutto, 'api', 'chat.js')}`);
console.log('完了。marutto-study をデプロイすると https://www.chatstudy.jp/tsudumon/ で公開されます。');
