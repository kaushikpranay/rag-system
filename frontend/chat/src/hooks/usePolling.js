import { useRef, useCallback, useEffect } from 'react'
import { queueStatus } from '../api/client'

const POLL_INTERVAL_MS = 5000
const MAX_POLLS = 60

export function usePolling(sessionId, { onResolved, onTimeout }) {
  const pendingRef = useRef([])
  const intervalRef = useRef(null)

  const tick = useCallback(async () => {
    let allDone = true
    for (const esc of pendingRef.current) {
      if (esc.resolved) continue
      esc.pollCount++
      if (esc.pollCount > MAX_POLLS) {
        esc.resolved = true
        onTimeout(esc.query)
        continue
      }
      allDone = false
      try {
        const data = await queueStatus(sessionId, esc.query)
        if (!data.in_queue && data.answer) {
          esc.resolved = true
          onResolved(esc.query, data.answer)
        }
      } catch {
        // network hiccup, try again next tick
      }
    }
    if (allDone && intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [sessionId, onResolved, onTimeout])

  const startPolling = useCallback((query) => {
    pendingRef.current.push({ query, pollCount: 0, resolved: false })
    if (!intervalRef.current) {
      intervalRef.current = setInterval(tick, POLL_INTERVAL_MS)
    }
  }, [tick])

  useEffect(() => () => {
    if (intervalRef.current) clearInterval(intervalRef.current)
  }, [])

  return { startPolling }
}
