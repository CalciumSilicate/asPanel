<template>
  <div class="page">
    <el-card shadow="never">
      <template #header>
        <div class="header-bar">
          <div class="flex items-center header-title">
            <span class="text-base font-medium">玩家管理</span>
            <el-tag type="info" class="title-count">共 {{ filteredRows.length }} 个玩家</el-tag>
          </div>
          <div class="header-actions">
            <el-button-group>
              <el-button type="success" :icon="Refresh" @click="refreshPlayTime">刷新时长</el-button>
              <el-button type="warning" :icon="RefreshRight" :loading="busyNames" @click="refreshOfficialNames">刷新正版玩家名</el-button>
            </el-button-group>
            <el-button-group>
              <el-button type="primary" :icon="Plus" @click="openWhitelistDialog">添加玩家到白名单</el-button>
              <el-button type="danger" :icon="CircleClose" @click="openBanDialog">封禁玩家/IP</el-button>
            </el-button-group>
          </div>
        </div>
      </template>

      <div class="toolbar mb-2">
        <el-input v-model="query" placeholder="搜索玩家名 / UUID" clearable style="max-width: 300px;">
          <template #prefix><el-icon><Search/></el-icon></template>
        </el-input>
        <div class="scope-group">
          <el-radio-group v-model="scope" @change="onScopeChange">
            <el-radio-button label="all">所有玩家</el-radio-button>
            <el-radio-button label="official_only">仅正版玩家</el-radio-button>
            <el-radio-button label="include_cracked">包括盗版玩家</el-radio-button>
          </el-radio-group>
          <el-popover placement="bottom-start" trigger="click" width="260">
            <template #reference>
              <el-button class="btn-scope-like" type="primary">数据来源 ({{ selectedServers.length }})</el-button>
            </template>
            <el-checkbox-group v-model="selectedServers" @change="onServersFilterChange" class="server-checkboxes">
              <el-checkbox v-for="s in serverNames" :key="s" :label="s">{{ s }}</el-checkbox>
            </el-checkbox-group>
          </el-popover>
          <el-checkbox class="wl-only" v-model="whitelistOnly" @change="onWhitelistToggle">仅白名单玩家</el-checkbox>
        </div>
      </div>

      <div class="table-container">
        <el-table :data="pagedRows" size="small" stripe :height="'100%'">
          <el-table-column label="头像" width="80" align="center">
            <template #default="{ row }">
              <img class="avatar" :src="avatarUrl(row.uuid)" alt="avatar" />
            </template>
          </el-table-column>
          <el-table-column label="玩家" min-width="260">
            <template #default="{ row }">
              <div class="name-cell">
                <template v-if="canEditName(row) && editingId === row.id">
                  <el-input v-model="editName" size="small" @keyup.enter.native="submitEdit(row)" @blur="cancelEdit" />
                </template>
                <template v-else>
                  <div class="pname" :class="{ clickable: canEditName(row) }" @click="startEdit(row)">{{ row.player_name || '（未设置）' }}</div>
                </template>
                <div class="uuid" :class="{ clickable: canEditName(row) && !row.player_name }" @click="startEdit(row)">{{ row.uuid }}</div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="管理员 (OP)" min-width="220">
            <template #default="{ row }">
              <el-space wrap v-if="(opServersByUuid[row.uuid] || []).length > 0">
                <el-tag
                    v-for="s in (opServersByUuid[row.uuid] || [])"
                    :key="s"
                    type="warning"
                    effect="plain"
                    size="small"
                >
                  {{ s }}
                </el-tag>
              </el-space>
              <el-tag v-else type="info" effect="plain" size="small">否</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="服务器组" min-width="200">
            <template #default="{ row }">
              <el-space wrap v-if="(row.server_link_groups || []).length > 0">
                <el-tag
                    v-for="g in (row.server_link_groups || [])"
                    :key="g.id"
                    type="success"
                    effect="plain"
                    size="small"
                >
                  {{ g.name }}
                </el-tag>
              </el-space>
              <el-tag v-else type="info" effect="plain" size="small">无</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="游玩时长" width="200" align="center">
            <template #header>
              <span class="pt-sort-header" @click="togglePlaytimeSort">游玩时长<span v-if="playtimeSort==='desc'"> ↓</span><span v-else> —</span></span>
            </template>
            <template #default="{ row }">
              <span>{{ formatDuration(sumTicks(row)) }}</span>
            </template>
          </el-table-column>
        </el-table>

    </div>
    </el-card>

    <!-- 添加玩家到白名单 -->
    <el-dialog v-model="whitelistDialogVisible" title="添加玩家到白名单" width="560px" align-center>
      <el-form label-width="110px" class="pm-dialog-form">
        <el-form-item label="玩家名">
          <el-input v-model="whitelistForm.player_name" placeholder="请输入玩家名（支持未入库玩家）" clearable />
        </el-form-item>
        <el-form-item label="玩家类型">
          <el-radio-group v-model="whitelistForm.is_official">
            <el-radio-button :label="true">正版</el-radio-button>
            <el-radio-button :label="false">离线</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="服务器">
          <el-select v-model="whitelistForm.servers" multiple filterable placeholder="请选择服务器" style="width: 100%;">
            <el-option v-for="s in serverNames" :key="s" :label="s" :value="s" />
          </el-select>
          <div class="pm-form-hint">不包含 Velocity 服务器；默认勾选“数据来源”的服务器。</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="whitelistDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="whitelistSubmitting" @click="submitWhitelist">确认添加</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 封禁玩家 / IP -->
    <el-dialog v-model="banDialogVisible" title="封禁玩家 / IP" width="640px" align-center>
      <el-form label-width="110px" class="pm-dialog-form">
        <el-form-item label="封禁类型">
          <el-radio-group v-model="banForm.type">
            <el-radio-button label="player">玩家</el-radio-button>
            <el-radio-button label="ip">IP</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="玩家" v-if="banForm.type === 'player'">
          <el-select v-model="banForm.uuid" filterable placeholder="选择玩家（可搜索名字/UUID）" style="width: 100%;">
            <el-option
                v-for="p in playerOptions"
                :key="p.uuid"
                :label="p.label"
                :value="p.uuid"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="IP" v-else>
          <el-input v-model="banForm.ip" placeholder="例如：203.0.113.10 或 2001:db8::1" />
        </el-form-item>

        <el-form-item label="原因">
          <el-input v-model="banForm.reason" placeholder="可选，不填则使用默认原因" />
        </el-form-item>

        <el-form-item label="服务器">
          <el-select v-model="banForm.servers" multiple filterable placeholder="请选择服务器" style="width: 100%;">
            <el-option v-for="s in serverNames" :key="s" :label="s" :value="s" />
          </el-select>
          <div class="pm-form-hint">不包含 Velocity 服务器；默认勾选“数据来源”的服务器。</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="banDialogVisible = false">取消</el-button>
          <el-button type="danger" :loading="banSubmitting" @click="submitBan">确认封禁</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 外部分页，置于右下角 -->
	    <div class="pm-pagination">
	      <el-pagination
	          background
	          layout="prev, pager, next, sizes, total"
	          :page-sizes="[10, 20, 50, 100]"
	          :page-size="pageSize"
	          :current-page="page"
	          :total="filteredRows.length"
	          @current-change="onPageChange"
	          @size-change="onPageSizeChange"
	      />
	    </div>
	  </div>
  
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import api from '@/api'
import { ElMessage } from 'element-plus'
import { Search, Refresh, RefreshRight, Plus, CircleClose } from '@element-plus/icons-vue'

