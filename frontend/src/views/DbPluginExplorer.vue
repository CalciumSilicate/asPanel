<template>
  <div class="db-plugin-manager">
    <!-- Toolbar -->
    <el-card shadow="never" class="mb-3">
      <template #header>
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <span class="text-base font-medium">数据库插件库</span>
            <el-tag type="info" v-if="items.length">共 {{ items.length }} 个插件</el-tag>
          </div>
          <div class="flex items-center gap-2">
            <el-button-group>
              <el-button :loading="loading" type="primary" @click="load">
                <el-icon class="mr-1">
                  <Refresh/>
                </el-icon>
                刷新
              </el-button>
              <el-button type="success" @click="uploadDialogVisible = true">
                <el-icon class="mr-1">
                  <UploadFilled/>
                </el-icon>
                上传插件
              </el-button>
            </el-button-group>
          </div>
        </div>
      </template>

      <div class="flex">
        <el-input
            v-model="query"
            placeholder="搜索：名称 / 文件名"
            clearable
            style="max-width: 400px;"
            @input="handleSearch"
        >
          <template #prefix>
            <el-icon>
              <Search/>
            </el-icon>
          </template>
        </el-input>
      </div>
    </el-card>

    <!-- List -->
    <div class="table-card">
      <el-table :data="paged" v-loading="loading" stripe size="small" height="60vh">
      <el-table-column label="插件" min-width="260">
        <template #default="{ row }">
          <div class="flex items-start gap-2">
            <el-tag type="primary" effect="plain" size="small" v-if="row.meta.id">{{ row.meta.id }}</el-tag>
            <div>
              <div class="font-medium leading-5">{{ row.meta.name || '未知名称' }}</div>
              <div class="text-xs text-gray-500 leading-4">{{ row.file_name }}</div>
            </div>
          </div>
        </template>
      </el-table-column>

      <el-table-column prop="meta.version" label="版本" width="130">
        <template #default="{ row }">
          <el-tag v-if="row.meta.version" size="small" type="success">{{ row.meta.version }}</el-tag>
          <el-tag v-else size="small" type="info">未知</el-tag>
        </template>
      </el-table-column>

      <el-table-column label="作者" min-width="160">
        <template #default="{ row }">
          <el-space wrap>
            <el-tag v-for="a in getAuthorsArray(row.meta)" :key="a" size="small">{{ a }}</el-tag>
            <span v-if="getAuthorsArray(row.meta).length === 0"><el-tag size="small" type="info">未知</el-tag></span>
          </el-space>
        </template>
      </el-table-column>

      <el-table-column label="文件大小" width="120" align="center">
        <template #default="{ row }">
          <span>{{ (row.size / 1024).toFixed(1) }} KB</span>
        </template>
      </el-table-column>

      <!-- [MODIFIED] 操作列 -->
      <el-table-column label="操作" width="280" align="center">
        <template #default="{ row }">
          <el-button-group>
            <el-button size="small" type="primary" :icon="Download" @click="handleInstallClick(row)">
              安装
            </el-button>
            <el-button size="small" type="warning" :icon="Remove" @click="handleUninstallClick(row)">
              卸载
            </el-button>
            <el-popconfirm
                title="确定要从数据库中永久删除这个插件吗？"
                width="250"
                @confirm="handleDelete(row)"
            >
              <template #reference>
                <el-button size="small" type="danger" :icon="Delete">删除</el-button>
              </template>
            </el-popconfirm>
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
          @current-change="(p) => page = p"
          @size-change="(s) => { pageSize = s; page = 1; }"
      />
    </div>

    <!-- Upload Dialog -->
    <el-dialog v-model="uploadDialogVisible" title="上传插件到数据库" width="500px">
      <el-upload
          ref="uploadRef"
          drag
          :http-request="customUploadRequest"
          :limit="1"
          :on-exceed="handleExceed"
          :on-success="handleUploadSuccess"
          :on-error="handleUploadError"
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
          <el-button type="primary" @click="submitUpload" :loading="isUploading">
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
// [MODIFIED] Import Remove icon
import {Search, Refresh, UploadFilled, Download, Delete, Remove} from '@element-plus/icons-vue';
import apiClient from '@/api';

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

// 使用 apiClient 的自定义上传请求，统一走拦截器与基地址
const customUploadRequest = async (options) => {
  try {
    const formData = new FormData();
    formData.append('file', options.file);
    const res = await apiClient.post('/api/plugins/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (e && e.total) {
          const percent = Math.round((e.loaded / e.total) * 100);
          options.onProgress && options.onProgress({ percent });
        }
      },
    });
    options.onSuccess && options.onSuccess(res.data);
  } catch (err) {
    options.onError && options.onError(err);
  }
};

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
    ElMessage.error('加载数据库插件列表失败: ' + (error.response?.data?.detail || error.message));
  } finally {
    loading.value = false;
  }
};

const fetchServers = async () => {
  try {
    const {data} = await apiClient.get('/api/servers');
    servers.value = data;
  } catch (error) {
    ElMessage.error('加载服务器列表失败: ' + (error.response?.data?.detail || error.message));
  }
};

const handleSearch = () => {
  page.value = 1;
};

// Upload Logic
const submitUpload = () => {
  if (uploadRef.value) {
    isUploading.value = true;
    uploadRef.value.submit();
  }
};

const handleExceed = (files) => {
  uploadRef.value.clearFiles();
  const file = files[0];
  uploadRef.value.handleStart(file);
};

const handleUploadSuccess = (response, uploadFile) => {
  ElMessage.success(`插件 ${response.file_name} 上传成功!`);
  isUploading.value = false;
  uploadDialogVisible.value = false;
  uploadRef.value.clearFiles();
  load();
};

const handleUploadError = (error, uploadFile) => {
  isUploading.value = false;
  try {
    const errData = JSON.parse(error.message);
    ElMessage.error(`上传失败: ${errData.detail || '未知错误'}`);
  } catch (e) {
    ElMessage.error(`上传失败: ${error.message}`);
  }
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
/* Scoped styles from MCDRPluginExplorer.vue for consistency */
.db-plugin-manager :deep(.el-card__header) {
  padding: 10px 16px;
}

.mb-3 {
  margin-bottom: 12px;
}

.text-gray-500 {
  color: #909399;
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

.mt-3 {
  margin-top: 12px;
}

.mt-4 {
  margin-top: 16px;
}

.mb-2 {
  margin-bottom: 8px;
}

.mr-1 {
  margin-right: 4px;
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

.w-full {
  width: 100%;
}

/* 表格圆角统一样式 */
.rounded-table {
  border-radius: 8px;
  overflow: hidden;
}
/* 让本页占满可用高度，内部滚动不外溢到整个页面 */
.db-plugin-manager {
  /* 占满可视区域（减去头部高度），避免出现页面级滚动条 */
  height: calc(100vh - var(--el-header-height));
  overflow: auto; /* 允许内部滚动 */
  box-sizing: border-box;
  scrollbar-gutter: stable;
  scrollbar-width: thin;
}
.db-plugin-manager :deep(.el-scrollbar__bar) { opacity: 0.9; }
.db-plugin-manager :deep(.el-dialog__body) { max-height: 70vh; overflow: auto; }

</style>
