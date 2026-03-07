<template>
  <div class="mcdr-page">

    <!-- Glass toolbar -->
    <div class="mcdr-toolbar">
      <div class="mcdr-toolbar-left">
        <span class="mcdr-title">MCDR 插件市场</span>
        <el-tag type="info" v-if="stats.total" size="small">共 {{ stats.total }} 个</el-tag>
        <el-tag type="success" v-if="stats.updatedAt" size="small">{{ stats.updatedAt }}</el-tag>
        <div class="toolbar-divider" />
        <div class="search-wrap">
          <el-input v-model="query" placeholder="搜索：名称 / ID / 作者 / 标签 / 描述" clearable class="search-input" @input="handleSearch">
            <template #prefix><el-icon style="color:var(--brand-primary)"><Search /></el-icon></template>
          </el-input>
        </div>
        <el-select v-model="selectedLabels" multiple collapse-tags collapse-tags-tooltip placeholder="标签筛选" class="labels-select">
          <el-option v-for="l in allLabels" :key="l" :label="l" :value="l"/>
        </el-select>
        <el-select v-model="sortBy" placeholder="排序" class="sort-select">
          <el-option label="最新发布" value="latestDate"/>
          <el-option label="下载最多" value="downloads"/>
          <el-option label="Star 最多" value="stars"/>
          <el-option label="名称" value="name"/>
        </el-select>
        <div class="check-group">
          <el-checkbox v-model="showPrerelease" size="small">预发布</el-checkbox>
          <el-checkbox v-model="hideArchived" size="small">隐藏归档</el-checkbox>
        </div>
      </div>
      <div class="mcdr-toolbar-right">
        <template v-if="filtered.length > pageSize">
          <div class="page-nav">
            <button class="page-btn" :disabled="page <= 1" @click="page--">
              <el-icon :size="12"><ArrowLeft /></el-icon>
            </button>
            <span class="page-indicator">{{ page }}<span class="page-sep">/</span>{{ Math.ceil(filtered.length / pageSize) }}</span>
            <button class="page-btn" :disabled="page >= Math.ceil(filtered.length / pageSize)" @click="page++">
              <el-icon :size="12"><ArrowRight /></el-icon>
            </button>
          </div>
          <div class="toolbar-divider" />
        </template>
        <button class="btn-refresh" :class="{ 'is-loading': loading }" @click="load">
          <el-icon :size="13"><Refresh /></el-icon>
          <span>刷新</span>
        </button>
      </div>
    </div>

    <!-- Glass card -->
    <div class="mcdr-glass-card">
      <div class="shimmer-line" aria-hidden="true" />

      <!-- Table -->
      <div class="mcdr-table-wrap" v-loading="loading" element-loading-background="transparent">
        <table class="native-table">
          <colgroup>
            <col style="min-width:280px" />
            <col style="width:130px" />
            <col style="min-width:160px" />
            <col style="width:170px" />
            <col style="width:230px" />
          </colgroup>
          <thead>
            <tr class="thead-row">
              <th class="th-cell">插件</th>
              <th class="th-cell">最新版本</th>
              <th class="th-cell">作者</th>
              <th class="th-cell th-center">统计</th>
              <th class="th-cell th-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!loading && paged.length === 0">
              <td colspan="5" class="td-empty">
                <el-empty description="暂无插件" :image-size="80" />
              </td>
            </tr>
            <tr v-for="row in paged" :key="row.meta.id" class="tbl-row" @dblclick="openDetail(row)">
              <td class="td-cell">
                <PluginNameCell
                  :id="row.meta.id"
                  :name="row.meta.name"
                  :description="row.meta.description?.zh_cn || row.meta.description?.en_us"
                />
              </td>
              <td class="td-cell">
                <el-tag size="small" :type="row.latest?.prerelease ? 'warning' : 'success'">
                  {{ row.release?.latest_version || '-' }}
                </el-tag>
              </td>
              <td class="td-cell">
                <AuthorTagsCell :authors="row.meta?.authors" />
              </td>
              <td class="td-cell td-center">
                <div class="stats-cell">
                  <el-tooltip content="Repo Stars">
                    <span class="stat-chip stat-star">
                      <el-icon :size="11"><Star /></el-icon>
                      {{ row.repository?.stargazers_count ?? 0 }}
                    </span>
                  </el-tooltip>
                  <el-tooltip content="下载量">
                    <span class="stat-chip stat-dl">
                      <el-icon :size="11"><Download /></el-icon>
                      {{ row.latest?.asset?.download_count ?? 0 }}
                    </span>
                  </el-tooltip>
                </div>
              </td>
              <td class="td-cell td-right">
                <div class="row-actions">
                  <button class="act-btn act-detail" @click="openDetail(row)">详情</button>
                  <button class="act-btn act-dl" :disabled="!row.latest?.asset?.browser_download_url" @click="go(row.latest?.asset?.browser_download_url)">下载</button>
                  <button class="act-btn act-install" @click="handleInstallClick(row, row.latest)">
                    <el-icon :size="12"><Upload /></el-icon>安装
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Detail Drawer -->
    <el-drawer v-model="detailVisible" size="50%" direction="rtl" :destroy-on-close="true" append-to-body class="mcdr-detail-drawer">
      <template #header>
        <div class="drw-header">
          <div class="drw-header-shimmer" aria-hidden="true" />
          <div class="drw-header-body">
            <div class="drw-header-icon">
              <el-icon :size="18"><Coin /></el-icon>
            </div>
            <div class="drw-title-group">
              <div class="drw-title">{{ detail?.meta?.name }}</div>
              <div class="drw-subtitle">
                <span class="drw-id">{{ detail?.meta?.id }}</span>
                <el-tag size="small" :type="detail?.latest?.prerelease ? 'warning' : 'success'" effect="light">
                  {{ detail?.release?.latest_version }}
                </el-tag>
                <el-tag v-if="detail?.repository?.archived" size="small" type="danger" effect="light">Archived</el-tag>
              </div>
            </div>
          </div>
        </div>
      </template>

      <div class="drw-body">
        <!-- Meta info card -->
        <div class="drw-card">
          <div class="drw-info-grid">
            <div class="drw-info-row">
              <span class="drw-info-label">Repo</span>
              <span class="drw-info-value">
                <a v-if="detail?.repository?.html_url" :href="detail?.repository?.html_url" target="_blank" class="drw-link">
                  {{ detail?.repository?.full_name }}
                </a>
                <span v-else class="drw-none">—</span>
              </span>
            </div>
            <div class="drw-info-row" v-if="(detail?.repository?.stargazers_count ?? 0) > 0 || (detail?.latest?.asset?.download_count ?? 0) > 0">
              <span class="drw-info-label">统计</span>
              <span class="drw-info-value drw-stats">
                <span class="stat-chip stat-star">
                  <el-icon :size="11"><Star /></el-icon>
                  {{ detail?.repository?.stargazers_count ?? 0 }}
                </span>
                <span class="stat-chip stat-dl">
                  <el-icon :size="11"><Download /></el-icon>
                  {{ detail?.latest?.asset?.download_count ?? 0 }}
                </span>
              </span>
            </div>
            <div class="drw-info-row" v-if="(detail?.plugin?.labels || []).length > 0">
              <span class="drw-info-label">标签</span>
              <span class="drw-info-value drw-tags">
                <el-tag v-for="t in detail?.plugin?.labels || []" :key="t" size="small" effect="plain">{{ t }}</el-tag>
              </span>
            </div>
            <div class="drw-info-row" v-if="(detail?.meta?.authors || []).length > 0">
              <span class="drw-info-label">作者</span>
              <span class="drw-info-value drw-tags">
                <el-tag v-for="a in detail?.meta?.authors || []" :key="a" size="small" type="primary" effect="light">{{ a }}</el-tag>
              </span>
            </div>
          </div>
        </div>

        <!-- Introduction -->
        <div class="drw-section">
          <div class="drw-section-title">
            <span class="drw-section-dot" />简介
          </div>
          <div class="drw-intro">
            {{ detail?.plugin?.introduction?.zh_cn || detail?.plugin?.introduction?.en_us || detail?.meta?.description?.zh_cn || detail?.meta?.description?.en_us || '暂无介绍' }}
          </div>
        </div>

        <!-- Dependencies -->
        <template v-if="hasDependenciesInDetail">
          <div class="drw-section">
            <div class="drw-section-title">
              <span class="drw-section-dot drw-section-dot--purple" />依赖信息
              <span class="drw-section-badge">最新版本</span>
            </div>
            <div class="drw-card drw-card--deps">
              <div class="drw-info-row" v-if="detail?.latest?.meta?.dependencies">
                <span class="drw-info-label">插件依赖</span>
                <span class="drw-info-value drw-tags">
                  <template v-if="Object.keys(detail?.latest?.meta?.dependencies || {}).length > 0">
                    <el-tag v-for="(version, name) in (detail?.latest?.meta?.dependencies || {})" :key="name"
                            size="small" type="primary" effect="dark">{{ name }}: {{ version }}</el-tag>
                  </template>
                  <span v-else class="drw-none">无</span>
                </span>
              </div>
              <div class="drw-info-row" v-if="detail?.latest?.meta?.requirements">
                <span class="drw-info-label">Python 库</span>
                <span class="drw-info-value drw-tags">
                  <template v-if="(detail?.latest?.meta?.requirements || []).length > 0">
                    <el-tag v-for="req in (detail?.latest?.meta?.requirements || [])" :key="req"
                            size="small" type="success" effect="plain">{{ req }}</el-tag>
                  </template>
                  <span v-else class="drw-none">无</span>
                </span>
              </div>
            </div>
          </div>
        </template>

        <!-- Release history -->
        <div class="drw-section">
          <div class="drw-section-title">
            <span class="drw-section-dot drw-section-dot--green" />发布历史
            <span class="drw-section-badge">最多 10 条</span>
          </div>
          <div class="drw-timeline">
            <div v-for="(r, idx) in (detail?.release?.releases || []).slice(0, 10)" :key="idx" class="drw-release-card">
              <div class="drw-release-dot" :class="r.prerelease ? 'drw-release-dot--warn' : 'drw-release-dot--ok'" />
              <div class="drw-release-body">
                <div class="drw-release-head">
                  <div class="drw-release-name">
                    {{ r.name || r.tag_name }}
                    <el-tag v-if="r.prerelease" size="small" type="warning" effect="plain" class="drw-pre-tag">预发布</el-tag>
                  </div>
                  <div class="drw-release-actions">
                    <button v-if="r.asset?.browser_download_url" class="act-btn act-dl" @click="go(r.asset?.browser_download_url)">
                      <el-icon :size="11"><Download /></el-icon>下载
                    </button>
                    <button v-if="r.url" class="act-btn act-detail" @click="go(r.url)">发布页</button>
                    <button class="act-btn act-install" @click="detail && handleInstallClick(detail, r)">
                      <el-icon :size="11"><Upload /></el-icon>安装
                    </button>
                  </div>
                </div>
                <div class="drw-release-meta">
                  <span class="drw-release-time">{{ formatDate(r.created_at) }}</span>
                  <span v-if="r.description" class="drw-release-desc">{{ r.description }}</span>
                </div>
              </div>
            </div>
            <div v-if="!(detail?.release?.releases || []).length" class="drw-empty">暂无发布记录</div>
          </div>
        </div>
      </div>
    </el-drawer>

    <!-- Install Dialog -->
    <el-dialog v-model="installDialogVisible" width="560px" destroy-on-close append-to-body
               class="mcdr-action-dialog" :show-close="false">
      <template #header>
        <div class="adlg-head">
          <div class="adlg-icon adlg-icon--install">
            <el-icon :size="17"><Upload /></el-icon>
          </div>
          <div class="adlg-title-group">
            <span class="adlg-title">安装插件到服务器</span>
            <span class="adlg-subtitle" v-if="pluginToInstallInfo.plugin">
              {{ pluginToInstallInfo.plugin.meta.name }}
              <span class="adlg-version">{{ pluginToInstallInfo.versionTag }}</span>
            </span>
          </div>
          <button class="adlg-close-btn" @click="installDialogVisible = false">
            <el-icon :size="13"><Close /></el-icon>
          </button>
        </div>
      </template>

      <div v-if="pluginToInstallInfo.plugin" class="adlg-body">
        <!-- Plugin info card -->
        <div class="adlg-info-card">
          <div class="adlg-info-row" v-if="pluginToInstallInfo.dependencies.length > 0">
            <span class="adlg-info-label">插件依赖</span>
            <div class="adlg-info-tags">
              <el-tag v-for="dep in pluginToInstallInfo.dependencies" :key="dep" size="small" type="primary" effect="dark">{{ dep }}</el-tag>
            </div>
          </div>
          <div class="adlg-info-row" v-if="pluginToInstallInfo.requirements.length > 0">
            <span class="adlg-info-label">Python 库</span>
            <div class="adlg-info-tags">
              <el-tag v-for="req in pluginToInstallInfo.requirements" :key="req" size="small" type="success" effect="plain">{{ req }}</el-tag>
            </div>
          </div>
          <div v-if="pluginToInstallInfo.dependencies.length === 0 && pluginToInstallInfo.requirements.length === 0" class="adlg-no-deps">
            无额外依赖
          </div>
        </div>

        <!-- Server select -->
        <div class="adlg-section-label">选择目标服务器</div>
        <el-select v-model="selectedServers" multiple filterable placeholder="请选择服务器"
                   style="width:100%" :loading="isFetchingServerPlugins">
          <el-option v-for="server in servers" :key="server.id" :label="server.name" :value="server.id">
            <div class="adlg-server-opt">
              <span>{{ server.name }}</span>
              <el-tag size="small" :type="getPluginStatusForServer(server, pluginToInstallInfo.plugin.meta.id).type" effect="light">
                {{ getPluginStatusForServer(server, pluginToInstallInfo.plugin.meta.id).text }}
              </el-tag>
            </div>
          </el-option>
        </el-select>
      </div>

      <template #footer>
        <div class="adlg-footer">
          <button class="adlg-btn-ghost" @click="installDialogVisible = false">取消</button>
          <button class="adlg-btn-primary" :disabled="isInstalling || selectedServers.length === 0" @click="confirmInstall">
            <el-icon v-if="isInstalling" class="is-loading" :size="13"><Refresh /></el-icon>
            <el-icon v-else :size="13"><Upload /></el-icon>
            {{ isInstalling ? '安装中…' : '确认安装' }}
          </button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, onMounted, watch } from 'vue'
