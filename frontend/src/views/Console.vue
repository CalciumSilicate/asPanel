<template>
  <div class="console-page">

    <!-- ── Main log card ─────────────────────────────────── -->
    <div class="console-glass-card">

      <!-- Header -->
      <div class="console-header">
        <div class="header-left">
          <div class="srv-icon">
            <el-icon :size="15"><Monitor /></el-icon>
          </div>
          <div class="srv-info">
            <span class="srv-name">{{ serverName }}</span>
            <span class="conn-badge" :class="{ 'conn-on': isConnected }">
              <span class="conn-dot" />
              {{ isConnected ? 'WebSocket 已连接' : '未连接' }}
            </span>
          </div>
        </div>
        <div class="header-right">
          <span :class="['status-pill', 'sp-' + serverStatus]">
            <span v-if="serverStatus === 'running' || serverStatus === 'pending'" class="pulse-dot" />
            <span v-else class="static-dot" />
            {{ statusText }}
          </span>
        </div>
      </div>

      <!-- Log output -->
      <div class="log-output-wrapper" ref="logOutputWrapperRef">
        <pre class="log-output">{{ logs.join('\n') }}</pre>
      </div>

    </div>

    <!-- ── Command bar ────────────────────────────────────── -->
    <div class="command-bar">

      <!-- Action buttons -->
      <div class="action-group">
        <el-tooltip content="启动" placement="top" :show-after="400">
          <button
            class="act-btn act-start"
            :disabled="serverStatus === 'running' || serverStatus === 'pending'"
            @click="startServer"
          >
            <el-icon :size="13"><VideoPlay /></el-icon>
            <span>启动</span>
          </button>
        </el-tooltip>
        <el-tooltip content="停止" placement="top" :show-after="400">
          <button
            class="act-btn act-stop"
            :disabled="serverStatus !== 'running'"
            @click="stopServer"
          >
            <el-icon :size="13"><SwitchButton /></el-icon>
            <span>停止</span>
          </button>
        </el-tooltip>
        <el-tooltip content="重启" placement="top" :show-after="400">
          <button
            class="act-btn act-restart"
            :disabled="serverStatus !== 'running'"
            @click="restartServer"
          >
            <el-icon :size="13"><Refresh /></el-icon>
            <span>重启</span>
          </button>
        </el-tooltip>
      </div>

      <div class="cmd-sep" />

      <!-- Command input -->
      <div class="cmd-input-wrap">
        <span class="cmd-prompt">›</span>
        <el-input
          v-model="command"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 6 }"
          placeholder="输入 MCDR 命令，回车发送（多行逐行发送）"
          class="cmd-textarea"
          @keydown.enter.exact.prevent="sendCommand"
        />
      </div>

      <!-- Send button -->
      <button
        class="send-btn"
        :disabled="!isConnected || serverStatus !== 'running'"
        @click="sendCommand"
      >
        <el-icon :size="14"><Promotion /></el-icon>
        <span>发送</span>
      </button>

    </div>
  </div>
</template>

<script setup lang="ts">
import { VideoPlay, SwitchButton, Refresh, Promotion, Monitor } from '@element-plus/icons-vue';
import { ref, onMounted, onUnmounted, nextTick, watch, computed } from 'vue';
import { useRoute } from 'vue-router';
import { ElMessage } from 'element-plus';
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
/* ── Page layout ─────────────────────────────────────────── */
.console-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow: hidden;
  min-height: 0;
}

/* ── Main glass card ──────────────────────────────────────── */
.console-glass-card {
  position: relative;
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.62);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(119, 181, 254, 0.18);
  border-radius: 20px;
  box-shadow: 0 4px 24px rgba(119, 181, 254, 0.10), inset 0 1px 0 rgba(255, 255, 255, 0.85);
  overflow: hidden;
  transition: box-shadow 0.3s ease, border-color 0.3s ease;
}
.console-glass-card:hover {
  border-color: rgba(119, 181, 254, 0.28);
  box-shadow: 0 8px 40px rgba(119, 181, 254, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.85);
}
:global(.dark) .console-glass-card {
  background: rgba(15, 23, 42, 0.68);
  border-color: rgba(119, 181, 254, 0.12);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.40), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

/* ── Header ───────────────────────────────────────────────── */
.console-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 18px;
  border-bottom: 1px solid rgba(119, 181, 254, 0.10);
  flex-shrink: 0;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.srv-icon {
  width: 32px; height: 32px;
  border-radius: 9px;
  background: var(--brand-primary);
  display: flex; align-items: center; justify-content: center;
  color: #fff;
  flex-shrink: 0;
}
.srv-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.srv-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--color-text);
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.conn-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--el-text-color-placeholder);
}
.conn-dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: var(--el-text-color-placeholder);
  transition: background 0.3s ease, box-shadow 0.3s ease;
  flex-shrink: 0;
}
.conn-on .conn-dot {
  background: #10b981;
  box-shadow: 0 0 5px rgba(16, 185, 129, 0.65);
  animation: pulse 2.2s ease-in-out infinite;
}
.conn-on { color: #10b981; }

/* ── Status pill ──────────────────────────────────────────── */
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
  background: rgba(148, 163, 184, 0.10);
  border: 1px solid rgba(148, 163, 184, 0.20);
  color: var(--el-text-color-secondary);
}
.sp-running  { background: rgba(52,211,153,0.12); border-color: rgba(52,211,153,0.28); color: #10b981; }
.sp-pending  { background: rgba(119,181,254,0.12); border-color: rgba(119,181,254,0.28); color: var(--brand-primary); }
.sp-new_setup{ background: rgba(119,181,254,0.08); border-color: rgba(119,181,254,0.18); color: var(--brand-primary); }
:global(.dark) .sp-running  { color: #34d399; }
:global(.dark) .sp-pending,
:global(.dark) .sp-new_setup { color: var(--brand-primary); }

.pulse-dot {
  display: inline-block;
  width: 5px; height: 5px;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 4px currentColor;
  animation: pulse 2.2s ease-in-out infinite;
}
.static-dot {
  display: inline-block;
  width: 5px; height: 5px;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.55;
}
@keyframes pulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 3px currentColor; }
  50%       { opacity: 0.6; box-shadow: 0 0 7px currentColor, 0 0 14px currentColor; }
}

