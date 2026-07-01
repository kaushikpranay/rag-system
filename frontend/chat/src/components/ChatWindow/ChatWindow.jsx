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
      {messages.map((m) => (
        <MessageBubble key={m.id} message={m} />
      ))}
    </div>
  )
}