import {ElMessage, ElNotification} from 'element-plus'
import {Search, Star, Download, Upload, Refresh, ArrowLeft, ArrowRight, Coin, Close} from '@element-plus/icons-vue'
import apiClient, { isRequestCanceled } from '@/api'
import PluginNameCell from '@/components/PluginNameCell.vue'
import AuthorTagsCell from '@/components/AuthorTagsCell.vue'
import { useTasksStore } from '@/store/tasks'
const { fetchTasks } = useTasksStore()

// --- Interfaces ---
interface Asset {
  id?: number;
  name?: string;
  size?: number;
  download_count?: number;
  created_at?: string;
  browser_download_url?: string
}

interface Meta {
  schema_version?: number;
  id: string;
  name: string;
  version?: string;
  link?: string | null;
  authors?: string[];
  dependencies?: Record<string, string>;
  requirements?: string[];
  description?: Record<string, string>
}

interface ReleaseItem {
  url?: string;
  name?: string;
  tag_name?: string;
  created_at?: string;
  description?: string | null;
  prerelease?: boolean;
  asset?: Asset;
  meta?: Meta
}

interface ReleaseBlock {
  schema_version?: number;
  id?: string;
  latest_version?: string;
  latest_version_index?: number;
  releases?: ReleaseItem[]
}

