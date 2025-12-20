<template>
  <div class="archive-page">
    <div class="left-wrap">
      <div class="left-panel">
        <el-card shadow="never" class="toolbar-card">
          <div class="toolbar">
            <div class="toolbar-text">
              <div class="toolbar-title">存档管理</div>
              <div class="toolbar-subtitle">管理您的服务器存档与上传存档</div>
            </div>
            <div class="toolbar-actions">
              <el-input
                v-model="searchKeyword"
                class="toolbar-search"
                placeholder="搜索存档名称 / 版本"
                clearable
                :prefix-icon="Search"
              />
              <el-button :icon="Refresh" @click="fetchArchives" :loading="loading">刷新</el-button>
              <el-button
                type="danger"
                :icon="Delete"
                @click="handleBulkDelete"
                :disabled="selectedIds.length === 0"
              >
                删除已选 ({{ selectedIds.length }})
              </el-button>
              <el-button v-if="selectedIds.length > 0" text @click="clearSelection">清空选择</el-button>
            </div>
          </div>
        </el-card>

        <el-card shadow="never" class="section-card archives-card" v-loading="loading">
          <template #header>
            <div class="section-header">
              <div class="card-header-left">
                <span>所有存档</span>
                <el-tag size="small" effect="plain">{{ filteredArchives.length }}</el-tag>
              </div>
              <div class="section-actions">
                <el-button type="primary" :icon="FolderAdd" @click="openCreateFromServerDialog">从服务器创建</el-button>
                <el-button type="primary" :icon="Upload" @click="uploadDialogVisible = true">上传新存档</el-button>
              </div>
            </div>
          </template>

          <div v-if="filteredArchives.length === 0" class="empty-state">
            <el-empty description="暂无存档" />
          </div>
          <div v-else class="archive-grid">
            <el-card
              v-for="a in filteredArchives"
              :key="a.id"
              shadow="hover"
              class="archive-item-card"
              :class="{ selected: isSelected(a.id) }"
              :body-style="{ padding: '12px 12px 44px' }"
              @click="toggleSelected(a.id)"
            >
              <div class="archive-item-top">
                <div class="archive-name-row">
                  <el-icon class="archive-item-icon">
                    <Folder v-if="a.type === 'SERVER'" />
                    <Document v-else />
                  </el-icon>
                  <div class="archive-name" :title="a.name">{{ a.name }}</div>
                </div>
                <el-checkbox
                  :model-value="isSelected(a.id)"
                  @change="(val) => setSelected(a.id, val)"
                  @click.stop
                />
              </div>

              <div class="archive-item-meta">
                <div class="archive-tags">
                  <el-tag size="small" effect="plain">{{ a.type === 'SERVER' ? '服务器备份' : '上传' }}</el-tag>
                  <el-tag v-if="a.mc_version" size="small">{{ a.mc_version }}</el-tag>
                </div>
                <div class="archive-time">{{ formatDateTime(a.created_at) }}</div>
              </div>

              <div class="archive-item-actions" @click.stop>
                <el-tooltip content="恢复到服务器" placement="top">
                  <el-button type="success" :icon="Upload" circle @click.stop="openRestoreDialog(a)" />
                </el-tooltip>
                <el-tooltip content="下载" placement="top">
                  <el-button type="primary" :icon="Download" circle @click.stop="handleDownload(a)" />
                </el-tooltip>
                <el-tooltip content="删除" placement="top">
                  <el-button type="danger" :icon="Delete" circle @click.stop="handleDelete(a.id, a.name)" />
                </el-tooltip>
              </div>
            </el-card>
          </div>
        </el-card>
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
import {Upload, Download, Delete, WarningFilled, FolderAdd, Search, Refresh, Folder, Document} from '@element-plus/icons-vue';
import apiClient from '@/api';
import { settings } from '@/store/settings'
import { fetchTasks, onTaskEvent } from '@/store/tasks'

// --- 状态 ---
const allArchives = ref([]);
const loading = ref(true);
const uploadDialogVisible = ref(false);
const minecraftVersions = ref([]);
const versionsLoading = ref(false);
const showSnapshots = ref(false); // 是否包含快照版
const showExperiments = ref(false); // 是否包含实验版本
const searchKeyword = ref('');
const selectedArchiveIds = reactive(new Set());
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

