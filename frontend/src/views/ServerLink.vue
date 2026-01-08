<template>
  <div class="sl-page">
    <div class="left-wrap" :class="{ 'is-collapsed': asideCollapsed, 'is-collapsing': asideCollapsing }">
      <!-- 左侧：服务器组列表（仅平台管理员显示） -->
      <div class="table-card left-panel" v-if="isPlatformAdmin">
        <el-card shadow="never">
          <template #header>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="text-base font-medium">Server Link</span>
              </div>
              <div class="flex items-center gap-2">
                <el-button type="primary" size="small" @click="handleCreateGroup">新建组</el-button>
              </div>
            </div>
          </template>

          <el-input v-model="groupQuery" placeholder="搜索服务器组" clearable class="mb-2">
            <template #prefix><el-icon><Search/></el-icon></template>
          </el-input>

          <el-table :data="filteredGroups" size="small" stripe height="100%" @row-click="selectGroup">
            <el-table-column label="组名" min-width="180">
              <template #default="{ row }">
                <div class="flex items-center justify-between w-full">
                  <div class="server-cell">
                    <div class="name">{{ row.name }}</div>
                    <div class="muted">ID: {{ row.id }}</div>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" align="center">
              <template #default="{ row }">
                <el-button size="small" type="danger" @click.stop="deleteGroup(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </div>

      <!-- 右侧：组详情与配置（仿 PrimeBackup 右侧卡片 + 表格布局） -->
      <div class="right-panel" :class="{ 'full-width': !isPlatformAdmin }">
        <!-- 非平台管理员：显示只读提示 -->
        <div v-if="!isPlatformAdmin" class="main-placeholder">
          <el-empty description="此页面仅对平台管理员开放"/>
        </div>
        <template v-else>
        <el-card shadow="never" class="mb-3">
          <template #header>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="text-base font-medium">{{ activeGroup ? activeGroup.name : '请选择服务器组' }}</span>
                <el-tag v-if="activeGroup" size="small" type="info">服务器数：{{ selectedServersCount }}</el-tag>
                <el-tag v-if="activeGroup" size="small" type="success">已连接群聊：{{ connectedChatsCount }}</el-tag>
              </div>
            </div>
          </template>

          <div v-if="!activeGroup" class="placeholder">请选择左侧“服务器组”，或点击右上角“新建组”。</div>
          <div v-else>
            <el-form label-position="top" :model="activeGroup" class="mb-3">
              <el-form-item label="组名" required>
                <el-input v-model="activeGroup.name" placeholder="请输入组名"/>
              </el-form-item>

              <el-form-item label="选择服务器（多选）" required>
                <el-select v-model="activeGroup.serverIds" multiple filterable placeholder="请选择服务器" style="width: 100%;" :loading="serversLoading">
                  <el-option
                    v-for="s in servers"
                    :key="s.id"
                    :label="s.name"
                    :value="s.id"
                    :disabled="(s.core_config?.server_type || s.core_config?.serverType) === 'velocity'"
                  />
                </el-select>
              </el-form-item>

              <el-form-item label="数据来源（统计图展示用）">
                <el-select v-model="activeGroup.dataSourceIds" multiple filterable placeholder="默认使用所有选中的服务器" style="width: 100%;">
                   <el-option
                    v-for="s in dataSourceOptions"
                    :key="s.id"
                    :label="s.name"
                    :value="s.id"
                  />
                </el-select>
                <div class="muted mt-1">若留空，则默认统计该组内所有服务器的数据。</div>
              </el-form-item>

              <el-form-item label="QQ群聊（群号）">
                <div class="chat-bindings">
                  <el-input
                    v-model="activeGroup.qqGroup"
                    placeholder="请输入QQ群号"
                    clearable
                    style="max-width: 360px;"
                    @input="onQQInput"
                    @blur="onQQBlur"
                  />
                  <div class="muted mt-1">留空表示不绑定QQ群</div>
                </div>
              </el-form-item>

              <!-- 预留：更多选项（后续扩展） -->
              <!-- <el-form-item label="其他选项"> ... </el-form-item> -->
            </el-form>
          </div>
        </el-card>

        <!-- 右侧下方可扩展区域：比如展示组内服务器详情、拓扑等。先留空。 -->
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import apiClient from '@/api'
import { asideCollapsed, asideCollapsing } from '@/store/ui'
import { isPlatformAdmin, activeGroupId } from '@/store/user'

