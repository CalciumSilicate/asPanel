import { reactive } from 'vue'
import apiClient from '@/api'

export interface SettingsState {
  python_executable: string
  java_command: string
  timezone: string
  stats_ignore_server: number[]
}

export const settings = reactive<SettingsState>({
  python_executable: '.venv/bin/python',
  java_command: 'java',
  timezone: 'Asia/Shanghai',
  stats_ignore_server: [],
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

