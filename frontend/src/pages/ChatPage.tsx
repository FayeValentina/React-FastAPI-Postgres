import { useEffect, useRef, useState } from 'react'
import { useAuthStore } from '../stores/auth-store'
import ManagementLayout from '../components/Layout/ManagementLayout'

export default function ChatPage() {
  const wsRef = useRef<WebSocket | null>(null)
  const [messages, setMessages] = useState<{ role: 'user' | 'assistant'; content: string }[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const accessToken = useAuthStore((s) => s.accessToken)

  useEffect(() => {
    const base = (import.meta.env.VITE_API_URL || '').replace(/^http/, 'ws') + '/v1/ws/chat'
    const url = accessToken ? `${base}?token=${encodeURIComponent(accessToken)}` : base
    const ws = new WebSocket(url)
    wsRef.current = ws
    ws.onmessage = (ev) => {
      const data = JSON.parse(ev.data)
      if (data.type === 'delta') {
        setMessages((prev) => {
          const last = prev[prev.length - 1]
          if (last && last.role === 'assistant') {
            const copy = prev.slice()
            copy[copy.length - 1] = { role: 'assistant', content: last.content + data.content }
            return copy
          }
          return [...prev, { role: 'assistant', content: data.content }]
        })
      } else if (data.type === 'done') {
        setLoading(false)
      }
    }
    ws.onclose = () => {}
    return () => ws.close()
  }, [accessToken])

  const send = () => {
    const text = input.trim()
    if (!text || !wsRef.current) return
    setMessages((m) => [...m, { role: 'user', content: text }])
    setMessages((m) => [...m, { role: 'assistant', content: '' }])
    setLoading(true)
    wsRef.current.send(JSON.stringify({ content: text }))
    setInput('')
  }

  return (
    <ManagementLayout>
      <div style={{ maxWidth: 720, margin: '0 auto', padding: 16 }}>
        <h2>Local LLM Chat</h2>
        <div style={{ border: '1px solid #ddd', padding: 12, minHeight: 320 }}>
          {messages.map((m, i) => (
            <div key={i} style={{ whiteSpace: 'pre-wrap', margin: '8px 0' }}>
              <strong>{m.role}:</strong> {m.content}
            </div>
          ))}
          {loading && <div>Assistant is typing…</div>}
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
          <input value={input} onChange={(e) => setInput(e.target.value)} style={{ flex: 1 }} />
          <button onClick={send} disabled={loading}>Send</button>
        </div>
      </div>
    </ManagementLayout>
  )
}
