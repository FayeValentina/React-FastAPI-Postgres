import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react'
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Paper,
  Popover,
  Slider,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import ManagementLayout from '../components/Layout/ManagementLayout'
import ChatHistoryList from '../components/Chat/ChatHistoryList'
import { renderMarkdownToHtml } from '../utils/markdown'
import api from '../services/api'
import { useAuthStore } from '../stores/auth-store'
import {
  ChatCitationPayload,
  ChatEventPayload,
  ConversationListItem,
  ConversationListResponse,
  ConversationResponse,
  MessageAcceptedResponse,
  MessageListResponse,
  MessageResponse as ApiMessage,
} from '../types'

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

type ChatMessageView = {
  id?: number
  messageIndex?: number
  role: 'user' | 'assistant'
  content: string
  requestId?: string
  createdAt?: string
  updatedAt?: string
  citations?: CitationItem[]
  status?: 'pending' | 'streaming' | 'complete' | 'error'
}

interface PaginationState {
  nextBeforeIndex: number | null
  nextBeforeCreatedAt: string | null
}

const resolveApiRoot = (): string => {
  const env = import.meta.env.VITE_API_URL
  if (typeof env === 'string' && env.trim().length > 0) {
    return env.replace(/\/$/, '')
  }
  return '/api'
}

const truncateText = (value: string, limit = 200): string => {
  const text = value || ''
  if (text.length <= limit) {
    return text
  }
  return text.slice(0, limit).trimEnd() + '…'
}

const mapCitationPayload = (payload: ChatCitationPayload): CitationItem | null => {
  const key = payload.key ?? ''
  if (!key) {
    return null
  }
  return {
    key,
    chunkId: payload.chunk_id ?? null,
    documentId: payload.document_id ?? null,
    chunkIndex: payload.chunk_index ?? null,
    title: payload.title ?? null,
    sourceRef: payload.source_ref ?? null,
    similarity: payload.similarity ?? null,
    content: payload.content ?? '',
  }
}

