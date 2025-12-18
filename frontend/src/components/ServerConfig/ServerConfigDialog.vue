<template>
  <el-dialog
    v-model="dialogVisible"
    :title="dialogTitle"
    width="800px"
    top="8vh"
    align-center
    destroy-on-close
    class="config-dialog"
    @close="resetDialogState"
  >
    <div v-loading="configLoading" element-loading-text="正在加载配置...">
      <el-scrollbar max-height="65vh" class="config-form-scrollbar" always>
        <!-- 视图 1: 选择服务器类型 -->
        <SelectTypeView v-if="currentView === 'select_type'" v-model="selectedServerTypeForSetup"/>

        <!-- 视图 2: 动态表单组件 -->
        <component
            v-if="currentView === 'form'"
            :is="activeFormComponent"
            v-model:modelValue="configFormData"
            :is-initial-setup="dialogState.isInitialSetup && configFormData.server_type === 'velocity' && !dialogState.coreFileExists"
            :all-servers="allServers"
            :current-server-id="currentConfigServer?.id"
            :test-port="testPort"
        />

        <!-- 其他视图 -->
        <div v-if="currentView === 'unsupported_type'" class="unsupported-prompt">
          <p>此服务器类型 ({{ configFormData.server_type }}) 的配置界面暂未支持。</p>
        </div>
        <div v-if="currentView === 'downloading'" class="downloading-prompt">
          <el-progress type="circle" :percentage="downloadProgress" />
          <p>正在下载并安装核心文件，请稍候...</p>
        </div>
        <div v-if="currentView === 'needs_first_start'" class="initial-start-prompt">
           <el-alert
                title="需要首次启动以生成配置文件"
                type="warning" :closable="false" show-icon
                description="服务器核心文件已准备就绪。请启动一次服务器以生成默认配置文件，之后您才能进行详细配置。"
            />
          <div class="prompt-actions">
            <el-button type="primary" :icon="VideoPlay" @click="startAndContinue">启动并继续配置</el-button>
          </div>
        </div>
        <div v-if="currentView === 'waiting_for_startup'" class="waiting-prompt">
          <el-icon class="is-loading" :size="40"><Loading/></el-icon>
          <p>服务器启动中，正在等待生成配置文件...</p>
        </div>
      </el-scrollbar>
    </div>

    <template #footer>
      <div class="dialog-footer-flex">
        <div class="footer-left-buttons">
          <template v-if="currentView === 'form' && !dialogState.isNewSetup">
            <el-button @click="openFileEditor('mcdr_config')" :icon="Document">编辑 config.yml</el-button>
            <el-button v-if="configFormData.server_type === 'vanilla' || configFormData.server_type === 'beta18'" @click="openFileEditor('mc_properties')" :icon="Document">编辑 server.properties</el-button>
            <el-button v-if="configFormData.server_type === 'velocity'" @click="openFileEditor('velocity_toml')" :icon="Document">编辑 velocity.toml</el-button>
          </template>
        </div>
        <div class="footer-right-buttons">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button v-if="currentView === 'select_type'" type="primary" @click="confirmServerType" :disabled="!selectedServerTypeForSetup">下一步</el-button>
          <el-button v-if="currentView === 'form'" type="primary" @click="handleSaveConfig" :loading="isSavingConfig">
            {{ getSaveButtonText() }}
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
// [修复] 从 vue 的导入中移除了不再需要的 shallowRef
import { ref, reactive, computed, defineAsyncComponent } from 'vue';
import { ElMessage } from 'element-plus';
import { Document, VideoPlay, Loading } from '@element-plus/icons-vue';
import apiClient from '@/api';
import SelectTypeView from './views/SelectTypeView.vue';

// 动态异步加载表单组件
const VanillaConfigForm = defineAsyncComponent(() => import('./forms/VanillaConfigForm.vue'));
const VelocityConfigForm = defineAsyncComponent(() => import('./forms/VelocityConfigForm.vue'));

