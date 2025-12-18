<template>
  <div class="archive-page">
    <div class="left-wrap">
      <div class="left-panel">
        <!-- 顶栏操作区：移除“上传新存档”，仅保留批量删除 -->
        <el-card shadow="never" class="header-card">
          <div class="flex items-center justify-between">
            <span>管理您的服务器存档和上传的存档</span>
            <span>
              <el-button-group>
                <el-button
                    type="danger"
                    :icon="Delete"
                    @click="handleBulkDelete"
                    :disabled="selectedIds.length === 0"
                >
                  批量删除 ({{ selectedIds.length }})
                </el-button>
              </el-button-group>
            </span>
          </div>
        </el-card>

    <!-- 进行中的任务 (无变化) -->
        <el-card shadow="never" v-if="processingTasks.length > 0">
      <template #header>
        <div class="card-header">
          <span>进行中的任务</span>
        </div>
      </template>
      <div class="processing-tasks-list">
        <div v-for="task in processingTasks" :key="task.id" class="task-item">
          <div class="task-info">
            <span class="task-message">
              {{ task.status === 'FAILED' ? task.error : (task.message || `任务 (ID: ${task.id}) 正在排队...`) }}
            </span>
            <span class="task-status">{{ task.status }}</span>
          </div>
          <el-progress
              :percentage="task.progress"
              :status="task.status === 'FAILED' ? 'exception' : (task.status === 'SUCCESS' ? 'success' : '')"
              :stroke-width="10"
              striped
              striped-flow
          />
        </div>
      </div>
        </el-card>

    <!-- 存档列表 -->
        <div class="archive-tables-container">
          <!-- 服务器存档 -->
          <el-card shadow="never" class="archive-card">
            <template #header>
              <div class="flex items-center justify-between">
                <div class="card-header-left">
                  <span>服务器存档</span>
                  <el-tooltip content="这些存档是从您现有服务器的世界文件夹直接打包生成的。" placement="top">
                    <el-icon>
                      <QuestionFilled/>
                    </el-icon>
                  </el-tooltip>
                </div>
                <div>
                  <el-button type="primary" :icon="FolderAdd" @click="openCreateFromServerDialog">从服务器创建</el-button>
                </div>
              </div>
            </template>
            <el-table :data="serverArchives" v-loading="loading" row-key="id"
                      @selection-change="handleServerSelectionChange">
              <el-table-column type="selection" width="55" :reserve-selection="true"/>
              <el-table-column prop="name" label="存档名称" min-width="220" show-overflow-tooltip/>
              <el-table-column prop="created_at" label="创建时间" width="180" align="center">
                <template #default="scope">{{ formatDateTime(scope.row.created_at) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="300" align="center">
                <template #default="scope">
                  <el-button-group class="action-buttons">
                    <el-button type="success" :icon="Upload" size="small" @click="openRestoreDialog(scope.row)">恢复</el-button>
                    <el-button type="primary" :icon="Download" size="small" @click="handleDownload(scope.row.id)">下载</el-button>
                    <el-button type="danger" :icon="Delete" size="small" @click="handleDelete(scope.row.id, scope.row.name)">删除</el-button>
                  </el-button-group>
                </template>
              </el-table-column>
            </el-table>
          </el-card>

          <!-- 上传的存档 -->
          <el-card shadow="never" class="archive-card">
            <template #header>
              <div class="flex items-center justify-between">
                <div class="card-header-left">
                  <span>上传的存档</span>
                  <el-tooltip content="这些是您手动上传并经过验证的存档。" placement="top">
                    <el-icon>
                      <QuestionFilled/>
                    </el-icon>
                  </el-tooltip>
                </div>
                <div>
                  <el-button type="primary" :icon="Upload" @click="uploadDialogVisible = true">上传新存档</el-button>
                </div>
              </div>
            </template>
            <el-table :data="uploadedArchives" v-loading="loading" row-key="id"
                      @selection-change="handleUploadedSelectionChange">
              <el-table-column type="selection" width="55" :reserve-selection="true"/>
              <el-table-column prop="name" label="存档名称" min-width="220" show-overflow-tooltip/>
              <el-table-column prop="mc_version" label="游戏版本" width="120" align="center">
                <template #default="scope">
                  <el-tag v-if="scope.row.mc_version" size="small">{{ scope.row.mc_version }}</el-tag>
                  <span v-else>未指定</span>
                </template>
              </el-table-column>
              <el-table-column prop="created_at" label="上传时间" width="180" align="center">
                <template #default="scope">{{ formatDateTime(scope.row.created_at) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="300" align="center">
                <template #default="scope">
                  <el-button-group class="action-buttons">
                    <el-button type="success" :icon="Upload" size="small" @click="openRestoreDialog(scope.row)">恢复</el-button>
                    <el-button type="primary" :icon="Download" size="small" @click="handleDownload(scope.row.id)">下载</el-button>
                    <el-button type="danger" :icon="Delete" size="small" @click="handleDelete(scope.row.id, scope.row.name)">删除</el-button>
                  </el-button-group>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </div>
      </div>
    </div>

    <!-- 上传存档对话框（拖拽样式，宽度占满） -->
    <el-dialog v-model="uploadDialogVisible" title="上传新存档" width="500px" @closed="resetUploadForm" class="upload-dialog">
      <el-form ref="uploadFormRef" :model="uploadForm" :rules="uploadRules" label-position="top">
        <el-form-item label="Minecraft 版本" prop="mc_version">
          <el-select v-model="uploadForm.mc_version" placeholder="请选择版本 (可选)" filterable clearable
                     style="width: 100%;" :loading="versionsLoading" @visible-change="fetchMinecraftVersions">
            <el-option v-for="item in filteredMinecraftVersions" :key="item.id" :label="item.id" :value="item.id"/>
          </el-select>
          <div class="version-checkboxes" style="margin-top: 8px; display: flex; gap: 12px;">
            <el-checkbox v-model="showSnapshots" size="small">包含快照版</el-checkbox>
            <el-checkbox v-model="showExperiments" size="small">包含实验版本</el-checkbox>
          </div>
        </el-form-item>
        <el-form-item label="存档压缩包" prop="file">
          <el-upload
              ref="uploaderRef"
              v-model:file-list="fileList"
              action="#"
              drag
              :auto-upload="false"
              :limit="1"
              :on-exceed="handleExceed"
              :on-change="handleFileChange"
              accept=".zip,.rar,.7z,.tar,.gz"
              class="full-width-uploader"
              style="width: 100%"
          >
            <el-icon class="el-icon--upload">
              <Upload />
            </el-icon>
            <div class="el-upload__text">
              拖拽文件到此处或 <em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">请上传 .zip, .rar, .7z, .tar, .gz 格式的压缩文件。</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleUpload" :loading="isUploading">
          {{ isUploading ? '正在上传并处理...' : '上传' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 恢复存档对话框 -->
    <el-dialog v-model="restoreDialog.visible" title="恢复存档至服务器" width="500px" @closed="resetRestoreDialog">
      <p>准备将存档 <strong>{{ restoreDialog.archiveName }}</strong> 恢复至以下服务器。</p>
      <p class="restore-warning">
        <el-icon><WarningFilled /></el-icon>
        此操作将备份并替换目标服务器的现有世界并重启/开启目标服务器，请谨慎操作！
      </p>
      <el-form label-position="top" style="margin-top: 20px;">
        <el-form-item label="选择目标服务器" required>
          <el-select
              v-model="restoreDialog.targetServerId"
              placeholder="请选择一个服务器"
              style="width: 100%;"
              filterable
              :loading="allServersLoading"
          >
            <el-option
                v-for="server in allServers"
                :key="server.id"
                :label="formatServerOptionLabel(server)"
                :value="server.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="restoreDialog.visible = false">取消</el-button>
        <el-button
            type="primary"
            @click="handleConfirmRestore"
            :loading="restoreDialog.isRestoring"
            :disabled="!restoreDialog.targetServerId"
        >
          {{ restoreDialog.isRestoring ? '正在恢复...' : '确认恢复' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 从服务器创建存档对话框 -->
    <el-dialog v-model="createFromServerDialog.visible" title="从服务器创建存档" width="520px" align-center @open="fetchAllServers">
      <el-form label-position="top">
        <el-form-item label="选择服务器" required>
          <el-select v-model="createFromServerDialog.serverId" filterable placeholder="请选择服务器" :loading="allServersLoading" style="width: 100%;">
            <el-option
                v-for="s in allServers"
                :key="s.id"
                :label="formatServerOptionLabel(s)"
                :value="s.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createFromServerDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="createFromServerDialog.isCreating" :disabled="!createFromServerDialog.serverId" @click="handleCreateFromServer">从服务器创建</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
import {ref, onMounted, onUnmounted, computed, reactive} from 'vue';
import {useRoute} from 'vue-router';
import {ElMessage, ElMessageBox} from 'element-plus';
import {Upload, Download, QuestionFilled, Delete, WarningFilled, FolderAdd} from '@element-plus/icons-vue';
import apiClient from '@/api';
import { settings } from '@/store/settings'

// --- 状态 ---
const allArchives = ref([]);
const loading = ref(true);
const uploadDialogVisible = ref(false);
const processingTasks = ref([]);
const pollers = new Map();
const minecraftVersions = ref([]);
const versionsLoading = ref(false);
const showSnapshots = ref(false); // 是否包含快照版
const showExperiments = ref(false); // 是否包含实验版本
const serverSelection = ref([]);
const uploadedSelection = ref([]);
const allServers = ref([]); // <-- [新增] 用于存储所有服务器列表
const allServersLoading = ref(false); // <-- [新增] 服务器列表加载状态

// --- [新增] 恢复对话框状态 ---
const restoreDialog = reactive({
  visible: false,
  archiveId: null,
  archiveName: '',
  targetServerId: null,
  isRestoring: false,
});

// 从服务器创建对话框状态
const createFromServerDialog = reactive({
  visible: false,
  serverId: null,
  isCreating: false,
});

const selectedIds = computed(() => [
  ...serverSelection.value.map(item => item.id),
  ...uploadedSelection.value.map(item => item.id),
]);

// --- 计算属性 ---
const serverArchives = computed(() => allArchives.value.filter(a => a.type === 'SERVER'));
const uploadedArchives = computed(() => allArchives.value.filter(a => a.type === 'UPLOADED'));
const getDownloadUrl = (archiveId) => {
  const token = localStorage.getItem('token');
  return `${apiClient.defaults.baseURL}/api/archives/download/${archiveId}?token=${token}`;
};
const formatDateTime = (isoString) => {
  if (!isoString) return 'N/A';
  const date = new Date(isoString);
  return date.toLocaleString('zh-CN', { timeZone: settings.timezone || 'Asia/Shanghai' });
};

// [新增] 格式化服务器选择项的标签
const formatServerOptionLabel = (server) => {
  const serverType = server.server_type?.replace('_handler', '');
  if (serverType === 'vanilla' && server.game_version) {
    return `${server.name} (v${server.game_version})`;
  }
  return server.name;
};

// --- API 调用 ---
const fetchArchives = async () => {
  loading.value = true;
  try {
    const {data} = await apiClient.get('/api/archives');
    allArchives.value = data;
  } catch (error) {
    ElMessage.error('加载存档列表失败');
  } finally {
    loading.value = false;
  }
};

// [新增] 获取所有服务器列表
const fetchAllServers = async () => {
  if (allServers.value.length > 0) return;
  allServersLoading.value = true;
  try {
    const {data} = await apiClient.get('/api/servers');
    allServers.value = data;
  } catch (error) {
    ElMessage.error('获取服务器列表失败');
  } finally {
    allServersLoading.value = false;
  }
};

const fetchMinecraftVersions = async (visible) => {
  if (!visible || minecraftVersions.value.length > 0) return;
  versionsLoading.value = true;
  try {
    const {data} = await apiClient.get('/api/minecraft/versions');
    // 保留全部版本，具体展示通过勾选项进行过滤
    minecraftVersions.value = (data.versions || [])
        .slice()
        .sort((a, b) => b.id.localeCompare(a.id, undefined, {numeric: true}));
  } catch (error) {
    ElMessage.error('获取 Minecraft 版本列表失败');
  } finally {
    versionsLoading.value = false;
  }
};

// 基于勾选项过滤版本列表（仿 ServerList.vue 的用法）
const filteredMinecraftVersions = computed(() => {
  return minecraftVersions.value.filter(v => {
    if (v.type === 'release') return true;
    if (showSnapshots.value && (v.type === 'snapshot')) return true;
    if (showExperiments.value && (v.type === 'old_beta' || v.type === 'beta' || v.type === 'old_alpha')) return true;
    return false;
  });
});
const fetchActiveTasks = async () => {
  try {
    const {data} = await apiClient.get('/api/archives/active-tasks');
    processingTasks.value = data;
  } catch (error) {
    ElMessage.error("获取进行中的任务列表失败");
  }
};

// --- 任务轮询 (无变化) ---
const pollTaskStatus = (taskId) => {
  if (pollers.has(taskId)) return;
  const pollerId = setInterval(async () => {
    try {
      const {data} = await apiClient.get(`/api/system/task-progress/${taskId}`);
      const taskIndex = processingTasks.value.findIndex(t => t.id === taskId);
      if (taskIndex === -1) {
        clearInterval(pollerId);
        pollers.delete(taskId);
        return;
      }
      Object.assign(processingTasks.value[taskIndex], data);

      if (data.status === 'SUCCESS' || data.status === 'FAILED') {
        clearInterval(pollerId);
        pollers.delete(taskId);
        if (data.status === 'SUCCESS') {
          ElMessage.success(data.message || '任务完成！');
          setTimeout(() => {
            processingTasks.value.splice(taskIndex, 1);
            fetchArchives();
          }, 2000);
        } else {
          ElMessage.error(`任务失败: ${data.error || '未知错误'}`);
          setTimeout(() => processingTasks.value.splice(taskIndex, 1), 5000);
        }
      }
    } catch (error) {
      clearInterval(pollerId);
      pollers.delete(taskId);
    }
  }, 2000);
  pollers.set(taskId, pollerId);
};
const addTaskAndStartPolling = (task) => {
  if (processingTasks.value.some(t => t.id === task.id)) return;
  processingTasks.value.unshift(task);
  pollTaskStatus(task.id);
};

// --- 上传逻辑 ---
const isUploading = ref(false);
const uploadFormRef = ref(null);
const uploaderRef = ref(null);
const fileList = ref([]);
const uploadForm = ref({mc_version: '', file: null});
const uploadRules = {
  file: [{required: true, message: '请选择要上传的存档文件'}],
};
const handleFileChange = (uploadFile) => {
  uploadForm.value.file = uploadFile.raw;
};
const handleExceed = (files) => {
  uploaderRef.value.clearFiles();
  uploaderRef.value.handleStart(files[0]);
};
const resetUploadForm = () => {
  uploadForm.value = {mc_version: '', file: null};
  fileList.value = [];
  uploadFormRef.value?.resetFields();
};
const handleUpload = async () => {
  if (!uploadFormRef.value) return;
  const valid = await uploadFormRef.value.validate().catch(() => false);
  if (!valid) {
    return;
  }

  isUploading.value = true;
  const formData = new FormData();
  formData.append('file', uploadForm.value.file);
  try {
    const {data} = await apiClient.post('/api/archives/create/from-upload', formData, {
      params: uploadForm.value.mc_version ? {mc_version: uploadForm.value.mc_version} : undefined,
      timeout: 0,
    });
    ElMessage.info('文件上传成功，正在后台处理...');
    uploadDialogVisible.value = false;
    addTaskAndStartPolling({id: data.task_id, status: 'PENDING', progress: 0});
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || error.message || '上传失败');
  } finally {
    isUploading.value = false;
  }
};

// --- [新增] 恢复功能 ---
const openRestoreDialog = (archive) => {
  fetchAllServers(); // 确保服务器列表已加载
  restoreDialog.archiveId = archive.id;
  restoreDialog.archiveName = archive.name;
  restoreDialog.visible = true;
};
const resetRestoreDialog = () => {
  restoreDialog.archiveId = null;
  restoreDialog.archiveName = '';
  restoreDialog.targetServerId = null;
  restoreDialog.isRestoring = false;
};
const handleConfirmRestore = async () => {
  if (!restoreDialog.targetServerId) {
    ElMessage.warning('请选择一个目标服务器');
    return;
  }
  restoreDialog.isRestoring = true;
  try {
    const { data } = await apiClient.post(`/api/archives/restore/${restoreDialog.archiveId}`, {
      target_server_id: restoreDialog.targetServerId,
    });
    ElMessage.info('恢复任务已开始，请在任务列表查看进度。');
    addTaskAndStartPolling({ id: data.task_id, status: 'pending', progress: 0 });
    restoreDialog.visible = false;
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '启动恢复任务失败');
    restoreDialog.isRestoring = false;
  }
};


// --- [新增] 下载功能处理 ---
const handleDownload = (archiveId) => {
  window.location.href = getDownloadUrl(archiveId);
};

// 从服务器创建存档
const openCreateFromServerDialog = () => {
  createFromServerDialog.serverId = null;
  createFromServerDialog.visible = true;
  fetchAllServers();
};
const handleCreateFromServer = async () => {
  if (!createFromServerDialog.serverId) return ElMessage.warning('请选择服务器');
  createFromServerDialog.isCreating = true;
  try {
    const { data } = await apiClient.post('/api/archives/create/from-server', null, { params: { server_id: createFromServerDialog.serverId } });
    ElMessage.success('创建备份任务已发起！');
    addTaskAndStartPolling({ id: data.task_id, status: 'pending', progress: 0, message: '任务已接收，正在排队...' });
    createFromServerDialog.visible = false;
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '发起创建任务失败');
  } finally {
    createFromServerDialog.isCreating = false;
  }
};

// --- 删除逻辑 ---
const handleDelete = async (archiveId, archiveName) => {
  try {
    await ElMessageBox.confirm(`确定要删除存档 "${archiveName}" 吗？此操作不可逆！`, '警告', {type: 'warning'});
    await apiClient.delete(`/api/archives/delete/${archiveId}`);
    ElMessage.success(`存档 "${archiveName}" 已被删除`);
    fetchArchives();
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败');
    }
  }
};
const handleServerSelectionChange = (val) => serverSelection.value = val;
const handleUploadedSelectionChange = (val) => uploadedSelection.value = val;
const handleBulkDelete = async () => {
  if (selectedIds.value.length === 0) return;
  try {
    await ElMessageBox.confirm(`确定要删除选中的 ${selectedIds.value.length} 个存档吗？`, '警告', {type: 'warning'});
    await apiClient.post('/api/archives/batch-delete', {ids: selectedIds.value});
    ElMessage.success(`已成功删除 ${selectedIds.value.length} 个存档`);
    serverSelection.value = [];
    uploadedSelection.value = [];
    fetchArchives();
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '批量删除失败');
    }
  }
};

