<template>
  <div class="db-page">

    <!-- Glass toolbar -->
    <div class="db-toolbar">
      <div class="db-toolbar-left">
        <span class="db-title">数据库插件库</span>
        <el-tag type="info" v-if="items.length" size="small">共 {{ items.length }} 个</el-tag>
        <div class="toolbar-divider" />
        <div class="search-wrap">
          <el-input v-model="query" placeholder="搜索：名称 / 文件名" clearable class="search-input" @input="handleSearch">
            <template #prefix><el-icon style="color:var(--brand-primary)"><Search /></el-icon></template>
          </el-input>
        </div>
      </div>
      <div class="db-toolbar-right">
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
        <button class="btn-ghost" @click="load">
          <el-icon :size="13"><Refresh /></el-icon><span>刷新</span>
        </button>
        <button class="btn-upload" @click="uploadDialogVisible = true">
          <el-icon :size="13"><UploadFilled /></el-icon><span>上传插件</span>
        </button>
      </div>
    </div>

    <!-- Glass card -->
    <div class="db-glass-card">
      <div class="shimmer-line" aria-hidden="true" />

      <!-- Table -->
      <div class="db-table-wrap" v-loading="loading" element-loading-background="transparent">
        <table class="native-table">
          <colgroup>
            <col style="min-width:280px" />
            <col style="width:130px" />
            <col style="min-width:160px" />
            <col style="width:110px" />
            <col style="width:260px" />
          </colgroup>
          <thead>
            <tr class="thead-row">
              <th class="th-cell">插件</th>
              <th class="th-cell">版本</th>
              <th class="th-cell">作者</th>
              <th class="th-cell th-center">文件大小</th>
              <th class="th-cell th-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!loading && paged.length === 0">
              <td colspan="5" class="td-empty">
                <el-empty description="暂无插件" :image-size="80" />
              </td>
            </tr>
            <tr v-for="row in paged" :key="row.id" class="tbl-row">
              <td class="td-cell">
                <PluginNameCell
                  :id="row.meta.id"
                  :name="row.meta.name"
                  :filename="row.file_name"
                />
              </td>
              <td class="td-cell">
                <el-tag v-if="row.meta.version" size="small" type="success">{{ row.meta.version }}</el-tag>
                <el-tag v-else size="small" type="info">未知</el-tag>
              </td>
              <td class="td-cell">
                <AuthorTagsCell :authors="getAuthorsArray(row.meta)" />
              </td>
              <td class="td-cell td-center">
                <span class="size-cell">{{ (row.size / 1024).toFixed(1) }} KB</span>
              </td>
              <td class="td-cell td-right">
                <div class="row-actions">
                  <button class="act-btn act-install" @click="handleInstallClick(row)">
                    <el-icon :size="11"><Download /></el-icon>安装
                  </button>
                  <button class="act-btn act-uninstall" @click="handleUninstallClick(row)">
                    <el-icon :size="11"><Remove /></el-icon>卸载
                  </button>
                  <button class="act-btn act-delete" @click="openDeleteConfirm(row)">
                    <el-icon :size="11"><Delete /></el-icon>删除
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Upload Dialog -->
    <el-dialog v-model="uploadDialogVisible" title="上传插件到数据库" width="500px">
      <el-upload
          ref="uploadRef"
          drag
          :limit="1"
          :on-exceed="handleExceed"
          :auto-upload="false"
          accept=".py,.pyz,.zip,.mcdr"
      >
        <el-icon class="el-icon--upload">
          <upload-filled/>
        </el-icon>
        <div class="el-upload__text">
          拖拽文件到此处或 <em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            请上传 .py, .pyz, .mcdr 或 .zip 格式的插件文件
          </div>
        </template>
      </el-upload>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="uploadDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitUpload">
            确认上传
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- Install Dialog -->
    <el-dialog v-model="installDialogVisible" width="540px" destroy-on-close append-to-body
               class="db-action-dialog" :show-close="false">
      <template #header>
        <div class="adlg-head">
          <div class="adlg-icon adlg-icon--install">
            <el-icon :size="17"><Upload /></el-icon>
          </div>
          <div class="adlg-title-group">
            <span class="adlg-title">安装插件到服务器</span>
            <span class="adlg-subtitle" v-if="activePlugin">
              {{ activePlugin.meta.name || activePlugin.file_name }}
              <span class="adlg-version">{{ activePlugin.meta.version || '未知版本' }}</span>
            </span>
          </div>
          <button class="adlg-close-btn" @click="installDialogVisible = false">
            <el-icon :size="13"><Close /></el-icon>
          </button>
        </div>
      </template>

      <div v-if="activePlugin" class="adlg-body">
        <div class="adlg-section-label">选择目标服务器</div>
        <el-select v-model="selectedServersForInstall" multiple filterable placeholder="请选择服务器"
                   style="width:100%" :loading="isFetchingServerPlugins">
          <el-option v-for="server in servers" :key="server.id" :label="server.name" :value="server.id">
            <div class="adlg-server-opt">
              <span>{{ server.name }}</span>
              <el-tag size="small" :type="getPluginStatusForServer(server, activePlugin.meta.id).type" effect="light">
                {{ getPluginStatusForServer(server, activePlugin.meta.id).text }}
              </el-tag>
            </div>
          </el-option>
        </el-select>
      </div>

      <template #footer>
        <div class="adlg-footer">
          <button class="adlg-btn-ghost" @click="installDialogVisible = false">取消</button>
          <button class="adlg-btn-primary" :disabled="isInstalling || selectedServersForInstall.length === 0" @click="confirmInstall">
            <el-icon v-if="isInstalling" class="is-loading" :size="13"><Refresh /></el-icon>
            <el-icon v-else :size="13"><Upload /></el-icon>
            {{ isInstalling ? '安装中…' : '确认安装' }}
          </button>
        </div>
      </template>
    </el-dialog>

    <!-- Uninstall Dialog -->
    <el-dialog v-model="uninstallDialogVisible" width="540px" destroy-on-close append-to-body
               class="db-action-dialog" :show-close="false">
      <template #header>
        <div class="adlg-head">
          <div class="adlg-icon adlg-icon--uninstall">
            <el-icon :size="17"><Remove /></el-icon>
          </div>
          <div class="adlg-title-group">
            <span class="adlg-title">从服务器卸载插件</span>
            <span class="adlg-subtitle" v-if="activePlugin">
              {{ activePlugin.meta.name || activePlugin.file_name }}
              <span v-if="activePlugin.meta.id" class="adlg-version">{{ activePlugin.meta.id }}</span>
            </span>
          </div>
          <button class="adlg-close-btn" @click="uninstallDialogVisible = false">
            <el-icon :size="13"><Close /></el-icon>
          </button>
        </div>
      </template>

      <div v-if="activePlugin" class="adlg-body">
        <el-alert v-if="serversWithPluginInstalled.length === 0 && !isFetchingServerPlugins"
                  title="当前没有服务器安装了此插件。" type="info" :closable="false" show-icon />
        <template v-else>
          <div class="adlg-section-label">选择要卸载此插件的服务器</div>
          <el-select v-model="selectedServersForUninstall" multiple filterable placeholder="请选择服务器"
                     style="width:100%" :loading="isFetchingServerPlugins">
            <el-option v-for="server in servers" :key="server.id" :label="server.name" :value="server.id">
              <div class="adlg-server-opt">
                <span>{{ server.name }}</span>
                <el-tag size="small" :type="getPluginStatusForServer(server, activePlugin.meta.id).type" effect="light">
                  {{ getPluginStatusForServer(server, activePlugin.meta.id).text }}
                </el-tag>
              </div>
            </el-option>
          </el-select>
        </template>
      </div>

      <template #footer>
        <div class="adlg-footer">
          <button class="adlg-btn-ghost" @click="uninstallDialogVisible = false">取消</button>
          <button class="adlg-btn-danger" :disabled="isUninstalling || serversWithPluginInstalled.length === 0" @click="confirmUninstall">
            <el-icon v-if="isUninstalling" class="is-loading" :size="13"><Refresh /></el-icon>
            <el-icon v-else :size="13"><Remove /></el-icon>
            {{ isUninstalling ? '卸载中…' : '确认卸载' }}
          </button>
        </div>
      </template>
    </el-dialog>
    <!-- Delete Confirm Dialog -->
    <el-dialog v-if="deleteConfirmVisible" v-model="deleteConfirmVisible"
               width="420px" top="30vh" destroy-on-close append-to-body
               class="db-action-dialog" :show-close="false">
      <template #header>
        <div class="adlg-head">
          <div class="adlg-icon adlg-icon--uninstall">
            <el-icon :size="17"><Delete /></el-icon>
          </div>
          <div class="adlg-title-group">
            <span class="adlg-title">永久删除插件</span>
            <span class="adlg-subtitle">插件文件将从数据库中移除，不可撤销</span>
          </div>
          <button class="adlg-close-btn" @click="deleteConfirmVisible = false">
            <el-icon :size="13"><Close /></el-icon>
          </button>
        </div>
      </template>
      <div class="adlg-body" style="gap:6px">
        <div style="font-size:14px;font-weight:700;color:var(--color-text)">
          {{ pluginToDelete?.meta?.name || pluginToDelete?.file_name }}
        </div>
        <div style="font-size:12px;color:var(--el-text-color-secondary)">
          文件：<span style="font-family:'Maple Mono',ui-monospace,monospace;font-size:11px;background:rgba(248,113,113,0.08);border-radius:4px;padding:1px 5px">{{ pluginToDelete?.file_name }}</span>
        </div>
      </div>
      <template #footer>
        <div class="adlg-footer">
          <button class="adlg-btn-ghost" @click="deleteConfirmVisible = false">取消</button>
          <button class="adlg-btn-danger" :disabled="isDeleting" @click="executeDelete">
            <el-icon v-if="isDeleting" class="is-loading" :size="13"><Refresh /></el-icon>
            <el-icon v-else :size="13"><Delete /></el-icon>
            {{ isDeleting ? '删除中…' : '确认删除' }}
          </button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import {ref, computed, onMounted} from 'vue';
