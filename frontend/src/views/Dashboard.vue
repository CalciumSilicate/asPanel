<template>
  <div class="dashboard-container">
    <!-- 1. 欢迎卡片 -->
    <el-card shadow="never" class="welcome-card">
      <div class="welcome-content">
        <el-avatar :size="70" :src="fullAvatarUrl" :icon="UserFilled" />
        <div class="welcome-text">
          <div class="title">欢迎回来, {{ user.username || 'admin' }}!</div>
          <div class="subtitle">这是服务器状态总览。</div>
        </div>
      </div>
    </el-card>

    <!-- 2. 核心数据统计 -->
    <el-row :gutter="20" class="stats-cards">
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="icon-wrapper stat-servers-bg">
              <el-icon class="icon stat-servers-color"><Tickets /></el-icon>
            </div>
            <div class="text">
              <div class="label">服务器状态</div>
              <div class="value">{{ stats.running_servers }} <span class="unit">/ {{ stats.total_servers }} 运行中</span></div>
            </div>
          </div>
           <el-progress :percentage="serverPercent" :show-text="false" :stroke-width="6" status="success" />
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="icon-wrapper stat-cpu-bg">
              <el-icon class="icon stat-cpu-color"><Cpu /></el-icon>
            </div>
            <div class="text">
              <div class="label">主机 CPU 负载</div>
              <div class="value">{{ systemStatus.cpu_percent }}<span class="unit">%</span></div>
            </div>
          </div>
           <el-progress :percentage="systemStatus.cpu_percent" :show-text="false" :stroke-width="6" status="success" />
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="icon-wrapper stat-memory-bg">
              <el-icon class="icon stat-memory-color"><DataLine /></el-icon>
            </div>
            <div class="text">
              <div class="label">主机内存占用</div>
              <div class="value">{{ systemStatus.memory_used }}<span class="unit">GB / {{ systemStatus.memory_total }} GB</span></div>
            </div>
          </div>
          <el-progress :percentage="systemStatus.memory_percent" :show-text="false" :stroke-width="6" status="warning" />
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="icon-wrapper stat-disk-bg">
              <el-icon class="icon stat-disk-color"><Folder /></el-icon>
            </div>
            <div class="text">
              <div class="label">主机磁盘占用</div>
              <div class="value">{{ systemStatus.disk_used_gb }}<span class="unit">GB / {{ systemStatus.disk_total_gb }} GB</span></div>
            </div>
          </div>
          <el-progress :percentage="systemStatus.disk_percent" :show-text="false" :stroke-width="6" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 3. 正在运行的服务器资源监控 -->
    <el-card shadow="never" class="resource-monitor-card">
       <template #header>
        <div class="card-header">
          <span>资源监控</span>
          <span class="header-hint">仅显示运行中 · 每 5 秒刷新</span>
        </div>
      </template>
      <div v-if="runningServersUsage.length === 0" class="resource-empty">
        <el-empty description="当前没有正在运行的服务器" />
      </div>
      <el-row v-else :gutter="16" class="resource-grid">
        <el-col v-for="server in runningServersUsage" :key="server.id" :xs="24" :sm="12" :md="8" :lg="6">
          <el-card shadow="hover" class="server-usage-card">
            <div class="server-usage-header">
              <div class="server-usage-title">
                <div class="name" :title="server.name">{{ server.name }}</div>
                <div class="meta">
                  <el-tag type="success" effect="plain" size="small">运行中</el-tag>
                </div>
              </div>
              <el-tooltip v-if="hasRole('ADMIN')" content="控制台" placement="top">
                <el-button size="small" type="primary" :icon="Monitor" circle
                           @click="goToConsole(server.id)" />
              </el-tooltip>
            </div>

            <div class="server-usage-metrics">
              <div class="metric">
                <div class="metric-row">
                  <span class="metric-label">
                    <el-icon><Cpu /></el-icon>
                    CPU
                  </span>
                  <span class="metric-value">{{ formatCpuPercent(server.cpu_percent) }}</span>
                </div>
                <el-progress
                    :percentage="clampPercent(server.cpu_percent)"
                    :status="getUsageStatus(clampPercent(server.cpu_percent))"
                    :stroke-width="6"
                    :show-text="false"
                />
              </div>

              <div class="metric">
                <div class="metric-row">
                  <span class="metric-label">
                    <el-icon><DataLine /></el-icon>
                    内存
                  </span>
                  <span class="metric-value">{{ formatMemoryMb(server.memory_mb) }}</span>
                </div>
                <el-progress
                    :percentage="getMemoryPercent(server.memory_mb)"
                    :status="getUsageStatus(getMemoryPercent(server.memory_mb))"
                    :stroke-width="6"
                    :show-text="false"
                />
                <div class="metric-hint" v-if="hostMemoryTotalMb > 0">
                  占主机总内存 {{ getMemoryPercent(server.memory_mb).toFixed(1) }}%
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import apiClient, { isRequestCanceled } from '@/api';
import { UserFilled, Monitor, Tickets, Cpu, DataLine, Folder } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { useUserStore } from '@/store/user'
import { storeToRefs } from 'pinia'
const userStore = useUserStore()
const user = userStore.user
const { fullAvatarUrl, activeGroupIds } = storeToRefs(userStore)
const { hasRole } = userStore