interface Repository {
  url?: string;
  name?: string;
  full_name?: string;
  html_url?: string;
  description?: string | null;
  archived?: boolean;
  stargazers_count?: number;
  watchers_count?: number;
  forks_count?: number;
  readme?: string | null;
  readme_url?: string | null;
  license?: any
}

interface PluginBlock {
  schema_version?: number;
  id?: string;
  authors?: string[];
  repository?: string;
  branch?: string;
  related_path?: string;
  labels?: string[];
  introduction?: Record<string, string>;
  introduction_urls?: Record<string, string>
}

interface PluginEntry {
  meta: Meta;
  plugin?: PluginBlock;
  release?: ReleaseBlock;
  repository?: Repository;
  latest?: ReleaseItem | null
  // cached lowercase text for fast client-side search
  searchText?: string
}

// [!code block start]
// Local plugin info from /api/plugins/server/{id}
interface LocalPluginInfo {
  file_name: string;
  enabled: boolean;
  meta: {
    id: string;
    version: string;
  };
}

// Server info from /api/servers
interface ServerInfo {
  id: number;
  name: string;
  // plugins property is removed as it's now fetched dynamically
}

// [!code block end]

// --- Component State ---
const loading = ref(false)
const error = ref<string | null>(null)
const items = ref<PluginEntry[]>([])
const servers = ref<ServerInfo[]>([])

// Filtering and Sorting
const query = ref('')
const selectedLabels = ref<string[]>([])
const sortBy = ref<'latestDate' | 'downloads' | 'stars' | 'name'>('downloads')
const showPrerelease = ref(false)
const hideArchived = ref(true)

