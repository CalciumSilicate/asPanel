<template>
  <div class="server-plugin-manager-layout" :class="{ 'is-collapsed': asideCollapsed, 'is-collapsing': asideCollapsing }">
  
    <!-- 左侧边栏：参考 PrimeBackup 风格 -->
    <div class="table-card left-panel">
      <el-card shadow="never" v-loading="serversLoading">
        <template #header>
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="text-base font-medium">选择服务器</span>
            </div>
            <div class="flex items-center gap-2">
              <el-tag type="success">总插件数：{{ totalPluginCount }}</el-tag>
            </div>
          </div>
        </template>

        <el-input v-model="serverQuery" placeholder="搜索服务器" clearable class="mb-2">
          <template #prefix><el-icon><Search/></el-icon></template>
        </el-input>

        <el-table :data="filteredServers" size="small" stripe @row-click="row => selectServer(row.id)">
          <el-table-column label="服务器" min-width="180">
            <template #default="{ row }">
              <div class="flex items-center justify-between w-full">
                <div class="server-cell">
                  <div class="server-name">{{ row.name }}</div>
                  <div class="muted">ID: {{ row.id }}</div>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="插件数" width="100" align="center">
            <template #default="{ row }">
              <span>{{ Number(row.plugins_count) || 0 }}</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <!-- Main Content Area -->
    <el-main class="plugin-content-area">
      <div v-if="!selectedServer" class="main-placeholder">
        <el-empty description="请从左侧选择一个服务器以管理插件"/>
      </div>

      <div v-else>
        <!-- Toolbar -->
        <el-card shadow="never" class="mb-3">
          <template #header>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="text-base font-medium">{{ selectedServer ? selectedServer.name : '请选择服务器' }}</span>
                <el-tag type="info" v-if="selectedServer">共 {{ currentPlugins.length }} 个插件</el-tag>
              </div>
              <div class="flex items-center gap-2">
                <el-button-group>
                  <el-button type="success" :icon="Plus" @click="openAddOnlinePluginDialog" :disabled="!selectedServer">添加联网插件</el-button>
                  <el-button type="primary" :icon="Coin" @click="openAddDbPluginDialog" :disabled="!selectedServer">添加数据库插件</el-button>
                </el-button-group>
              </div>
            </div>
          </template>
          <div class="flex items-center gap-2">
            <el-input v-model="query" placeholder="搜索：名称 / ID / 文件名" clearable style="max-width: 300px;">
              <template #prefix>
                <el-icon>
                  <Search/>
                </el-icon>
              </template>
            </el-input>
            <el-radio-group v-model="filterStatus">
              <el-radio-button value="all">全部</el-radio-button>
              <el-radio-button value="enabled">已启用</el-radio-button>
              <el-radio-button value="disabled">已禁用</el-radio-button>
            </el-radio-group>
          </div>
        </el-card>

        <!-- Plugin List Table -->
        <div class="table-card">
          <el-table :data="pagedPlugins" v-loading="pluginsLoading" stripe size="small"
                    :row-class-name="pluginRowClassName">
          
          <el-table-column label="插件" min-width="280">
            <template #default="{ row }">
              <div class="plugin-cell-layout">
                <el-tag type="primary" effect="plain" size="small" v-if="row.meta.id">{{ row.meta.id }}</el-tag>
                <div>
                  <div class="plugin-name">{{ row.meta.name || '未知名称' }}</div>
                  <div class="plugin-description">
                    {{ row.meta.description?.zh_cn || row.meta.description?.en_us || row.file_name }}
                  </div>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="作者" min-width="160">
            <template #default="{ row }">
              <el-space wrap>
                <el-tag v-for="a in getAuthorsArray(row.meta)" :key="a" size="small">{{ a }}</el-tag>
                <span v-if="getAuthorsArray(row.meta).length === 0"><el-tag size="small"
                                                                            type="info">未知</el-tag></span>
              </el-space>
            </template>
          </el-table-column>
          <el-table-column label="版本" width="180">
            <template #default="{ row }">
              <div class="version-cell">
                <el-tag size="small" :type="row.meta.version ? 'success' : 'info'">{{
                    row.meta.version || '未知'
                  }}
                </el-tag>
                <el-tooltip :content="`有新版：${onlinePluginsMap.get(row.meta.id)?.release?.latest_version || ''}`" placement="top-start" effect="light" v-if="isUpdateAvailable(row)">
                  <el-button size="small" type="warning" circle plain :icon="Refresh" :loading="row.loading" @click="handleUpdatePlugin(row)" />
                </el-tooltip>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="文件大小" width="100" align="center">
            <template #default="{ row }">
              <span>{{ (row.size / 1024).toFixed(1) }} KB</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-switch v-model="row.enabled" @change="handlePluginSwitch(row)" :loading="row.loading"/>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="250" align="center">
            <template #default="{ row }">
              <el-button size="small" type="success" :icon="Download" :loading="row.loading"
                         @click="handlePluginDownload(row)">下载
              </el-button>
              <el-popconfirm title="确定删除这个插件吗？" width="220" @confirm="handlePluginDelete(row)">
                <template #reference>
                  <el-button size="small" type="danger" :icon="Delete" :loading="row.loading">删除</el-button>
                </template>
              </el-popconfirm>
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
              :total="filteredPlugins.length"
              @current-change="p => page = p"
              @size-change="s => { pageSize = s; page = 1; }"
          />
        </div>
      </div>
    </el-main>

    <!-- [MODIFIED] Dialogs for adding plugins -->
    <el-dialog v-if="addOnlinePluginDialogVisible" v-model="addOnlinePluginDialogVisible" title="从 MCDR 市场添加插件"
               width="70%" top="8vh" destroy-on-close>
      <div class="plugin-toolbar">
        <el-input v-model="onlinePluginsQuery" placeholder="搜索：名称 / ID / 作者" clearable
                  style="width: 300px;"></el-input>
      </div>
      <el-table :data="filteredOnlinePlugins" v-loading="onlinePluginsLoading"
                @selection-change="handleOnlineSelectionChange" stripe border height="50vh" row-key="meta.id">
        <el-table-column type="selection" width="55" reserve-selection/>
        <el-table-column label="插件" min-width="260">
          <template #default="{ row }">
            <div class="plugin-cell-layout">
              <el-tag type="primary" effect="plain" size="small">{{ row.meta.id }}</el-tag>
              <div>
                <div class="plugin-name">{{ row.meta.name }}</div>
                <div class="plugin-description">
                  {{ (row.meta.description?.zh_cn || row.meta.description?.en_us || '-').substring(0, 50) }}
                </div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="最新版本" width="130">
          <template #default="{ row }">
            <el-tag size="small" :type="row.latest?.prerelease ? 'warning' : 'success'">
              {{ row.release?.latest_version || '-' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="当前版本" width="130">
          <template #default="{ row }">
            <el-tag v-if="getPluginInstallStatus(row.meta.id)" type="success" size="small">
              {{ getPluginInstallStatus(row.meta.id) }}
            </el-tag>
            <el-tag v-else type="info" size="small" effect="plain">未安装</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="作者" min-width="160">
          <template #default="{ row }">
            <el-space wrap>
              <el-tag v-for="a in getAuthorsArray(row.meta)" :key="a" size="small">{{ a }}</el-tag>
              <span v-if="getAuthorsArray(row.meta).length === 0">未知</span>
            </el-space>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="addOnlinePluginDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="prepareInstallationConfirmation"
                     :disabled="onlinePluginsSelected.length === 0">
            安装已选 ({{ onlinePluginsSelected.length }})
          </el-button>
        </span>
      </template>
    </el-dialog>

    <el-dialog v-if="installConfirmDialogVisible" v-model="installConfirmDialogVisible" title="安装确认" width="70%"
               top="8vh">
      <el-table :data="pluginsToInstall" stripe border max-height="60vh">
        <el-table-column label="插件" width="360">
          <template #default="{ row }">
            <div class="plugin-cell-layout">
              <el-tag type="primary" effect="plain" size="small">{{ row.meta.id }}</el-tag>
              <div>
                <div class="plugin-name">{{ row.meta.name }}</div>
                <div class="plugin-description">
                  {{ (row.meta.description?.zh_cn || row.meta.description?.en_us || '-').substring(0, 50) }}
                </div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="当前版本" width="120">
          <template #default="{ row }">
            <el-tag v-if="getPluginInstallStatus(row.meta.id)" type="success" size="small">
              {{ getPluginInstallStatus(row.meta.id) }}
            </el-tag>
            <el-tag v-else type="info" size="small" effect="plain">未安装</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="安装版本" width="130">
          <template #default="{ row }">
            <el-select v-if="row.availableVersions && row.availableVersions.length > 0" v-model="row.selectedVersion"
                       placeholder="选择版本" size="small" style="width: 100px;">
              <el-option v-for="version in row.availableVersions" :key="version" :label="version" :value="version"/>
            </el-select>
            <span v-else>无可用版本</span>
          </template>
        </el-table-column>
        <el-table-column label="依赖" min-width="250">
          <template #default="{ row }">
            <el-space wrap>
              <el-tooltip v-for="(version, dep) in row.meta.dependencies" :key="dep"
                          :content="`插件依赖: ${dep} (版本: ${version})`">
                <el-tag size="small" type="info">{{ dep }}</el-tag>
              </el-tooltip>
              <el-tooltip v-for="req in row.meta.requirements" :key="req" :content="`Python库: ${req}`">
                <el-tag size="small" type="warning">{{ req }}</el-tag>
              </el-tooltip>
              <span v-if="!row.meta.dependencies && !row.meta.requirements">无</span>
            </el-space>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="installConfirmDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="executeInstallation" :loading="isInstallingPlugins">确认安装</el-button>
        </span>
      </template>
    </el-dialog>

    <el-dialog v-if="addDbPluginDialogVisible" v-model="addDbPluginDialogVisible" title="从数据库添加插件" width="60%"
               top="8vh" destroy-on-close>
      <div class="plugin-toolbar">
        <el-input v-model="dbPluginsQuery" placeholder="搜索：名称 / 文件名" clearable style="width: 300px;"></el-input>
      </div>
      <el-table :data="filteredDbPlugins" v-loading="dbPluginsLoading" @selection-change="handleDbSelectionChange"
                stripe border height="50vh" row-key="id">
        <el-table-column type="selection" width="55" reserve-selection/>
        <el-table-column label="插件" min-width="260">
          <template #default="{ row }">
            <div class="plugin-cell-layout">
              <el-tag v-if="row.meta.id" type="primary" effect="plain" size="small">{{ row.meta.id }}</el-tag>
              <div>
                <div class="plugin-name">{{ row.meta.name || row.file_name }}</div>
                <div class="plugin-description">
                  {{ (row.meta.description?.zh_cn || row.meta.description?.en_us || '').substring(0, 50) }}
                </div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="插件版本" width="130">
          <template #default="{ row }">
            <el-tag v-if="row.meta.version" type="success" size="small">{{ row.meta.version || "未知" }}</el-tag>
            <el-tag v-else type="info" size="small">未知</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="当前版本" width="130">
          <template #default="{ row }">
            <el-tag v-if="getPluginInstallStatus(row.meta.id)" type="success" size="small">
              {{ getPluginInstallStatus(row.meta.id) }}
            </el-tag>
            <el-tag v-else type="info" size="small" effect="plain">未安装</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="作者" min-width="160">
          <template #default="{ row }">
            <el-space wrap>
              <el-tag v-for="a in getAuthorsArray(row.meta)" :key="a" size="small">{{ a }}</el-tag>
              <span v-if="getAuthorsArray(row.meta).length === 0">未知</span>
            </el-space>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="addDbPluginDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleInstallDbPlugins" :loading="isInstallingPlugins"
                     :disabled="dbPluginsSelected.length === 0">
            安装已选 ({{ dbPluginsSelected.length }})
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import {ref, onMounted, computed} from 'vue';
import {ElMessage, ElNotification} from 'element-plus';
import {Search, Refresh, Plus, Coin, Delete, Download} from '@element-plus/icons-vue';
import apiClient from '@/api';
import { asideCollapsed, asideCollapsing } from '@/store/ui'

// --- Page State ---
const servers = ref([]);
const serversLoading = ref(false);
const selectedServerId = ref(null);
const serverPluginsMap = new Map();
const currentPlugins = ref([]);
const pluginsLoading = ref(false);

// Left panel search & aggregates
const serverQuery = ref('');
const filteredServers = computed(() => {
  const q = serverQuery.value.trim().toLowerCase();
  if (!q) return servers.value;
  return servers.value.filter(s => s.name?.toLowerCase().includes(q) || String(s.id).includes(q));
});
const totalPluginCount = computed(() => servers.value.reduce((sum, s) => sum + (Number(s.plugins_count) || 0), 0));

// --- Filtering & Pagination State ---
const query = ref('');
const filterStatus = ref('all');
const page = ref(1);
const pageSize = ref(20);

// --- Dialogs & Installation State ---
const addOnlinePluginDialogVisible = ref(false);
const addDbPluginDialogVisible = ref(false);
const installConfirmDialogVisible = ref(false);
const isInstallingPlugins = ref(false);

const onlinePlugins = ref([]);
const onlinePluginsLoading = ref(false);
const onlinePluginsQuery = ref('');
const onlinePluginsSelected = ref([]);
const pluginsToInstall = ref([]);

const dbPlugins = ref([]);
const dbPluginsLoading = ref(false);
const dbPluginsQuery = ref('');
const dbPluginsSelected = ref([]);

// --- Computed Properties ---
const selectedServer = computed(() => {
  return servers.value.find(s => s.id === selectedServerId.value) || null;
});

const filteredPlugins = computed(() => {
  return currentPlugins.value.filter(p => {
    const q = query.value.toLowerCase();
    const matchesQuery = !q || p.file_name.toLowerCase().includes(q) || (p.meta.name && p.meta.name.toLowerCase().includes(q)) || (p.meta.id && p.meta.id.toLowerCase().includes(q));
    const matchesFilter = filterStatus.value === 'all' || (filterStatus.value === 'enabled' && p.enabled) || (filterStatus.value === 'disabled' && !p.enabled);
    return matchesQuery && matchesFilter;
  });
});

const pagedPlugins = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return filteredPlugins.value.slice(start, start + pageSize.value);
});

