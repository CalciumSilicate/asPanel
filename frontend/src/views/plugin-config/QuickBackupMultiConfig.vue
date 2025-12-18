<template>
  <div class="pb-page">
    <div class="left-wrap" :class="{ 'is-collapsed': asideCollapsed, 'is-collapsing': asideCollapsing }">
      <div class="table-card left-panel">
        <el-card shadow="never">
          <template #header>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="text-base font-medium">Quick Backup Multi</span>
              </div>
              <div class="flex items-center gap-2">
                <el-tag type="success">安装数：{{ installedTotal }}</el-tag>
              </div>
            </div>
          </template>

          <el-input v-model="serverQuery" placeholder="搜索服务器" clearable class="mb-2">
            <template #prefix><el-icon><Search/></el-icon></template>
          </el-input>

          <el-table :data="filteredServers" size="small" stripe height="100%" v-loading="loadingServers" @row-click="selectServer">
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
                <el-tag v-if="!isAllowed(row)" type="warning" size="small">不支持</el-tag>
                <template v-else>
                  <el-tag v-if="isInstalled(row)" type="success" size="small">已安装</el-tag>
                  <el-button v-else size="small" type="success" :loading="installingServerId===row.id" @click.stop="installFor(row)">安装</el-button>
                </template>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </div>

      <div class="right-panel">
        <div v-if="!activeServer" class="main-placeholder">
          <el-empty description="请从左侧选择一个服务器以进行配置"/>
        </div>
        <div v-else>
          <PluginConfigForm :plugin-key="'quick_backup_multi'"
                            :server-id="activeServer.id"
                            :server-name="activeServer.name"
                            :show-raw-button="true"
                            :naked="false" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { asideCollapsed, asideCollapsing } from '@/store/ui'
import { normalizeServerType, installMCDR, fetchServerPlugins, fetchServersCached, invalidateServerPlugins } from './_Shared'
import PluginConfigForm from './components/PluginConfigForm.vue'

const PLUGIN_ID = 'quick_backup_multi'

const servers = ref<any[]>([])
const loadingServers = ref(false)
const serverQuery = ref('')
const installingServerId = ref<number|null>(null)
const activeServer = ref<any|null>(null)

const installedMap = ref(new Map<number, boolean>())
const installedTotal = computed(() => servers.value.filter(s => isAllowed(s) && !!installedMap.value.get(s.id)).length)
const filteredServers = computed(() => {
  if (!serverQuery.value.trim()) return servers.value
  const q = serverQuery.value.toLowerCase()
  return servers.value.filter(s => s.name?.toLowerCase().includes(q) || String(s.id).includes(q))
})

const isAllowed = (s:any) => normalizeServerType(s) !== 'velocity'
const isInstalled = (s:any) => !!installedMap.value.get(s.id)
const selectServer = (row:any) => { if (!isAllowed(row) || !isInstalled(row)) return; activeServer.value = row }

const loadServers = async () => {
  loadingServers.value = true
  try { servers.value = await fetchServersCached() } catch (e:any) { ElMessage.error('加载服务器失败') } finally { loadingServers.value = false }
  await refreshInstalled()
}

const refreshInstalled = async () => {
  installedMap.value = new Map()
  const tasks = servers.value.map(async (s:any) => {
    try { const plugs = await fetchServerPlugins(s.id); installedMap.value.set(s.id, !!(plugs.find((p:any)=> (p?.meta?.id||'')===PLUGIN_ID))) }
    catch { installedMap.value.set(s.id, false) }
  })
  await Promise.allSettled(tasks)
}

const installFor = async (s:any) => {
  if (!isAllowed(s)) return
  installingServerId.value = s.id
  try { await installMCDR(s.id, PLUGIN_ID); ElMessage.success(`已发起安装 ${PLUGIN_ID} 到 ${s.name}`); invalidateServerPlugins(s.id); installedMap.value.set(s.id, true) }
  catch (e:any) { ElMessage.error(e.response?.data?.detail || e.message || '安装失败') }
  finally { installingServerId.value = null }
}

onMounted(loadServers)
</script>

<style scoped>
.pb-page { }
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
.main-placeholder { display: flex; align-items: center; justify-content: center; height: 100%; }
.muted { color: #909399; font-size: 12px; }
.mb-2 { margin-bottom: 8px; }
.flex { display: flex; }
.items-center { align-items: center; }
.justify-between { justify-content: space-between; }
.gap-2 { gap: 8px; }
.w-full { width: 100%; }
.text-base { font-size: 14px; }
.font-medium { font-weight: 600; }
.server-cell .name { line-height: 18px; }
</style>