// Pagination
const page = ref(1)
const pageSize = ref(20)

watch([selectedLabels, sortBy, showPrerelease, hideArchived], () => {
  page.value = 1
})

// Stats
const stats = ref({total: 0, updatedAt: ''})

// Detail Drawer State
const detailVisible = ref(false)
const detail = ref<PluginEntry | null>(null)

// Installation Dialog State
const installDialogVisible = ref(false)
const pluginToInstall = ref<{ plugin: PluginEntry; release: ReleaseItem } | null>(null)
const selectedServers = ref<number[]>([])
const isInstalling = ref(false)

// [!code block start]
// New state for dynamically fetched server plugins
const serverPlugins = ref(new Map<number, LocalPluginInfo[]>());
const isFetchingServerPlugins = ref(false);
// [!code block end]

// --- Computed Properties ---
const allLabels = computed(() => {
  const s = new Set<string>()
  items.value.forEach(i => (i.plugin?.labels || []).forEach(l => s.add(l)))
  return Array.from(s).sort()
})

const baseList = computed(() => {
  let result = items.value
  if (!showPrerelease.value) {
    result = result.filter(i => !(i.latest?.prerelease))
  }
  if (hideArchived.value) {
    result = result.filter(i => !i.repository?.archived)
  }
  return result
})

const sortedBase = computed(() => {
  const result = [...baseList.value]
  result.sort((a, b) => {
    if (sortBy.value === 'name') return (a.meta.name || a.meta.id).localeCompare(b.meta.name || b.meta.id)
    if (sortBy.value === 'stars') return (b.repository?.stargazers_count ?? 0) - (a.repository?.stargazers_count ?? 0)
    if (sortBy.value === 'downloads') return (b.latest?.asset?.download_count ?? 0) - (a.latest?.asset?.download_count ?? 0)
    const da = a.latest?.created_at ? new Date(a.latest.created_at).getTime() : 0
    const db = b.latest?.created_at ? new Date(b.latest.created_at).getTime() : 0
    return db - da
  })
  return result
})

const filtered = computed(() => {
  let result = sortedBase.value
  const q = query.value.trim().toLowerCase()
  if (q) {
    result = result.filter(i => (i.searchText || '').includes(q))
  }
  if (selectedLabels.value.length) {
    result = result.filter(i => selectedLabels.value.every(l => (i.plugin?.labels || []).includes(l)))
  }
  return result
})

const paged = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filtered.value.slice(start, start + pageSize.value)
})

const hasDependenciesInDetail = computed(() => {
  const meta = detail.value?.latest?.meta
  return !!(meta?.dependencies || meta?.requirements)
})

const pluginToInstallInfo = computed(() => {
  if (!pluginToInstall.value) {
    return {plugin: null, versionTag: '', dependencies: [], requirements: []}
  }
  const {plugin, release} = pluginToInstall.value;
  const meta = release.meta;

  const dependencies = meta?.dependencies ? Object.entries(meta.dependencies).map(([name, version]) => `${name}: ${version}`) : [];
  const requirements = meta?.requirements || [];

  const displayVersion = release.meta?.version || plugin.release?.latest_version || release.tag_name || '未知';

  return {
    plugin,
    versionTag: displayVersion,
    dependencies,
    requirements
  };
});


// --- Methods ---
function getAuthHeaders() {
  const token = localStorage.getItem('token');
  const headers = new Headers({'Accept': 'application/json'});
  if (token) {
    headers.append('Authorization', `Bearer ${token}`);
  }
  return headers;
}

function joinRecordValues(record?: Record<string, string> | null): string {
  if (!record) return ''
  return Object.values(record).filter(Boolean).join(' ')
}

function buildSearchText(entry: PluginEntry): string {
  const parts = [
    entry.meta?.id,
    entry.meta?.name,
    (entry.meta?.authors || []).join(' '),
    (entry.plugin?.labels || []).join(' '),
    joinRecordValues(entry.meta?.description),
    joinRecordValues(entry.plugin?.introduction),
    entry.repository?.full_name,
  ]

  return parts.filter(Boolean).join(' ').toLowerCase()
}

function normalize(data: any): PluginEntry[] {
  const map = data?.plugins || {}
  return Object.keys(map).map((k: string) => {
    const p = map[k]
    const latest = p?.release?.releases?.[0] ?? null
    const entry: PluginEntry = {meta: p.meta, plugin: p.plugin, release: p.release, repository: p.repository, latest}
    entry.searchText = buildSearchText(entry)
    return entry
  })
}

function formatDate(d?: string) {
  if (!d) return '-'
  return new Date(d).toLocaleString()
}

function openDetail(row: PluginEntry) {
  detail.value = row
  detailVisible.value = true
}

function go(url?: string) {
  if (url) window.open(url, '_blank')
}

// [!code block start]
async function handleInstallClick(plugin: PluginEntry, release: ReleaseItem | null) {
  if (!release || !release.asset) {
    ElMessage.warning('没有可供安装的版本');
    return;
  }
  pluginToInstall.value = {plugin, release};
  selectedServers.value = [];

  try {
    // Fetch server plugin info before showing the dialog
    await fetchAllServerPlugins();
    installDialogVisible.value = true;
  } catch (error) {
    ElMessage.error('获取服务器插件信息失败');
    console.error(error);
  }
}

async function fetchAllServerPlugins() {
  isFetchingServerPlugins.value = true;
  serverPlugins.value.clear();

  const promises = servers.value.map(async (server) => {
    try {
      const res = await fetch(`/api/plugins/server/${server.id}`, {headers: getAuthHeaders()});
      if (!res.ok) throw new Error(`Failed to fetch plugins for server ${server.name}`);
      const data = await res.json();
      serverPlugins.value.set(server.id, data.data || []);
    } catch (e) {
      console.warn(`Could not load plugins for server ${server.name}:`, e);
      serverPlugins.value.set(server.id, []); // Set empty on error to avoid breaking UI
    }
  });

  try {
    await Promise.all(promises);
  } finally {
    isFetchingServerPlugins.value = false;
  }
}

