// 簡化版 Service Worker for 書籍識別 PWA
const CACHE_NAME = 'book-scanner-v1.0';
const urlsToCache = [
  '/scanner',
  '/static/js/scanner_3.js'
];

// Service Worker 安裝事件
self.addEventListener('install', (event) => {
  console.log('📦 Service Worker 安裝中...');
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('✅ 快取已開啟');
        return cache.addAll(urlsToCache);
      })
      .then(() => {
        console.log('✅ 資源已快取');
        return self.skipWaiting();
      })
      .catch((error) => {
        console.error('❌ 快取失敗:', error);
      })
  );
});

// Service Worker 激活事件
self.addEventListener('activate', (event) => {
  console.log('🚀 Service Worker 已激活');
  
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('🗑️ 清除舊快取:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => {
      return self.clients.claim();
    })
  );
});

// 攔截網路請求
self.addEventListener('fetch', (event) => {
  // 跳過非 GET 請求
  if (event.request.method !== 'GET') {
    return;
  }
  
  // 跳過 API 請求（讓它們正常走網路）
  if (event.request.url.includes('/api/')) {
    return;
  }
  
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        // 快取命中，返回快取的資源
        if (response) {
          console.log('📦 從快取載入:', event.request.url);
          return response;
        }
        
        // 快取未命中，發起網路請求
        console.log('🌐 從網路載入:', event.request.url);
        return fetch(event.request)
          .then((response) => {
            // 檢查回應是否有效
            if (!response || response.status !== 200 || response.type !== 'basic') {
              return response;
            }
            
            // 複製回應（因為 response 是一次性的）
            const responseToCache = response.clone();
            
            // 將新資源加入快取
            caches.open(CACHE_NAME)
              .then((cache) => {
                cache.put(event.request, responseToCache);
              });
            
            return response;
          })
          .catch((error) => {
            console.error('❌ 網路請求失敗:', error);
            
            // 如果是導航請求且快取中有 scanner 頁面，返回它
            if (event.request.mode === 'navigate') {
              return caches.match('/scanner');
            }
            
            throw error;
          });
      })
  );
});

console.log('✅ Service Worker 腳本已載入');