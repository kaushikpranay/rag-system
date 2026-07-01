import { useState } from 'react'
import { login } from '../../api/client'
import './LoginGate.css'

export function LoginGate({ onSuccess }) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError(false)
    const ok = await login(password)
    setSubmitting(false)
    if (ok) {
      onSuccess()
    } else {
      setError(true)
    }
  }

  return (
    <form className="login-gate" onSubmit={submit}>
      <label htmlFor="dashboard-password">Dashboard Password</label>
      <input
        id="dashboard-password"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        autoFocus
      />
      <button type="submit" disabled={submitting}>{submitting ? 'Checking...' : 'Log in'}</button>
      {error ? <p className="login-error">Incorrect password</p> : null}
    </form>
  )
}
