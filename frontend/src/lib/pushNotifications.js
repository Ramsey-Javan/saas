import api from '@/api/client'

const VAPID_PUBLIC_KEY = import.meta.env.VITE_VAPID_PUBLIC_KEY

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const rawData = window.atob(base64)
  const outputArray = new Uint8Array(rawData.length)
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i)
  }
  return outputArray
}

export async function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) return null
  try {
    return await navigator.serviceWorker.register('/service-worker.js')
  } catch (err) {
    console.error('SW registration failed:', err)
    return null
  }
}

async function sendSubscriptionToServer(sub) {
  const key = sub.getKey('p256dh')
  const auth = sub.getKey('auth')
  await api.post('/communication/push/subscribe/', {
    endpoint: sub.endpoint,
    p256dh: btoa(String.fromCharCode(...new Uint8Array(key))),
    auth: btoa(String.fromCharCode(...new Uint8Array(auth))),
    user_agent: navigator.userAgent,
  })
}

export async function subscribeToPush() {
  if (!('PushManager' in window) || !VAPID_PUBLIC_KEY) return false

  const reg = await navigator.serviceWorker.ready
  const existing = await reg.pushManager.getSubscription()
  if (existing) {
    await sendSubscriptionToServer(existing)
    return true
  }

  const subscription = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
  })
  await sendSubscriptionToServer(subscription)
  return true
}

export async function unsubscribeFromPush() {
  const reg = await navigator.serviceWorker.ready
  const sub = await reg.pushManager.getSubscription()
  if (sub) {
    await api.delete('/communication/push/unsubscribe/', { data: { endpoint: sub.endpoint } })
    await sub.unsubscribe()
  }
}
