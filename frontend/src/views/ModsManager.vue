<template>
  <div class="mm-page">

    <!-- Toolbar -->
    <ModsToolbar
      :selected-server="selectedServer"
      :mods-count="mods.length"
      :total-mods-count="totalModsCount"
      :is-server-running="isServerRunning"
      @select-server="selectServerById"
      @modrinth="openModrinthDialog"
      @curseforge="openCurseforgeDialog"
      @upload="openUploadDialog"
      @copy="openCopyDialog"
      @check-updates="checkUpdates"
    />

    <!-- No server selected: Picker -->
    <div v-if="!selectedServer" class="mm-placeholder">
      <ModsServerPicker
        :servers="servers"
        :loading="serversLoading"
        :total-mods-count="totalModsCount"
        @select="selectServer"
      />
    </div>

    <!-- Server selected: Glass card -->
    <div v-else class="mm-glass-card">
      <div class="shimmer-line" aria-hidden="true" />

      <!-- Overview info strip -->
      <div v-if="overview" class="mm-overview">
        <el-descriptions :column="4" border size="small">
          <el-descriptions-item label="存储根">{{ overview.storage_root }}</el-descriptions-item>
          <el-descriptions-item label="核心版本">{{ overview.mc_version || '-' }}</el-descriptions-item>
          <el-descriptions-item label="加载器">
            <span v-if="overview.loader==='未安装'">
              未安装
              <el-button size="small" type="primary" @click="goToServers">去安装</el-button>
            </span>
            <span v-else>{{ overview.loader }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="加载器版本">{{ overview.loader_version || '-' }}</el-descriptions-item>
        </el-descriptions>
      </div>

      <!-- Mods table -->
      <div class="mm-table-wrap" v-loading="modsLoading" element-loading-background="transparent">
        <table class="native-table">
          <colgroup>
            <col style="min-width:240px" />
            <col style="width:120px" />
            <col style="width:160px" />
            <col style="min-width:140px" />
            <col style="width:120px" />
            <col style="width:250px" />
          </colgroup>
          <thead>
            <tr class="thead-row">
              <th class="th-cell">模组</th>
              <th class="th-cell th-center">来源</th>
              <th class="th-cell th-center">模组版本</th>
              <th class="th-cell">支持的MC版本</th>
              <th class="th-cell th-center">状态</th>
              <th class="th-cell th-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!modsLoading && pagedMods.length === 0">
              <td colspan="6" class="td-empty">
                <el-empty description="暂无模组" :image-size="80" />
              </td>
            </tr>
            <tr v-for="row in pagedMods" :key="row.file_name" class="tbl-row">
              <td class="td-cell">
                <PluginNameCell
                  :id="row.meta.slug || row.meta.id"
                  :name="row.meta.name"
                  :description="row.meta.description"
                  :filename="row.file_name"
                />
              </td>
              <td class="td-cell td-center">
                <el-tag v-if="row.meta.source" size="small">{{ row.meta.source }}</el-tag>
                <el-tag v-else size="small" type="info">未知</el-tag>
              </td>
              <td class="td-cell td-center">
                <div class="version-cell">
                  <el-tag size="small" type="success">{{ row.meta.version || '-' }}</el-tag>
                  <el-tooltip v-if="updatesMap.get(row.file_name)" :content="`有新版：${updatesMap.get(row.file_name)?.version || ''}`" placement="top-start" effect="light">
                    <el-button size="small" type="warning" circle plain :icon="Refresh" @click="installUpdateForMod(row)" />
                  </el-tooltip>
                </div>
              </td>
              <td class="td-cell">
                <template v-if="(row.meta.game_versions || []).length >= 3">
                  <div class="ellipsis-tags">
                    <el-tag v-for="v in (row.meta.game_versions || []).slice(0,2)" :key="v" size="small" style="margin-right:4px;">{{ v }}</el-tag>
                    <el-tooltip placement="top-start" effect="light">
                      <template #content>
                        <div>
                          <el-tag v-for="v in (row.meta.game_versions || [])" :key="v" size="small" style="margin:2px;">{{ v }}</el-tag>
                        </div>
                      </template>
                      <el-tag size="small" type="info">+{{ (row.meta.game_versions || []).length - 2 }}</el-tag>
                    </el-tooltip>
                  </div>
                </template>
                <template v-else>
                  <el-space wrap>
                    <el-tag v-for="v in (row.meta.game_versions || [])" :key="v" size="small">{{ v }}</el-tag>
                    <span v-if="!(row.meta.game_versions || []).length"><el-tag size="small" type="info">未知</el-tag></span>
                  </el-space>
                </template>
              </td>
              <td class="td-cell td-center">
                <el-switch v-model="row.enabled" @change="toggleMod(row)" :loading="row.loading" :disabled="isServerRunning"/>
              </td>
              <td class="td-cell td-right">
                <div class="row-actions">
                  <button class="act-btn act-dl" :disabled="row.loading" @click="downloadMod(row)">
                    <el-icon :size="12"><Download /></el-icon>下载
                  </button>
                  <button class="act-btn act-detail" @click="openChangeVersion(row)">更改版本</button>
                  <el-popconfirm title="确定删除这个模组吗？" width="220" @confirm="deleteMod(row)">
                    <template #reference>
                      <button class="act-btn act-danger" :disabled="row.loading || isServerRunning">
                        <el-icon :size="12"><Delete /></el-icon>删除
                      </button>
                    </template>
                  </el-popconfirm>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Footer: pagination -->
      <div class="mm-footer">
        <el-pagination
          background
          layout="prev, pager, next, sizes, total"
          :page-sizes="[15, 20, 50, 100]"
          :page-size="pageSize"
          :current-page="page"
          :total="filteredMods.length"
          @current-change="p => page = p"
          @size-change="s => { pageSize = s; page = 1 }"
        />
      </div>
    </div>

    <!-- 对话框：Modrinth 搜索 -->
    <el-dialog v-if="modrinthDialog.visible" v-model="modrinthDialog.visible" title="从 Modrinth 添加" width="70%" top="8vh" destroy-on-close>
      <div class="plugin-toolbar compact">
        <el-input v-model="modrinthDialog.query" placeholder="搜索：名称 / 描述" clearable style="width: 360px;" @keyup.enter="searchModrinth"/>
        <el-button type="primary" :icon="Search" @click="searchModrinth">搜索</el-button>
      </div>
      <div v-loading="modrinthDialog.loading" element-loading-background="transparent" style="max-height:50vh;overflow-y:auto;overflow-x:hidden;scrollbar-width:thin;">
        <table class="native-table">
          <colgroup>
            <col style="min-width:320px" />
            <col style="width:140px" />
            <col style="width:160px" />
            <col style="width:240px" />
          </colgroup>
          <thead>
            <tr class="thead-row">
              <th class="th-cell">模组</th>
              <th class="th-cell th-center">当前安装</th>
              <th class="th-cell th-center">统计</th>
              <th class="th-cell th-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!modrinthDialog.loading && modrinthDialog.items.length === 0">
              <td colspan="4" class="td-empty">
                <el-empty description="暂无结果" :image-size="80" />
              </td>
            </tr>
            <tr v-for="row in modrinthDialog.items" :key="row.project_id" class="tbl-row">
              <td class="td-cell">
                <PluginNameCell
                  :id="row.slug"
                  :name="row.title"
                  :description="row.description"
                />
              </td>
              <td class="td-cell td-center">
                <el-tag v-if="isInstalledSlug(row.slug)" size="small" type="success">已安装</el-tag>
                <el-tag v-else size="small" type="info">未安装</el-tag>
              </td>
              <td class="td-cell td-center">
                <div class="stats-cell">
                  <span class="stat-chip stat-dl-chip">
                    <el-icon :size="11"><Download /></el-icon>
                    {{ abbrNumber(row.downloads) }}
                  </span>
                  <span class="stat-chip stat-star">
                    ★ {{ abbrNumber(row.follows) }}
                  </span>
                </div>
              </td>
              <td class="td-cell td-right">
                <el-button-group>
                  <el-button
                    v-if="!isInstalledSlug(row.slug)"
                    size="small"
                    type="primary"
                    :loading="row.installing"
                    @click="installFromModrinth(row)"
                  >安装</el-button>
                  <el-button
                    v-else
                    size="small"
                    type="primary"
                    @click="openChangeVersionForSlug(row)"
                  >版本</el-button>
                  <el-button size="small" type="success" @click="openModrinthDetail(row)">跳转详情</el-button>
                </el-button-group>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <template #footer>
        <div class="dialog-footer-flex">
          <div class="left">
            <el-checkbox v-model="modrinthDialog.compatibleOnly">只看与当前版本兼容</el-checkbox>
          </div>
          <div class="right">
            <el-pagination
              background
              layout="prev, pager, next, sizes, total"
              :page-sizes="[10,20,50,100]"
              :current-page="modrinthDialog.page"
              :total="modrinthDialog.total"
              :page-size="modrinthDialog.limit"
              @current-change="p => { modrinthDialog.page = p; searchModrinth(); }"
              @size-change="s => { modrinthDialog.limit = s; modrinthDialog.page = 1; searchModrinth(); }"
            />
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- 对话框：Curseforge 搜索（占位） -->
    <el-dialog v-if="curseforgeDialog.visible" v-model="curseforgeDialog.visible" title="从 Curseforge 添加" width="600px">
      <div>暂未配置 Curseforge API Key，或后端未实现。可先使用 Modrinth。</div>
      <template #footer>
        <el-button @click="curseforgeDialog.visible=false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 对话框：上传 -->
    <el-dialog v-if="uploadDialog.visible" v-model="uploadDialog.visible" title="上传模组 (.jar)" width="520px">
      <el-upload
        drag
        :auto-upload="false"
        :on-change="file => uploadDialog.file=file.raw"
        :limit="1"
        accept=".jar"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">将文件拖到此处，或<em>点击上传</em></div>
      </el-upload>
      <template #footer>
        <el-button @click="uploadDialog.visible=false">取消</el-button>
        <el-button type="primary" :disabled="!uploadDialog.file" @click="doUpload">开始上传</el-button>
      </template>
    </el-dialog>

    <!-- 对话框：复制 -->
    <el-dialog v-if="copyDialog.visible" v-model="copyDialog.visible" title="从其他服务器复制" width="520px">
      <el-form label-position="top">
        <el-form-item label="选择源服务器" required>
          <el-select v-model="copyDialog.src" filterable placeholder="请选择服务器" style="width: 100%;">
            <el-option v-for="s in servers" :key="s.id" :label="s.name + ' (ID '+s.id+')'" :value="s.id" :disabled="s.id===selectedServer.id || !canCopyFrom(s)" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="copyDialog.deleteBefore">复制前删除目标服务器现有模组</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="copyDialog.visible=false">取消</el-button>
        <el-button type="primary" :loading="copyDialog.loading" :disabled="!copyDialog.src" @click="doCopy">确认复制</el-button>
      </template>
        </el-dialog>

    <!-- 更改版本对话框 -->
    <el-dialog v-if="changeDialog.visible" v-model="changeDialog.visible" title="更改模组版本" width="600px">
      <div v-if="changeDialog.row">
        <div class="mb-3">{{ changeDialog.row.meta?.name || changeDialog.row.file_name }}</div>
        <el-form label-position="top">
          <el-form-item label="选择版本">
            <el-select v-model="changeDialog.selectedVersion" filterable placeholder="请选择版本" :loading="changeDialog.loading" style="width: 100%;">
              <el-option v-for="v in changeDialog.versions" :key="v.id" :label="v.version_number" :value="v.id">
                <span>{{ v.version_number }}</span>
                <span class="muted" style="margin-left: 8px;">{{ (v.game_versions || []).join(', ') }}</span>
              </el-option>
            </el-select>
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="changeDialog.visible=false">取消</el-button>
        <el-button type="primary" :loading="changeDialog.submitting" :disabled="!changeDialog.selectedVersion" @click="confirmChangeVersion">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import {ref, computed, onMounted, watch} from 'vue'
import { ElMessage, ElNotification } from 'element-plus'
import { Delete, Download, Upload, UploadFilled, Refresh, Search } from '@element-plus/icons-vue'
import PluginNameCell from '@/components/PluginNameCell.vue'
import apiClient, { isRequestCanceled } from '@/api'
import { useTasksStore } from '@/store/tasks'
import { useTransfersStore } from '@/store/transfers'
import { useUserStore } from '@/store/user'
import { storeToRefs } from 'pinia'
import router from '@/router'
import ModsToolbar from './mods-manager/ModsToolbar.vue'
import ModsServerPicker from './mods-manager/ModsServerPicker.vue'
const { fetchTasks } = useTasksStore()
const { startDownload, startUpload } = useTransfersStore()
const { activeGroupIds } = storeToRefs(useUserStore())

// 左侧数据
const servers = ref([])
const serversLoading = ref(false)
const modsCountsLoaded = ref(false)
const totalModsCount = computed(() => {
  if (!modsCountsLoaded.value) return '计算中'
  return servers.value.reduce((sum, s) => sum + (Number(s.mods_count) || 0), 0)
})

// 右侧数据
const selectedServer = ref(null)
const mods = ref([])
// 后台预取的模组列表缓存
const serverModsMap = new Map()
const modsLoading = ref(false)
const overview = ref(null)

// 分页
const page = ref(1)
const pageSize = ref(15)

const filteredMods = computed(() => mods.value)
const pagedMods = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredMods.value.slice(start, start + pageSize.value)
})