// 服务器列表（来自 /api/servers）
const servers = ref([])
const serversLoading = ref(false)

// 组列表（后端对接）
const groups = ref([])
const groupQuery = ref('')
const activeGroup = ref(null)
const saving = ref(false)
let saveVersion = 0  // 用于跟踪保存请求的版本，避免竞态条件

const filteredGroups = computed(() => {
  const q = groupQuery.value.trim().toLowerCase()
  if (!q) return groups.value
  return groups.value.filter(g => g.name?.toLowerCase().includes(q) || String(g.id).includes(q))
})

const selectedServersCount = computed(() => activeGroup.value?.serverIds?.length || 0)
// 预留字段：后续可接入真实群聊绑定统计
const connectedChatsCount = computed(() => (activeGroup.value?.qqGroup ? 1 : 0))

const dataSourceOptions = computed(() => {
  if (!activeGroup.value || !activeGroup.value.serverIds) return []
  return servers.value.filter(s => activeGroup.value.serverIds.includes(s.id))
})

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
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '创建服务器组失败')
  }
}

const deleteGroup = (row) => {
  ElMessageBox.confirm(`确定删除服务器组 “${row.name}” 吗？`, '确认删除', { type: 'warning' })
    .then(async () => {
      try {
        await apiClient.delete(`/api/tools/server-link/groups/${row.id}`)
        const idx = groups.value.findIndex(g => g.id === row.id)
        if (idx >= 0) groups.value.splice(idx, 1)
        if (activeGroup.value?.id === row.id) activeGroup.value = null
        ElMessage.success('已删除')
      } catch (e) {
        ElMessage.error(e?.response?.data?.detail || '删除失败')
      }
    })
    .catch(() => {})
}

const selectGroup = (row) => { activeGroup.value = row }

const ensureActiveGroup = () => {
  if (!activeGroup.value) return false
  if (!activeGroup.value.serverIds) activeGroup.value.serverIds = []
  if (!activeGroup.value.dataSourceIds) activeGroup.value.dataSourceIds = []
  if (!activeGroup.value.chatBindings) activeGroup.value.chatBindings = []
  if (activeGroup.value.qqGroup === undefined || activeGroup.value.qqGroup === null) {
    activeGroup.value.qqGroup = activeGroup.value.chatBindings?.[0] || ''
  }
  return true
}

const onQQInput = (val) => {
  if (!ensureActiveGroup()) return
  const digits = String(val ?? '').replace(/\D/g, '').slice(0, 12)
  activeGroup.value.qqGroup = digits
  activeGroup.value.chatBindings = digits ? [digits] : []
}

const onQQBlur = () => {
  if (!ensureActiveGroup()) return
  const value = String(activeGroup.value.qqGroup || '').trim()
  if (value && !/^\d{5,12}$/.test(value)) {
    ElMessage.warning('请输入有效的QQ群号（5-12位数字）')
    activeGroup.value.qqGroup = ''
    activeGroup.value.chatBindings = []
  }
}

const saveGroup = async () => {
  if (!activeGroup.value) return
  if (!activeGroup.value.name?.trim()) return // 避免每次输入时弹提示，交由失焦/点击保存时提示
  if (!activeGroup.value.serverIds || activeGroup.value.serverIds.length === 0) return
  
  const currentVersion = ++saveVersion  // 递增版本号
  const currentGroupId = activeGroup.value.id
  
  try {
    saving.value = true
    const payload = toAPIPayload(activeGroup.value)
    const { data } = await apiClient.put(`/api/tools/server-link/groups/${currentGroupId}`, payload)
    
    // 只有当这是最新的保存请求，且用户仍在编辑同一个组时，才更新状态
    if (currentVersion === saveVersion && activeGroup.value?.id === currentGroupId) {
      const updated = toUIGroup(data)
      const idx = groups.value.findIndex(g => g.id === updated.id)
      if (idx >= 0) groups.value[idx] = updated
      // 不再覆盖 activeGroup，避免用户正在编辑的内容被旧请求覆盖
    }
  } catch (e) {
    // 静默失败，避免在频繁自动保存期间干扰用户
  } finally {
    saving.value = false
  }
}

