import { useEffect, useRef } from 'react'
import { MessageBubble } from '../MessageBubble/MessageBubble'
import './ChatWindow.css'

export function ChatWindow({ messages }) {
  const boxRef = useRef(null)

  useEffect(() => {
    if (boxRef.current) {
      boxRef.current.scrollTop = boxRef.current.scrollHeight
    }
  }, [messages])

  return (
    <div id="chat-box" ref={boxRef}>
      {messages.length === 0 ? (
        <div className="chat-empty">Ask me anything about the system</div>
      ) : (
        messages.map((m) => <MessageBubble key={m.id} message={m} />)
      )}
    </div>
  )
}
