import { useState } from 'react'
import './QueryInput.css'

export function QueryInput({ onSend, disabled }) {
  const [value, setValue] = useState('')

  const submit = () => {
    const query = value.trim()
    if (!query) return
    onSend(query)
    setValue('')
  }

  return (
    <div className="input-bar">
      <input
        id="query-input"
        type="text"
        placeholder="Ask a question..."
        maxLength={1000}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && submit()}
      />
      <button id="send-btn" onClick={submit} disabled={disabled}>
        Send
      </button>
    </div>
  )
}