type Player = {
  id: number,
  uuid: string,
  player_name?: string | null,
  is_offline: boolean,
  play_time: Record<string, number>,
  server_link_groups?: { id: number, name: string }[]
}

const rows = ref<Player[]>([])
const servers = ref<any[]>([])
const serverNames = computed(() => servers.value
  .filter((s: any) => (s.core_config?.server_type || s.coreConfig?.server_type) !== 'velocity')
  .map((s: any) => (s.path?.split('/').pop()) || s.name)
)
const selectedServers = ref<string[]>([])
const query = ref('')
const scope = ref<'official_only'|'include_cracked'|'all'>('official_only')

// 白名单过滤
const whitelistUUIDs = ref<string[]>([])
const whitelistOnly = ref(false)
const whitelistSet = computed(() => new Set(whitelistUUIDs.value))

const busyTicks = ref(false)
const busyNames = ref(false)

const opServersByUuid = ref<Record<string, string[]>>({})
const opLoading = ref(false)

	const page = ref(1)
	const pageSize = ref(20)
	const onPageChange = (p: number) => { page.value = p }
	const onPageSizeChange = (s: number) => {
	  pageSize.value = s
	  page.value = 1
	}

// 游玩时长排序：'desc' 或 'none'
const playtimeSort = ref<'none' | 'desc'>('none')