const onlinePluginsMap = computed(() => new Map(
  onlinePlugins.value
    .map(p => [p?.meta?.id || '', p])
    .filter(([k]) => !!k)
));

const filteredOnlinePlugins = computed(() => {
  if (!onlinePluginsQuery.value) return onlinePlugins.value;
  const q = onlinePluginsQuery.value.toLowerCase();
  return onlinePlugins.value.filter(p =>
    (p.meta?.id && p.meta.id.toLowerCase().includes(q)) ||
    (p.meta?.name && p.meta.name.toLowerCase().includes(q)) ||
    getAuthorsArray(p.meta).join(',').toLowerCase().includes(q)
  );
});

const filteredDbPlugins = computed(() => {
  if (!dbPluginsQuery.value) return dbPlugins.value;
  const q = dbPluginsQuery.value.toLowerCase();
  return dbPlugins.value.filter(p => p.file_name.toLowerCase().includes(q) || (p.meta.name && p.meta.name.toLowerCase().includes(q)));
});

// --- Main Methods ---
const initialLoad = async (forceOnlineRefresh = false) => {
  serversLoading.value = true;
  try {
    const [{ data: serverData }] = await Promise.all([
      apiClient.get('/api/servers'),
      fetchOnlinePlugins(forceOnlineRefresh)
    ]);

    // 直接使用后端返回的 servers（已包含 plugins_count），尽快展示列表
    servers.value = serverData || [];

    // 后台预取每个服务器的插件列表，填充缓存，避免后续重复拉取
    // 不阻塞 UI 加载
    prefetchAllServerPlugins(servers.value);

    // 如果已选择过服务器，优先从缓存展示，否则等待预取完成或按需获取
    if (selectedServerId.value) {
      await fetchCurrentServerPlugins();
    }
  } catch (error) {
    ElMessage.error('加载服务器列表失败: ' + (error.response?.data?.detail || error.message));
  } finally {
    serversLoading.value = false;
  }
};

