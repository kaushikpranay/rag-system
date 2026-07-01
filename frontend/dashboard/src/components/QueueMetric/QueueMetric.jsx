import './QueueMetric.css'

export function QueueMetric({ depth }) {
  const label = depth === 1 ? 'Pending item' : 'Pending'
  return (
    <div className="metric-box">
      <div className="num">{depth >= 0 ? depth : '?'}</div>
      <div className="lbl">{label} in Queue</div>
    </div>
  )
}