const loadServers = async () => {
  const { data } = await api.get('/api/servers')
  servers.value = data || []
  // 默认全选（先赋值，后尝试从服务器取上次保存的选择覆盖）
  selectedServers.value = serverNames.value.slice()
  try {
    const { data: saved } = await api.get('/api/players/data-source-selection')
    if (Array.isArray(saved)) {
      const set = new Set(serverNames.value)
      const picked = saved.filter((x: any) => set.has(String(x)))
      if (picked.length > 0) selectedServers.value = picked
    }
  } catch (e) { /* 忽略错误，维持默认全选 */ }
}

const load = async () => {
  const { data } = await api.get('/api/players/with-groups', { params: { scope: scope.value } })
  rows.value = (data || []).map((x: any) => ({ ...x, play_time: x.play_time || {}, server_link_groups: x.server_link_groups || [] }))
  page.value = 1
  loadOpServers()
}

const loadOpServers = async () => {
  opLoading.value = true
  try {
    const { data } = await api.get('/api/players/op-servers')
    opServersByUuid.value = (data && typeof data === 'object') ? data : {}
  } catch (e) {
    opServersByUuid.value = {}
  } finally {
    opLoading.value = false
  }
}

const refreshPlayTime = async () => {
  busyTicks.value = true
  try {
    await api.post('/api/players/refresh-playtime')
    ElMessage.success('已开始后台刷新时长')
  } finally { busyTicks.value = false }
}

const refreshOfficialNames = async () => {
  busyNames.value = true
  try {
    await api.post('/api/players/refresh-names-official')
    ElMessage.success('已开始后台刷新正版玩家名')
  } finally { busyNames.value = false }
}

const avatarUrl = (uuid: string) => `/api/users/mc/avatar/${encodeURIComponent(uuid)}`

const sumTicks = (row: Player) => {
  const pt = row.play_time || {}
  const picks = selectedServers.value
  let total = 0
  for (const s of picks) { total += Number(pt[s] || 0) }
  return total
}

const filteredRows = computed(() => {
  const q = query.value.trim().toLowerCase()
  const base = rows.value
  const afterWhitelist = whitelistOnly.value
    ? base.filter(r => whitelistSet.value.has(r.uuid))
    : base
  if (!q) return afterWhitelist
  return afterWhitelist.filter(r => {
    const name = (r.player_name || '').toLowerCase()
    const uuid = (r.uuid || '').toLowerCase()
    return (name && name.includes(q)) || uuid.includes(q)
  })
})

const sortedRows = computed(() => {
  const arr = filteredRows.value.slice()
  if (playtimeSort.value === 'desc') {
    return arr.sort((a, b) => sumTicks(b) - sumTicks(a))
  }
  return arr
})

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return sortedRows.value.slice(start, start + pageSize.value)
})

