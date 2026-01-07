// frontend/src/store/transfers.ts
// 通用传输管理 store - 支持上传和下载进度跟踪

import { computed, reactive } from 'vue'
import apiClient, { isRequestCanceled } from '@/api'
import type { AxiosProgressEvent, AxiosRequestConfig } from 'axios'

export type TransferType = 'download' | 'upload'
export type TransferStatus = 'PREPARING' | 'TRANSFERRING' | 'SUCCESS' | 'FAILED' | 'CANCELED'

export interface TransferItem {
  id: string
  type: TransferType
  title: string
  filename: string
  status: TransferStatus
  progress: number
  loaded: number
  total: number | null
  message?: string | null
  error?: string | null
  created_at: number
}

const state = reactive({
  items: [] as TransferItem[],
})

const controllers = new Map<string, AbortController>()
const userCanceled = new Set<string>()

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

const resolveTransferError = async (error: any): Promise<string> => {
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

  return String(error?.message || '传输失败')
}

const upsert = (item: Partial<TransferItem> & { id: string }) => {
  const idx = state.items.findIndex((x) => x.id === item.id)
  if (idx === -1) state.items.unshift(item as TransferItem)
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

export const transfers = computed(() => state.items)

export const activeTransfersCount = computed(
  () => state.items.filter((d) => d.status === 'PREPARING' || d.status === 'TRANSFERRING').length
)

export const hasActiveTransfers = computed(() => activeTransfersCount.value > 0)

export const activeDownloadsCount = computed(
  () => state.items.filter((d) => d.type === 'download' && (d.status === 'PREPARING' || d.status === 'TRANSFERRING')).length
)

export const activeUploadsCount = computed(
  () => state.items.filter((d) => d.type === 'upload' && (d.status === 'PREPARING' || d.status === 'TRANSFERRING')).length
)

export const finishedTransfersCount = computed(
  () => state.items.filter((d) => d.status === 'SUCCESS' || d.status === 'FAILED' || d.status === 'CANCELED').length
)

export const clearFinishedTransfers = () => {
  state.items = state.items.filter((d) => d.status === 'PREPARING' || d.status === 'TRANSFERRING') as any
}

export const clearTransfer = (id: string) => {
  controllers.delete(id)
  const idx = state.items.findIndex((d) => d.id === id)
  if (idx !== -1) state.items.splice(idx, 1)
}

export const cancelTransfer = (id: string) => {
  userCanceled.add(id)
  const controller = controllers.get(id)
  try {
    controller?.abort('user-canceled')
  } catch (e) {
    // ignore
  }
  clearTransfer(id)
}

export interface DownloadOptions {
  url: string
  title?: string
  fallbackFilename?: string
  params?: Record<string, any>
  method?: 'get' | 'post'
  data?: any
}

export const startDownload = async (options: DownloadOptions): Promise<string> => {
  const id = genId()
  const created_at = Date.now()
  const fallbackFilename = options.fallbackFilename || 'download'

  const item: TransferItem = {
    id,
    type: 'download',
    title: options.title || fallbackFilename,
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
    const requestConfig = {
      responseType: 'blob' as const,
      timeout: 0,
      signal: controller.signal,
      params: options.params,
      onDownloadProgress: (evt: AxiosProgressEvent) => {
        if (userCanceled.has(id) || controller.signal.aborted) return
        const loaded = Number(evt.loaded ?? 0)
        const total = Number.isFinite(Number(evt.total)) ? Number(evt.total) : null
        const progress = total ? Math.min(99, Math.round((loaded / total) * 100)) : 0
        upsert({
          id,
          loaded,
          total,
          progress,
          status: 'TRANSFERRING',
          message: total ? `下载中… ${progress}%` : '下载中…',
        })
      },
    }
    
    const res = options.method === 'post'
      ? await apiClient.post(options.url, options.data, requestConfig)
      : await apiClient.get(options.url, requestConfig)

    if (userCanceled.has(id) || controller.signal.aborted) {
      clearTransfer(id)
      return id
    }

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
    })
  } catch (error: any) {
    const canceled = isRequestCanceled(error) || error?.code === 'ERR_CANCELED' || error?.name === 'CanceledError'
    if (canceled) {
      clearTransfer(id)
      return id
    }
    upsert({
      id,
      status: 'FAILED',
      message: '下载失败',
      error: await resolveTransferError(error),
    })
  } finally {
    userCanceled.delete(id)
    controllers.delete(id)
  }

  return id
}

