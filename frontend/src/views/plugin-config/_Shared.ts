import apiClient from '@/api'

// 统一浏览器缓存工具（仅作用于 plugin-config 目录下的页面使用）
// - 使用 localStorage 存储，键前缀 pcache:
// - 简单 TTL 机制，默认 60s；可按需覆盖
// - 失败兜底：当网络失败且缓存存在时返回旧缓存

type CacheEntry<T> = { expires: number; value: T }

const CACHE_PREFIX = 'pcache:'

const now = () => Date.now()

const buildKey = (key: string) => `${CACHE_PREFIX}${key}`

export const getCache = <T = any>(key: string): T | null => {
  try {
    const raw = localStorage.getItem(buildKey(key))
    if (!raw) return null
    const obj = JSON.parse(raw) as CacheEntry<T>
    if (!obj || typeof obj.expires !== 'number') return null
    if (obj.expires >= now()) return obj.value
    // 过期直接返回 null（保留条目用于故障兜底）
    return null
  } catch { return null }
}

export const getStaleCache = <T = any>(key: string): T | null => {
  try {
    const raw = localStorage.getItem(buildKey(key))
    if (!raw) return null
    const obj = JSON.parse(raw) as CacheEntry<T>
    return obj?.value ?? null
  } catch { return null }
}

export const setCache = <T = any>(key: string, value: T, ttlMs = 60_000) => {
  try {
    const entry: CacheEntry<T> = { expires: now() + Math.max(0, ttlMs), value }
    localStorage.setItem(buildKey(key), JSON.stringify(entry))
  } catch { /* 忽略存储异常 */ }
}

export const invalidateCache = (key: string) => {
  try { localStorage.removeItem(buildKey(key)) } catch {}
}

export const invalidateCacheByPrefix = (prefix: string) => {
  try {
    const p = buildKey(prefix)
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i) || ''
      if (k.startsWith(p)) localStorage.removeItem(k)
    }
  } catch {}
}

const cachedGet = async <T = any>(url: string, { key = url, ttlMs = 60_000 }: { key?: string; ttlMs?: number } = {}): Promise<T> => {
  const k = key
  const cached = getCache<T>(k)
  if (cached != null) return cached
  try {
    const { data } = await apiClient.get(url)
    setCache<T>(k, data as T, ttlMs)
    return data as T
  } catch (e) {
    const stale = getStaleCache<T>(k)
    if (stale != null) return stale
    throw e
  }
}

export type Server = {
  id: number
  name: string
  status?: string
  core_config?: any
}

export const normalizeServerType = (s?: Server | null) => {
  const cfg = s?.core_config || {}
  const t = cfg.server_type || cfg.serverType
  if (t === 'velocity') return 'velocity'
  if (t === 'forge') return 'forge'
  if (t === 'vanilla' && (cfg.is_fabric || cfg.isFabric)) return 'fabric'
  return 'vanilla'
}

export const installModrinth = async (serverId: number, projectId: string) => {
  await apiClient.post('/api/mods/install/modrinth', { server_id: serverId, project_id: projectId })
}

export const installMCDR = async (serverId: number, pluginId: string, tag: string = 'latest') => {
  await apiClient.post(`/api/plugins/server/${serverId}/install/from-online?plugin_id=${encodeURIComponent(pluginId)}&tag_name=${encodeURIComponent(tag)}`)
}

export const fetchServersCached = async (ttlMs = 60_000) => {
  // 服务器列表频繁被多个配置页访问，适合短期缓存
  const data = await cachedGet<any[]>(`/api/servers`, { key: `servers`, ttlMs })
  return data || []
}

export const fetchServerPlugins = async (serverId: number, { ttlMs = 60_000, cached = true }: { ttlMs?: number; cached?: boolean } = {}) => {
  const key = `plugins:${serverId}`
  if (!cached) {
    const { data } = await apiClient.get(`/api/plugins/server/${serverId}`)
    return data?.data || []
  }
  const data = await cachedGet<{ data: any[] }>(`/api/plugins/server/${serverId}`, { key, ttlMs })
  // 兼容 data.data 包装
  // 当 cachedGet 命中缓存时，data 可能已经是 {data:[]} 或者纯数组（旧缓存），都做兼容
  // @ts-ignore
  return (data?.data ?? data) || []
}

export const fetchServerMods = async (serverId: number, { ttlMs = 60_000, cached = true }: { ttlMs?: number; cached?: boolean } = {}) => {
  const key = `mods:${serverId}`
  if (!cached) {
    const { data } = await apiClient.get(`/api/mods/server/${serverId}`)
    return data?.data || []
  }
  const data = await cachedGet<{ data: any[] }>(`/api/mods/server/${serverId}`, { key, ttlMs })
  // @ts-ignore
  return (data?.data ?? data) || []
}

export const hasModrinthSlug = (mods: any[], slug: string) => {
  const target = (slug || '').toLowerCase()
  return !!mods.find(m => {
    const meta = m?.meta || {}
    const s = String(meta.slug || meta.id || meta.modrinth_project_id || '')
    return !!m?.enabled && s.toLowerCase() === target
  })
}

// 针对配置页右侧表单的数据缓存/失效
export const fetchPluginConfigCached = async (pluginKey: string, serverId: number, ttlMs = 30_000) => {
  const key = `cfg:${pluginKey}:${serverId}`
  const data = await cachedGet<any>(`/api/configs/${pluginKey}/${serverId}`, { key, ttlMs })
  return data
}

export const invalidateServers = () => invalidateCache('servers')
export const invalidateServerPlugins = (serverId: number) => invalidateCache(`plugins:${serverId}`)
export const invalidateServerMods = (serverId: number) => invalidateCache(`mods:${serverId}`)
export const invalidatePluginConfig = (pluginKey: string, serverId: number) => invalidateCache(`cfg:${pluginKey}:${serverId}`)