const selectedIds = computed(() => Array.from(selectedArchiveIds));
const isSelected = (archiveId) => selectedArchiveIds.has(archiveId);
const setSelected = (archiveId, selected) => {
  if (selected) {
    selectedArchiveIds.add(archiveId);
  } else {
    selectedArchiveIds.delete(archiveId);
  }
};
const toggleSelected = (archiveId) => {
  if (selectedArchiveIds.has(archiveId)) {
    selectedArchiveIds.delete(archiveId);
  } else {
    selectedArchiveIds.add(archiveId);
  }
};
const clearSelection = () => selectedArchiveIds.clear();

// --- 计算属性 ---
const toTimestamp = (isoString) => {
  if (!isoString) return 0;
  const t = new Date(isoString).getTime();
  return Number.isFinite(t) ? t : 0;
};
const keyword = computed(() => searchKeyword.value.trim().toLowerCase());
const matchesKeyword = (archive) => {
  const q = keyword.value;
  if (!q) return true;
  const name = String(archive?.name ?? '').toLowerCase();
  const version = String(archive?.mc_version ?? '').toLowerCase();
  return name.includes(q) || version.includes(q);
};

const archives = computed(() => {
  return allArchives.value
    .slice()
    .sort((a, b) => toTimestamp(b.created_at) - toTimestamp(a.created_at));
});
const filteredArchives = computed(() => archives.value.filter(matchesKeyword));

const getFilenameFromContentDisposition = (contentDisposition) => {
  if (!contentDisposition) return null;
  const utf8Match = String(contentDisposition).match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch (e) {
      return utf8Match[1];
    }
  }
  const asciiMatch = String(contentDisposition).match(/filename=\"?([^\";]+)\"?/i);
  return asciiMatch?.[1] || null;
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
    const validIds = new Set(Array.isArray(data) ? data.map((a) => a.id) : []);
    Array.from(selectedArchiveIds).forEach((id) => {
      if (!validIds.has(id)) selectedArchiveIds.delete(id);
    });
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
    fetchTasks().catch(() => {});
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
    const { data } = await apiClient.post(`/api/archives/restore/${restoreDialog.archiveId}/${restoreDialog.targetServerId}`);
    ElMessage.info('恢复任务已开始，请在任务列表查看进度。');
    fetchTasks().catch(() => {});
    restoreDialog.visible = false;
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '启动恢复任务失败');
    restoreDialog.isRestoring = false;
  }
};


// --- 下载功能处理 ---
const resolveDownloadError = async (error) => {
  const detail = error?.response?.data?.detail;
  if (detail) return detail;
  const data = error?.response?.data;
  if (data instanceof Blob) {
    try {
      const text = await data.text();
      try {
        const json = JSON.parse(text);
        if (json?.detail) return json.detail;
      } catch (e) {
        // ignore
      }
      if (text) return text;
    } catch (e) {
      // ignore
    }
  }
  return error?.message || '下载失败';
};
const handleDownload = async (archive) => {
  try {
    const res = await apiClient.get(`/api/archives/download/${archive.id}`, {responseType: 'blob'});
    const cd = res.headers?.['content-disposition'];
    const filename =
      getFilenameFromContentDisposition(cd) ||
      (archive?.type === 'SERVER' ? `${archive.name}.tar.gz` : `${archive.name}.zip`);

    const blob = res.data instanceof Blob ? res.data : new Blob([res.data], {type: res.headers?.['content-type']});
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  } catch (error) {
    ElMessage.error(await resolveDownloadError(error));
  }
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
    fetchTasks().catch(() => {});
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
    selectedArchiveIds.delete(archiveId);
    fetchArchives();
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败');
    }
  }
};
const handleBulkDelete = async () => {
  if (selectedIds.value.length === 0) return;
  try {
    await ElMessageBox.confirm(`确定要删除选中的 ${selectedIds.value.length} 个存档吗？`, '警告', {type: 'warning'});
    await apiClient.post('/api/archives/batch-delete', {ids: selectedIds.value});
    ElMessage.success(`已成功删除 ${selectedIds.value.length} 个存档`);
    selectedArchiveIds.clear();
    fetchArchives();
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '批量删除失败');
    }
  }
};

