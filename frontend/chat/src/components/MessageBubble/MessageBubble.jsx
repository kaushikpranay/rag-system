import './MessageBubble.css'

export function MessageBubble({ message }) {
  const { type, text, confidence, escalated, loading } = message

  if (type === 'status' || type === 'resolved') {
    return <div className={type === 'resolved' ? 'resolved-msg' : 'status-msg'}>{text}</div>
  }

  const className = ['msg', type, escalated ? 'escalated' : ''].filter(Boolean).join(' ')

  return (
    <div className={className}>
      {loading ? <span className="spinner" /> : null}
      {text}
      {confidence ? <div className="confidence">Confidence: {confidence}{escalated ? ' · Auto-escalated ✓' : ''}</div> : null}
    </div>
  )
}