interface SystemStatus {
  cpu_percent: number
  memory_percent: number
  memory_used: number
  memory_total: number
  disk_percent: number
  disk_used_gb: number
  disk_total_gb: number
}

interface ServerStats {
  total_servers: number
  running_servers: number
}

interface ServerUsage {
  id: number
  name: string
  cpu_percent: number
  memory_mb: number
}

interface ServerItem {
  id: number
  status: string
}

const router = useRouter();

const stats = ref<ServerStats>({ total_servers: 0, running_servers: 0 });
const serverPercent = computed(() => {
  const total = stats.value.total_servers;
  const running = stats.value.running_servers;
  if (!total) return 0;
  return Math.min(100, Math.max(0, Math.round((running / total) * 100)));
});
const systemStatus = ref<SystemStatus>({
  cpu_percent: 0,
  memory_percent: 0,
  memory_used: 0,
  memory_total: 0,
  disk_percent: 0,
  disk_used_gb: 0,
  disk_total_gb: 0,
});
const runningServersUsage = ref<ServerUsage[]>([]);

let refreshInterval: ReturnType<typeof setInterval> | null = null;

const clampPercent = (n: number) => Math.min(100, Math.max(0, Number(n) || 0));
const formatCpuPercent = (n: number) => `${clampPercent(n).toFixed(2)}%`;
const formatMemoryMb = (mb: number) => {
  const n = Number(mb);
  if (!Number.isFinite(n)) return '--';
  return `${Math.round(n).toLocaleString()} MB`;
};
const hostMemoryTotalMb = computed(() => (systemStatus.value.memory_total || 0) * 1024);
const getMemoryPercent = (mb: number) => {
  const totalMb = hostMemoryTotalMb.value;
  if (!totalMb) return 0;
  return clampPercent(((Number(mb) || 0) / totalMb) * 100);
};
const getUsageStatus = (p: number): '' | 'success' | 'warning' | 'exception' => {
  const n = Number(p) || 0;
  if (n >= 90) return 'exception';
  if (n >= 70) return 'warning';
  return 'success';
};

const fetchDashboardData = async () => {
  try {
    const [serversRes, systemRes, usageRes] = await Promise.all([
      apiClient.get('/api/servers'),
      apiClient.get('/api/system/status'),
      apiClient.get('/api/servers/resource-usage'),
    ]);
    const servers: ServerItem[] = Array.isArray(serversRes.data) ? serversRes.data : [];
    const running = servers.filter(s => s.status === 'running').length;
    stats.value = { total_servers: servers.length, running_servers: running };
    const s = systemRes.data || {};
    systemStatus.value = {
      cpu_percent: clampPercent(s.cpu_percent),
      memory_percent: clampPercent(s.memory_percent),
      memory_used: Number(s.memory_used) || 0,
      memory_total: Number(s.memory_total) || 0,
      disk_percent: clampPercent(s.disk_percent),
      disk_used_gb: Number(s.disk_used_gb) || 0,
      disk_total_gb: Number(s.disk_total_gb) || 0,
    };
    const runningIds = new Set(servers.filter(sv => sv.status === 'running').map(sv => sv.id));
    const usageList: ServerUsage[] = Array.isArray(usageRes.data) ? usageRes.data : [];
    runningServersUsage.value = usageList.filter(u => runningIds.has(u?.id));
  } catch (error) {
    if (isRequestCanceled(error)) return;
    ElMessage.error('获取仪表盘数据失败，请检查后端服务。');
    console.error(error);
    if (refreshInterval) {
      clearInterval(refreshInterval);
    }
  }
};

