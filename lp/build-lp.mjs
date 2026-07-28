// つづもんLPを配信ビルド（dist-web/）へ出力するスクリプト
//
// 使い方:  node lp/build-lp.mjs
//
// やること:
//   1. LPのHTML（index / terms / privacy / tokushoho）を dist-web/ へコピー
//   2. 全HTMLが参照している画像だけを dist-web/img/ へコピー
//   3. 下層ページの共通CSS（css/doc.css）と robots.txt をコピー
//   4. sitemap.xml を生成
//   5. FAQの構造化データ（JSON-LD）を本文のFAQから作り直して出力に反映
//      → 本文とJSON-LDが食い違うのを構造的に防ぐ
//   6. 価格表記の整合チェック（本文・JSON-LD・特商法・チャットFAQ）
//
// → Firebase Hosting（site: tsudumon）が https://tsudumon.jp/ として配信する。
//
// ※ LPの正本はこのフォルダ（pdf-workbook/lp）。編集したらこのスクリプトを再実行する。
// ※ 教材（wb/ref/map）と手書きページ（login/ activate/ account/ parents/）は
//    `python -X utf8 deploy_tsudumon.py` が同じ dist-web/ へ出力する。両方を実行してからデプロイすること。
//    保護者ページは web/parents/ が正本。lp/parents.html は廃止し、firebase.json で /parents/ へ301。
// ※ AIチャットAPIは Cloud Function `tsudumonLpChat`（marutto-study/functions/src/tsudumonLpChat.ts）。
//    firebase.json の rewrite により /api/chat で到達する。

import { cp, mkdir, readFile, writeFile, stat, readdir, rm } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const lp = fileURLToPath(new URL('.', import.meta.url));
const dest = join(lp, '..', 'dist-web');

const SITE = 'https://tsudumon.jp';
const PRICE_YEN = 1280;                 // 月額（税込）。改定時はここと本文をあわせて直す
const SIBLING_YEN = 980;                // きょうだい2人目以降の月額（税込）

const PAGES = ['index.html', 'terms.html', 'privacy.html', 'tokushoho.html'];

// sitemap に載せる「インデックスさせたい」URL。
// 規約・プライバシー・特商法は noindex なので載せない。
// /parents/ は deploy_tsudumon.py が出力する保護者向けページ。
const SITEMAP_URLS = [
  { loc: `${SITE}/`, priority: '1.0', changefreq: 'weekly' },
  { loc: `${SITE}/parents/`, priority: '0.8', changefreq: 'monthly' },
];

const warnings = [];
const warn = (msg) => { warnings.push(msg); };

// ---------------------------------------------------------------- 読み込み
const html = {};
for (const page of PAGES) {
  html[page] = await readFile(join(lp, page), 'utf-8');
}

// ------------------------------------------------- FAQ構造化データの作り直し
// 本文の <div class="faq"> 内の <details> から Q/A を拾って FAQPage を組み立てる。
// これにより「本文を直したのにJSON-LDが古いまま」が起きなくなる。
function stripTags(s) {
  return s
    .replace(/<br\s*\/?>/gi, ' ')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/\s+/g, ' ')
    .trim();
}

function buildFaqJsonLd(source) {
  const faqBlock = source.match(/<div class="faq[^"]*">([\s\S]*?)<\/div>\s*<\/div>\s*<\/section>/);
  if (!faqBlock) { warn('FAQブロックが見つからず、構造化データを再生成できませんでした'); return null; }

  const items = [];
  const re = /<details>\s*<summary>([\s\S]*?)<\/summary>\s*<div class="a">([\s\S]*?)<\/div>\s*<\/details>/g;
  let m;
  while ((m = re.exec(faqBlock[1])) !== null) {
    items.push({
      '@type': 'Question',
      name: stripTags(m[1]),
      acceptedAnswer: { '@type': 'Answer', text: stripTags(m[2]) },
    });
  }
  if (!items.length) { warn('FAQのQ&Aを1件も抽出できませんでした'); return null; }
  return { json: JSON.stringify({ '@context': 'https://schema.org', '@type': 'FAQPage', mainEntity: items }, null, 2), count: items.length };
}

const faq = buildFaqJsonLd(html['index.html']);
if (faq) {
  const tag = /(<script type="application\/ld\+json" id="faq-jsonld">)[\s\S]*?(<\/script>)/;
  if (!tag.test(html['index.html'])) {
    warn('faq-jsonld のscriptタグが見つからず、差し替えできませんでした');
  } else {
    html['index.html'] = html['index.html'].replace(tag, (_all, open, close) => `${open}\n${faq.json}\n${close}`);
  }
}