import {ElMessage, ElNotification} from 'element-plus';
import {Search, Refresh, UploadFilled, Upload, Download, Delete, Remove, ArrowLeft, ArrowRight, Close} from '@element-plus/icons-vue';
import PluginNameCell from '@/components/PluginNameCell.vue';
import AuthorTagsCell from '@/components/AuthorTagsCell.vue';
import apiClient, { isRequestCanceled } from '@/api';
import { useTasksStore } from '@/store/tasks'
import { useTransfersStore } from '@/store/transfers'
const { fetchTasks } = useTasksStore()
const { startUpload } = useTransfersStore()

// --- State ---
const loading = ref(false);
const items = ref([]);
const servers = ref([]);
const query = ref('');
const page = ref(1);
const pageSize = ref(20);
const activePlugin = ref(null);
const serverPlugins = ref(new Map());
const isFetchingServerPlugins = ref(false);

// Upload Dialog
const uploadDialogVisible = ref(false);
const isUploading = ref(false);
const uploadRef = ref(null);

// Install Dialog
const installDialogVisible = ref(false);
const isInstalling = ref(false);
const selectedServersForInstall = ref([]);

// [NEW] Uninstall Dialog State
const uninstallDialogVisible = ref(false);
const isUninstalling = ref(false);
const selectedServersForUninstall = ref([]);

