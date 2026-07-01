import { useState } from 'react'
import './EscalationPanel.css'

export function EscalationPanel({ chatHistory, onEscalate }) {
  const [isOpen, setIsOpen] = useState(false)
  const [selectedQuery, setSelectedQuery] = useState(null)
  const [sending, setSending] = useState(false)

  const togglePanel = () => {
    if (!isOpen) setSelectedQuery(null)
    setIsOpen((open) => !open)
  }

  const handleSend = async () => {
    if (!selectedQuery) {
      alert('Please select a question first.')
      return
    }
    setSending(true)
    try {
      await onEscalate(selectedQuery)
      setIsOpen(false)
      setSelectedQuery(null)
    } catch {
      alert('Failed to send. Try again.')
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
                onClick={() => setSelectedQuery(q)}
              >
                {q}
              </div>
            ))
          )}
        </div>
        <button className="panel-btn primary" disabled={sending} onClick={handleSend}>
          {sending ? 'Sending...' : 'Send to Human'}
        </button>
        <button className="panel-btn secondary" onClick={togglePanel}>Cancel</button>
      </div>
    </>
  )
}