const selectServer = async (serverId) => {
  if (selectedServerId.value === serverId && currentPlugins.value.length > 0) return;
  selectedServerId.value = serverId;
  page.value = 1;
  query.value = '';
  filterStatus.value = 'all';
  await fetchCurrentServerPlugins();
};

const fetchCurrentServerPlugins = async () => {
  if (!selectedServerId.value) return;
  const cached = serverPluginsMap.get(selectedServerId.value);
  if (cached) {
    currentPlugins.value = cached;
    return;
  }

  pluginsLoading.value = true;
  try {
    const { data } = await apiClient.get(`/api/plugins/server/${selectedServerId.value}`);
    const plugins = (data.data || []).map(p => ({ ...p, loading: false }));
    serverPluginsMap.set(selectedServerId.value, plugins);
    currentPlugins.value = plugins;
  } catch (error) {
    ElMessage.error(`加载插件列表失败: ${error.response?.data?.detail || error.message}`);
    currentPlugins.value = [];
  } finally {
    pluginsLoading.value = false;
  }
};

// 预取所有服务器的插件列表到本地缓存（不阻塞 UI）
const prefetchAllServerPlugins = async (serverList = []) => {
  if (!Array.isArray(serverList) || serverList.length === 0) return;
  // 控制并发以避免瞬时压力过大
  const concurrency = 5;
  const queue = [...serverList];
  const workers = Array.from({ length: Math.min(concurrency, queue.length) }, () => (async () => {
    while (queue.length > 0) {
      const srv = queue.shift();
      if (!srv) break;
      const id = srv.id;
      if (serverPluginsMap.has(id)) continue;
      try {
        const { data } = await apiClient.get(`/api/plugins/server/${id}`);
        const plugins = (data.data || []).map(p => ({ ...p, loading: false }));
        serverPluginsMap.set(id, plugins);
        // 若当前正查看该服务器且尚未有列表，则立即展示
        if (selectedServerId.value === id && currentPlugins.value.length === 0) {
          currentPlugins.value = plugins;
        }
      } catch {
        serverPluginsMap.set(id, []);
      }
    }
  })());

  await Promise.allSettled(workers);
};