// --- Computed ---
const filtered = computed(() => {
  if (!query.value.trim()) {
    return items.value;
  }
  const q = query.value.toLowerCase();
  return items.value.filter(item =>
      (item.meta.name && item.meta.name.toLowerCase().includes(q)) ||
      (item.file_name && item.file_name.toLowerCase().includes(q))
  );
});

const paged = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return filtered.value.slice(start, start + pageSize.value);
});

// [NEW] Computed property to find servers where the active plugin is installed
const serversWithPluginInstalled = computed(() => {
  if (!activePlugin.value?.meta?.id) return [];
  const pluginId = activePlugin.value.meta.id;
  const result = [];

  for (const [serverId, plugins] of serverPlugins.value.entries()) {
    const installedPlugin = plugins.find(p => p.meta?.id === pluginId);
    if (installedPlugin) {
      const serverInfo = servers.value.find(s => s.id === serverId);
      if (serverInfo) {
        result.push({
          id: serverId,
          name: serverInfo.name,
          fileName: installedPlugin.file_name, // Crucial for the DELETE API call
        });
      }
    }
  }
  return result;
});


// --- Methods ---
const getAuthorsArray = (meta) => {
  if (!meta) return [];
  if (meta.authors && Array.isArray(meta.authors)) return meta.authors.filter(Boolean);
  if (meta.author) {
    if (Array.isArray(meta.author)) return meta.author.filter(Boolean);
    if (typeof meta.author === 'string') return [meta.author];
  }
  return [];
};

