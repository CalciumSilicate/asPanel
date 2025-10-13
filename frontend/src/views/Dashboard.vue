<template>
  <div class="dashboard-container">
    <!-- 1. 欢迎卡片 -->
    <el-card shadow="never" class="welcome-card">
      <div class="welcome-content">
        <!-- 此处正确使用了 store 中的 fullAvatarUrl，无需修改 -->
        <el-avatar :size="70" :src="fullAvatarUrl" :icon="UserFilled" />
        <div class="welcome-text">
          <div class="title">欢迎回来, {{ user.username || 'admin' }}!</div>
          <div class="subtitle">这是您的服务器状态总览。</div>
        </div>
      </div>
    </el-card>

    <!-- 2. 核心数据统计 -->
    <el-row :gutter="20" class="stats-cards">
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="hover">
          <div class="stat-item">
            <div class="icon-wrapper" style="background: #e7f6f6;">
              <el-icon class="icon" color="#40c9c6"><Tickets /></el-icon>
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
            <div class="icon-wrapper" style="background: #eaf3fe;">
              <el-icon class="icon" color="#36a3f7"><Cpu /></el-icon>
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
            <div class="icon-wrapper" style="background: #fef5f5;">
              <el-icon class="icon" color="#f4516c"><DataLine /></el-icon>
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
            <div class="icon-wrapper" style="background: #f3eefc;">
              <el-icon class="icon" color="#9575cd"><Folder /></el-icon>
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
    <el-card shadow="never">
       <template #header>
        <div class="card-header">
          <span>资源监控 (正在运行的服务器)</span>
        </div>
      </template>
      <el-table :data="runningServersUsage" style="width: 100%" empty-text="当前没有正在运行的服务器">
        <el-table-column prop="name" label="服务器名称" />
        <el-table-column prop="cpu_percent" label="CPU 使用率" width="180" align="center">
          <template #default="scope">
            {{ scope.row.cpu_percent.toFixed(2) }} %
          </template>
        </el-table-column>
        <el-table-column prop="memory_mb" label="内存占用 (MB)" width="180" align="center" />
        <el-table-column label="操作" width="120" align="center">
           <template #default="scope">
              <el-button size="small" type="primary" @click="goToConsole(scope.row.id)" :icon="Monitor">
                控制台
              </el-button>
           </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import apiClient from '@/api';
import { UserFilled, Monitor, Tickets, Cpu, DataLine, Folder } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { user, fullAvatarUrl } from '@/store/user';

const router = useRouter();

const stats = ref({ total_servers: 0, running_servers: 0 });
const serverPercent = computed(() => {
  const total = Number(stats.value.total_servers) || 0;
  const running = Number(stats.value.running_servers) || 0;
  if (!total) return 0;
  const p = Math.round((running / total) * 100);
  return Math.min(100, Math.max(0, p));
});
const systemStatus = ref({
  cpu_percent: 0,
  memory_percent: 0,
  memory_used: 0,
  memory_total: 0,
  disk_percent: 0,
  disk_used_gb: 0,
  disk_total_gb: 0,
});
const runningServersUsage = ref([]);

let refreshInterval = null;

const fetchDashboardData = async () => {
  try {
    const [serversRes, systemRes, usageRes] = await Promise.all([
      apiClient.get('/api/servers'),
      apiClient.get('/api/system/status'),
      apiClient.get('/api/servers/resource-usage'),
    ]);
    const servers = Array.isArray(serversRes.data) ? serversRes.data : [];
    const running = servers.filter(s => s.status === 'running').length;
    stats.value = { total_servers: servers.length, running_servers: running };
    // 规范化并夹紧系统百分比，确保 0-100
    const s = systemRes.data || {};
    const clamp = (n) => Math.min(100, Math.max(0, Number(n) || 0));
    systemStatus.value = {
      ...systemStatus.value,
      cpu_percent: clamp(s.cpu_percent),
      memory_percent: clamp(s.memory_percent),
      memory_used: Number(s.memory_used) || 0,
      memory_total: Number(s.memory_total) || 0,
      disk_percent: clamp(s.disk_percent),
      disk_used_gb: Number(s.disk_used_gb) || 0,
      disk_total_gb: Number(s.disk_total_gb) || 0,
    };
    runningServersUsage.value = Array.isArray(usageRes.data) ? usageRes.data : [];
  } catch (error) {
    ElMessage.error('获取仪表盘数据失败，请检查后端服务。');
    console.error(error);
    if (refreshInterval) {
      clearInterval(refreshInterval);
    }
  }
};

const goToConsole = (serverId) => {
  router.push(`/console/${serverId}`);
};

onMounted(() => {
  fetchDashboardData();
  refreshInterval = setInterval(fetchDashboardData, 5000);
});

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval);
  }
});
</script>

<style scoped>
.dashboard-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.welcome-card {
  background-color: #fff;
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
  color: #999;
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
  color: rgba(0,0,0,.45);
  font-size: 16px;
  margin-bottom: 12px;
}
.stat-item .text .value {
  font-size: 20px;
  font-weight: bold;
  color: #666;
}
.stat-item .text .unit {
  font-size: 14px;
  font-weight: normal;
  margin-left: 5px;
  color: #999;
}
.el-col:hover .icon-wrapper {
    transform: translateY(-5px);
}
.card-header {
  font-weight: bold;
}
</style>