const pluginRowClassName = ({row}) => row.enabled ? '' : 'disabled-plugin-row';

// --- Plugin Action & Dialog Methods ---
const getAuthorsArray = (meta) => {
  if (!meta) return [];
  if (meta.authors && Array.isArray(meta.authors)) return meta.authors.filter(Boolean);
  if (meta.author) {
    if (Array.isArray(meta.author)) return meta.author.filter(Boolean);
    if (typeof meta.author === 'string') return [meta.author];
  }
  return [];
};

const handlePluginSwitch = async (plugin) => {
  plugin.loading = true;
  const enable = plugin.enabled;
  try {
    await apiClient.post(`/api/plugins/server/${selectedServerId.value}/switch/${plugin.file_name}?enable=${enable}`);
    ElMessage.success(`插件 "${plugin.meta.name || plugin.file_name}" 已${enable ? '启用' : '禁用'}`);
  } catch (error) {
    ElMessage.error(`操作失败: ${error.response?.data?.detail || error.message}`);
    plugin.enabled = !enable; // Revert on failure
  } finally {
    plugin.loading = false;
  }
};
// [NEW] Download plugin method
const handlePluginDownload = async (plugin) => {
  if (!selectedServerId.value) return;
  plugin.loading = true;
  try {
    const response = await apiClient.get(
        `/api/plugins/download/${selectedServerId.value}/${plugin.file_name}`,
        {responseType: 'blob'}
    );

    // --- 关键修正 ---
    // 根据插件类型决定下载的文件名
    const downloadFilename = plugin.type === 'FOLDER'
        ? `${plugin.file_name}.zip`
        : plugin.file_name;
    // -----------------
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', downloadFilename); // 使用修正后的文件名
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  } catch (error) {
    ElMessage.error(`下载失败: ${error.response?.data?.detail || error.message}`);
  } finally {
    plugin.loading = false;
  }
};
const handlePluginDelete = async (plugin) => {
  plugin.loading = true;
  try {
    await apiClient.delete(`/api/plugins/server/${selectedServerId.value}/${plugin.file_name}`);
    ElMessage.success(`插件 "${plugin.meta.name || plugin.file_name}" 已删除`);
    await initialLoad();
  } catch (error) {
    ElMessage.error(`删除失败: ${error.response?.data?.detail || error.message}`);
    plugin.loading = false;
  }
};

