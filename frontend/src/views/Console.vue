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

<script setup>
import {VideoPlay, SwitchButton, Refresh, Promotion, ArrowDown} from '@element-plus/icons-vue';
import {ref, onMounted, onUnmounted, nextTick, watch, computed} from 'vue';
import {useRoute} from 'vue-router';
import {io} from 'socket.io-client';
import apiClient from '@/api';
import { API_BASE_URL } from '@/config';
import {ElMessage, ElTag, ElButton, ElInput, ElDropdown, ElDropdownMenu, ElDropdownItem, ElCard, ElIcon} from 'element-plus';

const route = useRoute();
const serverId = ref(route.params.server_id);
const logs = ref([]);
const command = ref('');
const isConnected = ref(false);
const logOutputWrapperRef = ref(null);
let socket = null;

const serverName = ref('加载中...');
const serverStatus = ref('loading');

// 防止日志无限增长导致页面卡顿/内存暴涨
const MAX_LOG_LINES = 2000;
const trimLogs = () => {
  const extra = logs.value.length - MAX_LOG_LINES;
  if (extra > 0) logs.value.splice(0, extra);
};

// --- 计算属性保持不变 ---
const statusText = computed(() => {
  switch (serverStatus.value) {
    case 'running': return '运行中';
    case 'pending': return '启动中';
    case 'stopped': return '未启动';
    case 'new_setup': return '未配置';
    default:
      if (typeof serverStatus.value === 'number') {
        return `已退出 (code: ${serverStatus.value})`;
      }
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

const fetchServerDetails = async () => {
  try {
    const response = await apiClient.get('/api/servers');
    const currentServer = response.data.find(s => s.id == serverId.value);
    if (currentServer) {
      serverName.value = currentServer.name;
      serverStatus.value = currentServer.status;
    } else {
      serverName.value = `服务器 #${serverId.value} 未找到`;
      serverStatus.value = 'not existed';
      ElMessage.error('无法在服务器列表中找到该服务器');
    }
  } catch (error) {
    serverName.value = '未知';
    serverStatus.value = 'error';
  }
};

// --- start/stop/restart/sendCommand 等操作函数保持不变 ---
const startServer = async () => {
  try {
    // 立即切换到“启动中”，等待后端事件再切至“运行中”
    serverStatus.value = 'pending'
    await apiClient.post(`/api/servers/start?server_id=${serverId.value}`);
    ElMessage.success('启动命令已发送');
  } catch (error) {
    serverStatus.value = 'stopped'
    ElMessage.error(`启动失败: ${error.response?.data?.detail || error.message}`);
  }
};

const stopServer = async () => {
  try {
    await apiClient.post(`/api/servers/stop?server_id=${serverId.value}`);
    ElMessage.success('停止命令已发送');
  } catch (error) {
    ElMessage.error(`停止失败: ${error.response?.data?.detail || error.message}`);
  }
};

const restartServer = async () => {
  try {
    await apiClient.post(`/api/servers/restart?server_id=${serverId.value}`);
    ElMessage.success('重启命令已发送');
  } catch (error) {
    ElMessage.error(`重启失败: ${error.response?.data?.detail || error.message}`);
  }
};

const handleActionCommand = (action) => {
  if (action === 'start') startServer();
  else if (action === 'stop') stopServer();
  else if (action === 'restart') restartServer();
}

const sendCommand = () => {
  if (!socket || !isConnected.value) return;

  const lines = command.value
      .split('\n')
      .map(line => line.trim())
      .filter(line => line.length > 0);

  if (lines.length === 0) return;

  lines.forEach(line => {
    socket.emit('console_command', {
      server_id: parseInt(serverId.value, 10),
      command: line,
    });
  });

  command.value = '';
};

const setupSocketListeners = () => {
  socket.on('connect', () => {
    isConnected.value = true;
    // 重要提示: 请确保后端 socket_handlers.py 中处理 join_console_room 事件时，
    // 将客户端加入到名为 `server_console_{server_id}` 的房间中，
    // 例如: await sio.enter_room(sid, f'server_console_{server_id}')
    socket.emit('join_console_room', {server_id: parseInt(serverId.value, 10)});
    logs.value.push('--- [系统] 已连接到服务器控制台，开始接收实时日志 ---');
    trimLogs();
  });

  // [修改] 移除旧的 'console_log' 监听器，或将其作为备用
  // socket.on('console_log', ...);

  // [新增] 监听批量日志事件，这是性能优化的核心
  socket.on('console_log_batch', (data) => {
    if (data && Array.isArray(data.logs) && data.logs.length > 0) {
      logs.value.push(...data.logs);
      trimLogs();
    }
  });

  // [修改] 监听更详细的 'server_status_update' 事件
  socket.on('server_status_update', (serverDetails) => {
    // 确保这个状态更新是针对当前页面的服务器的
    if (serverDetails && serverDetails.id == serverId.value) {
      const oldStatus = serverStatus.value;
      serverStatus.value = serverDetails.status;
      serverName.value = serverDetails.name; // 同时同步服务器名

      // 只有在状态真正改变时才打印日志，避免不必要的信息
      if (oldStatus !== serverDetails.status) {
        logs.value.push(`--- [系统] 服务器状态更新: ${statusText.value} ---`);
        trimLogs();
      }
    }
  });

  socket.on('server_delete', (serverDetails) => {
    if (serverDetails && serverDetails.id == serverId.value) {
      logs.value.push(`--- [系统] 服务器已被删除，请退出该页面 ---`);
      trimLogs();
    }
  });

  socket.on('disconnect', () => {
    isConnected.value = false;
    logs.value.push('--- [系统] 已从服务器断开连接 ---');
    trimLogs();
  });

  socket.on('connect_error', (error) => {
    logs.value.push(`--- [系统] 连接错误: ${error.message} ---`);
    trimLogs();
  });
};

const fetchHistoricalLogs = async () => {
  logs.value = ['--- [系统] 正在加载历史日志... ---'];
  try {
    const response = await apiClient.get(`/api/servers/${serverId.value}/logs`);
    if (response.data && response.data.length > 0) {
      logs.value = response.data;
    } else {
      logs.value = ['--- [系统] 未找到历史日志或日志为空 ---'];
    }
  } catch (error) {
    logs.value = ['--- [系统] 加载历史日志失败 ---'];
  } finally {
    trimLogs();
  }
};

const initializeConsole = () => {
  fetchServerDetails();
  fetchHistoricalLogs();

  // 连接到后端 Socket.IO 服务
  socket = io(API_BASE_URL, {path: '/ws/socket.io'});
  setupSocketListeners();
};

onMounted(() => {
  setTimeout(initializeConsole, 0);
});

onUnmounted(() => {
  if (socket) {
    // [修改] 确保清理所有事件监听器
    socket.off('connect');
    socket.off('console_log_batch');
    socket.off('server_status_update');
    socket.off('disconnect');
    socket.off('connect_error');
    socket.disconnect();
  }
});

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
