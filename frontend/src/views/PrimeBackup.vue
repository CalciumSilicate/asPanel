<template>
  <div class="pb-page">
    <div class="left-wrap" :class="{ 'is-collapsed': asideCollapsed, 'is-collapsing': asideCollapsing }">
      <!-- 左侧：服务器列表 -->
      <div class="table-card left-panel">
        <el-card shadow="never">
          <template #header>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="text-base font-medium">Prime Backup</span>
              </div>
              <div class="flex items-center gap-2">
                <el-tag type="success">总占用：{{ formatBytes(usageTotal) }}</el-tag>
              </div>
            </div>
          </template>

          <el-input v-model="serverQuery" placeholder="搜索服务器" clearable class="mb-2">
            <template #prefix><el-icon><Search/></el-icon></template>
          </el-input>

          <el-table :data="filteredServers" size="small" stripe v-loading="loadingServers" @row-click="selectServer">
            <el-table-column label="服务器" min-width="180">
              <template #default="{ row }">
                <div class="flex items-center justify-between w-full">
                  <div class="server-cell">
                    <div class="name">{{ row.name }}</div>
                    <div class="muted">ID: {{ row.id }}</div>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="120" align="center">
              <template #default="{ row }">
                <template v-if="isPBInstalled(row)">
                  <el-button v-if="isOutdated(row)" size="small" type="warning" :loading="updatingServerId === row.id" @click.stop="updatePB(row)">更新</el-button>
                  <el-tag v-else type="success" size="small">已安装</el-tag>
                </template>
                <template v-else>
                  <el-button
                    size="small"
                    type="success"
                    :icon="Download"
                    :loading="installingServerId === row.id"
                    @click.stop="installPB(row)"
                  >安装</el-button>
                </template>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </div>

      <!-- 右侧：功能区 -->
      <div class="right-panel">
        <el-card shadow="never" class="mb-3">
          <template #header>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="text-base font-medium">{{ activeServer ? activeServer.name : '请选择服务器' }}</span>
                <el-tag v-if="activeServer" size="small" :type="getPBStatus(activeServer).type">{{ getPBStatus(activeServer).text }}</el-tag>
                <el-tag v-if="activeServer" size="small" type="info">占用：{{ formatBytes(activeUsage) }}</el-tag>
              </div>
              <div class="flex items-center gap-2"></div>
            </div>
          </template>

          <div v-if="!activeServer" class="placeholder">请选择左侧服务器以管理其 Prime Backup 备份。</div>
          <div v-else>
            <el-descriptions :column="3" border size="small" class="mb-3" v-if="overview">
              <el-descriptions-item label="存储根">{{ overview.storage_root || '-' }}</el-descriptions-item>
              <el-descriptions-item label="备份数量">{{ overview.backup_amount ?? '-' }}</el-descriptions-item>
              <el-descriptions-item label="数据库版本">{{ overview.db_version ?? '-' }}</el-descriptions-item>
            </el-descriptions>
          </div>
        </el-card>

        <!-- 备份列表（独立区域，参考 ServerPluginManager 布局） -->
        <div class="table-card">
          <el-table :data="pagedBackups" size="small" stripe v-loading="loadingBackups" empty-text="暂无备份">
            <el-table-column prop="id" label="ID" width="80"/>
            <el-table-column prop="date" label="创建时间" min-width="180">
              <template #default="{ row }">{{ formatPBDate(row.date) }}</template>
            </el-table-column>
            <el-table-column label="压缩大小" width="140" align="center">
              <template #default="{ row }">{{ formatBytes(row.stored_size || 0) }}</template>
            </el-table-column>
            <el-table-column label="原始大小" width="140" align="center">
              <template #default="{ row }">{{ formatBytes(row.raw_size || 0) }}</template>
            </el-table-column>
            <el-table-column prop="creator" label="创建者" min-width="160"/>
            <el-table-column prop="comment" label="备注" min-width="160"/>
            <el-table-column label="操作" width="220" align="center">
              <template #default="{ row }">
                <el-button-group>
                  <el-button size="small" :icon="Download" @click="doExport(row)">下载</el-button>
                  <el-button size="small" type="primary" @click="openRestoreDialog(row)">恢复到服务器</el-button>
                </el-button-group>
              </template>
            </el-table-column>
          </el-table>

        </div>
        <div class="mt-3 flex items-center justify-end">
          <el-pagination
            background
            layout="prev, pager, next, sizes, total"
            :page-sizes="[10, 20, 50, 100]"
            :page-size="pageSize"
            :current-page="page"
            :total="backups.length"
            @current-change="p => page = p"
            @size-change="s => { pageSize = s; page = 1 }"
          />
        </div>
      </div>
    </div>

    <!-- 恢复到服务器（仅选择服务器，运行中服务器不可选） -->
    <el-dialog v-model="restoreDialog.visible" title="恢复到服务器" width="520px" @open="fetchAllServers">
      <el-form label-position="top">
        <el-form-item label="选择目标服务器" required>
          <el-select v-model="restoreDialog.targetServerId" filterable placeholder="请选择服务器" :loading="allServersLoading" style="width: 100%;">
            <el-option
              v-for="s in allServers"
              :key="s.id"
              :label="formatServerOptionLabel(s)"
              :value="s.id"
              :disabled="s.status === 'running'"
            >
              <div class="option-row">
                <span>{{ formatServerOptionLabel(s) }}</span>
                <el-tag v-if="s.status === 'running'" size="small" type="success">运行中</el-tag>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="restoreDialog.visible=false">取消</el-button>
        <el-tooltip :disabled="!isActiveRunning" content="服务器运行中，不允许使用" placement="top">
          <span>
            <el-button type="primary" :disabled="isActiveRunning || !restoreDialog.targetServerId" @click="confirmRestore">确认恢复</el-button>
          </span>
        </el-tooltip>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import {ref, computed, onMounted} from 'vue'
