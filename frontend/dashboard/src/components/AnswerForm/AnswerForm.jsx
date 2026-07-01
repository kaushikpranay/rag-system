import { useState } from 'react'
import './AnswerForm.css'

export function AnswerForm({ onSubmit }) {
  const [answer, setAnswer] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const submit = async () => {
    if (!answer.trim()) {
      setError('Answer cannot be empty.')
      return
    }
    setSubmitting(true)
    setError(null)
    const result = await onSubmit(answer.trim())
    setSubmitting(false)
    if (!result.resolved) {
      setError('One or more storage steps failed. Check logs.')
    }
  }

  return (
    <div className="answer-form">
      <textarea
        placeholder="Type the correct answer here..."
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
        rows={4}
      />
      <button onClick={submit} disabled={submitting}>
        {submitting ? 'Storing...' : '✅ Submit'}
      </button>
      {error ? <p className="answer-error">{error}</p> : null}
    </div>
  )
}