// 500ms 防抖自动保存
let saveTimer = null
const scheduleAutoSave = () => {
  if (!activeGroup.value) return
  clearTimeout(saveTimer)
  saveTimer = setTimeout(() => {
    saveGroup()
  }, 500)
}

watch(() => activeGroup.value && activeGroup.value.name, scheduleAutoSave)
watch(() => activeGroup.value && JSON.stringify(activeGroup.value.serverIds || []), scheduleAutoSave)
watch(() => activeGroup.value && JSON.stringify(activeGroup.value.dataSourceIds || []), scheduleAutoSave)
watch(() => activeGroup.value && activeGroup.value.qqGroup, scheduleAutoSave)

const loadServers = async () => {
  serversLoading.value = true
  try {
    const { data } = await apiClient.get('/api/servers')
    servers.value = data || []
  } catch (e) {
    ElMessage.error('加载服务器列表失败')
    servers.value = []
  } finally {
    serversLoading.value = false
  }
}

onMounted(() => {
  loadServers()
  loadGroups()
})

// 映射工具：API <-> UI
const toUIGroup = (g) => ({
  id: g.id,
  name: g.name,
  serverIds: g.server_ids || [],
  dataSourceIds: g.data_source_ids || [],
  chatBindings: g.chat_bindings || [],
  qqGroup: (g.chat_bindings && g.chat_bindings[0]) || '',
  created_at: g.created_at
})
const toAPIPayload = (g) => ({
  name: g.name,
  server_ids: g.serverIds || [],
  data_source_ids: g.dataSourceIds || [],
  chat_bindings: g.qqGroup ? [g.qqGroup] : []
})

const loadGroups = async () => {
  try {
    const { data } = await apiClient.get('/api/tools/server-link/groups')
    groups.value = Array.isArray(data) ? data.map(toUIGroup) : []
    if (!activeGroup.value && groups.value.length > 0) activeGroup.value = groups.value[0]
  } catch (e) {
    groups.value = []
  }
}
</script>

<style scoped>
.sl-page { }
.left-wrap { display: flex; gap: 16px; align-items: stretch; height: calc(100vh - var(--el-header-height) - 48px); overflow: hidden; min-height: 0; }
.left-panel { width: 320px; flex-shrink: 0; align-self: stretch; height: 100%; min-height: 0; }
.left-panel { transition: width 0.32s cubic-bezier(.34,1.56,.64,1); will-change: width; overflow: hidden; }
.is-collapsed .left-panel, .is-collapsing .left-panel { width: 0 !important; }
.is-collapsing .left-panel :deep(.el-card__body), .is-collapsing .left-panel :deep(.el-card__header) { display: none !important; }
.left-panel :deep(.el-card) { height: 100%; display: flex; flex-direction: column; }
.left-panel :deep(.el-card__body) { padding: 8px; flex: 1 1 auto; min-height: 0; display: flex; flex-direction: column; }
.left-panel :deep(.el-input), .left-panel :deep(.el-input__wrapper) { width: 100%; }
.left-panel :deep(.el-table__inner-wrapper) { width: 100%; }
.left-panel :deep(.el-table) { flex: 1 1 auto; min-height: 0; }
.right-panel { flex: 1 1 auto; min-height: 0; overflow: auto; }
.right-panel.full-width { width: 100%; }
.right-panel :deep(.el-descriptions) { border-radius: 8px; overflow: hidden; }
.right-panel { scrollbar-gutter: stable; scrollbar-width: thin; }
.main-placeholder { display: flex; align-items: center; justify-content: center; height: 100%; }
/* 工具类 */
.mb-2 { margin-bottom: 8px; }
.mb-3 { margin-bottom: 12px; }
.mt-3 { margin-top: 12px; }
.flex { display: flex; }
.items-center { align-items: center; }
.justify-between { justify-content: space-between; }
.justify-end { justify-content: flex-end; }
.gap-2 { gap: 8px; }
.w-full { width: 100%; }
.text-base { font-size: 14px; }
.font-medium { font-weight: 600; }
.muted { color: #909399; font-size: 12px; }
.server-cell .name { line-height: 18px; }
</style>