const isVelocity = (s) => (s?.core_config?.server_type || s?.core_config?.serverType) === 'velocity'
const isServerRunning = computed(() => selectedServer.value?.status === 'running')

const selectServerById = async (id) => {
  if (!id) { selectedServer.value = null; return }
  const srv = servers.value.find(s => s.id === id)
  if (srv) await selectServer(srv)
}

const formatBytes = (bytes) => {
  const b = Number(bytes || 0)
  if (!b) return '0 B'
  const units = ['B','KB','MB','GB','TB']
  const i = Math.floor(Math.log(b) / Math.log(1024))
  return (b / Math.pow(1024, i)).toFixed(2) + ' ' + units[i]
}

let modsCountsRequestSeq = 0
const fetchServersModsCounts = async (requestId) => {
  try {
    const { data } = await apiClient.get('/api/mods/servers')
    if (requestId !== modsCountsRequestSeq) return

    const countMap = new Map((data || []).map(item => [Number(item.id), item.mods_count]))
    servers.value.forEach((s) => {
      if (countMap.has(Number(s.id))) {
        s.mods_count = countMap.get(Number(s.id))
        s.mods_count_state = 'ok'
      } else {
        s.mods_count = null
        s.mods_count_state = 'failed'
      }
    })
    modsCountsLoaded.value = true
  } catch (e) {
    if (requestId !== modsCountsRequestSeq) return
    servers.value.forEach((s) => {
      s.mods_count = null
      s.mods_count_state = 'failed'
    })
    modsCountsLoaded.value = true
  }
}