import {ElMessage, ElMessageBox, ElNotification} from 'element-plus'
import { Search, Refresh, Download } from '@element-plus/icons-vue'
import apiClient from '@/api'
import { asideCollapsed, asideCollapsing } from '@/store/ui'
import { settings } from '@/store/settings'
import { settings } from '@/store/settings'

const PB_PLUGIN_META_ID = 'prime_backup'

// 服务器列表与插件状态
const servers = ref([])
const loadingServers = ref(false)
const serverQuery = ref('')
const serverPlugins = ref(new Map()) // server_id -> plugins[]
const usageMap = ref(new Map()) // server_id -> bytes
const installingServerId = ref(null)

const activeServer = ref(null)
const overview = ref(null)
const backups = ref([])
const loadingBackups = ref(false)

// Pagination for backups
const page = ref(1)
const pageSize = ref(20)
const pagedBackups = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return backups.value.slice(start, start + pageSize.value)
})

const formatPBDate = (d) => {
  try { return new Date(d).toLocaleString('zh-CN', { timeZone: settings.timezone || 'Asia/Shanghai' }) } catch { return d || '' }
}

// 总占用（来自后端总量接口，失败时回退到聚合）
const usageTotal = ref(0)
const activeUsage = ref(0)

// 恢复对话框
const restoreDialog = ref({ visible: false, backupId: null, targetServerId: null, loading: false })
const allServers = ref([])
const allServersLoading = ref(false)

// 在线最新版本（用于检测是否可更新）
const latestPBVersion = ref(null)
const updatingServerId = ref(null)

// 搜索过滤
const filteredServers = computed(() => {
  if (!serverQuery.value.trim()) return servers.value
  const q = serverQuery.value.toLowerCase()
  return servers.value.filter(s => s.name?.toLowerCase().includes(q) || String(s.id).includes(q))
})

// 工具函数：字节格式化
const formatBytes = (bytes) => {
  const b = Number(bytes || 0)
  if (!b) return '0 B'
  const units = ['B','KB','MB','GB','TB']
  const i = Math.floor(Math.log(b) / Math.log(1024))
  return (b / Math.pow(1024, i)).toFixed(2) + ' ' + units[i]
}

const isPBInstalled = (server) => {
  const list = serverPlugins.value.get(server.id) || []
  return !!list.find(p => p?.meta?.id === PB_PLUGIN_META_ID)
}

const getPBStatus = (server) => {
  if (!serverPlugins.value.size) return { text: '加载中...', type: 'info' }
  const list = serverPlugins.value.get(server.id) || []
  const found = list.find(p => p?.meta?.id === PB_PLUGIN_META_ID)
  return found ? { text: `已安装${found?.meta?.version? ' ('+found.meta.version+')':''}`, type: 'success' } : { text: '未安装', type: 'warning' }
}