const props = defineProps({
  allServers: { type: Array, required: true },
  testPort: { type: Function, required: true },
  openFileEditor: { type: Function, required: true },
});
const emit = defineEmits(['config-saved']);

const dialogVisible = ref(false);
const configLoading = ref(false);
const isSavingConfig = ref(false);
const currentConfigServer = ref(null);
const configFormData = ref({});
const selectedServerTypeForSetup = ref('');
const downloadProgress = ref(0);
let pollInterval = null;
const currentView = ref('select_type'); // select_type, form, downloading, needs_first_start, waiting_for_startup, unsupported_type

const dialogState = reactive({
  isNewSetup: false,
  coreFileExists: false,
  configFileExists: false,
});

const dialogTitle = computed(() => {
  if (!currentConfigServer.value) return '配置服务器';
  return dialogState.isNewSetup
    ? `初始化服务器配置 - ${currentConfigServer.value.name}`
    : `配置服务器 - ${currentConfigServer.value.name}`;
});

// [修复] activeFormComponent 现在直接返回组件定义，而不是一个 ref
const activeFormComponent = computed(() => {
  const type = configFormData.value.server_type;
  if (type === 'vanilla' || type === 'beta18') {
    return VanillaConfigForm;
  }
  if (type === 'velocity') {
    return VelocityConfigForm;
  }
  return null;
});

const getSaveButtonText = () => {
    if (dialogState.isNewSetup) {
        return configFormData.value.server_type === 'velocity' ? '下载并准备' : '创建并保存';
    }
    return '保存配置';
};

const resetDialogState = () => {
  if (pollInterval) clearInterval(pollInterval);
  pollInterval = null; // Ensure it's cleared
  configFormData.value = {};
  selectedServerTypeForSetup.value = '';
  currentView.value = 'select_type';
  Object.assign(dialogState, { isNewSetup: false, coreFileExists: false, configFileExists: false });
};

const open = async (server, isNew = false) => {
  resetDialogState();
  currentConfigServer.value = server;
  dialogVisible.value = true;
  configLoading.value = true;

  if (isNew) {
      dialogState.isNewSetup = true;
      configFormData.value = {
        jvm: { min_memory: '128M', max_memory: '512M', extra_args: '' },
        server_properties: {}, // Ensure nested objects exist
        velocity_toml: {}
      };
      currentView.value = 'select_type';
      configLoading.value = false;
      return;
  }

  try {
    const {data} = await apiClient.get(`/api/servers/config?server_id=${server.id}`);
    configFormData.value = data.config;
    dialogState.isNewSetup = data.is_new_setup;
    dialogState.coreFileExists = data.core_file_exists;
    dialogState.configFileExists = data.config_file_exists;

    if (server.status === 'new_setup') {
        currentView.value = 'select_type';
        if (data.config.server_type) {
            selectedServerTypeForSetup.value = data.config.server_type;
        }
    } else {
      navigateToCorrectView(data.config.server_type);
    }
  } catch (error) {
    ElMessage.error(`加载配置失败: ${error.response?.data?.detail || error.message}`);
    dialogVisible.value = false;
  } finally {
    configLoading.value = false;
  }
};

const navigateToCorrectView = (type) => {
  if (type === 'vanilla' || type === 'beta18') {
    currentView.value = 'form';
  } else if (type === 'velocity') {
    if (!dialogState.coreFileExists) {
      currentView.value = 'form';
    } else if (!dialogState.configFileExists) {
      currentView.value = 'needs_first_start';
    } else {
      currentView.value = 'form';
    }
  } else {
    currentView.value = 'unsupported_type';
  }
};

const confirmServerType = () => {
  configFormData.value.server_type = selectedServerTypeForSetup.value;
  navigateToCorrectView(selectedServerTypeForSetup.value);
};