// --- 生命周期 ---
onMounted(async () => {
  await Promise.all([fetchArchives(), fetchActiveTasks()]);
  const route = useRoute();
  const newTaskId = route.query.new_task_id;
  if (newTaskId) {
    addTaskAndStartPolling({id: newTaskId, status: 'pending', progress: 0, message: '任务已接收，正在排队...'});
    window.history.replaceState({}, document.title, window.location.pathname);
  }
  processingTasks.value.forEach(task => pollTaskStatus(task.id));
});
onUnmounted(() => {
  pollers.forEach(pollerId => clearInterval(pollerId));
  pollers.clear();
});
//
</script>

<style scoped>
/* 居中收窄布局（参考 SuperFlatWorld.vue） */
.left-wrap { display: flex; justify-content: center; }
.left-panel { max-width: 960px; width: 960px; }

.flex { display: flex; }
.items-center { align-items: center; }
.justify-between { justify-content: space-between; }

.archive-tables-container { display: grid; grid-template-columns: 1fr; gap: 20px; }

.processing-tasks-list { display: flex; flex-direction: column; gap: 15px; }
.task-item { padding: 10px; border: 1px solid var(--el-border-color-lighter); border-radius: 4px; }
.task-info { display: flex; justify-content: space-between; margin-bottom: 8px; }
.action-buttons { display: inline-flex; flex-wrap: nowrap; gap: 0; }

.card-header { display: flex; align-items: center; gap: 8px; font-weight: bold; }
.card-header-left { display: flex; align-items: center; gap: 8px; font-weight: bold; }

/* 顶部标题卡片与首个卡片间距 */
.header-card { margin-bottom: 16px; }

/* 恢复对话框警告样式 */
.restore-warning {
  background-color: var(--el-color-warning-light-9);
  color: var(--el-color-warning);
  padding: 8px 12px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

/* 让拖拽上传区域占满宽度（参考 DbPluginExplorer.vue 的效果） */
.upload-dialog :deep(.full-width-uploader .el-upload-dragger) {
  width: 100%;
}
</style>