export interface UploadOptions {
  url: string
  data: FormData
  title?: string
  filename?: string
  params?: Record<string, any>
  method?: 'post' | 'put'
}

export const startUpload = async (options: UploadOptions): Promise<{ id: string; response?: any; error?: string }> => {
  const id = genId()
  const created_at = Date.now()
  const filename = options.filename || 'upload'

  const item: TransferItem = {
    id,
    type: 'upload',
    title: options.title || filename,
    filename,
    status: 'PREPARING',
    progress: 0,
    loaded: 0,
    total: null,
    message: '准备上传…',
    error: null,
    created_at,
  }
  upsert(item)
  prune()

  const controller = new AbortController()
  controllers.set(id, controller)

  try {
    const config: AxiosRequestConfig = {
      timeout: 0,
      signal: controller.signal,
      params: options.params,
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (evt: AxiosProgressEvent) => {
        if (userCanceled.has(id) || controller.signal.aborted) return
        const loaded = Number(evt.loaded ?? 0)
        const total = Number.isFinite(Number(evt.total)) ? Number(evt.total) : null
        const progress = total ? Math.min(99, Math.round((loaded / total) * 100)) : 0
        upsert({
          id,
          loaded,
          total,
          progress,
          status: 'TRANSFERRING',
          message: total ? `上传中… ${progress}%` : '上传中…',
        })
      },
    }

    const method = options.method || 'post'
    const res = method === 'put'
      ? await apiClient.put(options.url, options.data, config)
      : await apiClient.post(options.url, options.data, config)

    if (userCanceled.has(id) || controller.signal.aborted) {
      clearTransfer(id)
      return { id }
    }

    upsert({
      id,
      status: 'SUCCESS',
      progress: 100,
      message: '上传完成',
      error: null,
    })

    return { id, response: res.data }
  } catch (error: any) {
    const canceled = isRequestCanceled(error) || error?.code === 'ERR_CANCELED' || error?.name === 'CanceledError'
    if (canceled) {
      clearTransfer(id)
      return { id }
    }
    const errorMsg = await resolveTransferError(error)
    upsert({
      id,
      status: 'FAILED',
      message: '上传失败',
      error: errorMsg,
    })
    return { id, error: errorMsg }
  } finally {
    userCanceled.delete(id)
    controllers.delete(id)
  }
}

// 页面关闭确认 - 当有活跃传输时提示用户
let beforeUnloadHandler: ((e: BeforeUnloadEvent) => any) | null = null

export const setupBeforeUnloadWarning = () => {
  if (beforeUnloadHandler) return

  beforeUnloadHandler = (e: BeforeUnloadEvent) => {
    if (hasActiveTransfers.value) {
      e.preventDefault()
      e.returnValue = '有正在进行的上传或下载任务，确定要离开吗？'
      return e.returnValue
    }
  }

  window.addEventListener('beforeunload', beforeUnloadHandler)
}

export const removeBeforeUnloadWarning = () => {
  if (beforeUnloadHandler) {
    window.removeEventListener('beforeunload', beforeUnloadHandler)
    beforeUnloadHandler = null
  }
}

// 为兼容现有代码，保留 downloads 相关导出
export const downloads = computed(() => state.items.filter(i => i.type === 'download'))
export const downloadArchive = async (archive: { id: number | string; name: string; type?: string | null }) => {
  const fallbackFilename = String(archive?.type || '').toUpperCase() === 'SERVER'
    ? `${archive.name}.tar.gz`
    : `${archive.name}.zip`

  return startDownload({
    url: `/api/archives/download/${archive.id}`,
    title: archive.name || '存档下载',
    fallbackFilename,
  })
}

export const clearFinishedDownloads = clearFinishedTransfers
export const cancelDownload = cancelTransfer
export const clearDownload = clearTransfer
