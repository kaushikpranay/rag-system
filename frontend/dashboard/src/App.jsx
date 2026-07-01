import { useCallback, useEffect, useState } from 'react'
import './App.css'
import { LoginGate } from './components/LoginGate/LoginGate'
import { QueueMetric } from './components/QueueMetric/QueueMetric'
import { EscalationList } from './components/EscalationList/EscalationList'
import { getStoredHash, clearStoredHash, getQueueDepth, fetchEscalations, resolveEscalation } from './api/client'

function App() {
  const [authed, setAuthed] = useState(() => !!getStoredHash())
  const [queueDepth, setQueueDepth] = useState(-1)
  const [escalations, setEscalations] = useState([])
  const [resolvedIds, setResolvedIds] = useState(new Set())
  const [maxMessages, setMaxMessages] = useState(5)
  const [fetching, setFetching] = useState(false)

  const refreshQueueDepth = useCallback(async () => {
    setQueueDepth(await getQueueDepth())
  }, [])

  useEffect(() => {
    if (authed) refreshQueueDepth()
  }, [authed, refreshQueueDepth])

  const handleFetch = async () => {
    setFetching(true)
    const fetched = await fetchEscalations(maxMessages)
    setEscalations((prev) => {
      const existingIds = new Set(prev.map((m) => m.message_id))
      const newOnes = fetched.filter((m) => !existingIds.has(m.message_id))
      return [...prev, ...newOnes]
    })
    setFetching(false)
    refreshQueueDepth()
  }

  const handleClearResolved = () => {
    setEscalations((prev) => prev.filter((m) => !resolvedIds.has(m.message_id)))
    setResolvedIds(new Set())
  }

  const handleResolve = async (escalation, answer) => {
    const result = await resolveEscalation({
      receiptHandle: escalation.receipt_handle,
      sessionId: escalation.session_id,
      query: escalation.query,
      answer,
    })
    if (result.resolved) {
      setResolvedIds((prev) => new Set(prev).add(escalation.message_id))
      refreshQueueDepth()
    }
    return result
  }

  const handleLogout = () => {
    clearStoredHash()
    setAuthed(false)
  }

  if (!authed) {
    return <LoginGate onSuccess={() => setAuthed(true)} />
  }

  const total = escalations.length
  const resolvedCount = resolvedIds.size

  return (
    <div className="dashboard-app">
      <aside className="sidebar">
        <h2>🧠 RAG System</h2>
        <p className="subtitle">Human Agent Dashboard</p>
        <QueueMetric depth={queueDepth} />
        <label className="max-messages">
          Max messages to fetch
          <input
            type="number"
            min={1}
            max={10}
            value={maxMessages}
            onChange={(e) => setMaxMessages(Number(e.target.value))}
          />
        </label>
        <button className="logout-btn" onClick={handleLogout}>Logout</button>
      </aside>

      <main className="main">
        <h1>Escalation Queue</h1>
        <p className="subtitle">Review low-confidence queries escalated by the RAG agent. Submit verified answers to improve the knowledge base.</p>

        <div className="toolbar">
          <button onClick={handleFetch} disabled={fetching}>
            {fetching ? 'Polling SQS...' : '🔄 Fetch Escalated Queries'}
          </button>
          <button className="secondary" onClick={handleClearResolved}>🗑 Clear Resolved</button>
        </div>

        {total > 0 ? (
          <p className="summary">{total} message(s) loaded — {resolvedCount} resolved, {total - resolvedCount} pending</p>
        ) : null}

        <EscalationList escalations={escalations} resolvedIds={resolvedIds} onResolve={handleResolve} />
      </main>
    </div>
  )
}

export default App
