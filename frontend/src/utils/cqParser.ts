// CQ Code parsing utilities for ChatRoom

export interface Segment {
  kind: 'text' | 'tag' | 'reply' | 'share' | 'image' | 'record' | 'data'
  text?: string
  label?: string
  url?: string
  title?: string
  displayUrl?: string
  content?: string
  unsupported?: boolean
  raw?: string
}

const unsupportedLabels: Record<string, string> = {
  rps: '[猜拳]',
  dice: '[骰子]',
  shake: '[抖一抖]',
  anonymous: '[匿名消息]',
  contact: '[名片]',
  location: '[位置]',
  music: '[音乐]',
  redbag: '[红包]',
  poke: '[戳一戳]',
  gift: '[礼物]',
  cardimage: '[卡片图片]',
  tts: '[语音合成]',
}

const defaultOrigin =
  typeof window !== 'undefined' && window.location
    ? window.location.origin
    : 'http://localhost'

export const normalizeContent = (value: unknown): string => {
  if (value === null || value === undefined) return ''
  return typeof value === 'string' ? value : String(value)
}

const cqUnescape = (text: string): string => {
  if (!text) return ''
  return text
    .replace(/&amp;/g, '&')
    .replace(/&#91;/g, '[')
    .replace(/&#93;/g, ']')
    .replace(/&#44;/g, ',')
}

const CQ_REGEX = /\[CQ:([^\],]+)((?:,[^\]]+)*)\]/g

const parseCQSegments = (content: unknown) => {
  const text =
    typeof content === 'string'
      ? content
      : content !== null && content !== undefined
        ? String(content)
        : ''
  if (!text) return []
  const result: Array<{ type: string; text?: string; data?: Record<string, string>; raw?: string }> = []
  let lastIndex = 0
  CQ_REGEX.lastIndex = 0
  let match: RegExpExecArray | null
  while ((match = CQ_REGEX.exec(text)) !== null) {
    const index = match.index
    if (index > lastIndex) {
      const piece = text.slice(lastIndex, index)
      if (piece) result.push({ type: 'text', text: cqUnescape(piece) })
    }
    const type = match[1] || ''
    const paramsRaw = match[2] || ''
    const data: Record<string, string> = {}
    if (paramsRaw) {
      paramsRaw
        .slice(1)
        .split(',')
        .forEach((param) => {
          if (!param) return
          const eq = param.indexOf('=')
          if (eq === -1) {
            data[param] = ''
          } else {
            data[param.slice(0, eq)] = cqUnescape(param.slice(eq + 1))
          }
        })
    }
    result.push({ type, data, raw: match[0] })
    lastIndex = index + match[0].length
  }
  if (lastIndex < text.length) {
    const tail = text.slice(lastIndex)
    if (tail) result.push({ type: 'text', text: cqUnescape(tail) })
  }
  return result
}

const sanitizeCqMediaUrl = (value: unknown): string => {
  if (!value) return ''
  const raw = String(value).trim()
  if (!raw) return ''
  try {
    const url = new URL(raw, defaultOrigin)
    if (url.hostname.endsWith('qpic.cn') && url.protocol === 'http:') {
      url.protocol = 'https:'
      return url.toString()
    }
    return url.toString()
  } catch {
    if (raw.startsWith('http://') && raw.includes('.qpic.cn')) {
      return raw.replace(/^http:\/\//i, 'https://')
    }
    return raw
  }
}

const transformSegments = (
  segments: ReturnType<typeof parseCQSegments>,
): Segment[] => {
  const mapped: Segment[] = []
  segments.forEach((seg) => {
    const type = seg.type
    if (type === 'text') {
      const rawText = seg.text ?? ''
      mapped.push({ kind: 'text', text: typeof rawText === 'string' ? rawText : String(rawText) })
      return
    }
    const data = (seg.data as Record<string, string>) || {}
    if (type === 'face') {
      mapped.push({ kind: 'tag', label: '[QQ表情]', raw: seg.raw })
      return
    }
    if (type === 'record') {
      const rawUrl = data.url ?? data.file ?? ''
      mapped.push({ kind: 'record', label: '[语音]', url: rawUrl ? String(rawUrl) : '', raw: seg.raw })
      return
    }
    if (type === 'video') {
      mapped.push({ kind: 'tag', label: '[短视频]', unsupported: true, raw: seg.raw })
      return
    }
    if (type === 'at') {
      const targetRaw = data.qq || data.text || ''
      const target = typeof targetRaw === 'string' ? targetRaw : String(targetRaw)
      if (target.toLowerCase() === 'all') {
        mapped.push({ kind: 'text', text: '@全体成员' })
      } else if (target) {
        mapped.push({ kind: 'text', text: `@${target}` })
      } else {
        mapped.push({ kind: 'text', text: '@' })
      }
      return
    }
    if (type === 'share') {
      const sanitizedUrl = sanitizeCqMediaUrl(data.url ?? data.jumpUrl ?? data.file ?? '')
      const rawUrl = data.url ?? data.jumpUrl ?? data.file ?? ''
      const displayUrl = rawUrl ? String(rawUrl) : ''
      const url = sanitizedUrl || displayUrl
      const rawTitle = data.title ?? data.content ?? ''
      mapped.push({ kind: 'share', label: '[链接]', url, title: rawTitle ? String(rawTitle) : '', displayUrl, raw: seg.raw })
      return
    }
    if (type === 'image') {
      const sanitizedUrl = sanitizeCqMediaUrl(data.url ?? data.file ?? '')
      const rawUrl = data.url ?? data.file ?? ''
      const url = sanitizedUrl || (rawUrl ? String(rawUrl) : '')
      mapped.push({ kind: 'image', url, raw: seg.raw })
      return
    }
    if (type === 'reply') {
      mapped.push({ kind: 'reply', label: '(回复)', raw: seg.raw })
      return
    }
    if (type === 'forward') {
      mapped.push({ kind: 'tag', label: '[合并转发]', raw: seg.raw })
      return
    }
    if (type === 'xml' || type === 'json') {
      const rawDetail = data.data ?? ''
      mapped.push({ kind: 'data', label: type === 'json' ? 'JSON消息' : 'XML消息', content: rawDetail ? String(rawDetail) : '', raw: seg.raw })
      return
    }
    const label = unsupportedLabels[type]
    if (label) {
      mapped.push({ kind: 'tag', label, unsupported: true, raw: seg.raw })
      return
    }
    mapped.push({ kind: 'tag', label: `[${type}]`, unsupported: true, raw: seg.raw })
  })
  return mapped
}

export const buildMessageSegments = (content: unknown): Segment[] => {
  const parsed = parseCQSegments(content)
  const mapped = transformSegments(parsed)
  if (mapped.length === 0) {
    const text = normalizeContent(content)
    return text ? [{ kind: 'text', text }] : []
  }
  return mapped
}