const initialLoad = async () => {
  serversLoading.value = true
  try {
    // 快速获取服务器列表（不含 mods_count，单独通过 /api/mods/servers 获取）
    const { data: serverData } = await apiClient.get('/api/servers')
    servers.value = (serverData || []).map(s => ({
      ...s,
      mods_count: null,
      mods_count_state: 'pending',
    }))

    modsCountsLoaded.value = false
    const requestId = ++modsCountsRequestSeq
    fetchServersModsCounts(requestId)

    // 后台预取各服务器的模组列表，填充缓存，避免后续重复拉取
    prefetchAllServerMods(servers.value)
    // 初始不选中服务器，保持右侧空白
  } catch (e) {
    if (!isRequestCanceled(e)) ElMessage.error('加载服务器失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    serversLoading.value = false
  }
}

const handleSelectServer = async (server) => {
  await selectServer(server)
}

const selectServer = async (server) => {
  const type = (server?.core_config?.server_type || server?.core_config?.serverType || '').toLowerCase()
  if (type === 'vanilla' && !(server?.core_config?.is_fabric || server?.core_config?.isFabric)) {
    ElMessage.warning('Vanilla 服务器不支持模组管理')
    return
  }
  selectedServer.value = server
  page.value = 1
  await fetchMods()
  await fetchOverview()
}

const fetchMods = async () => {
  if (!selectedServer.value) return
  const cached = serverModsMap.get(selectedServer.value.id)
  if (cached) {
    mods.value = cached
    return
  }
  modsLoading.value = true
  try {
    const { data } = await apiClient.get(`/api/mods/server/${selectedServer.value.id}`)
    mods.value = (data?.data || []).map(x => ({ ...x, loading: false }))
    serverModsMap.set(selectedServer.value.id, mods.value)
    // 从 DB 元数据中恢复更新提示
    updatesMap.clear()
    mods.value.forEach(m => {
      const meta = m.meta || {}
      if (meta.modrinth_update_available && (meta.modrinth_latest_version_number || meta.modrinth_latest_version_id)) {
        updatesMap.set(m.file_name, { version: meta.modrinth_latest_version_number, version_id: meta.modrinth_latest_version_id })
      }
    })
  } catch (e) {
    if (!isRequestCanceled(e)) ElMessage.error('加载模组失败: ' + (e.response?.data?.detail || e.message))
    mods.value = []
  } finally {
    modsLoading.value = false
  }
}

// 后台预取所有服务器的模组列表到缓存，控制并发
const prefetchAllServerMods = async (serverList = []) => {
  if (!Array.isArray(serverList) || serverList.length === 0) return
  const concurrency = 5
  const queue = [...serverList]
  const workers = Array.from({ length: Math.min(concurrency, queue.length) }, () => (async () => {
    while (queue.length > 0) {
      const srv = queue.shift()
      if (!srv) break
      const id = srv.id
      if (serverModsMap.has(id)) continue
      try {
        const { data } = await apiClient.get(`/api/mods/server/${id}`)
        const list = (data?.data || []).map(x => ({ ...x, loading: false }))
        serverModsMap.set(id, list)
        // 如果当前正在查看该服务器且尚未有列表，则立刻显示
        if (selectedServer.value && selectedServer.value.id === id && mods.value.length === 0) {
          mods.value = list
        }
      } catch {
        serverModsMap.set(id, [])
      }
    }
  })())
  await Promise.allSettled(workers)
}

const fetchOverview = async () => {
  if (!selectedServer.value) return
  try {
    const { data } = await apiClient.get(`/api/mods/overview/${selectedServer.value.id}`)
    overview.value = data
  } catch (e) {
    overview.value = null
  }
}

const getAuthorsArray = (meta) => {
  if (!meta) return []
  if (Array.isArray(meta.authors)) return meta.authors.filter(Boolean)
  if (meta.author) {
    if (Array.isArray(meta.author)) return meta.author.filter(Boolean)
    if (typeof meta.author === 'string') return [meta.author]
  }
  return []
}

const toggleMod = async (row) => {
  row.loading = true
  const enable = row.enabled
  try {
    const { data } = await apiClient.post(`/api/mods/server/${selectedServer.value.id}/switch/${row.file_name}?enable=${enable}`)
    ElMessage.success(`模组 "${row.meta.name || row.file_name}" 已${enable ? '启用' : '禁用'}`)
    if (data && data.file_name) {
      row.file_name = data.file_name
    }
  } catch (e) {
    ElMessage.error('切换失败: ' + (e.response?.data?.detail || e.message))
    row.enabled = !enable
  } finally {
    row.loading = false
  }
}

const downloadMod = async (row) => {
  row.loading = true
  try {
    await startDownload({
      url: `/api/mods/download/${selectedServer.value.id}/${row.file_name}`,
      title: row.meta?.name || row.file_name,
      fallbackFilename: row.file_name,
    })
  } catch (e) {
    ElMessage.error('下载失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    row.loading = false
  }
}

const deleteMod = async (row) => {
  row.loading = true
  try {
    await apiClient.delete(`/api/mods/server/${selectedServer.value.id}/${row.file_name}`)
    ElMessage.success('已删除')
    await fetchMods()
  } catch (e) {
    ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
    row.loading = false
  }
}

// Modrinth 搜索/安装
const modrinthDialog = ref({ visible: false, loading: false, query: '', items: [], page: 1, limit: 15, total: 0, compatibleOnly: true })
const openModrinthDialog = async () => {
  modrinthDialog.value.query = ''
  modrinthDialog.value.items = []
  modrinthDialog.value.page = 1
  modrinthDialog.value.total = 0
  modrinthDialog.value.visible = true
}
const searchModrinth = async () => {
  modrinthDialog.value.loading = true
  try {
    const params = new URLSearchParams()
    params.set('q', modrinthDialog.value.query || '')
    params.set('limit', String(modrinthDialog.value.limit))
    params.set('offset', String((modrinthDialog.value.page - 1) * modrinthDialog.value.limit))
    // 依据加载器过滤
    const loader = overview.value?.loader
    if (loader && loader !== '未安装') params.set('loader', loader)
    // Velocity 场景不传 game_version，避免 Modrinth 过滤器出错
    if (modrinthDialog.value.compatibleOnly && overview.value?.mc_version && String(loader).toLowerCase() !== 'velocity') {
      params.set('game_version', overview.value.mc_version)
    }
    const { data } = await apiClient.get(`/api/mods/search/modrinth?${params.toString()}`)
    const hits = data?.hits || []
    modrinthDialog.value.items = hits.map(h => ({
      project_id: h.project_id,
      slug: h.slug,
      title: h.title,
      description: h.description,
      downloads: h.downloads || 0,
      follows: h.follows || h.followers || 0,
      project_type: h.project_type,
      installing: false,
    }))
    modrinthDialog.value.total = data?.total_hits || hits.length
  } catch (e) {
    if (!isRequestCanceled(e)) ElMessage.error('搜索失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    modrinthDialog.value.loading = false
  }
}
const isInstalledSlug = (slug) => mods.value.some(m => ((m.meta?.slug || m.meta?.id || m.meta?.modrinth_project_id || '') + '').toLowerCase() === String(slug || '').toLowerCase())
const abbrNumber = (n) => {
  const num = Number(n || 0)
  if (num < 1000) return String(num)
  if (num < 1e6) return (num / 1e3).toFixed(1).replace(/\.0$/, '') + 'K'
  if (num < 1e9) return (num / 1e6).toFixed(1).replace(/\.0$/, '') + 'M'
  return (num / 1e9).toFixed(1).replace(/\.0$/, '') + 'B'
}

const openModrinthDetail = (row) => {
  if (!row?.slug) return
  const kind = (row.project_type || '').toLowerCase() === 'plugin' ? 'plugin' : 'mod'
  window.open(`https://modrinth.com/${kind}/${row.slug}`,'_blank')
}

const getInstalledModBySlug = (slug) => mods.value.find(m => ((m.meta?.slug || m.meta?.id || m.meta?.modrinth_project_id || '') + '').toLowerCase() === String(slug || '').toLowerCase())
const openChangeVersionForSlug = (row) => {
  const installed = getInstalledModBySlug(row.slug)
  if (!installed) return ElMessage.warning('未在当前服务器安装该模组')
  openChangeVersion(installed)
}

const changeDialog = ref({ visible: false, row: null, versions: [], loading: false, selectedVersion: null, submitting: false })
const openChangeVersion = async (row) => {
  changeDialog.value.visible = true
  changeDialog.value.row = row
  changeDialog.value.selectedVersion = null
  changeDialog.value.loading = true
  changeDialog.value.versions = []
  try {
    const projectId = row.meta?.modrinth_project_id || row.meta?.id
    if (row.meta?.source === 'modrinth' && projectId) {
      const params = new URLSearchParams()
      params.set('project_id', projectId)
      const loader = overview.value?.loader
      if (loader && loader !== '未安装') params.set('loader', loader)
      if (overview.value?.mc_version && String(loader).toLowerCase() !== 'velocity') {
        params.set('game_version', overview.value.mc_version)
      }
      const { data } = await apiClient.get(`/api/mods/modrinth/versions?${params.toString()}`)
      changeDialog.value.versions = data || []
    } else {
      ElMessage.warning('当前来源不支持更改版本')
      changeDialog.value.visible = false
    }
  } catch (e) {
    ElMessage.error('获取版本失败: ' + (e.response?.data?.detail || e.message))
    changeDialog.value.visible = false
  } finally {
    changeDialog.value.loading = false
  }
}
const confirmChangeVersion = async () => {
  if (!changeDialog.value.row || !changeDialog.value.selectedVersion) return
  const row = changeDialog.value.row
  const versionId = changeDialog.value.selectedVersion
  changeDialog.value.submitting = true
  try {
    await apiClient.post('/api/mods/change-version', {
      server_id: selectedServer.value.id,
      file_name: row.file_name,
      source: row.meta?.source || 'modrinth',
      project_id: row.meta?.modrinth_project_id || row.meta?.id,
      version_id: versionId,
    })
    ElMessage.success('已更改版本')
    changeDialog.value.visible = false
    await fetchMods()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message)
  } finally {
    changeDialog.value.submitting = false
  }
}

const installFromModrinth = async (row) => {
  if (!selectedServer.value) return
  row.installing = true
  try {
    await apiClient.post('/api/mods/install/modrinth', {
      server_id: selectedServer.value.id,
      project_id: row.project_id,
    })
    ElNotification({ title: '安装成功', message: `${row.title} 已安装`, type: 'success' })
    await fetchMods()
  } catch (e) {
    ElNotification({ title: '安装失败', message: e.response?.data?.detail || e.message, type: 'error', duration: 0 })
  } finally {
    row.installing = false
  }
}

// Curseforge（占位）
const curseforgeDialog = ref({ visible: false })
const openCurseforgeDialog = () => curseforgeDialog.value.visible = true

// 上传
const uploadDialog = ref({ visible: false, file: null, loading: false })
const openUploadDialog = () => { uploadDialog.value.visible = true; uploadDialog.value.file = null }
const doUpload = async () => {
  if (!uploadDialog.value.file) return
  
  const file = uploadDialog.value.file
  uploadDialog.value.visible = false
  
  const form = new FormData()
  form.append('file', file)
  
  const { error } = await startUpload({
    url: `/api/mods/upload/${selectedServer.value.id}`,
    data: form,
    title: file.name || '模组上传',
    filename: file.name,
  })
  
  if (error) {
    ElMessage.error('上传失败: ' + error)
  } else {
    ElMessage.success('上传成功')
    await fetchMods()
  }
}

// 复制
const copyDialog = ref({ visible: false, src: null, deleteBefore: false, loading: false })
const openCopyDialog = () => { copyDialog.value.visible = true; copyDialog.value.src = null; copyDialog.value.deleteBefore = false }

const normalizeServerType = (s) => {
  const cfg = s?.core_config || {}
  const t = cfg.server_type || cfg.serverType
  if (t === 'velocity') return 'velocity'
  if (t === 'forge') return 'forge'
  if (t === 'vanilla' && (cfg.is_fabric || cfg.isFabric)) return 'fabric'
  return 'vanilla'
}
const canCopyFrom = (s) => {
  if (!selectedServer.value) return false
  return normalizeServerType(s) === normalizeServerType(selectedServer.value)
}
const doCopy = async () => {
  copyDialog.value.loading = true
  try {
    await apiClient.post('/api/mods/copy', {
      source_server_id: copyDialog.value.src,
      target_server_id: selectedServer.value.id,
      delete_target_before: copyDialog.value.deleteBefore,
    })
    ElMessage.success('复制完成')
    copyDialog.value.visible = false
    fetchTasks().catch(() => {})
    await fetchMods()
  } catch (e) {
    ElMessage.error('复制失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    copyDialog.value.loading = false
  }
}

// 检查更新
const checkUpdates = async () => {
  try {
    await apiClient.get(`/api/mods/check-updates/${selectedServer.value.id}`)
    ElMessage.success('检查任务已开始，请稍后刷新')
    // 可选：延迟刷新一次
    setTimeout(fetchMods, 12000)
  } catch (e) {
    ElMessage.error('检查失败: ' + (e.response?.data?.detail || e.message))
  }
}

const updatesMap = new Map()
const installUpdateForMod = async (row) => {
  const info = updatesMap.get(row.file_name)
  if (!info) return
  const projectId = row.meta?.modrinth_project_id || row.meta?.id
  if (!projectId) return ElMessage.error('无法获取项目 ID，无法更新')
  row.loading = true
  try {
    await apiClient.post('/api/mods/change-version', {
      server_id: selectedServer.value.id,
      file_name: row.file_name,
      source: 'modrinth',
      project_id: projectId,
      version_id: info.version_id,
    })
    ElNotification({ title: '更新完成', message: `${row.meta?.name || row.file_name} -> ${info.version}` , type: 'success' })
    await fetchMods()
    updatesMap.delete(row.file_name)
  } catch (e) {
    ElNotification({ title: '更新失败', message: e.response?.data?.detail || e.message, type: 'error', duration: 0 })
  } finally {
    row.loading = false
  }
}

const openModDetail = (row) => {
  const source = row.meta?.source
  if (source === 'modrinth') {
    const slug = row.meta?.slug || row.meta?.id || row.meta?.modrinth_project_id
    const kind = (row.meta?.project_page || '').toLowerCase() === 'plugin' ? 'plugin' : 'mod'
    if (slug) window.open(`https://modrinth.com/${kind}/${slug}`, '_blank')
  }
}

const goToServers = () => router.push('/servers')

// 监听组切换，重新加载服务器和模组列表
watch(activeGroupIds, () => {
  selectedServer.value = null
  mods.value = []
  serverModsMap.clear()
  initialLoad()
}, { deep: true })

onMounted(initialLoad)
</script>

<style scoped>
/* ── Page layout ─────────────────────────────────────────── */
.mm-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: calc(100vh - var(--el-header-height) - 48px);
  overflow: hidden;
  min-height: 0;
}

/* ── Placeholder (no server selected) ────────────────────── */
.mm-placeholder {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  align-self: center;
  width: 100%;
  max-width: 520px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.58);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(167, 139, 250, 0.18);
  box-shadow: 0 4px 32px rgba(167, 139, 250, 0.10);
}
:global(.dark) .mm-placeholder {
  background: rgba(15, 23, 42, 0.65);
  border-color: rgba(167, 139, 250, 0.12);
}

/* ── Glass card (server selected) ────────────────────────── */
.mm-glass-card {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.58);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(167, 139, 250, 0.18);
  box-shadow: 0 4px 32px rgba(167, 139, 250, 0.10), inset 0 1px 0 rgba(255, 255, 255, 0.80);
  overflow: hidden;
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
}
.mm-glass-card:hover {
  border-color: rgba(167, 139, 250, 0.28);
  box-shadow: 0 8px 40px rgba(167, 139, 250, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.80);
}
:global(.dark) .mm-glass-card {
  background: rgba(15, 23, 42, 0.65);
  border-color: rgba(167, 139, 250, 0.12);
  box-shadow: 0 4px 32px rgba(0, 0, 0, 0.40), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

/* shimmer accent line */
.shimmer-line {
  height: 3px;
  flex-shrink: 0;
  background: linear-gradient(90deg, #a78bfa 0%, var(--brand-primary) 50%, #a78bfa 100%);
  background-size: 200% 100%;
  animation: shimmer-slide 3s linear infinite;
  border-radius: 3px 3px 0 0;
}
@keyframes shimmer-slide {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* overview strip */
.mm-overview {
  flex-shrink: 0;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(167, 139, 250, 0.12);
}

.mm-table-wrap {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
  padding: 0 4px;
}

.mm-footer {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 10px 20px;
  border-top: 1px solid rgba(167, 139, 250, 0.12);
}

/* ── Native table ────────────────────────────────────────── */
.native-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: auto;
}
thead { position: sticky; top: 0; z-index: 10; }
.thead-row {
  background: rgba(248, 250, 255, 0.96);
  -webkit-backdrop-filter: saturate(140%) blur(8px);
  backdrop-filter: saturate(140%) blur(8px);
  border-bottom: 1px solid rgba(167, 139, 250, 0.12);
}
:global(.dark) .thead-row { background: rgba(15, 23, 42, 0.96); }
.th-cell {
  padding: 10px 12px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--el-text-color-secondary);
  opacity: 0.72;
  white-space: nowrap;
  text-align: left;
}
.th-center { text-align: center; }
.th-right  { text-align: right; padding-right: 16px; }
.tbl-row {
  border-bottom: 1px solid rgba(167, 139, 250, 0.07);
  transition: background 0.12s ease;
}
.tbl-row:last-child { border-bottom: none; }
.tbl-row:hover { background: rgba(167, 139, 250, 0.05); }
.td-cell {
  padding: 12px 12px;
  vertical-align: middle;
}
.td-center { text-align: center; }
.td-right  { text-align: right; padding-right: 16px; }
.td-empty  { text-align: center; padding: 48px 0; }

/* ── Shared cell styles ───────────────────────────────────── */
.muted { font-size: 12px; color: var(--el-text-color-secondary); }
.version-cell { display: flex; align-items: center; gap: 8px; }
.version-cell .el-button.is-circle .el-icon { display: inline-flex; align-items: center; justify-content: center; }
.ellipsis-tags { display: inline-flex; align-items: center; }

/* ── Stat chips ──────────────────────────────────────────── */
.stats-cell { display: inline-flex; align-items: center; gap: 6px; }
.stat-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 999px;
  font-size: 12px; font-weight: 600; white-space: nowrap;
}
.stat-star { background: rgba(245,158,11,0.10); color: #f59e0b; border: 1px solid rgba(245,158,11,0.22); }
.stat-dl-chip { background: rgba(167,139,250,0.10); color: #a78bfa; border: 1px solid rgba(167,139,250,0.22); }

/* ── Row action buttons ──────────────────────────────────── */
.row-actions { display: inline-flex; align-items: center; gap: 4px; }
.act-btn {
  display: inline-flex; align-items: center; gap: 4px;
  height: 26px; padding: 0 10px; border-radius: 8px;
  border: 1px solid rgba(167,139,250,0.20);
  background: transparent;
  color: var(--el-text-color-regular);
  font-size: 12px; font-weight: 500; font-family: inherit;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease, transform 0.15s ease;
}
.act-btn:not(:disabled):hover { transform: translateY(-1px); }
.act-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.act-detail:hover { background: rgba(167,139,250,0.10); color: #a78bfa; border-color: rgba(167,139,250,0.35); }
.act-dl:not(:disabled):hover { background: rgba(52,211,153,0.10); color: #10b981; border-color: rgba(52,211,153,0.30); }
.act-danger:not(:disabled):hover { background: rgba(239,68,68,0.10); color: #ef4444; border-color: rgba(239,68,68,0.30); }

/* ── Dialog util ─────────────────────────────────────────── */
.mb-3 { margin-bottom: 12px; }
.plugin-toolbar.compact { display: flex; gap: 10px; margin-bottom: 10px; align-items: center; }
.dialog-footer-flex { display: flex; align-items: center; justify-content: space-between; width: 100%; }
</style>