const openAddOnlinePluginDialog = async () => {
  onlinePluginsQuery.value = '';
  onlinePluginsSelected.value = [];
  await fetchOnlinePlugins();
  addOnlinePluginDialogVisible.value = true;
};

const openAddDbPluginDialog = async () => {
  dbPluginsQuery.value = '';
  dbPluginsSelected.value = [];
  await fetchDbPlugins();
  addDbPluginDialogVisible.value = true;
};

const fetchOnlinePlugins = async (force = false) => {
  if (onlinePlugins.value.length > 0 && !force) return;
  onlinePluginsLoading.value = true;
  try {
    const {data} = await apiClient.get('/api/plugins/mcdr/versions');
    const map = data?.plugins || {};
    onlinePlugins.value = Object.keys(map).map(k => {
      const p = map[k];
      const latest = p?.release?.releases?.[0] ?? null;
      return {meta: p.meta, plugin: p.plugin, release: p.release, repository: p.repository, latest};
    }).sort((a, b) => (b.repository?.stargazers_count ?? 0) - (a.repository?.stargazers_count ?? 0));
  } catch (error) {
    ElMessage.error(`加载 MCDR 市场插件失败: ${error.message}`);
  } finally {
    onlinePluginsLoading.value = false;
  }
};

const fetchDbPlugins = async () => {
  dbPluginsLoading.value = true;
  try {
    const {data} = await apiClient.get('/api/plugins/db');
    dbPlugins.value = data || [];
  } catch (error) {
    ElMessage.error(`加载数据库插件失败: ${error.message}`);
  } finally {
    dbPluginsLoading.value = false;
  }
};

