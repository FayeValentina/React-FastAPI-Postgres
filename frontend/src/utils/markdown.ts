// Minimal, safe Markdown renderer for assistant replies.
// - Escapes HTML by default
// - Supports headings (#, ##, ###), bold, italic, inline code, code blocks, links, and unordered lists
// - Produces sanitized HTML using only a limited set of tags

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function escapeAttr(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function renderInline(md: string): string {
  // inline code
  let s = md.replace(/`([^`]+)`/g, (_m, g1) => `<code>${g1}</code>`)
  // bold then italic
  s = s.replace(/\*\*([^*]+)\*\*/g, (_m, g1) => `<strong>${g1}</strong>`)
  s = s.replace(/\*([^*]+)\*/g, (_m, g1) => `<em>${g1}</em>`)
  // links [text](url)
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, text, url) => {
    const safeUrl = String(url || '')
    const href = escapeAttr(safeUrl)
    const label = text
    return `<a href="${href}" target="_blank" rel="noopener noreferrer">${label}</a>`
  })
  // citations [CITEx]
  s = s.replace(/\[CITE(\d+)\]/g, (_m, idx) => {
    const key = `CITE${idx}`
    return `<sup data-cite-key="${key}">[${key}]</sup>`
  })
  return s
}

export function renderMarkdownToHtml(md: string): string {
  if (!md) return ''
  const lines = (md.replace(/\r\n/g, '\n')).split('\n')
  const html: string[] = []

  let inCode = false
  let codeLang = ''
  let codeBuf: string[] = []
  let inList = false
  let listBuf: string[] = []
  let paraBuf: string[] = []

  const flushParagraph = () => {
    if (paraBuf.length) {
      const text = escapeHtml(paraBuf.join(' '))
      html.push(`<p>${renderInline(text)}</p>`)
      paraBuf = []
    }
  }
  const flushList = () => {
    if (listBuf.length) {
      html.push(`<ul>${listBuf.join('')}</ul>`)
      listBuf = []
    }
    inList = false
  }
  const flushCode = () => {
    if (inCode) {
      const code = escapeHtml(codeBuf.join('\n'))
      const langClass = codeLang ? ` class="language-${escapeAttr(codeLang)}"` : ''
      html.push(`<pre><code${langClass}>${code}</code></pre>`)
      codeBuf = []
      codeLang = ''
      inCode = false
    }
  }

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i]
    const line = raw.trimEnd()

    // fenced code block
    const fence = line.match(/^```(.*)$/)
    if (fence) {
      if (inCode) {
        // closing fence
        flushCode()
      } else {
        // opening fence
        flushParagraph()
        flushList()
        inCode = true
        codeLang = (fence[1] || '').trim()
      }
      continue
    }
    if (inCode) {
      codeBuf.push(raw)
      continue
    }

    // list item
    const li = line.match(/^\s*[-*]\s+(.*)$/)
    if (li) {
      flushParagraph()
      if (!inList) inList = true
      const item = escapeHtml(li[1])
      listBuf.push(`<li>${renderInline(item)}</li>`)
      continue
    } else if (inList && line.trim() === '') {
      flushList()
      continue
    } else if (inList && !li) {
      // end of list on a non-list line
      flushList()
    }

    // headings
    const h3 = line.match(/^###\s+(.*)$/)
    const h2 = !h3 && line.match(/^##\s+(.*)$/)
    const h1 = !h3 && !h2 && line.match(/^#\s+(.*)$/)
    if (h3) {
      flushParagraph()
      html.push(`<h3>${renderInline(escapeHtml(h3[1]))}</h3>`) ; continue
    }
    if (h2) {
      flushParagraph()
      html.push(`<h2>${renderInline(escapeHtml(h2[1]))}</h2>`) ; continue
    }
    if (h1) {
      flushParagraph()
      html.push(`<h1>${renderInline(escapeHtml(h1[1]))}</h1>`) ; continue
    }

    // blank line flushes paragraph
    if (line.trim() === '') {
      flushParagraph()
    } else {
      paraBuf.push(line)
    }
  }

  // flush remaining buffers
  flushCode()
  flushList()
  const hadPara = paraBuf.length > 0
  flushParagraph()
  if (!html.length && hadPara) {
    // fallback if only paragraph content existed
    const text = escapeHtml(paraBuf.join(' '))
    html.push(`<p>${renderInline(text)}</p>`)
  }

  return html.join('\n')
}
