<template>
  <div class="page">
    <el-card shadow="never">
      <template #header>
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <span class="text-base font-medium">玩家管理</span>
            <el-radio-group v-model="scope" size="small" @change="load">
              <el-radio-button label="official_only">仅正版玩家</el-radio-button>
              <el-radio-button label="include_cracked">包括盗版玩家</el-radio-button>
              <el-radio-button label="all">所有玩家</el-radio-button>
            </el-radio-group>
            <el-select v-model="selectedServers" multiple collapse-tags collapse-tags-tooltip placeholder="时长数据来源" size="small" style="min-width: 260px" @change="noop">
              <el-option v-for="s in serverNames" :key="s" :label="s" :value="s" />
            </el-select>
          </div>
          <div class="flex items-center gap-2">
            <el-button size="small" :loading="busyTicks" @click="refreshPlayTime">刷新时长</el-button>
            <el-button size="small" type="primary" :loading="busyNames" @click="refreshOfficialNames">刷新正版玩家名</el-button>
          </div>
        </div>
      </template>

      <el-table :data="rows" size="small" stripe :max-height="'calc(100vh - var(--el-header-height) - 220px)'">
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
        <el-table-column label="游玩时长" width="200" align="center">
          <template #default="{ row }">
            <span>{{ formatDuration(sumTicks(row)) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
  
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import api from '@/api'
import { ElMessage } from 'element-plus'

type Player = {
  id: number,
  uuid: string,
  player_name?: string | null,
  is_offline: boolean,
  play_time: Record<string, number>
}

const rows = ref<Player[]>([])
const servers = ref<{id:number,name:string,path:string}[]>([])
const serverNames = computed(() => servers.value.map(s => s.path.split('/').pop() || s.name))
const selectedServers = ref<string[]>([])
const scope = ref<'official_only'|'include_cracked'|'all'>('official_only')

const busyTicks = ref(false)
const busyNames = ref(false)

const loadServers = async () => {
  const { data } = await api.get('/api/servers')
  servers.value = data || []
  // 默认全选
  selectedServers.value = serverNames.value.slice()
}

const load = async () => {
  const { data } = await api.get('/api/players', { params: { scope: scope.value } })
  rows.value = (data || []).map((x: any) => ({ ...x, play_time: x.play_time || {} }))
}

const refreshPlayTime = async () => {
  busyTicks.value = true
  try {
    await api.post('/api/players/refresh-playtime')
    await load()
    ElMessage.success('已刷新时长')
  } finally { busyTicks.value = false }
}

const refreshOfficialNames = async () => {
  busyNames.value = true
  try {
    await api.post('/api/players/refresh-names-official')
    await load()
    ElMessage.success('已刷新正版玩家名')
  } finally { busyNames.value = false }
}

const avatarUrl = (uuid: string) => `https://mc-heads.net/avatar/${encodeURIComponent(uuid)}`

const sumTicks = (row: Player) => {
  const pt = row.play_time || {}
  const picks = selectedServers.value.length ? selectedServers.value : serverNames.value
  let total = 0
  for (const s of picks) { total += Number(pt[s] || 0) }
  return total
}

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

const noop = () => {}

onMounted(async () => {
  await loadServers()
  await load()
})
</script>

<style scoped>
.page { display: flex; flex-direction: column; gap: 12px; }
.avatar { width: 42px; height: 42px; border-radius: 6px; }
.name-cell { display: flex; flex-direction: column; }
.name-cell .pname { font-weight: 600; color: var(--el-text-color-primary); }
.name-cell .uuid { color: var(--el-text-color-secondary); font-size: 12px; }
.clickable { cursor: pointer; }
</style>

