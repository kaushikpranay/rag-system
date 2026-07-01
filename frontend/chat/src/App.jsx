import { useCallback, useRef, useState } from 'react'
import './App.css'
import { ChatWindow } from './components/ChatWindow/ChatWindow'
import { QueryInput } from './components/QueryInput/QueryInput'
import { EscalationPanel } from './components/EscalationPanel/EscalationPanel'
import { usePolling } from './hooks/usePolling'
import { sendQuery, escalate } from './api/client'

function App() {
  const [sessionId] = useState(() => crypto.randomUUID())
  const [messages, setMessages] = useState([])
  const [chatHistory, setChatHistory] = useState([])
  const [sending, setSending] = useState(false)
  const nextId = useRef(0)

  const addMessage = useCallback((message) => {
    const id = nextId.current++
    setMessages((prev) => [...prev, { id, timestamp: Date.now(), ...message }])
    return id
  }, [])

  const updateMessage = useCallback((id, patch) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...patch } : m)))
  }, [])

  const onResolved = useCallback((query, answer) => {
    addMessage({ type: 'resolved', text: `✅ Human agent answered: ${answer}` })
  }, [addMessage])

  const onTimeout = useCallback((query) => {
    addMessage({ type: 'status', text: `⏰ Timed out waiting for: "${query}"` })
  }, [addMessage])

  const { startPolling } = usePolling(sessionId, { onResolved, onTimeout })

  const handleSend = async (query) => {
    setChatHistory((prev) => [...prev, query])
    addMessage({ type: 'user', text: query })
    const loadingId = addMessage({ type: 'bot', text: 'Thinking...', loading: true })
    setSending(true)

    try {
      const data = await sendQuery(query, sessionId)
      updateMessage(loadingId, {
        text: data.answer || 'No response.',
        confidence: data.confidence,
        escalated: data.escalated,
        sources: data.sources,
        loading: false,
      })
      if (data.escalated) startPolling(query)
    } catch {
      updateMessage(loadingId, { text: 'Error connecting to server. Try again.', loading: false })
    }
    setSending(false)
  }

  const handleEscalate = async (query) => {
    const data = await escalate(query, sessionId)
    if (data.escalated) {
      addMessage({ type: 'status', text: `⏳ "${query}" sent to human agent. Ask me again in ~1 minute.` })
      startPolling(query)
    }
  }

  return (
    <div className="chat-app">
      <header className="header">
        <div className="header-icon">🔍</div>
        <div className="header-text">
          <h1>RAG Query System</h1>
          <p>Ask anything related to our system</p>
        </div>
        <div className="header-status">
          <span className="status-dot" />
          System Online
        </div>
      </header>

      <div className="chat-wrapper">
        <ChatWindow messages={messages} />
        <div className="input-row">
          <EscalationPanel chatHistory={chatHistory} onEscalate={handleEscalate} />
          <QueryInput onSend={handleSend} disabled={sending} />
        </div>
      </div>
    </div>
  )
}

export default App