const loadServers = async () => {
  loadingServers.value = true
  try {
    const { data } = await apiClient.get('/api/servers')
    servers.value = data
  } catch (e) {
    ElMessage.error('加载服务器列表失败')
  } finally {
    loadingServers.value = false
  }
  await Promise.all([fetchAllServerPlugins(), fetchAllUsage()])
  await fetchUsageTotal()
}

const fetchAllServerPlugins = async () => {
  serverPlugins.value.clear()
  const tasks = servers.value.map(async (s) => {
    try {
      const { data } = await apiClient.get(`/api/plugins/server/${s.id}`)
      serverPlugins.value.set(s.id, data.data || [])
    } catch (e) {
      serverPlugins.value.set(s.id, [])
    }
  })
  await Promise.allSettled(tasks)
}

// 获取远端最新 prime_backup 版本（用于显示“更新”按钮）
const fetchLatestPBVersion = async () => {
  try {
    const { data } = await apiClient.get('/api/plugins/mcdr/versions')
    latestPBVersion.value = data?.plugins?.prime_backup?.release?.latest_version || null
  } catch (e) {
    latestPBVersion.value = null
  }
}

const fetchAllUsage = async () => {
  usageMap.value = new Map()
  const tasks = servers.value.map(async (s) => {
    try {
      const { data } = await apiClient.get(`/api/tools/pb/${s.id}/usage`)
      usageMap.value.set(s.id, Number(data?.bytes || 0))
    } catch (e) {
      usageMap.value.set(s.id, 0)
    }
  })
  await Promise.allSettled(tasks)
}

const fetchUsageTotal = async () => {
  try {
    const { data } = await apiClient.get('/api/tools/pb/usage/total')
    usageTotal.value = Number(data?.bytes || 0)
  } catch (e) {
    let s = 0
    for (const v of usageMap.value.values()) s += Number(v || 0)
    usageTotal.value = s
  }
}

const openServer = (row) => {
  activeServer.value = row
  doOverview()
  doList()
  fetchActiveUsage()
}

const selectServer = (row) => openServer(row)

const fetchActiveUsage = async () => {
  if (!activeServer.value) { activeUsage.value = 0; return }
  try {
    const { data } = await apiClient.get(`/api/tools/pb/${activeServer.value.id}/usage`)
    activeUsage.value = Number(data?.bytes || 0)
  } catch (e) {
    activeUsage.value = 0
  }
}

// 恢复到服务器对话框逻辑
const openRestoreDialog = (row) => {
  restoreDialog.value.visible = true
  restoreDialog.value.backupId = row.id
  restoreDialog.value.targetServerId = activeServer.value?.id || null
}

const fetchAllServers = async () => {
  allServersLoading.value = true
  try {
    const { data } = await apiClient.get('/api/servers')
    allServers.value = data
  } catch (e) {
    ElMessage.error('获取服务器列表失败')
  } finally {
    allServersLoading.value = false
  }
}

const formatServerOptionLabel = (s) => s?.game_version ? `${s.name} (v${s.game_version})` : s?.name

const confirmRestore = async () => {
  if (!activeServer.value) return
  if (!restoreDialog.value.targetServerId) return ElMessage.warning('请选择目标服务器')
  try {
    await apiClient.post(`/api/tools/pb/${activeServer.value.id}/restore`, { id: restoreDialog.value.backupId, target_server_id: restoreDialog.value.targetServerId })
    ElMessage.success('恢复完成')
    restoreDialog.value.visible = false
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '恢复失败')
  }
}

// 自动发现 DB 中 prime_backup 的记录
let cachedPBDBId = null
const getPBDBId = async () => {
  if (cachedPBDBId) return cachedPBDBId
  const { data } = await apiClient.get('/api/plugins/db')
  const rec = (data || []).find(r => r?.meta?.id === PB_PLUGIN_META_ID)
  if (!rec) throw new Error('数据库中未找到 prime_backup 插件，请先上传或同步到插件库')
  cachedPBDBId = rec.id
  return cachedPBDBId
}