const getPluginInstallStatus = (pluginId) => {
  if (!pluginId) return null;
  const installed = currentPlugins.value.find(p => p.meta.id === pluginId);
  return installed ? installed.meta.version : null;
};

const handleOnlineSelectionChange = (selection) => onlinePluginsSelected.value = selection;
const handleDbSelectionChange = (selection) => dbPluginsSelected.value = selection;

const compareVersions = (v1, v2) => {
  if (typeof v1 !== 'string' || typeof v2 !== 'string') return 0;
  const parts1 = v1.replace(/^v/, '').split('-')[0].split('.').map(part => parseInt(part, 10) || 0);
  const parts2 = v2.replace(/^v/, '').split('-')[0].split('.').map(part => parseInt(part, 10) || 0);
  const len = Math.max(parts1.length, parts2.length);
  for (let i = 0; i < len; i++) {
    const p1 = parts1[i] || 0;
    const p2 = parts2[i] || 0;
    if (p1 > p2) return 1;
    if (p1 < p2) return -1;
  }
  return 0;
};

const isUpdateAvailable = (installedPlugin) => {
  if (!installedPlugin.meta.id) return false;
  const onlinePlugin = onlinePluginsMap.value.get(installedPlugin.meta.id);
  if (!onlinePlugin || !onlinePlugin.release?.latest_version || !installedPlugin.meta.version) return false;
  return compareVersions(onlinePlugin.release.latest_version, installedPlugin.meta.version) > 0;
};

const handleUpdatePlugin = async (plugin) => {
  const onlinePlugin = onlinePluginsMap.value.get(plugin.meta.id);
  if (!onlinePlugin) return ElMessage.error("在市场中找不到该插件，无法更新。");
  plugin.loading = true;
  try {
    const latestVersion = onlinePlugin.release.latest_version;
    const url = `/api/plugins/server/${selectedServerId.value}/install/from-online?plugin_id=${encodeURIComponent(plugin.meta.id)}&tag_name=${encodeURIComponent(latestVersion)}`;
    await apiClient.post(url);
    ElNotification({
      title: '更新任务已创建',
      message: `插件 "${plugin.meta.name}" 已加入后台更新队列。`,
      type: 'success'
    });
    setTimeout(initialLoad, 3000); // Refresh all data after a delay
  } catch (error) {
    ElNotification({
      title: '更新请求失败',
      message: `插件 "${plugin.meta.name}": ${error.response?.data?.detail || error.message}`,
      type: 'error',
      duration: 0
    });
  } finally {
    plugin.loading = false;
  }
};

