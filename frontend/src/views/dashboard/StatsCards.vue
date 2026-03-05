<template>
  <el-row :gutter="20" class="stats-cards">
    <el-col :xs="24" :sm="12" :lg="6">
      <el-card shadow="hover">
        <div class="stat-item">
          <div class="icon-wrapper stat-servers-bg">
            <el-icon class="icon stat-servers-color"><Tickets /></el-icon>
          </div>
          <div class="text">
            <div class="label">服务器状态</div>
            <div class="value">
              {{ stats.running_servers }}
              <span class="unit">/ {{ stats.total_servers }} 运行中</span>
            </div>
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
            <div class="value">
              {{ systemStatus.memory_used }}
              <span class="unit">GB / {{ systemStatus.memory_total }} GB</span>
            </div>
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
            <div class="value">
              {{ systemStatus.disk_used_gb }}
              <span class="unit">GB / {{ systemStatus.disk_total_gb }} GB</span>
            </div>
          </div>
        </div>
        <el-progress :percentage="systemStatus.disk_percent" :show-text="false" :stroke-width="6" />
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup lang="ts">
import { Tickets, Cpu, DataLine, Folder } from '@element-plus/icons-vue'
import type { SystemStatus, ServerStats } from '@/composables/useDashboard'

defineProps<{
  stats: ServerStats
  systemStatus: SystemStatus
  serverPercent: number
}>()
</script>

<style scoped>
.stats-cards .el-card { border-radius: 8px; }
.stats-cards .el-progress { margin-top: 10px; }

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
.stat-item .icon { font-size: 48px; }
.stat-item .text { text-align: right; }
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

.el-col:hover .icon-wrapper { transform: translateY(-5px); }

.stat-servers-bg { background: var(--stat-servers-bg); }
.stat-servers-color { color: var(--stat-servers-color); }
.stat-cpu-bg { background: var(--stat-cpu-bg); }
.stat-cpu-color { color: var(--stat-cpu-color); }
.stat-memory-bg { background: var(--stat-memory-bg); }
.stat-memory-color { color: var(--stat-memory-color); }
.stat-disk-bg { background: var(--stat-disk-bg); }
.stat-disk-color { color: var(--stat-disk-color); }
</style>
