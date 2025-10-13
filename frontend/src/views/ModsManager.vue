<template>
  <div class="mods-manager-layout" :class="{ 'is-collapsed': asideCollapsed, 'is-collapsing': asideCollapsing }">
    <!-- 左侧服务器列表 -->
    <div class="table-card left-panel">
      <el-card shadow="never" v-loading="serversLoading">
        <template #header>
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="text-base font-medium">Mods管理</span>
            </div>
            <div class="flex items-center gap-2">
              <el-tag type="success">模组总数：{{ totalModsCount }}</el-tag>
            </div>
          </div>
        </template>

        <el-input v-model="serverQuery" placeholder="搜索服务器" clearable class="mb-2">
          <template #prefix>
            <el-icon><Search/></el-icon>
          </template>
        </el-input>

        <el-table :data="filteredServers" size="small" stripe @row-click="handleSelectServer" row-key="id">
          <el-table-column label="服务器" min-width="160">
            <template #default="{ row }">
              <div class="flex items-center justify-between w-full">
                <div class="server-cell">
                  <div class="server-name ellipsis">{{ row.name }}</div>
                  <div class="muted ellipsis">ID: {{ row.id }}</div>
                </div>

              </div>
            </template>
          </el-table-column>
          <el-table-column label="mods数" width="80" align="center">
            <template #default="{ row }">
              <span>{{ Number(row.modsCount) || 0 }}</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <!-- 右侧主视图 -->
    <el-main class="mods-content-area">
      <div v-if="!selectedServer" class="main-placeholder">
        <el-empty description="请从左侧选择一个服务器以管理模组"/>
      </div>

      <div v-else>
        <!-- 工具栏与概览 -->
        <el-card shadow="never" class="mb-3">
          <template #header>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="text-base font-medium">{{ selectedServer.name }}</span>
                <el-tag type="info">共 {{ mods.length }} 个模组</el-tag>
              </div>
              <div class="flex items-center gap-2">
                <el-button-group>
                  <el-button type="primary" :icon="Plus" @click="openModrinthDialog" :disabled="isServerRunning">从Modrinth添加</el-button>
                  <el-button type="primary" :icon="Plus" @click="openCurseforgeDialog" :disabled="isServerRunning">从Curseforge添加</el-button>
                  <el-button type="success" :icon="Upload" @click="openUploadDialog" :disabled="isServerRunning && !isVelocity(selectedServer.value)">从本地上传</el-button>
                  <el-button type="warning" :icon="CopyDocument" @click="openCopyDialog" :disabled="isServerRunning && !isVelocity(selectedServer.value)">从其他服务器复制</el-button>
                  <el-button type="info" :icon="Refresh" @click="checkUpdates" :disabled="mods.length===0">检查更新</el-button>
                </el-button-group>
              </div>
            </div>
          </template>

          <el-descriptions :column="3" border size="small" v-if="overview">
            <el-descriptions-item label="存储根">{{ overview.storage_root }}</el-descriptions-item>
            <el-descriptions-item label="核心版本">{{ overview.mc_version || '-' }}</el-descriptions-item>
            <el-descriptions-item label="加载器">
              <span v-if="overview.loader==='未安装'">
                未安装
                <el-button size="small" type="primary" @click="goToServers">去安装</el-button>
              </span>
              <span v-else>{{ overview.loader }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="模组加载器版本">{{ overview.loader_version || '-' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>

        <!-- 模组列表 -->
        <div class="table-card">
          <el-table :data="pagedMods" v-loading="modsLoading" stripe size="small" :max-height="tableMaxHeight" style="width: 100%;">
            <el-table-column label="模组" min-width="240">
              <template #default="{ row }">
                <div class="plugin-cell-layout">
                  <el-tag v-if="(row.meta.slug || row.meta.id)" type="primary" effect="plain" size="small">{{ row.meta.slug || row.meta.id }}</el-tag>
                  <div>
                    <div class="plugin-name">{{ row.meta.name || row.file_name }}</div>
                    <el-tooltip :content="(row.meta.description || row.file_name)" placement="top-start" effect="light">
                      <div class="plugin-description ellipsis">{{ row.meta.description || row.file_name }}</div>
                    </el-tooltip>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="来源" width="120" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.meta.source" size="small">{{ row.meta.source }}</el-tag>
                <el-tag v-else size="small" type="info">未知</el-tag>
              </template>
            </el-table-column>

            <el-table-column label="模组版本" width="160" align="center">
              <template #default="{ row }">
                <div class="version-cell">
                  <el-tag size="small" type="success">{{ row.meta.version || '-' }}</el-tag>
                  <el-tooltip v-if="updatesMap.get(row.file_name)" :content="`有新版：${updatesMap.get(row.file_name)?.version || ''}`" placement="top-start" effect="light">
                    <el-button size="small" type="warning" circle plain :icon="Refresh" @click="installUpdateForMod(row)" />
                  </el-tooltip>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="支持的MC版本" min-width="140">
              <template #default="{ row }">
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
              </template>
            </el-table-column>

            <el-table-column label="状态" width="120" align="center">
              <template #default="{ row }">
                <el-switch v-model="row.enabled" @change="toggleMod(row)" :loading="row.loading" :disabled="isServerRunning"/>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="280" align="center">
              <template #default="{ row }">
                <el-button-group>
                  <el-button size="small" type="success" :icon="Download" :loading="row.loading" @click="downloadMod(row)">下载</el-button>
                  <el-button size="small" type="primary" @click="openChangeVersion(row)">更改版本</el-button>
                  <el-popconfirm title="确定删除这个模组吗？" width="220" @confirm="deleteMod(row)">
                    <template #reference>
                      <el-button size="small" type="danger" :icon="Delete" :loading="row.loading" :disabled="isServerRunning">删除</el-button>
                    </template>
                  </el-popconfirm>
                </el-button-group>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- 分页 -->
        <div class="mt-3 flex items-center justify-end">
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
    </el-main>

    <!-- 对话框：Modrinth 搜索 -->
    <el-dialog v-if="modrinthDialog.visible" v-model="modrinthDialog.visible" title="从 Modrinth 添加" width="70%" top="8vh" destroy-on-close>
      <div class="plugin-toolbar compact">
        <el-input v-model="modrinthDialog.query" placeholder="搜索：名称 / 描述" clearable style="width: 360px;" @keyup.enter="searchModrinth"/>
        <el-button type="primary" :icon="Search" @click="searchModrinth">搜索</el-button>
      </div>
      <el-table :data="modrinthDialog.items" v-loading="modrinthDialog.loading" height="50vh" stripe border row-key="project_id">
        <el-table-column label="模组" min-width="320">
          <template #default="{ row }">
            <div class="plugin-cell-layout">
              <el-tag type="primary" effect="plain" size="small">{{ row.slug }}</el-tag>
              <div>
                <div class="plugin-name">{{ row.title }}</div>
                <el-tooltip :content="row.description" placement="top-start" effect="light">
                  <div class="plugin-description ellipsis">{{ row.description }}</div>
                </el-tooltip>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="当前安装" width="140">
          <template #default="{ row }">
            <el-tag v-if="isInstalledSlug(row.slug)" size="small" type="success">已安装</el-tag>
            <el-tag v-else size="small" type="info">未安装</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="统计" width="160" align="center">
          <template #default="{ row }">
            <span>⬇ {{ abbrNumber(row.downloads) }}　★ {{ abbrNumber(row.follows) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" align="center">
          <template #default="{ row }">
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
          </template>
        </el-table-column>
      </el-table>
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
        <el-button type="primary" :loading="uploadDialog.loading" :disabled="!uploadDialog.file" @click="doUpload">开始上传</el-button>
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
import {ref, computed, onMounted} from 'vue'
import { ElMessage, ElNotification } from 'element-plus'
import { Search, Plus, Delete, Download, Upload, UploadFilled, Refresh, CopyDocument } from '@element-plus/icons-vue'
import apiClient from '@/api'
import { asideCollapsed, asideCollapsing } from '@/store/ui'
import router from '@/router'

// 左侧数据
const servers = ref([])
const serverQuery = ref('')
const serversLoading = ref(false)
const totalModsCount = ref(0)

// 右侧数据
const selectedServer = ref(null)
const mods = ref([])
const modsLoading = ref(false)
const overview = ref(null)

// 分页
const page = ref(1)
const pageSize = ref(15)

const filteredServers = computed(() => {
  if (!serverQuery.value.trim()) return servers.value
  const q = serverQuery.value.toLowerCase()
  return servers.value.filter(s => s.name?.toLowerCase().includes(q) || String(s.id).includes(q))
})

const filteredMods = computed(() => mods.value)
const pagedMods = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredMods.value.slice(start, start + pageSize.value)
})

const isVelocity = (s) => (s?.core_config?.server_type || s?.core_config?.serverType) === 'velocity'
const isServerRunning = computed(() => selectedServer.value?.status === 'running')
const tableMaxHeight = computed(() => {
  const h = window.innerHeight || 900
  return Math.max(240, h - 320)
})

const formatBytes = (bytes) => {
  const b = Number(bytes || 0)
  if (!b) return '0 B'
  const units = ['B','KB','MB','GB','TB']
  const i = Math.floor(Math.log(b) / Math.log(1024))
  return (b / Math.pow(1024, i)).toFixed(2) + ' ' + units[i]
}

const initialLoad = async () => {
  serversLoading.value = true
  try {
    const { data: serverData } = await apiClient.get('/api/servers')
    // 仅拉取 overview 以获取数量，避免耗时的 mods 列表
    const overviewTasks = serverData.map(async (server) => {
      try {
        const { data } = await apiClient.get(`/api/mods/overview/${server.id}`)
        return { srv: server, count: Number(data?.mods_amount || 0) }
      } catch (e) {
        return { srv: server, count: 0 }
      }
    })
    const results = await Promise.all(overviewTasks)
    let total = 0
    servers.value = results.map(r => { total += r.count; return { ...r.srv, modsCount: r.count } })
    totalModsCount.value = total
    // 不默认选中服务器，保持初始空白区（参考 PrimeBackup 初始）
  } catch (e) {
    ElMessage.error('加载服务器失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    serversLoading.value = false
  }
}

const handleSelectServer = async (server) => {
  await selectServer(server)
}

const selectServer = async (server) => {
  selectedServer.value = server
  page.value = 1
  await fetchMods()
  await fetchOverview()
}

const fetchMods = async () => {
  if (!selectedServer.value) return
  modsLoading.value = true
  try {
    const { data } = await apiClient.get(`/api/mods/server/${selectedServer.value.id}`)
    mods.value = (data?.data || []).map(x => ({ ...x, loading: false }))
    // 从 DB 元数据中恢复更新提示
    updatesMap.clear()
    mods.value.forEach(m => {
      const meta = m.meta || {}
      if (meta.modrinth_update_available && (meta.modrinth_latest_version_number || meta.modrinth_latest_version_id)) {
        updatesMap.set(m.file_name, { version: meta.modrinth_latest_version_number, version_id: meta.modrinth_latest_version_id })
      }
    })
  } catch (e) {
    ElMessage.error('加载模组失败: ' + (e.response?.data?.detail || e.message))
    mods.value = []
  } finally {
    modsLoading.value = false
  }
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
    const res = await apiClient.get(`/api/mods/download/${selectedServer.value.id}/${row.file_name}`, { responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', row.file_name)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
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
    ElMessage.error('搜索失败: ' + (e.response?.data?.detail || e.message))
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
  uploadDialog.value.loading = true
  try {
    const form = new FormData()
    form.append('file', uploadDialog.value.file)
    await apiClient.post(`/api/mods/upload/${selectedServer.value.id}`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
    ElMessage.success('上传成功')
    uploadDialog.value.visible = false
    await fetchMods()
  } catch (e) {
    ElMessage.error('上传失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    uploadDialog.value.loading = false
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

onMounted(initialLoad)
</script>

<style scoped>
.mods-manager-layout { display: flex; gap: 12px; height: calc(100vh - 64px); overflow: hidden; }
.left-panel { width: 280px; max-width: 280px; flex-shrink: 0; align-self: flex-start; transition: width 0.32s cubic-bezier(.34,1.56,.64,1); will-change: width; overflow-x: hidden; overflow-y: auto; }
.is-collapsed .left-panel, .is-collapsing .left-panel { width: 0 !important; }
.is-collapsing .left-panel :deep(.el-card__body), .is-collapsing .left-panel :deep(.el-card__header) { display: none !important; }
.mods-content-area { padding: 0 20px 20px; flex: 1 1 auto; min-height: 0; overflow-y: auto; overflow-x: hidden; scrollbar-width: none; -ms-overflow-style: none; }
.mods-content-area::-webkit-scrollbar { width: 0; height: 0; }
.main-placeholder { display: flex; justify-content: center; align-items: center; height: 100%; }

.mb-3 { margin-bottom: 12px; }
.mt-3 { margin-top: 12px; }
.flex { display: flex; }
.items-center { align-items: center; }
.justify-between { justify-content: space-between; }
.justify-end { justify-content: flex-end; }
.gap-2 { gap: 8px; }
.plugin-cell-layout { display: flex; align-items: flex-start; gap: 8px; }
.plugin-name { font-weight: 500; line-height: 1.2; }
.plugin-description { font-size: 12px; color: #909399; line-height: 1.3; max-width: 520px; }
.ellipsis { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ellipsis-tags { display: inline-flex; align-items: center; }
.server-name { font-weight: 500; }
.muted { font-size: 12px; color: #909399; }

/* 左侧面板内部元素宽度与溢出控制，避免横向滚动 */
.left-panel :deep(.el-card) { display: block; }
.left-panel :deep(.el-card__body) { padding: 8px; }
.left-panel :deep(.el-input),
.left-panel :deep(.el-input__wrapper) { width: 100%; }
.left-panel :deep(.el-table),
.left-panel :deep(.el-table__inner-wrapper) { width: 100%; }
.left-panel :deep(.el-scrollbar__wrap) { overflow-x: hidden !important; }

/* 对话框底部布局：左下角兼容开关，右下角分页 */
.dialog-footer-flex { display: flex; align-items: center; justify-content: space-between; width: 100%; }
.plugin-toolbar.compact { display: flex; gap: 10px; margin-bottom: 10px; align-items: center; }
</style>

