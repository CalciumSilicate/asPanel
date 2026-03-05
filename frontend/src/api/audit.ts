// frontend/src/api/audit.ts
import apiClient from '@/api'

export interface AuditLogItem {
  id: number
  ts: string | null
  category: string
  action: string
  actor_id: number | null
  actor_name: string | null
  ip_address: string | null
  target_type: string | null
  target_id: string | null
  target_name: string | null
  detail: Record<string, unknown> | string | null
  result: string
  error_msg: string | null
}

export interface AuditLogsResponse {
  total: number
  page: number
  page_size: number
  items: AuditLogItem[]
}

export interface AuditLogsParams {
  category?: string
  action?: string
  actor_id?: number
  actor_name?: string
  target_type?: string
  target_id?: string
  target_name?: string
  result?: string
  start_ts?: string
  end_ts?: string
  page?: number
  page_size?: number
}

export interface CategoryOption {
  value: string
  label: string
}

export async function fetchAuditLogs(params: AuditLogsParams = {}): Promise<AuditLogsResponse> {
  const res = await apiClient.get('/api/audit/logs', { params })
  return res.data
}

export async function fetchAuditCategories(): Promise<CategoryOption[]> {
  const res = await apiClient.get('/api/audit/categories')
  return res.data
}
