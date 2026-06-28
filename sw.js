/* ============================================================
 * Service Worker — MyNotes PWA
 * 缓存策略：安装时预缓存所有静态资源，网络优先 + 回退缓存
 * ============================================================ */

const CACHE_NAME = 'mynotes-v1';

const PRECACHE_URLS = [
  '/note/',
  '/note/index.html',
  '/note/manifest.json',
  '/note/css/base.css',
  '/note/css/nav.css',
  '/note/css/calendar.css',
  '/note/css/panel.css',
  '/note/css/time-picker.css',
  '/note/js/helpers.js',
  '/note/js/state.js',
  '/note/js/storage.js',
  '/note/js/lang.js',
  '/note/js/notes.js',
  '/note/js/timepicker.js',
  '/note/js/calendar.js',
  '/note/js/plans.js',
  '/note/js/app.js',
  '/note/icons/icon-48.svg',
  '/note/icons/icon-192.svg',
  '/note/icons/icon-512.svg'
];

// ─── 安装：预缓存所有静态资源 ───
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

// ─── 激活：清理旧缓存 ───
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// ─── 请求拦截：网络优先，回退到缓存 ───
self.addEventListener('fetch', event => {
  // 只缓存 GET 请求
  if (event.request.method !== 'GET') return;

  event.respondWith(
    fetch(event.request)
      .then(response => {
        // 成功则缓存并返回
        const clone = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        return response;
      })
      .catch(() => {
        // 离线时从缓存取
        return caches.match(event.request).then(cached => {
          if (cached) return cached;
          // 如果是导航请求，尝试返回首页
          if (event.request.mode === 'navigate') {
            return caches.match('/note/index.html');
          }
          return new Response('离线', { status: 503 });
        });
      })
  );
});