const load = async () => {
  loading.value = true;
  try {
    const {data} = await apiClient.get('/api/plugins/db');
    items.value = data.sort((a, b) => (b.id - a.id));
  } catch (error) {
    if (!isRequestCanceled(error)) ElMessage.error('加载数据库插件列表失败: ' + (error.response?.data?.detail || error.message));
  } finally {
    loading.value = false;
  }
};

const fetchServers = async () => {
  try {
    const {data} = await apiClient.get('/api/servers');
    servers.value = data;
  } catch (error) {
    if (!isRequestCanceled(error)) ElMessage.error('加载服务器列表失败: ' + (error.response?.data?.detail || error.message));
  }
};

const handleSearch = () => {
  page.value = 1;
};

// 使用 transfers store 的 startUpload 进行非阻塞上传
const submitUpload = async () => {
  if (!uploadRef.value) return
  const uploadInstance = uploadRef.value
  const fileList = uploadInstance.uploadFiles
  if (!fileList || fileList.length === 0) {
    ElMessage.warning('请先选择要上传的文件')
    return
  }
  
  const file = fileList[0]?.raw
  if (!file) {
    ElMessage.warning('请先选择要上传的文件')
    return
  }
  
  uploadDialogVisible.value = false
  uploadInstance.clearFiles()
  
  const formData = new FormData()
  formData.append('file', file)
  
  const { id, response, error } = await startUpload({
    url: '/api/plugins/upload',
    data: formData,
    title: file.name || '插件上传',
    filename: file.name,
  })
  
  if (error) {
    ElMessage.error(`上传失败: ${error}`)
  } else {
    ElMessage.success(`插件 ${response?.file_name || file.name} 上传成功!`)
    fetchTasks().catch(() => {})
    load()
  }
}

const handleExceed = (files) => {
  uploadRef.value.clearFiles()
  const file = files[0]
  uploadRef.value.handleStart(file)
};

// Delete Logic
const handleDelete = async (plugin) => {
  try {
    await apiClient.delete(`/api/plugins/db/${plugin.id}`);
    ElMessage.success(`插件 "${plugin.meta.name || plugin.file_name}" 已从数据库删除`);
    load();
  } catch (error) {
    ElMessage.error('删除失败: ' + (error.response?.data?.detail || error.message));
  }
};

const deleteConfirmVisible = ref(false);
const pluginToDelete = ref(null);
const isDeleting = ref(false);
function openDeleteConfirm(plugin) {
  pluginToDelete.value = plugin;
  deleteConfirmVisible.value = true;
}
async function executeDelete() {
  if (!pluginToDelete.value) return;
  isDeleting.value = true;
  await handleDelete(pluginToDelete.value);
  isDeleting.value = false;
  deleteConfirmVisible.value = false;
}

// Common plugin status logic
const fetchAllServerPlugins = async () => {
  isFetchingServerPlugins.value = true;
  serverPlugins.value.clear();
  const promises = servers.value.map(async (server) => {
    try {
      const {data} = await apiClient.get(`/api/plugins/server/${server.id}`);
      serverPlugins.value.set(server.id, data.data || []);
    } catch (e) {
      console.warn(`无法加载服务器 ${server.name} 的插件:`, e);
      serverPlugins.value.set(server.id, []);
    }
  });
  try {
    await Promise.all(promises);
  } finally {
    isFetchingServerPlugins.value = false;
  }
};

const getPluginStatusForServer = (server, pluginId) => {
  if (!pluginId) return {text: '未知ID', type: 'warning'};
  const installedList = serverPlugins.value.get(server.id);
  if (isFetchingServerPlugins.value || !installedList) {
    return {text: '加载中...', type: 'info'};
  }
  const installedPlugin = installedList.find(p => p.meta.id === pluginId);
  return installedPlugin
      ? {text: `已安装 (${installedPlugin.meta.version})`, type: 'success'}
      : {text: '未安装', type: 'info'};
};

// Install Logic
const handleInstallClick = async (plugin) => {
  activePlugin.value = plugin;
  selectedServersForInstall.value = [];
  await fetchAllServerPlugins();
  installDialogVisible.value = true;
};

