<template>
  <div class="console-page-container">
    <el-card shadow="never" class="console-card">
      <template #header>
        <div class="console-header">
          <span>服务器: <strong>{{ serverName }}</strong></span>
          <div class="status-indicator">
            <span>状态:</span>
            <el-tag :type="statusTagType" effect="dark" size="small" :class="serverStatus === 'pending' ? 'pending-tag' : ''">{{ statusText }}</el-tag>
          </div>
        </div>
      </template>
      <div class="log-output-wrapper" ref="logOutputWrapperRef">
        <pre class="log-output">{{ logs.join('\n') }}</pre>
      </div>
    </el-card>

    <div class="command-input-area">
      <el-input
          v-model="command"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 60 }"
          placeholder="在此输入 MCDR 命令 (多行将逐行发送)"
          @keydown.enter.exact.prevent="sendCommand"
          clearable
      >
        <template #prepend>
          <el-dropdown trigger="click" @command="handleActionCommand">
            <el-button>
              操作
              <el-icon class="el-icon--right">
                <arrow-down/>
              </el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="start" :disabled="serverStatus === 'running' || serverStatus === 'pending'" :icon="VideoPlay">启动
                </el-dropdown-item>
                <el-dropdown-item command="stop" :disabled="serverStatus !== 'running'" :icon="SwitchButton">停止
                </el-dropdown-item>
                <el-dropdown-item command="restart" :disabled="serverStatus !== 'running'" :icon="Refresh">重启
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
        <template #append>
          <el-button @click="sendCommand" :disabled="!isConnected || serverStatus !== 'running'" :icon="Promotion">
            发送
          </el-button>
        </template>
      </el-input>
    </div>
  </div>
</template>

<script setup lang="ts">
import {VideoPlay, SwitchButton, Refresh, Promotion, ArrowDown} from '@element-plus/icons-vue';
import {ref, onMounted, onUnmounted, nextTick, watch, computed} from 'vue';
import {useRoute} from 'vue-router';
import {ElMessage} from 'element-plus';
import { useUserStore } from '@/store/user';
import { serversApi } from '@/api/servers';
import { useConsoleSocket } from '@/composables/useConsoleSocket';

const user = useUserStore().user;
const route = useRoute();
const serverId = ref(String(Array.isArray(route.params.server_id) ? route.params.server_id[0] : route.params.server_id));

const { logs, isConnected, serverName, serverStatus, appendLog, connect, disconnect, sendCommand: socketSendCommand } = useConsoleSocket(serverId.value, user);

const command = ref('');
const logOutputWrapperRef = ref<HTMLDivElement | null>(null);

const statusText = computed(() => {
  switch (serverStatus.value) {
    case 'running': return '运行中';
    case 'pending': return '启动中';
    case 'stopped': return '未启动';
    case 'new_setup': return '未配置';
    default:
      if (typeof serverStatus.value === 'number') return `已退出 (code: ${serverStatus.value})`;
      return `异常 (${serverStatus.value})`;
  }
});

const statusTagType = computed(() => {
  switch (serverStatus.value) {
    case 'running': return 'success';
    case 'pending': return 'info';
    case 'stopped': return 'warning';
    case 'new_setup': return 'info';
    default: return 'danger';
  }
});

const scrollToBottom = () => {
  nextTick(() => {
    if (logOutputWrapperRef.value) {
      logOutputWrapperRef.value.scrollTop = logOutputWrapperRef.value.scrollHeight;
    }
  });
};

watch(serverStatus, (newStatus, oldStatus) => {
  if (oldStatus !== 'loading' && oldStatus !== newStatus) {
    appendLog(`--- [系统] 服务器状态更新: ${statusText.value} ---`);
  }
});

const fetchServerDetails = async () => {
  try {
    const { data } = await serversApi.list();
    const currentServer = data.find(s => s.id === Number(serverId.value));
    if (currentServer) {
      serverName.value = currentServer.name;
      serverStatus.value = currentServer.status;
    } else {
      serverName.value = `服务器 #${serverId.value} 未找到`;
      serverStatus.value = 'not existed';
      ElMessage.error('无法在服务器列表中找到该服务器');
    }
  } catch {
    serverName.value = '未知';
    serverStatus.value = 'error';
  }
};

const fetchHistoricalLogs = async () => {
  logs.value = ['--- [系统] 正在加载历史日志... ---'];
  try {
    const { data } = await serversApi.getLogs(serverId.value);
    logs.value = data && data.length > 0 ? data : ['--- [系统] 未找到历史日志或日志为空 ---'];
  } catch {
    logs.value = ['--- [系统] 加载历史日志失败 ---'];
  }
};

const startServer = async () => {
  try {
    serverStatus.value = 'pending';
    await serversApi.start(serverId.value);
    ElMessage.success('启动命令已发送');
  } catch (error: any) {
    serverStatus.value = 'stopped';
    ElMessage.error(`启动失败: ${error.response?.data?.detail || error.message}`);
  }
};

const stopServer = async () => {
  try {
    await serversApi.stop(serverId.value);
    ElMessage.success('停止命令已发送');
  } catch (error: any) {
    ElMessage.error(`停止失败: ${error.response?.data?.detail || error.message}`);
  }
};

const restartServer = async () => {
  try {
    await serversApi.restart(serverId.value);
    ElMessage.success('重启命令已发送');
  } catch (error: any) {
    ElMessage.error(`重启失败: ${error.response?.data?.detail || error.message}`);
  }
};

const handleActionCommand = (action: string) => {
  if (action === 'start') startServer();
  else if (action === 'stop') stopServer();
  else if (action === 'restart') restartServer();
};

const sendCommand = () => {
  const lines = command.value.split('\n').map(l => l.trim()).filter(l => l.length > 0);
  if (lines.length === 0) return;
  socketSendCommand(lines);
  command.value = '';
};

onMounted(() => {
  setTimeout(() => {
    fetchServerDetails();
    fetchHistoricalLogs();
    connect();
  }, 0);
});

onUnmounted(() => disconnect());

watch(() => logs.value.length, scrollToBottom);
</script>

<style scoped>
/* 您的样式无需改动 */
.console-page-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 15px;
}
.console-card {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
:deep(.el-card__header) {
  padding: 10px 20px;
  flex-shrink: 0;
}
.console-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
}
.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}
:deep(.el-card__body) {
  padding: 0;
  flex-grow: 1;
  overflow: hidden;
  display: flex;
}
.log-output-wrapper {
  flex-grow: 1;
  overflow-y: auto;
  padding: 15px;
  background-color: #1e1e1e;
  color: #d4d4d4;
  font-family: 'Courier New', Courier, monospace;
}
.log-output {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 13px;
  line-height: 1.6;
}
.command-input-area {
  flex-shrink: 0;
}

/* 启动中使用品牌蓝色以提升可读性 */
.pending-tag {
  background-color: var(--el-color-primary) !important;
  border-color: var(--el-color-primary) !important;
  color: #fff !important;
}
</style>
