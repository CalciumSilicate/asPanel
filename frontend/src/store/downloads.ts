import { computed, reactive } from 'vue'
import apiClient from '@/api'
import type { AxiosProgressEvent } from 'axios'

export type DownloadStatus = 'PREPARING' | 'DOWNLOADING' | 'SUCCESS' | 'FAILED' | 'CANCELED'

export interface DownloadItem {
  id: string
  title: string
  filename: string
  status: DownloadStatus
  progress: number
  loaded: number
  total: number | null
  message?: string | null
  error?: string | null
  created_at: number
}

export interface ArchiveDownloadSource {
  id: number | string
  name: string
  type?: string | null
}

const state = reactive({
  items: [] as DownloadItem[],
})

const controllers = new Map<string, AbortController>()

const genId = () => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `${Date.now()}_${Math.random().toString(16).slice(2)}`
}

const getFilenameFromContentDisposition = (contentDisposition: any): string | null => {
  if (!contentDisposition) return null
  const cd = String(contentDisposition)
  const utf8Match = cd.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1])
    } catch (e) {
      return utf8Match[1]
    }
  }
  const asciiMatch = cd.match(/filename=\"?([^\";]+)\"?/i)
  return asciiMatch?.[1] || null
}

const resolveDownloadError = async (error: any): Promise<string> => {
  const detail = error?.response?.data?.detail
  if (detail) return String(detail)

  const data = error?.response?.data
  if (data instanceof Blob) {
    try {
      const text = await data.text()
      try {
        const json = JSON.parse(text)
        if (json?.detail) return String(json.detail)
      } catch (e) {
        // ignore
      }
      if (text) return text
    } catch (e) {
      // ignore
    }
  }

  return String(error?.message || '下载失败')
}

const upsert = (item: DownloadItem) => {
  const idx = state.items.findIndex((x) => x.id === item.id)
  if (idx === -1) state.items.unshift(item)
  else state.items[idx] = { ...state.items[idx], ...item }
}

const prune = (maxItems = 60) => {
  if (state.items.length <= maxItems) return
  const keep = state.items.slice(0, maxItems)
  const keepIds = new Set(keep.map((x) => x.id))
  state.items.forEach((x) => {
    if (!keepIds.has(x.id)) controllers.delete(x.id)
  })
  state.items = keep as any
}

export const downloads = computed(() => state.items)
export const activeDownloadsCount = computed(
  () => state.items.filter((d) => d.status === 'PREPARING' || d.status === 'DOWNLOADING').length
)
export const finishedDownloadsCount = computed(
  () => state.items.filter((d) => d.status === 'SUCCESS' || d.status === 'FAILED' || d.status === 'CANCELED').length
)

export const clearFinishedDownloads = () => {
  state.items = state.items.filter((d) => d.status === 'PREPARING' || d.status === 'DOWNLOADING') as any
}

export const clearDownload = (id: string) => {
  controllers.delete(id)
  const idx = state.items.findIndex((d) => d.id === id)
  if (idx !== -1) state.items.splice(idx, 1)
}

export const cancelDownload = (id: string) => {
  const controller = controllers.get(id)
  try {
    controller?.abort()
  } catch (e) {
    // ignore
  }
}

export const downloadArchive = async (archive: ArchiveDownloadSource) => {
  const id = genId()
  const created_at = Date.now()
  const fallbackFilename =
    String(archive?.type || '').toUpperCase() === 'SERVER' ? `${archive.name}.tar.gz` : `${archive.name}.zip`

  const item: DownloadItem = {
    id,
    title: archive?.name || '存档下载',
    filename: fallbackFilename,
    status: 'PREPARING',
    progress: 0,
    loaded: 0,
    total: null,
    message: '准备下载…',
    error: null,
    created_at,
  }
  upsert(item)
  prune()

  const controller = new AbortController()
  controllers.set(id, controller)

  try {
    const res = await apiClient.get(`/api/archives/download/${archive.id}`, {
      responseType: 'blob',
      signal: controller.signal,
      onDownloadProgress: (evt: AxiosProgressEvent) => {
        const loaded = Number(evt.loaded ?? 0)
        const total = Number.isFinite(Number(evt.total)) ? Number(evt.total) : null
        const progress = total ? Math.min(99, Math.round((loaded / total) * 100)) : 0
        upsert({
          id,
          loaded,
          total,
          progress,
          status: 'DOWNLOADING',
          message: total ? `下载中… ${progress}%` : '下载中…',
        } as any)
      },
    })

    const cd = (res.headers as any)?.['content-disposition']
    const filename = getFilenameFromContentDisposition(cd) || fallbackFilename

    const blob = res.data instanceof Blob ? res.data : new Blob([res.data], { type: (res.headers as any)?.['content-type'] })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', filename)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)

    upsert({
      id,
      filename,
      status: 'SUCCESS',
      progress: 100,
      loaded: (blob as any).size ?? item.loaded,
      total: (blob as any).size ?? item.total,
      message: '下载完成',
      error: null,
    } as any)
  } catch (error: any) {
    const canceled = error?.code === 'ERR_CANCELED' || error?.name === 'CanceledError'
    upsert({
      id,
      status: canceled ? 'CANCELED' : 'FAILED',
      message: canceled ? '已取消' : '下载失败',
      error: canceled ? null : await resolveDownloadError(error),
    } as any)
  } finally {
    controllers.delete(id)
  }
}