const installPB = async (server) => {
  try {
    installingServerId.value = server.id
    await apiClient.post(`/api/plugins/server/${server.id}/install/from-online`, null, { params: { plugin_id: 'prime_backup', tag_name: 'latest' } })
    ElNotification({ title: '安装成功', message: `已为 ${server.name} 安装 prime_backup`, type: 'success' })
    // 安装后刷新所有服务器的插件状态
    await fetchAllServerPlugins()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '安装失败')
  } finally {
    installingServerId.value = null
  }
}

const isOutdated = (server) => {
  try {
    if (!latestPBVersion.value) return false
    const list = serverPlugins.value.get(server.id) || []
    const installed = list.find(p => p?.meta?.id === PB_PLUGIN_META_ID)
    if (!installed?.meta?.version) return false
    return installed.meta.version !== latestPBVersion.value
  } catch (e) { return false }
}

const updatePB = async (server) => {
  try {
    updatingServerId.value = server.id
    await apiClient.post(`/api/plugins/server/${server.id}/install/from-online`, null, { params: { plugin_id: 'prime_backup', tag_name: 'latest' } })
    ElNotification({ title: '更新成功', message: `已为 ${server.name} 更新 prime_backup 至最新版本`, type: 'success' })
    // 更新后刷新所有服务器的插件状态
    await fetchAllServerPlugins()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '更新失败')
  } finally {
    updatingServerId.value = null
  }
}

// 下载导出
const doExport = async (row) => {
  try {
    const res = await apiClient.post(`/api/tools/pb/${activeServer.value.id}/export`, { id: row.id }, { responseType: 'blob' })
    if (res?.data) {
      const blob = new Blob([res.data])
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `pb_${activeServer.value.id}_${row.id}.tar`
      a.click()
      URL.revokeObjectURL(url)
    } else {
      ElMessage.success('导出任务已发起')
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '下载失败')
  }
}

// 刷新当前服务器数据
const refreshActive = async () => {
  if (!activeServer.value) return
  await Promise.all([doOverview(), doList()])
}

const doOverview = async () => {
  if (!activeServer.value) return
  try {
    const { data } = await apiClient.get(`/api/tools/pb/${activeServer.value.id}/overview`)
    overview.value = data
  } catch (e) {
    overview.value = null
  }
}

const doList = async () => {
  if (!activeServer.value) return
  loadingBackups.value = true
  try {
    const { data } = await apiClient.get(`/api/tools/pb/${activeServer.value.id}/list`)
    backups.value = Array.isArray(data) ? data : (data?.items || [])
  } catch (e) {
    backups.value = []
  } finally {
    loadingBackups.value = false
  }
}

const isActiveRunning = computed(() => {
  if (!activeServer.value) return false
  const s = servers.value.find(x => x.id === activeServer.value.id)
  return s?.status === 'running'
})








onMounted(() => {
  loadServers()
  fetchLatestPBVersion()
})
</script>

<style scoped>
.pb-page { }
.left-wrap { display: flex; gap: 16px; align-items: stretch; height: calc(100vh - var(--el-header-height) - 48px); overflow: hidden; min-height: 0; }
.left-panel { width: 320px; flex-shrink: 0; align-self: flex-start; }
.left-panel { transition: width 0.32s cubic-bezier(.34,1.56,.64,1); will-change: width; overflow: hidden; }
.is-collapsed .left-panel, .is-collapsing .left-panel { width: 0 !important; }
.is-collapsing .left-panel :deep(.el-card__body), .is-collapsing .left-panel :deep(.el-card__header) { display: none !important; }
.left-panel :deep(.el-card) { display: block; }
.left-panel :deep(.el-card__body) { padding: 8px; }
.left-panel :deep(.el-input), .left-panel :deep(.el-input__wrapper) { width: 100%; }
.left-panel :deep(.el-table__inner-wrapper) { width: 100%; }
.right-panel { flex: 1 1 auto; min-height: 0; overflow: auto; }
.right-panel :deep(.el-descriptions) { border-radius: 8px; overflow: hidden; }
/* 隐藏右侧滚动条但保留滚动 */
.right-panel::-webkit-scrollbar { width: 0; height: 0; }
.right-panel { scrollbar-width: none; -ms-overflow-style: none; }
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
.pre-like { white-space: pre-wrap; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
</style>

