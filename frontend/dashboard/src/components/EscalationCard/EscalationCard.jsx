import { AnswerForm } from '../AnswerForm/AnswerForm'
import './EscalationCard.css'

export function EscalationCard({ escalation, index, resolved, onResolve }) {
  return (
    <div className={'query-card' + (resolved ? ' resolved' : '')}>
      <div className="card-header">
        <div className="card-title">Query #{index + 1}</div>
        <span className={'badge' + (resolved ? ' resolved' : '')}>
          {resolved ? 'RESOLVED' : 'PENDING'}
        </span>
      </div>
      <div className="label">Session ID</div>
      <div className="value mono">{escalation.session_id}</div>
      <div className="label">User Query</div>
      <div className="value">❓ {escalation.query}</div>
      <div className="label">LLM Answer (Low Confidence)</div>
      <div className="value muted">🤖 {escalation.answer}</div>

      {resolved ? (
        <div className="resolved-note">✔ Resolved — answer stored in RDS + S3</div>
      ) : (
        <AnswerForm onSubmit={(answer) => onResolve(escalation, answer)} />
      )}
    </div>
  )
}
