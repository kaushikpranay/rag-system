const BASE_URL = import.meta.env.VITE_API_BASE_URL

export async function sendQuery(query, sessionId) {
  const res = await fetch(`${BASE_URL}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, session_id: sessionId }),
  })
  return res.json()
}

export async function escalate(query, sessionId) {
  const res = await fetch(`${BASE_URL}/escalate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, session_id: sessionId }),
  })
  return res.json()
}

export async function queueStatus(sessionId, query) {
  const res = await fetch(
    `${BASE_URL}/queue-status/${sessionId}?query=${encodeURIComponent(query)}`
  )
  return res.json()
}
