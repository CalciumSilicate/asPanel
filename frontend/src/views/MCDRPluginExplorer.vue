<template>
  <div class="mcdr-explorer">
    <!-- Toolbar -->
    <el-card shadow="never" class="mb-3">
      <template #header>
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <span class="text-base font-medium">MCDR 插件浏览</span>
            <el-tag type="info" v-if="stats.total">共 {{ stats.total }} 个插件</el-tag>
            <el-tag type="success" v-if="stats.updatedAt">最近刷新：{{ stats.updatedAt }}</el-tag>
          </div>
          <div class="flex items-center gap-2">
            <el-button :loading="loading" type="primary" @click="load">刷新</el-button>
          </div>
        </div>
      </template>

      <div class="grid grid-cols-1 md:grid-cols-12 gap-3">
        <el-input
            v-model="query"
            placeholder="搜索：名称 / ID / 作者 / 标签 / 描述"
            clearable
            class="md:col-span-4"
            @input="handleSearch"
        >
          <template #prefix>
            <el-icon>
              <Search/>
            </el-icon>
          </template>
        </el-input>

        <el-select v-model="selectedLabels" class="md:col-span-3" multiple collapse-tags collapse-tags-tooltip
                   placeholder="标签筛选">
          <el-option v-for="l in allLabels" :key="l" :label="l" :value="l"/>
        </el-select>

        <el-select v-model="sortBy" class="md:col-span-2" placeholder="排序">
          <el-option label="最新发布" value="latestDate"/>
          <el-option label="下载最多" value="downloads"/>
          <el-option label="Star 最多" value="stars"/>
          <el-option label="名称" value="name"/>
        </el-select>

        <div class="md:col-span-3 flex items-center gap-3">
          <el-checkbox v-model="showPrerelease">包含预发布</el-checkbox>
          <el-checkbox v-model="hideArchived">隐藏已归档</el-checkbox>
        </div>
      </div>
    </el-card>

    <!-- List -->
    <div class="table-card">
      <el-table :data="paged" v-loading="loading" stripe size="small" @row-dblclick="openDetail">
      <el-table-column label="插件" min-width="260">
        <template #default="{ row }">
          <div class="flex items-start gap-2">
            <el-tag type="primary" effect="plain">{{ row.meta.id }}</el-tag>
            <div>
              <div class="font-medium leading-5">{{ row.meta.name }}</div>
              <div class="text-xs text-gray-500 leading-4">
                {{ row.meta.description?.zh_cn || row.meta.description?.en_us || '-' }}
              </div>
            </div>
          </div>
        </template>
      </el-table-column>

      <el-table-column prop="release.latest_version" label="最新版本" width="130">
        <template #default="{ row }">
          <el-tag size="small" :type="row.latest?.prerelease ? 'warning' : 'success'">
            {{ row.release?.latest_version || '-' }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column label="作者" min-width="160">
        <template #default="{ row }">
          <el-space wrap>
            <el-tag v-for="a in row.meta?.authors || []" :key="a" size="small">{{ a }}</el-tag>
          </el-space>
        </template>
      </el-table-column>

      <el-table-column label="统计" width="220" align="center">
        <template #default="{ row }">
          <el-space>
            <el-tooltip content="Repo Stars">
              <el-tag type="info" size="small">
                <el-icon class="mr-1">
                  <Star/>
                </el-icon>
                {{ row.repository?.stargazers_count ?? 0 }}
              </el-tag>
            </el-tooltip>
            <el-tooltip content="Latest Asset Downloads">
              <el-tag type="info" size="small">
                <el-icon class="mr-1">
                  <Download/>
                </el-icon>
                {{ row.latest?.asset?.download_count ?? 0 }}
              </el-tag>
            </el-tooltip>
          </el-space>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="230" align="center">
        <template #default="{ row }">
          <el-button-group>
            <el-button size="small" @click="openDetail(row)">详情</el-button>
            <el-button size="small" type="primary" :disabled="!row.latest?.asset?.browser_download_url"
                       @click="go(row.latest?.asset?.browser_download_url)">下载
            </el-button>
            <el-button size="small" type="success" :icon="Upload" @click="handleInstallClick(row, row.latest)">
              为服务器安装
            </el-button>
          </el-button-group>
        </template>
      </el-table-column>
      </el-table>
    </div>

    <!-- Pagination -->
    <div class="mt-3 flex items-center justify-end">
      <el-pagination
          background
          layout="prev, pager, next, sizes, total"
          :page-sizes="[10, 20, 50, 100]"
          :page-size="pageSize"
          :current-page="page"
          :total="filtered.length"
          @current-change="(p:number)=>page=p"
          @size-change="(s:number)=>{pageSize=s; page=1}"
      />
    </div>

    <!-- Detail Drawer -->
    <el-drawer v-model="detailVisible" size="50%" direction="rtl" :destroy-on-close="true">
      <template #header>
        <div class="flex items-center gap-2">
          <div class="text-base font-medium">{{ detail?.meta?.name }}<span class="text-gray-500">（{{
              detail?.meta?.id
            }}）</span></div>
          <el-tag size="small" :type="detail?.latest?.prerelease ? 'warning' : 'success'">
            {{ detail?.release?.latest_version }}
          </el-tag>
          <el-tag v-if="detail?.repository?.archived" size="small" type="danger">Archived</el-tag>
        </div>
      </template>

      <div class="table-card">
        <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="Repo">
          <el-link v-if="detail?.repository?.html_url" :href="detail?.repository?.html_url" target="_blank"
                   type="primary">{{ detail?.repository?.full_name }}
          </el-link>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="Labels">
          <el-space wrap>
            <el-tag v-for="t in detail?.plugin?.labels || []" :key="t" size="small" effect="plain">{{ t }}</el-tag>
          </el-space>
        </el-descriptions-item>
        <el-descriptions-item label="Authors" :span="2">
          <el-space wrap>
            <el-tag v-for="a in detail?.meta?.authors || []" :key="a" size="small">{{ a }}</el-tag>
          </el-space>
        </el-descriptions-item>
        </el-descriptions>
      </div>

      <el-divider>简介</el-divider>
      <div class="text-sm leading-6 text-gray-700 whitespace-pre-wrap">
        {{
          detail?.plugin?.introduction?.zh_cn || detail?.plugin?.introduction?.en_us || detail?.meta?.description?.zh_cn || detail?.meta?.description?.en_us || '无'
        }}
      </div>

      <template v-if="hasDependenciesInDetail">
        <el-divider>依赖信息 (最新版本)</el-divider>
        <div class="table-card" style="margin-bottom: 20px;">
          <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="插件依赖" v-if="detail?.latest?.meta?.dependencies">
            <el-space wrap v-if="Object.keys(detail?.latest?.meta?.dependencies || {}).length > 0">
              <el-tag v-for="(version, name) in (detail?.latest?.meta?.dependencies || {})" :key="name" size="small"
                      type="primary" effect="dark">
                {{ name }}: {{ version }}
              </el-tag>
            </el-space>
            <span v-else>无</span>
          </el-descriptions-item>
          <el-descriptions-item label="Python库依赖" v-if="detail?.latest?.meta?.requirements">
            <el-space wrap v-if="(detail?.latest?.meta?.requirements || []).length > 0">
              <el-tag v-for="req in (detail?.latest?.meta?.requirements || [])" :key="req" size="small" type="success"
                      effect="plain">
                {{ req }}
              </el-tag>
            </el-space>
            <span v-else>无</span>
          </el-descriptions-item>
          </el-descriptions>
        </div>
      </template>

      <el-divider>发布历史（最多 10 条）</el-divider>
      <el-timeline>
        <el-timeline-item v-for="(r, idx) in (detail?.release?.releases || []).slice(0, 10)" :key="idx"
                          :timestamp="formatDate(r.created_at)" :type="r.prerelease ? 'warning' : 'primary'">
          <div class="flex items-center justify-between gap-2">
            <div>
              <div class="font-medium">{{ r.name || r.tag_name }}</div>
              <div class="text-xs text-gray-500">{{ r.description || '——' }}</div>
            </div>
            <div class="flex items-center gap-2">
              <el-button-group>
                <el-button v-if="r.asset?.browser_download_url" size="small" type="primary"
                           @click="go(r.asset.browser_download_url)">下载
                </el-button>
                <el-button v-if="r.url" size="small" @click="go(r.url)">发布页</el-button>
                <el-button size="small" type="success" :icon="Upload" @click="detail && handleInstallClick(detail, r)">
                  为服务器安装
                </el-button>
              </el-button-group>
            </div>
          </div>
        </el-timeline-item>
      </el-timeline>
    </el-drawer>

    <!-- Install Dialog -->
    <el-dialog v-model="installDialogVisible" title="安装插件到服务器" width="600px" destroy-on-close>
      <div v-if="pluginToInstallInfo.plugin">
        <div class="table-card">
          <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="插件名称">{{ pluginToInstallInfo.plugin.meta.name }}</el-descriptions-item>
          <el-descriptions-item label="安装版本">{{ pluginToInstallInfo.versionTag }}</el-descriptions-item>
          <el-descriptions-item label="插件依赖">
            <el-space wrap v-if="pluginToInstallInfo.dependencies.length > 0">
              <el-tag v-for="dep in pluginToInstallInfo.dependencies" :key="dep" type="primary" effect="dark"
                      size="small">{{ dep }}
              </el-tag>
            </el-space>
            <span v-else>无</span>
          </el-descriptions-item>
          <el-descriptions-item label="Python库依赖">
            <el-space wrap v-if="pluginToInstallInfo.requirements.length > 0">
              <el-tag v-for="req in pluginToInstallInfo.requirements" :key="req" type="success" effect="plain"
                      size="small">{{ req }}
              </el-tag>
            </el-space>
            <span v-else>无</span>
          </el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="mt-4">
          <p class="mb-2 font-medium">选择要安装的服务器:</p>
          <el-select
              v-model="selectedServers"
              multiple
              filterable
              placeholder="请选择服务器"
              style="width: 100%;"
              :loading="isFetchingServerPlugins"
          >
            <el-option
                v-for="server in servers"
                :key="server.id"
                :label="server.name"
                :value="server.id"
            >
              <div class="flex justify-between items-center w-full">
                <span>{{ server.name }}</span>
                <el-tag
                    size="small"
                    :type="getPluginStatusForServer(server, pluginToInstallInfo.plugin.meta.id).type"
                    effect="light"
                >
                  {{ getPluginStatusForServer(server, pluginToInstallInfo.plugin.meta.id).text }}
                </el-tag>
              </div>
            </el-option>
          </el-select>
        </div>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="installDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="confirmInstall" :loading="isInstalling">
            确认安装
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script lang="ts" setup>
import {ref, computed, onMounted} from 'vue'
import {ElMessage, ElNotification} from 'element-plus'
import {Search, Star, Download, Upload} from '@element-plus/icons-vue'
import apiClient from '@/api'

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

const filtered = computed(() => {
  let result = items.value
  if (query.value.trim()) {
    const q = query.value.trim().toLowerCase()
    result = result.filter(i => {
      const desc = JSON.stringify(i.meta?.description || i.plugin?.introduction || {}).toLowerCase()
      const authors = (i.meta?.authors || []).join(',').toLowerCase()
      const labels = (i.plugin?.labels || []).join(',').toLowerCase()
      return (
          i.meta.id.toLowerCase().includes(q) ||
          (i.meta.name || '').toLowerCase().includes(q) ||
          authors.includes(q) || labels.includes(q) || desc.includes(q)
      )
    })
  }
  if (selectedLabels.value.length) {
    result = result.filter(i => selectedLabels.value.every(l => (i.plugin?.labels || []).includes(l)))
  }
  if (!showPrerelease.value) {
    result = result.filter(i => !(i.latest?.prerelease))
  }
  if (hideArchived.value) {
    result = result.filter(i => !i.repository?.archived)
  }

  result = [...result].sort((a, b) => {
    if (sortBy.value === 'name') return (a.meta.name || a.meta.id).localeCompare(b.meta.name || b.meta.id)
    if (sortBy.value === 'stars') return (b.repository?.stargazers_count ?? 0) - (a.repository?.stargazers_count ?? 0)
    if (sortBy.value === 'downloads') return (b.latest?.asset?.download_count ?? 0) - (a.latest?.asset?.download_count ?? 0)
    const da = a.latest?.created_at ? new Date(a.latest.created_at).getTime() : 0
    const db = b.latest?.created_at ? new Date(b.latest.created_at).getTime() : 0
    return db - da
  })
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

function normalize(data: any): PluginEntry[] {
  const map = data?.plugins || {}
  return Object.keys(map).map((k: string) => {
    const p = map[k]
    const latest = p?.release?.releases?.[0] ?? null
    return {meta: p.meta, plugin: p.plugin, release: p.release, repository: p.repository, latest}
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
}

async function fetchServers() {
  try {
    const res = await apiClient.get('/api/servers');
    servers.value = res.data;
  } catch (e: any) {
    ElMessage.error(`加载服务器列表失败: ${e.message || String(e)}`);
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
.mcdr-explorer :deep(.el-card__header) {
  padding: 10px 16px;
}

.mb-3 {
  margin-bottom: 12px;
}

.text-gray-500 {
  color: #909399;
}

.text-gray-700 {
  color: #606266;
}

.flex {
  display: flex;
}

.items-center {
  align-items: center;
}

.items-start {
  align-items: flex-start;
}

.justify-between {
  justify-content: space-between;
}

.justify-end {
  justify-content: flex-end;
}

.gap-2 {
  gap: 8px;
}

.gap-3 {
  gap: 12px;
}

.grid {
  display: grid;
}

.grid-cols-1 {
  grid-template-columns:repeat(1, minmax(0, 1fr));
}

.md\:grid-cols-12 {
  grid-template-columns:repeat(12, minmax(0, 1fr));
}

.md\:col-span-2 {
  grid-column: span 2/span 2;
}

.md\:col-span-3 {
  grid-column: span 3/span 3;
}

.md\:col-span-4 {
  grid-column: span 4/span 4;
}

.mt-3 {
  margin-top: 12px;
}

.mt-4 {
  margin-top: 16px;
}

.mb-2 {
  margin-bottom: 8px;
}

.font-medium {
  font-weight: 500;
}

.text-base {
  font-size: 14px;
}

.text-xs {
  font-size: 12px;
}

.leading-5 {
  line-height: 20px;
}

.leading-4 {
  line-height: 16px;
}

.leading-6 {
  line-height: 24px;
}

.w-full {
  width: 100%;
}

/* 表格与描述组件圆角 */
.rounded-table {
  border-radius: 8px;
  overflow: hidden;
}
/* 让本页滚动限制在视图内部，避免出现页面级滚动条；隐藏滚动条但保留滚动功能 */
.mcdr-explorer {
  height: calc(100vh - var(--el-header-height) - 48px); /* 减去头部与 el-main 内边距 */
  overflow: auto;
  box-sizing: border-box;
  scrollbar-gutter: stable;
  scrollbar-width: thin;
}
/* Element Plus 自定义滚动条保持可见 */
.mcdr-explorer :deep(.el-scrollbar__bar) { opacity: 0.9; }

</style>
