import { useEffect, useRef, useState } from 'react'
import { useAuthStore } from '../stores/auth-store'
import ManagementLayout from '../components/Layout/ManagementLayout'
import { renderMarkdownToHtml } from '../utils/markdown'

export default function ChatPage() {
  const wsRef = useRef<WebSocket | null>(null)
  const [messages, setMessages] = useState<{ role: 'user' | 'assistant'; content: string }[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [temperature, setTemperature] = useState<number>(0.2)
  const listRef = useRef<HTMLDivElement | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)
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

  // Auto scroll to bottom when messages update or loading status changes
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, loading])

  const send = () => {
    const text = input.trim()
    if (!text || !wsRef.current) return
    setMessages((m) => [...m, { role: 'user', content: text }])
    setMessages((m) => [...m, { role: 'assistant', content: '' }])
    setLoading(true)
    wsRef.current.send(JSON.stringify({ content: text, temperature }))
    setInput('')
  }

  return (
    <ManagementLayout>
      <div style={{ maxWidth: 860, margin: '0 auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <h2 style={{ margin: 0 }}>Local LLM Chat</h2>

        {/* Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <label htmlFor="temperature" style={{ fontSize: 14, color: '#555' }}>Temperature</label>
            <input
              id="temperature"
              type="range"
              min={0}
              max={2}
              step={0.05}
              value={temperature}
              onChange={(e) => setTemperature(parseFloat(e.target.value))}
              style={{ width: 200 }}
            />
            <span style={{ width: 40, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{temperature.toFixed(2)}</span>
          </div>
          <button
            onClick={() => {
              setMessages([])
              wsRef.current?.send(JSON.stringify({ type: 'reset' }))
            }}
            style={{ padding: '6px 10px' }}
          >
            Reset
          </button>
        </div>

        {/* Messages */}
        <div
          ref={listRef}
          style={{
            border: '1px solid #e5e7eb',
            borderRadius: 12,
            padding: 12,
            minHeight: 420,
            maxHeight: '60vh',
            overflowY: 'auto',
            background: '#fafafa',
          }}
        >
          {messages.map((m, i) => {
            const isUser = m.role === 'user'
            return (
              <div
                key={i}
                style={{
                  display: 'flex',
                  justifyContent: isUser ? 'flex-end' : 'flex-start',
                  margin: '8px 0',
                }}
              >
                <div
                  style={{
                    maxWidth: '76%',
                    padding: '10px 12px',
                    borderRadius: 12,
                    whiteSpace: 'pre-wrap',
                    boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                    background: isUser ? '#dbeafe' : '#ffffff',
                    border: '1px solid #e5e7eb',
                  }}
                >
                  {isUser ? (
                    m.content
                  ) : (
                    <div
                      dangerouslySetInnerHTML={{ __html: renderMarkdownToHtml(m.content) }}
                    />
                  )}
                </div>
              </div>
            )
          })}
          {loading && (
            <div style={{ display: 'flex', justifyContent: 'flex-start', margin: '8px 0' }}>
              <div
                style={{
                  maxWidth: '76%',
                  padding: '10px 12px',
                  borderRadius: 12,
                  background: '#ffffff',
                  border: '1px solid #e5e7eb',
                  color: '#6b7280',
                  fontSize: 14,
                }}
              >
                Assistant is typing…
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Composer */}
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                if (!loading) send()
              }
            }}
            placeholder="Type a message and press Enter..."
            style={{ flex: 1, padding: '10px 12px', borderRadius: 10, border: '1px solid #e5e7eb' }}
          />
          <button onClick={send} disabled={loading || !input.trim()} style={{ padding: '10px 14px' }}>Send</button>
        </div>
      </div>
    </ManagementLayout>
  )
}
