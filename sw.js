const CACHE_VERSION = 'ibasho-v1';
// Caminhos relativos ao próprio sw.js — funciona tanto servido na raiz do domínio (Netlify)
// quanto num subcaminho (ex: GitHub Pages em /Katana/).
const APP_SHELL = [
  './',
  './index.html',
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-maskable-192.png',
  './icons/icon-maskable-512.png',
  './assets/models/zoro_katana.glb',
  './vendor/three/build/three.module.js',
  './vendor/three/examples/jsm/loaders/GLTFLoader.js',
  './vendor/three/examples/jsm/controls/OrbitControls.js',
  './vendor/three/examples/jsm/utils/BufferGeometryUtils.js',
];

// APIs de dados externos — sempre busca da rede, nunca serve do cache (dados desatualizados
// de anime/jogo/livro seriam piores que um erro de rede claro).
const API_HOSTS = ['api.jikan.moe', 'api.rawg.io', 'www.googleapis.com', 'sketchfab.com'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(
        names.filter((n) => n !== CACHE_VERSION).map((n) => caches.delete(n))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  if (API_HOSTS.includes(url.hostname)) return; // deixa o navegador lidar direto, sem cache

  if (url.origin === self.location.origin) {
    // app shell same-origin: cache-first, atualiza em segundo plano (stale-while-revalidate)
    event.respondWith(
      caches.match(req).then((cached) => {
        const network = fetch(req).then((res) => {
          if (res.ok) caches.open(CACHE_VERSION).then((cache) => cache.put(req, res.clone()));
          return res;
        }).catch(() => cached);
        return cached || network;
      })
    );
  }
});