const prepareInstallationConfirmation = () => {
  if (onlinePluginsSelected.value.length === 0) return;
  pluginsToInstall.value = onlinePluginsSelected.value.map(plugin => {
    const availableVersions = plugin.release?.releases?.map(r => r.meta.version || r.tag_name).filter(Boolean) || [];
    const latestVersion = plugin.release?.latest_version;
    return {...plugin, availableVersions, selectedVersion: latestVersion || (availableVersions[0] || null)};
  });
  installConfirmDialogVisible.value = true;
};

const executeInstallation = async () => {
  if (pluginsToInstall.value.length === 0) return;
  isInstallingPlugins.value = true;
  const installPromises = pluginsToInstall.value.map(plugin => {
    const version = plugin.selectedVersion;
    if (!version) return Promise.resolve({name: plugin.meta.name, status: 'rejected', reason: '未选择安装版本'});
    const url = `/api/plugins/server/${selectedServerId.value}/install/from-online?plugin_id=${encodeURIComponent(plugin.meta.id)}&tag_name=${encodeURIComponent(version)}`;
    return apiClient.post(url).then(() => ({
      name: plugin.meta.name,
      status: 'fulfilled'
    })).catch(err => ({name: plugin.meta.name, status: 'rejected', reason: err.response?.data?.detail || err.message}));
  });

  const results = await Promise.all(installPromises);
  let successCount = 0;
  results.forEach(result => {
    if (result.status === 'fulfilled') {
      successCount++;
      ElNotification({title: '安装任务已创建', message: `插件 "${result.name}" 已加入后台安装队列。`, type: 'success'});
    } else {
      ElNotification({
        title: '安装请求失败',
        message: `插件 "${result.name}": ${result.reason}`,
        type: 'error',
        duration: 0
      });
    }
  });

  isInstallingPlugins.value = false;
  if (successCount > 0) {
    installConfirmDialogVisible.value = false;
    addOnlinePluginDialogVisible.value = false;
    setTimeout(initialLoad, 1000);
  }
};

const handleInstallDbPlugins = async () => {
  if (dbPluginsSelected.value.length === 0) return;
  isInstallingPlugins.value = true;
  const installPromises = dbPluginsSelected.value.map(plugin => {
    const url = `/api/plugins/server/${selectedServerId.value}/install/from-db/${plugin.id}`;
    return apiClient.post(url).then(() => ({
      name: plugin.meta.name || plugin.file_name,
      status: 'fulfilled'
    })).catch(err => ({
      name: plugin.meta.name || plugin.file_name,
      status: 'rejected',
      reason: err.response?.data?.detail || err.message
    }));
  });

  const results = await Promise.all(installPromises);
  let successCount = 0;
  results.forEach(result => {
    if (result.status === 'fulfilled') {
      successCount++;
      ElNotification({title: '安装成功', message: `插件 "${result.name}" 已安装。`, type: 'success'});
    } else {
      ElNotification({
        title: '安装失败',
        message: `插件 "${result.name}": ${result.reason}`,
        type: 'error',
        duration: 0
      });
    }
  });

  isInstallingPlugins.value = false;
  if (successCount > 0) {
    addDbPluginDialogVisible.value = false;
    await initialLoad();
  }
};

// --- Lifecycle ---
onMounted(() => {
  initialLoad();
});
</script>

<style scoped>
/* Main layout */
.server-plugin-manager-layout {
  display: flex;
  align-items: stretch; /* 让右侧主视图占满高度，保证可滚动 */
  gap: 16px; /* 与 PB 左右间距一致 */
  /* 与全局头部高度一致，且扣除 el-main 上下各 24px 的内边距 */
  height: calc(100vh - var(--el-header-height) - 48px);
  /* 限制外溢，滚动交由内部区域处理 */
  overflow: hidden;
  min-height: 0;
  background-color: transparent;
}

