// 全局系统设置（从后端 /api/settings 获取）
import { reactive } from 'vue'
import apiClient from '@/api'

export const settings = reactive({
  python_executable: '.venv/bin/python',
  java_command: 'java',
  timezone: 'Asia/Shanghai',
})

export const loadSettings = async () => {
  try {
    const { data } = await apiClient.get('/api/settings')
    Object.assign(settings, data || {})
  } catch (e) {
    // 忽略，维持默认
  }
}

export const updateSettings = async (patch) => {
  const { data } = await apiClient.patch('/api/settings', patch)
  Object.assign(settings, data || {})
  return data
}

// 常用时区选项（可按需扩充）
export const COMMON_TIMEZONES = [
  { label: 'UTC+8 北京时间', value: 'Asia/Shanghai' },
  { label: 'UTC+9 东京', value: 'Asia/Tokyo' },
  { label: 'UTC+1 柏林/巴黎', value: 'Europe/Berlin' },
  { label: 'UTC 伦敦', value: 'UTC' },
  { label: 'UTC-5 纽约', value: 'America/New_York' },
]