const formatDuration = (ticks: number) => {
  const seconds = Math.floor(ticks / 20)
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds/60)}min`
  if (seconds < 86400) return `${(seconds/3600).toFixed(1)}h`
  return `${(seconds/3600).toFixed(1)}h`
}

const editingId = ref<number|null>(null)
const editName = ref('')
const canEditName = (row: Player) => row.is_offline === true
const startEdit = (row: Player) => {
  if (!canEditName(row)) return
  editingId.value = row.id
  editName.value = row.player_name || ''
}
const cancelEdit = () => { editingId.value = null }
const submitEdit = async (row: Player) => {
  if (!editName.value.trim()) { ElMessage.warning('名字不能为空'); return }
  await api.patch(`/api/players/${row.id}/name`, { name: editName.value.trim() })
  editingId.value = null
  await load()
}

const onScopeChange = async () => { await load() }
const onServersFilterChange = async () => {
  // 触发视图更新，并保存选择到服务器
  try {
    await api.patch('/api/players/data-source-selection', { servers: selectedServers.value })
  } catch (e) { /* 忽略错误 */ }
}
const onWhitelistToggle = () => { page.value = 1 }
const togglePlaytimeSort = () => {
  playtimeSort.value = playtimeSort.value === 'none' ? 'desc' : 'none'
  page.value = 1
}

const playerOptions = computed(() => {
  return rows.value
    .map((p) => {
      const name = (p.player_name || '').trim()
      const label = name ? `${name} (${p.uuid})` : p.uuid
      return { uuid: p.uuid, label }
    })
    .sort((a, b) => a.label.localeCompare(b.label))
})

const whitelistDialogVisible = ref(false)
const whitelistSubmitting = ref(false)
const whitelistForm = ref<{ player_name: string, is_official: boolean, servers: string[] }>({ player_name: '', is_official: true, servers: [] })
const openWhitelistDialog = () => {
  whitelistForm.value = {
    player_name: '',
    is_official: true,
    servers: (selectedServers.value.length > 0 ? selectedServers.value.slice() : serverNames.value.slice()),
  }
  whitelistDialogVisible.value = true
}
const submitWhitelist = async () => {
  if (!whitelistForm.value.player_name.trim()) { ElMessage.warning('请输入玩家名'); return }
  if (whitelistForm.value.servers.length === 0) { ElMessage.warning('请选择至少一个服务器'); return }
  whitelistSubmitting.value = true
  try {
    const name = whitelistForm.value.player_name.trim()
    const payload = {
      player_name: name,
      is_official: whitelistForm.value.is_official,
      servers: whitelistForm.value.servers,
    }
    const { data } = await api.post('/api/players/whitelist', payload)
    const ok = Array.isArray(data?.updated) ? data.updated.length : 0
    const err = Array.isArray(data?.errors) ? data.errors.length : 0
    ElMessage.success(`已写入白名单：${ok} 个服务器${err ? `（${err} 个失败）` : ''}`)
    whitelistDialogVisible.value = false
    // 刷新白名单 UUID 列表（用于“仅白名单玩家”筛选）
    try {
      const { data: wl } = await api.get('/api/players/whitelist-uuids')
      whitelistUUIDs.value = Array.isArray(wl) ? wl : []
    } catch (e) { /* ignore */ }
  } catch (e: any) {
    ElMessage.error(`添加失败: ${e?.response?.data?.detail || e?.message || '未知错误'}`)
  } finally {
    whitelistSubmitting.value = false
  }
}

const banDialogVisible = ref(false)
const banSubmitting = ref(false)
const banForm = ref<{ type: 'player' | 'ip', uuid: string, ip: string, reason: string, servers: string[] }>({
  type: 'player',
  uuid: '',
  ip: '',
  reason: '',
  servers: [],
})
const openBanDialog = () => {
  banForm.value = {
    type: 'player',
    uuid: '',
    ip: '',
    reason: '',
    servers: (selectedServers.value.length > 0 ? selectedServers.value.slice() : serverNames.value.slice()),
  }
  banDialogVisible.value = true
}
const submitBan = async () => {
  if (banForm.value.servers.length === 0) { ElMessage.warning('请选择至少一个服务器'); return }
  if (banForm.value.type === 'player' && !banForm.value.uuid) { ElMessage.warning('请选择玩家'); return }
  if (banForm.value.type === 'ip' && !banForm.value.ip.trim()) { ElMessage.warning('请输入 IP'); return }
  banSubmitting.value = true
  try {
    const p = banForm.value.type === 'player'
      ? rows.value.find(r => r.uuid === banForm.value.uuid)
      : null
    const payload: any = {
      type: banForm.value.type,
      servers: banForm.value.servers,
      reason: banForm.value.reason || null,
    }
    if (banForm.value.type === 'player') {
      payload.uuid = banForm.value.uuid
      payload.name = p?.player_name || null
    } else {
      payload.ip = banForm.value.ip.trim()
    }
    const { data } = await api.post('/api/players/ban', payload)
    const ok = Array.isArray(data?.updated) ? data.updated.length : 0
    const err = Array.isArray(data?.errors) ? data.errors.length : 0
    ElMessage.success(`已写入封禁：${ok} 个服务器${err ? `（${err} 个失败）` : ''}`)
    banDialogVisible.value = false
  } catch (e: any) {
    ElMessage.error(`封禁失败: ${e?.response?.data?.detail || e?.message || '未知错误'}`)
  } finally {
    banSubmitting.value = false
  }
}

watch(serverNames, (list) => {
  // 当服务器列表变化时，默认全选
  if (selectedServers.value.length === 0) selectedServers.value = list.slice()
})

onMounted(async () => {
  await loadServers()
  try {
    const { data } = await api.get('/api/players/whitelist-uuids')
    whitelistUUIDs.value = Array.isArray(data) ? data : []
    // 若白名单存在 uuid，则默认勾选；若为空，则默认不勾选
    whitelistOnly.value = whitelistUUIDs.value.length > 0
  } catch (e) {
    // 忽略错误，默认不勾选
    whitelistUUIDs.value = []
    whitelistOnly.value = false
  }
  await load()
})
</script>

<style scoped>
.page { display: flex; flex-direction: column; gap: 12px; height: 100%; overflow: hidden; }
.avatar { width: 36px; height: 36px; border-radius: 6px; }
.name-cell { display: flex; flex-direction: column; }
.name-cell .pname { font-weight: 600; color: var(--el-text-color-primary); }
.name-cell .uuid { color: var(--el-text-color-secondary); font-size: 12px; }
.name-cell .pname, .name-cell .uuid { line-height: 1.1; }
.clickable { cursor: pointer; }

/* 让筛选工具行与表格距离更舒适 */
.mb-2 { margin-bottom: 8px; }

/* 标题与计数之间留出间距 */
.header-title .title-count { margin-left: 8px; }
.header-actions { display:flex; align-items:center; gap:8px; white-space: nowrap; }
/* 头部栏：标题在左，操作在右 */
.header-bar { display:flex; align-items:center; justify-content: space-between; flex-wrap: nowrap; }
.header-title { display:flex; align-items:center; }

/* 让卡片内容充满并内部滚动 */
:deep(.el-card) { height: 100%; display: flex; flex-direction: column; }
:deep(.el-card__body) { flex: 1 1 auto; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
.table-container { flex: 1 1 auto; min-height: 0; overflow: hidden; }

/* 紧凑表格行高 */
:deep(.el-table--small .el-table__cell) { padding-top: 4px; padding-bottom: 4px; }
:deep(.el-table .cell) { padding-top: 0; padding-bottom: 0; }
.pt-sort-header { cursor: pointer; user-select: none; }

/* 工具条布局对齐插件页 */
.toolbar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.server-checkboxes { display: flex; flex-direction: column; gap: 6px; max-height: 240px; overflow: auto; }

/* 将“数据来源”按钮视觉上与单选组拼接，统一样式 */
.scope-group { display: inline-flex; align-items: center; }
.scope-group :deep(.el-radio-button__inner) { border-radius: 0 !important; }
.btn-scope-like { border-radius: 0 !important; margin-left: -1px; }
.wl-only { margin-left: 8px; }

/* 让页面底部留白用于容纳外部分页 */
.page { padding-bottom: 8px; }

/* 外部分页容器对齐右下角 */
.pm-pagination { display: flex; justify-content: flex-end; margin-top: 8px; }

.pm-dialog-form :deep(.el-form-item) { margin-bottom: 14px; }
.pm-form-hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.2;
}

</style>
