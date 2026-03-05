import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import apiClient from '@/api'
import { useUserStore } from '@/store/user'
import { storeToRefs } from 'pinia'

export interface ServerLinkGroup {
  id: number
  name: string
  serverIds: number[]
  dataSourceIds: number[]
  chatBindings: string[]
  qqGroup: string
  created_at?: string
  server_ids: number[]
}

export interface ServerItem {
  id: number
  name: string
  core_config?: { server_type?: string; serverType?: string }
}

const toUIGroup = (g: Record<string, unknown>): ServerLinkGroup => ({
  id: g.id as number,
  name: g.name as string,
  serverIds: (g.server_ids as number[]) || [],
  dataSourceIds: (g.data_source_ids as number[]) || [],
  chatBindings: (g.chat_bindings as string[]) || [],
  qqGroup: ((g.chat_bindings as string[]) && (g.chat_bindings as string[])[0]) || '',
  created_at: g.created_at as string | undefined,
  server_ids: (g.server_ids as number[]) || [],
})

const toAPIPayload = (g: ServerLinkGroup) => ({
  name: g.name,
  server_ids: g.serverIds || [],
  data_source_ids: g.dataSourceIds || [],
  chat_bindings: g.qqGroup ? [g.qqGroup] : [],
})

export function useServerLink() {
  const userStore = useUserStore()
  const { isPlatformAdmin } = storeToRefs(userStore)

  const groups = ref<ServerLinkGroup[]>([])
  const activeGroup = ref<ServerLinkGroup | null>(null)
  const servers = ref<ServerItem[]>([])
  const serversLoading = ref(false)
  const saving = ref(false)
  let saveVersion = 0
  let saveTimer: ReturnType<typeof setTimeout> | null = null
  let pendingGroupToSave: ServerLinkGroup | null = null

  // ── Computed ────────────────────────────────────────────────

  const selectedServersCount = computed(() => activeGroup.value?.serverIds?.length ?? 0)
  const connectedChatsCount = computed(() => (activeGroup.value?.qqGroup ? 1 : 0))

  const dataSourceOptions = computed(() => {
    if (!activeGroup.value?.serverIds) return []
    return servers.value.filter((s) => activeGroup.value!.serverIds.includes(s.id))
  })

  // ── Group CRUD ──────────────────────────────────────────────

  const selectGroup = (row: ServerLinkGroup) => {
    activeGroup.value = row
  }

  const handleCreateGroup = async () => {
    try {
      const id = Date.now()
      const name = `新建组-${id % 100000}`
      const payload = { name, server_ids: [], data_source_ids: [], chat_bindings: [] }
      const { data } = await apiClient.post('/api/tools/server-link/groups', payload)
      const created = toUIGroup(data)
      groups.value.unshift(created)
      activeGroup.value = created
      ElMessage.success('已创建服务器组')
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      ElMessage.error(err?.response?.data?.detail || '创建服务器组失败')
    }
  }

  const deleteGroup = (row: ServerLinkGroup) => {
    ElMessageBox.confirm(`确定删除服务器组 "${row.name}" 吗？`, '确认删除', { type: 'warning' })
      .then(async () => {
        try {
          await apiClient.delete(`/api/tools/server-link/groups/${row.id}`)
          const idx = groups.value.findIndex((g) => g.id === row.id)
          if (idx >= 0) groups.value.splice(idx, 1)
          if (activeGroup.value?.id === row.id) activeGroup.value = null
          ElMessage.success('已删除')
        } catch (e: unknown) {
          const err = e as { response?: { data?: { detail?: string } } }
          ElMessage.error(err?.response?.data?.detail || '删除失败')
        }
      })
      .catch(() => {})
  }

  // ── QQ input ────────────────────────────────────────────────

  const ensureActiveGroup = (): boolean => {
    if (!activeGroup.value) return false
    if (!activeGroup.value.serverIds) activeGroup.value.serverIds = []
    if (!activeGroup.value.dataSourceIds) activeGroup.value.dataSourceIds = []
    if (!activeGroup.value.chatBindings) activeGroup.value.chatBindings = []
    return true
  }

  const onQQInput = (val: string) => {
    if (!ensureActiveGroup()) return
    const digits = String(val ?? '').replace(/\D/g, '').slice(0, 12)
    activeGroup.value!.qqGroup = digits
    activeGroup.value!.chatBindings = digits ? [digits] : []
  }

  const onQQBlur = () => {
    if (!ensureActiveGroup()) return
    const value = String(activeGroup.value!.qqGroup || '').trim()
    if (value && !/^\d{5,12}$/.test(value)) {
      ElMessage.warning('请输入有效的QQ群号（5-12位数字）')
      activeGroup.value!.qqGroup = ''
      activeGroup.value!.chatBindings = []
    }
  }

  // ── Auto-save ───────────────────────────────────────────────

  const saveGroup = async (groupToSave = activeGroup.value) => {
    if (!groupToSave?.name?.trim()) return
    const currentVersion = ++saveVersion
    const currentGroupId = groupToSave.id
    try {
      saving.value = true
      const payload = toAPIPayload(groupToSave)
      const { data } = await apiClient.put(`/api/tools/server-link/groups/${currentGroupId}`, payload)
      if (currentVersion === saveVersion) {
        const updated = toUIGroup(data)
        const idx = groups.value.findIndex((g) => g.id === updated.id)
        if (idx >= 0) {
          groups.value[idx] = { ...groups.value[idx], ...updated }
        }
      }
    } catch {
      // silent fail during auto-save
    } finally {
      saving.value = false
    }
  }

  const scheduleAutoSave = () => {
    if (!activeGroup.value) return
    pendingGroupToSave = { ...activeGroup.value }
    if (saveTimer) clearTimeout(saveTimer)
    saveTimer = setTimeout(() => {
      if (pendingGroupToSave) {
        saveGroup(pendingGroupToSave)
        pendingGroupToSave = null
      }
    }, 500)
  }

  const flushPendingSave = () => {
    if (saveTimer) { clearTimeout(saveTimer); saveTimer = null }
    if (pendingGroupToSave) { saveGroup(pendingGroupToSave); pendingGroupToSave = null }
  }

  watch(() => activeGroup.value?.id, (newId, oldId) => {
    if (oldId && oldId !== newId) flushPendingSave()
  })

  watch(() => activeGroup.value?.name, scheduleAutoSave)
  watch(() => JSON.stringify(activeGroup.value?.serverIds || []), scheduleAutoSave)
  watch(() => JSON.stringify(activeGroup.value?.dataSourceIds || []), scheduleAutoSave)
  watch(() => activeGroup.value?.qqGroup, scheduleAutoSave)

  // ── API loaders ─────────────────────────────────────────────

  const loadServers = async () => {
    serversLoading.value = true
    try {
      const { data } = await apiClient.get('/api/servers')
      servers.value = data || []
    } catch {
      ElMessage.error('加载服务器列表失败')
      servers.value = []
    } finally {
      serversLoading.value = false
    }
  }

  const loadGroups = async () => {
    try {
      const { data } = await apiClient.get('/api/tools/server-link/groups')
      groups.value = Array.isArray(data) ? data.map(toUIGroup) : []
    } catch {
      groups.value = []
    }
  }

  onMounted(() => {
    loadServers()
    loadGroups()
  })

  onUnmounted(() => {
    flushPendingSave()
  })

  return {
    isPlatformAdmin,
    groups,
    activeGroup,
    servers,
    serversLoading,
    saving,
    selectedServersCount,
    connectedChatsCount,
    dataSourceOptions,
    selectGroup,
    handleCreateGroup,
    deleteGroup,
    onQQInput,
    onQQBlur,
    loadGroups,
  }
}