const goToConsole = (serverId: number) => {
  router.push(`/console/${serverId}`);
};

const startPolling = () => {
  if (refreshInterval) return;
  refreshInterval = setInterval(fetchDashboardData, 5000);
};

const stopPolling = () => {
  if (refreshInterval) {
    clearInterval(refreshInterval);
    refreshInterval = null;
  }
};

const handleVisibilityChange = () => {
  if (document.hidden) {
    stopPolling();
  } else {
    fetchDashboardData();
    startPolling();
  }
};

onMounted(() => {
  fetchDashboardData();
  startPolling();
  document.addEventListener('visibilitychange', handleVisibilityChange);
});

watch(activeGroupIds, () => {
  fetchDashboardData();
}, { deep: true });

onUnmounted(() => {
  stopPolling();
  document.removeEventListener('visibilitychange', handleVisibilityChange);
});
</script>

<style scoped>
.dashboard-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.welcome-card {
  background-color: var(--color-surface) !important;
}
.welcome-content {
  display: flex;
  align-items: center;
  gap: 20px;
}
.welcome-text .title {
  font-size: 20px;
  font-weight: 500;
  margin-bottom: 10px;
}
.welcome-text .subtitle {
  color: var(--el-text-color-secondary);
}

.stats-cards .el-card {
  border-radius: 8px;
}
.stats-cards .el-progress {
  margin-top: 10px;
}

.stat-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.stat-item .icon-wrapper {
  padding: 16px;
  border-radius: 6px;
  transition: all 0.3s ease-out;
}
.stat-item .icon {
  font-size: 48px;
}
.stat-item .text {
  text-align: right;
}
.stat-item .text .label {
  color: var(--el-text-color-secondary);
  font-size: 16px;
  margin-bottom: 12px;
}
.stat-item .text .value {
  font-size: 20px;
  font-weight: bold;
  color: var(--color-text);
}
.stat-item .text .unit {
  font-size: 14px;
  font-weight: normal;
  margin-left: 5px;
  color: var(--el-text-color-secondary);
}

/* 统计卡片色组（引用全局 theme.css 中的 CSS 变量） */
.stat-servers-bg { background: var(--stat-servers-bg); }
.stat-servers-color { color: var(--stat-servers-color); }
.stat-cpu-bg { background: var(--stat-cpu-bg); }
.stat-cpu-color { color: var(--stat-cpu-color); }
.stat-memory-bg { background: var(--stat-memory-bg); }
.stat-memory-color { color: var(--stat-memory-color); }
.stat-disk-bg { background: var(--stat-disk-bg); }
.stat-disk-color { color: var(--stat-disk-color); }

.el-col:hover .icon-wrapper {
    transform: translateY(-5px);
}
.card-header {
  font-weight: bold;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.header-hint {
  font-weight: normal;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.resource-empty {
  padding: 20px 0;
}

.resource-grid {
  padding: 4px 2px 2px;
}

.server-usage-card {
  border-radius: 12px;
  border: 1px solid var(--el-border-color-lighter);
  background: linear-gradient(180deg, rgba(54, 163, 247, 0.06) 0%, var(--color-surface) 70%) !important;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.server-usage-card:hover {
  transform: translateY(-2px);
}

.server-usage-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.server-usage-title {
  min-width: 0;
  flex: 1;
}
.server-usage-title .name {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.server-usage-title .meta {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.server-usage-metrics {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.metric-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
}
.metric-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.metric-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  font-variant-numeric: tabular-nums;
}
.metric-hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.server-usage-card :deep(.el-progress-bar__outer) {
  border-radius: 999px;
}
.server-usage-card :deep(.el-progress-bar__inner) {
  border-radius: 999px;
}
</style>