function getPluginStatusForServer(server: ServerInfo, pluginId: string): {
  text: string;
  type: 'success' | 'info' | 'warning'
} {
  const installedList = serverPlugins.value.get(server.id);

  if (isFetchingServerPlugins.value || installedList === undefined) {
    return {text: '加载中...', type: 'info'};
  }

  const installedPlugin = installedList.find(p => p.meta.id === pluginId);
  if (installedPlugin) {
    return {text: `已安装 (${installedPlugin.meta.version})`, type: 'success'};
  }
  return {text: '未安装', type: 'info'};
}

// [!code block end]


async function confirmInstall() {
  if (selectedServers.value.length === 0) {
    ElMessage.warning('请至少选择一个服务器');
    return;
  }
  if (!pluginToInstall.value) return;
  isInstalling.value = true;
  const {plugin, release} = pluginToInstall.value;
  const pluginId = plugin.meta.id;

  const versionForApi = release.meta?.version || plugin.release?.latest_version || release.tag_name || 'latest';
  const installPromises = selectedServers.value.map(serverId => {
    const serverName = servers.value.find(s => s.id === serverId)?.name || `ID: ${serverId}`;
    const url = `/api/plugins/server/${serverId}/install/from-online?plugin_id=${encodeURIComponent(pluginId)}&tag_name=${encodeURIComponent(versionForApi)}`;

    return fetch(url, {method: 'POST', headers: getAuthHeaders()})
        .then(res => {
          if (res.status !== 202) {
            return res.text().then(text => Promise.reject(new Error(`[${serverName}] 安装请求失败: ${text || res.statusText}`)));
          }
          return {serverName, status: 'fulfilled'};
        })
        .catch(err => ({serverName, status: 'rejected', reason: err.message}));
  });
  const results = await Promise.allSettled(installPromises);
  results.forEach(result => {
    if (result.status === 'fulfilled' && result.value.status === 'fulfilled') {
      ElNotification({
        title: '请求已接受',
        message: `已为服务器 [${result.value.serverName}] 创建安装任务，请稍后查看状态。`,
        type: 'success',
      });
    } else {
      const reason = result.status === 'rejected' ? result.reason : (result.value as any).reason;
      ElNotification({
        title: '安装请求失败',
        message: String(reason),
        type: 'error',
      });
    }
  });
  isInstalling.value = false;
  installDialogVisible.value = false;
  fetchTasks().catch(() => {});
}

async function fetchServers() {
  try {
    const res = await apiClient.get('/api/servers');
    servers.value = res.data;
  } catch (e: any) {
    if (!isRequestCanceled(e)) ElMessage.error(`加载服务器列表失败: ${e.message || String(e)}`);
  }
}

async function load() {
  loading.value = true
  error.value = null
  try {
    const res = await apiClient.get('/api/plugins/mcdr/versions');
    const data = res.data
    items.value = normalize(data)
    stats.value.total = items.value.length
    stats.value.updatedAt = new Date().toLocaleString()
    page.value = 1
  } catch (e: any) {
    if (isRequestCanceled(e)) return;
    error.value = e?.message || String(e)
    ElMessage.error(`加载失败：${error.value}`)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
}

onMounted(() => {
  load();
  fetchServers();
});
</script>


<style scoped>
/* ── Page layout ──────────────────────────────────────────── */
.mcdr-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: calc(100vh - var(--el-header-height) - 48px);
  overflow: hidden;
  min-height: 0;
}

/* ── Glass toolbar ───────────────────────────────────────── */
.mcdr-toolbar {
  font-family: 'Lexend', -apple-system, sans-serif;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 18px;
  background: rgba(255, 255, 255, 0.62);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(119, 181, 254, 0.18);
  border-radius: 20px;
  box-shadow: 0 4px 24px rgba(119, 181, 254, 0.10), inset 0 1px 0 rgba(255, 255, 255, 0.85);
  flex-shrink: 0;
  transition: box-shadow 0.3s ease, border-color 0.3s ease;
}
.mcdr-toolbar:hover {
  border-color: rgba(119, 181, 254, 0.28);
  box-shadow: 0 6px 32px rgba(119, 181, 254, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.85);
}
:global(.dark) .mcdr-toolbar {
  background: rgba(15, 23, 42, 0.68);
  border-color: rgba(119, 181, 254, 0.12);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.mcdr-toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1 1 auto;
  min-width: 0;
  flex-wrap: wrap;
}
.mcdr-toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.mcdr-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--color-text);
  flex-shrink: 0;
  white-space: nowrap;
}
.toolbar-divider {
  width: 1px; height: 20px;
  background: linear-gradient(180deg, transparent, rgba(119,181,254,0.35), transparent);
  flex-shrink: 0;
}
.search-wrap { flex: 1 1 auto; min-width: 180px; max-width: 280px; }
.search-input :deep(.el-input__wrapper) {
  border-radius: 22px !important;
  background: rgba(255,255,255,0.60) !important;
  border: 1px solid rgba(119,181,254,0.22) !important;
  box-shadow: none !important;
  transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}
.search-input :deep(.el-input__wrapper:hover) { border-color: rgba(119,181,254,0.42) !important; }
.search-input :deep(.el-input__wrapper.is-focus) {
  border-color: rgba(119,181,254,0.60) !important;
  box-shadow: 0 0 0 3px rgba(119,181,254,0.12) !important;
}
:global(.dark) .search-input :deep(.el-input__wrapper) {
  background: rgba(15,23,42,0.60) !important;
  border-color: rgba(119,181,254,0.18) !important;
}
.labels-select { width: 160px; flex-shrink: 0; }
.sort-select { width: 110px; flex-shrink: 0; }
.check-group { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }

