function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const rawData = atob(base64)
  const output = new Uint8Array(rawData.length)
  for (let i = 0; i < rawData.length; i++) {
    output[i] = rawData.charCodeAt(i)
  }
  return output
}

export function usePush() {
  function isSupported() {
    return 'serviceWorker' in navigator && 'PushManager' in window
  }

  async function getCurrentSubscription(): Promise<PushSubscription | null> {
    if (!isSupported()) return null
    const registration = await navigator.serviceWorker.ready
    return registration.pushManager.getSubscription()
  }

  async function isSubscribed(): Promise<boolean> {
    return (await getCurrentSubscription()) !== null
  }

  async function subscribe(): Promise<void> {
    if (!isSupported()) throw new Error('Push notifications are not supported on this browser')

    const permission = await Notification.requestPermission()
    if (permission !== 'granted') throw new Error('Notification permission was not granted')

    const { public_key: publicKey } = await $fetch<{ public_key: string }>(
      '/api/notifications/vapid-public-key'
    )
    if (!publicKey) throw new Error('Push is not configured on the server yet')

    const registration = await navigator.serviceWorker.ready
    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    })

    const json = subscription.toJSON()
    await $fetch('/api/notifications/push-subscriptions', {
      method: 'POST',
      body: { endpoint: json.endpoint, keys: json.keys },
    })
  }

  async function unsubscribe(): Promise<void> {
    const subscription = await getCurrentSubscription()
    if (!subscription) return
    const endpoint = subscription.endpoint
    await subscription.unsubscribe()
    await $fetch('/api/notifications/push-subscriptions', { method: 'DELETE', query: { endpoint } })
  }

  return { isSupported, isSubscribed, subscribe, unsubscribe }
}
