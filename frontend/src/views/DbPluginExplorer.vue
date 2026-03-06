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
                  <el-popconfirm title="确定要从数据库中永久删除这个插件吗？" width="250" @confirm="handleDelete(row)">
                    <template #reference>
                      <button class="act-btn act-delete"><el-icon :size="11"><Delete /></el-icon>删除</button>
                    </template>
                  </el-popconfirm>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Footer pagination -->
      <div class="db-footer">
        <el-pagination
          background
          layout="prev, pager, next, sizes, total"
          :page-sizes="[10, 20, 50, 100]"
          :page-size="pageSize"
          :current-page="page"
          :total="filtered.length"
          @current-change="(p) => page = p"
          @size-change="(s) => { pageSize = s; page = 1; }"
        />
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
    <el-dialog v-model="installDialogVisible" title="安装插件到服务器" width="600px" destroy-on-close>
      <div v-if="activePlugin">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="插件名称">{{
              activePlugin.meta.name || activePlugin.file_name
            }}
          </el-descriptions-item>
          <el-descriptions-item label="安装版本">{{ activePlugin.meta.version || '未知' }}</el-descriptions-item>
        </el-descriptions>

        <div class="mt-4">
          <p class="mb-2 font-medium">选择要安装的服务器:</p>
          <el-select
              v-model="selectedServersForInstall"
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
                    :type="getPluginStatusForServer(server, activePlugin.meta.id).type"
                    effect="light"
                >
                  {{ getPluginStatusForServer(server, activePlugin.meta.id).text }}
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

    <!-- [NEW] Uninstall Dialog -->
    <el-dialog v-model="uninstallDialogVisible" title="从服务器卸载插件" width="600px" destroy-on-close>
      <div v-if="activePlugin">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="插件名称">{{
              activePlugin.meta.name || activePlugin.file_name
            }}
          </el-descriptions-item>
          <el-descriptions-item label="插件ID">{{ activePlugin.meta.id || '未知' }}</el-descriptions-item>
        </el-descriptions>

        <div class="mt-4">
          <p class="mb-2 font-medium">选择要卸载此插件的服务器:</p>
          <el-alert v-if="serversWithPluginInstalled.length === 0 && !isFetchingServerPlugins"
                    title="当前没有服务器安装了此插件。" type="info" :closable="false" show-icon/>
          <el-select
              v-else
              v-model="selectedServersForUninstall"
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
                    :type="getPluginStatusForServer(server, activePlugin.meta.id).type"
                    effect="light"
                >
                  {{ getPluginStatusForServer(server, activePlugin.meta.id).text }}
                </el-tag>
              </div>
            </el-option>
          </el-select>
          <!--          <el-checkbox-group v-model="selectedServersForUninstall" v-loading="isFetchingServerPlugins">-->
          <!--              <el-checkbox-->
          <!--                v-for="server in serversWithPluginInstalled"-->
          <!--                :key="server.id"-->
          <!--                :label="server.id"-->
          <!--                border-->
          <!--                class="w-full mb-2"-->
          <!--              >-->
          <!--                {{ server.name }} (文件名: {{ server.fileName }})-->
          <!--              </el-checkbox>-->
          <!--          </el-checkbox-group>-->
        </div>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="uninstallDialogVisible = false">取消</el-button>
          <el-button type="danger" @click="confirmUninstall" :loading="isUninstalling"
                     :disabled="serversWithPluginInstalled.length === 0">
            确认卸载
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import {ref, computed, onMounted} from 'vue';
import {ElMessage, ElNotification} from 'element-plus';
import {Search, Refresh, UploadFilled, Download, Delete, Remove} from '@element-plus/icons-vue';
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
.db-footer {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 10px 20px;
  border-top: 1px solid rgba(119, 181, 254, 0.12);
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
</style>
