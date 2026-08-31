/// <reference lib="webworker" />
import { cleanupOutdatedCaches, precacheAndRoute } from 'workbox-precaching'

declare let self: ServiceWorkerGlobalScope

// Workbox handles app-shell caching; this file only adds what a generated service worker
// can't provide out of the box — Web Push handling for the shopping/duty/reminder
// notifications (see plan doc, Key flows: Shopping -> push).
precacheAndRoute(self.__WB_MANIFEST)
cleanupOutdatedCaches()

self.addEventListener('push', (event) => {
  let data: { title?: string; body?: string; url?: string } = {}
  try {
    data = event.data?.json() ?? {}
  } catch {
    data = { body: event.data?.text() }
  }

  const title = data.title ?? 'Breidablik'
  const options: NotificationOptions = {
    body: data.body ?? '',
    icon: '/icons/icon-192.png',
    badge: '/icons/icon-192.png',
    data: { url: data.url ?? '/' },
  }
  event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = (event.notification.data && event.notification.data.url) || '/'
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientsArr) => {
      const existing = clientsArr.find((c) => 'focus' in c && c.url === url)
      if (existing) return (existing as WindowClient).focus()
      return self.clients.openWindow(url)
    })
  )
})

self.skipWaiting()
self.addEventListener('activate', () => {
  self.clients.claim()
})
