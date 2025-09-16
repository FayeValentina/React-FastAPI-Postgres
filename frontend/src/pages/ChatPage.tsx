import { useEffect, useRef, useState } from 'react'
import { Box, Button, Paper, Slider, Stack, TextField, Typography } from '@mui/material'
import { useAuthStore } from '../stores/auth-store'
import ManagementLayout from '../components/Layout/ManagementLayout'
import { renderMarkdownToHtml } from '../utils/markdown'

export default function ChatPage() {
  const wsRef = useRef<WebSocket | null>(null)
  const [messages, setMessages] = useState<{ role: 'user' | 'assistant'; content: string }[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [temperature, setTemperature] = useState<number>(0.2)
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
      <Box
        sx={{
          maxWidth: 920,
          mx: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 2.5,
          py: { xs: 1.5, md: 3 },
        }}
      >
        <Typography
          variant="h5"
          sx={{
            fontSize: { xs: 20, sm: 24, md: 28 },
            fontWeight: 600,
          }}
        >
          Local LLM Chat
        </Typography>

        {/* Controls */}
        <Paper
          variant="outlined"
          sx={{
            p: { xs: 1.5, sm: 2 },
            display: 'flex',
            flexDirection: { xs: 'column', md: 'row' },
            gap: { xs: 1.5, md: 3 },
            alignItems: { xs: 'stretch', md: 'center' },
            justifyContent: 'space-between',
          }}
        >
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            spacing={{ xs: 1, sm: 2 }}
            alignItems={{ xs: 'stretch', sm: 'center' }}
            sx={{ flex: 1, minWidth: 0 }}
          >
            <Typography variant="body2" color="text.secondary">
              Temperature
            </Typography>
            <Slider
              value={temperature}
              min={0}
              max={2}
              step={0.05}
              onChange={(_, value) => setTemperature(Array.isArray(value) ? value[0] : value)}
              sx={{
                flex: 1,
                minWidth: { xs: '100%', sm: 160 },
                maxWidth: { xs: '100%', md: 260 },
              }}
            />
            <Typography
              variant="body2"
              sx={{
                fontVariantNumeric: 'tabular-nums',
                textAlign: { xs: 'left', sm: 'right' },
                width: { sm: 48 },
              }}
            >
              {temperature.toFixed(2)}
            </Typography>
          </Stack>
          <Button
            variant="outlined"
            onClick={() => {
              setMessages([])
              wsRef.current?.send(JSON.stringify({ type: 'reset' }))
            }}
            sx={{ alignSelf: { xs: 'stretch', md: 'center' } }}
          >
            Reset
          </Button>
        </Paper>

        {/* Messages */}
        <Paper
          variant="outlined"
          sx={{
            p: { xs: 1.5, sm: 2 },
            minHeight: { xs: 320, md: 420 },
            maxHeight: { xs: '60vh', md: '65vh' },
            overflowY: 'auto',
            bgcolor: 'grey.50',
          }}
        >
          {messages.map((m, i) => {
            const isUser = m.role === 'user'
            return (
              <Box
                key={i}
                sx={{
                  display: 'flex',
                  justifyContent: isUser ? 'flex-end' : 'flex-start',
                  my: 1,
                }}
              >
                <Box
                  sx={{
                    maxWidth: { xs: '88%', sm: '76%' },
                    px: 1.5,
                    py: 1.25,
                    borderRadius: 2,
                    bgcolor: isUser ? 'primary.light' : 'background.paper',
                    border: '1px solid',
                    borderColor: 'divider',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
                    whiteSpace: 'pre-wrap',
                    fontSize: 14,
                  }}
                >
                  {isUser ? (
                    m.content
                  ) : (
                    <Box
                      component="div"
                      sx={{ '& p': { my: 1 }, '& pre': { whiteSpace: 'pre-wrap' } }}
                      dangerouslySetInnerHTML={{ __html: renderMarkdownToHtml(m.content) }}
                    />
                  )}
                </Box>
              </Box>
            )
          })}
          {loading && (
            <Box sx={{ display: 'flex', justifyContent: 'flex-start', my: 1 }}>
              <Box
                sx={{
                  maxWidth: { xs: '88%', sm: '76%' },
                  px: 1.5,
                  py: 1.25,
                  borderRadius: 2,
                  bgcolor: 'background.paper',
                  border: '1px solid',
                  borderColor: 'divider',
                  color: 'text.secondary',
                  fontSize: 14,
                }}
              >
                Assistant is typing…
              </Box>
            </Box>
          )}
          <Box ref={bottomRef} />
        </Paper>

        {/* Composer */}
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
          <TextField
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                if (!loading) send()
              }
            }}
            placeholder="Type a message and press Enter..."
            fullWidth
            size="medium"
            autoComplete="off"
          />
          <Button
            variant="contained"
            onClick={send}
            disabled={loading || !input.trim()}
            sx={{
              px: { xs: 2, sm: 3 },
              py: { xs: 1.25, sm: 1 },
              fontWeight: 600,
            }}
          >
            Send
          </Button>
        </Stack>
      </Box>
    </ManagementLayout>
  )
}