// ------------------------------------------------------------ 価格の整合検査
{
  const src = html['index.html'];
  const withComma = PRICE_YEN.toLocaleString('en-US');           // "1,280"

  // 価格表示（.price-main の金額）
  const shown = src.match(/<div class="yen">([\d,]+)<small>/);
  if (!shown) warn('価格表示（.price-main .yen）が見つかりません');
  else if (shown[1] !== withComma) warn(`本文の価格 ${shown[1]}円 が PRICE_YEN(${withComma}円) と一致しません`);

  // 構造化データの price は 本体価格 or きょうだい価格 のどちらかであるべき
  const allowed = new Set([String(PRICE_YEN), String(SIBLING_YEN)]);
  const jsonPrices = [...src.matchAll(/"price":\s*"(\d+)"/g)].map((x) => x[1]);
  if (!jsonPrices.length) warn('構造化データに price がありません');
  for (const p of jsonPrices) {
    if (!allowed.has(p)) warn(`構造化データの price ${p} が想定（${[...allowed].join(' / ')}）と一致しません`);
  }
  if (!jsonPrices.includes(String(SIBLING_YEN))) warn('構造化データに きょうだい価格の Offer がありません');

  // きょうだい価格が本文・特商法・保護者ページで揃っているか
  if (!src.includes(`${SIBLING_YEN}円`)) warn(`本文に きょうだい価格 ${SIBLING_YEN}円 の記載がありません`);
  if (!html['tokushoho.html'].includes(`${SIBLING_YEN}円`)) {
    warn(`特定商取引法ページに きょうだい価格 ${SIBLING_YEN}円 の記載がありません`);
  }

  // 本文・チャットFAQ内に別の金額表記が紛れていないか（1,280以外の「N,NNN円」を検出）
  const others = [...new Set([...src.matchAll(/([\d]{1,3},[\d]{3})円/g)].map((x) => x[1]))]
    .filter((v) => v !== withComma && v !== '5,000' && v !== '1,000');   // 5,000/1,000 は比較表の相場
  if (others.length) warn(`本文に想定外の金額表記があります: ${others.join(', ')}`);

  // 特商法ページとも突き合わせる
  if (!html['tokushoho.html'].includes(`${withComma}円`)) {
    warn(`特定商取引法ページに ${withComma}円 の記載が見つかりません`);
  }
}

// ------------------------------------------------------------------- 出力
await mkdir(join(dest, 'img'), { recursive: true });

for (const page of PAGES) {
  await writeFile(join(dest, page), html[page], 'utf-8');
}

// 全HTMLが参照している画像を拾う（index.html だけを見ていると下層ページの画像が漏れる）
const imgs = [...new Set(
  PAGES.flatMap((page) => html[page].match(/img\/[a-zA-Z0-9._/-]+\.(?:png|jpe?g|webp|svg|gif)/gi) || [])
)];
for (const img of imgs) {
  const target = join(dest, img);
  await mkdir(dirname(target), { recursive: true });
  await cp(join(lp, img), target);
}

// dist-web/img/ に残った「もうLPが参照していない画像」を掃除する。
// （dist-web/img は LP専用。教材側は dist-web/_shared/img を使うので巻き込まない）
{
  const keep = new Set(imgs.map((p) => p.replace(/\\/g, '/')));
  let removed = 0;
  const sweep = async (rel) => {
    for (const entry of await readdir(join(dest, rel), { withFileTypes: true })) {
      const child = `${rel}/${entry.name}`;
      if (entry.isDirectory()) await sweep(child);
      else if (!keep.has(child)) { await rm(join(dest, child)); removed++; }
    }
  };
  await sweep('img');
  if (removed) console.log(`  古い画像を${removed}枚 dist-web/img から削除`);
}

// 下層ページの共通CSS
await mkdir(join(dest, 'css'), { recursive: true });
await cp(join(lp, 'css', 'doc.css'), join(dest, 'css', 'doc.css'));

// robots.txt
await cp(join(lp, 'robots.txt'), join(dest, 'robots.txt'));

// sitemap.xml（lastmod は index.html の更新日時）
const lastmod = (await stat(join(lp, 'index.html'))).mtime.toISOString().slice(0, 10);
const sitemap = [
  '<?xml version="1.0" encoding="UTF-8"?>',
  '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
  ...SITEMAP_URLS.map((u) => [
    '  <url>',
    `    <loc>${u.loc}</loc>`,
    `    <lastmod>${lastmod}</lastmod>`,
    `    <changefreq>${u.changefreq}</changefreq>`,
    `    <priority>${u.priority}</priority>`,
    '  </url>',
  ].join('\n')),
  '</urlset>',
  '',
].join('\n');
await writeFile(join(dest, 'sitemap.xml'), sitemap, 'utf-8');

// ------------------------------------------------------------------- 結果
console.log(`LP → ${dest}`);
console.log(`  ページ${PAGES.length}枚 + 画像${imgs.length}枚 + css/doc.css + robots.txt + sitemap.xml`);
if (faq) console.log(`  FAQ構造化データを本文から再生成（${faq.count}件）`);

if (warnings.length) {
  console.log('');
  for (const w of warnings) console.log(`  ⚠ ${w}`);
  console.log('');
  console.log('⚠ 上の警告を確認してください（出力自体は完了しています）');
} else {
  console.log('完了。`firebase deploy --only hosting:tsudumon` で https://tsudumon.jp/ に反映されます。');
}
