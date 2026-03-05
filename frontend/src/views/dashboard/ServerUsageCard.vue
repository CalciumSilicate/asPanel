<template>
  <el-card shadow="hover" class="server-usage-card">
    <div class="server-usage-header">
      <div class="server-usage-title">
        <div class="name" :title="server.name">{{ server.name }}</div>
        <div class="meta">
          <el-tag type="success" effect="plain" size="small">运行中</el-tag>
        </div>
      </div>
      <el-tooltip v-if="showConsole" content="控制台" placement="top">
        <el-button size="small" type="primary" :icon="Monitor" circle @click="emit('console', server.id)" />
      </el-tooltip>
    </div>

    <div class="server-usage-metrics">
      <div class="metric">
        <div class="metric-row">
          <span class="metric-label"><el-icon><Cpu /></el-icon>CPU</span>
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
          <span class="metric-label"><el-icon><DataLine /></el-icon>内存</span>
          <span class="metric-value">{{ formatMemoryMb(server.memory_mb) }}</span>
        </div>
        <el-progress
          :percentage="memoryPercent"
          :status="getUsageStatus(memoryPercent)"
          :stroke-width="6"
          :show-text="false"
        />
        <div class="metric-hint" v-if="hostMemoryTotalMb > 0">
          占主机总内存 {{ memoryPercent.toFixed(1) }}%
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Monitor, Cpu, DataLine } from '@element-plus/icons-vue'
import type { ServerUsage } from '@/composables/useDashboard'
import { clampPercent, formatCpuPercent, formatMemoryMb, getUsageStatus } from '@/utils/metrics'

const props = defineProps<{
  server: ServerUsage
  hostMemoryTotalMb: number
  showConsole: boolean
}>()

const emit = defineEmits<{ console: [id: number] }>()

const memoryPercent = computed(() => {
  if (!props.hostMemoryTotalMb) return 0
  return clampPercent(((Number(props.server.memory_mb) || 0) / props.hostMemoryTotalMb) * 100)
})
</script>

<style scoped>
.server-usage-card {
  border-radius: 12px;
  border: 1px solid var(--el-border-color-lighter);
  background: linear-gradient(180deg, rgba(54, 163, 247, 0.06) 0%, var(--color-surface) 70%) !important;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.server-usage-card:hover { transform: translateY(-2px); }

.server-usage-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.server-usage-title { min-width: 0; flex: 1; }
.server-usage-title .name {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.server-usage-title .meta { margin-top: 8px; display: flex; align-items: center; gap: 10px; }

.server-usage-metrics { margin-top: 14px; display: flex; flex-direction: column; gap: 12px; }

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
.metric-hint { margin-top: 6px; font-size: 12px; color: var(--el-text-color-secondary); }

:deep(.el-progress-bar__outer),
:deep(.el-progress-bar__inner) { border-radius: 999px; }
</style>
