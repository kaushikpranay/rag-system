import { useState } from 'react'
import './EscalationPanel.css'

export function EscalationPanel({ chatHistory, onEscalate }) {
  const [isOpen, setIsOpen] = useState(false)
  const [selectedQuery, setSelectedQuery] = useState(null)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState(null)

  const togglePanel = () => {
    if (!isOpen) {
      setSelectedQuery(null)
      setError(null)
    }
    setIsOpen((open) => !open)
  }

  const handleSend = async () => {
    if (!selectedQuery) {
      setError('Please select a question first.')
      return
    }
    setSending(true)
    setError(null)
    try {
      await onEscalate(selectedQuery)
      setIsOpen(false)
      setSelectedQuery(null)
    } catch {
      setError('Failed to send. Try again.')
    }
    setSending(false)
  }

  return (
    <>
      <button id="ask-human-btn" onClick={togglePanel} data-tooltip="Ask a human expert">
        🙋
      </button>

      <div id="escalate-panel" className={isOpen ? 'open' : ''}>
        <p className="panel-title">Ask a Human Expert</p>
        <p className="panel-sub">Select a question to send to an agent.</p>
        <hr className="panel-divider" />
        <div id="query-list">
          {chatHistory.length === 0 ? (
            <p className="panel-empty">No questions yet.</p>
          ) : (
            chatHistory.map((q, i) => (
              <div
                key={i}
                className={'query-item' + (selectedQuery === q ? ' selected' : '')}
                onClick={() => { setSelectedQuery(q); setError(null) }}
              >
                {q}
              </div>
            ))
          )}
        </div>
        {error ? <p className="panel-error">{error}</p> : null}
        <button className="panel-btn primary" disabled={sending} onClick={handleSend}>
          {sending ? 'Sending...' : 'Send to Human'}
        </button>
        <button className="panel-btn secondary" onClick={togglePanel}>Cancel</button>
      </div>
    </>
  )
}

