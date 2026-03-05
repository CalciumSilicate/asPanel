import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import type { Ref } from 'vue'
import apiClient, { isRequestCanceled } from '@/api'
import { ElMessage } from 'element-plus'
import { clampPercent } from '@/utils/metrics'

export interface SystemStatus {
  cpu_percent: number
  memory_percent: number
  memory_used: number
  memory_total: number
  disk_percent: number
  disk_used_gb: number
  disk_total_gb: number
}

export interface ServerStats {
  total_servers: number
  running_servers: number
}

export interface ServerUsage {
  id: number
  name: string
  cpu_percent: number
  memory_mb: number
}

interface ServerItem {
  id: number
  status: string
}

const POLL_INTERVAL = 5000

export function useDashboard(activeGroupIds: Ref<number[]>) {
  const stats = ref<ServerStats>({ total_servers: 0, running_servers: 0 })
  const systemStatus = ref<SystemStatus>({
    cpu_percent: 0,
    memory_percent: 0,
    memory_used: 0,
    memory_total: 0,
    disk_percent: 0,
    disk_used_gb: 0,
    disk_total_gb: 0,
  })
  const runningServersUsage = ref<ServerUsage[]>([])

  const serverPercent = computed(() => {
    const { total_servers: total, running_servers: running } = stats.value
    if (!total) return 0
    return Math.min(100, Math.max(0, Math.round((running / total) * 100)))
  })

  const hostMemoryTotalMb = computed(() => (systemStatus.value.memory_total || 0) * 1024)

  let timer: ReturnType<typeof setInterval> | null = null

  const fetchData = async () => {
    try {
      const [serversRes, systemRes, usageRes] = await Promise.all([
        apiClient.get('/api/servers'),
        apiClient.get('/api/system/status'),
        apiClient.get('/api/servers/resource-usage'),
      ])
      const servers: ServerItem[] = Array.isArray(serversRes.data) ? serversRes.data : []
      const running = servers.filter(s => s.status === 'running').length
      stats.value = { total_servers: servers.length, running_servers: running }

      const s = systemRes.data || {}
      systemStatus.value = {
        cpu_percent:    clampPercent(s.cpu_percent),
        memory_percent: clampPercent(s.memory_percent),
        memory_used:    Number(s.memory_used)    || 0,
        memory_total:   Number(s.memory_total)   || 0,
        disk_percent:   clampPercent(s.disk_percent),
        disk_used_gb:   Number(s.disk_used_gb)   || 0,
        disk_total_gb:  Number(s.disk_total_gb)  || 0,
      }

      const runningIds = new Set(servers.filter(sv => sv.status === 'running').map(sv => sv.id))
      const usageList: ServerUsage[] = Array.isArray(usageRes.data) ? usageRes.data : []
      runningServersUsage.value = usageList.filter(u => runningIds.has(u?.id))
    } catch (err) {
      if (isRequestCanceled(err)) return
      ElMessage.error('获取仪表盘数据失败，请检查后端服务。')
      console.error(err)
      stopPolling()
    }
  }

  const startPolling = () => {
    if (timer) return
    timer = setInterval(fetchData, POLL_INTERVAL)
  }

  const stopPolling = () => {
    if (timer) { clearInterval(timer); timer = null }
  }

  const onVisibilityChange = () => {
    if (document.hidden) {
      stopPolling()
    } else {
      fetchData()
      startPolling()
    }
  }

  onMounted(() => {
    fetchData()
    startPolling()
    document.addEventListener('visibilitychange', onVisibilityChange)
  })

  onUnmounted(() => {
    stopPolling()
    document.removeEventListener('visibilitychange', onVisibilityChange)
  })

  watch(activeGroupIds, () => fetchData(), { deep: true })

  return { stats, systemStatus, runningServersUsage, serverPercent, hostMemoryTotalMb }
}
