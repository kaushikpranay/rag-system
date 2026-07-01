import { useState } from 'react'
import './MessageBubble.css'

function confidenceLevel(confidence) {
  const n = typeof confidence === 'number' ? confidence : parseFloat(confidence)
  if (Number.isNaN(n)) return 'medium'
  const pct = n <= 1 ? n * 100 : n
  if (pct >= 75) return 'high'
  if (pct >= 45) return 'medium'
  return 'low'
}

function formatTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function Sources({ sources }) {
  const [open, setOpen] = useState(false)
  if (!sources || sources.length === 0) return null

  return (
    <div className="sources">
      <button className="sources-toggle" onClick={() => setOpen((v) => !v)}>
        {open ? '▾' : '▸'} {sources.length} source{sources.length > 1 ? 's' : ''}
      </button>
      {open && (
        <div className="sources-list">
          {sources.map((s, i) => (
            <span className="source-chip" key={i} title={s.snippet || s.url || ''}>
              {s.title || s.url || `Source ${i + 1}`}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export function MessageBubble({ message }) {
  const { type, text, confidence, escalated, loading, sources, timestamp } = message

  if (type === 'status' || type === 'resolved') {
    return <div className={type === 'resolved' ? 'resolved-msg' : 'status-msg'}>{text}</div>
  }

  const className = ['msg', type, escalated ? 'escalated' : ''].filter(Boolean).join(' ')

  return (
    <div className={className}>
      {type === 'bot' && <div className="avatar">🤖</div>}
      <div className="bubble">
        {loading ? (
          <div className="retrieving">
            <span className="dot" />
            <span className="dot" />
            <span className="dot" />
          </div>
        ) : (
          <>
            {text}
            {confidence ? (
              <div className="meta-row">
                <span className={`confidence-badge ${confidenceLevel(confidence)}`}>
                  {typeof confidence === 'number' && confidence <= 1
                    ? `${Math.round(confidence * 100)}%`
                    : confidence}
                </span>
                {escalated ? <span className="escalated-badge">Auto-escalated ✓</span> : null}
              </div>
            ) : null}
            <Sources sources={sources} />
          </>
        )}
        {timestamp ? <span className="timestamp">{formatTime(timestamp)}</span> : null}
      </div>
    </div>
  )
}
