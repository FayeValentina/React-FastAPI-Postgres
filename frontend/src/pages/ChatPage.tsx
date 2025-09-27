import { useEffect, useMemo, useRef, useState } from 'react'
import { Box, Button, Paper, Popover, Slider, Stack, TextField, Typography } from '@mui/material'
import { useAuthStore } from '../stores/auth-store'
import ManagementLayout from '../components/Layout/ManagementLayout'
import { renderMarkdownToHtml } from '../utils/markdown'

type CitationItem = {
  key: string
  chunkId: number | null
  documentId: number | null
  chunkIndex: number | null
  title?: string | null
  sourceRef?: string | null
  similarity?: number | null
  content: string
}

type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
  citations?: CitationItem[]
}

type CitationPayload = {
  key?: string
  chunk_id?: number | null
  document_id?: number | null
  chunk_index?: number | null
  title?: string | null
  source_ref?: string | null
  similarity?: number | null
  content?: string
}

export default function ChatPage() {
  const wsRef = useRef<WebSocket | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [temperature, setTemperature] = useState<number>(0.5)
  const bottomRef = useRef<HTMLDivElement | null>(null)
  const accessToken = useAuthStore((s) => s.accessToken)
  const [citationAnchor, setCitationAnchor] = useState<HTMLElement | null>(null)
  const [activeMessageIndex, setActiveMessageIndex] = useState<number | null>(null)
  const [activeCitationKey, setActiveCitationKey] = useState<string | null>(null)

  useEffect(() => {
    const base = (import.meta.env.VITE_API_URL || '').replace(/^http/, 'ws') + '/v1/ws/chat'
    const url = accessToken ? `${base}?token=${encodeURIComponent(accessToken)}` : base
    const ws = new WebSocket(url)
    wsRef.current = ws
    ws.onmessage = (ev) => {
      const data = JSON.parse(ev.data)
      if (data.type === 'citations') {
        const rawItems: CitationPayload[] = Array.isArray(data.items) ? data.items : []
        const items = rawItems.reduce<CitationItem[]>((acc, item) => {
          const key = item.key ?? ''
          if (!key) {
            return acc
          }
          acc.push({
            key,
            chunkId: item.chunk_id ?? null,
            documentId: item.document_id ?? null,
            chunkIndex: item.chunk_index ?? null,
            title: item.title ?? null,
            sourceRef: item.source_ref ?? null,
            similarity: item.similarity ?? null,
            content: item.content ?? '',
          })
          return acc
        }, [])

        setMessages((prev) => {
          if (!prev.length) return prev
          const next = prev.slice()
          const lastIndex = next.length - 1
          const last = next[lastIndex]
          if (last && last.role === 'assistant') {
            next[lastIndex] = { ...last, citations: items }
          }
          return next
        })
        return
      }

      if (data.type === 'delta') {
        setMessages((prev) => {
          if (!prev.length) {
            return [{ role: 'assistant', content: data.content }]
          }
          const copy = prev.slice()
          const lastIndex = copy.length - 1
          const last = copy[lastIndex]
          if (last && last.role === 'assistant') {
            copy[lastIndex] = { ...last, content: (last.content || '') + data.content }
          } else {
            copy.push({ role: 'assistant', content: data.content })
          }
          return copy
        })
      } else if (data.type === 'done') {
        setLoading(false)
        setCitationAnchor(null)
        setActiveCitationKey(null)
        setActiveMessageIndex(null)
      } else if (data.type === 'error') {
        setLoading(false)
        setCitationAnchor(null)
        setActiveCitationKey(null)
        setActiveMessageIndex(null)
      } else if (data.type === 'reset_ok') {
        setLoading(false)
        setCitationAnchor(null)
        setActiveCitationKey(null)
        setActiveMessageIndex(null)
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
    setMessages((prev) => [...prev, { role: 'user', content: text }, { role: 'assistant', content: '' }])
    setLoading(true)
    wsRef.current.send(JSON.stringify({ content: text, temperature }))
    setInput('')
  }

  const handleCitationClick = (event: React.MouseEvent<HTMLElement>, messageIndex: number) => {
    const target = event.target as HTMLElement | null
    const citeEl = target?.closest('[data-cite-key]') as HTMLElement | null
    if (!citeEl) return
    const citeKey = citeEl.dataset.citeKey
    if (!citeKey) return
    event.preventDefault()
    setCitationAnchor(citeEl)
    setActiveMessageIndex(messageIndex)
    setActiveCitationKey(citeKey)
  }

  const closeCitation = () => {
    setCitationAnchor(null)
    setActiveMessageIndex(null)
    setActiveCitationKey(null)
  }

  const activeCitation = useMemo(() => {
    if (activeMessageIndex === null || !activeCitationKey) return undefined
    return messages[activeMessageIndex]?.citations?.find((c) => c.key === activeCitationKey)
  }, [activeCitationKey, activeMessageIndex, messages])

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
              closeCitation()
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
                      sx={{
                        '& p': { my: 1 },
                        '& pre': { whiteSpace: 'pre-wrap' },
                        '& sup[data-cite-key]': {
                          cursor: 'pointer',
                          color: 'primary.main',
                          fontWeight: 600,
                          transition: 'color 0.15s ease',
                        },
                        '& sup[data-cite-key]:hover': {
                          color: 'primary.dark',
                          textDecoration: 'underline',
                        },
                      }}
                      onClick={(event) => handleCitationClick(event, i)}
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

        <Popover
          open={Boolean(citationAnchor && activeCitation)}
          anchorEl={citationAnchor}
          onClose={closeCitation}
          anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
          transformOrigin={{ vertical: 'bottom', horizontal: 'center' }}
          PaperProps={{
            sx: {
              maxWidth: 320,
              p: 1.5,
            },
          }}
        >
          {activeCitation ? (
            <Stack spacing={1}>
              <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                {activeCitation.key}
              </Typography>
              {(activeCitation.title || activeCitation.sourceRef) && (
                <Box>
                  {activeCitation.title && (
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {activeCitation.title}
                    </Typography>
                  )}
                  {activeCitation.sourceRef && (
                    <Typography variant="body2" color="text.secondary">
                      {activeCitation.sourceRef}
                    </Typography>
                  )}
                </Box>
              )}
              {(activeCitation.chunkIndex !== null || activeCitation.similarity !== null) && (
                <Typography variant="caption" color="text.disabled">
                  {activeCitation.chunkIndex !== null && `Chunk #${activeCitation.chunkIndex}`}
                  {activeCitation.chunkIndex !== null && activeCitation.similarity !== null && ' • '}
                  {activeCitation.similarity != null && `sim ${activeCitation.similarity.toFixed(2)}`}
                </Typography>
              )}
              <Typography variant="body2" sx={{ whiteSpace: 'pre-line' }}>
                {activeCitation.content}
              </Typography>
            </Stack>
          ) : (
            <Typography variant="body2" color="text.secondary">
              Citation unavailable
            </Typography>
          )}
        </Popover>
      </Box>
    </ManagementLayout>
  )
}
