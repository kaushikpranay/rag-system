const BASE_URL = import.meta.env.VITE_API_BASE_URL
const AUTH_KEY = 'dashboard_password_hash'

export async function sha256Hex(text) {
  const data = new TextEncoder().encode(text)
  const digest = await crypto.subtle.digest('SHA-256', data)
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
}

export function getStoredHash() {
  return sessionStorage.getItem(AUTH_KEY)
}

export function clearStoredHash() {
  sessionStorage.removeItem(AUTH_KEY)
}

async function authedFetch(path, options = {}) {
  const hash = getStoredHash()
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      ...(options.headers || {}),
      Authorization: `Bearer ${hash}`,
    },
  })
  if (res.status === 401) clearStoredHash()
  return res
}

export async function login(password) {
  const hash = await sha256Hex(password)
  const res = await fetch(`${BASE_URL}/dashboard/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password_hash: hash }),
  })
  if (!res.ok) return false
  sessionStorage.setItem(AUTH_KEY, hash)
  return true
}

export async function getQueueDepth() {
  const res = await authedFetch('/dashboard/queue-depth')
  if (!res.ok) return -1
  return (await res.json()).depth
}

export async function fetchEscalations(maxMessages = 5) {
  const res = await authedFetch(`/dashboard/escalations?max_messages=${maxMessages}`)
  if (!res.ok) return []
  return res.json()
}

export async function resolveEscalation({ receiptHandle, sessionId, query, answer }) {
  const res = await authedFetch('/dashboard/escalations/resolve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      receipt_handle: receiptHandle,
      session_id: sessionId,
      query,
      answer,
    }),
  })
  return res.json()
}