const handleSaveConfig = async () => {
  isSavingConfig.value = true;
  const payload = {
    server_id: currentConfigServer.value.id,
    config: {...configFormData.value},
    is_new_setup: dialogState.isNewSetup,
  };
  try {
    const {data} = await apiClient.post('/api/servers/config', payload);
    if (data.status === 'downloading' && data.task_id) {
      currentView.value = 'downloading';
      pollDownloadStatus(data.task_id);
    } else {
      ElMessage.success(data.message || '配置已成功保存！');
      dialogVisible.value = false;
      emit('config-saved');
    }
  } catch (error) {
    ElMessage.error(`保存配置失败: ${error.response?.data?.detail || error.message}`);
  } finally {
    if (currentView.value !== 'downloading') {
      isSavingConfig.value = false;
    }
  }
};

const pollDownloadStatus = (taskId) => {
  isSavingConfig.value = false;
  pollInterval = setInterval(async () => {
    try {
      const {data} = await apiClient.get(`/api/system/task-progress/${taskId}`);
      downloadProgress.value = data.progress;
      if (data.status === 'SUCCESS') {
        clearInterval(pollInterval);
        pollInterval = null;
        ElMessage.success('核心文件安装完成！');
        dialogState.coreFileExists = true;
        // 重新获取一次配置，以加载生成的新文件
        const { data: updatedData } = await apiClient.get(`/api/servers/config?server_id=${currentConfigServer.value.id}`);
        configFormData.value = updatedData.config;
        dialogState.configFileExists = updatedData.config_file_exists;

        navigateToCorrectView(configFormData.value.server_type);
        emit('config-saved');
      } else if (data.status === 'FAILED') {
        clearInterval(pollInterval);
        pollInterval = null;
        ElMessage.error(`处理失败: ${data.error || '未知错误'}`);
        navigateToCorrectView(configFormData.value.server_type);
      }
    } catch (error) {
      clearInterval(pollInterval);
      pollInterval = null;
      ElMessage.error('无法获取进度，请检查后端服务。');
      navigateToCorrectView(configFormData.value.server_type);
    }
  }, 1000);
};

const startAndContinue = async () => {
  currentView.value = 'waiting_for_startup';
  try {
    await apiClient.post(`/api/servers/start?server_id=${currentConfigServer.value.id}`);
    ElMessage.info('服务器启动命令已发送，请稍后在主列表查看状态并重新打开配置。');
    dialogVisible.value = false;
    emit('config-saved');
  } catch (e) {
    ElMessage.error(`启动失败: ${e.response?.data?.detail || e.message}`);
    currentView.value = 'needs_first_start';
  }
};

// Also, let's fix the v-model on the dynamic component to be more explicit.
// From v-model="configFormData" to v-model:modelValue="configFormData"
// and in the child forms, change `v-model:config` to `v-model:modelValue`
// Let me double check if this is necessary. The error is about the component itself,
// but the prop name consistency is good practice. Let me check the child form.
// In VanillaConfigForm.vue: `defineProps({ modelValue: ... })`.
// So the parent should use `v-model:modelValue` or `v-model`.
// I used `v-model="configFormData"` which defaults to `v-model:modelValue`. This is correct.
// The prop name in `VanillaConfigForm.vue` is `modelValue`.
// In `VelocityConfigForm.vue` it's also `modelValue`.
// So the original `v-model="configFormData"` is correct.
// The `Component is missing template` error is the only real issue.
// The code I provided above fixes this.

defineExpose({open, currentConfigServer});
</script>

<style scoped>
.dialog-footer-flex {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.footer-left-buttons, .footer-right-buttons {
  display: flex;
  gap: 10px;
}

.config-form-scrollbar {
  padding: 0 20px;
  margin: 0 -20px;
}

.unsupported-prompt, .downloading-prompt, .initial-start-prompt, .waiting-prompt {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  text-align: center;
  gap: 20px;
  font-size: 16px;
  color: var(--el-text-color-secondary);
}

.initial-start-prompt .el-alert {
  width: 100%;
}

.prompt-actions {
  margin-top: 20px;
}
</style>