const confirmInstall = async () => {
  if (selectedServersForInstall.value.length === 0) {
    return ElMessage.warning('请至少选择一个服务器');
  }
  if (!activePlugin.value) return;

  isInstalling.value = true;
  const pluginId = activePlugin.value.id;
  const installPromises = selectedServersForInstall.value.map(serverId => {
    const serverName = servers.value.find(s => s.id === serverId)?.name || `ID ${serverId}`;
    return apiClient.post(`/api/plugins/server/${serverId}/install/from-db/${pluginId}`)
        .then(() => ({serverName, status: 'fulfilled'}))
        .catch(err => ({serverName, status: 'rejected', reason: err.response?.data?.detail || err.message}));
  });
  const results = await Promise.all(installPromises);
  results.forEach(result => {
    if (result.status === 'fulfilled') {
      ElNotification({title: '安装成功', message: `插件已成功安装到服务器 [${result.serverName}]。`, type: 'success'});
    } else {
      ElNotification({
        title: '安装失败',
        message: `为 [${result.serverName}] 安装失败: ${result.reason}`,
        type: 'error'
      });
    }
  });

  isInstalling.value = false;
  installDialogVisible.value = false;
  fetchTasks().catch(() => {});
  await fetchAllServerPlugins(); // Refresh status after installation
};

// [NEW] Uninstall Logic
const handleUninstallClick = async (plugin) => {
  activePlugin.value = plugin;
  selectedServersForUninstall.value = [];
  await fetchAllServerPlugins();
  uninstallDialogVisible.value = true;
};

const confirmUninstall = async () => {
  if (selectedServersForUninstall.value.length === 0) {
    return ElMessage.warning('请至少选择一个要卸载的服务器');
  }
  if (!activePlugin.value) return;

  isUninstalling.value = true;

  const uninstallPromises = selectedServersForUninstall.value.map(serverId => {
    const serverData = serversWithPluginInstalled.value.find(s => s.id === serverId);
    if (!serverData) {
      return Promise.resolve({
        serverName: `ID ${serverId}`,
        status: 'rejected',
        reason: '未找到服务器的插件信息'
      });
    }

    const {name: serverName, fileName} = serverData;
    return apiClient.delete(`/api/plugins/server/${serverId}/${fileName}`)
        .then(() => ({serverName, status: 'fulfilled'}))
        .catch(err => ({serverName, status: 'rejected', reason: err.response?.data?.detail || err.message}));
  });

  const results = await Promise.all(uninstallPromises);
  results.forEach(result => {
    if (result.status === 'fulfilled') {
      ElNotification({title: '卸载成功', message: `已从服务器 [${result.serverName}] 卸载插件。`, type: 'success'});
    } else {
      ElNotification({
        title: '卸载失败',
        message: `从 [${result.serverName}] 卸载失败: ${result.reason}`,
        type: 'error'
      });
    }
  });

  isUninstalling.value = false;
  uninstallDialogVisible.value = false;
  await fetchAllServerPlugins(); // Refresh status after uninstallation
};


onMounted(() => {
  load();
  fetchServers();
});
</script>

<style scoped>
/* ── Page layout ──────────────────────────────────────────── */
.db-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: calc(100vh - var(--el-header-height) - 48px);
  overflow: hidden;
  min-height: 0;
}