/* ── Log output (always dark terminal) ────────────────────── */
.log-output-wrapper {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 14px 18px;
  background: #0d1117;
  color: #c9d1d9;
  font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
}
.log-output-wrapper::-webkit-scrollbar { width: 6px; }
.log-output-wrapper::-webkit-scrollbar-track { background: transparent; }
.log-output-wrapper::-webkit-scrollbar-thumb {
  background: rgba(119, 181, 254, 0.25);
  border-radius: 3px;
}
.log-output-wrapper::-webkit-scrollbar-thumb:hover {
  background: rgba(119, 181, 254, 0.45);
}
.log-output {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12.5px;
  line-height: 1.65;
}

/* ── Command bar ──────────────────────────────────────────── */
.command-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.62);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(119, 181, 254, 0.18);
  border-radius: 20px;
  box-shadow: 0 4px 24px rgba(119, 181, 254, 0.10), inset 0 1px 0 rgba(255, 255, 255, 0.85);
  flex-shrink: 0;
  transition: box-shadow 0.3s ease, border-color 0.3s ease;
}
.command-bar:focus-within {
  border-color: rgba(119, 181, 254, 0.32);
  box-shadow: 0 6px 32px rgba(119, 181, 254, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.85);
}
:global(.dark) .command-bar {
  background: rgba(15, 23, 42, 0.68);
  border-color: rgba(119, 181, 254, 0.12);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

/* Action button group */
.action-group {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  background: rgba(119, 181, 254, 0.05);
  border: 1px solid rgba(119, 181, 254, 0.12);
  border-radius: 12px;
  padding: 3px;
  flex-shrink: 0;
}
.act-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 30px;
  padding: 0 10px;
  border-radius: 8px;
  border: 1px solid transparent;
  background: transparent;
  cursor: pointer;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 600;
  transition: background 0.14s ease, color 0.14s ease, border-color 0.14s ease;
  flex-shrink: 0;
}
.act-btn:disabled { opacity: 0.28; cursor: not-allowed; }
.act-start:not(:disabled):hover   { background: rgba(52,211,153,0.14);  color: #10b981; border-color: rgba(52,211,153,0.28); }
.act-stop:not(:disabled):hover    { background: rgba(248,113,113,0.14); color: #ef4444; border-color: rgba(248,113,113,0.28); }
.act-restart:not(:disabled):hover { background: rgba(245,158,11,0.14);  color: #f59e0b; border-color: rgba(245,158,11,0.28); }

.cmd-sep {
  width: 1px; height: 22px;
  background: rgba(119, 181, 254, 0.18);
  flex-shrink: 0;
}

/* Input area */
.cmd-input-wrap {
  flex: 1 1 auto;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.cmd-prompt {
  font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace;
  font-size: 18px;
  font-weight: 700;
  color: var(--brand-primary);
  opacity: 0.6;
  flex-shrink: 0;
  line-height: 1;
  user-select: none;
}
.cmd-textarea :deep(.el-textarea__inner) {
  font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace !important;
  font-size: 13px !important;
  line-height: 1.55 !important;
  border-radius: 12px !important;
  background: rgba(255, 255, 255, 0.55) !important;
  border: 1px solid rgba(119, 181, 254, 0.18) !important;
  box-shadow: none !important;
  resize: none !important;
  padding: 7px 12px !important;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease !important;
}
.cmd-textarea :deep(.el-textarea__inner:hover) {
  border-color: rgba(119, 181, 254, 0.38) !important;
}
.cmd-textarea :deep(.el-textarea__inner:focus) {
  border-color: rgba(119, 181, 254, 0.55) !important;
  box-shadow: 0 0 0 3px rgba(119, 181, 254, 0.10) !important;
  background: rgba(255, 255, 255, 0.88) !important;
}
:global(.dark) .cmd-textarea :deep(.el-textarea__inner) {
  background: rgba(15, 23, 42, 0.55) !important;
  border-color: rgba(119, 181, 254, 0.15) !important;
  color: var(--el-text-color-regular) !important;
}
:global(.dark) .cmd-textarea :deep(.el-textarea__inner:focus) {
  background: rgba(15, 23, 42, 0.85) !important;
}

/* Send button */
.send-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 36px;
  padding: 0 18px;
  border-radius: 12px;
  border: none;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, var(--brand-primary) 0%, #a78bfa 100%);
  box-shadow: 0 4px 14px rgba(119, 181, 254, 0.35);
  transition: box-shadow 0.2s ease, transform 0.2s cubic-bezier(.34,1.56,.64,1);
  flex-shrink: 0;
}
.send-btn:hover:not(:disabled) {
  box-shadow: 0 6px 22px rgba(119, 181, 254, 0.55);
  transform: translateY(-1px);
}
.send-btn:active:not(:disabled) { transform: scale(0.97); }
.send-btn:disabled { opacity: 0.35; cursor: not-allowed; box-shadow: none; }
</style>
