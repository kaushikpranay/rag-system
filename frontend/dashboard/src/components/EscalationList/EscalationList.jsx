import { EscalationCard } from '../EscalationCard/EscalationCard'
import './EscalationList.css'

export function EscalationList({ escalations, resolvedIds, onResolve }) {
  if (escalations.length === 0) {
    return (
      <div className="escalation-empty">
        <div className="icon">📭</div>
        <div>No escalated queries loaded.</div>
        <div className="hint">Click "Fetch Escalated Queries" to poll SQS.</div>
      </div>
    )
  }

  return (
    <div className="escalation-list">
      {escalations.map((esc, i) => (
        <EscalationCard
          key={esc.message_id}
          escalation={esc}
          index={i}
          resolved={resolvedIds.has(esc.message_id)}
          onResolve={onResolve}
        />
      ))}
    </div>
  )
}