export default function ChatPage() {
  const accessToken = useAuthStore((state) => state.accessToken)

  const [conversations, setConversations] = useState<ConversationListItem[]>([])
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyActionPending, setHistoryActionPending] = useState(false)

  const [messages, setMessages] = useState<ChatMessageView[]>([])
  const [pagination, setPagination] = useState<PaginationState | null>(null)
  const [messagesLoading, setMessagesLoading] = useState(false)
  const [loadingOlder, setLoadingOlder] = useState(false)
  const [messageError, setMessageError] = useState<string | null>(null)

  const [input, setInput] = useState('')
  const [temperature, setTemperature] = useState(0.5)
  const [isSending, setIsSending] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamStage, setStreamStage] = useState<string | null>(null)
  const [streamError, setStreamError] = useState<string | null>(null)

  const [citationAnchor, setCitationAnchor] = useState<HTMLElement | null>(null)
  const [activeMessageIndex, setActiveMessageIndex] = useState<number | null>(null)
  const [activeCitationKey, setActiveCitationKey] = useState<string | null>(null)

  const bottomRef = useRef<HTMLDivElement | null>(null)
  const skipScrollRef = useRef(false)
  const eventControllerRef = useRef<AbortController | null>(null)
  const apiRootRef = useRef<string>(resolveApiRoot())

  const mapApiMessage = useCallback((message: ApiMessage): ChatMessageView => {
    return {
      id: message.id,
      messageIndex: message.message_index,
      role: message.role,
      content: message.content,
      requestId: message.request_id,
      createdAt: message.created_at,
      updatedAt: message.updated_at,
      status: 'complete',
    }
  }, [])

  const fetchConversations = useCallback(async (mode: 'initial' | 'refresh' = 'initial') => {
    if (mode === 'initial') {
      setHistoryLoading(true)
    } else {
      setHistoryActionPending(true)
    }
    try {
      const params = new URLSearchParams({
        limit: '50',
        offset: '0',
      })
      const response = await api.get<ConversationListResponse>(`/v1/chat/conversations?${params.toString()}`)
      const items = response.items ?? []
      setConversations(items)
      setSelectedConversationId((previous) => {
        if (previous && items.some((item) => item.id === previous)) {
          return previous
        }
        return items[0]?.id ?? null
      })
    } catch (error) {
      console.error('Failed to load conversations', error)
    } finally {
      if (mode === 'initial') {
        setHistoryLoading(false)
      } else {
        setHistoryActionPending(false)
      }
    }
  }, [])

  const handleCreateConversation = useCallback(async (): Promise<ConversationResponse | null> => {
    setHistoryActionPending(true)
    try {
      const conversation = await api.post<ConversationResponse>('/v1/chat/conversations', {})
      const listItem: ConversationListItem = {
        ...conversation,
        last_message_preview: null,
      }
      setConversations((prev) => [listItem, ...prev])
      setSelectedConversationId(conversation.id)
      setMessages([])
      setPagination(null)
      setMessageError(null)
      return conversation
    } catch (error) {
      console.error('Failed to create conversation', error)
      return null
    } finally {
      setHistoryActionPending(false)
    }
  }, [])

  const ensureConversationExists = useCallback(async (): Promise<string | null> => {
    if (selectedConversationId) {
      return selectedConversationId
    }
    const created = await handleCreateConversation()
    return created?.id ?? null
  }, [handleCreateConversation, selectedConversationId])

  const loadMessages = useCallback(
    async (conversationId: string) => {
      setMessagesLoading(true)
      setMessageError(null)
      try {
        const params = new URLSearchParams({
          limit: '50',
        })
        const response = await api.get<MessageListResponse>(
          `/v1/chat/conversations/${conversationId}/messages?${params.toString()}`
        )
        const mapped = (response.messages ?? []).map(mapApiMessage)
        setMessages(mapped)
        setPagination({
          nextBeforeIndex: response.next_before_index ?? null,
          nextBeforeCreatedAt: response.next_before_created_at ?? null,
        })
      } catch (error) {
        console.error('Failed to load messages', error)
        setMessageError('无法加载聊天记录，请稍后重试。')
        setMessages([])
        setPagination(null)
      } finally {
        setMessagesLoading(false)
      }
    },
    [mapApiMessage]
  )

  const loadOlderMessages = useCallback(async () => {
    if (!selectedConversationId || !pagination) return
    const { nextBeforeIndex, nextBeforeCreatedAt } = pagination
    if (nextBeforeIndex == null && !nextBeforeCreatedAt) return

    skipScrollRef.current = true
    setLoadingOlder(true)
    try {
      const params = new URLSearchParams({
        limit: '50',
      })
      if (nextBeforeIndex != null) {
        params.set('before_message_index', String(nextBeforeIndex))
      }
      if (nextBeforeCreatedAt) {
        params.set('before_created_at', nextBeforeCreatedAt)
      }

      const response = await api.get<MessageListResponse>(
        `/v1/chat/conversations/${selectedConversationId}/messages?${params.toString()}`
      )
      const mapped = (response.messages ?? []).map(mapApiMessage)
      setMessages((prev) => [...mapped, ...prev])
      setPagination({
        nextBeforeIndex: response.next_before_index ?? null,
        nextBeforeCreatedAt: response.next_before_created_at ?? null,
      })
    } catch (error) {
      console.error('Failed to load older messages', error)
    } finally {
      setLoadingOlder(false)
    }
  }, [mapApiMessage, pagination, selectedConversationId])

  const handleSendMessage = useCallback(async () => {
    const trimmed = input.trim()
    if (!trimmed || isSending || isStreaming) {
      return
    }
    setIsSending(true)
    setStreamError(null)

    try {
      const conversationId = await ensureConversationExists()
      if (!conversationId) {
        throw new Error('Conversation unavailable')
      }

      const response = await api.post<MessageAcceptedResponse>(
        `/v1/chat/conversations/${conversationId}/messages`,
        {
          content: trimmed,
          temperature,
        }
      )

      const requestId = response.request_id
      const nowIso = new Date().toISOString()

      setMessages((prev) => [
        ...prev,
        {
          role: 'user',
          content: trimmed,
          requestId,
          createdAt: nowIso,
          status: 'complete',
        },
        {
          role: 'assistant',
          content: '',
          requestId,
          createdAt: nowIso,
          status: 'streaming',
        },
      ])
      setInput('')
      setIsStreaming(true)
      setStreamStage('queued')
    } catch (error) {
      console.error('Failed to send message', error)
      setStreamError('发送消息失败，请稍后重试。')
    } finally {
      setIsSending(false)
    }
  }, [ensureConversationExists, input, isSending, isStreaming, temperature])

  const handleSseEvent = useCallback((event: ChatEventPayload) => {
    const requestId = event.request_id
    if (!requestId) {
      return
    }

    if (event.type === 'progress') {
      setStreamStage(event.stage ?? null)
      if (event.stage === 'recovered') {
        setIsStreaming(false)
      }
      return
    }

    if (event.type === 'citations') {
      if (!event.citations?.length) return
      const mapped = event.citations
        .map(mapCitationPayload)
        .filter(Boolean) as CitationItem[]

      setMessages((prev) => {
        const next = [...prev]
        const idx = next.findIndex((msg) => msg.role === 'assistant' && msg.requestId === requestId)
        if (idx !== -1) {
          next[idx] = {
            ...next[idx],
            citations: mapped,
          }
        }
        return next
      })
      return
    }

    if (event.type === 'delta') {
      if (typeof event.content !== 'string') return
      const deltaContent = event.content
      setMessages((prev) => {
        const next = [...prev]
        const idx = next.findIndex((msg) => msg.role === 'assistant' && msg.requestId === requestId)
        if (idx === -1) {
          next.push({
            role: 'assistant',
            content: deltaContent,
            requestId,
            status: 'streaming',
          })
        } else {
          const current = next[idx]
          next[idx] = {
            ...current,
            content: (current.content || '') + deltaContent,
            status: 'streaming',
          }
        }
        return next
      })
      setIsStreaming(true)
      return
    }

    if (event.type === 'done') {
      let assistantPreview = ''
      setMessages((prev) =>
        prev.map((msg) => {
          if (msg.requestId === requestId) {
            if (msg.role === 'assistant') {
              assistantPreview = msg.content
            }
            return {
              ...msg,
              status: 'complete',
            }
          }
          return msg
        })
      )
      setIsStreaming(false)
      setStreamStage(null)
      setStreamError(null)

      setConversations((prev) => {
        const index = prev.findIndex((item) => item.id === event.conversation_id)
        if (index === -1) {
          return prev
        }
        const previousPreview = prev[index].last_message_preview
        const nextPreview = assistantPreview
          ? truncateText(assistantPreview)
          : previousPreview !== undefined
            ? previousPreview
            : null

        const updatedItem: ConversationListItem = {
          ...prev[index],
          updated_at: new Date().toISOString(),
          last_message_preview: nextPreview,
        }
        const reordered = [updatedItem, ...prev.filter((_, idx) => idx !== index)]
        return reordered
      })
      return
    }

    if (event.type === 'error') {
      const detailMessage = event.detail || event.message || '后台处理失败。'
      setMessages((prev) =>
        prev.map((msg) => {
          if (msg.requestId === requestId) {
            if (msg.role === 'assistant') {
              const fallbackContent = msg.content ? msg.content : `⚠️ ${detailMessage}`
              return {
                ...msg,
                content: fallbackContent,
                status: 'error',
              }
            }
            return {
              ...msg,
              status: 'complete',
            }
          }
          return msg
        })
      )
      setIsStreaming(false)
      setStreamStage(null)
      setStreamError('助手生成回答时出现问题，请稍后再试。')
    }
  }, [])

  useEffect(() => {
    fetchConversations('initial')
  }, [fetchConversations])

  useEffect(() => {
    if (!selectedConversationId) {
      setMessages([])
      setPagination(null)
      setMessageError(null)
      return
    }
    loadMessages(selectedConversationId)
  }, [loadMessages, selectedConversationId])

  useEffect(() => {
    setStreamError(null)
    setStreamStage(null)
    setIsStreaming(false)
  }, [selectedConversationId])

  useEffect(() => {
    if (!selectedConversationId || !accessToken) {
      if (eventControllerRef.current) {
        eventControllerRef.current.abort()
        eventControllerRef.current = null
      }
      return
    }

    const controller = new AbortController()
    if (eventControllerRef.current) {
      eventControllerRef.current.abort()
    }
    eventControllerRef.current = controller

    const connect = async () => {
      try {
        const url = `${apiRootRef.current}/v1/chat/conversations/${selectedConversationId}/events`
        const response = await fetch(url, {
          headers: {
            Authorization: `Bearer ${accessToken}`,
            Accept: 'text/event-stream',
          },
          credentials: 'include',
          signal: controller.signal,
        })

        if (!response.ok) {
          throw new Error(`SSE connection failed with status ${response.status}`)
        }
        if (!response.body) {
          throw new Error('SSE response does not contain a readable body')
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        const processBuffer = () => {
          let match: RegExpMatchArray | null
          // Handle both LF and CRLF event delimiters.
          while ((match = buffer.match(/\r?\n\r?\n/))) {
            const delimiter = match[0]
            if (!delimiter) {
              break
            }
            const boundaryIndex = match.index ?? buffer.indexOf(delimiter)
            if (boundaryIndex === -1) {
              break
            }

            const rawEvent = buffer.slice(0, boundaryIndex)
            buffer = buffer.slice(boundaryIndex + delimiter.length)

            const dataLines = rawEvent
              .split(/\r?\n/)
              .filter((line) => line.startsWith('data:'))
              .map((line) => line.slice(5).trim())

            if (dataLines.length) {
              const payloadText = dataLines.join('\n')
              try {
                const payload = JSON.parse(payloadText) as ChatEventPayload
                if (payload.conversation_id === selectedConversationId) {
                  handleSseEvent(payload)
                }
              } catch (error) {
                console.error('Failed to parse SSE payload', error, payloadText)
              }
            }
          }
        }

        while (true) {
          const { value, done } = await reader.read()
          const chunk = decoder.decode(value ?? new Uint8Array(), { stream: !done })
          buffer += chunk
          processBuffer()
          if (done) {
            // Flush any trailing buffered bytes.
            buffer += decoder.decode()
            processBuffer()
            break
          }
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          console.error('SSE connection error', error)
          setStreamError('事件流连接中断，请刷新页面后重试。')
        }
      }
    }

    connect()

    return () => {
      controller.abort()
      if (eventControllerRef.current === controller) {
        eventControllerRef.current = null
      }
    }
  }, [accessToken, handleSseEvent, selectedConversationId])

  useEffect(() => {
    return () => {
      if (eventControllerRef.current) {
        eventControllerRef.current.abort()
      }
    }
  }, [])

  useEffect(() => {
    if (skipScrollRef.current) {
      skipScrollRef.current = false
      return
    }
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, isStreaming])

  const closeCitation = useCallback(() => {
    setCitationAnchor(null)
    setActiveCitationKey(null)
    setActiveMessageIndex(null)
  }, [])

  const handleCitationClick = useCallback(
    (event: ReactMouseEvent<HTMLElement>, messageIndex: number) => {
      const target = event.target as HTMLElement | null
      const citeEl = target?.closest('[data-cite-key]') as HTMLElement | null
      if (!citeEl) return
      const citeKey = citeEl.dataset.citeKey
      if (!citeKey) return
      event.preventDefault()
      setCitationAnchor(citeEl)
      setActiveMessageIndex(messageIndex)
      setActiveCitationKey(citeKey)
    },
    []
  )

  useEffect(() => {
    // Close popover if the underlying message array changes drastically
    if (activeMessageIndex !== null && (activeMessageIndex < 0 || activeMessageIndex >= messages.length)) {
      closeCitation()
    }
  }, [activeMessageIndex, closeCitation, messages.length])

  const activeCitation = useMemo(() => {
    if (activeMessageIndex === null || !activeCitationKey) return undefined
    return messages[activeMessageIndex]?.citations?.find((citation) => citation.key === activeCitationKey)
  }, [activeCitationKey, activeMessageIndex, messages])

  const stageLabel = useMemo(() => {
    switch (streamStage) {
      case 'queued':
        return '请求已排队，正在启动任务…'
      case 'retrieval':
        return '正在检索相关知识片段…'
      case 'generating':
        return '助手正在生成回答…'
      case 'recovered':
        return '已恢复历史回答。'
      default:
        return null
    }
  }, [streamStage])

  const activeConversation = useMemo(
    () => conversations.find((conversation) => conversation.id === selectedConversationId) ?? null,
    [conversations, selectedConversationId]
  )

  const hasMoreHistory =
    !!pagination &&
    (pagination.nextBeforeIndex !== null || (pagination.nextBeforeCreatedAt !== null && pagination.nextBeforeCreatedAt !== undefined))

  const handleSelectConversation = useCallback(
    (conversationId: string) => {
      if (conversationId === selectedConversationId) return
      setSelectedConversationId(conversationId)
      closeCitation()
    },
    [closeCitation, selectedConversationId]
  )

  const handleRefreshConversations = useCallback(() => {
    fetchConversations('refresh')
  }, [fetchConversations])

  const handleCreateConversationClick = useCallback(() => {
    void handleCreateConversation()
  }, [handleCreateConversation])

  return (
    <ManagementLayout>
      <Box
        sx={{
          display: 'flex',
          flexDirection: { xs: 'column', lg: 'row' },
          gap: { xs: 3, lg: 4 },
          alignItems: 'stretch',
          py: { xs: 1.5, md: 3 },
        }}
      >
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography
            variant="h5"
            sx={{
              fontSize: { xs: 20, sm: 24, md: 28 },
              fontWeight: 600,
              mb: 2,
            }}
          >
            Local LLM Chat
          </Typography>

          <Paper
            variant="outlined"
            sx={{
              p: { xs: 1.5, sm: 2 },
              mb: 3,
            }}
          >
            <Stack
              direction={{ xs: 'column', md: 'row' }}
              spacing={{ xs: 1.5, md: 3 }}
              alignItems={{ xs: 'stretch', md: 'center' }}
              justifyContent="space-between"
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
              <Stack direction="column" spacing={0.5} sx={{ minWidth: { md: 220 } }}>
                <Typography variant="caption" color="text.secondary">
                  当前会话
                </Typography>
                <Typography
                  variant="body1"
                  sx={{
                    fontWeight: 600,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {activeConversation?.title || '新建对话'}
                </Typography>
              </Stack>
            </Stack>
          </Paper>

          <Paper
            variant="outlined"
            sx={{
              p: { xs: 1.5, sm: 2 },
              minHeight: { xs: 360, md: 420 },
              maxHeight: { xs: '60vh', md: '65vh' },
              overflowY: 'auto',
              bgcolor: 'grey.50',
              display: 'flex',
              flexDirection: 'column',
              gap: 1.5,
            }}
          >
            {messageError && (
              <Alert severity="error" sx={{ mb: 1 }}>
                {messageError}
              </Alert>
            )}

            {messagesLoading && !messages.length ? (
              <Box sx={{ py: 4, textAlign: 'center' }}>
                <CircularProgress size={28} />
              </Box>
            ) : null}

            {hasMoreHistory && (
              <Box sx={{ textAlign: 'center' }}>
                <Button
                  variant="text"
                  size="small"
                  onClick={loadOlderMessages}
                  disabled={loadingOlder}
                >
                  {loadingOlder ? '加载中…' : '加载更早的消息'}
                </Button>
              </Box>
            )}

            {messages.map((message, index) => {
              const isUser = message.role === 'user'
              const key =
                message.id ??
                (message.requestId ? `${message.requestId}-${index}` : `message-${index}`)
              const borderColor =
                message.status === 'error'
                  ? 'error.light'
                  : 'divider'

              return (
                <Box
                  key={key}
                  sx={{
                    display: 'flex',
                    justifyContent: isUser ? 'flex-end' : 'flex-start',
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
                      borderColor,
                      boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
                      whiteSpace: 'pre-wrap',
                      fontSize: 14,
                    }}
                  >
                    {isUser ? (
                      message.content
                    ) : message.content ? (
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
                        onClick={(event) => handleCitationClick(event, index)}
                        dangerouslySetInnerHTML={{ __html: renderMarkdownToHtml(message.content) }}
                      />
                    ) : (
                      <Typography variant="body2" color="text.secondary">
                        助手正在生成回答…
                      </Typography>
                    )}
                    {message.status === 'error' && (
                      <Typography variant="caption" color="error.main" sx={{ mt: 1, display: 'block' }}>
                        回答未完成，请稍后重试。
                      </Typography>
                    )}
                  </Box>
                </Box>
              )
            })}

            {streamError && (
              <Alert severity="warning" sx={{ mt: 1 }}>
                {streamError}
              </Alert>
            )}

            {(isStreaming || stageLabel) && (
              <Box sx={{ display: 'flex', justifyContent: 'flex-start' }}>
                <Box
                  sx={{
                    maxWidth: { xs: '88%', sm: '76%' },
                    px: 1.5,
                    py: 1,
                    borderRadius: 2,
                    bgcolor: 'background.paper',
                    border: '1px dashed',
                    borderColor: 'divider',
                    color: 'text.secondary',
                    fontSize: 14,
                    fontStyle: 'italic',
                  }}
                >
                  {stageLabel || '助手正在生成回答…'}
                </Box>
              </Box>
            )}

            <Box ref={bottomRef} />
          </Paper>

          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ mt: 3 }}>
            <TextField
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  if (!isStreaming && !isSending) {
                    void handleSendMessage()
                  }
                }
              }}
              placeholder="输入消息并按 Enter 发送..."
              fullWidth
              size="medium"
              autoComplete="off"
              disabled={isSending}
            />
            <Button
              variant="contained"
              onClick={() => void handleSendMessage()}
              disabled={isSending || isStreaming || !input.trim()}
              sx={{
                px: { xs: 2, sm: 3 },
                py: { xs: 1.25, sm: 1 },
                fontWeight: 600,
              }}
            >
              发送
            </Button>
          </Stack>
        </Box>

        <ChatHistoryList
          conversations={conversations}
          selectedConversationId={selectedConversationId}
          loading={historyLoading}
          refreshing={historyActionPending}
          onSelect={handleSelectConversation}
          onCreateConversation={handleCreateConversationClick}
          onRefresh={handleRefreshConversations}
        />
      </Box>

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
    </ManagementLayout>
  )
}
