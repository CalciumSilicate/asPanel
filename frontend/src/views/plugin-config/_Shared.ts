import apiClient from '@/api'

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

export const fetchServerPlugins = async (serverId: number) => {
  const { data } = await apiClient.get(`/api/plugins/server/${serverId}`)
  return data?.data || []
}

export const fetchServerMods = async (serverId: number) => {
  const { data } = await apiClient.get(`/api/mods/server/${serverId}`)
  return data?.data || []
}

export const hasModrinthSlug = (mods: any[], slug: string) => {
  const target = (slug || '').toLowerCase()
  return !!mods.find(m => {
    const meta = m?.meta || {}
    const s = String(meta.slug || meta.id || meta.modrinth_project_id || '')
    return !!m?.enabled && s.toLowerCase() === target
  })
}