.btn-refresh {
  display: inline-flex; align-items: center; gap: 6px;
  height: 34px; padding: 0 14px; border-radius: 22px;
  border: 1px solid rgba(119,181,254,0.28);
  background: rgba(119,181,254,0.08);
  color: var(--brand-primary); font-size: 12px; font-weight: 600;
  font-family: inherit; cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease, transform 0.18s ease;
}
.btn-refresh:hover { background: rgba(119,181,254,0.16); border-color: rgba(119,181,254,0.50); transform: translateY(-1px); }

/* ── Glass card ──────────────────────────────────────────── */
.mcdr-glass-card {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.58);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(119, 181, 254, 0.18);
  box-shadow: 0 4px 32px rgba(119, 181, 254, 0.10), inset 0 1px 0 rgba(255, 255, 255, 0.80);
  overflow: hidden;
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
}
.mcdr-glass-card:hover {
  border-color: rgba(119, 181, 254, 0.28);
  box-shadow: 0 8px 40px rgba(119, 181, 254, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.80);
}
:global(.dark) .mcdr-glass-card {
  background: rgba(15, 23, 42, 0.65);
  border-color: rgba(119, 181, 254, 0.12);
  box-shadow: 0 4px 32px rgba(0, 0, 0, 0.40), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.shimmer-line {
  height: 3px;
  flex-shrink: 0;
  background: linear-gradient(90deg, transparent, rgba(119,181,254,0.7), rgba(239,183,186,0.6), rgba(167,139,250,0.5), transparent);
  background-size: 200% 100%;
  animation: shimmer-slide 4s linear infinite;
  border-radius: 3px 3px 0 0;
  pointer-events: none;
}
@keyframes shimmer-slide {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.mcdr-table-wrap {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
}
/* ── Compact page navigation ─────────────────────────────── */
.page-nav { display: inline-flex; align-items: center; gap: 4px; flex-shrink: 0; }
.page-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; border-radius: 9px;
  border: 1px solid rgba(119,181,254,0.22);
  background: rgba(119,181,254,0.06);
  color: var(--el-text-color-secondary);
  cursor: pointer;
  transition: background 0.18s ease, color 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
  flex-shrink: 0;
}
.page-btn:not(:disabled):hover {
  background: rgba(119,181,254,0.14); border-color: rgba(119,181,254,0.45);
  color: var(--brand-primary); transform: scale(1.08);
}
.page-btn:disabled { opacity: 0.32; cursor: not-allowed; }
:global(.dark) .page-btn { border-color: rgba(119,181,254,0.16); background: rgba(119,181,254,0.04); }
.page-indicator {
  font-size: 12px; font-weight: 700; color: var(--el-text-color-regular);
  font-variant-numeric: tabular-nums; min-width: 36px; text-align: center; user-select: none;
}
.page-sep { color: var(--el-text-color-placeholder); margin: 0 1px; font-weight: 400; }

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
  border-bottom: 1px solid rgba(119, 181, 254, 0.12);
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
  border-bottom: 1px solid rgba(119, 181, 254, 0.07);
  transition: background 0.12s ease;
  cursor: default;
}
.tbl-row:last-child { border-bottom: none; }
.tbl-row:hover { background: rgba(119, 181, 254, 0.05); }
.td-cell {
  padding: 12px 12px;
  vertical-align: middle;
}
.td-center { text-align: center; }
.td-right  { text-align: right; padding-right: 16px; }
.td-empty  { text-align: center; padding: 48px 0; }