// --- 生命周期 ---
let offTaskEvents = null;
let refreshTimer = null;
const scheduleRefreshArchives = () => {
  if (refreshTimer) return;
  refreshTimer = window.setTimeout(async () => {
    refreshTimer = null;
    await fetchArchives();
  }, 800);
};

onMounted(async () => {
  const route = useRoute();
  await fetchArchives();
  fetchTasks().catch(() => {});

  offTaskEvents = onTaskEvent((evt) => {
    const status = String(evt?.task?.status || '');
    const type = String(evt?.task?.type || '').toUpperCase();
    if ((evt.action === 'finished' || evt.action === 'updated') && status === 'SUCCESS' && type.includes('ARCHIVE')) {
      scheduleRefreshArchives();
    }
  });

  const newTaskId = route.query.new_task_id;
  if (newTaskId) {
    ElMessage.info('已提交任务，可在右上角任务列表查看进度。');
    fetchTasks().catch(() => {});
    window.history.replaceState({}, document.title, window.location.pathname);
  }
});
onUnmounted(() => {
  try {
    offTaskEvents?.();
  } catch (e) {
    // ignore
  }
  offTaskEvents = null;
  if (refreshTimer) {
    clearTimeout(refreshTimer);
    refreshTimer = null;
  }
});
//
</script>

<style scoped>
/* 居中收窄布局（参考 SuperFlatWorld.vue） */
.left-wrap { display: flex; justify-content: center; }
.left-panel { width: min(1120px, calc(100vw - 32px)); max-width: 1120px; }
.archive-page :deep(.left-wrap .left-panel) { overflow-y: auto !important; overflow-x: hidden !important; }
.archive-page :deep(.left-wrap .left-panel) { min-height: 0; }

.card-header { display: flex; align-items: center; gap: 8px; font-weight: bold; }
.card-header-left { display: flex; align-items: center; gap: 8px; font-weight: bold; }

/* 顶部工具条 */
.toolbar-card { margin-bottom: 16px; border-radius: 10px; flex-shrink: 0; }
.toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.toolbar-text { display: flex; flex-direction: column; gap: 2px; }
.toolbar-title { font-size: 16px; font-weight: 600; }
.toolbar-subtitle { font-size: 13px; color: var(--el-text-color-secondary); }
.toolbar-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.toolbar-search { width: 260px; }

/* 分区与卡片网格 */
.archives-card { flex-shrink: 0; }
.section-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.section-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.section-card { border-radius: 10px; }
.section-card :deep(.el-card__header) { padding: 12px 14px; }
.section-card :deep(.el-card__body) { padding: 14px; }

.empty-state { padding: 16px 0; }
.archive-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }

.archive-item-card { border-radius: 12px; cursor: pointer; position: relative; transition: transform 0.16s ease, box-shadow 0.16s ease; }
.archive-item-card:hover { transform: translateY(-2px); }
.archive-item-card.selected { box-shadow: 0 0 0 1px var(--el-color-primary) inset; }

.archive-item-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.archive-name-row { display: flex; align-items: flex-start; gap: 8px; min-width: 0; }
.archive-item-icon { color: var(--el-text-color-secondary); margin-top: 2px; flex: 0 0 auto; }
.archive-name {
  font-weight: 600;
  line-height: 1.35;
  min-width: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.archive-item-meta { margin-top: 10px; display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.archive-tags { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.archive-time { font-size: 12px; color: var(--el-text-color-secondary); white-space: nowrap; }
.archive-item-actions {
  position: absolute;
  right: 12px;
  bottom: 10px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  opacity: 0;
  transform: translateY(4px);
  pointer-events: none;
  transition: opacity 0.16s ease, transform 0.16s ease;
}
.archive-item-card:hover .archive-item-actions { opacity: 1; transform: translateY(0); pointer-events: auto; }
@media (hover: none) {
  .archive-item-actions { opacity: 1; transform: translateY(0); pointer-events: auto; }
}

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
