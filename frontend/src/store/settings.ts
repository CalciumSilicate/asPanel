import { reactive } from 'vue'
import apiClient from '@/api'

export interface SettingsState {
  python_executable: string
  java_command: string
  timezone: string
  stats_ignore_server: number[]
  // 新增网页可配置项
  token_expire_minutes: number
  allow_register: boolean
  register_require_qq: boolean
  default_user_role: string
  copy_limit_mbps: number
}

export const settings = reactive<SettingsState>({
  python_executable: '.venv/bin/python',
  java_command: 'java',
  timezone: 'Asia/Shanghai',
  stats_ignore_server: [],
  // 新增网页可配置项
  token_expire_minutes: 10080,
  allow_register: true,
  register_require_qq: true,
  default_user_role: 'USER',
  copy_limit_mbps: 1024.0,
})

export const loadSettings = async () => {
  try {
    const { data } = await apiClient.get('/api/settings')
    Object.assign(settings, data || {})
  } catch {
    // keep defaults
  }
}

export const updateSettings = async (patch: Partial<SettingsState>) => {
  const { data } = await apiClient.patch('/api/settings', patch)
  Object.assign(settings, data || {})
  return data
}

export const COMMON_TIMEZONES: Array<{ label: string; value: string }> = [
  { label: 'UTC+8 北京时间', value: 'Asia/Shanghai' },
  { label: 'UTC+9 东京', value: 'Asia/Tokyo' },
  { label: 'UTC+1 柏林/巴黎', value: 'Europe/Berlin' },
  { label: 'UTC 伦敦', value: 'UTC' },
  { label: 'UTC-5 纽约', value: 'America/New_York' },
]

export const USER_ROLES: Array<{ label: string; value: string }> = [
  { label: '访客 (GUEST)', value: 'GUEST' },
  { label: '普通用户 (USER)', value: 'USER' },
  { label: '管理员 (ADMIN)', value: 'ADMIN' },
]
