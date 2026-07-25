// つづもんLPを配信ビルド（dist-web/）へ出力するスクリプト
//
// 使い方:  node lp/build-lp.mjs
//
// やること:
//   LP本体（index.html / tokushoho.html / privacy.html と、index.html が参照している画像）を
//   pdf-workbook/dist-web/ へコピーする。
//   → Firebase Hosting（site: tsudumon）が https://tsudumon.jp/ として配信する。
//
// ※ LPの正本はこのフォルダ（pdf-workbook/lp）。編集したらこのスクリプトを再実行する。
// ※ 教材（wb/ref/map）と手書きページ（login/ activate/ account/）は
//    `python -X utf8 deploy_tsudumon.py` が同じ dist-web/ へ出力する。両方を実行してからデプロイすること。
// ※ AIチャットAPIは Cloud Function `tsudumonLpChat`（marutto-study/functions/src/tsudumonLpChat.ts）。
//    firebase.json の rewrite により /api/chat で到達する。以前は Vercel の Serverless Function
//    （marutto-study/api/chat.js）だったが、Vercel依存を外すため移行した。

import { cp, mkdir, readFile } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const lp = fileURLToPath(new URL('.', import.meta.url));
const dest = join(lp, '..', 'dist-web');

// LPが実際に参照している画像だけを index.html から拾ってコピーする
const html = await readFile(join(lp, 'index.html'), 'utf-8');
const imgs = [...new Set(html.match(/img\/[a-zA-Z0-9._/-]+\.(?:png|jpe?g|webp|svg|gif)/gi) || [])];

await mkdir(join(dest, 'img'), { recursive: true });
for (const page of ['index.html', 'tokushoho.html', 'privacy.html']) {
  await cp(join(lp, page), join(dest, page));
}
for (const img of imgs) {
  const target = join(dest, img);
  await mkdir(dirname(target), { recursive: true });
  await cp(join(lp, img), target);
}

console.log(`LP → ${dest}`);
console.log(`  ページ3枚 + 画像${imgs.length}枚`);
console.log('完了。`firebase deploy --only hosting:tsudumon` で https://tsudumon.jp/ に反映されます。');