/* Sidebar */
.server-sidebar {
  background-color: #fff;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 10px;
  overflow: hidden;
}

.sidebar-inner { display: flex; flex-direction: column; }

.sidebar-header {
  padding: 15px;
  border-bottom: 1px solid #e6e6e6;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 刷新按钮样式优化：更轻的文本按钮 + 悬浮色 */
.refresh-btn {
  color: var(--el-text-color-secondary);
}
.refresh-btn:hover {
  color: var(--el-color-primary);
}

.server-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.server-list-item {
  padding: 12px 15px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: background-color 0.2s;
  border-bottom: 1px solid #f0f2f5;
}

.server-list-item:hover {
  background-color: #ecf5ff;
}

.server-list-item.is-active {
  background-color: #d9ecff;
  color: #409EFF;
  font-weight: 500;
}

.server-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 10px;
}

.no-servers-placeholder {
  padding-top: 40px;
}

/* Main Content Area */
.plugin-content-area {
  padding: 0 20px 20px;
  flex: 1 1 auto;
  min-height: 0; /* 允许在父 flex 容器内收缩，避免溢出 */
  overflow: auto; /* 内部滚动 */
  /* 隐藏滚动条但保留滚动功能 */
  scrollbar-width: none;      /* Firefox */
  -ms-overflow-style: none;   /* IE 10+ */
}
.plugin-content-area::-webkit-scrollbar { width: 0; height: 0; }

/* 左侧面板（与 PB 对齐） */
.left-panel { width: 320px; flex-shrink: 0; align-self: flex-start; }
.left-panel { transition: width 0.32s cubic-bezier(.34,1.56,.64,1); will-change: width; overflow: hidden; }
.left-panel :deep(.el-card) { display: block; }
.left-panel :deep(.el-card__body) { padding: 8px; }
.left-panel :deep(.el-input), .left-panel :deep(.el-input__wrapper) { width: 100%; }
.left-panel :deep(.el-table__inner-wrapper) { width: 100%; }
.is-collapsed .left-panel, .is-collapsing .left-panel { width: 0 !important; }
.is-collapsing .left-panel :deep(.el-card__body), .is-collapsing .left-panel :deep(.el-card__header) { display: none !important; }

/* 隐藏 Element Plus 自定义滚动条（左侧 el-scrollbar） */
.server-plugin-manager-layout :deep(.el-scrollbar__bar) { display: none !important; }
.server-plugin-manager-layout :deep(.el-scrollbar__wrap) {
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.server-plugin-manager-layout :deep(.el-scrollbar__wrap::-webkit-scrollbar) { width: 0; height: 0; }

.main-placeholder {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
}

/* Reused Styles & Dialog Styles */
.mb-3 {
  margin-bottom: 12px;
}

.mt-3 {
  margin-top: 12px;
}

.flex {
  display: flex;
}

.items-center {
  align-items: center;
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

.gap-4 {
  gap: 16px;
}

.font-medium {
  font-weight: 500;
}

.text-base {
  font-size: 14px;
}

.plugin-cell-layout {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.plugin-name {
  font-weight: 500;
  line-height: 1.2;
}

.plugin-description {
  font-size: 12px;
  color: #909399;
  line-height: 1.3;
}

.version-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
/* 圆形按钮内图标可见性（当前版本旁刷新按钮） */
.version-cell .el-button.is-circle .el-icon { display: inline-flex; align-items: center; justify-content: center; }
.version-cell .el-button.el-button--primary.is-circle:not(.is-plain) .el-icon { color: #fff; }
.version-cell .el-button.el-button--primary.is-circle.is-plain .el-icon { color: var(--brand-primary); }

.plugin-toolbar {
  display: flex;
  gap: 15px;
  margin-bottom: 15px;
  align-items: center;
}

/* 表格圆角统一样式 */
.rounded-table {
  border-radius: 8px;
  overflow: hidden;
}

:deep(.disabled-plugin-row) {
  color: #a8abb2;
  background-color: #fafafa;
}

:deep(.disabled-plugin-row:hover > td) {
  background-color: #f5f5f5 !important;
}
</style>
