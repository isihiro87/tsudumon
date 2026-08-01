/* つづもん Service Worker（オフライン対応）
 *
 * ねらいは「一度開いた単元は、電波が無くても読める／解ける」こと。
 * 進捗は localStorage にあるので、ページと画像さえ返せればオフラインでも学習は続く。
 *
 * 方針:
 *   - HTML（ページ移動）… ネットワーク優先。取れたら控えを更新し、取れなければ控えを返す。
 *     どちらも無ければ /offline.html。
 *   - 画像・CSS・JS（同一オリジン）… 控え優先。返したあと裏で静かに更新する。
 *   - API（Cloud Functions）・POST・LINEログイン … 一切さわらない（素通し）。
 *     採点・チャット・課金は必ず本物のサーバに届ける必要があるため。
 *
 * キャッシュ名の版を上げると、古い控えは activate で消える。
 */
// 版を上げると activate で古い控えが消える。
// v2: clone のタイミング修正＋問題ページの「前回のつづき」修正を確実に配るため（2026-08-01）
const VERSION = 'tzm-v2';
const PAGES = 'tzm-pages-' + VERSION;
const ASSETS = 'tzm-assets-' + VERSION;
const OFFLINE_URL = '/offline.html';
const ASSET_LIMIT = 600;          // 画像を無制限に貯めない（古いものから捨てる）

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(PAGES);
    try { await cache.add(new Request(OFFLINE_URL, { cache: 'reload' })); } catch (e) {}
    self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.map((n) => (n.endsWith(VERSION) ? null : caches.delete(n))));
    await self.clients.claim();
  })());
});

// ページから「今すぐ新しい版に切り替えて」と言われたとき用
self.addEventListener('message', (e) => {
  if (e.data === 'skip-waiting') self.skipWaiting();
});

/** 控えが増えすぎないように、古いものから捨てる */
async function trim(cacheName, limit) {
  const cache = await caches.open(cacheName);
  const keys = await cache.keys();
  if (keys.length <= limit) return;
  for (let i = 0; i < keys.length - limit; i++) await cache.delete(keys[i]);
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;                       // 採点・チャット等の POST は素通し
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;        // Firebase SDK・音声CDN等は素通し
  if (url.pathname.startsWith('/login/') || url.pathname.startsWith('/activate/')) return;
  if (url.search.includes('back=')) { /* 解説からの戻り付きURLも通常どおり扱う */ }

  // ページ（HTML）: ネットワーク優先＋控えにフォールバック
  if (req.mode === 'navigate' || (req.headers.get('accept') || '').includes('text/html')) {
    event.respondWith((async () => {
      try {
        const fresh = await fetch(req);
        const cache = await caches.open(PAGES);
        cache.put(req, fresh.clone());
        return fresh;
      } catch (e) {
        const cached = await caches.match(req, { ignoreSearch: true });
        return cached || (await caches.match(OFFLINE_URL)) || Response.error();
      }
    })());
    return;
  }

  // 画像・CSS・JS: 控え優先（表示が速く、オフラインでも欠けない）
  if (/\.(png|jpe?g|webp|gif|svg|css|js|woff2?|mp3|m4a)$/i.test(url.pathname)) {
    event.respondWith((async () => {
      const cached = await caches.match(req);
      const network = fetch(req).then((res) => {
        if (res && res.ok) {
          // ⚠️ clone() は **return より前・同期的に** 呼ぶ。
          // caches.open(...).then(...) の中で clone すると、そのときには
          // すでに res の body がページ側で読まれていて
          // 「Response body is already used」で落ちる（実際に出ていた）。
          const copy = res.clone();
          caches.open(ASSETS).then((c) => {
            c.put(req, copy);
            trim(ASSETS, ASSET_LIMIT);
          });
        }
        return res;
      }).catch(() => null);
      return cached || (await network) || Response.error();
    })());
  }
});
