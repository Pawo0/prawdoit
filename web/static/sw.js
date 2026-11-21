// Minimal service worker: makes the site installable (PWA) so Android users get "Prawdowid" in the Share menu.
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => self.clients.claim());
self.addEventListener('fetch', () => {});