/* ── Glass toolbar ───────────────────────────────────────── */
.db-toolbar {
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
.db-toolbar:hover {
  border-color: rgba(119, 181, 254, 0.28);
  box-shadow: 0 6px 32px rgba(119, 181, 254, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.85);
}
:global(.dark) .db-toolbar {
  background: rgba(15, 23, 42, 0.68);
  border-color: rgba(119, 181, 254, 0.12);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}
.db-toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1 1 auto;
  min-width: 0;
  flex-wrap: wrap;
}
.db-toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.db-title {
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
.search-wrap { flex: 1 1 auto; min-width: 180px; max-width: 300px; }
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

.btn-ghost {
  display: inline-flex; align-items: center; gap: 6px;
  height: 34px; padding: 0 14px; border-radius: 22px;
  border: 1px solid rgba(119,181,254,0.28);
  background: rgba(119,181,254,0.08);
  color: var(--brand-primary); font-size: 12px; font-weight: 600;
  font-family: inherit; cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease, transform 0.18s ease;
}
.btn-ghost:hover { background: rgba(119,181,254,0.16); border-color: rgba(119,181,254,0.50); transform: translateY(-1px); }

.btn-upload {
  display: inline-flex; align-items: center; gap: 7px;
  height: 34px; padding: 0 16px; border-radius: 22px; border: none;
  cursor: pointer; font-size: 13px; font-weight: 600; font-family: inherit; color: #fff;
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  box-shadow: 0 4px 14px rgba(16,185,129,0.35);
  transition: box-shadow 0.25s ease, transform 0.25s cubic-bezier(.34,1.56,.64,1);
}
.btn-upload:hover { box-shadow: 0 6px 22px rgba(16,185,129,0.55); transform: translateY(-1px) scale(1.04); }

/* ── Glass card ──────────────────────────────────────────── */
.db-glass-card {
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
.db-glass-card:hover {
  border-color: rgba(119, 181, 254, 0.28);
  box-shadow: 0 8px 40px rgba(119, 181, 254, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.80);
}
:global(.dark) .db-glass-card {
  background: rgba(15, 23, 42, 0.65);
  border-color: rgba(119, 181, 254, 0.12);
  box-shadow: 0 4px 32px rgba(0, 0, 0, 0.40), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.shimmer-line {
  height: 3px;
  flex-shrink: 0;
  background: linear-gradient(90deg, transparent, rgba(119,181,254,0.7), rgba(16,185,129,0.5), rgba(119,181,254,0.7), transparent);
  background-size: 200% 100%;
  animation: shimmer-slide 4s linear infinite;
  border-radius: 3px 3px 0 0;
  pointer-events: none;
}
@keyframes shimmer-slide {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.db-table-wrap {
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

/* ── Cell styles ─────────────────────────────────────────── */
.size-cell {
  font-family: 'Maple Mono', ui-monospace, monospace;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

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
.act-install { background: linear-gradient(135deg, var(--brand-primary), #a78bfa); color: #fff; border-color: transparent; }
.act-install:hover { box-shadow: 0 4px 12px rgba(119,181,254,0.40); transform: translateY(-1px); }
.act-uninstall:hover { background: rgba(245,158,11,0.10); color: #f59e0b; border-color: rgba(245,158,11,0.30); }
.act-delete:hover { background: rgba(248,113,113,0.10); color: #ef4444; border-color: rgba(248,113,113,0.30); }

/* ── Utility classes used in dialogs ─────────────────────── */
.flex { display: flex; }
.items-center { align-items: center; }
.justify-between { justify-content: space-between; }
.items-start { align-items: flex-start; }
.w-full { width: 100%; }
.mt-4 { margin-top: 16px; }
.mb-2 { margin-bottom: 8px; }
.font-medium { font-weight: 500; }

/* ── Action Dialogs (install / uninstall) ────────────────── */
:global(.db-action-dialog) {
  border-radius: 20px !important; overflow: hidden;
  background: rgba(255,255,255,0.90) !important;
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(119,181,254,0.18) !important;
  box-shadow: 0 20px 60px rgba(0,0,0,0.16), 0 4px 20px rgba(119,181,254,0.12) !important;
}
:global(.dark .db-action-dialog) { background: rgba(15,23,42,0.90) !important; border-color: rgba(119,181,254,0.14) !important; }
:global(.db-action-dialog .el-dialog__header) { padding: 0 !important; margin-right: 0 !important; }
:global(.db-action-dialog .el-dialog__body)   { padding: 0 !important; }
:global(.db-action-dialog .el-dialog__footer) { padding: 0 !important; }

.adlg-head {
  display: flex; align-items: center; gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(119,181,254,0.10);
}
.adlg-icon {
  width: 36px; height: 36px; border-radius: 10px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; color: #fff;
}
.adlg-icon--install   { background: linear-gradient(135deg, var(--brand-primary) 0%, #a78bfa 100%); }
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
.adlg-btn-danger {
  display: inline-flex; align-items: center; gap: 6px;
  height: 34px; padding: 0 18px; border-radius: 10px; border: none; font-family: inherit;
  cursor: pointer; font-size: 13px; font-weight: 600; color: #fff;
  background: linear-gradient(135deg, #f59e0b 0%, #ef4444 100%);
  box-shadow: 0 4px 14px rgba(239,68,68,0.30);
  transition: box-shadow 0.2s ease, transform 0.2s cubic-bezier(.34,1.56,.64,1);
}
.adlg-btn-danger:hover:not(:disabled) { box-shadow: 0 6px 22px rgba(239,68,68,0.45); transform: translateY(-1px); }
.adlg-btn-danger:disabled { opacity: 0.42; cursor: not-allowed; box-shadow: none; }
</style>
