import apiClient from '@/api'

export const bindApi = {
  requestBind: (playerName: string) =>
    apiClient.post('/api/users/me/bind-request', { player_name: playerName }),
  getPending: () =>
    apiClient.get('/api/users/me/bind-pending'),
  cancelBind: () =>
    apiClient.delete('/api/users/me/bind-request'),
}
