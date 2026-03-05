import apiClient from './index'

export interface ServerItem {
  id: number
  name: string
  status: string
}

export const serversApi = {
  list: () => apiClient.get<ServerItem[]>('/api/servers'),
  start: (serverId: number | string) => apiClient.post(`/api/servers/start?server_id=${serverId}`),
  stop: (serverId: number | string) => apiClient.post(`/api/servers/stop?server_id=${serverId}`),
  restart: (serverId: number | string) => apiClient.post(`/api/servers/restart?server_id=${serverId}`),
  getLogs: (serverId: number | string) => apiClient.get<string[]>(`/api/servers/${serverId}/logs`),
}