/* ── Table cell styles ──────────────────────────────────── */
.stats-cell { display: inline-flex; align-items: center; gap: 6px; }
.stat-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 999px;
  font-size: 12px; font-weight: 600;
  white-space: nowrap;
}
.stat-star { background: rgba(245,158,11,0.10); color: #f59e0b; border: 1px solid rgba(245,158,11,0.22); }
.stat-dl   { background: rgba(119,181,254,0.10); color: var(--brand-primary); border: 1px solid rgba(119,181,254,0.22); }

/* ── Row action buttons ──────────────────────────────────── */
.row-actions { display: inline-flex; align-items: center; gap: 4px; }
.act-btn {
  display: inline-flex; align-items: center; gap: 4px;
  height: 26px; padding: 0 10px; border-radius: 8px;
  border: 1px solid rgba(119,181,254,0.20);
  background: transparent;
  color: var(--el-text-color-regular);
  font-size: 12px; font-weight: 500; font-family: inherit;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease, transform 0.15s ease;
}
.act-btn:not(:disabled):hover { transform: translateY(-1px); }
.act-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.act-detail:hover { background: rgba(119,181,254,0.10); color: var(--brand-primary); border-color: rgba(119,181,254,0.35); }
.act-dl:not(:disabled):hover { background: rgba(52,211,153,0.10); color: #10b981; border-color: rgba(52,211,153,0.30); }
.act-install { background: linear-gradient(135deg, var(--brand-primary), #a78bfa); color: #fff; border-color: transparent; }
.act-install:hover { box-shadow: 0 4px 12px rgba(119,181,254,0.40); transform: translateY(-1px); }

/* ── Utility classes used in drawer/dialog ───────────────── */
.flex { display: flex; }
.items-center { align-items: center; }
.items-start { align-items: flex-start; }
.justify-between { justify-content: space-between; }
.gap-2 { gap: 8px; }
.mt-4 { margin-top: 16px; }
.mb-2 { margin-bottom: 8px; }
.font-medium { font-weight: 500; }
.text-base { font-size: 14px; }
.text-sm { font-size: 13px; }
.text-xs { font-size: 12px; }
.leading-5 { line-height: 20px; }
.leading-4 { line-height: 16px; }
.leading-6 { line-height: 24px; }
.w-full { width: 100%; }
.whitespace-pre-wrap { white-space: pre-wrap; }
.text-gray-500 { color: #909399; }
.text-gray-700 { color: #606266; }

/* ── Action Dialog (install) ─────────────────────────────── */
:global(.mcdr-action-dialog) {
  border-radius: 20px !important; overflow: hidden;
  background: rgba(255,255,255,0.90) !important;
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(119,181,254,0.18) !important;
  box-shadow: 0 20px 60px rgba(0,0,0,0.16), 0 4px 20px rgba(119,181,254,0.12) !important;
}
:global(.dark .mcdr-action-dialog) { background: rgba(15,23,42,0.90) !important; border-color: rgba(119,181,254,0.14) !important; }
:global(.mcdr-action-dialog .el-dialog__header) { padding: 0 !important; margin-right: 0 !important; }
:global(.mcdr-action-dialog .el-dialog__body)   { padding: 0 !important; }
:global(.mcdr-action-dialog .el-dialog__footer) { padding: 0 !important; }

.adlg-head {
  display: flex; align-items: center; gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(119,181,254,0.10);
}
.adlg-icon {
  width: 36px; height: 36px; border-radius: 10px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; color: #fff;
}
.adlg-icon--install { background: linear-gradient(135deg, var(--brand-primary) 0%, #a78bfa 100%); }
.adlg-icon--uninstall { background: linear-gradient(135deg, #f59e0b 0%, #ef4444 100%); }
.adlg-title-group { flex: 1; display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.adlg-title { font-size: 15px; font-weight: 700; color: var(--color-text); line-height: 1.2; }
.adlg-subtitle { font-size: 12px; color: var(--el-text-color-secondary); display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.adlg-version {
  font-family: 'Maple Mono', ui-monospace, monospace; font-size: 11px;
  background: rgba(119,181,254,0.10); border: 1px solid rgba(119,181,254,0.20);
  border-radius: 5px; padding: 0 5px; color: var(--brand-primary);
}
.adlg-close-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; border-radius: 8px; flex-shrink: 0;
  border: 1px solid rgba(119,181,254,0.18); background: transparent;
  color: var(--el-text-color-secondary); cursor: pointer; transition: all 0.15s ease;
}
.adlg-close-btn:hover { background: rgba(248,113,113,0.10); border-color: rgba(248,113,113,0.28); color: #ef4444; }

.adlg-body { padding: 16px 20px; display: flex; flex-direction: column; gap: 12px; }
.adlg-info-card {
  border: 1px solid rgba(119,181,254,0.13); border-radius: 12px; overflow: hidden;
  background: rgba(248,250,255,0.70);
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
}
:global(.dark) .adlg-info-card { background: rgba(15,23,42,0.50); border-color: rgba(119,181,254,0.10); }
.adlg-info-row {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 9px 14px; border-bottom: 1px solid rgba(119,181,254,0.07);
}
.adlg-info-row:last-child { border-bottom: none; }
.adlg-info-label {
  flex-shrink: 0; width: 64px;
  font-size: 11px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
  color: var(--el-text-color-secondary); opacity: 0.7; padding-top: 2px;
}
.adlg-info-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.adlg-no-deps {
  padding: 10px 14px; font-size: 12px; color: var(--el-text-color-placeholder);
}
.adlg-section-label {
  font-size: 11px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;
  color: var(--el-text-color-secondary); opacity: 0.7;
}
.adlg-server-opt { display: flex; justify-content: space-between; align-items: center; width: 100%; }
.adlg-footer {
  display: flex; justify-content: flex-end; align-items: center; gap: 10px;
  padding: 14px 20px 18px; border-top: 1px solid rgba(119,181,254,0.09);
}
.adlg-btn-ghost {
  display: inline-flex; align-items: center; gap: 6px;
  height: 34px; padding: 0 16px; border-radius: 10px; font-family: inherit;
  border: 1px solid rgba(119,181,254,0.22); background: transparent;
  color: var(--el-text-color-regular); font-size: 13px; font-weight: 500; cursor: pointer;
  transition: background 0.18s ease, border-color 0.18s ease;
}
.adlg-btn-ghost:hover { background: rgba(119,181,254,0.07); border-color: rgba(119,181,254,0.40); }
.adlg-btn-primary {
  display: inline-flex; align-items: center; gap: 6px;
  height: 34px; padding: 0 18px; border-radius: 10px; border: none; font-family: inherit;
  cursor: pointer; font-size: 13px; font-weight: 600; color: #fff;
  background: linear-gradient(135deg, var(--brand-primary) 0%, #a78bfa 100%);
  box-shadow: 0 4px 14px rgba(119,181,254,0.35);
  transition: box-shadow 0.2s ease, transform 0.2s cubic-bezier(.34,1.56,.64,1);
}
.adlg-btn-primary:hover:not(:disabled) { box-shadow: 0 6px 22px rgba(119,181,254,0.55); transform: translateY(-1px); }
.adlg-btn-primary:disabled { opacity: 0.42; cursor: not-allowed; box-shadow: none; }

/* ── Detail Drawer ──────────────────────────────────────── */
:global(.mcdr-detail-drawer) { --el-drawer-padding-primary: 0; }
:global(.mcdr-detail-drawer .el-drawer__header) {
  margin-bottom: 0;
  padding: 0;
  border-bottom: none;
}
:global(.mcdr-detail-drawer .el-drawer__body) { padding: 0; overflow: hidden; }

.drw-header {
  position: relative;
  overflow: hidden;
  background: linear-gradient(135deg, rgba(119,181,254,0.12) 0%, rgba(167,139,250,0.08) 100%);
  border-bottom: 1px solid rgba(119,181,254,0.14);
}
.drw-header-shimmer {
  position: absolute; top: 0; left: 0; right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(119,181,254,0.7), rgba(167,139,250,0.6), transparent);
  background-size: 200% 100%;
  animation: shimmer-slide 4s linear infinite;
}
.drw-header-body {
  display: flex; align-items: center; gap: 12px;
  padding: 16px 20px 14px;
}
.drw-header-icon {
  flex-shrink: 0;
  width: 38px; height: 38px; border-radius: 12px;
  background: linear-gradient(135deg, var(--brand-primary), #a78bfa);
  display: flex; align-items: center; justify-content: center;
  color: #fff;
  box-shadow: 0 4px 12px rgba(119,181,254,0.35);
}
.drw-title-group { min-width: 0; flex: 1; }
.drw-title {
  font-size: 15px; font-weight: 700;
  color: var(--color-text);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  line-height: 1.3;
}
.drw-subtitle {
  display: flex; align-items: center; gap: 6px; margin-top: 4px; flex-wrap: wrap;
}
.drw-id {
  font-family: 'Maple Mono', ui-monospace, monospace;
  font-size: 11px; color: var(--el-text-color-secondary);
  background: rgba(119,181,254,0.10);
  border: 1px solid rgba(119,181,254,0.18);
  border-radius: 6px; padding: 1px 6px;
}

.drw-body {
  height: calc(100% - 72px);
  overflow-y: auto; overflow-x: hidden;
  scrollbar-width: thin;
  padding: 20px;
  display: flex; flex-direction: column; gap: 16px;
}

/* ── Info card ── */
.drw-card {
  background: rgba(255,255,255,0.55);
  border: 1px solid rgba(119,181,254,0.14);
  border-radius: 14px;
  overflow: hidden;
  backdrop-filter: saturate(160%) blur(12px);
  -webkit-backdrop-filter: saturate(160%) blur(12px);
}
:global(.dark) .drw-card {
  background: rgba(15,23,42,0.55);
  border-color: rgba(119,181,254,0.10);
}
.drw-card--deps { margin-top: 0; }

.drw-info-grid { display: flex; flex-direction: column; }
.drw-info-row {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 10px 16px;
  border-bottom: 1px solid rgba(119,181,254,0.07);
}
.drw-info-row:last-child { border-bottom: none; }
.drw-info-label {
  flex-shrink: 0; width: 68px;
  font-size: 11px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
  color: var(--el-text-color-secondary); opacity: 0.7;
  padding-top: 2px;
}
.drw-info-value { flex: 1; min-width: 0; font-size: 13px; color: var(--color-text); }
.drw-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.drw-stats { display: flex; align-items: center; gap: 6px; }
.drw-link {
  color: var(--brand-primary); text-decoration: none; font-size: 13px;
  transition: opacity 0.15s;
}
.drw-link:hover { opacity: 0.75; text-decoration: underline; }
.drw-none { color: var(--el-text-color-placeholder); font-size: 13px; }

/* ── Section title ── */
.drw-section { display: flex; flex-direction: column; gap: 10px; }
.drw-section-title {
  display: flex; align-items: center; gap: 7px;
  font-size: 12px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;
  color: var(--el-text-color-secondary); opacity: 0.8;
}
.drw-section-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
  background: var(--brand-primary);
  box-shadow: 0 0 6px rgba(119,181,254,0.6);
}
.drw-section-dot--purple { background: #a78bfa; box-shadow: 0 0 6px rgba(167,139,250,0.6); }
.drw-section-dot--green  { background: #34d399; box-shadow: 0 0 6px rgba(52,211,153,0.5); }
.drw-section-badge {
  font-size: 10px; font-weight: 500; letter-spacing: 0; text-transform: none;
  color: var(--el-text-color-placeholder);
  background: rgba(119,181,254,0.08);
  border: 1px solid rgba(119,181,254,0.14); border-radius: 99px;
  padding: 1px 7px;
}

/* ── Introduction ── */
.drw-intro {
  font-size: 13px; line-height: 1.7; color: var(--el-text-color-regular);
  white-space: pre-wrap;
  background: rgba(255,255,255,0.45);
  border: 1px solid rgba(119,181,254,0.10);
  border-radius: 12px; padding: 14px 16px;
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
}
:global(.dark) .drw-intro {
  background: rgba(15,23,42,0.45);
  border-color: rgba(119,181,254,0.08);
}

/* ── Release timeline ── */
.drw-timeline { display: flex; flex-direction: column; gap: 0; }
.drw-release-card {
  display: flex; gap: 14px;
  padding: 12px 0;
  border-bottom: 1px solid rgba(119,181,254,0.07);
  position: relative;
}
.drw-release-card:last-child { border-bottom: none; }
.drw-release-dot {
  flex-shrink: 0;
  width: 10px; height: 10px; border-radius: 50%;
  margin-top: 5px;
  position: relative; z-index: 1;
}
.drw-release-dot--ok   { background: #34d399; box-shadow: 0 0 6px rgba(52,211,153,0.55); }
.drw-release-dot--warn { background: #f59e0b; box-shadow: 0 0 6px rgba(245,158,11,0.55); }
.drw-release-body { flex: 1; min-width: 0; }
.drw-release-head {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  flex-wrap: wrap;
}
.drw-release-name {
  font-size: 13px; font-weight: 600; color: var(--color-text);
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
}
.drw-pre-tag { vertical-align: middle; }
.drw-release-actions { display: inline-flex; align-items: center; gap: 4px; flex-shrink: 0; }
.drw-release-meta {
  display: flex; align-items: baseline; gap: 10px; margin-top: 4px; flex-wrap: wrap;
}
.drw-release-time {
  font-size: 11px; color: var(--el-text-color-placeholder);
  font-variant-numeric: tabular-nums;
}
.drw-release-desc {
  font-size: 12px; color: var(--el-text-color-secondary);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 320px;
}
.drw-empty {
  text-align: center; padding: 32px 0;
  color: var(--el-text-color-placeholder); font-size: 13px;
}
</style>
